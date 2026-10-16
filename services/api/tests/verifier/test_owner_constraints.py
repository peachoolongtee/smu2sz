"""Owner-goal constraints in `evaluate` (the /nl EX12 goal), `plans=`, and the per-evaluation router memo."""

from __future__ import annotations

import pytest

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
    Tier,
)
from app.mandate import demo_owner_public_key_hex
from app.verifier import OwnerConstraints, evaluate
from tests.verifier.conftest import compiled, declared_for

KEY = demo_owner_public_key_hex()
GOAL = OwnerConstraints(max_early_pay_bp=85, zero_forward_concessions=True)


def _early_pay_offer(rate_bp: int, offer_id: str = "GOAL-TEST") -> CompiledOffer:
    """The buyer's standing early-pay offer on RCV-A as a typed obligation (as /nl builds it)."""
    text = "Get paid early on the Foshan invoice"
    ob = Obligation(
        id=f"{offer_id}-O1", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=rate_bp,
        base=ObligationBase(kind=BaseKind.INVOICE, receivable_id="RCV-A", amount_fen=42_000_000),
        contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF),
        spans=[SourceSpan(doc_id="OWNER-DOC", start=4, end=14, text=text[4:14])], confidence=1.0,
    )
    return CompiledOffer(offer_id=offer_id, counterparty_id="BUYER-1", doc_ids=["OWNER-DOC"], received_day=0,
                         status=CompileStatus.COMPILED, obligations=[ob], compiler="nl-goal", prompt_version="nl-v1")


def _eval(offer, state, mandate, **kw):  # type: ignore[no-untyped-def]
    return evaluate(offer, state, mandate, trusted_owner_key_hex=KEY, **kw)


# ---------------------------------------------------------------- owner constraints


def test_goal_above_the_owner_cap_gets_a_counter_that_satisfies_it(state, mandate) -> None:
    b = _eval(_early_pay_offer(120), state, mandate, owner_constraints=GOAL)
    v = b.verdict
    assert v.outcome == Outcome.COUNTER and v.required_tier == Tier.TIER_1
    (c,) = v.counters
    (ob,) = c.obligations
    assert ob.type == ObligationType.IMMEDIATE_DISCOUNT and ob.rate_bp == 85
    # Counter A's face: 255,000 / (1 − 0.85%) up to a whole ¥100 (compute_golden.py counter_a_face)
    assert ob.base.amount_fen == 26_000_000 and ob.base.receivable_id == "RCV-A"
    assert c.forward_value_fen == 0
    assert "owner goal (early pay at most 0.85%, zero forward concessions)" in v.summary


def test_a_tighter_owner_cap_adjusts_the_counter_rate(state, mandate) -> None:
    v = _eval(_early_pay_offer(120), state, mandate,
              owner_constraints=OwnerConstraints(max_early_pay_bp=80, zero_forward_concessions=True)).verdict
    (c,) = v.counters
    assert v.outcome == Outcome.COUNTER and c.obligations[0].rate_bp == 80


def test_a_package_inside_the_mandate_but_above_the_goal_is_never_accepted(state, mandate) -> None:
    plain = _eval(_early_pay_offer(60), state, mandate).verdict
    assert plain.outcome == Outcome.ACCEPT and not plain.counters
    v = _eval(_early_pay_offer(60), state, mandate,
              owner_constraints=OwnerConstraints(max_early_pay_bp=50)).verdict
    assert v.outcome == Outcome.COUNTER
    assert all(o.rate_bp is not None and o.rate_bp <= 50 for c in v.counters for o in c.obligations)


def test_a_package_that_satisfies_the_goal_keeps_the_mandate_verdict(state, mandate) -> None:
    plain = _eval(_early_pay_offer(60), state, mandate).verdict
    v = _eval(_early_pay_offer(60), state, mandate, owner_constraints=GOAL).verdict
    assert (v.outcome, v.required_tier, v.counters) == (plain.outcome, plain.required_tier, plain.counters)
    assert v.id != plain.id  # a constrained verdict is stored under its own id


def test_constraints_never_loosen_a_reject_and_filter_its_counters(state, mandate) -> None:
    ex01 = compiled("EX01_PACKAGE")
    kw = {"owner_declared": declared_for("EX01_PACKAGE")}
    plain = _eval(ex01, state, mandate, **kw).verdict
    assert plain.outcome == Outcome.REJECT and [c.label for c in plain.counters] == ["Option A", "Option B"]
    v = _eval(ex01, state, mandate, owner_constraints=OwnerConstraints(zero_forward_concessions=True), **kw).verdict
    assert v.outcome == Outcome.REJECT and v.violations == plain.violations
    assert [c.label for c in v.counters] == ["Option A"]
    assert all(o.type == ObligationType.IMMEDIATE_DISCOUNT for c in v.counters for o in c.obligations)
    terms = _eval(ex01, state, mandate, owner_constraints=OwnerConstraints(max_terms_days=45), **kw).verdict
    assert all(o.type != ObligationType.TERMS_EXTENSION or (o.target_terms_days or 0) <= 45
               for c in terms.counters for o in c.obligations)


