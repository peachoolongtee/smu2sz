"""Two Chinese reads a judge meets in the chat demo: a buyer's request for longer terms gets its counter in Chinese (the log keeps the
engine's English), and the owner's "what needs my attention" answer names its alert in Chinese."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.engine_zh import translate
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
BUYER = {"X-Counterparty-Key": "demo-buyer-1-key"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Bank credit line", "Invoice financing (onboarded platform)"]
TERMS_ZH = "我们希望把以后所有发票的账期从45天延长到60天。其他不变。"
TERMS_EN = "We would like 60 days payment terms on all future invoices instead of 45. Nothing else changes."


@pytest.fixture
def api():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    reset_sessions()
    from app.main import app

    yield TestClient(app)
    set_runtime(None)
    reset_sessions()


def _buyer(api: TestClient, text: str, lang: str) -> dict:
    r = api.post("/nl", json={"session_id": "b", "text": text, "lang": lang, "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1"},
                 headers=BUYER)
    assert r.status_code == 200, r.text
    return r.json()


def _owner(api: TestClient, text: str, lang: str) -> dict:
    r = api.post("/nl", json={"session_id": "o", "text": text, "lang": lang, "actor": "OWNER"}, headers=OWNER)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_chinese_terms_request_gets_the_counter_in_chinese(api: TestClient) -> None:
    out = _buyer(api, TERMS_ZH, "zh")
    assert out["reply"].startswith("方案 A：账期保持 45 天。") and "\n方案 B：接受 55 天账期" in out["reply"]
    assert "¥260,000" in out["reply"] and "0.85%" in out["reply"] and "0.30%" in out["reply"]
    assert english_leaks({"reply": out["reply"]}, NAMES) == []


def test_the_english_counter_is_unchanged_and_carries_the_same_figures(api: TestClient) -> None:
    out = _buyer(api, TERMS_EN, "en")
    assert out["reply"].startswith("Option A: Terms stay at 45 days. We will accept early settlement on up to ¥260,000")
    assert "Option B: 55-day terms accepted with a 0.30% price adjustment" in out["reply"]


def test_the_owner_sees_the_counter_steps_in_chinese(api: TestClient) -> None:
    out = _owner(api, f"这是Foshan的好报价吗？“{TERMS_ZH}”", "zh")
    steps = [s["description"] for s in out["plan"] if s["kind"] == "COUNTER_OFFER"]
    assert len(steps) == 2 and english_leaks({"steps": steps}, NAMES) == []


def test_the_chinese_attention_answer_names_its_alert_in_chinese(api: TestClient) -> None:
    out = _owner(api, "有什么需要我关注的？", "zh")
    assert "Reserve headroom" not in out["reply"] and "第 32 天现金距最低现金储备很近" in out["reply"]
    assert english_leaks({"reply": out["reply"]}, NAMES) == []
    assert "Reserve headroom thin on day 32" in _owner(api, "What needs my attention?", "en")["reply"]


@pytest.mark.parametrize("sentence", [
    "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥257,200 of this invoice at 0.85%, paid on or before day 2.",
    "No rebate is on record, so none applies. We will accept early settlement on up to ¥10,000 of this invoice at 0.50%, paid on or before day 3. Nothing else changes.",
    "We can extend terms by 15 days on the next three invoices if the 1.00% credit is firm on each of them.",
    "We can extend terms by 10 days on the next invoice.",
    "Reserve headroom thin on day 5",
])
def test_every_counter_and_alert_template_has_a_chinese_twin(sentence: str) -> None:
    assert english_leaks({"s": translate(sentence)}) == []
