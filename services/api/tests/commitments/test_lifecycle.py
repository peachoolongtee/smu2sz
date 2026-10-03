"""Commitment lifecycle: every legal and illegal transition, expiry, creation and acceptance checks."""

from __future__ import annotations

import itertools

import pytest

from app.commitments import (
    ALLOWED,
    CommitmentExpired,
    IllegalTransition,
    check_acceptance,
    new_commitment,
    terms_hash,
    transition,
)
from app.domain.models import CommitmentStatus as S
from app.domain.models import ViolationCode
from app.persistence import InMemoryLedgerStore
from tests.persistence import factories as f

LEGAL = {
    (S.PROPOSED, S.ACCEPTED),
    (S.PROPOSED, S.EXPIRED),
    (S.PROPOSED, S.REVOKED),
    (S.ACCEPTED, S.ACTIVE),
    (S.ACCEPTED, S.EXPIRED),
    (S.ACCEPTED, S.REVOKED),
    (S.ACTIVE, S.FULFILLED),
    (S.ACTIVE, S.REVOKED),
    (S.ACTIVE, S.EXPIRED),  # red team d, F3: the clock ends an early-pay commitment whose early payments lapsed
}
ALL_PAIRS = list(itertools.product(S, S))


def test_allowed_table_is_exactly_the_specified_lifecycle():
    assert {(a, b) for a, targets in ALLOWED.items() for b in targets} == LEGAL
    assert set(ALLOWED) == set(S)


@pytest.mark.parametrize(("src", "dst"), sorted(LEGAL))
def test_legal_transition_returns_a_copy_in_the_new_status(src, dst):
    c = f.commitment(status=src, expires_day=10)
    out = transition(c, dst, day=5)
    assert out.status == dst
    assert out.model_dump(exclude={"status"}) == c.model_dump(exclude={"status"})
    assert c.status == src  # the input is not mutated


@pytest.mark.parametrize(("src", "dst"), [p for p in ALL_PAIRS if p not in LEGAL])
def test_illegal_transition_raises(src, dst):
    c = f.commitment(status=src, expires_day=10)
    with pytest.raises(IllegalTransition) as exc:
        transition(c, dst, day=5)
    assert (exc.value.from_status, exc.value.to_status) == (src, dst)


@pytest.mark.parametrize(("src", "dst"), [p for p in ALL_PAIRS if p not in LEGAL])
def test_illegal_transition_after_expiry_is_still_illegal(src, dst):
    with pytest.raises(IllegalTransition):
        transition(f.commitment(status=src, expires_day=10), dst, day=11)


def test_the_expiry_day_itself_is_still_valid():
    c = f.commitment(expires_day=10)
    assert transition(c, S.ACCEPTED, day=10).status == S.ACCEPTED


@pytest.mark.parametrize(
    ("src", "dst"),
    [(S.PROPOSED, S.ACCEPTED), (S.PROPOSED, S.REVOKED), (S.ACCEPTED, S.ACTIVE), (S.ACCEPTED, S.REVOKED)],
)
def test_moving_a_not_yet_active_commitment_after_expiry_raises(src, dst):
    c = f.commitment(status=src, expires_day=10)
    with pytest.raises(CommitmentExpired) as exc:
        transition(c, dst, day=11)
    assert (exc.value.expires_day, exc.value.day) == (10, 11)


@pytest.mark.parametrize("src", [S.PROPOSED, S.ACCEPTED])
def test_expiring_after_the_expiry_day_is_allowed(src):
    assert transition(f.commitment(status=src, expires_day=10), S.EXPIRED, day=30).status == S.EXPIRED


@pytest.mark.parametrize("dst", [S.FULFILLED, S.REVOKED, S.EXPIRED])
def test_an_active_commitment_can_still_close_after_its_acceptance_expiry(dst):
    assert transition(f.commitment(status=S.ACTIVE, expires_day=10), dst, day=400).status == dst


def test_status_may_be_given_as_its_string_value():
    assert transition(f.commitment(), "ACCEPTED", day=0).status == S.ACCEPTED  # type: ignore[arg-type]


# ---------------------------------------------------------------- new_commitment


def test_new_commitment_is_proposed_with_hash_nonce_and_expiry():
    offer = f.offer()
    obs = [f.discount(rate_bp=85)]
    c = new_commitment(offer, "V-1", obs, 3, 7, 12_345, nonce_factory=lambda: "nonce-xyz")
    assert c.status == S.PROPOSED
    assert (c.offer_id, c.offer_version, c.counterparty_id, c.verdict_id) == ("OFF-1", 1, f.BUYER, "V-1")
    assert c.terms_hash == terms_hash(obs)
    assert (c.nonce, c.expires_day, c.mandate_version, c.forward_value_fen) == ("nonce-xyz", 7, 3, 12_345)
    assert c.obligations == obs
    again = new_commitment(offer, "V-1", obs, 3, 7, 12_345, nonce_factory=lambda: "nonce-xyz")
    assert again.id == c.id and c.id.startswith("CMT-")


def test_default_nonces_are_unique():
    offer = f.offer()
    a = new_commitment(offer, "V-1", offer.obligations, 1, 7, 0)
    b = new_commitment(offer, "V-1", offer.obligations, 1, 7, 0)
    assert a.nonce != b.nonce and a.id != b.id and len(a.nonce) >= 32


def test_new_commitment_refuses_another_counterpartys_obligations():
    with pytest.raises(ValueError):
        new_commitment(f.offer(), "V-1", [f.discount(counterparty_id="BUYER-2")], 1, 7, 0)


def test_new_commitment_refuses_an_empty_nonce():
    with pytest.raises(ValueError):
        new_commitment(f.offer(), "V-1", [f.discount()], 1, 7, 0, nonce_factory=lambda: "")


# ---------------------------------------------------------------- check_acceptance


def test_clean_acceptance_has_no_violations():
    store = InMemoryLedgerStore()
    c = f.commitment(expires_day=10)
    assert check_acceptance(c, c.terms_hash, c.nonce, 10, store) == []


def test_changed_terms_are_reported():
    store = InMemoryLedgerStore()
    c = f.commitment()
    changed = terms_hash([f.discount(rate_bp=150)])
    assert check_acceptance(c, changed, c.nonce, 0, store) == [ViolationCode.TERMS_CHANGED]


def test_expiry_is_reported():
    store = InMemoryLedgerStore()
    c = f.commitment(expires_day=10)
    assert check_acceptance(c, c.terms_hash, c.nonce, 11, store) == [ViolationCode.COMMITMENT_EXPIRED]
    expired = c.model_copy(update={"status": S.EXPIRED})
    assert check_acceptance(expired, c.terms_hash, c.nonce, 0, store) == [ViolationCode.COMMITMENT_EXPIRED]


def test_used_or_foreign_nonce_is_a_replay():
    store = InMemoryLedgerStore()
    c = f.commitment()
    assert check_acceptance(c, c.terms_hash, "some-other-nonce", 0, store) == [ViolationCode.REPLAY]
    store.mark_nonce_used(c.nonce)
    assert check_acceptance(c, c.terms_hash, c.nonce, 0, store) == [ViolationCode.REPLAY]


def test_all_codes_come_in_executor_order_and_nothing_is_written():
    store = InMemoryLedgerStore()
    c = f.commitment(expires_day=10)
    store.mark_nonce_used(c.nonce)
    codes = check_acceptance(c, "0" * 64, c.nonce, 99, store)
    assert codes == [ViolationCode.REPLAY, ViolationCode.COMMITMENT_EXPIRED, ViolationCode.TERMS_CHANGED]
    assert store.operations() == [] and store.commitments() == []
