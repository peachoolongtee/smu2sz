"""Commitment lifecycle: PROPOSED -> ACCEPTED -> ACTIVE -> FULFILLED, or EXPIRED / REVOKED.

Pure state-machine rules and replay/expiry/terms checks. It decides no business question (tier,
mandate, verdict); the executor calls it and decides what to do with what it reports.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable, Iterable
from typing import Protocol

from app.commitments.terms import terms_hash
from app.domain.models import (
    Commitment,
    CommitmentStatus,
    CompiledOffer,
    Day,
    Fen,
    Obligation,
    ViolationCode,
)

S = CommitmentStatus

ALLOWED: dict[CommitmentStatus, frozenset[CommitmentStatus]] = {
    S.PROPOSED: frozenset({S.ACCEPTED, S.EXPIRED, S.REVOKED}),
    S.ACCEPTED: frozenset({S.ACTIVE, S.EXPIRED, S.REVOKED}),
    # ACTIVE -> EXPIRED: the clock ends a commitment whose only obligations are early payments whose day passed unpaid
    # (red team d, F3); nothing in it binds any more
    S.ACTIVE: frozenset({S.FULFILLED, S.REVOKED, S.EXPIRED}),
    S.EXPIRED: frozenset(),
    S.REVOKED: frozenset(),
    S.FULFILLED: frozenset(),
}

# States in which the commitment is not yet in force, so its expiry day still gates progress.
PRE_ACTIVE = frozenset({S.PROPOSED, S.ACCEPTED})


class CommitmentError(Exception):
    """Base class for lifecycle errors."""


class IllegalTransition(CommitmentError):
    def __init__(
        self, commitment_id: str, from_status: CommitmentStatus, to_status: CommitmentStatus
    ) -> None:
        super().__init__(f"commitment {commitment_id}: {from_status} -> {to_status} is not allowed")
        self.commitment_id = commitment_id
        self.from_status = from_status
        self.to_status = to_status


class CommitmentExpired(CommitmentError):
    def __init__(self, commitment_id: str, expires_day: Day, day: Day) -> None:
        super().__init__(f"commitment {commitment_id} expired on day {expires_day}; now day {day}")
        self.commitment_id = commitment_id
        self.expires_day = expires_day
        self.day = day


class NonceLedger(Protocol):
    """The slice of `LedgerStore` that acceptance checks need."""

    def nonce_used(self, nonce: str) -> bool: ...


def can_transition(from_status: CommitmentStatus, to_status: CommitmentStatus) -> bool:
    return to_status in ALLOWED[from_status]


def transition(commitment: Commitment, to_status: CommitmentStatus, day: Day) -> Commitment:
    """Return a copy of `commitment` in `to_status`.

    Raises `IllegalTransition` for any move outside `ALLOWED`, and `CommitmentExpired` when a
    not-yet-active commitment (PROPOSED or ACCEPTED) is moved to anything but EXPIRED after its
    `expires_day`.
    """
    to_status = CommitmentStatus(to_status)
    if not can_transition(commitment.status, to_status):
        raise IllegalTransition(commitment.id, commitment.status, to_status)
    if day > commitment.expires_day and to_status != S.EXPIRED and commitment.status in PRE_ACTIVE:
        raise CommitmentExpired(commitment.id, commitment.expires_day, day)
    return commitment.model_copy(update={"status": to_status})


def default_nonce() -> str:
    return secrets.token_hex(16)


def commitment_id_for(offer: CompiledOffer, verdict_id: str, nonce: str) -> str:
    digest = hashlib.sha256(f"{offer.offer_id}|{offer.version}|{verdict_id}|{nonce}".encode()).hexdigest()
    return f"CMT-{digest[:16]}"


def new_commitment(
    offer: CompiledOffer,
    verdict_id: str,
    obligations: Iterable[Obligation],
    mandate_version: int,
    expires_day: Day,
    forward_value_fen: Fen,
    nonce_factory: Callable[[], str] = default_nonce,
) -> Commitment:
    """A PROPOSED commitment for `obligations` (the offer's own or an accepted counter's)."""
    obs = list(obligations)
    foreign = sorted({o.counterparty_id for o in obs} - {offer.counterparty_id})
    if foreign:
        raise ValueError(
            f"obligations for {foreign} cannot be committed on offer from {offer.counterparty_id}"
        )
    nonce = nonce_factory()
    if not nonce:
        raise ValueError("nonce_factory returned an empty nonce")
    return Commitment(
        id=commitment_id_for(offer, verdict_id, nonce),
        offer_id=offer.offer_id,
        offer_version=offer.version,
        counterparty_id=offer.counterparty_id,
        verdict_id=verdict_id,
        terms_hash=terms_hash(obs),
        obligations=obs,
        status=S.PROPOSED,
        nonce=nonce,
        expires_day=expires_day,
        mandate_version=mandate_version,
        forward_value_fen=forward_value_fen,
    )


def check_acceptance(
    commitment: Commitment,
    presented_terms_hash: str,
    presented_nonce: str,
    day: Day,
    store: NonceLedger,
) -> list[ViolationCode]:
    """Replay, expiry and terms checks for accepting `commitment`, in the executor's order.

    - REPLAY: the presented nonce is not this commitment's nonce, or it was already used.
    - COMMITMENT_EXPIRED: `day` is after `expires_day`, or the commitment is already EXPIRED.
    - TERMS_CHANGED: the presented terms hash differs from the committed one.
    An empty list means none of these apply. Nothing is written.
    """
    codes: list[ViolationCode] = []
    if not hmac.compare_digest(presented_nonce.encode(), commitment.nonce.encode()) or store.nonce_used(
        presented_nonce
    ):
        codes.append(ViolationCode.REPLAY)
    if day > commitment.expires_day or commitment.status == S.EXPIRED:
        codes.append(ViolationCode.COMMITMENT_EXPIRED)
    if not hmac.compare_digest(presented_terms_hash.encode(), commitment.terms_hash.encode()):
        codes.append(ViolationCode.TERMS_CHANGED)
    return codes
