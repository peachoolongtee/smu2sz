"""SEC-26 (Security Lead, 17 Oct, from the external review of the self-assessment): the SEC-10 budget of 300 recorded refusals an hour
was shared by everyone, so one anonymous address could spend it in about a minute (its rate bucket holds 300) and every later refused
credential that hour, from anyone, went unrecorded, with nothing counting them. Each address now has a share of the budget, and what is
not recorded is counted: a warning line while it happens and one event when the hour turns."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.api import auth
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore


@pytest.fixture
def app():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield app
    set_runtime(None)


def refusals() -> list:
    return [e for e in get_runtime().store.security_events() if e.id.startswith("SEC-AUTH-")]


def test_one_address_cannot_spend_everyone_s_budget(app):
    prober, owner_typo = TestClient(app, client=("203.0.113.7", 5000)), TestClient(app, client=("198.51.100.20", 5000))
    for _ in range(200):
        assert prober.get("/ledger").status_code == 401
    assert len(refusals()) == 30 + 1  # its share, then one event saying the rest are counted
    assert "from one address" in refusals()[-1].detail
    assert owner_typo.get("/ledger", headers={"X-Owner-Token": "typo"}).status_code == 401
    assert refusals()[-1].detail.startswith("owner token missing or wrong: GET /ledger")  # another address is still recorded


def test_what_is_not_recorded_is_counted_and_reported_when_the_hour_turns(app, monkeypatch, caplog):
    clock = [1_800_000_000.0]
    monkeypatch.setattr(auth.time, "time", lambda: clock[0])
    prober = TestClient(app, client=("203.0.113.7", 5000))
    with caplog.at_level(logging.WARNING, logger="termsledger.auth"):
        for _ in range(30 + 1 + 40):
            prober.get("/state")
    assert any("not recorded this hour: 1 from 1 address" in r.getMessage() for r in caplog.records)  # an operator sees it now
    clock[0] += 3600
    prober.get("/state")
    summary = [e for e in refusals() if "counted but not recorded" in e.detail]
    assert len(summary) == 1 and summary[0].detail.startswith("40 refused credentials from 1 address(es)")
    assert refusals()[-1].detail.startswith("owner token")  # a new hour, a new budget


def test_the_hourly_cap_still_bounds_many_addresses(app, monkeypatch):
    monkeypatch.setattr(auth, "REFUSAL_EVENTS_PER_HOUR", 50)
    for n in range(10):
        c = TestClient(app, client=(f"203.0.113.{n}", 5000))
        for _ in range(20):
            c.get("/ledger")
    assert len(refusals()) == 51
    assert "more than 50 refused credentials this hour" in refusals()[-1].detail
