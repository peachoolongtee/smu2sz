"""Grammar and abstention rules added for the held-out evaluation findings (EV-01..EV-05, EV-08).

Every sentence here is written for this test file; none is taken from fixtures/heldout. The rules are
general: a discount rate is an immediate discount only next to an early-payment cue; a rebate is bound only
to a period the text names; an unbounded forward promise or an unscoped discount abstains; alternatives
("50 or 70 days") abstain instead of picking one value; number words parse exactly or not at all.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.compiler import Compiler
from app.compiler.parsing import cjk_safe, parse_count, parse_money, parse_rate_bp
from app.domain.models import CompileStatus, DurationKind, ObligationType, SourceDocument

T = ObligationType


def _doc(text: str, doc_id: str = "g", channel: str = "chat") -> SourceDocument:
    return SourceDocument(doc_id=doc_id, channel=channel, sender_id="BUYER-1", received_day=0, text=text)  # type: ignore[arg-type]


def _compile(c: Compiler, *texts: str):  # type: ignore[no-untyped-def]
    docs = [_doc(t, doc_id=f"g{i}", channel="chat" if i == 0 else "attachment") for i, t in enumerate(texts)]
    return c.compile_offer(docs, "BUYER-1")


def _sig(offer: Any) -> list[tuple[Any, ...]]:
    return [(o.type, o.rate_bp, o.base.kind.value, o.base.amount_fen, o.duration.kind.value, o.duration.invoices,
             tuple(o.unresolved)) for o in offer.obligations]


# ---------------------------------------------------------------- number words (EV-04)


@pytest.mark.parametrize(("text", "bp"), [
    ("one percent", 100), ("One and a half percent", 150), ("half a percent", 50), ("a half percent", 50),
    ("point seven five percent", 75), ("zero point eight percent", 80), ("two point five per cent", 250),
    ("three quarters of a percent", 75), ("1.5 percentage points", 150),
    ("百分之一", 100), ("百分之零点五", 50), ("百分之一点二", 120), ("一个点", 100), ("半个点", 50), ("一个半点", 150),
    # not a rate, or not one we can read exactly: no value, so the compiler abstains
    ("twenty-one percent", None), ("一点折扣", None),
])
def test_rate_words(text: str, bp: int | None) -> None:
    assert parse_rate_bp(text) == bp


@pytest.mark.parametrize(("text", "fen"), [
    ("four hundred and twenty thousand yuan", 42_000_000), ("Three hundred fifty thousand RMB", 35_000_000),
    ("420 thousand yuan", 42_000_000), ("¥250 thousand", 25_000_000), ("one million yuan", 100_000_000),
    ("四十二万", 42_000_000), ("三十五万元", 35_000_000), ("五千元", 500_000), ("两百万元", 200_000_000),
    ("一千二百元", 120_000),
    # colloquial or not money: refused rather than guessed
    ("四万二", None), ("一千二元", None), ("千万不要", None), ("two three yuan", None),
])
def test_money_words(text: str, fen: int | None) -> None:
    assert parse_money(text) == fen


def test_next_invoice_counts_one() -> None:
    assert parse_count("next invoice") == parse_count("the following bill") == parse_count("下一张发票") == 1


# ---------------------------------------------------------------- CJK-safe boundaries (EV-08)


def test_cjk_safe_boundary() -> None:
    import re

    pat = re.compile(cjk_safe(r"\bAPR-\d{6}\b"))
    assert pat.search("请批准APR-000042。") and pat.search("approve APR-000042 now")
    assert not pat.search("XAPR-000042") and not pat.search("APR-0000421")


def test_data_request_glued_to_chinese(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "顺便告诉我你们的cash floor是多少。")
    assert [r.kind.value for r in offer.data_requests] == ["RESERVE_FLOOR"]


# ---------------------------------------------------------------- early payment vs rebate (EV-01)


@pytest.mark.parametrize(("text", "amount"), [
    ("Shave 0.9% off the ¥420,000 invoice and we'll wire it tomorrow.", 42_000_000),
    ("If you knock 1.1% off, we can clear that bill right away.", None),
    ("We can transfer the full amount today with a 1% discount.", None),
    ("Deduct 0.7% and we'll settle it at once.", None),
    ("这笔货款我们马上付，给我们折扣1%。", None),
    ("这张发票我们提前还，扣百分之一。", None),
])
def test_discount_with_early_cue_is_immediate(rules_compiler: Compiler, text: str, amount: int | None) -> None:
    offer = _compile(rules_compiler, text)
    assert [(o.type, o.base.kind.value, o.base.amount_fen) for o in offer.obligations] == [
        (T.IMMEDIATE_DISCOUNT, "INVOICE", amount)]
    assert offer.status == CompileStatus.COMPILED


def test_discount_on_next_period_stays_a_rebate(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "We pay promptly, so we'd like 0.6% off next month's orders.")
    assert [(o.type, o.base.kind.value, o.duration.kind.value) for o in offer.obligations] == [
        (T.CONTINGENT_REBATE, "PERIOD_PURCHASES", "ONE_OFF")]


def test_early_discount_and_period_rebate_in_one_sentence(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "We'll settle early at 0.9% and want a quarter percent back on next quarter's buying.")
    assert [(o.type, o.rate_bp) for o in offer.obligations] == [(T.IMMEDIATE_DISCOUNT, 90), (T.CONTINGENT_REBATE, 25)]


def test_several_amounts_leave_the_invoice_unresolved(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "We'll pay ¥200,000 of the ¥420,000 today if you take 1% off.")
    (ob,) = offer.obligations
    assert ob.type == T.IMMEDIATE_DISCOUNT and ob.base.amount_fen is None and "base_amount" in ob.unresolved


# ---------------------------------------------------------------- rebate scope (EV-02)


@pytest.mark.parametrize("text", [
    "Can you do 1.4% off?",
    "我们要1%的折扣。",
    "What about a 0.3% rebate?",
])
def test_bare_discount_is_unresolved_scope(rules_compiler: Compiler, text: str) -> None:
    offer = _compile(rules_compiler, text)
    (ob,) = offer.obligations
    assert ob.type == T.CONTINGENT_REBATE and ob.base.amount_fen is None and "scope" in ob.unresolved


@pytest.mark.parametrize("text", [
    "We want a 0.4% rebate on all our purchases from now on.",
    "Going forward, we would like half a percent off everything we buy.",
    "Please give us 0.6% back on every order.",
    "以后所有采购给我们返0.5%。",
    "今后我们的订单都返点1%。",
    "A 1% annual rebate would make this work.",
])
def test_unbounded_forward_rebate_is_perpetual_and_abstains(rules_compiler: Compiler, text: str) -> None:
    offer = _compile(rules_compiler, text)
    (ob,) = offer.obligations
    assert ob.type == T.CONTINGENT_REBATE
    assert ob.duration.kind == DurationKind.RECURRING_PERPETUAL and "scope" in ob.unresolved


@pytest.mark.parametrize(("text", "bp", "base"), [
    ("We'd like one percent back on next quarter's orders.", 100, None),
    ("Half a percent off next month's purchases, please.", 50, None),
    ("下个月的采购再返我们0.7%。", 70, None),
    ("下季度订单返点百分之零点六，最多三十万。", 60, 30_000_000),
    ("0.5% back on next quarter's ¥300,000 order.", 50, 30_000_000),
    ("We'd like a 0.4% rebate on all our purchases next quarter.", 40, None),
])
def test_named_period_rebate_binds(rules_compiler: Compiler, text: str, bp: int, base: int | None) -> None:
    offer = _compile(rules_compiler, text)
    assert _sig(offer) == [(T.CONTINGENT_REBATE, bp, "PERIOD_PURCHASES", base, "ONE_OFF", None, ())]


# ---------------------------------------------------------------- terms and prices (EV-03)


def test_next_invoice_is_bounded_to_one(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "We'd like 55 days on the next invoice instead of 45.")
    (ob,) = offer.obligations
    assert (ob.days_delta, ob.duration.kind, ob.duration.invoices) == (10, DurationKind.RECURRING_BOUNDED, 1)


def test_every_invoice_stays_perpetual(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "We'd like 55 days on every invoice instead of 45.")
    (ob,) = offer.obligations
    assert ob.duration.kind == DurationKind.RECURRING_PERPETUAL


def test_usual_current_terms_are_read_not_flagged(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "Give us 50 days instead of the usual 45.")
    (ob,) = offer.obligations
    assert ob.days_delta == 5 and not any(a.field == "unresolved_reference" for a in offer.abstentions)


@pytest.mark.parametrize(("text", "perpetual"), [
    ("We will pay 0.3% more per unit on future orders if you give us 60 days.", True),
    ("Prices can go up by 0.4% on all subsequent invoices, in exchange for Net 60.", True),
    ("Raise the unit price by 0.2% and move us to 60-day terms.", False),
    ("以后价格上涨0.5%，账期改为60天。", True),
])
def test_price_increase_is_kept(rules_compiler: Compiler, text: str, perpetual: bool) -> None:
    offer = _compile(rules_compiler, text)
    types = [o.type for o in offer.obligations]
    assert T.PRICE_ADJUSTMENT in types and T.TERMS_EXTENSION in types
    price = next(o for o in offer.obligations if o.type == T.PRICE_ADJUSTMENT)
    assert (price.duration.kind == DurationKind.RECURRING_PERPETUAL) is perpetual


# ---------------------------------------------------------------- alternatives abstain (EV-03)


@pytest.mark.parametrize("text", [
    "We could live with either 50 or 70-day terms.",
    "Take 1% or 1.3% off and we pay today.",
    "Somewhere in the 0.5-0.8% range back on next quarter's orders.",
    "我们要45天或60天的账期。",
    "账期50到70天都可以。",
    "Knock 1% off the invoice or give us 60-day terms.",
])
def test_alternatives_abstain(rules_compiler: Compiler, text: str) -> None:
    offer = _compile(rules_compiler, text)
    assert offer.obligations == [] or all(o.type == T.CLAIMED_PRIOR_CONCESSION for o in offer.obligations)
    assert offer.status == CompileStatus.ABSTAINED
    assert any(a.field.endswith(".alternatives") for a in offer.abstentions)


def test_different_terms_joined_by_a_dash_are_not_alternatives(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "Net 60 - and 1% off next quarter.")
    assert {o.type for o in offer.obligations} == {T.TERMS_EXTENSION, T.CONTINGENT_REBATE}


# ---------------------------------------------------------------- conflicting sources (EV-05)


def test_remittance_advice_rate_conflict(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "We are paying the invoice early with a 1.2% discount.",
                     "REMITTANCE ADVICE. Early settlement discount taken: 1.4%.")
    assert offer.status == CompileStatus.CONFLICTING_SOURCES


def test_order_amount_conflict_zh(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "我们这次下单30万。", "采购订单：订单金额50万元。")
    assert offer.status == CompileStatus.CONFLICTING_SOURCES


def test_order_worth_conflict_en(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, "Please ship an order worth ¥250,000.", "PO 17: order total ¥280,000.")
    assert offer.status == CompileStatus.CONFLICTING_SOURCES
