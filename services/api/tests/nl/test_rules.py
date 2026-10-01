"""The deterministic parser: every owner intent in English and Chinese, and exact value parsing."""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.nl import lexicon as lx
from app.nl.models import Intent
from app.nl.rules import fixture_id, parse

STATE = load_scenario()[0]

CASES = [
    ("Evaluate EX01", Intent.EVALUATE_OFFER),
    ("评估 EX02", Intent.EVALUATE_OFFER),
    ("Is this a good offer? “We can pay early at 1.5%.”", Intent.EVALUATE_OFFER),
    ("Negotiate EX01 with the buyer", Intent.NEGOTIATE),
    ("Send the counters", Intent.NEGOTIATE),
    ("发送反报价", Intent.NEGOTIATE),
    ("Get paid early on the Foshan invoice without giving anything away next quarter.", Intent.ACCELERATE_RECEIPT),
    ("佛山那张发票想提前收款", Intent.ACCELERATE_RECEIPT),
    ("Fund the cash gap", Intent.FUND_GAP),
    ("fund it", Intent.FUND_GAP),
    ("帮我补足资金缺口", Intent.FUND_GAP),
    ("Draw ¥50,000 on the credit line", Intent.FUND_GAP),
    ("Repay the credit line", Intent.REPAY_FACILITY),
    ("偿还授信额度", Intent.REPAY_FACILITY),
    ("How's our cash position?", Intent.SHOW_STATUS),
    ("现金状况怎么样", Intent.SHOW_STATUS),
    ("Why was it rejected?", Intent.EXPLAIN),
    ("为什么被拒绝？", Intent.EXPLAIN),
    ("What if we give Foshan 60-day terms?", Intent.WHAT_IF),
    ("如果给佛山60天账期呢？", Intent.WHAT_IF),
    ("Approve APR-000001", Intent.APPROVE),
    ("Reject APR-000002", Intent.REJECT),
    ("批准待审批的操作", Intent.APPROVE),
    ("Book me a flight", None),
    ("help me sort out our cash", Intent.AMBIGUOUS),
    ("Can we buy the ¥600k machine?", Intent.CAPEX),
    ("Sign a personal guarantee for the loan", Intent.OUT_OF_SCOPE),
    ("把工厂抵押给银行", Intent.OUT_OF_SCOPE),
]


@pytest.mark.parametrize(("text", "intent"), CASES)
def test_intent(text, intent):
    p = parse(text, STATE)
    assert (p.intent if p else None) == intent


def test_tier3_slots():
    assert parse("Sign a personal guarantee", STATE).slots.tier3 == "SIGN_PERSONAL_GUARANTEE"
    assert parse("发行新股权融资", STATE).slots.tier3 == "ISSUE_EQUITY"
    assert parse("Lower the reserve floor to ¥200,000", STATE).slots.tier3 == "CHANGE_MANDATE"


def test_pending_plan_turns_confirmation_and_correction():
    assert parse("go ahead", STATE, pending_plan=True).confirm_plan
    assert parse("执行", STATE, pending_plan=True).intent == Intent.APPROVE
    p = parse("actually make it 0.8%", STATE, pending_plan=True)
    assert p.correction and p.slots.rate_bp == 80
    p = parse("no, use invoice financing instead", STATE, pending_plan=True)
    assert p.correction and p.slots.use_financing
    assert parse("cancel", STATE, pending_plan=True).intent == Intent.REJECT
    explicit = parse("approve APR-000001", STATE, pending_plan=True)  # an explicit approval id is not the plan
    assert explicit.intent == Intent.APPROVE and not explicit.confirm_plan
    p = parse("actually make it 0.8%", STATE)  # nothing pending: not a correction
    assert p is None or not p.correction


def test_fixture_ids():
    assert fixture_id("evaluate ex01") == "EX01_PACKAGE"
    assert fixture_id("EX01B please") == "EX01B_REWORDED"
    assert fixture_id("EX08A") == "EX08A_JOINT_BUYER1"
    assert fixture_id("the SEC_DEMO message") == "SEC_DEMO_FASTCAPITAL"
    assert fixture_id("EX99") is None


def test_values_are_exact_integers():
    assert [f.value for f in lx.amounts("¥420k and 50万元 and 500,000 yuan and ¥1,234.56")] == \
        [42_000_000, 50_000_000, 50_000_000, 123_456]
    assert [f.value for f in lx.rates("0.85% or 80bp or 1.2％")] == [85, 80, 120]
    assert [f.value for f in lx.rates("0.855%")] == []  # sub-bp: ignored, never rounded
    assert [f.value for f in lx.days("60-day terms, 45天")] == [60, 45]
    assert lx.invoices("the next three invoices") == 3


def test_counterparty_names():
    assert lx.find_counterparty("the Foshan invoice", STATE) == ["BUYER-1"]
    assert lx.find_counterparty("东莞的订单", STATE) == ["BUYER-2"]
    assert lx.find_counterparty("the bank", STATE) == []


def test_language_detection():
    assert lx.detect_lang("Fund the gap") == "en"
    assert lx.detect_lang("帮我补足资金缺口") == "zh"
