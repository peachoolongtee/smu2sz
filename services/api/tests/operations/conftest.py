from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.operations import Executor
from tests.operations.builders import Clock, make_executor, seeded_store


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Any]:
    """Every executor test runs against both stores, seeded from golden_sme with the SIGNED mandate."""
    s = seeded_store(request.param, f"sqlite:///{tmp_path / 'ledger.db'}")
    yield s
    if request.param == "sqlite":
        s.dispose()


@pytest.fixture
def clock() -> Clock:
    return Clock(0)


@pytest.fixture
def ex(store: Any, clock: Clock) -> Executor:
    return make_executor(store, clock)
