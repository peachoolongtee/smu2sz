"""Intent classes missed on the second held-out set: forecasts and receivables, zh draws, early collection,
pasted offers, counters, vague delegation, and FUND_GAP behaving the same in English and Chinese.

The report's miss CLASSES guided this file; every utterance was written for it and none is copied from
fixtures/heldout2.
"""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.nl.rules import parse
from tests.nl.conftest import Chat, ops

STATE = load_scenario()[0]


@pytest.mark.parametrize(("text", "intent"), [
    # status: forecasts, cash flow, receivables
    ("pull up the cash flow forecast", "SHOW_STATUS"),
    ("what does the 8-week projection look like", "SHOW_STATUS"),
    ("应收账款列一下", "SHOW_STATUS"),
    ("who owes us money right now?", "SHOW_STATUS"),
    ("下周的现金流怎么样", "SHOW_STATUS"),
    ("how's our cash flow looking", "SHOW_STATUS"),
    # "cash flow" as a topic is not a request to see it
    ("We should really fix our cash flow somehow.", "AMBIGUOUS"),
    # zh / en draws
    ("从信用额度借20万出来周转", "FUND_GAP"),
    ("在授信里提5万出来", "FUND_GAP"),
    # early collection, en / zh / mixed
    ("chase Dongguan to settle their invoice sooner", "ACCELERATE_RECEIPT"),
    ("try to collect Dongguan's money earlier", "ACCELERATE_RECEIPT"),
    ("东莞那笔货款能不能让他们早点打款？折扣最多0.6%", "ACCELERATE_RECEIPT"),
    ("Dongguan 那张 invoice 可以 early pay 吗", "ACCELERATE_RECEIPT"),
    # a repayment that says "sooner" is still a repayment
    ("can we pay off the credit line sooner", "REPAY_FACILITY"),
    # pasted offers
    ("Dongguan just emailed: 'We can pay the ¥250k early at 0.8% if you extend us to 50 days.' Should we accept?",
     "EVALUATE_OFFER"),
    ("佛山那边发来：提前付款扣1个点。能接吗", "EVALUATE_OFFER"),
    ("the customer wrote: we want 0.5% back on next quarter's orders. thoughts?", "EVALUATE_OFFER"),
    # counters and negotiation verbs outrank an early-pay cue
    ("counter Dongguan at 0.6%", "NEGOTIATE"),
    ("跟东莞谈谈，提前付款最多给0.5%", "NEGOTIATE"),
    ("Negotiate with Foshan, a 0.3% rebate at most", "NEGOTIATE"),
    # vague delegation: one clarifying question
    ("sort that thing out with Dongguan", "AMBIGUOUS"),
    ("make it better", "AMBIGUOUS"),
    ("那件事怎么样了", "AMBIGUOUS"),
])
def test_intent(text: str, intent: str) -> None:
    p = parse(text, STATE)
    assert p is not None and p.intent.value == intent, (text, p)


def test_cash_flow_as_a_topic_is_not_a_status_request() -> None:
    p = parse("Compose a limerick about cash flow", STATE)
    assert p is None or p.intent.value != "SHOW_STATUS"


def test_pasted_offer_keeps_only_the_buyers_words() -> None:
    p = parse("Dongguan just emailed: 'We can pay the ¥250k early at 0.8% if you extend us to 50 days.' "
              "Should we accept?", STATE)
    assert p is not None and p.slots.quoted_text == "We can pay the ¥250k early at 0.8% if you extend us to 50 days."
    p = parse("佛山那边发来：提前付款扣1个点。能接吗", STATE)
    assert p is not None and p.slots.quoted_text == "提前付款扣1个点。"


@pytest.mark.parametrize(("text", "rebate"), [
    ("Negotiate with Foshan, a 0.3% rebate at most", 30),
    ("跟东莞谈谈，返点最多0.4%", 40),
    ("counter Dongguan at 0.6%", None),
])
def test_rebate_slot(text: str, rebate: int | None) -> None:
    p = parse(text, STATE)
    assert p is not None and p.slots.rebate_bp == rebate


@pytest.mark.parametrize("text", [
    "Get the Dongguan invoice paid sooner, but don't give anything away",
    "get Foshan to pay early and give nothing away next quarter",
    "让佛山提前付款，不要给任何让利",
])
def test_zero_forward_slot(text: str) -> None:
    p = parse(text, STATE)
    assert p is not None and p.intent.value == "ACCELERATE_RECEIPT" and p.slots.zero_forward


# ---------------------------------------------------------------- FUND_GAP: the same rule in en and zh


@pytest.mark.parametrize(("text", "tentative"), [
    ("Cover the payroll gap", True),
    ("把工资缺口补上", True),
    ("Fund the cash gap", True),
    ("帮我补足资金缺口", True),
    ("Find me the cheapest way to cover the payroll gap", True),
    ("帮我找最便宜的方式补上工资缺口", True),
    ("how can we close the funding gap?", True),
    ("资金缺口怎么补？", True),
    ("payroll is short this month", True),
    ("这个月工资不够", True),
])
def test_fund_gap_without_an_amount_always_proposes(text: str, tentative: bool) -> None:
    p = parse(text, STATE)
    assert p is not None and p.intent.value == "FUND_GAP" and p.tentative is tentative


@pytest.mark.parametrize("text", ["Find me the cheapest way to cover the cash gap", "帮我找最便宜的方式把资金缺口补上"])
def test_find_me_a_way_proposes_and_waits_in_both_languages(client, text: str) -> None:
    c = Chat(client, f"t-explore-{len(text)}")
    r = c.say(text)
    assert r["intent"] == "FUND_GAP" and ops(r) == [] and r["awaiting_confirmation"]
    r = c.say("go ahead" if text.isascii() else "执行")
    assert r["intent"] == "FUND_GAP" and ops(r) and all(s == "EXECUTED" for _, s in ops(r))


def test_cost_what_if_does_not_ask_for_a_buyer(client) -> None:
    r = Chat(client, "t-rent").say("what if rent rises 5% next month")
    assert r["intent"] == "WHAT_IF" and r["clarification"] is None and ops(r) == []
