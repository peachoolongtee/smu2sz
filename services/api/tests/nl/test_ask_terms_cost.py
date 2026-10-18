"""A terms question that names the change is priced with that change (Ask FLOW QA, 18 Oct): "账期从45天改成60天，我该接受吗？成本是多少？"
priced the 45 days it replaces (a no-op) and said ¥0, "within your mandate". And a terms question that asked "which buyer?" forgot the new
terms when the owner answered. The figure is the engine's (the what-if), never written here; the demo books price 60-day terms for Foshan at
¥24,326.92 against a ¥5,000 limit. No test calls a model: the router's backend is scripted."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.runtime import Runtime
from app.nl import lexicon as lx
from app.nl.answers import answers as ans
from app.nl.answers.metrics import Reading, terms_extension_cost
from app.nl.router import route as rr
from tests.nl.conftest import Chat
from tests.nl.test_ask_router import Scripted, calls, ctx_for

EXTENSION = "2432692"  # fen: 13 invoices in the window (tests/test_fixtures.py: extension_committed_12m)
ZH_QUESTION = "账期从45天改成60天，我该接受吗？成本是多少？"
EN_QUESTION = "Should I accept 60-day terms instead of 45? What does it cost?"
OVER = {"en": "above your ¥5,000 limit", "zh": "超过您 ¥5,000 的上限"}
WITHIN = ("within your", "within the", "在您", "可在您的授权内接受", "could accept")


def engine_cost(rt: Runtime, days: int) -> dict[str, Any]:
    d = terms_extension_cost(Reading.of(ctx_for(rt)), "BUYER-1", days)
    return {"fen": d.value, **d.detail}


def never_reassuring(reply: str) -> None:
    assert not any(w in reply for w in WITHIN), reply
    assert "¥0," not in reply and "¥0 " not in reply, reply


# ---------------------------------------------------------------- reading the change


@pytest.mark.parametrize(("text", "target"), [
    (ZH_QUESTION, 60), (EN_QUESTION, 60), ("Foshan wants to move from 45 days to 60 days", 60), ("extend 45 days to 60 days", 60),
    ("60 days instead of 45 days", 60), ("give Foshan 60 days", 60), ("给佛山60天账期", 60), ("账期延长到60天", 60),
    ("账期从45天改为60天", 60), ("what does 60-day terms cost", 60),
])
def test_the_terms_asked_for_are_the_ones_after_to_and_instead_of(text: str, target: int) -> None:
    got = lx.terms_change(text)
    assert got.target == target and not got.ambiguous


def test_day_counts_that_cannot_be_told_apart_are_not_guessed() -> None:
    got = lx.terms_change("is 45 days or 60 days better")
    assert got.target is None and got.ambiguous


def test_an_early_payment_window_is_not_a_terms_request() -> None:
    for text in ("a 2% discount if I pay within 10 days", "Foshan asks for 2% off if they pay in 10 days", "10天内付款给2%折扣"):
        assert lx.terms_change(text) == lx.TermsChange(), text
    assert lx.terms_change("2% discount on 60-day terms").target == 60  # "terms" says they are terms


# ---------------------------------------------------------------- the answer


def test_the_zh_question_is_priced_at_60_days_not_45(client: Any, rt: Runtime) -> None:
    fen = engine_cost(rt, 60)
    assert str(fen["fen"]) == EXTENSION and fen["over_cap"] is True
    reply = Chat(client, "zh-1").say(ZH_QUESTION)["reply"]
    assert "¥24,326.92" in reply and OVER["zh"] in reply and "第 47 天" in reply
    assert "还价" in reply and "佛山" in reply
    never_reassuring(reply)


def test_the_en_question_is_priced_at_60_days_not_45(client: Any, rt: Runtime) -> None:
    reply = Chat(client, "en-1").say(EN_QUESTION)["reply"]
    assert "¥24,326.92" in reply and OVER["en"] in reply and "counter rather than accept" in reply
    never_reassuring(reply)


@pytest.mark.parametrize("text", [
    "Should I accept Foshan's request to move from 45 to 60 days? What does it cost?", "Should I accept 60 days instead of 45 for Foshan?",
    "佛山要求账期从45天改成60天，我该接受吗？成本是多少？", "What if we extend terms to 60 days instead of 45?",
    "如果把账期从45天延长到60天会怎样？", "给佛山60天账期要花多少钱？",
])
def test_every_wording_of_the_extension_gets_the_engines_figure(client: Any, text: str) -> None:
    reply = Chat(client, "w-" + str(abs(hash(text)))).say(text)["reply"]
    assert "¥24,326.92" in reply, reply
    never_reassuring(reply)


@pytest.mark.parametrize("days", [45, 30, 10])
def test_terms_that_are_not_longer_are_never_priced_or_called_acceptable(rt: Runtime, days: int) -> None:
    c = terms_extension_cost(Reading.of(ctx_for(rt)), "BUYER-1", days)
    assert c.value is None and c.detail["no_extension"] and c.detail["current_terms_days"] == 45
    for lang in ("en", "zh"):
        reply = ans.terms_cost_reply(ans.W(Reading.of(ctx_for(rt, lang)), lang), "BUYER-1", days).text
        never_reassuring(reply)
        assert "45" in reply and ("not be an extension" in reply or "并不比现在更长" in reply)


def test_a_discount_with_a_payment_window_is_not_priced_as_terms(client: Any) -> None:
    en = Chat(client, "d-en").say("Foshan asks for 2% off if they pay in 10 days. Should I accept, and what does it cost?")
    assert en["intent"] == "WHAT_IF" and "TERMS_EXTENSION" not in en["reply"] and "Verdict COUNTER" in en["reply"]
    zh = Chat(client, "d-zh").say("供应商给2%的折扣，10天内付款，我该接受吗？成本是多少？")["reply"]
    never_reassuring(zh)
    assert "10 天账期" not in zh


# ---------------------------------------------------------------- the router: whatever number the model copied


@pytest.mark.parametrize(("lang", "question"), [("zh", ZH_QUESTION), ("en", "Would Foshan going from 45 days to 60 days be OK?")])
def test_the_router_prices_the_terms_in_the_question_even_if_the_model_copied_the_old_ones(
        rt: Runtime, monkeypatch: pytest.MonkeyPatch, lang: str, question: str) -> None:
    spy = Scripted(calls(("terms_extension_cost", {"customer": "Foshan", "days": 45})))
    reply = rr.route(question, lang, ctx_for(rt, lang), [spy])
    assert reply is not None and "¥24,326.92" in reply.text, reply
    never_reassuring(reply.text)


def test_the_router_tool_given_the_old_terms_says_nothing_is_priced(rt: Runtime) -> None:
    spy = Scripted(calls(("terms_extension_cost", {"customer": "Foshan", "days": 45})))
    reply = rr.route("is the discount fine", "en", ctx_for(rt), [spy])  # no terms in the question: the model's number stands
    assert reply is not None and "not be an extension" in reply.text
    never_reassuring(reply.text)


# ---------------------------------------------------------------- the two-turn conversation


def test_which_buyer_then_foshan_answers_for_the_60_days(client: Any, rt: Runtime) -> None:
    chat = Chat(client, "two-turn-1")
    first = chat.say("What would happen if a customer wanted 60 days payment terms?")
    assert first["intent"] == "AMBIGUOUS" and first["reply"].startswith("Which buyer is this for?")
    second = chat.say("Foshan")
    assert second["intent"] == "WHAT_IF", second["reply"]
    assert "Which change should I test" not in second["reply"]
    assert "Forward concessions ¥24,326.92 against ¥5,000.00" in second["reply"]
    assert "RESERVE_BREACH" in second["reply"] or "REJECT" in second["reply"]


def test_which_buyer_then_the_zh_name_answers_for_the_60_days(client: Any) -> None:
    chat = Chat(client, "two-turn-2")
    first = chat.say("假设买家要60天账期，会有什么影响？")
    assert first["intent"] == "AMBIGUOUS" and "哪位买家" in first["reply"]
    second = chat.say("1")
    assert "¥24,326.92" in second["reply"] and "请问要测试哪种变化" not in second["reply"] and "要测试哪种变化" not in second["reply"]


def _two_buyers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The customer is not named and the books do not point at one (as when more than one customer has open invoices)."""
    monkeypatch.setattr(ans, "_buyer_asked", lambda r, q: None)


