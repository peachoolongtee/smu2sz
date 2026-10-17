"""Natural wordings of "am I safe on cash this month?" are the status read (the same cash-runway answer as "Will we run short of cash this
month?") in the offline rules classifier, in English and Chinese; a question about a deal or an invoice is not."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
RUNWAY = "Will we run short of cash this month?"


@pytest.fixture
def api():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    reset_sessions()
    from app.main import app

    yield TestClient(app, headers=OWNER)
    set_runtime(None)
    reset_sessions()


def _ask(api: TestClient, text: str, lang: str) -> dict:
    r = api.post("/nl", json={"session_id": "s", "text": text, "lang": lang, "actor": "OWNER"})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("text", [
    "Am I safe this month?", "Are we OK for cash?", "Are we safe?", "Are we okay on cash this month?", "Are we covered until payday?",
    "How is our cash?", "What is our cash runway?", "How long will our cash last?", "Will I have enough cash?",
])
def test_english_wordings_are_the_cash_runway_read(api: TestClient, text: str) -> None:
    """Each wording is the cash read: the status read itself, or (for a top owner question, app/nl/answers) the answer module's
    cash answer, which leads with the answer and names the same first unsafe day. Nothing runs either way."""
    out = _ask(api, text, "en")
    assert out["operations"] == [] and not out["awaiting_confirmation"]
    if out["intent"] == "ASK_BOOKS":
        assert re.match(r"^(?:Not on today's books|12 days to your reserve)", out["reply"]), out["reply"]
        assert "day 12" in out["reply"] and "¥300,000 reserve" in out["reply"]
    else:
        assert out["intent"] == "SHOW_STATUS"
        assert out["reply"] == _ask(api, RUNWAY, "en")["reply"]


@pytest.mark.parametrize("text", [
    "我这个月安全吗？", "我们安全吗", "现金够不够？", "钱够不够用？", "现金能撑多久？", "这个月我们会不会缺钱？", "资金紧张吗？",
])
def test_chinese_wordings_are_the_cash_runway_read(api: TestClient, text: str) -> None:
    out = _ask(api, text, "zh")
    assert out["operations"] == [] and not out["awaiting_confirmation"]
    if out["intent"] == "ASK_BOOKS":  # the answer module's cash answer (LIQ-01 / LIQ-03), leading with the answer
        assert re.match(r"^(?:按今日账目并不安全|距离跌破储备线还有 12 天)", out["reply"]), out["reply"]
        assert "第 12 天" in out["reply"] and "¥300,000" in out["reply"]
    else:
        assert out["intent"] == "SHOW_STATUS"
        assert out["reply"] == _ask(api, "这个月我们会不会缺钱？", "zh")["reply"]


@pytest.mark.parametrize(("text", "lang"), [
    ("Are we OK to accept this offer from Foshan?", "en"), ("Is the invoice safe?", "en"), ("这份合同安全吗", "zh"),
])
def test_a_question_about_a_deal_is_not_the_cash_read(api: TestClient, text: str, lang: str) -> None:
    out = _ask(api, text, lang)
    assert out["intent"] != "SHOW_STATUS"
    assert not out["reply"].startswith(("Not on today's books", "按今日账目并不安全"))  # nor the answer module's cash answer
