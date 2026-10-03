"""Fixtures for the two-process concurrency certification.

Every test runs on three engines: `sqlite-immediate` and `sqlite-deferred` (a fresh file database per test) and
`postgres`, which runs only when TERMSLEDGER_TEST_DATABASE_URL is set (skipped otherwise) and only against an
empty database or one this suite created (`claim_postgres` refuses anything else)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.concurrency.harness import PG_ENV, Engine, WorkerPair, claim_postgres, engine_for, open_store


@pytest.fixture(scope="session")
def workers() -> Iterator[WorkerPair]:
    pair = WorkerPair()
    yield pair
    pair.close()


@pytest.fixture(params=["sqlite-immediate", "sqlite-deferred", "postgres"])
def engine(request: pytest.FixtureRequest, tmp_path: Path) -> Engine:
    if request.param == "postgres":
        if not os.environ.get(PG_ENV):
            pytest.skip(f"{PG_ENV} is not set: the PostgreSQL variant is UNVERIFIED in this run")
        claim_postgres(os.environ[PG_ENV])  # refuses (raises) unless the database is empty or test-created
    return engine_for(request.param, tmp_path)


@pytest.fixture
def books(engine: Engine) -> Iterator[Any]:
    """The parent's own connection: creates the schema, seeds, and inspects the books afterwards."""
    store = open_store(engine, create=True)
    yield store
    store.dispose()
