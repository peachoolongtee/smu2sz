"""R04 and R05: unauthenticated intake (POST /offers, buyer turns on POST /nl) is capped per simulated day."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api.auth import DEMO_COUNTERPARTY_KEYS
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import Settings, get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OFFER = {"fixture_id": "EX01_PACKAGE"}
OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
CHANNEL = {"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-1"]}
BUYER_TURN = {"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": "hello"}


def make_client(settings: Settings) -> TestClient:
    rt = Runtime(settings=settings, store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    return TestClient(app)  # no default credential: an anonymous caller


@pytest.fixture
def anon():
    yield make_client(get_settings())
    set_runtime(None)


@pytest.fixture
def small_cap():
    yield make_client(replace(get_settings(), intake_cap_per_day=3))
    set_runtime(None)


def capped_events() -> list:
    return [e for e in get_runtime().store.security_events() if e.id.startswith("SEC-INTAKE-")]


def test_the_default_cap_is_200(anon):
    assert get_settings().intake_cap_per_day == 200


def test_the_201st_unauthenticated_offer_in_a_day_is_429_with_one_security_event(anon):
    for i in range(200):
        assert anon.post("/offers", json=OFFER).status_code == 200, i
    assert capped_events() == []
    r = anon.post("/offers", json=OFFER)
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "INTAKE_CAPPED"
    assert isinstance(r.json()["detail"]["message"], str)
    assert len(capped_events()) == 1
    assert anon.post("/offers", json=OFFER).status_code == 429
    assert len(capped_events()) == 2  # one per capped request


def test_a_capped_offer_is_not_stored(small_cap):
    for _ in range(3):
        assert small_cap.post("/offers", json=OFFER).status_code == 200
    stored = len(get_runtime().documents)
    assert small_cap.post("/offers", json=OFFER).status_code == 429
    assert len(get_runtime().documents) == stored


@pytest.mark.parametrize("headers", [OWNER, AGENT, CHANNEL], ids=["owner", "agent", "channel-key"])
def test_authenticated_callers_are_never_capped(small_cap, headers):
    for _ in range(3):
        assert small_cap.post("/offers", json=OFFER).status_code == 200
    assert small_cap.post("/offers", json=OFFER).status_code == 429
    for _ in range(8):
        assert small_cap.post("/offers", headers=headers, json=OFFER).status_code == 200
    assert len(capped_events()) == 1  # only the anonymous request above
    assert get_runtime().intake_count == 3  # authenticated calls do not use the allowance


def test_a_wrong_channel_key_is_unauthenticated_and_capped(small_cap):
    wrong = {"X-Counterparty-Key": "not-a-key"}
    for _ in range(3):
        assert small_cap.post("/offers", headers=wrong, json=OFFER).status_code == 200
    assert small_cap.post("/offers", headers=wrong, json=OFFER).status_code == 429


def test_the_cap_resets_when_the_day_advances(small_cap):
    for _ in range(3):
        assert small_cap.post("/offers", json=OFFER).status_code == 200
    assert small_cap.post("/offers", json=OFFER).status_code == 429
    assert small_cap.post("/clock/advance", headers=OWNER, json={"days": 1}).status_code == 200
    for _ in range(3):
        assert small_cap.post("/offers", json=OFFER).status_code == 200
    assert small_cap.post("/offers", json=OFFER).status_code == 429


def test_the_cap_resets_with_the_demo_reset(small_cap):
    for _ in range(3):
        small_cap.post("/offers", json=OFFER)
    assert small_cap.post("/offers", json=OFFER).status_code == 429
    assert small_cap.post("/demo/reset", headers=OWNER).status_code == 200
    assert small_cap.post("/offers", json=OFFER).status_code == 200


def test_offers_and_buyer_turns_share_one_daily_allowance(small_cap):
    assert small_cap.post("/offers", json=OFFER).status_code == 200
    assert small_cap.post("/nl", json=BUYER_TURN).status_code == 200
    assert small_cap.post("/offers", json=OFFER).status_code == 200
    assert small_cap.post("/nl", json=BUYER_TURN).status_code == 429
    assert small_cap.post("/offers", json=OFFER).status_code == 429


def test_the_setting_reads_the_environment(monkeypatch):
    monkeypatch.setenv("INTAKE_CAP_PER_DAY", "7")
    assert Settings().intake_cap_per_day == 7
    monkeypatch.setenv("INTAKE_CAP_PER_DAY", "lots")
    assert Settings().intake_cap_per_day == 200
