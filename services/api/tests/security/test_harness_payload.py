"""SEC-01: the attack harness reads the server's typed payload strictly. Presentation keys (`*_display`, `*_when`) are dropped before the strict
model; anything else unknown must still fail, so a typed field the server invents cannot pass the harness unnoticed."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import CompiledOffer
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.security.attacks import _without_display

OWNER = {"X-Owner-Token": "demo-owner-token"}


@pytest.fixture
def client():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def _offer_payloads(client: TestClient) -> list[dict]:
    out = []
    for f in client.get("/fixtures/offers").json()["offers"]:
        if f["kind"] != "offer":
            continue
        r = client.post("/offers", json={"fixture_id": f["id"]}, headers=OWNER)
        if r.status_code == 200:
            out.append(r.json()["offer"])
    return out


def test_every_fixture_offer_payload_parses_after_presentation_keys_are_dropped(client: TestClient) -> None:
    offers = _offer_payloads(client)
    assert offers, "no fixture offer compiled"
    assert any(a.get("reason_when") for o in offers for a in o.get("abstentions", [])), "no payload carries the key that broke the harness"
    for offer in offers:
        CompiledOffer.model_validate_json(json.dumps(_without_display(offer)))


def test_presentation_keys_are_dropped_at_every_depth() -> None:
    x = {"a_display": 1, "b": [{"reason_when": "s", "reason": "r"}], "c": {"message_when": "m", "d": 2}}
    assert _without_display(x) == {"b": [{"reason": "r"}], "c": {"d": 2}}


def test_an_unknown_typed_key_still_fails_the_strict_model(client: TestClient) -> None:
    offer = _without_display(_offer_payloads(client)[0])
    offer["approved_by_owner"] = True  # a field no presentation suffix covers
    with pytest.raises(ValidationError):
        CompiledOffer.model_validate_json(json.dumps(offer))
