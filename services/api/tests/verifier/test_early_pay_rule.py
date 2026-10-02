"""ADR-0007: when an early-payment discount is worth taking (audit F1, F2).

Test 1: the break-even for the actual tenor. Test 2: the cash is needed. Test 3: cheaper than the router's plan.
The hand-calculated table of the ADR is one test per row (golden books, floor ¥300,000, day 0, settled day 2).
Offers are typed obligations (no LLM), built the way the what-if and the /nl goal build them.
"""

from __future__ import annotations

import re
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import (
    BaseKind,
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    FacilityStatus,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SourceSpan,
)
from app.domain.money import fmt_pct
from app.financial import project
from app.funding import break_even_discount, marginal_cost, plan
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.verifier import evaluate
from tests.verifier.conftest import bundle, codes

SPAN = [SourceSpan(doc_id="OWNER-DOC", start=0, end=0, text="")]
NEW_CODES = {"EARLY_PAY_NOT_NEEDED", "EARLY_PAY_DEARER_THAN_PLAN"}
WHOLE = 42_000_000  # RCV-A, ¥420,000
# ¥3,113.93: the router's plan with no offer, line 841.64 + an advance of 255,000 (the gap includes the existing loan's
# ¥45,000 day-30 payment): 1,634.79 + 637.50 = 2,272.29 (tests/verifier/test_early_pay_handcalc.py)
C0_GOLDEN = 311_393


def _leg(rate_bp: int, face: int = WHOLE, day: int = 2, oid: str = "EP-O1") -> Obligation:
    return Obligation(
        id=oid, type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=rate_bp,
        effective_day=day, base=ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A", amount_fen=face),
        contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN, confidence=1.0)


def _extension(days: int = 15, oid: str = "EP-EXT") -> Obligation:
    return Obligation(
        id=oid, type=ObligationType.TERMS_EXTENSION, counterparty_id="BUYER-1", days_delta=days,
        base=ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=WHOLE), contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL), spans=SPAN, confidence=1.0)


def _offer(*obs: Obligation) -> CompiledOffer:
    return CompiledOffer(offer_id="EP-TEST", counterparty_id="BUYER-1", doc_ids=["OWNER-DOC"], received_day=0,
                         status=CompileStatus.COMPILED, obligations=list(obs), compiler="nl-test",
                         prompt_version="nl-v1")


def _ev(state, mandate, key, *obs: Obligation):  # type: ignore[no-untyped-def]
    return evaluate(_offer(*obs), state, mandate, trusted_owner_key_hex=key)


def _fen(text: str) -> int:
    return int(Decimal(re.sub(r"[^\d.]", "", text)) * 100)


def _figures(b) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """(C1, C0) in fen, from the violation or the passed check the rule produced."""
    for v in b.verdict.violations:
        if v.code.value in NEW_CODES:
            return _fen(v.inputs["cost_with_offer"]), _fen(v.inputs["cost_without_offer"])
    (p,) = [p for p in b.passed_checks if p.code == "EARLY_PAY_VS_PLAN"]
    return _fen(p.inputs["cost_with_offer"]), _fen(p.inputs["cost_without_offer"])


def _new(b) -> list[str]:  # type: ignore[no-untyped-def]
    return [c for c in codes(b.verdict.violations) if c in NEW_CODES]


def _with(state, **facility_updates: dict[str, Any]):  # type: ignore[no-untyped-def]
    """The state with the named facilities updated: _with(state, **{"FAC-IF": {...}})."""
    return state.model_copy(update={"facilities": [
        f.model_copy(update=facility_updates[f.id]) if f.id in facility_updates else f for f in state.facilities]})


