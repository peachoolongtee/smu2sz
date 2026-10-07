"""R05: buyer turns on POST /nl without a channel key are capped per day; callers with a credential are not."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.auth import DEMO_COUNTERPARTY_KEYS
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

CAP = 3
TURN = {"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": "hello"}
CHANNEL = {"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-1"]}


@pytest.fixture
def anon():
    rt = Runtime(settings=replace(get_settings(), intake_cap_per_day=CAP), store=InMemoryLedgerStore(),
                 owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def events(prefix: str) -> list:
    return [e for e in get_runtime().store.security_events() if e.id.startswith(prefix)]


def test_a_buyer_turn_over_the_cap_is_429_with_exactly_one_security_event(anon):
    for _ in range(CAP):
        assert anon.post("/nl", json=TURN).status_code == 200
    before = len(get_runtime().store.security_events())
    r = anon.post("/nl", json=TURN)
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "INTAKE_CAPPED"
    after = get_runtime().store.security_events()
    assert len(after) == before + 1
    assert after[-1].id.startswith("SEC-INTAKE-") and after[-1].day == get_runtime().day


def test_a_capped_turn_with_a_wrong_key_logs_only_the_capped_event(anon):
    for _ in range(CAP):
        assert anon.post("/nl", json=TURN).status_code == 200
    before = len(get_runtime().store.security_events())
    r = anon.post("/nl", headers={"X-Counterparty-Key": "wrong"}, json=TURN)
    assert r.status_code == 429
    assert len(get_runtime().store.security_events()) == before + 1
    assert events("SEC-CPKEY-") == []


def test_a_wrong_key_under_the_cap_is_still_logged_as_before(anon):
    assert anon.post("/nl", headers={"X-Counterparty-Key": "wrong"}, json=TURN).status_code == 200
    assert len(events("SEC-CPKEY-")) == 1


@pytest.mark.parametrize("headers", [CHANNEL, {"X-Owner-Token": "demo-owner-token"}, {"X-Agent-Key": "demo-agent-key"}],
                         ids=["channel-key", "owner", "agent"])
def test_credentialed_buyer_turns_are_never_capped(anon, headers):
    for _ in range(CAP):
        assert anon.post("/nl", json=TURN).status_code == 200
    assert anon.post("/nl", json=TURN).status_code == 429
    for _ in range(CAP + 4):
        assert anon.post("/nl", headers=headers, json=TURN).status_code == 200
    assert len(events("SEC-INTAKE-")) == 1


def test_owner_turns_are_never_counted(anon):
    owner = {"X-Owner-Token": "demo-owner-token"}
    for _ in range(CAP + 3):
        assert anon.post("/nl", headers=owner, json={"actor": "OWNER", "text": "what is my cash"}).status_code == 200
    assert get_runtime().intake_count == 0


def test_the_buyer_allowance_resets_the_next_day(anon):
    for _ in range(CAP):
        anon.post("/nl", json=TURN)
    assert anon.post("/nl", json=TURN).status_code == 429
    assert anon.post("/clock/advance", headers={"X-Owner-Token": "demo-owner-token"}, json={"days": 1}).status_code == 200
    assert anon.post("/nl", json=TURN).status_code == 200
