"""Database-level guards on the audit trail (F-11, SEC-08).

The engine hook in `sql_store` refuses SQLAlchemy Core UPDATE/DELETE on the log, but a textual statement on the same connection
bypasses it. These triggers make the database itself refuse, whatever the client:

- any UPDATE or DELETE (and, on Postgres, TRUNCATE) on the append-only tables: the operations log, the used nonces and the
  security events;
- on `approvals`, anything but deciding a PENDING approval once: PENDING becomes APPROVED or REJECTED with who decided and the day,
  and nothing else about the row changes. A decided approval cannot be put back to PENDING (the SEC-08 flip: a rejected Tier-2
  operation reset to pending in the database and then approved and executed, with the hash chain still valid), and no approval
  row can be deleted.

SQLite: BEFORE triggers that `RAISE(ABORT)`. Postgres: PL/pgSQL functions raising `insufficient_privilege`, bound by row triggers
(UPDATE, DELETE) and a statement trigger (TRUNCATE) on each table.

`reset()` (the demo reset) is the only sanctioned delete. It lifts the guards inside its own transaction only: on SQLite it drops the
triggers and recreates them before the transaction commits; on Postgres it disables the tables' triggers with ALTER TABLE, which
needs the table owner's rights, and enables them again before the commit. Both are transactional DDL, so a failure restores them.
(Until SEC-08 the Postgres functions let a statement through when the session setting `termsledger.allow_reset` was on, which any
session could set without any privilege.)

This is defence in depth, not the audit guarantee: a client with arbitrary SQL as the table owner can still drop a trigger. Run the
API as a role that does not own the tables to close that; the hash chain (`verify_chain`) is what detects an edit to the log.

Migrations 0003 and 0009 install the same triggers (by name) on a migrated database; the SQLite statements use IF NOT EXISTS so a store
opened with `create_tables=True` on a migrated file changes nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection

PROTECTED_TABLES = ("operations", "used_nonces", "security_events")  # append-only
DECIDE_ONCE_TABLE = "approvals"
GUARDED_TABLES = (*PROTECTED_TABLES, DECIDE_ONCE_TABLE)  # every table a reset must lift the guard on
PG_FUNCTION = "termsledger_append_only"
PG_DECIDE_ONCE = "termsledger_decide_once"
PG_INSTALL_LOCK = 0x544C4755  # "TLGU": the advisory-lock key the guard installers serialise on

_DECIDED = "('APPROVED', 'REJECTED')"


def _sqlite_trigger(table: str, action: str) -> tuple[str, str]:
    name = f"trg_{table}_no_{action.lower()}"
    create = (
        f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is append-only; {action} refused'); END"
    )
    return name, create


SQLITE_TRIGGERS: tuple[tuple[str, str], ...] = (
    *(_sqlite_trigger(table, action) for table in PROTECTED_TABLES for action in ("UPDATE", "DELETE")),
    (
        "trg_approvals_decide_once",
        (
            "CREATE TRIGGER IF NOT EXISTS trg_approvals_decide_once BEFORE UPDATE ON approvals "
            f"WHEN NOT (OLD.status = 'PENDING' AND NEW.status IN {_DECIDED} AND NEW.row_id IS OLD.row_id AND NEW.id IS OLD.id "
            "AND NEW.op_id IS OLD.op_id AND NEW.kind IS OLD.kind AND NEW.op_json IS OLD.op_json AND NEW.reason IS OLD.reason) "
            "BEGIN SELECT RAISE(ABORT, 'approvals: a decision is recorded once; UPDATE refused'); END"
        ),
    ),
    (
        "trg_approvals_no_delete",
        (
            "CREATE TRIGGER IF NOT EXISTS trg_approvals_no_delete BEFORE DELETE ON approvals "
            "BEGIN SELECT RAISE(ABORT, 'approvals: a decision is recorded once; DELETE refused'); END"
        ),
    ),
)

PG_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION {PG_FUNCTION}() RETURNS trigger
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

PG_DECIDE_ONCE_SQL = f"""
CREATE OR REPLACE FUNCTION {PG_DECIDE_ONCE}() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = 'PENDING' AND NEW.status IN {_DECIDED}
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

