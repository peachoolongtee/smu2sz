"""AcceptOffer / RecordCommitment / CounterOffer / RejectOffer: replay, expiry, terms hash and tiers."""

from __future__ import annotations

from typing import Any

from app.domain.models import (
    AcceptOffer,
    Actor,
    CommitmentStatus,
    CounterOffer,
    Outcome,
    RecordCommitment,
    RejectOffer,
    SecurityEventKind,
    Tier,
    ViolationCode,
)
from app.domain.models import OperationStatus as S
from app.operations import approval_id_of, security_summary
from tests.operations.builders import Clock, counter, extension, offer, op, rebate, seed_offer, verdict


def accept(clock: Clock, c: Any, **overrides: Any) -> AcceptOffer:
    fields = {"offer_id": c.offer_id, "offer_version": c.offer_version, "terms_hash": c.terms_hash, "nonce": c.nonce}
    return op(AcceptOffer, clock, **{**fields, **overrides})


def codes(result: Any) -> list[ViolationCode]:
    return [v.code for v in result.violations]


def test_accept_activates_commitment_and_books_forward_concession(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    before = store.get_state()
    result = ex.execute(accept(clock, c))
    assert result.status == S.EXECUTED and result.tier == Tier.TIER_1
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE
    assert store.nonce_used(c.nonce)
    after = store.get_state()
    [fc] = after.forward_concessions
    assert (fc.value_fen, fc.commitment_id, fc.counterparty_id) == (300_000, c.id, "BUYER-1")
    assert after.cash_fen == before.cash_fen and after.state_version == before.state_version + 1


def test_reused_nonce_is_replay(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    assert ex.execute(accept(clock, c)).status == S.EXECUTED
    before = store.get_state()
    again = ex.execute(accept(clock, c))  # new idempotency key, same nonce
    assert again.status == S.REFUSED and codes(again) == [ViolationCode.REPLAY]
    assert store.get_state() == before
    assert SecurityEventKind.REPLAY in {e.kind for e in store.security_events()}


def test_wrong_nonce_is_replay(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    result = ex.execute(accept(clock, c, nonce="FORGED"))
    assert codes(result) == [ViolationCode.REPLAY]
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED


def test_acceptance_after_expiry_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, expires_day=5)
    clock.day = 6
    result = ex.execute(accept(clock, c))
    assert result.status == S.REFUSED and codes(result) == [ViolationCode.COMMITMENT_EXPIRED]
    assert store.get_state().forward_concessions == []
    assert not store.nonce_used(c.nonce)


def test_acceptance_cannot_be_backdated_past_expiry(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, expires_day=5)
    clock.day = 6
    result = ex.execute(op(AcceptOffer, Clock(5), offer_id=c.offer_id, offer_version=1, terms_hash=c.terms_hash,
                           nonce=c.nonce))
    assert result.status == S.REFUSED and codes(result) == [ViolationCode.REPLAY]
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED


def test_changed_terms_hash_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    result = ex.execute(accept(clock, c, terms_hash="0" * 64))
    assert result.status == S.REFUSED and codes(result) == [ViolationCode.TERMS_CHANGED]
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED
    assert SecurityEventKind.TERMS_CHANGED in {e.kind for e in store.security_events()}


def test_terms_change_is_tier2_and_runs_after_owner_approval(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, obligations=[extension()])
    pending = ex.execute(accept(clock, c))
    assert pending.status == S.PENDING_APPROVAL and pending.tier == Tier.TIER_2
    assert store.get_commitment(c.id).status == CommitmentStatus.PROPOSED
    clock.day = 2
    done = ex.decide(approval_id_of(pending), True, Actor.OWNER)
    assert done.status == S.EXECUTED
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE
    assert security_summary(store)["unauthorised_executions"] == 0


def test_commitment_above_threshold_is_tier2(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, value_fen=10_000_001)
    result = ex.execute(accept(clock, c))
    assert result.status == S.PENDING_APPROVAL and result.tier == Tier.TIER_2
    assert "above the Tier-2 threshold" in result.message


def test_verdict_requiring_owner_raises_the_tier(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, tier=Tier.TIER_2)
    assert ex.execute(accept(clock, c)).status == S.PENDING_APPROVAL


def test_accept_without_a_backing_verdict_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    store.put_offer(offer("OFF-9", [rebate()]))
    store.put_verdict(verdict("V-OFF-9", "OFF-9"))
    c = ex.propose_commitment("V-OFF-9", expires_day=5, nonce="N9")
    # The stored verdict is replaced by a REJECT with no counters: nothing backs these terms any more.
    store.put_verdict(verdict("V-OFF-9", "OFF-9", outcome=Outcome.REJECT))
    result = ex.execute(accept(clock, c))
    assert result.status == S.REFUSED and codes(result) == [ViolationCode.INSUFFICIENT_AUTHORITY]


def test_accept_for_unknown_offer_is_refused(ex: Any, store: Any, clock: Clock) -> None:
    result = ex.execute(op(AcceptOffer, clock, offer_id="NOPE", offer_version=1, terms_hash="x", nonce="y"))
    assert result.status == S.REFUSED


def test_counter_commitment_can_be_accepted(ex: Any, store: Any, clock: Clock) -> None:
    k = counter()
    store.put_offer(offer("OFF-2", [rebate(rate_bp=300)]))
    store.put_verdict(verdict("V-2", "OFF-2", outcome=Outcome.REJECT, counters=[k]))
    c = ex.propose_commitment("V-2", counter_id=k.id, expires_day=5, nonce="N2")
    assert c.forward_value_fen == k.supplier_cost_fen
    result = ex.execute(accept(clock, c))
    assert result.status == S.EXECUTED
    assert store.get_state().forward_concessions[0].value_fen == 200_000


def test_record_commitment_executes_once(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex)
    first = ex.execute(op(RecordCommitment, clock, commitment_id=c.id, nonce=c.nonce))
    assert first.status == S.EXECUTED
    second = ex.execute(op(RecordCommitment, clock, commitment_id=c.id, nonce=c.nonce))
    assert second.status == S.REFUSED and ViolationCode.REPLAY in codes(second)


def test_record_commitment_with_terms_change_needs_owner(ex: Any, store: Any, clock: Clock) -> None:
    c = seed_offer(store, ex, obligations=[extension()])
    result = ex.execute(op(RecordCommitment, clock, commitment_id=c.id, nonce=c.nonce))
    assert result.status == S.PENDING_APPROVAL and result.tier == Tier.TIER_2


def test_counter_offer_uses_the_verdict_template(ex: Any, store: Any, clock: Clock) -> None:
    k = counter()
    store.put_offer(offer("OFF-3", [rebate(rate_bp=300)]))
    store.put_verdict(verdict("V-3", "OFF-3", outcome=Outcome.REJECT, counters=[k]))
    before = store.get_state()
    ok = ex.execute(op(CounterOffer, clock, offer_id="OFF-3", counter_id=k.id, source_verdict_id="V-3"))
    assert ok.status == S.EXECUTED and ok.message == k.text
    bad = ex.execute(op(CounterOffer, clock, offer_id="OFF-3", counter_id="CTR-FAKE", source_verdict_id="V-3"))
    assert bad.status == S.REFUSED
    assert store.get_state() == before


def test_reject_offer_is_logged_only(ex: Any, store: Any, clock: Clock) -> None:
    before = store.get_state()
    r = ex.execute(op(RejectOffer, clock, offer_id="OFF-1", reason_codes=[ViolationCode.RESERVE_BREACH]))
    assert r.status == S.EXECUTED and store.get_state() == before and store.verify_chain()
