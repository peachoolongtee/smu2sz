"""Guard the rest of the audit trail in the database itself (SEC-08).

- `security_events` becomes append-only, like `operations` and `used_nonces` (0003).
- `approvals`: a PENDING approval can be decided once (APPROVED or REJECTED, with who and when), and nothing else about a row can change;
  no approval row can be deleted. Before this, a rejected approval reset to PENDING in the database was then approved and executed with
  the hash chain still valid (reproduced on SQLite and PostgreSQL 17).
- Postgres: `termsledger_append_only()` no longer lets a statement through when the session setting `termsledger.allow_reset` is on
  (any session could set it). The demo reset now lifts the guards with ALTER TABLE ... DISABLE TRIGGER inside its own transaction, which
  needs the table owner's rights.

The statements are frozen here; `app/persistence/guards.py` creates the same triggers, by the same names, for stores opened with
`create_tables=True`.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

APPEND_ONLY = "security_events"

PG_APPEND_ONLY = """
CREATE OR REPLACE FUNCTION termsledger_append_only() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION USING
        MESSAGE = TG_TABLE_NAME || ' is append-only; ' || TG_OP || ' refused',
        ERRCODE = 'insufficient_privilege';
END;
$$
"""

PG_APPEND_ONLY_0003 = """
CREATE OR REPLACE FUNCTION termsledger_append_only() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF current_setting('termsledger.allow_reset', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    RAISE EXCEPTION USING
        MESSAGE = TG_TABLE_NAME || ' is append-only; ' || TG_OP || ' refused',
        ERRCODE = 'insufficient_privilege';
END;
$$
"""

PG_DECIDE_ONCE = """
CREATE OR REPLACE FUNCTION termsledger_decide_once() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'PENDING' AND NEW.status IN ('APPROVED', 'REJECTED')
       AND NEW.row_id = OLD.row_id AND NEW.id = OLD.id AND NEW.op_json = OLD.op_json AND NEW.reason = OLD.reason
       AND NEW.op_id IS NOT DISTINCT FROM OLD.op_id AND NEW.kind IS NOT DISTINCT FROM OLD.kind THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION USING
        MESSAGE = 'approvals: a decision is recorded once; ' || TG_OP || ' refused',
        ERRCODE = 'insufficient_privilege';
END;
$$
"""

SQLITE_UP = (
    (
        "CREATE TRIGGER IF NOT EXISTS trg_security_events_no_update BEFORE UPDATE ON security_events "
        "BEGIN SELECT RAISE(ABORT, 'security_events is append-only; UPDATE refused'); END"
    ),
    (
        "CREATE TRIGGER IF NOT EXISTS trg_security_events_no_delete BEFORE DELETE ON security_events "
        "BEGIN SELECT RAISE(ABORT, 'security_events is append-only; DELETE refused'); END"
    ),
    (
        "CREATE TRIGGER IF NOT EXISTS trg_approvals_decide_once BEFORE UPDATE ON approvals "
        "WHEN NOT (OLD.status = 'PENDING' AND NEW.status IN ('APPROVED', 'REJECTED') AND NEW.row_id IS OLD.row_id "
        "AND NEW.id IS OLD.id AND NEW.op_id IS OLD.op_id AND NEW.kind IS OLD.kind AND NEW.op_json IS OLD.op_json "
        "AND NEW.reason IS OLD.reason) "
        "BEGIN SELECT RAISE(ABORT, 'approvals: a decision is recorded once; UPDATE refused'); END"
    ),
    (
        "CREATE TRIGGER IF NOT EXISTS trg_approvals_no_delete BEFORE DELETE ON approvals "
        "BEGIN SELECT RAISE(ABORT, 'approvals: a decision is recorded once; DELETE refused'); END"
    ),
)
SQLITE_NAMES = ("trg_security_events_no_update", "trg_security_events_no_delete", "trg_approvals_decide_once",
                "trg_approvals_no_delete")


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for stmt in SQLITE_UP:
            op.execute(stmt)
    elif dialect == "postgresql":
        op.execute(PG_APPEND_ONLY)
        op.execute(PG_DECIDE_ONCE)
        op.execute(f'DROP TRIGGER IF EXISTS trg_{APPEND_ONLY}_append_only ON "{APPEND_ONLY}"')
        op.execute(f'CREATE TRIGGER trg_{APPEND_ONLY}_append_only BEFORE UPDATE OR DELETE ON "{APPEND_ONLY}" '
                   "FOR EACH ROW EXECUTE FUNCTION termsledger_append_only()")
        op.execute(f'DROP TRIGGER IF EXISTS trg_{APPEND_ONLY}_no_truncate ON "{APPEND_ONLY}"')
        op.execute(f'CREATE TRIGGER trg_{APPEND_ONLY}_no_truncate BEFORE TRUNCATE ON "{APPEND_ONLY}" '
                   "FOR EACH STATEMENT EXECUTE FUNCTION termsledger_append_only()")
        op.execute('DROP TRIGGER IF EXISTS trg_approvals_decide_once ON "approvals"')
        op.execute('CREATE TRIGGER trg_approvals_decide_once BEFORE UPDATE OR DELETE ON "approvals" '
                   "FOR EACH ROW EXECUTE FUNCTION termsledger_decide_once()")
        op.execute('DROP TRIGGER IF EXISTS trg_approvals_no_truncate ON "approvals"')
        op.execute('CREATE TRIGGER trg_approvals_no_truncate BEFORE TRUNCATE ON "approvals" '
                   "FOR EACH STATEMENT EXECUTE FUNCTION termsledger_append_only()")
        op.execute("REVOKE ALL ON FUNCTION termsledger_decide_once() FROM PUBLIC")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for name in SQLITE_NAMES:
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
    elif dialect == "postgresql":
        for table, name in ((APPEND_ONLY, f"trg_{APPEND_ONLY}_append_only"), (APPEND_ONLY, f"trg_{APPEND_ONLY}_no_truncate"),
                            ("approvals", "trg_approvals_decide_once"), ("approvals", "trg_approvals_no_truncate")):
            op.execute(f'DROP TRIGGER IF EXISTS {name} ON "{table}"')
        op.execute("DROP FUNCTION IF EXISTS termsledger_decide_once()")
        op.execute(PG_APPEND_ONLY_0003)
