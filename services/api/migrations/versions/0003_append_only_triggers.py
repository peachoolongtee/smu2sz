"""Make `operations` and `used_nonces` append-only in the database itself (F-11).

SQLite: BEFORE UPDATE / BEFORE DELETE triggers that RAISE(ABORT).
Postgres: a PL/pgSQL function raising `insufficient_privilege`, bound by row triggers (UPDATE,
DELETE) and a statement trigger (TRUNCATE) on each table. The function lets a statement through
only when the transaction-local setting `termsledger.allow_reset` is 'on', which only
`SqlLedgerStore.reset()` sets (with SET LOCAL, so it ends with that transaction).

The statements are frozen here; `app/persistence/guards.py` creates the same triggers, by the same
names, for stores opened with `create_tables=True`. The hash chain is still computed in Python
(ADR-0001); the triggers only refuse edits. Leaves 0002's RLS untouched.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = ("operations", "used_nonces")

PG_FUNCTION = """
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


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in TABLES:
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_{action.lower()} BEFORE {action} ON {table} "
                    f"BEGIN SELECT RAISE(ABORT, '{table} is append-only; {action} refused'); END"
                )
    elif dialect == "postgresql":
        op.execute(PG_FUNCTION)
        for table in TABLES:
            op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_append_only ON "{table}"')
            op.execute(
                f'CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON "{table}" '
                "FOR EACH ROW EXECUTE FUNCTION termsledger_append_only()"
            )
            op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON "{table}"')
            op.execute(
                f'CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON "{table}" '
                "FOR EACH STATEMENT EXECUTE FUNCTION termsledger_append_only()"
            )
        # The function is internal; nobody but the owner needs to call it (0002 revoked table access).
        op.execute("REVOKE ALL ON FUNCTION termsledger_append_only() FROM PUBLIC")


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in TABLES:
            for action in ("update", "delete"):
                op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_{action}")
    elif dialect == "postgresql":
        for table in TABLES:
            op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_append_only ON "{table}"')
            op.execute(f'DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON "{table}"')
        op.execute("DROP FUNCTION IF EXISTS termsledger_append_only()")