# (table, trigger name) of every Postgres trigger, for the "already installed" check
PG_TRIGGERS: tuple[tuple[str, str], ...] = (
    *((t, f"trg_{t}_{kind}") for t in PROTECTED_TABLES for kind in ("append_only", "no_truncate")),
    (DECIDE_ONCE_TABLE, "trg_approvals_decide_once"),
    (DECIDE_ONCE_TABLE, "trg_approvals_no_truncate"),
)


def pg_trigger_statements() -> list[str]:
    out = [PG_FUNCTION_SQL, PG_DECIDE_ONCE_SQL]
    for table in PROTECTED_TABLES:
        out += [
            f'DROP TRIGGER IF EXISTS trg_{table}_append_only ON "{table}"',
            (
                f'CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON "{table}" '
                f"FOR EACH ROW EXECUTE FUNCTION {PG_FUNCTION}()"
            ),
            f'DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON "{table}"',
            (
                f'CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON "{table}" '
                f"FOR EACH STATEMENT EXECUTE FUNCTION {PG_FUNCTION}()"
            ),
        ]
    table = DECIDE_ONCE_TABLE
    out += [
        f'DROP TRIGGER IF EXISTS trg_{table}_decide_once ON "{table}"',
        f'CREATE TRIGGER trg_{table}_decide_once BEFORE UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION {PG_DECIDE_ONCE}()',
        f'DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON "{table}"',
        f'CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON "{table}" FOR EACH STATEMENT EXECUTE FUNCTION {PG_FUNCTION}()',
    ]
    return out


def install(conn: Connection) -> None:
    """Create the triggers (idempotent). Other dialects are left alone."""
    dialect = conn.dialect.name
    if dialect == "sqlite":
        for _name, create in SQLITE_TRIGGERS:
            conn.exec_driver_sql(create)
    elif dialect == "postgresql":
        # Every store re-installs the guard when it opens. Two processes opening at once raced on the catalog ("tuple concurrently
        # updated") and one failed to start; a transaction-scoped advisory lock makes the installers take turns.
        conn.exec_driver_sql(f"SELECT pg_advisory_xact_lock({PG_INSTALL_LOCK})")
        if _pg_installed(conn):
            return  # already in place: no DDL, so no table lock that a crashed worker's open transaction could hold up
        for stmt in pg_trigger_statements():
            conn.exec_driver_sql(stmt)


def _pg_installed(conn: Connection) -> bool:
    """Whether both guard functions (with these exact bodies) and every trigger are already in place."""
    for name, sql in ((PG_FUNCTION, PG_FUNCTION_SQL), (PG_DECIDE_ONCE, PG_DECIDE_ONCE_SQL)):
        current = conn.exec_driver_sql("SELECT prosrc FROM pg_proc WHERE proname = %(f)s", {"f": name}).scalar()
        if current != sql.split("$$")[1]:
            return False
    names = [name for _table, name in PG_TRIGGERS]
    found = conn.exec_driver_sql("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname = ANY(%(n)s)",
                                 {"n": names}).scalar()
    return found == len(names)


@contextmanager
def lifted(conn: Connection) -> Iterator[None]:
    """Allow DELETE on the guarded tables for the rest of `conn`'s open transaction only.

    The caller must already have written in this transaction (on SQLite, pysqlite opens the
    transaction lazily at the first DML statement, and DDL before it would autocommit)."""
    dialect = conn.dialect.name
    if dialect == "sqlite":
        for name, _create in SQLITE_TRIGGERS:
            conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {name}")
        yield
        for _name, create in SQLITE_TRIGGERS:
            conn.exec_driver_sql(create)
    elif dialect == "postgresql":
        # ALTER TABLE needs the table owner's rights; a session setting, which any session could set, no longer lifts anything
        for table in GUARDED_TABLES:
            conn.exec_driver_sql(f'ALTER TABLE "{table}" DISABLE TRIGGER USER')
        yield
        for table in GUARDED_TABLES:
            conn.exec_driver_sql(f'ALTER TABLE "{table}" ENABLE TRIGGER USER')
    else:
        yield