def test_constrained_verdict_is_deterministic(state, mandate) -> None:
    a = _eval(_early_pay_offer(120), state, mandate, owner_constraints=GOAL).verdict
    b = _eval(_early_pay_offer(120), state, mandate, owner_constraints=GOAL).verdict
    assert a == b
    other = _eval(_early_pay_offer(120), state, mandate,
                  owner_constraints=OwnerConstraints(max_early_pay_bp=80, zero_forward_concessions=True)).verdict
    assert other.id != a.id


# ---------------------------------------------------------------- owner terms constraint: terms in force


def _extension(days_delta: int) -> Obligation:
    return Obligation(
        id="OWN-T1", type=ObligationType.TERMS_EXTENSION, counterparty_id="BUYER-1", days_delta=days_delta,
        effective_day=1, base=ObligationBase(kind=BaseKind.FUTURE_INVOICES), contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
        spans=[SourceSpan(doc_id="OWNER-DOC", start=0, end=4, text="test")], confidence=1.0)


def test_owner_terms_constraint_is_evaluated_against_the_terms_in_force(state) -> None:
    from app.domain.models import InvoiceAdjustment
    from app.verifier.owner import _current_terms, breaches, terms_after

    cap = OwnerConstraints(max_terms_days=57)
    ob = _extension(5)
    # template base terms are 45 days: +5 is 50, inside the owner's 57-day cap
    assert _current_terms(state, "BUYER-1") == 45 and terms_after(ob, state) == 50
    assert breaches([ob], [], state, cap) == []
    # after an accepted +10-day perpetual extension 55-day terms are in force: +5 is 60, above the cap
    adj = InvoiceAdjustment(id="CMT-X:O1", commitment_id="CMT-X", obligation_id="O1", counterparty_id="BUYER-1",
                            days_delta=10, price_bp=0, from_issue_day=0)
    extended = state.model_copy(update={"invoice_adjustments": [adj]})
    assert _current_terms(extended, "BUYER-1") == 55 and terms_after(ob, extended) == 60
    (why,) = breaches([ob], [], extended, cap)
    assert "payment terms 60 days above the owner's 57 days" in why


# ---------------------------------------------------------------- plans= and the router memo


@pytest.mark.parametrize("offer_id", ["EX01_PACKAGE", "EX02_EARLY_1_5", "EX05_CONSOLIDATE", "EX06_THREE_INVOICES"])
def test_committed_plans_mode_gives_the_same_verdict_without_the_expected_plan(offer_id, state, mandate) -> None:
    kw = {"owner_declared": declared_for(offer_id)}
    full = _eval(compiled(offer_id), state, mandate, **kw)
    lean = _eval(compiled(offer_id), state, mandate, plans="committed", **kw)
    assert lean.verdict == full.verdict
    assert lean.plan_committed == full.plan_committed and lean.cure_plan == full.cure_plan
    assert full.plan_expected is not None and lean.plan_expected is None


def _status_quo() -> CompiledOffer:
    return CompiledOffer(offer_id="NL-SQ-TEST", counterparty_id="OWNER", doc_ids=["NL-SQ-TEST"], received_day=0,
                         status=CompileStatus.COMPILED, obligations=[], compiler="nl-status-quo",
                         prompt_version="nl-v1")


def test_identical_router_calls_run_once_per_evaluation(state, mandate) -> None:
    calls: list[int] = []
    b = _eval(_status_quo(), state, mandate, plans="committed", _router_probe=lambda r: calls.append(r.calls))
    assert calls == [0]  # the status-quo committed plan is the baseline's: no new search
    assert b.plan_committed is not None and b.plan_committed.admissible
    _eval(_status_quo(), state, mandate, _router_probe=lambda r: calls.append(r.calls))
    assert calls[-1] == 1  # only the expected plan
    _eval(compiled("EX01_PACKAGE"), state, mandate, owner_declared=declared_for("EX01_PACKAGE"),
          plans="committed", _router_probe=lambda r: calls.append(r.calls))
    assert calls[-1] == 3  # committed + cure (different states) + the early-pay leg priced at the margin (ADR-0007), no expected plan
