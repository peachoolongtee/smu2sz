"""Tiers are computed by the executor and enforced in code (INVARIANTS 3, 6, 12)."""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.models import (
    Actor,
    AddFacility,
    ApplyForFacility,
    ChangeMandate,
    DrawFacility,
    FacilityStatus,
    GenerateBorrowerFile,
    IssueEquity,
    OperationStatus,
    PledgeCollateral,
    SecurityEventKind,
    SignPersonalGuarantee,
    Tier,
    ViolationCode,
)
from app.operations import approval_id_of, security_summary
from tests.operations.builders import Clock, new_facility, op

TIER3 = [
    (SignPersonalGuarantee, {"facility_id": "FAC-LINE"}, ViolationCode.TIER3_PERSONAL_GUARANTEE),
    (PledgeCollateral, {"facility_id": "FAC-LINE"}, ViolationCode.TIER3_COLLATERAL),
    (IssueEquity, {"amount_fen": 100_000_000}, ViolationCode.TIER3_EQUITY),
    (ChangeMandate, {"new_version": 2}, ViolationCode.TIER3_MANDATE_CHANGE),
]


@pytest.mark.parametrize("actor", list(Actor))
@pytest.mark.parametrize(("cls", "fields", "code"), TIER3, ids=[c[0].__name__ for c in TIER3])
def test_tier3_refused_for_every_actor_and_nothing_changes(
    ex: Any, store: Any, clock: Clock, actor: Actor, cls: type, fields: dict, code: ViolationCode
) -> None:
    before = store.get_state()
    result = ex.execute(op(cls, clock, actor=actor, **fields))
    assert result.status == OperationStatus.REFUSED
    assert result.tier == Tier.TIER_3
    assert [v.code for v in result.violations] == [code]
    assert store.get_state() == before
    assert store.approvals() == []
    assert [e.kind for e in store.security_events()] == [SecurityEventKind.TIER3]
    assert result.seq == 1 and result.entry_hash and store.verify_chain()
    assert security_summary(store)["unauthorised_executions"] == 0


@pytest.mark.parametrize("actor", [Actor.AGENT, Actor.COUNTERPARTY, Actor.SYSTEM])
def test_add_facility_by_non_owner_is_refused(ex: Any, store: Any, clock: Clock, actor: Actor) -> None:
    before = store.get_state()
    known = ex.execute(op(AddFacility, clock, actor=actor, facility=new_facility("BANK-1")))
    unknown = ex.execute(op(AddFacility, clock, actor=actor, facility=new_facility("SHADOW-LENDER", "FAC-X")))
    assert known.status == unknown.status == OperationStatus.REFUSED
    assert known.tier == unknown.tier == Tier.TIER_3
    assert [v.code for v in known.violations] == [ViolationCode.INSUFFICIENT_AUTHORITY]
    assert [v.code for v in unknown.violations] == [ViolationCode.UNKNOWN_COUNTERPARTY]
    assert store.get_state() == before and store.approvals() == []
    kinds = {e.kind for e in store.security_events()}
    assert kinds == {SecurityEventKind.TIER3, SecurityEventKind.UNKNOWN_COUNTERPARTY}
    assert security_summary(store)["facilities_added_by_non_owner"] == 0


def test_add_facility_by_owner_goes_pending_then_owner_approves(ex: Any, store: Any, clock: Clock) -> None:
    fac = new_facility("NEW-BANK", "FAC-NEW")
    pending = ex.execute(op(AddFacility, clock, actor=Actor.OWNER, facility=fac))
    assert pending.status == OperationStatus.PENDING_APPROVAL and pending.tier == Tier.TIER_2
    assert "FAC-NEW" not in {f.id for f in store.get_state().facilities}
    aid = approval_id_of(pending)
    assert aid is not None and store.get_approval(aid).status == "PENDING"

    clock.day = 1
    done = ex.decide(aid, True, Actor.OWNER)
    assert done.status == OperationStatus.EXECUTED
    state = store.get_state()
    added = next(f for f in state.facilities if f.id == "FAC-NEW")
    assert added.owner_approved and state.state_version == 2
    assert any(c.id == "NEW-BANK" and c.role == "LENDER" for c in state.counterparties)
    s = security_summary(store)
    assert s["facilities_added_by_non_owner"] == 0 and s["unauthorised_executions"] == 0


def test_line_draw_is_tier1_and_executes_exactly(ex: Any, store: Any, clock: Clock) -> None:
    before = store.get_state()
    result = ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=15_000_000))
    assert result.status == OperationStatus.EXECUTED and result.tier == Tier.TIER_1
    after = store.get_state()
    assert after.cash_fen - before.cash_fen == 15_000_000
    assert next(f for f in after.facilities if f.id == "FAC-LINE").drawn_fen == 15_000_000
    assert after.state_version == before.state_version + 1


def test_draw_beyond_available_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=10_000_000))
    before = store.get_state()
    result = ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=5_000_001))
    assert result.status == OperationStatus.REFUSED
    assert [v.code for v in result.violations] == [ViolationCode.PRECONDITION_FAILED]
    assert store.get_state() == before


def test_draw_on_uncommitted_facility_goes_to_owner(ex: Any, store: Any, clock: Clock) -> None:
    before = store.get_state()
    result = ex.execute(op(DrawFacility, clock, facility_id="FAC-GGL", amount_fen=15_000_000))
    assert result.status == OperationStatus.PENDING_APPROVAL and result.tier == Tier.TIER_2
    assert store.get_state() == before
    [approval] = store.approvals()
    assert approval.op_id == result.op_id and approval.kind == "DRAW_FACILITY"
    assert result.approval_id == approval.id and result.effective_day == 0
    # Even approved, the executor re-checks: the facility is still NOT_APPLIED, so nothing is drawn.
    decided = ex.decide(approval.id, True, Actor.OWNER)
    assert decided.status == OperationStatus.REFUSED and decided.approval_id == approval.id
    assert [v.code for v in decided.violations] == [ViolationCode.UNCOMMITTED_FACILITY]
    assert store.get_state() == before


@pytest.mark.parametrize(("cls", "fields"), [
    (ApplyForFacility, {"facility_id": "FAC-GGL", "amount_fen": 30_000_000}),
    (GenerateBorrowerFile, {"facility_id": "FAC-GGL", "amount_fen": 30_000_000}),
])
def test_always_tier2_operations_queue_and_run_on_approval(
    ex: Any, store: Any, clock: Clock, cls: type, fields: dict
) -> None:
    pending = ex.execute(op(cls, clock, **fields))
    assert pending.status == OperationStatus.PENDING_APPROVAL and pending.tier == Tier.TIER_2
    done = ex.decide(approval_id_of(pending), True, Actor.OWNER)
    assert done.status == OperationStatus.EXECUTED
    ggl = next(f for f in store.get_state().facilities if f.id == "FAC-GGL")
    expected = FacilityStatus.PENDING if cls is ApplyForFacility else FacilityStatus.NOT_APPLIED
    assert ggl.status == expected
    assert security_summary(store)["unauthorised_executions"] == 0
