"""A ConcurrentWriteConflict that survives the retries is HTTP 409 with a retry hint in every route that writes,
never a 500 (concurrency certification, follow-up B2). The store here conflicts on every write."""

from __future__ import annotations

import pytest

from app.api.errors import CONFLICT_CODE
from app.api.runtime import get_runtime
from app.persistence import ConcurrentWriteConflict, StateVersionConflict


def _always_conflict(client, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    rt = get_runtime()
    seen: list[str] = []

    def put_state(state, expected_version=None):
        seen.append("put_state")
        raise StateVersionConflict("a concurrent writer committed first")

    def append_operation(*a, **k):
        seen.append("append_operation")
        raise ConcurrentWriteConflict("the log head moved")

    monkeypatch.setattr(rt.store, "put_state", put_state)
    monkeypatch.setattr(rt.store, "append_operation", append_operation)
    return seen


def _assert_retry_hint(r) -> None:
    assert r.status_code == 409, r.text
    assert r.headers["Retry-After"] == "1"
    d = r.json()["detail"]
    assert d["code"] == CONFLICT_CODE and d["retry"] is True and d["retry_after_seconds"] == 1


def test_clock_advance_answers_409_with_a_retry_hint(client, monkeypatch):
    seen = _always_conflict(client, monkeypatch)
    rt = get_runtime()
    before = rt.store.get_state()
    r = client.post("/clock/advance", json={"to_day": 40})
    _assert_retry_hint(r)
    assert seen and rt.store.get_state() == before  # nothing was kept


def test_operations_answer_409_with_a_retry_hint(client, monkeypatch):
    rt = get_runtime()
    line = next(f for f in rt.store.get_state().facilities if f.kind.value == "CREDIT_LINE")
    op = {"kind": "DRAW_FACILITY", "op_id": "c1", "idempotency_key": "c1", "mandate_version": rt.store.get_mandate().version,
          "requested_by": "AGENT", "facility_id": line.id, "amount_fen": 1_000_000}
    _always_conflict(client, monkeypatch)
    before = rt.store.get_state()
    r = client.post("/operations", json=op)
    _assert_retry_hint(r)
    assert rt.store.get_state() == before


def test_the_handler_is_installed_for_the_whole_app():
    """One shared handler, so every router (operations, approvals, clock, alerts, nl, negotiate, capex) maps the
    same way: the app, not a route, owns the mapping."""
    from app.main import app

    assert ConcurrentWriteConflict in app.exception_handlers
    assert StateVersionConflict.__mro__[1] is ConcurrentWriteConflict
