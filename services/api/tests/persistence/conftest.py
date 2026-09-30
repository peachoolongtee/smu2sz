from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.persistence import InMemoryLedgerStore, SqlLedgerStore


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[InMemoryLedgerStore | SqlLedgerStore]:
    """Every contract test runs against both implementations."""
    if request.param == "memory":
        yield InMemoryLedgerStore()
        return
    sql = SqlLedgerStore(f"sqlite:///{tmp_path / 'ledger.db'}")
    yield sql
    sql.dispose()


@pytest.fixture
def sql_store(tmp_path: Path) -> Iterator[SqlLedgerStore]:
    sql = SqlLedgerStore(f"sqlite:///{tmp_path / 'ledger.db'}")
    yield sql
    sql.dispose()
