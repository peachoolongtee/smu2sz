"""Database-level append-only guard for `operations` and `used_nonces` (F-11).

The engine hook in `sql_store` refuses SQLAlchemy Core UPDATE/DELETE on the log, but a textual
statement on the same connection bypasses it. These triggers make the database itself refuse any
UPDATE or DELETE (and, on Postgres, TRUNCATE) on the two append-only tables, whatever the client.

- SQLite: BEFORE UPDATE / BEFORE DELETE triggers that `RAISE(ABORT)`.
- Postgres: one PL/pgSQL function raising `insufficient_privilege`, bound by row triggers
  (UPDATE, DELETE) and a statement trigger (TRUNCATE) on each table.

`reset()` (the demo reset) is the only sanctioned delete. It lifts the guard inside its own
transaction only: on SQLite it drops the triggers and recreates them before the transaction
commits (SQLite DDL is transactional, so a failure restores them); on Postgres it sets the
transaction-local `termsledger.allow_reset` setting that the function checks (`SET LOCAL` ends with
the transaction). Neither survives the reset's transaction.

This is defence in depth, not the audit guarantee: a client with arbitrary SQL as the table owner
can still drop a trigger. The hash chain (`verify_chain`) is what detects any edit.

Migration 0003 installs the same triggers (by name) on a migrated database; the SQLite statements
use IF NOT EXISTS so a store opened with `create_tables=True` on a migrated file changes nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection

PROTECTED_TABLES = ("operations", "used_nonces")
PG_FUNCTION = "termsledger_append_only"
PG_RESET_SETTING = "termsledger.allow_reset"
PG_INSTALL_LOCK = 0x544C4755  # "TLGU": the advisory-lock key the guard installers serialise on


def _sqlite_trigger(table: str, action: str) -> tuple[str, str]:
    name = f"trg_{table}_no_{action.lower()}"
    create = (
        f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{table} is append-only; {action} refused'); END"
    )
    return name, create


SQLITE_TRIGGERS: tuple[tuple[str, str], ...] = tuple(
    _sqlite_trigger(table, action) for table in PROTECTED_TABLES for action in ("UPDATE", "DELETE")
)

PG_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION {PG_FUNCTION}() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    IF current_setting('{PG_RESET_SETTING}', true) = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    RAISE EXCEPTION USING
        MESSAGE = TG_TABLE_NAME || ' is append-only; ' || TG_OP || ' refused',
        ERRCODE = 'insufficient_privilege';
END;
$$
"""


def pg_trigger_statements() -> list[str]:
    out = [PG_FUNCTION_SQL]
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
    """Whether the guard function (with this exact body) and every trigger are already in place."""
    body = PG_FUNCTION_SQL.split("$$")[1]
    current = conn.exec_driver_sql("SELECT prosrc FROM pg_proc WHERE proname = %(f)s", {"f": PG_FUNCTION}).scalar()
    if current != body:
        return False
    names = [f"trg_{t}_{kind}" for t in PROTECTED_TABLES for kind in ("append_only", "no_truncate")]
    found = conn.exec_driver_sql("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname = ANY(%(n)s)",
                                 {"n": names}).scalar()
    return found == len(names)


@contextmanager
def lifted(conn: Connection) -> Iterator[None]:
    """Allow DELETE on the protected tables for the rest of `conn`'s open transaction only.

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
        conn.exec_driver_sql(f"SET LOCAL {PG_RESET_SETTING} = 'on'")
        yield
        conn.exec_driver_sql(f"SET LOCAL {PG_RESET_SETTING} = 'off'")
    else:
        yield
