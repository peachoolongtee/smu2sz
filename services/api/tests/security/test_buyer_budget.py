"""R-10, the owner's decision of 16 Oct 2026: a keyed buyer may send only BUYER_ATTEMPTS_PER_DAY offers or messages per simulated
day (default 5) through POST /offers and POST /nl. Past it: 429 BUYER_BUDGET_EXHAUSTED in neutral words, and a security event
against that buyer. The owner, the agent and anonymous intake (its own cap) are unaffected."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.auth import DEMO_COUNTERPARTY_KEYS
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
KEY1 = {"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-1"]}
KEY2 = {"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-2"]}
TURN = {"actor": "COUNTERPARTY", "text": "We will pay the ¥420,000 invoice early at a 0.86% discount."}
OFFER = {"fixture_id": "EX01_PACKAGE"}


@pytest.fixture
def api():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def budget_events() -> list:
    return [e for e in get_runtime().store.security_events() if e.id.startswith("SEC-BUDGET-")]


def test_the_default_budget_is_five():
    assert get_settings().buyer_attempts_per_day == 5


def test_the_sixth_message_in_a_day_is_refused_in_neutral_words(api):
    for _ in range(5):
        assert api.post("/nl", headers=KEY1, json=TURN).status_code == 200
    r = api.post("/nl", headers=KEY1, json=TURN)
    assert r.status_code == 429
    detail = r.json()["detail"]
    assert detail["code"] == "BUYER_BUDGET_EXHAUSTED"
    assert detail["message"] == "We have received your messages for today. Please write again tomorrow."
    assert not any(c in detail["message"] for c in "¥%0123456789")
    [event] = budget_events()
    assert event.counterparty_id == "BUYER-1" and event.kind.value == "DATA_EXTRACTION"
    zh = api.post("/nl", headers=KEY1, json={**TURN, "lang": "zh"}).json()["detail"]
    assert zh["message"] == "今天的消息我们已收到。请明天再联系。"


def test_one_event_per_buyer_per_day_however_often_it_retries(api):
    for _ in range(5):
        api.post("/nl", headers=KEY1, json=TURN)
    for _ in range(20):
        assert api.post("/nl", headers=KEY1, json=TURN).status_code == 429
    assert len(budget_events()) == 1 and get_runtime().buyer_refusals["BUYER-1"] == (0, 20)
    assert api.post("/clock/advance", headers=OWNER, json={"days": 1}).status_code == 200
    for _ in range(5):
        api.post("/nl", headers=KEY1, json=TURN)
    for _ in range(3):
        assert api.post("/nl", headers=KEY1, json=TURN).status_code == 429
    assert len(budget_events()) == 2 and len({e.id for e in budget_events()}) == 2


def test_offers_and_messages_share_one_budget(api):
    for _ in range(3):
        assert api.post("/nl", headers=KEY1, json=TURN).status_code == 200
    for _ in range(2):
        assert api.post("/offers", headers=KEY1, json=OFFER).status_code == 200
    r = api.post("/offers", headers=KEY1, json=OFFER)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "BUYER_BUDGET_EXHAUSTED"


def test_the_next_simulated_day_resets_the_budget(api):
    for _ in range(5):
        api.post("/nl", headers=KEY1, json=TURN)
    assert api.post("/nl", headers=KEY1, json=TURN).status_code == 429
    assert api.post("/clock/advance", headers=OWNER, json={"days": 1}).status_code == 200
    assert api.post("/nl", headers=KEY1, json=TURN).status_code == 200


def test_each_buyer_has_its_own_budget(api):
    for _ in range(5):
        api.post("/nl", headers=KEY1, json=TURN)
    assert api.post("/nl", headers=KEY1, json=TURN).status_code == 429
    assert api.post("/nl", headers=KEY2, json=TURN).status_code == 200


@pytest.mark.parametrize("headers", [OWNER, {"X-Agent-Key": "demo-agent-key"}], ids=["owner", "agent"])
def test_the_owner_and_the_agent_are_unaffected(api, headers):
    for _ in range(5):
        api.post("/nl", headers=KEY1, json=TURN)
    for _ in range(7):
        assert api.post("/nl", headers=headers, json={"text": "show cash status"}).status_code == 200
        assert api.post("/nl", headers={**headers, **KEY1}, json=TURN).status_code == 200
    assert len(budget_events()) == 0


def test_anonymous_intake_keeps_its_own_cap(api):
    anon = {**TURN, "counterparty_id": "BUYER-1"}
    for _ in range(8):
        assert api.post("/nl", json=anon).status_code == 200
    assert get_runtime().intake_count == 8 and budget_events() == []
