"""The demo owner key and the signed golden mandate.

DEMO ONLY: fixtures/keys/owner_demo_ed25519.json is a published, throwaway key so the demo and the
tests can sign and verify offline. It is not a secret and must never sign a real mandate.

Regenerate the signed fixture after changing the golden mandate:
    cd services/api && uv run python -m app.mandate.fixture
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.fixtures import FIXTURES, load_scenario
from app.domain.models import Mandate
from app.mandate.signing import public_key_for, sign

DEMO_KEY_PATH: Path = FIXTURES / "keys" / "owner_demo_ed25519.json"
SIGNED_MANDATE_PATH: Path = FIXTURES / "scenarios" / "golden_sme.mandate.signed.json"


def load_demo_owner_key() -> dict[str, str]:
    """{'private_key_hex', 'public_key_hex', ...}. Demo only, not a secret."""
    data = json.loads(DEMO_KEY_PATH.read_text(encoding="utf-8"))
    if public_key_for(data["private_key_hex"]) != data["public_key_hex"]:
        raise ValueError("demo key file is inconsistent")
    return data


def demo_owner_public_key_hex() -> str:
    return load_demo_owner_key()["public_key_hex"]


def load_signed_mandate(path: Path | None = None) -> Mandate:
    """The golden mandate, signed with the demo owner key."""
    raw = json.loads((path or SIGNED_MANDATE_PATH).read_text(encoding="utf-8"))
    return Mandate.model_validate_json(json.dumps(raw["mandate"]))


def build_signed_mandate() -> Mandate:
    _, mandate = load_scenario()
    return sign(mandate, load_demo_owner_key()["private_key_hex"])


def write_signed_mandate(path: Path | None = None) -> Path:
    target = path or SIGNED_MANDATE_PATH
    doc = {
        "_note": (
            "Golden mandate (fixtures/scenarios/golden_sme.json) signed with the DEMO owner key "
            "fixtures/keys/owner_demo_ed25519.json. Ed25519 over canonical_bytes(): sorted-key compact "
            "UTF-8 JSON excluding signature_hex. Regenerate: uv run python -m app.mandate.fixture"
        ),
        "mandate": build_signed_mandate().model_dump(mode="json"),
    }
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    print(write_signed_mandate())
