import json

import pytest

from app.domain.fixtures import load_scenario
from app.domain.models import ViolationCode
from app.domain.ports import MandatePolicy
from app.mandate import (
    MandatePolicyImpl,
    canonical_bytes,
    check_validity,
    demo_owner_public_key_hex,
    load_demo_owner_key,
    load_signed_mandate,
    revoke,
    sign,
    verify_signature,
)
from app.mandate.fixture import DEMO_KEY_PATH, build_signed_mandate

OTHER_KEY = "11" * 32


@pytest.fixture(scope="module")
def key():
    return load_demo_owner_key()["private_key_hex"]


@pytest.fixture(scope="module")
def mandate():
    return load_scenario()[1]


@pytest.fixture(scope="module")
def signed():
    return load_signed_mandate()


def _codes(vs):
    return {v.code for v in vs}


def test_policy_satisfies_port():
    policy: MandatePolicy = MandatePolicyImpl()
    assert policy.verify_signature(load_signed_mandate())


def test_demo_key_is_loudly_marked():
    raw = json.loads(DEMO_KEY_PATH.read_text())
    assert raw["WARNING"].startswith("DEMO ONLY - NOT A SECRET")


def test_canonical_bytes_sorted_compact_and_excludes_signature(signed):
    b = canonical_bytes(signed)
    data = json.loads(b)
    assert "signature_hex" not in data
    assert data["public_key_hex"] == signed.public_key_hex
    assert list(data) == sorted(data)
    assert b == json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert canonical_bytes(signed.model_copy(update={"signature_hex": "00"})) == b


def test_round_trip(mandate, key):
    s = sign(mandate, key)
    assert s.public_key_hex == demo_owner_public_key_hex()
    assert verify_signature(s)
    assert verify_signature(s, demo_owner_public_key_hex())


def test_signed_fixture_matches_golden_mandate(signed):
    # Ed25519 is deterministic: the committed fixture must equal a fresh signature of the golden mandate.
    assert signed == build_signed_mandate()
    assert verify_signature(signed, demo_owner_public_key_hex())
    assert check_validity(signed, day=0, expected_version=1) == []


def test_unsigned_is_bad(mandate):
    assert not verify_signature(mandate)
    assert _codes(check_validity(mandate, 0, 1)) == {ViolationCode.BAD_SIGNATURE}


def test_tamper_min_cash_by_one_fen(signed):
    tampered = signed.model_copy(update={"min_cash_fen": signed.min_cash_fen - 1})
    assert not verify_signature(tampered)
    [v] = check_validity(tampered, 0, 1)
    assert v.code == ViolationCode.BAD_SIGNATURE and v.observed == "invalid"


def test_tamper_public_key_or_signature(signed):
    assert not verify_signature(signed.model_copy(update={"public_key_hex": "zz"}))
    assert not verify_signature(signed.model_copy(update={"signature_hex": "00" * 64}))


def test_resigned_by_another_key_fails_pinning(signed):
    forged = sign(signed.model_copy(update={"min_cash_fen": 0}), OTHER_KEY)
    assert verify_signature(forged)  # self-consistent...
    assert not verify_signature(forged, demo_owner_public_key_hex())  # ...but not the owner's key
    policy = MandatePolicyImpl(trusted_public_key_hex=demo_owner_public_key_hex())
    [v] = policy.check_validity(forged, 0, 1)
    assert v.code == ViolationCode.BAD_SIGNATURE and v.observed == "signed by an untrusted key"


def test_expiry_boundary(signed):
    assert check_validity(signed, signed.expires_day, 1) == []
    [v] = check_validity(signed, signed.expires_day + 1, 1)
    assert v.code == ViolationCode.MANDATE_EXPIRED and v.day == 91


def test_version_mismatch(signed):
    [v] = check_validity(signed, 0, 2)
    assert v.code == ViolationCode.MANDATE_VERSION_MISMATCH
    assert check_validity(signed, 0, None) == []


def test_revoke_is_a_new_object(signed, key):
    r = revoke(signed)
    assert r is not signed and r.revoked and not signed.revoked
    # Unsigned revocation still revokes; the stale signature is also reported.
    assert _codes(check_validity(r, 0, 1)) == {ViolationCode.MANDATE_REVOKED, ViolationCode.BAD_SIGNATURE}
    r2 = revoke(signed, key)
    assert verify_signature(r2)
    assert _codes(check_validity(r2, 0, 1)) == {ViolationCode.MANDATE_REVOKED}


def test_every_failure_is_reported(mandate):
    vs = check_validity(revoke(mandate), 200, 3)
    assert _codes(vs) == {
        ViolationCode.BAD_SIGNATURE,
        ViolationCode.MANDATE_EXPIRED,
        ViolationCode.MANDATE_REVOKED,
        ViolationCode.MANDATE_VERSION_MISMATCH,
    }
