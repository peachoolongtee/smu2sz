"""A cancel is honoured when it sits beside small talk or answers "which customer?" while a plan waits (PAY-3).

`rules._small_talk` ran before the pending-plan logic and its off-topic check had no decline guard, and `ask.resume_parse` took any short
reply that names a customer: so "no, cancel. tell me a joke" and "cancel Foshan" were read, and the plan the owner had just refused
stayed pending. Now a message the consent grammar judges (a yes or a no) or that declines (no / cancel / 取消 ...) goes to the plan logic
first. Consent itself is unchanged: "Foshan, go ahead" still executes nothing."""

from __future__ import annotations

from typing import Any

import pytest

from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat
from tests.nl.test_ask_terms_cost import _two_buyers

EN_QUESTION = "What would 60-day payment terms cost us?"
ZH_QUESTION = "60天账期会让我们付出多少成本？"


def _pending(sid: str) -> bool:
    s = SESSIONS.get(sid)
    return s is not None and s.pending_plan is not None


@pytest.mark.parametrize(("lang", "fund", "reply"), [
    ("en", "fund the cash gap", "no, cancel. tell me a joke"),
    ("en", "fund the cash gap", "cancel, and tell me a joke"),
    ("zh", "为资金缺口融资", "不用了，取消。讲个笑话"),
    ("zh", "为资金缺口融资", "不要了，给我写首诗"),
])
def test_a_cancel_beside_small_talk_drops_the_plan(client, rt, lang, fund, reply) -> None:
    chat = Chat(client, f"st-{lang}")
    first = chat.say(fund, lang=lang)
    assert first["awaiting_confirmation"] is True and _pending(f"st-{lang}")
    before = len(rt.store.operations())
    r = chat.say(reply, lang=lang)
    assert not _pending(f"st-{lang}"), r["reply"]
    assert r["awaiting_confirmation"] is False and r["operations"] == []
    assert len(rt.store.operations()) == before


def test_plain_small_talk_still_keeps_the_plan(client, rt) -> None:
    chat = Chat(client, "st-keep")
    chat.say("fund the cash gap")
    r = chat.say("tell me a joke")
    assert _pending("st-keep") and r["operations"] == []


@pytest.mark.parametrize(("lang", "question", "replies"), [
    ("en", EN_QUESTION, ["cancel Foshan", "no, Foshan", "nope Foshan", "cancel, Foshan"]),
    ("zh", ZH_QUESTION, ["取消 佛山", "不要，佛山", "取消佛山"]),
])
def test_a_cancel_naming_the_customer_drops_the_plan(client, rt, monkeypatch, lang, question, replies) -> None:
    _two_buyers(monkeypatch)
    for i, reply in enumerate(replies):
        sid = f"cc-{lang}-{i}"
        chat = Chat(client, sid)
        chat.say("fund the cash gap" if lang == "en" else "为资金缺口融资", lang=lang)
        asked = chat.say(question, lang=lang)
        assert "Which customer" in asked["reply"] or "哪位客户" in asked["reply"], asked["reply"]
        assert _pending(sid)
        before = len(rt.store.operations())
        r = chat.say(reply, lang=lang)
        assert not _pending(sid), (reply, r["reply"])
        assert r["awaiting_confirmation"] is False and r["operations"] == []
        assert len(rt.store.operations()) == before


@pytest.mark.parametrize(("lang", "question", "reply"), [("en", EN_QUESTION, "Foshan, go ahead"), ("zh", ZH_QUESTION, "佛山，执行")])
def test_consent_is_not_widened_foshan_go_ahead_executes_nothing(client, rt, monkeypatch, lang, question, reply) -> None:
    """The consent grammar decides, as before: a go-ahead with a customer's name in it is not a whole-message affirmative."""
    from app.nl import consent

    assert consent.confirmation(reply) is None
    _two_buyers(monkeypatch)
    chat = Chat(client, f"cg-{lang}")
    chat.say("fund the cash gap" if lang == "en" else "为资金缺口融资", lang=lang)
    chat.say(question, lang=lang)
    before = len(rt.store.operations())
    r: dict[str, Any] = chat.say(reply, lang=lang)
    assert len(rt.store.operations()) == before and r["operations"] == []
    assert _pending(f"cg-{lang}")  # the plan still waits; only a plain "go ahead" runs it


def test_a_plain_name_still_finishes_the_question_with_a_plan_waiting(client, rt, monkeypatch) -> None:
    _two_buyers(monkeypatch)
    chat = Chat(client, "cn")
    chat.say("fund the cash gap")
    chat.say(EN_QUESTION)
    r = chat.say("Foshan")
    assert "¥24,326.92 in forward concessions" in r["reply"] and _pending("cn")
    done = chat.say("go ahead")
    assert [o["kind"] for o in done["operations"]][:1] == ["DRAW_FACILITY"]


@pytest.mark.parametrize(("lang", "cancel"), [("en", "cancel Foshan"), ("en", "no, Foshan"), ("zh", "取消 佛山")])
def test_a_cancel_naming_a_customer_drops_the_plan_without_any_question(client, rt, lang, cancel) -> None:
    chat = Chat(client, f"cx-{lang}")
    chat.say("fund the cash gap")
    r = chat.say(cancel, lang=lang)
    assert not _pending(f"cx-{lang}") and r["operations"] == [] and r["awaiting_confirmation"] is False


@pytest.mark.parametrize("go", ["go ahead Foshan", "yes, Foshan", "Foshan: go ahead"])
def test_a_go_ahead_naming_a_customer_still_runs_nothing(client, rt, go) -> None:
    chat = Chat(client, "cy")
    chat.say("fund the cash gap")
    before = len(rt.store.operations())
    r = chat.say(go)
    assert r["operations"] == [] and len(rt.store.operations()) == before and _pending("cy")
