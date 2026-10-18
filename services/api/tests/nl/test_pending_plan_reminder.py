"""ASK-2 (security review of the question gate): a question must not hide the plan that is waiting.

With a plan waiting for "go ahead", an owner question that touches an action ("should we draw ¥100,000 on the line?") says
plainly that the earlier plan, with its cost, is still waiting and that "go ahead" runs it, not the amount asked about. The
plan is kept (a question never cancels anything); the reply says so.
"""

from __future__ import annotations

import pytest

from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat, ops

ACTION_QUESTIONS = [
    ("should we draw ¥100,000 on the line?", "en", "¥100,000.00"),
    ("draw ¥50,000 on the line?", "en", "¥50,000.00"),
    ("repay the line?", "en", None),
    ("get Foshan to pay early?", "en", None),
    ("我们要不要提款10万？", "zh", "¥100,000.00"),
]


@pytest.mark.parametrize(("text", "lang", "amount"), ACTION_QUESTIONS)
def test_a_question_about_an_action_says_the_earlier_plan_is_still_waiting(client, rt, text, lang, amount):
    c = Chat(client, f"ask2-{abs(hash(text)) % 10**8}")
    plan = c.say("fund the gap", lang=lang)
    assert plan["awaiting_confirmation"]
    before = len(rt.store.operations())
    r = c.say(text, lang=lang)
    assert r["intent"] == "ASK_BOOKS" and ops(r) == [] and len(rt.store.operations()) == before
    assert r["awaiting_confirmation"], r["reply"]  # the earlier plan is still waiting
    assert SESSIONS.get(c.session_id).pending_plan is not None
    if lang == "en":
        assert "Your earlier plan is still waiting and nothing has changed" in r["reply"], r["reply"]
        assert "Draw ¥150,000.00 on FAC-LINE" in r["reply"] and "(cost ¥3,113.93)" in r["reply"], r["reply"]
        assert "'go ahead' and that plan runs, not " in r["reply"], r["reply"]
        if amount:
            assert f"not the {amount} you just asked about" in r["reply"], r["reply"]
    else:
        assert "您之前的方案仍在等待，没有任何变化" in r["reply"] and "（成本 ¥3,113.93）" in r["reply"], r["reply"]
        assert "而不是" in r["reply"], r["reply"]
    # and the go-ahead runs exactly that earlier plan
    go = c.say("go ahead", lang=lang)
    assert ops(go) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")], go["reply"]
    assert rt.store.operations()[before].payload_json.count("15000000") == 1


READ_TURNS = [
    ("are we safe?", "en"), ("how much do we owe the banks?", "en"), ("is equity an option?", "en"),
    ("How much would FLOW's plan cost?", "en"), ("what is our cash?", "en"), ("how are we doing?", "en"),
    ("现金够吗？", "zh"), ("我们欠银行多少钱？", "zh"),
]


@pytest.mark.parametrize(("text", "lang"), READ_TURNS)
def test_every_owner_read_turn_says_the_plan_is_still_waiting_rules_path(client, rt, text, lang):
    """ASK-2b: not only a question about an action: any read keeps the plan visible, and never clears or confirms it."""
    c = Chat(client, f"ask2b-{abs(hash(text)) % 10**8}")
    assert c.say("fund the gap", lang=lang)["awaiting_confirmation"]
    before = len(rt.store.operations())
    r = c.say(text, lang=lang)
    assert r["awaiting_confirmation"], r["reply"]
    assert ops(r) == [] and len(rt.store.operations()) == before
    assert SESSIONS.get(c.session_id).pending_plan is not None
    if lang == "en":
        assert "Your earlier plan is still waiting and nothing has changed" in r["reply"], r["reply"]
        assert "Reply 'go ahead' and that plan runs; reply 'cancel' to drop it." in r["reply"], r["reply"]
        assert "(cost ¥3,113.93)" in r["reply"]
    else:
        assert "您之前的方案仍在等待，没有任何变化" in r["reply"] and "回复“执行”将运行该方案；回复“取消”可放弃" in r["reply"], r["reply"]
    assert r["reply"].count("still waiting") + r["reply"].count("仍在等待") == 1  # said once, not twice
    go = c.say("go ahead", lang=lang)  # the question changed nothing: the go-ahead runs the plan held
    assert ops(go) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")], go["reply"]
    assert SESSIONS.get(c.session_id).pending_plan is None


@pytest.mark.parametrize(("text", "lang"), [("what is our exposure to the banks?", "en"), ("how long can we keep paying the bills?", "en"),
                                            ("我们对银行的敞口有多大？", "zh")])
def test_a_router_answer_also_says_the_plan_is_still_waiting(client, rt, monkeypatch, text, lang):
    from app.nl.router import route as rr
    from tests.nl.test_ask_router import Scripted, calls

    spy = Scripted(calls(("total_debt", {})))
    monkeypatch.setattr(rr, "default_backends", lambda: [spy])
    monkeypatch.setenv("FEATURE_ASK_ROUTER", "1")
    c = Chat(client, f"ask2b-router-{abs(hash(text)) % 10**8}")
    assert c.say("fund the gap", lang=lang)["awaiting_confirmation"]
    r = c.say(text, lang=lang)
    assert len(spy.prompts) == 1 and "1,500,000" in r["reply"], r["reply"]  # the router answered
    assert r["awaiting_confirmation"], r["reply"]
    assert ("Your earlier plan is still waiting" in r["reply"]) if lang == "en" else ("您之前的方案仍在等待" in r["reply"])
    assert SESSIONS.get(c.session_id).pending_plan is not None
    go = c.say("go ahead", lang=lang)
    assert ops(go) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")], go["reply"]


def test_a_read_that_proposes_or_cancels_is_not_given_the_reminder(client, rt):
    c = Chat(client, "ask2b-cancel")
    c.say("fund the gap")
    r = c.say("cancel")
    assert "still waiting" not in r["reply"] and not r["awaiting_confirmation"]
    assert SESSIONS.get(c.session_id).pending_plan is None


def test_no_reminder_without_a_waiting_plan(client, rt):
    r = Chat(client, "ask2-none").say("should we draw ¥100,000 on the line?")
    assert "still waiting" not in r["reply"] and not r["awaiting_confirmation"]


def test_the_agent_key_is_never_told_about_the_owners_plan(client, rt):
    r = Chat(client, "ask2-agent", owner=False).say("should we draw ¥100,000 on the line?")
    assert "still waiting" not in r["reply"] and "3,113" not in r["reply"]


def test_the_agent_key_gets_no_reminder_on_a_read_either(client, rt):
    r = Chat(client, "ask2b-agent", owner=False).say("are we safe?")
    assert "still waiting" not in r["reply"] and "3,113" not in r["reply"]
