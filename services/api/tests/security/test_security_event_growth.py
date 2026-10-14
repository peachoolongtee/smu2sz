"""SEC-10 (security register, 14 Oct): every refused credential wrote one SecurityEvent whose id came from a full read of the table, so
an anonymous caller grew the store without bound, each refusal cost a read of every earlier event, and concurrent refusals shared ids."""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from app.api import auth
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore


@pytest.fixture
def c(monkeypatch):
    monkeypatch.setattr(auth, "REFUSAL_EVENTS_PER_HOUR", 25)
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def refusals() -> list:
    return [e for e in get_runtime().store.security_events() if e.id.startswith("SEC-AUTH-")]


def test_refusal_events_stop_growing_past_the_hourly_budget_and_say_so(c):
    for _ in range(100):
        assert c.get("/ledger").status_code == 401
    got = refusals()
    assert len(got) == 26  # the budget, then one event saying further refusals this hour are counted, not recorded
    assert "not recorded" in got[-1].detail


def test_a_refusal_does_not_read_the_event_table(c, monkeypatch):
    rt = get_runtime()

    def boom():
        raise AssertionError("a refusal read every stored event")

    monkeypatch.setattr(rt.store, "security_events", boom)
    assert c.get("/ledger").status_code == 401


def test_concurrent_refusals_get_distinct_ids(c):
    barrier = threading.Barrier(12)

    def hit():
        barrier.wait()
        c.get("/state")

    threads = [threading.Thread(target=hit) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ids = [e.id for e in refusals()]
    assert len(ids) == 12 and len(set(ids)) == 12
