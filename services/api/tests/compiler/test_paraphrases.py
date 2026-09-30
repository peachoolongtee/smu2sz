"""The rules grammar handles reasonable paraphrases of the fixture phrasings, in English and Chinese."""

from __future__ import annotations

from typing import Any

import pytest

from app.compiler import Compiler
from app.compiler.parsing import parse_count, parse_days, parse_money, parse_rate_bp
from app.domain.models import CompileStatus, DurationKind, ObligationType, SourceDocument

T = ObligationType

# text -> [(type, rate_bp, days_delta, base amount_fen, duration, invoices)]
CASES: list[tuple[str, list[tuple[Any, ...]]]] = [
    ("Happy to pay the ¥420,000 invoice early at 1.2%.",
     [(T.IMMEDIATE_DISCOUNT, 120, None, 42_000_000, "ONE_OFF", None)]),
    ("We'll pay early for a 1.2% discount.",
     [(T.IMMEDIATE_DISCOUNT, 120, None, None, "ONE_OFF", None)]),
    ("We can settle 42万 ahead of time at 1.2%.",
     [(T.IMMEDIATE_DISCOUNT, 120, None, 42_000_000, "ONE_OFF", None)]),
    ("A 2% discount for paying today, and we want 60-day terms from now on.",
     [(T.IMMEDIATE_DISCOUNT, 200, None, None, "ONE_OFF", None),
      (T.TERMS_EXTENSION, None, None, None, "RECURRING_PERPETUAL", None)]),
    ("Please extend terms from 45 to 60 days going forward.",
     [(T.TERMS_EXTENSION, None, 15, None, "RECURRING_PERPETUAL", None)]),
    ("Net 60 please.",
     [(T.TERMS_EXTENSION, None, None, None, "RECURRING_PERPETUAL", None)]),
    ("Give us 60 days on the next two invoices instead of 45.",
     [(T.TERMS_EXTENSION, None, 15, None, "RECURRING_BOUNDED", 2)]),
    ("Can you give us 1% off next quarter on up to 42万?",
     [(T.CONTINGENT_REBATE, 100, None, 42_000_000, "ONE_OFF", None)]),
    ("We'd like a 1.5% rebate on next quarter's orders, capped at ¥300,000.",
     [(T.CONTINGENT_REBATE, 150, None, 30_000_000, "ONE_OFF", None)]),
    ("Deliver everything to our Shenzhen warehouse and we'll switch you to 30-day terms.",
     [(T.OPERATIONAL_CONCESSION, None, None, None, "RECURRING_PERPETUAL", None),
      (T.TERMS_EXTENSION, None, None, None, "RECURRING_PERPETUAL", None)]),
    ("You promised us a 2% rebate, so confirm it.",
     [(T.CLAIMED_PRIOR_CONCESSION, 200, None, None, "ONE_OFF", None)]),
    ("60-day terms accepted with a 0.45% price adjustment on future invoices.",
     [(T.TERMS_EXTENSION, None, None, None, "RECURRING_PERPETUAL", None),
      (T.PRICE_ADJUSTMENT, 45, None, None, "RECURRING_PERPETUAL", None)]),
    # Chinese
    ("我们可以提前付款，折扣1.2%，但今后账期要改为60天，下季度再给我们1%的返利。",
     [(T.IMMEDIATE_DISCOUNT, 120, None, None, "ONE_OFF", None),
      (T.TERMS_EXTENSION, None, None, None, "RECURRING_PERPETUAL", None),
      (T.CONTINGENT_REBATE, 100, None, None, "ONE_OFF", None)]),
    ("提前结清42万货款，折扣1.2%。",
     [(T.IMMEDIATE_DISCOUNT, 120, None, 42_000_000, "ONE_OFF", None)]),
    ("接下来三张发票账期从30天延长到45天。",
     [(T.TERMS_EXTENSION, None, 15, None, "RECURRING_BOUNDED", 3)]),
    ("请确认上个月你们已经同意的2%返利。",
     [(T.CLAIMED_PRIOR_CONCESSION, 200, None, None, "ONE_OFF", None)]),
    ("合并送货到我们佛山仓库，我们把账期缩短到30天。",
     [(T.OPERATIONAL_CONCESSION, None, None, None, "RECURRING_PERPETUAL", None),
      (T.TERMS_EXTENSION, None, None, None, "RECURRING_PERPETUAL", None)]),
]


def _compile(c: Compiler, text: str):  # type: ignore[no-untyped-def]
    return c.compile_offer([SourceDocument(doc_id="p", channel="chat", sender_id="BUYER-1", received_day=0, text=text)], "BUYER-1")


@pytest.mark.parametrize(("text", "expected"), CASES, ids=[c[0][:40] for c in CASES])
def test_paraphrase(rules_compiler: Compiler, text: str, expected: list[tuple[Any, ...]]) -> None:
    offer = _compile(rules_compiler, text)
    got = [(o.type, o.rate_bp, o.days_delta, o.base.amount_fen, o.duration.kind.value, o.duration.invoices) for o in offer.obligations]
    assert got == expected
    assert offer.status == CompileStatus.COMPILED


def test_as_usual_variants(rules_compiler: Compiler) -> None:
    for text in ("Early pay at 1.5%. Same terms as before.", "提前付款1.5%，其他照旧。", "Early pay at 1.5%, as usual."):
        offer = _compile(rules_compiler, text)
        assert [o.type for o in offer.obligations] == [T.IMMEDIATE_DISCOUNT]
        assert any(a.field == "unresolved_reference" for a in offer.abstentions)


def test_similar_wording_different_economics(rules_compiler: Compiler) -> None:
    a = _compile(rules_compiler, "Take 45 days on the next three invoices instead of 30.").obligations[0]
    b = _compile(rules_compiler, "Take 45 days going forward instead of 30.").obligations[0]
    assert a.days_delta == b.days_delta == 15
    assert a.duration.kind == DurationKind.RECURRING_BOUNDED and b.duration.kind == DurationKind.RECURRING_PERPETUAL


@pytest.mark.parametrize(("text", "fen"), [
    ("¥420k", 42_000_000), ("¥420,000", 42_000_000), ("42万", 42_000_000), ("400,000元", 40_000_000),
    ("¥1.2m", 120_000_000), ("RMB 250,000", 25_000_000), ("¥150", 15_000), ("¥841.64", 84_164), ("50万元", 50_000_000),
    ("420,000", None), ("¥0.001", None),
])
def test_money(text: str, fen: int | None) -> None:
    assert parse_money(text) == fen


@pytest.mark.parametrize(("text", "bp"), [("1.2%", 120), ("0.75%", 75), ("2.8 %", 280), ("百分之1.5", 150), ("1％", 100), ("0.125%", None)])
def test_rates(text: str, bp: int | None) -> None:
    assert parse_rate_bp(text) == bp


def test_days_and_counts() -> None:
    assert parse_days("60 days") == parse_days("60-day") == parse_days("60天") == parse_days("Net 60") == 60
    assert parse_days("30") == 30 and parse_days("10 business days") == 10
    assert parse_count("three") == parse_count("3") == parse_count("三") == 3 and parse_count("十二") == 12