@pytest.mark.parametrize(("lang", "question", "reply_name", "shown"), [
    ("en", EN_QUESTION, "Foshan", "¥24,326.92 in forward concessions"), ("zh", ZH_QUESTION, "佛山", "远期让步 ¥24,326.92")])
def test_a_read_only_question_that_asks_which_customer_keeps_the_terms(
        client: Any, monkeypatch: pytest.MonkeyPatch, lang: str, question: str, reply_name: str, shown: str) -> None:
    _two_buyers(monkeypatch)
    chat = Chat(client, "ask-" + lang)
    first = chat.say(question)
    assert first["intent"] == "ASK_BOOKS" and ("Which customer" in first["reply"] or "哪位客户" in first["reply"])
    never_reassuring(first["reply"])
    second = chat.say(reply_name)
    assert second["intent"] == "ASK_BOOKS" and shown in second["reply"], second["reply"]
    assert OVER[lang] in second["reply"]
    never_reassuring(second["reply"])
    # the pending question was used up: the same name again is not an answer to anything
    third = chat.say(reply_name)
    assert shown not in third["reply"]


def test_the_router_tool_that_asks_which_customer_is_finished_by_the_name(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_ASK_ROUTER", "1")
    spy = Scripted(calls(("terms_extension_cost", {"customer": "the retailer", "days": 60})))
    monkeypatch.setattr(rr, "default_backends", lambda: [spy])
    chat = Chat(client, "router-two")
    first = chat.say("how much would it cost us to be that generous with the retailer?")
    assert "Which customer do you mean" in first["reply"]
    second = chat.say("Foshan")
    assert "¥24,326.92 in forward concessions" in second["reply"] and OVER["en"] in second["reply"], second["reply"]
    assert len(spy.prompts) == 1  # the answer to "which customer" is code, not a second model call


def test_an_unrelated_turn_after_which_customer_drops_the_pending_question(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _two_buyers(monkeypatch)
    chat = Chat(client, "drop")
    chat.say(EN_QUESTION)
    other = chat.say("How are we doing?")
    assert "¥24,326.92" not in other["reply"]
    assert "¥24,326.92" not in chat.say("Foshan")["reply"]
