"""Fifth red team (round e), verifier side: findings F1 (fixed-sum early-pay discount) and F2 (target terms against the
terms in force). Probes: docs/research/redteam-2026-10-03e/p05_fixed_amount_discount.py and p07_target_terms_stack.py.

Golden books (see test_early_pay_handcalc.py): RCV-A 420,000.00 due day 32, settlement day 2 (30 days early), mandate
discount cap 150 bp, rate ceiling 15%, standing plan C0 = 311,393 fen.
"""

from __future__ import annotations

from fractions import Fraction

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SourceSpan,
)
from app.mandate.predicates import discount_rate
from app.verifier import evaluate
from app.verifier.bind import bind
from tests.verifier.conftest import codes

SPAN = [SourceSpan(doc_id="OWNER-DOC", start=0, end=0, text="")]
WHOLE = 42_000_000
EARLY = {"IMMEDIATE_DISCOUNT_EXCEEDED", "DISCOUNT_ABOVE_BREAK_EVEN", "MAX_APR_EXCEEDED", "EARLY_PAY_DEARER_THAN_PLAN",
         "EARLY_PAY_NOT_NEEDED"}


def _leg(*, rate_bp: int | None = None, sum_fen: int | None = None, face: int | None = WHOLE,
         receivable: str | None = "RCV-A") -> Obligation:
    return Obligation(
        id="RE-O1", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=rate_bp,
        amount_fen=sum_fen, effective_day=2,
        base=ObligationBase(kind=BaseKind.INVOICE, receivable_id=receivable, amount_fen=face),
        contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF), spans=SPAN, confidence=1.0)


def _offer(*obs: Obligation) -> CompiledOffer:
    return CompiledOffer(offer_id="RE-TEST", counterparty_id="BUYER-1", doc_ids=["OWNER-DOC"], received_day=0,
                         status=CompileStatus.COMPILED, obligations=list(obs), compiler="nl-re-test",
                         prompt_version="nl-v1")


def _ev(state, mandate, key, ob):  # type: ignore[no-untyped-def]
    return evaluate(_offer(ob), state, mandate, trusted_owner_key_hex=key)


# ---------------------------------------------------------------- F1: a fixed sum is tested at its exact rate


def test_f1_fixed_sum_is_bound_with_its_amount_and_an_exact_rate_on_its_portion(state):
    (b,), notes = bind(_offer(_leg(sum_fen=800_000)), state)
    assert b.amount_fen == 800_000 and b.rate_bp is None  # the engine, executor and reconciliation book the sum
    assert b.base.receivable_id == "RCV-A" and b.base.amount_fen == WHOLE
    assert discount_rate(b) == Fraction(800_000, WHOLE) == Fraction(4, 210)
    assert any(n.field == "rate_bp" and n.resolved and "1.9048%" in n.message for n in notes)


def test_f1_8000_on_420000_gives_the_same_codes_as_the_190bp_control(state, mandate, key):
    fixed = _ev(state, mandate, key, _leg(sum_fen=800_000))  # 8,000 / 420,000 = 1.9048%
    control = _ev(state, mandate, key, _leg(rate_bp=190))
    got = set(codes(fixed.verdict.violations))
    assert got & EARLY == set(codes(control.verdict.violations)) & EARLY == {
        "IMMEDIATE_DISCOUNT_EXCEEDED", "DISCOUNT_ABOVE_BREAK_EVEN", "MAX_APR_EXCEEDED", "EARLY_PAY_DEARER_THAN_PLAN"}
    assert fixed.verdict.outcome == control.verdict.outcome == Outcome.COUNTER
    cap = next(v for v in fixed.verdict.violations if v.code.value == "IMMEDIATE_DISCOUNT_EXCEEDED")
    assert cap.inputs["exact_rate"] == "2/105" and cap.inputs["amount_fen"] == "800000"
    dearer = next(v for v in fixed.verdict.violations if v.code.value == "EARLY_PAY_DEARER_THAN_PLAN")
    assert dearer.inputs["cost_with_offer"] == "¥8,000.00"  # C1 is the sum itself (no funding needed)


def test_f1_fixed_sum_at_the_plan_boundary_matches_the_rate_boundary(state, mandate, key):
    # 3,108.00 on 420,000 is exactly 0.74%: accepted like 74 bp (310,800 < 311,393); 3,150.00 = 0.75%: countered.
    below = _ev(state, mandate, key, _leg(sum_fen=310_800))
    assert not set(codes(below.verdict.violations)) & EARLY and below.verdict.outcome == Outcome.ACCEPT
    above = _ev(state, mandate, key, _leg(sum_fen=315_000))
    assert set(codes(above.verdict.violations)) & EARLY == {"EARLY_PAY_DEARER_THAN_PLAN"}
    assert above.verdict.outcome == Outcome.COUNTER


def test_f1_cap_comparison_is_exact_not_whole_basis_points(state, mandate, key):
    assert mandate.max_immediate_discount_bp == 150
    at_cap = _ev(state, mandate, key, _leg(sum_fen=630_000))  # exactly 1.50%
    assert "IMMEDIATE_DISCOUNT_EXCEEDED" not in codes(at_cap.verdict.violations)
    one_fen_over = _ev(state, mandate, key, _leg(sum_fen=630_001))  # 1.5000024%: rounds to 150 bp, still above
    assert "IMMEDIATE_DISCOUNT_EXCEEDED" in codes(one_fen_over.verdict.violations)


def test_f1_fixed_sum_on_a_stated_portion_is_rated_on_that_portion(state, mandate, key):
    # 2,186.20 on 257,200 of RCV-A is exactly Counter A's 0.85%: accepted like the rate (C1 = 302,777 < 311,393)
    b = _ev(state, mandate, key, _leg(sum_fen=218_620, face=25_720_000))
    assert not set(codes(b.verdict.violations)) & EARLY and b.verdict.outcome == Outcome.ACCEPT
    passed = next(p for p in b.passed_checks if p.code == "EARLY_PAY_VS_PLAN")
    assert passed.inputs["cost_with_offer"] == "¥3,027.77"


def test_f1_a_sum_not_below_its_portion_is_unbound(state, mandate, key):
    b = _ev(state, mandate, key, _leg(sum_fen=WHOLE))
    assert "UNRESOLVED_SCOPE" in codes(b.verdict.violations)
