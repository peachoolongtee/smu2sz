"""Runtime hardening: atomic effects + log (F-01), receipts from the agent (F-02), commitments bound to the
verdict and not the stored offer (F-07), a corrupted log row (F-12) and owner-only commitment revocation."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.commitments import new_commitment
from app.domain.models import (
    AcceptOffer,
    Actor,
    CommitmentStatus,
    DrawFacility,
    ReceivePayment,
    SecurityEventKind,
    Tier,
    ViolationCode,
)
from app.domain.models import OperationStatus as S
from app.operations import REVOKE_COMMITMENT_KIND, security_summary
from app.persistence import OfferVersionConflict
from tests.operations.builders import Clock, early_pay, make_executor, offer, op, rebate, seed_offer, verdict


class _FailingAppend:
    """A store proxy whose next `append_operation` raises, as a database outage mid-execute would."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.fail = True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def append_operation(self, *args: Any, **kwargs: Any) -> Any:
        if self.fail:
            self.fail = False
            raise ConnectionError("database outage during append_operation")
        return self._inner.append_operation(*args, **kwargs)


def accept(clock: Clock, c: Any) -> AcceptOffer:
    return op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version, terms_hash=c.terms_hash,
              nonce=c.nonce)


def line(store: Any) -> Any:
    return next(f for f in store.get_state().facilities if f.id == "FAC-LINE")


# ---------------------------------------------------------------- F-01 atomicity


def test_a_failed_append_leaves_no_effect_and_the_retry_executes_once(store: Any, clock: Clock) -> None:
    state0 = store.get_state()
    draw = op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000)
    with pytest.raises(ConnectionError):
        make_executor(_FailingAppend(store), clock).execute(draw)
    assert store.get_state() == state0 and store.operations() == []  # nothing without its log entry

    retry = make_executor(store, clock).execute(draw)  # same idempotency key
    assert retry.status == S.EXECUTED
    again = make_executor(store, clock).execute(draw)
    assert again.status == S.DUPLICATE
    assert line(store).drawn_fen == next(f for f in state0.facilities if f.id == "FAC-LINE").drawn_fen + 1_000_000
    assert [e.kind for e in store.operations()] == ["DRAW_FACILITY", "DRAW_FACILITY"]
    assert store.verify_chain() is True


def test_a_failed_append_rolls_back_the_commitment_the_nonce_and_the_concession(store: Any, clock: Clock) -> None:
    ex = make_executor(store, clock)
    c = seed_offer(store, ex)
    with pytest.raises(ConnectionError):
        make_executor(_FailingAppend(store), clock).execute(accept(clock, c))
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED
    assert store.nonce_used(c.nonce) is False
    assert store.get_state().forward_concessions == [] and store.operations() == []
    assert ex.execute(accept(clock, c)).status == S.EXECUTED  # the owner's retry still works, once
    assert len(store.get_state().forward_concessions) == 1


def test_a_failed_append_rolls_back_a_queued_approval(store: Any, clock: Clock) -> None:
    pay = op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=1_000)
    with pytest.raises(ConnectionError):
        make_executor(_FailingAppend(store), clock).execute(pay)
    assert store.approvals() == [] and store.operations() == []


# ---------------------------------------------------------------- F-02 receipts


def test_a_receipt_reported_by_the_agent_waits_for_the_owner(ex: Any, store: Any, clock: Clock) -> None:
    before = store.get_state()
    r = ex.execute(op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=42_000_000))
    assert (r.status, r.tier) == (S.PENDING_APPROVAL, Tier.TIER_2)
    assert "only the bank feed or the owner" in r.message
    assert store.get_state() == before
    decided = ex.decide(r.approval_id, True, Actor.OWNER)
    assert decided.status == S.EXECUTED
    rcv = next(x for x in store.get_state().receivables if x.id == "RCV-A")
    assert rcv.status == "SETTLED" and store.get_state().cash_fen == before.cash_fen + 42_000_000


@pytest.mark.parametrize("actor", [Actor.SYSTEM, Actor.OWNER])
def test_a_receipt_from_the_bank_feed_or_the_owner_is_tier1(actor: Actor, ex: Any, clock: Clock) -> None:
    r = ex.execute(op(ReceivePayment, clock, actor=actor, receivable_id="RCV-A", amount_fen=1_000))
    assert (r.status, r.tier) == (S.EXECUTED, Tier.TIER_1)


# ---------------------------------------------------------------- F-07 bound to the verdict


