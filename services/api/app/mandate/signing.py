"""Canonical serialisation and Ed25519 signing of the owner mandate (PyNaCl)."""

from __future__ import annotations

import json

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from app.domain.models import Mandate


def canonical_bytes(mandate: Mandate) -> bytes:
    """Sorted-key, compact UTF-8 JSON of the mandate, excluding `signature_hex`.

    `public_key_hex` is included, so the signature also binds the signer's key."""
    data = mandate.model_dump(mode="json", exclude={"signature_hex"})
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def public_key_for(private_key_hex: str) -> str:
    return SigningKey(bytes.fromhex(private_key_hex)).verify_key.encode().hex()


def sign(mandate: Mandate, private_key_hex: str) -> Mandate:
    """A new mandate carrying the signer's public key and an Ed25519 signature over
    `canonical_bytes`. `private_key_hex` is the 32-byte seed in hex. Owner action only."""
    key = SigningKey(bytes.fromhex(private_key_hex))
    unsigned = mandate.model_copy(update={"public_key_hex": key.verify_key.encode().hex(), "signature_hex": None})
    signature = key.sign(canonical_bytes(unsigned)).signature.hex()
    return unsigned.model_copy(update={"signature_hex": signature})


def verify_signature(mandate: Mandate, trusted_public_key_hex: str | None = None) -> bool:
    """True only if the mandate is signed and the signature verifies against its embedded public
    key. When `trusted_public_key_hex` is given, the embedded key must also equal it (key pinning:
    otherwise anyone could re-sign an edited mandate with their own key)."""
    if not mandate.signature_hex or not mandate.public_key_hex:
        return False
    if trusted_public_key_hex is not None and mandate.public_key_hex.lower() != trusted_public_key_hex.lower():
        return False
    try:
        VerifyKey(bytes.fromhex(mandate.public_key_hex)).verify(
            canonical_bytes(mandate), bytes.fromhex(mandate.signature_hex)
        )
    except (BadSignatureError, ValueError, TypeError):
        return False
    return True


def revoke(mandate: Mandate, private_key_hex: str | None = None) -> Mandate:
    """Owner action: a new mandate with `revoked=True`. Pass the owner's key to re-sign it;
    otherwise the old signature no longer matches and validity reports BAD_SIGNATURE as well as
    MANDATE_REVOKED. Revocation is honoured either way (it can only remove authority)."""
    revoked = mandate.model_copy(update={"revoked": True})
    return sign(revoked, private_key_hex) if private_key_hex else revoked
