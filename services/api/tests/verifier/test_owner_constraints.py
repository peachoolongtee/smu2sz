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
    assert ob.base.amount_fen == 21_190_000 and ob.base.receivable_id == "RCV-A"
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
    assert plain.outcome == Outcome.REJECT and len(plain.counters) == 2
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