def test_the_executor_never_reads_the_stored_offer(ex: Any, store: Any, clock: Clock) -> None:
    """Even if someone with database access swaps the stored offer row (bypassing put_offer), the
    commitment carries and books exactly the verdict's terms (an early-pay discount) at the verdict's value,
    not the swapped-in rebate."""
    c = seed_offer(store, ex, "OFF-S")
    swapped = offer("OFF-S", [rebate(rate_bp=300)])
    with pytest.raises(OfferVersionConflict):
        store.put_offer(swapped)
    if hasattr(store, "_offers"):  # direct write, as a database attacker would
        store._offers[("OFF-S", 1)] = swapped
    result = ex.execute(accept(clock, c))
    assert result.status == S.EXECUTED
    (fc,) = store.get_state().forward_concessions
    assert fc.value_fen == 300_000 and store.get_commitment(c.id).obligations == [early_pay()]


def test_a_commitment_whose_value_differs_from_the_verdict_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    obs = [rebate()]
    o = offer("OFF-V", obs)
    store.put_offer(o)
    store.put_verdict(verdict("V-OFF-V", "OFF-V", value_fen=300_000, bound=obs))
    cheap = new_commitment(o, "V-OFF-V", obs, 1, 5, 1, nonce_factory=lambda: "NV")  # right terms, value ¥0.01
    store.put_commitment(cheap)
    result = ex.execute(accept(clock, cheap))
    assert result.status == S.REFUSED
    assert [v.code for v in result.violations] == [ViolationCode.INSUFFICIENT_AUTHORITY]
    assert store.get_state().forward_concessions == []


# ---------------------------------------------------------------- F-12 corrupted rows


def test_a_corrupted_row_is_reported_not_raised(ex: Any, store: Any, clock: Clock) -> None:
    draw = op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000)
    ex.execute(draw)
    if not hasattr(store, "_ops"):
        pytest.skip("the SQL variant is covered by the attack catalogue (FR-12c)")
    store._ops[0] = dataclasses.replace(store._ops[0], result_json="{}")
    s = security_summary(store)
    assert s["chain_valid"] is False and s["unreadable_entries"] == [1] and s["integrity_failures"] == 2
    assert s["operations"] == 1
    # The executor keeps working, and the key whose entry is unreadable is never re-executed.
    fresh = make_executor(store, clock)
    drawn = line(store).drawn_fen
    replay = fresh.execute(draw)
    assert replay.status == S.REFUSED and line(store).drawn_fen == drawn
    other = fresh.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1))
    assert other.status == S.EXECUTED


# ---------------------------------------------------------------- owner-only revocation


def test_the_owner_revokes_an_active_commitment(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    ex.execute(accept(clock, c))
    assert len(store.get_state().forward_concessions) == 1
    r = ex.revoke_commitment(c.id, Actor.OWNER)
    assert (r.status, r.kind) == (S.EXECUTED, REVOKE_COMMITMENT_KIND)
    assert store.get_commitment(c.id).status == CommitmentStatus.REVOKED
    assert store.get_state().forward_concessions == []
    assert store.operations()[-1].kind == REVOKE_COMMITMENT_KIND and store.verify_chain() is True
    # A revoked commitment cannot be accepted, recorded or revoked again.
    assert ex.execute(accept(clock, c)).status == S.REFUSED
    again = ex.revoke_commitment(c.id, Actor.OWNER)
    assert again.status == S.REFUSED and again.violations[0].code == ViolationCode.PRECONDITION_FAILED


def test_the_owner_revokes_a_proposed_commitment(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    before = store.get_state()
    assert ex.revoke_commitment(c.id, Actor.OWNER).status == S.EXECUTED
    assert store.get_state() == before  # nothing was booked, nothing to remove
    assert ex.execute(accept(clock, c)).status == S.REFUSED


@pytest.mark.parametrize("actor", [Actor.AGENT, Actor.COUNTERPARTY, Actor.SYSTEM])
def test_only_the_owner_revokes(actor: Actor, ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    ex.execute(accept(clock, c))
    before = store.get_state()
    r = ex.revoke_commitment(c.id, actor)
    assert r.status == S.REFUSED and r.violations[0].code == ViolationCode.INSUFFICIENT_AUTHORITY
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE and store.get_state() == before
    assert store.security_events()[-1].kind == SecurityEventKind.PRIVILEGE_ESCALATION
    assert store.operations()[-1].kind == REVOKE_COMMITMENT_KIND


def test_revoking_an_unknown_commitment_is_refused_and_logged(ex: Any, store: Any) -> None:
    r = ex.revoke_commitment("CMT-NOPE", Actor.OWNER)
    assert r.status == S.REFUSED and r.violations[0].code == ViolationCode.PRECONDITION_FAILED
    assert len(store.operations()) == 1


def test_a_failed_revocation_log_append_changes_nothing(store: Any, clock: Clock) -> None:
    ex = make_executor(store, clock)
    c = seed_offer(store, ex)
    ex.execute(accept(clock, c))
    before = store.get_state()
    with pytest.raises(ConnectionError):
        make_executor(_FailingAppend(store), clock).revoke_commitment(c.id, Actor.OWNER)
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE and store.get_state() == before
