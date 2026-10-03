"""The store's compare-and-swap contract, on two connections in one process (the two-process proofs are in
tests/concurrency): state version, log head, `BEGIN IMMEDIATE`, and the executor running a lost unit again."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.domain.fixtures import load_scenario
from app.domain.models import DrawFacility, OperationStatus
from app.persistence import (
    ConcurrentWriteConflict,
    SqlLedgerStore,
    StateVersionConflict,
    is_retryable,
)
from tests.operations.builders import Clock, make_executor, op, seeded_store


def _state(version: int, cash: int = 1) -> Any:
    state, _ = load_scenario()
    return state.model_copy(update={"state_version": version, "cash_fen": cash})


def test_put_state_with_the_expected_version_writes_and_with_another_refuses(store: Any) -> None:
    store.put_state(_state(1))
    store.put_state(_state(2, cash=2), expected_version=1)
    assert store.get_state().state_version == 2
    with pytest.raises(StateVersionConflict):
        store.put_state(_state(3, cash=3), expected_version=1)  # computed from version 1, the books are at 2
    assert [s.state_version for s in store.state_history()] == [1, 2] and store.get_state().cash_fen == 2
    store.put_state(_state(2, cash=9))  # without an expected version: unconditional, as before (fixtures, seeding)
    assert store.get_state().cash_fen == 9


def test_a_refused_compare_and_swap_rolls_back_its_unit_of_work(store: Any) -> None:
    store.put_state(_state(1))
    with pytest.raises(StateVersionConflict), store.transaction():
        store.append_operation("OP-1", "DRAW_FACILITY", "k-1", "{}", '{"status":"EXECUTED"}')
        store.put_state(_state(2), expected_version=7)
    assert store.operations() == [] and len(store.state_history()) == 1


@pytest.fixture
def two(tmp_path: Path) -> Iterator[tuple[SqlLedgerStore, SqlLedgerStore]]:
    url = f"sqlite:///{(tmp_path / 'two.db').as_posix()}"
    a = SqlLedgerStore(url, sqlite_begin="deferred")
    b = SqlLedgerStore(url, create_tables=False, sqlite_begin="deferred")
    yield a, b
    a.dispose()
    b.dispose()


def test_a_unit_that_read_before_another_writer_committed_cannot_append(two: Any) -> None:
    a, b = two
    a.put_state(_state(1))
    with pytest.raises(ConcurrentWriteConflict, match="log head moved"), a.transaction():
        assert a.get_state().state_version == 1  # a decides on these books ...
        b.append_operation("OP-B", "RECEIVE_PAYMENT", "k-b", "{}", '{"status":"EXECUTED"}')  # ... b commits ...
        a.append_operation("OP-A", "DRAW_FACILITY", "k-a", "{}", '{"status":"EXECUTED"}')  # ... a may not land
    assert [e.op_id for e in a.operations()] == ["OP-B"] and a.verify_chain()


def test_a_unit_that_lost_the_state_compare_and_swap_keeps_nothing(two: Any) -> None:
    a, b = two
    a.put_state(_state(1))
    with pytest.raises(StateVersionConflict), a.transaction():
        read = a.get_state()
        b.put_state(_state(2, cash=2), expected_version=1)  # b commits a new version first
        a.put_state(_state(2, cash=3), expected_version=read.state_version)
    assert [s.cash_fen for s in a.state_history()] == [1, 2]  # b's write stands; a's is gone, nothing overwritten


def test_begin_immediate_takes_the_write_lock_when_the_unit_begins(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'lock.db').as_posix()}"
    a = SqlLedgerStore(url)
    impatient = SqlLedgerStore(url, create_tables=False,
                               engine=create_engine(url, connect_args={"check_same_thread": False, "timeout": 0.05}))
    try:
        a.put_state(_state(1))
        with a.transaction():
            a.get_state()  # only a read so far, yet the unit already holds the write lock
            with pytest.raises(OperationalError, match="locked"), impatient.transaction():
                pass
            assert impatient.get_state().state_version == 1  # readers are not blocked
    finally:
        impatient.dispose()
        a.dispose()


class _LoseOnce:
    """A store whose first compare-and-swap loses, as when another process committed first."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.lost = False
        self.units = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def transaction(self) -> Any:
        self.units += 1
        return self._inner.transaction()

    def put_state(self, state: Any, **kwargs: Any) -> None:
        if not self.lost:
            self.lost = True
            raise StateVersionConflict("another writer committed first")
        self._inner.put_state(state, **kwargs)


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_the_executor_runs_a_unit_that_lost_its_compare_and_swap_again(kind: str, tmp_path: Path) -> None:
    store = seeded_store(kind, f"sqlite:///{(tmp_path / 'ex.db').as_posix()}")
    clock = Clock(0)
    proxy = _LoseOnce(store)
    r = make_executor(proxy, clock).execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000))
    assert r.status == OperationStatus.EXECUTED and proxy.units == 2
    assert [e.op_id for e in store.operations()] == [r.op_id] and store.verify_chain()
    assert store.get_state().state_version == 2
    if isinstance(store, SqlLedgerStore):
        store.dispose()


def test_retryable_errors() -> None:
    class Orig(Exception):
        def __init__(self, sqlstate: str) -> None:
            self.sqlstate = sqlstate

    class Wrapped(Exception):
        def __init__(self, sqlstate: str) -> None:
            self.orig = Orig(sqlstate)

    assert is_retryable(ConcurrentWriteConflict("x")) and is_retryable(StateVersionConflict("x"))
    assert is_retryable(Wrapped("40001")) and is_retryable(Wrapped("40P01"))  # serialization failure, deadlock
    assert not is_retryable(Wrapped("23505")) and not is_retryable(ValueError("x"))
