"""Alembic migration 0001 on a temp SQLite file: creates every table and matches tables.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.persistence import SqlLedgerStore
from app.persistence.tables import metadata

API_DIR = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "organizations",
    "counterparties",
    "offers",
    "obligations",
    "facilities",
    "mandates",
    "states",
    "verdicts",
    "commitments",
    "operations",
    "used_nonces",
    "approvals",
    "security_events",
    "llm_calls",
    "evaluation_runs",
    "evidence_exports",
}


def _config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


def test_upgrade_head_creates_every_table_and_matches_the_metadata(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_config(url), "head")

    engine = create_engine(url)
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names()) - {"alembic_version"}
        assert tables == EXPECTED_TABLES == {tb.name for tb in metadata.sorted_tables}
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), metadata)
        assert diff == []
    engine.dispose()

    store = SqlLedgerStore(url, create_tables=False)
    store.append_operation("OP-1", "DRAW_FACILITY", "k-1", "{}", '{"status":"EXECUTED"}')
    store.mark_nonce_used("n-1")
    assert store.verify_chain() is True
    store.dispose()


def test_downgrade_base_drops_every_table(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'down.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(url)
    with engine.connect() as conn:
        assert set(inspect(conn).get_table_names()) <= {"alembic_version"}
    engine.dispose()


def test_alembic_cli_reads_database_url(tmp_path: Path):
    db = tmp_path / "cli.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}"}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        assert EXPECTED_TABLES <= set(inspect(conn).get_table_names())
    engine.dispose()
