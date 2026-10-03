"""Fifth red team (round e), verifier side: findings F1 (fixed-sum early-pay discount) and F2 (target terms against the
terms in force). Probes: docs/research/redteam-2026-10-03e/p05_fixed_amount_discount.py and p07_target_terms_stack.py.

Golden books (see test_early_pay_handcalc.py): RCV-A 420,000.00 due day 32, settlement day 2 (30 days early), mandate
discount cap 150 bp, rate ceiling 15%, standing plan C0 = 311,393 fen.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    InvoiceAdjustment,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SourceSpan,
)
from app.financial.invoices import terms_in_force
from app.mandate.fixture import demo_owner_public_key_hex
from app.mandate.predicates import discount_rate
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore
from app.verifier import evaluate
from app.verifier.bind import bind, is_gain
from tests.verifier.conftest import codes, compiled, declared_for

OWNER = {"X-Owner-Token": "demo-owner-token"}
BUYER1 = {"X-Counterparty-Key": "demo-buyer-1-key"}

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


# ---------------------------------------------------------------- F2: a target term is against the terms in force


def _with_55_days(state):  # type: ignore[no-untyped-def]
    """The golden books after an accepted +10-day perpetual extension (55-day terms in force for BUYER-1)."""
    adj = InvoiceAdjustment(id="CMT-X:O1", commitment_id="CMT-X", obligation_id="O1", counterparty_id="BUYER-1",
                            days_delta=10, price_bp=0, from_issue_day=0)
    return state.model_copy(update={"invoice_adjustments": [adj]})


def _target(days: int) -> Obligation:
    return Obligation(
        id="RE-T1", type=ObligationType.TERMS_EXTENSION, counterparty_id="BUYER-1", target_terms_days=days,
        effective_day=1, base=ObligationBase(kind=BaseKind.FUTURE_INVOICES), contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL), spans=SPAN, confidence=1.0)


def test_f2_terms_in_force_apply_the_accepted_adjustments_to_the_next_invoice(state):
    assert terms_in_force(state, "BUYER-1") == 45
    assert terms_in_force(_with_55_days(state), "BUYER-1") == 55
    assert terms_in_force(state, "NOBODY") is None


def test_f2_a_target_of_40_against_55_in_force_binds_minus_15_a_gain(state):
    (b,), notes = bind(_offer(_target(40)), _with_55_days(state))
    assert b.days_delta == -15 and is_gain(b)
    assert any("40 days − current 55 days" in n.message for n in notes)
    (base,), _ = bind(_offer(_target(40)), state)
    assert base.days_delta == -5  # unchanged on books without an adjustment


def test_f2_counter_a_quotes_the_terms_in_force(state, mandate, key):
    b = evaluate(compiled("EX01_PACKAGE"), _with_55_days(state), mandate, trusted_owner_key_hex=key,
                 owner_declared=declared_for("EX01_PACKAGE"))
    a = next(c for c in b.verdict.counters if c.label == "Option A")
    assert a.text.startswith("Terms stay at 55 days") and "45 days" not in a.text


@pytest.fixture
def rt() -> Any:
    r = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    r.reset()
    set_runtime(r)
    reset_sessions()
    yield r
    set_runtime(None)
    reset_sessions()


def _buyer_agrees(client: TestClient, text: str, session: str) -> None:
    r = client.post("/nl", headers=BUYER1, json={"text": text, "actor": "COUNTERPARTY", "session_id": session})
    assert r.status_code == 200, r.text
    [a] = [a for a in client.get("/approvals/queue", headers=OWNER).json()["approvals"] if a["status"] == "PENDING"]
    d = client.post(f"/approvals/{a['id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
    assert d["status"] == "EXECUTED", d["message"]


def test_f2_stored_invoices_carry_the_last_agreed_terms_not_a_stack(rt: Runtime) -> None:
    from app.main import app

    client = TestClient(app)
    _buyer_agrees(client, "We accept 55-day terms with a 0.30% price adjustment on future invoices.", "re-f2-1")
    assert client.post("/clock/advance", json={"to_day": 1}, headers=OWNER).status_code == 200
    _buyer_agrees(client, "Standard terms going forward: 40 days.", "re-f2-2")
    s = rt.store.get_state()
    assert [a.days_delta for a in s.invoice_adjustments if a.days_delta] == [10, -15]
    assert terms_in_force(s, "BUYER-1") == 40
    assert client.post("/clock/advance", json={"to_day": 3}, headers=OWNER).status_code == 200
    ri = next(r for r in rt.store.get_state().receivables if r.id == "RI:BUYER-1:2")
    assert (ri.terms_days, ri.base_terms_days, ri.due_day) == (40, 45, 42)
    assert len([c for c in rt.store.commitments() if c.status.value == "ACTIVE"]) == 2
