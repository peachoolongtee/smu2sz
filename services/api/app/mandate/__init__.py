"""Mandate: canonical serialisation, Ed25519 signing, validity, tiers and mandate predicates.

Public interface: `canonical_bytes()`, `sign()`, `verify_signature()`, `revoke()`,
`check_validity()`, `tier_for()`, `check_predicates()`, `check_apr()`, `load_signed_mandate()`,
and `MandatePolicyImpl`, which satisfies `app.domain.ports.MandatePolicy`.
"""

from __future__ import annotations

from app.domain.models import (
    ConcessionValue,
    FinancialState,
    Mandate,
    Obligation,
    Tier,
    Trajectory,
    Violation,
)
from app.domain.money import Ratio
from app.mandate.fixture import demo_owner_public_key_hex, load_demo_owner_key, load_signed_mandate
from app.mandate.predicates import check_apr, check_predicates
from app.mandate.signing import canonical_bytes, public_key_for, revoke, sign, verify_signature
from app.mandate.tiers import tier_for
from app.mandate.validity import check_validity


class MandatePolicyImpl:
    """Satisfies `app.domain.ports.MandatePolicy`.

    `trusted_public_key_hex` pins the owner's key: signature checks then also require the mandate
    to be signed by that key. Leave it None to accept any valid self-consistent signature."""

    def __init__(self, trusted_public_key_hex: str | None = None) -> None:
        self.trusted_public_key_hex = trusted_public_key_hex

    def canonical_bytes(self, mandate: Mandate) -> bytes:
        return canonical_bytes(mandate)

    def verify_signature(self, mandate: Mandate) -> bool:
        return verify_signature(mandate, self.trusted_public_key_hex)

    def check_validity(self, mandate: Mandate, day: int, expected_version: int | None) -> list[Violation]:
        return check_validity(mandate, day, expected_version, self.trusted_public_key_hex)

    def tier_for(
        self,
        operation: object,
        mandate: Mandate,
        state: FinancialState,
        *,
        accepts_terms_change: bool = False,
        commitment_value_fen: int | None = None,
    ) -> Tier:
        return tier_for(
            operation,
            mandate,
            state,
            accepts_terms_change=accepts_terms_change,
            commitment_value_fen=commitment_value_fen,
        )

    def check_predicates(
        self,
        trajectory: Trajectory,
        obligations: list[Obligation],
        concession_values: list[ConcessionValue],
        state: FinancialState,
        mandate: Mandate,
        counterparty_id: str | None,
    ) -> list[Violation]:
        return check_predicates(trajectory, obligations, concession_values, state, mandate, counterparty_id)

    def check_apr(self, annual_rate: Ratio, mandate: Mandate, label: str) -> Violation | None:
        return check_apr(annual_rate, mandate, label)


__all__ = [
    "MandatePolicyImpl",
    "canonical_bytes",
    "check_apr",
    "check_predicates",
    "check_validity",
    "demo_owner_public_key_hex",
    "load_demo_owner_key",
    "load_signed_mandate",
    "public_key_for",
    "revoke",
    "sign",
    "tier_for",
    "verify_signature",
]
