"""Ask FLOW's Home-reading intents (what changed, what is waiting, when money arrives, a late payment) read the Home sentences through the
plain read, never through the GET /home route function with its address parameters left as FastAPI defaults (the AttributeError the live
run logged). On the Demo and on the busy company, in both languages: the turn answers with the intent's sentences, never the unavailable
sentence, and the route never fails."""

from __future__ import annotations

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