def _cost(state, mandate, obs):  # type: ignore[no-untyped-def]
    p = plan(state, obs, mandate, "COMMITTED")
    t = project(state, obs, p.actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    return t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen


# ---------------------------------------------------------------- 1. the ADR table, one test per row


def test_whole_invoice_at_85bp_costs_3570_against_the_plan_3113_93_and_is_countered(state, mandate, key):
    b = _ev(state, mandate, key, _leg(85))
    assert b.verdict.outcome == Outcome.COUNTER
    assert codes(b.verdict.violations) == ["EARLY_PAY_DEARER_THAN_PLAN"]  # test 1 passes: 0.85% < 0.8832%
    assert _figures(b) == (357_000, C0_GOLDEN)
    v = b.verdict.violations[0]
    assert (v.observed, v.limit) == ("¥3,570.00", "< ¥3,113.93")
    assert v.inputs["plan_with_offer"] == "no funding needed"
    assert v.inputs["plan_without_offer"] == "committed plan: ¥841.64 + ¥2,272.29 = ¥3,113.93"
    assert v.spans == SPAN
    (a,) = b.verdict.counters  # the partial early-pay counter still exists
    assert a.obligations[0].base.amount_fen == 25_720_000 and a.obligations[0].rate_bp == 85


def test_whole_invoice_at_64bp_costs_2688_and_is_accepted(state, mandate, key):
    b = _ev(state, mandate, key, _leg(64))
    assert b.verdict.outcome == Outcome.ACCEPT and _new(b) == []
    assert _figures(b) == (268_800, C0_GOLDEN)
    assert any(p.code == "EARLY_PAY_VS_PLAN" for p in b.passed_checks)


def test_whole_invoice_at_75bp_costs_3150_and_is_countered(state, mandate, key):
    # 42,000,000 × 0.0075 = 315,000 > 311,393 (65 bp, 273,000, is below the plan now; 74 bp, 310,800, too)
    b = _ev(state, mandate, key, _leg(75))
    assert b.verdict.outcome == Outcome.COUNTER
    assert codes(b.verdict.violations) == ["EARLY_PAY_DEARER_THAN_PLAN"]
    assert _figures(b) == (315_000, C0_GOLDEN)


def test_counter_a_face_257200_at_85bp_costs_3027_77_and_is_accepted(state, mandate, key):
    # discount 257,200 × 0.85% = 2,186.20 + line 149,986.20 × 6.4% × 32/365 = 841.57 -> 3,027.77 < 3,113.93
    b = _ev(state, mandate, key, _leg(85, face=25_720_000))
    assert b.verdict.outcome == Outcome.ACCEPT and _new(b) == []
    assert _figures(b) == (302_777, C0_GOLDEN)


def test_whole_invoice_at_89bp_is_above_the_break_even_whatever_the_plan(state, mandate, key):
    b = _ev(state, mandate, key, _leg(89))
    assert b.verdict.outcome == Outcome.COUNTER
    assert "DISCOUNT_ABOVE_BREAK_EVEN" in codes(b.verdict.violations)
    v = next(x for x in b.verdict.violations if x.code.value == "DISCOUNT_ABOVE_BREAK_EVEN")
    assert v.inputs["break_even_days"] == "30" and v.inputs["break_even_bp_floor"] == "88"
    assert "for 30 days (1 × 30-day periods)" in v.formula


def test_no_funding_need_and_nothing_drawn_the_discount_buys_nothing(state, mandate, key):
    rich = state.model_copy(update={"cash_fen": 200_000_000})
    b = _ev(rich, mandate, key, _leg(64))
    assert codes(b.verdict.violations) == ["EARLY_PAY_NOT_NEEDED"]
    assert b.verdict.outcome == Outcome.REJECT and not b.verdict.counters  # no cash gap, so nothing to counter
    assert _figures(b) == (268_800, 0)


def test_the_new_codes_are_pricing_faults_never_security_events(state, mandate, key):
    from app.verifier.evaluate import PRICE_CODES, _is_hard

    for code in NEW_CODES:
        assert any(c.value == code for c in PRICE_CODES)
    b = _ev(state, mandate, key, _leg(85))
    assert not any(_is_hard(v) for v in b.verdict.violations) and b.security_events == []


# ---------------------------------------------------------------- 2. the break-even for the tenor


def _old_break_even(state, mandate) -> Fraction:
    rate, _ = marginal_cost(state, mandate)
    c = rate.value * 30 / 365
    return c / (1 + c)


def test_break_even_at_30_days_is_unchanged(state, mandate):
    d, floor_bp = break_even_discount(state, mandate)
    assert d.value == _old_break_even(state, mandate) and floor_bp == 88 and fmt_pct(d.value, 4) == "0.8832%"
    assert break_even_discount(state, mandate, 30) == (d, 88)


def test_invoice_financing_is_billed_in_whole_periods(state, mandate):
    rate, _ = marginal_cost(state, mandate)
    d30 = break_even_discount(state, mandate, 30)[0].value
    assert break_even_discount(state, mandate, 3)[0].value == d30  # one whole period
    assert break_even_discount(state, mandate, 1)[0].value == d30

    def d(periods: int) -> Fraction:
        c = rate.value * 30 * periods / 365
        return c / (1 + c)

    assert break_even_discount(state, mandate, 31)[0].value == d(2) > d30  # two periods
    assert break_even_discount(state, mandate, 60)[0].value == d(2)
    assert break_even_discount(state, mandate, 90)[0].value == d(3) > Fraction(12, 1000)


def test_a_source_that_is_not_invoice_financing_accrues_by_the_day(state, mandate):
    s = _with(state, **{"FAC-IF": {"status": FacilityStatus.NOT_APPLIED}, "FAC-GGL": {"status": FacilityStatus.COMMITTED}})
    rate, fid = marginal_cost(s, mandate)
    assert fid == "FAC-GGL"
    for n in (10, 30, 45):
        c = rate.value * n / 365
        assert break_even_discount(s, mandate, n)[0].value == c / (1 + c)


# ---------------------------------------------------------------- 3. a long tenor is cheap


def _due_in(state, days_after_settlement: int):  # type: ignore[no-untyped-def]
    return state.model_copy(update={"receivables": [
        r.model_copy(update={"terms_days": 2 + days_after_settlement - r.issue_day}) if r.id == "RCV-A" else r
        for r in state.receivables]})


def test_one_point_two_percent_for_90_days_early_is_no_longer_above_the_break_even(state, mandate, key):
    s = _due_in(state, 90)
    b = _ev(s, mandate, key, _leg(120))
    assert "DISCOUNT_ABOVE_BREAK_EVEN" not in codes(b.verdict.violations)
    # and the same offer 30 days early still is
    assert "DISCOUNT_ABOVE_BREAK_EVEN" in codes(_ev(state, mandate, key, _leg(120)).verdict.violations)


def test_the_break_even_violation_states_the_tenor(state, mandate, key):
    s = _due_in(state, 90)
    b = _ev(s, mandate, key, _leg(300))
    v = next(x for x in b.verdict.violations if x.code.value == "DISCOUNT_ABOVE_BREAK_EVEN")
    assert v.inputs["break_even_days"] == "90" and "for 90 days (3 × 30-day periods)" in v.formula


# ---------------------------------------------------------------- 4. early cash that retires a drawn balance


def test_early_cash_that_retires_a_drawn_balance_and_lowers_total_cost_passes(state, mandate, key):
    s = _with(state.model_copy(update={"cash_fen": 200_000_000}), **{"FAC-LINE": {"drawn_fen": 15_000_000}})
    b = _ev(s, mandate, key, _leg(10, face=10_000_000))  # ¥100,000 at 0.10%: ¥100 against the interest it saves
    c1, c0 = _figures(b)
    assert plan(s, [], mandate, "COMMITTED").actions == [] and c0 > 0  # no new funding; interest on the drawn balance
    assert c1 < c0
    assert _new(b) == [] and b.verdict.outcome == Outcome.ACCEPT


# ---------------------------------------------------------------- 5. a package: the early-pay leg at the margin


def test_a_package_prices_the_early_pay_leg_against_the_other_leg(state, mandate, key):
    ext = _extension()
    b = _ev(state, mandate, key, _leg(64), ext)
    c1, c0 = _figures(b)
    assert c0 == _cost(state, mandate, [ext]) != C0_GOLDEN  # the extension is in C0
    assert c1 == _cost(state, mandate, [_leg(64), ext])
    inputs = next(p for p in b.passed_checks if p.code == "EARLY_PAY_VS_PLAN").inputs if _new(b) == [] else \
        next(v for v in b.verdict.violations if v.code.value in NEW_CODES).inputs
    assert inputs["plan_without_offer"] != inputs["plan_with_offer"]


# ---------------------------------------------------------------- 6. missing plans


def test_no_plan_with_the_offer_evaluates_neither_test(state, mandate, key):
    s = state.model_copy(update={"cash_fen": state.cash_fen - 30_000_000})  # need ¥660,000 > line + whole invoice
    b = _ev(s, mandate, key, _leg(64))
    assert not b.plan_committed.admissible
    assert _new(b) == [] and not any(p.code == "EARLY_PAY_VS_PLAN" for p in b.passed_checks)


def test_no_plan_without_the_offer_but_one_with_it_passes_both_tests(state, mandate, key):
    s = _with(state, **{"FAC-IF": {"status": FacilityStatus.NOT_APPLIED}, "FAC-EARLYPAY": {"status": FacilityStatus.NOT_APPLIED}})  # the line alone cannot cover ¥360,000
    b = _ev(s, mandate, key, _leg(50))
    assert not plan(s, [], mandate, "COMMITTED").admissible and b.plan_committed.admissible
    assert _new(b) == []
    (p,) = [p for p in b.passed_checks if p.code == "EARLY_PAY_VS_PLAN"]
    assert p.limit == "no admissible plan without the offer"


# ---------------------------------------------------------------- 7. the counter follows the rule


def test_golden_counter_a_is_unchanged(state):
    (a,) = [c for c in bundle("EX01_PACKAGE").verdict.counters if c.label == "Option A"]
    (ob,) = a.obligations
    # face ⌈255,000 / (1 − 0.85%)⌉ to ¥100 = 257,200; cost 2,186.20 + 841.57 = 3,027.77 (compute_golden.py)
    assert (ob.base.amount_fen, ob.rate_bp, a.supplier_cost_fen) == (25_720_000, 85, 302_777)
    assert "c = 10.8417% × 30/365 = 0.8911% → d < 0.8832%" in a.formula


def test_the_counter_states_the_tenor_of_its_break_even(state, mandate, key):
    s = _due_in(state, 90)
    b = _ev(s, mandate, key, _leg(300))
    a = next((c for c in b.verdict.counters if c.obligations[0].type == ObligationType.IMMEDIATE_DISCOUNT), None)
    if a is not None:
        assert "× 30/365 × 3 =" in a.formula


def test_no_early_pay_counter_when_none_beats_the_plan_and_the_offer_is_rejected(state, mandate, key):
    cheap = _with(state, **{"FAC-EARLYPAY": {"rate_bp": 40}})  # the router can take early pay at 0.40% itself
    b = _ev(cheap, mandate, key, _leg(85))
    assert codes(b.verdict.violations) == ["EARLY_PAY_DEARER_THAN_PLAN"]
    assert b.verdict.counters == [] and b.verdict.outcome == Outcome.REJECT


# ---------------------------------------------------------------- 8. re-verification of Counter A


@pytest.fixture
def rt() -> Any:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


def test_reverify_accepts_a_commitment_whose_obligation_is_counter_a(rt, state, mandate):
    (a,) = [c for c in bundle("EX01_PACKAGE").verdict.counters if c.label == "Option A"]
    c = Commitment(id="CMT-A", offer_id="OFF-A", offer_version=1, counterparty_id="BUYER-1", verdict_id="V-A",
                   terms_hash="h", obligations=list(a.obligations), status=CommitmentStatus.PROPOSED, nonce="n",
                   expires_day=7, mandate_version=1, forward_value_fen=0)
    out = rt.reverify(c, rt.store.get_state(), rt.store.get_mandate(), 0)
    assert out in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL)
