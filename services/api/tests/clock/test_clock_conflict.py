"""The clock runs through the same compare-and-swap retry as an executor unit (concurrency certification,
follow-up B1): the new books are written against the version they were computed from, a lost race reruns the
unit on the books as they now are, and a race lost every time is raised, with nothing kept."""

from __future__ import annotations

import pytest

from app.clock import ADVANCE_CLOCK_KIND, _CAS_ATTEMPTS, advance
from app.domain.fixtures import load_scenario
from app.persistence import ConcurrentWriteConflict, InMemoryLedgerStore, StateVersionConflict


def _store() -> InMemoryLedgerStore:
    s = InMemoryLedgerStore()
    s.put_state(load_scenario("golden_sme")[0])
    return s


def _spy(store: InMemoryLedgerStore, monkeypatch: pytest.MonkeyPatch, fail_first: int | None) -> list[dict]:
    """Record every put_state call; the first `fail_first` of them (all when None) lose the race."""
    real = store.put_state
    calls: list[dict] = []

    def put_state(state, expected_version=None):
        calls.append({"version": state.state_version, "expected_version": expected_version})
        if fail_first is None or len(calls) <= fail_first:
            raise StateVersionConflict("a concurrent writer committed first")
        return real(state, expected_version=expected_version)

    monkeypatch.setattr(store, "put_state", put_state)
    return calls


def test_advance_writes_compare_and_swap_on_the_version_it_read(monkeypatch):
    st = _store()
    v0 = st.get_state().state_version
    calls = _spy(st, monkeypatch, fail_first=0)
    adv = advance(st, 34)
    assert adv.result is not None and st.get_state().as_of_day == 34
    assert calls == [{"version": v0 + 1, "expected_version": v0}]


def test_a_lost_race_reruns_the_unit_and_logs_once(monkeypatch):
    st = _store()
    v0 = st.get_state().state_version
    calls = _spy(st, monkeypatch, fail_first=3)
    adv = advance(st, 34)
    assert len(calls) == 4 and all(c["expected_version"] == v0 for c in calls)
    assert st.get_state().state_version == v0 + 1 and st.get_state().as_of_day == 34
    ops = [o for o in st.operations() if o.kind == ADVANCE_CLOCK_KIND]
    assert len(ops) == 1 and adv.result is not None and adv.result.seq == ops[0].seq


def test_a_race_lost_every_time_is_raised_and_keeps_nothing(monkeypatch):
    st = _store()
    before = st.get_state()
    calls = _spy(st, monkeypatch, fail_first=None)
    with pytest.raises(ConcurrentWriteConflict):
        advance(st, 34)
    assert len(calls) == _CAS_ATTEMPTS
    assert st.get_state() == before
    assert [o for o in st.operations() if o.kind == ADVANCE_CLOCK_KIND] == []


def test_an_error_that_is_not_a_conflict_is_not_retried(monkeypatch):
    st = _store()
    n = {"calls": 0}

    def boom(state, expected_version=None):
        n["calls"] += 1
        raise RuntimeError("disk full")

    monkeypatch.setattr(st, "put_state", boom)
    with pytest.raises(RuntimeError):
        advance(st, 34)
    assert n["calls"] == 1
