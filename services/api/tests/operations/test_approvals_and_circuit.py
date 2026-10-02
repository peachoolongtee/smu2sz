"""Owner decisions on the Tier-2 queue, and the per-counterparty circuit breaker."""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.models import (
    AcceptOffer,
    Actor,
    AddFacility,
    DrawFacility,
    IssueEquity,
    OperationStatus,
    ReceivePayment,
    RequestOwnerApproval,
    SecurityEventKind,
    ViolationCode,
)
from app.mandate import load_demo_owner_key, load_signed_mandate, revoke
from app.operations import CIRCUIT_THRESHOLD, RESET_CIRCUIT_KIND, approval_id_of, security_summary
from app.persistence import ApprovalAlreadyDecided, NotFound
from tests.operations.builders import Clock, extension, new_facility, op, seed_offer


def codes(result: Any) -> list[ViolationCode]:
    return [v.code for v in result.violations]


def queue_terms_change(ex: Any, store: Any, clock: Clock) -> tuple[Any, str]:
    c = seed_offer(store, ex, obligations=[extension()], expires_day=30)
    pending = ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=1, terms_hash=c.terms_hash,
                            nonce=c.nonce))
    assert pending.status == OperationStatus.PENDING_APPROVAL
    assert pending.approval_id is not None and approval_id_of(pending) == pending.approval_id
    assert store.get_approval(pending.approval_id).op_id == pending.op_id
    return c, pending.approval_id


@pytest.mark.parametrize("actor", [Actor.AGENT, Actor.COUNTERPARTY, Actor.SYSTEM])
def test_decision_by_non_owner_is_refused(ex: Any, store: Any, clock: Clock, actor: Actor) -> None:
    c, aid = queue_terms_change(ex, store, clock)
    r = ex.decide(aid, True, actor)
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.INSUFFICIENT_AUTHORITY]
    assert store.get_approval(aid).status == "PENDING"
    assert store.get_commitment(c.id).status == "PROPOSED"
    assert SecurityEventKind.PRIVILEGE_ESCALATION in {e.kind for e in store.security_events()}
    assert r.seq == len(store.operations()) and store.verify_chain()


def test_approved_op_is_revalidated_against_a_mandate_revoked_after_queueing(
    ex: Any, store: Any, clock: Clock
) -> None:
    c, aid = queue_terms_change(ex, store, clock)
    store.put_mandate(revoke(load_signed_mandate(), load_demo_owner_key()["private_key_hex"]))
    r = ex.decide(aid, True, Actor.OWNER)
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.MANDATE_REVOKED]
    assert store.get_commitment(c.id).status == "PROPOSED"
    assert store.get_state().forward_concessions == []


def test_approved_op_is_revalidated_for_expiry_at_decision_time(ex: Any, store: Any, clock: Clock) -> None:
    _c, aid = queue_terms_change(ex, store, clock)
    clock.day = 31  # the commitment expired on day 30 while waiting for the owner
    r = ex.decide(aid, True, Actor.OWNER)
    assert r.status == OperationStatus.REFUSED and codes(r) == [ViolationCode.COMMITMENT_EXPIRED]


def test_owner_decline_executes_nothing_and_replay_stays_declined(ex: Any, store: Any, clock: Clock) -> None:
    _c, aid = queue_terms_change(ex, store, clock)
    before = store.get_state()
    r = ex.decide(aid, False, Actor.OWNER)
    assert r.status == OperationStatus.REFUSED and r.violations == []
    assert store.get_state() == before and store.get_approval(aid).status == "REJECTED"
    with pytest.raises(ApprovalAlreadyDecided):
        ex.decide(aid, True, Actor.OWNER)
    with pytest.raises(NotFound):
        ex.decide("APR-999999", True, Actor.OWNER)


def test_owner_approval_executes_once(ex: Any, store: Any, clock: Clock) -> None:
    _c, aid = queue_terms_change(ex, store, clock)
    clock.day = 3
    done = ex.decide(aid, True, Actor.OWNER)
    assert done.status == OperationStatus.EXECUTED
    assert (done.approval_id, done.effective_day) == (aid, 3)
    with pytest.raises(ApprovalAlreadyDecided):
        ex.decide(aid, True, Actor.OWNER)
    # Replaying the original operation now returns the executed result as a duplicate.
    original = store.operations()[0]
    replay = ex.execute(AcceptOffer.model_validate_json(original.payload_json))
    assert replay.status == OperationStatus.DUPLICATE and "EXECUTED" in replay.message
    assert len(store.get_state().forward_concessions) == 1


