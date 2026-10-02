"""Verdict display for near-limit covenant breaches (EV-12) and the Tier-1 early-pay-only acceptance rule."""

from __future__ import annotations

from app.compiler import compile_offer
from app.domain.fixtures import load_scenario
from app.domain.models import (
    Outcome,
    SourceDocument,
    Tier,
    Violation,
    ViolationCode,
)
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate
from app.verifier.display import describe_all, fmt_x4, month_ranges, precise


def _dscr(month: int, exact: str, observed: str = "1.25x", source: str = "mandate") -> Violation:
    return Violation(
        code=ViolationCode.DSCR_BREACH, month=month, observed=observed, limit="1.25x",
        message=f"DSCR {observed} in month {month} is below the {source} minimum 1.25x",
        formula=f"EBITDA_m / DS_m: ¥90,000.00 / ¥72,000.02 = {observed} < 1.25x",
        inputs={"dscr_exact": exact, "limit_exact": "5/4", "source": source},
    )


def test_breach_below_display_precision_shows_four_decimals() -> None:
    v = precise(_dscr(3, "4500000/3600001"))
    assert v.observed == "1.2499x"
    assert "DSCR 1.2499x in month 3" in v.message and "= 1.2499x < 1.25x" in (v.formula or "")


def test_visible_breach_is_left_alone() -> None:
    v = _dscr(3, "9000000/7500000", observed="1.20x")
    assert precise(v) == v


def test_leverage_rounds_away_from_the_limit() -> None:
    assert fmt_x4(__import__("fractions").Fraction(250000001, 100000000), down=False) == "2.5001x"
    assert fmt_x4(__import__("fractions").Fraction(249999999, 100000000), down=True) == "2.4999x"


def test_repeated_monthly_breaches_are_grouped() -> None:
    vs = [precise(_dscr(m, "4500000/3600001", source=s)) for m in range(1, 7) for s in ("facility", "mandate")]
    vs.append(precise(_dscr(9, "4500000/3600002")))
    items = describe_all(vs, lambda v: v.code.value)
    assert items == ["DSCR_BREACH: DSCR below 1.25x in months 1–6, 9 (lowest 1.2499x)"]


def test_month_ranges() -> None:
    assert month_ranges([4]) == "month 4"
    assert month_ranges([1, 2, 3, 5, 7, 8]) == "months 1–3, 5, 7–8"


def test_one_fen_dscr_breach_in_a_verdict_summary() -> None:
    state, _ = load_scenario()
    debts = [d.model_copy(update={"monthly_debt_service_fen": 7_200_002}) for d in state.debts]
    state = state.model_copy(update={"cash_fen": 80_000_000, "debts": debts})
    offer = compile_offer([SourceDocument(doc_id="d1", channel="chat", sender_id="BUYER-1", received_day=0,
                                          text="Half a percent off next quarter's purchases, up to ¥300,000.")],
                          "BUYER-1")
    v = evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex()).verdict
    dscr = [x for x in v.violations if x.code == ViolationCode.DSCR_BREACH]
    assert dscr and all(x.observed != x.limit for x in dscr)
    assert v.summary.count("DSCR_BREACH") == 1 and "DSCR below 1.25x in month" in v.summary


# ---------------------------------------------------------------- Tier-1 acceptance is early pay only


def _verdict(text: str):  # type: ignore[no-untyped-def]
    state, _ = load_scenario()
    offer = compile_offer([SourceDocument(doc_id="t1", channel="chat", sender_id="BUYER-1", received_day=0, text=text)],
                          "BUYER-1")
    return evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex()).verdict


def test_early_pay_discount_on_the_invoice_is_tier_1() -> None:
    v = _verdict("Deduct 0.6% and we'll settle the open ¥420,000 invoice early.")
    assert (v.outcome, v.required_tier) == (Outcome.ACCEPT, Tier.TIER_1)


def test_early_pay_discount_without_the_invoice_amount_waits_for_the_owner() -> None:
    """ADR-0005: binding to "the only open receivable" never qualifies for autonomy."""
    v = _verdict("Deduct 0.6% and we'll settle the open invoice early.")
    assert (v.outcome, v.required_tier) == (Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2)


def test_small_rebate_waits_for_the_owner() -> None:
    v = _verdict("A quarter percent back on next quarter's orders, please.")
    assert (v.outcome, v.required_tier) == (Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2)
    assert "only an early-payment discount on a named invoice" in v.summary and "CONTINGENT_REBATE" in v.summary
