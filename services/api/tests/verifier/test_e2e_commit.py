"""End to end: buyer text → compiler → verifier → propose_commitment → Executor, on the golden state and the
signed mandate. What the executor commits is exactly what the verifier bound and verified."""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from app.domain.fixtures import load_scenario
from app.domain.models import (
    AcceptOffer,
    Actor,
    CommitmentStatus,
    DrawFacility,
    ObligationType,
    OperationStatus,
    Outcome,
    Tier,
)
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.operations import Executor
from app.persistence import InMemoryLedgerStore
from app.verifier import evaluate
from tests.verifier.conftest import compiled, declared_for

_ids = itertools.count(1)


class _Clock:
    def __init__(self) -> None:
        self.day = 0

    def __call__(self) -> int:
        return self.day


@pytest.fixture
def desk() -> tuple[InMemoryLedgerStore, Executor, _Clock]:
    store = InMemoryLedgerStore()
    state, _ = load_scenario()
    store.put_state(state)
    store.put_mandate(load_signed_mandate())
    clock = _Clock()
    return store, Executor(store, trusted_owner_key_hex=demo_owner_public_key_hex(), clock=clock), clock


def _verdict(store: InMemoryLedgerStore, offer_id: str, owner_declared: dict | None = None) -> Any:
    offer = compiled(offer_id)
    store.put_offer(offer)
    b = evaluate(offer, store.get_state(), store.get_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex(),
                 owner_declared=owner_declared)
    store.put_verdict(b.verdict)
    return b.verdict


def _base(clock: _Clock, verdict_id: str | None = None) -> dict[str, Any]:
    n = next(_ids)
    return {"op_id": f"E2E-{n}", "idempotency_key": f"E2E-KEY-{n}", "mandate_version": load_signed_mandate().version,
            "requested_by": Actor.AGENT, "source_verdict_id": verdict_id, "day": clock.day}


def _accept(ex: Executor, clock: _Clock, verdict: Any, c: Any) -> Any:
    return ex.execute(AcceptOffer(**_base(clock, verdict.id), offer_id=c.offer_id, offer_version=c.offer_version,
                                  terms_hash=c.terms_hash, nonce=c.nonce))


def test_ex01_option_a_then_line_draw_executes_at_tier1(desk):
    store, ex, clock = desk
    v = _verdict(store, "EX01_PACKAGE")  # no owner declarations: the rebate base comes from expected orders
    assert v.outcome == Outcome.REJECT and [c.label for c in v.counters] == ["Option A", "Option B"]
    a = v.counters[0]

    c = ex.propose_commitment(v.id, counter_id=a.id, expires_day=5)
    assert c.forward_value_fen == 0 and a.forward_value_fen == 0 and a.supplier_cost_fen > 0
    assert c.obligations == a.obligations
    assert [o.type for o in c.obligations] == [ObligationType.IMMEDIATE_DISCOUNT]

    before = store.get_state()
    accepted = _accept(ex, clock, v, c)
    assert (accepted.status, accepted.tier) == (OperationStatus.EXECUTED, Tier.TIER_1), accepted.message
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE
    (fc,) = store.get_state().forward_concessions
    assert (fc.value_fen, fc.commitment_id) == (0, c.id)

    draw = ex.execute(DrawFacility(**_base(clock), facility_id="FAC-LINE", amount_fen=15_000_000))
    assert (draw.status, draw.tier) == (OperationStatus.EXECUTED, Tier.TIER_1), draw.message
    after = store.get_state()
    line = next(f for f in after.facilities if f.id == "FAC-LINE")
    assert line.drawn_fen == 15_000_000 and after.cash_fen == before.cash_fen + 15_000_000

    assert [r.kind for r in store.operations()] == ["ACCEPT_OFFER", "DRAW_FACILITY"]
    assert store.verify_chain()


def test_ex05_accept_waits_for_the_owner_then_executes(desk):
    """A shortening is a gain, but it is not an early-pay discount: accepting it is Tier 2 (EV-01/EV-02)."""
    store, ex, clock = desk
    v = _verdict(store, "EX05_CONSOLIDATE", declared_for("EX05_CONSOLIDATE"))  # per-event cost is owner-declared
    assert (v.outcome, v.required_tier) == (Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2)  # the verdict says so too
    c = ex.propose_commitment(v.id, expires_day=5)
    assert c.obligations == v.bound_obligations
    ext = next(o for o in c.obligations if o.type == ObligationType.TERMS_EXTENSION)
    assert ext.days_delta == -15  # 30-day terms from the ledger's 45: a shortening
    assert c.forward_value_fen == 0  # the FIRM gain outweighs the delivery cost; floored at zero
    before = store.get_state()
    pending = _accept(ex, clock, v, c)
    assert (pending.status, pending.tier) == (OperationStatus.PENDING_APPROVAL, Tier.TIER_2), pending.message
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED
    assert store.get_state() == before
    done = ex.decide(pending.approval_id, True, Actor.OWNER)
    assert done.status == OperationStatus.EXECUTED, done.message
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE
    assert store.verify_chain()


def test_ex01_option_b_needs_the_owner(desk):
    """Option B is the 55-day counter (60 days fails its own re-check); it lengthens terms, so the owner decides."""
    store, ex, clock = desk
    v = _verdict(store, "EX01_PACKAGE")
    b = v.counters[1]
    assert b.label == "Option B" and b.text.startswith("55-day terms accepted")
    c = ex.propose_commitment(v.id, counter_id=b.id, expires_day=5)
    assert c.obligations == b.obligations and c.forward_value_fen == b.forward_value_fen == 0
    result = _accept(ex, clock, v, c)
    assert (result.status, result.tier) == (OperationStatus.PENDING_APPROVAL, Tier.TIER_2)
    assert "lengthens payment terms" in result.message
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED
    assert store.get_state().forward_concessions == []
    assert store.verify_chain()


def test_ex01_verdict_itself_cannot_be_committed(desk):
    store, ex, _ = desk
    v = _verdict(store, "EX01_PACKAGE")
    with pytest.raises(ValueError, match="only a counter"):
        ex.propose_commitment(v.id, expires_day=5)
