"""Mandate validity: signature, expiry, revocation, version. Every failure is reported."""

from __future__ import annotations

from app.domain.models import Mandate, Violation, ViolationCode
from app.mandate.signing import verify_signature


def check_validity(
    mandate: Mandate,
    day: int,
    expected_version: int | None,
    trusted_public_key_hex: str | None = None,
) -> list[Violation]:
    """BAD_SIGNATURE (unsigned, invalid, or not the pinned owner key), MANDATE_EXPIRED
    (day > expires_day), MANDATE_REVOKED, MANDATE_VERSION_MISMATCH (when expected_version is given).
    An empty list means the mandate may be relied on for `day`."""
    out: list[Violation] = []
    if not verify_signature(mandate, trusted_public_key_hex):
        reason = "unsigned" if not mandate.signature_hex or not mandate.public_key_hex else "invalid"
        if reason == "invalid" and trusted_public_key_hex is not None and (
            (mandate.public_key_hex or "").lower() != trusted_public_key_hex.lower()
        ):
            reason = "signed by an untrusted key"
        out.append(
            Violation(
                code=ViolationCode.BAD_SIGNATURE,
                message=f"Mandate v{mandate.version} signature is {reason}",
                observed=reason,
                limit="valid Ed25519 owner signature",
                formula="Ed25519.verify(public_key, canonical_bytes(mandate), signature)",
                inputs={"version": str(mandate.version), "public_key_hex": mandate.public_key_hex or "none"},
            )
        )
    if day > mandate.expires_day:
        out.append(
            Violation(
                code=ViolationCode.MANDATE_EXPIRED,
                message=f"Mandate v{mandate.version} expired on day {mandate.expires_day}",
                day=day,
                observed=f"day {day}",
                limit=f"day {mandate.expires_day}",
                formula="day <= expires_day",
                inputs={"day": str(day), "expires_day": str(mandate.expires_day)},
            )
        )
    if mandate.revoked:
        out.append(
            Violation(
                code=ViolationCode.MANDATE_REVOKED,
                message=f"Mandate v{mandate.version} has been revoked by the owner",
                day=day,
                observed="revoked",
                limit="not revoked",
                formula="revoked == false",
                inputs={"version": str(mandate.version)},
            )
        )
    if expected_version is not None and mandate.version != expected_version:
        out.append(
            Violation(
                code=ViolationCode.MANDATE_VERSION_MISMATCH,
                message=f"Operation expects mandate v{expected_version}, current is v{mandate.version}",
                observed=f"v{mandate.version}",
                limit=f"v{expected_version}",
                formula="mandate.version == expected_version",
                inputs={"version": str(mandate.version), "expected_version": str(expected_version)},
            )
        )
    return out
