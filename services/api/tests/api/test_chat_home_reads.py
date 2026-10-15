"""Ask FLOW's Home-reading intents (what changed, what is waiting, when money arrives, a late payment) read the Home sentences through the
plain read, never through the GET /home route function with its address parameters left as FastAPI defaults (the AttributeError the live
run logged). On the Demo and on the busy company, in both languages: the turn answers with the intent's sentences, never the unavailable
sentence, and the route never fails."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

pytestmark = pytest.mark.usefixtures("fast_busy")  # the busy seed is replayed once per process (tests/api/busy_snapshot.py)

OWNER = {"X-Owner-Token": "demo-owner-token"}
UNAVAILABLE = ("I could not read your books just now", "我暂时无法读取您的账目")
# The question, its intent as the pipeline names it (the waiting and arrival questions answer under SHOW_STATUS), en and zh.
QUESTIONS = [
    ("CHANGES", "What changed since my last visit?", "自上次之后有什么变化？"),
    ("SHOW_STATUS", "What are we still waiting on?", "我们还在等什么？"),
    ("SHOW_STATUS", "When does the money arrive?", "资金什么时候到账？"),
]


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    reset_sessions()
    for clear in (worklist.clear_cache, offer_picture._cache.clear):
        clear()
    yield runtime
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _ask(api: TestClient, session: str, text: str, lang: str) -> dict[str, Any]:
    r = api.post("/nl", json={"session_id": session, "text": text, "lang": lang})
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


@pytest.mark.parametrize("scenario", ["golden_sme", "busy"])
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_home_reading_intents_answer_from_the_home_read(api: TestClient, scenario: str, lang: str) -> None:
    assert api.post(f"/demo/reset?scenario={scenario}").status_code == 200
    for n, (intent, en, zh) in enumerate(QUESTIONS):
        out = _ask(api, f"home-reads-{scenario}-{lang}-{n}", en if lang == "en" else zh, lang)
        assert out["intent"] == intent, (intent, out["intent"], out["reply"])
        assert out["reply"].strip(), intent
        assert not any(u in out["reply"] for u in UNAVAILABLE), (intent, out["reply"])


def test_the_chat_home_read_is_the_plain_read(rt: Runtime) -> None:
    """The reads the owner's chat holds call the plain Home read with the language and the marker only: the route's address parameters
    (decision, scenario) are never passed as their FastAPI defaults."""
    from app.api.nl import _owner_reads

    home = _owner_reads(rt).home("en", None)
    assert home is not None and "home_v2" in home
    assert home["home_v2"]["chart"].get("scenario_title_text") in (None, "") or isinstance(home["home_v2"]["chart"]["scenario_title_text"], str)


# ---------------------------------------------------------------- Slice B (S5): the reads are in Business words

_RAW = re.compile(r"APR-\d+|RCV-[\w-]+|OFF-[\w-]+|BUYER-\d+|\bday -?\d+\b|第 -?\d+ 天|\b(?:OPEN|FINANCED|PENDING|SETTLED)\b")
QUESTIONS_BUSINESS = [
    ("What changed today?", "今天有什么变化？"), ("What are we waiting for?", "我们在等什么？"), ("When does the money arrive?", "资金什么时候到账？"),
    ("What is overdue?", "什么逾期了？"), ("What happens if this payment is late?", "如果这笔款项晚到会怎样？"), ("Who owes us money?", "谁欠我们钱？"),
    ("show cash status", "查看现金状况")]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_home_reads_are_said_in_business_words_with_no_ids_no_day_numbers_and_no_status_codes(api: TestClient, lang: str) -> None:
    from tests.api.conftest import agree_on_rcv_a, english_leaks

    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    agree_on_rcv_a(api)  # a promise, an agreement and a pending application: every kind of row the reads can list
    names = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai",
             "Government-guaranteed working-capital loan"]
    for n, (en, zh) in enumerate(QUESTIONS_BUSINESS):
        for scope in (None, {"customer": "BUYER-2"}):
            body: dict[str, Any] = {"session_id": f"biz-{lang}-{n}-{scope is not None}", "text": en if lang == "en" else zh, "lang": lang}
            if scope:
                body["scope"] = scope
            r = api.post("/nl", params={"mode": "business"}, json=body)
            assert r.status_code == 200, r.text
            reply = r.json()["reply"]
            assert reply.strip() and not _RAW.search(reply), (en, scope, _RAW.findall(reply), reply)
            if lang == "zh":
                assert not english_leaks({"reply": reply}, names), (zh, reply)


def test_what_changed_says_a_late_invoice_with_a_distance_and_no_status_code(api: TestClient) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    for mode in ("business", "demo"):
        reply = api.post("/nl", params={"mode": mode}, json={"session_id": f"chg-{mode}", "text": "What changed today?", "lang": "en"}).json()["reply"]
        assert "was due 15 days ago and is still unpaid" in reply and "was due 30 days ago and is still unpaid" in reply, reply
        assert "day -15" not in reply and "OPEN" not in reply