def test_request_owner_approval_queues_but_tier3_stays_refused(ex: Any, store: Any, clock: Clock) -> None:
    # Tier 3 is never queued for the owner: asking for approval of a refused equity issue is itself refused
    refused = ex.execute(op(IssueEquity, clock, amount_fen=1_000_000))
    req = ex.execute(op(RequestOwnerApproval, clock, subject="please approve the equity issue",
                        payload_op_id=refused.op_id))
    assert req.status == OperationStatus.REFUSED and not store.approvals()
    # an agent-reported receipt is Tier 2: it is queued under the executor's own reason, not the subject
    reported = ex.execute(op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=1_000, day=clock.day + 1))
    assert reported.status == OperationStatus.REFUSED  # misdated: refused before the tier gate
    req = ex.execute(op(RequestOwnerApproval, clock, subject="routine sync, no payment", payload_op_id=reported.op_id))
    assert req.status == OperationStatus.PENDING_APPROVAL
    aid = approval_id_of(req)
    rec = store.get_approval(aid)
    assert rec.op_id == reported.op_id and "routine sync" not in rec.reason and "reported by AGENT" in rec.reason
    again = ex.execute(op(RequestOwnerApproval, clock, subject="again", payload_op_id=reported.op_id))
    assert approval_id_of(again) == aid and len(store.approvals()) == 1
    r = ex.decide(aid, True, Actor.OWNER)  # the owner, told exactly what it is, may book the reported receipt
    assert r.status == OperationStatus.EXECUTED
    assert security_summary(store)["unauthorised_executions"] == 0


def test_request_owner_approval_for_unknown_op_is_refused(ex: Any, clock: Clock) -> None:
    r = ex.execute(op(RequestOwnerApproval, clock, subject="?", payload_op_id="OP-NOPE"))
    assert r.status == OperationStatus.REFUSED


def replay_attempt(ex: Any, clock: Clock, c: Any) -> Any:
    return ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=1, terms_hash=c.terms_hash,
                         nonce="FORGED"))


def test_circuit_opens_after_three_refusals_and_only_the_owner_resets_it(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, expires_day=30)
    for _ in range(CIRCUIT_THRESHOLD):
        assert codes(replay_attempt(ex, clock, c)) == [ViolationCode.REPLAY]
    assert ex.circuit_open("BUYER-1")
    genuine = op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=1, terms_hash=c.terms_hash, nonce=c.nonce)
    blocked = ex.execute(genuine)
    assert blocked.status == OperationStatus.REFUSED and codes(blocked) == [ViolationCode.CIRCUIT_OPEN]
    # Other counterparties are unaffected.
    assert ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000)).status == "EXECUTED"

    by_agent = ex.reset_circuit("BUYER-1", Actor.AGENT)
    assert by_agent.status == OperationStatus.REFUSED and ex.circuit_open("BUYER-1")
    by_owner = ex.reset_circuit("BUYER-1", Actor.OWNER)
    assert by_owner.status == OperationStatus.EXECUTED and by_owner.kind == RESET_CIRCUIT_KIND
    assert not ex.circuit_open("BUYER-1")

    ok = ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=1, terms_hash=c.terms_hash,
                       nonce=c.nonce))
    assert ok.status == OperationStatus.EXECUTED
    assert store.verify_chain()


def test_circuit_counts_only_refusals_within_seven_days(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, expires_day=30)
    replay_attempt(ex, clock, c)
    replay_attempt(ex, clock, c)
    clock.day = 6
    replay_attempt(ex, clock, c)
    assert ex.circuit_open("BUYER-1")  # days 0, 0 and 6 are within 7 days of day 6
    clock.day = 7
    assert not ex.circuit_open("BUYER-1")  # the day-0 refusals have aged out
    assert ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=1, terms_hash=c.terms_hash,
                         nonce=c.nonce)).status == OperationStatus.EXECUTED


def test_circuit_trips_on_repeated_facility_injection(ex: Any, store: Any, clock: Clock) -> None:
    for _ in range(CIRCUIT_THRESHOLD):
        ex.execute(op(AddFacility, clock, actor=Actor.COUNTERPARTY, facility=new_facility("SHADOW")))
    assert ex.circuit_open("SHADOW")
    # The owner adding a facility from that lender is still blocked until the owner resets the circuit.
    owner = ex.execute(op(AddFacility, clock, actor=Actor.OWNER, facility=new_facility("SHADOW")))
    assert codes(owner) == [ViolationCode.CIRCUIT_OPEN]
