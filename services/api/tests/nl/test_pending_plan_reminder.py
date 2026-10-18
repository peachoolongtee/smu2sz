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


@pytest.mark.parametrize("text", ["How much would FLOW's plan cost?", "What is our cash?", "Is equity an option?"])
def test_a_question_that_is_not_about_an_action_adds_no_reminder(client, rt, text):
    c = Chat(client, f"ask2-quiet-{abs(hash(text)) % 10**8}")
    c.say("fund the gap")
    r = c.say(text)
    assert "still waiting" not in r["reply"]


def test_no_reminder_without_a_waiting_plan(client, rt):
    r = Chat(client, "ask2-none").say("should we draw ¥100,000 on the line?")
    assert "still waiting" not in r["reply"] and not r["awaiting_confirmation"]


def test_the_agent_key_is_never_told_about_the_owners_plan(client, rt):
    r = Chat(client, "ask2-agent", owner=False).say("should we draw ¥100,000 on the line?")
    assert "still waiting" not in r["reply"] and "3,113" not in r["reply"]
