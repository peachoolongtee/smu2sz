"""Review gap G1: an owner who states a new bill, invoice, delay or figure is told plainly that chat cannot record it.
The intent is read-only: no operation, no pending plan, no change to the books (EN and ZH)."""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.nl import Intent
from app.nl.rules import parse
from tests.nl.conftest import Chat

EN = [
    "We have a supplier bill of ¥80,000 due on day 30, add it to the forecast",
    "Record a ¥50,000 payable due on day 20",
    "We will pay the supplier 10 days late",
    "Our EBITDA is actually ¥120,000 a month",
    "Please add a new invoice from the packaging supplier to the books",
]
ZH = [
    "我们有一张8万元的供应商账单，30天后到期，请加入预测",
    "记一笔5万元的应付款，第20天到期",
    "我们要延迟付款15天",
    "新增一笔账单",
    "EBITDA 其实是 12 万",
]


def _books(rt) -> tuple:
    s = rt.store.get_state()
    return (s.state_version, s.cash_fen, len(s.flows), len(s.receivables), len(rt.store.operations()),
            len(rt.store.approvals()))


@pytest.mark.parametrize("text", EN)
def test_english_statements_are_answered_as_not_recorded(client, rt, text):
    before = _books(rt)
    r = Chat(client, "rf-en").say(text)
    assert r["intent"] == "RECORD_FACT"
    reply = r["reply"].lower()
    assert "cannot record" in reply and "forecast is unchanged" in reply
    assert "through the books" in reply and "not recorded or run anything" in reply
    assert r["operations"] == [] and r["awaiting_confirmation"] is False and not r.get("plan")
    assert _books(rt) == before


@pytest.mark.parametrize("text", ZH)
def test_chinese_statements_are_answered_as_not_recorded(client, rt, text):
    before = _books(rt)
    r = Chat(client, "rf-zh").say(text, lang="zh")
    assert r["intent"] == "RECORD_FACT"
    assert "无法记录" in r["reply"] and "预测保持不变" in r["reply"] and "账本" in r["reply"]
    assert r["operations"] == [] and r["awaiting_confirmation"] is False and not r.get("plan")
    assert _books(rt) == before


def test_the_amount_the_owner_named_is_echoed_and_the_agent_channel_gets_the_same_answer(client, rt):
    r = Chat(client, "rf-amt").say(EN[0])
    assert "¥80,000.00" in r["reply"]
    agent = Chat(client, "rf-agent", owner=False).say(EN[0])  # read-only: no sign-in needed, nothing disclosed
    assert agent["intent"] == "RECORD_FACT" and agent["operations"] == []


def test_it_does_not_arm_a_confirmation(client, rt):
    chat = Chat(client, "rf-confirm")
    chat.say(EN[0])
    before = _books(rt)
    r = chat.say("go ahead")
    assert r["operations"] == [] and _books(rt) == before


@pytest.mark.parametrize("text,intent", [
    ("get Foshan to pay early", Intent.ACCELERATE_RECEIPT),
    ("We have an invoice for Foshan, can we get it paid early?", Intent.ACCELERATE_RECEIPT),
    ("show me the 13 week forecast", Intent.SHOW_STATUS),
    ("list the open invoices", Intent.SHOW_STATUS),
    ("fund the gap", Intent.FUND_GAP),
    ("what is our DSCR?", Intent.SHOW_RATIOS),
    ("how are we doing", Intent.SHOW_STATUS),
])
def test_nearby_requests_keep_their_intent(text, intent):
    state, _ = load_scenario()
    p = parse(text, state)
    assert p is not None and p.intent == intent


def test_the_closed_command_grammar_is_untouched(client, rt):
    r = Chat(client, "rf-cmd").say("draw ¥100,000 on the credit line")
    assert r["intent"] != "RECORD_FACT"
