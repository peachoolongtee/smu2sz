"""Intent coverage for looser owner phrasings (EV-09), CJK-glued ids (EV-08) and specific clarification replies.

The utterances are written for this file, not taken from fixtures/heldout.
"""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.nl.rules import parse
from tests.nl.conftest import Chat, ops

STATE, _ = load_scenario()


@pytest.mark.parametrize(("text", "intent"), [
    # needs described rather than a funding instruction
    ("Rent is due Friday and the account is thin, sort it", "FUND_GAP"),
    ("Wages go out next week and we can't cover them", "FUND_GAP"),
    ("Make sure cash doesn't fall under the floor", "FUND_GAP"),
    ("月底要发工资，资金不够，帮我找钱", "FUND_GAP"),
    # repaying the line
    ("把信用额度的欠款还了", "REPAY_FACILITY"),
    ("Clear the balance on the credit line", "REPAY_FACILITY"),
    # position questions
    ("我们账上现在有多少现金？", "SHOW_STATUS"),
    ("How much money do we have right now?", "SHOW_STATUS"),
    ("Is there any risk of breaking a covenant?", "SHOW_STATUS"),
    ("我们下个月会不会跌破储备线？", "SHOW_STATUS"),
    ("Will we have enough cash for payroll?", "SHOW_STATUS"),
    # hypotheticals
    ("What happens if we accept a 1.5% early payment discount?", "WHAT_IF"),
    ("How would 70-day terms for Dongguan affect our cash?", "WHAT_IF"),
    ("给东莞3%的返利会怎么样？", "WHAT_IF"),
    # collections
    ("Get the Foshan invoice paid early", "ACCELERATE_RECEIPT"),
    # vague delegation: one clarifying question
    ("Can you take care of it?", "AMBIGUOUS"),
    ("你看着处理吧。", "AMBIGUOUS"),
    ("Just do the normal thing.", "AMBIGUOUS"),
    ("这事你决定。", "AMBIGUOUS"),
    ("帮我搞定。", "AMBIGUOUS"),
])
def test_rules_parse(text: str, intent: str) -> None:
    p = parse(text, STATE)
    assert p is not None and p.intent.value == intent, (text, p)


def test_ids_glued_to_chinese_text() -> None:
    p = parse("请批准APR-000042。", STATE)
    assert p is not None and p.intent.value == "APPROVE" and p.slots.approval_id == "APR-000042"
    p = parse("帮我评估一下EX06。", STATE)
    assert p is not None and p.intent.value == "EVALUATE_OFFER" and p.slots.fixture_id == "EX06_THREE_INVOICES"


def test_loose_funding_request_proposes_and_waits(client) -> None:
    r = Chat(client, "t-soft-fund").say("Wages go out next week and we can't cover them")
    assert r["intent"] == "FUND_GAP" and ops(r) == [] and r["awaiting_confirmation"]
    r = Chat(client, "t-soft-fund").say("go ahead")
    assert r["intent"] == "FUND_GAP" and ops(r) and all(s == "EXECUTED" for _, s in ops(r))


def test_vague_request_gets_one_question(client) -> None:
    r = Chat(client, "t-vague").say("Can you take care of it?")
    assert r["intent"] == "AMBIGUOUS" and r["clarification"] and len(r["clarification"]["options"]) == 3


def test_what_if_early_pay_names_the_only_invoice_holder(client) -> None:
    r = Chat(client, "t-whatif").say("What happens if we accept a 1.1% early payment discount?")
    assert r["intent"] == "WHAT_IF" and "only buyer with an open invoice" in r["reply"] and ops(r) == []


@pytest.mark.parametrize(("text", "phrase"), [
    ("Can you do 1.2% off?", "which invoice, or which period's purchases"),
    ("0.3% rebate on everything we buy from you from now on.", "which invoice, or which period's purchases"),
    ("Either 50 or 70-day terms, please.", "more than one value for a term"),
])
def test_counterparty_clarification_is_specific(client, text: str, phrase: str) -> None:
    r = Chat(client, "t-cp-clarify", actor="COUNTERPARTY", counterparty_id="BUYER-1").say(text)
    assert r["intent"] == "COUNTERPARTY_MESSAGE" and ops(r) == []
    assert phrase in r["reply"]
