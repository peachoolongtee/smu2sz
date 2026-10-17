"""SEC-19 (external review of the self-assessment, 17 Oct): an anonymous sender can name a registered buyer, and its offer appears on that
buyer's deal where the owner may accept it; the accept card and the approvals queue do not say nobody signed it. A demo reachable over a
network must be able to refuse anonymous intake outright. ANONYMOUS_INTAKE=0 does that; the local demo keeps it on."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

BUYER_1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
OWNER = {"X-Owner-Token": "demo-owner-token"}
TEXT = "We will pay invoice RCV-A early at 0.5%. Nothing else changes."
DOC = {"doc_id": "ANON-1", "channel": "email", "sender_id": "BUYER-1", "received_day": 0, "text": TEXT}


def client(monkeypatch, on: str | None) -> tuple[TestClient, Runtime]:
    if on is None:
        monkeypatch.delenv("ANONYMOUS_INTAKE", raising=False)
    else:
        monkeypatch.setenv("ANONYMOUS_INTAKE", on)
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    return TestClient(app), rt


@pytest.fixture(autouse=True)
def _clear():
    yield
    set_runtime(None)


def test_switched_off_an_unsigned_offer_or_message_is_refused_and_nothing_is_stored(monkeypatch):
    c, rt = client(monkeypatch, "0")
    before = len(rt.store.offers()) if hasattr(rt.store, "offers") else None
    r = c.post("/offers", json={"counterparty_id": "BUYER-1", "documents": [DOC]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ANONYMOUS_INTAKE_OFF"
    r = c.post("/nl", json={"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": TEXT})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ANONYMOUS_INTAKE_OFF"
    if before is not None:
        assert len(rt.store.offers()) == before


def test_switched_off_registered_buyers_and_the_owner_still_get_through(monkeypatch):
    c, _ = client(monkeypatch, "0")
    assert c.post("/offers", json={"documents": [DOC]}, headers=BUYER_1).status_code == 200
    assert c.post("/nl", json={"actor": "COUNTERPARTY", "text": TEXT}, headers=BUYER_1).status_code == 200
    assert c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).status_code == 200


def test_the_local_demo_keeps_anonymous_proposals(monkeypatch):
    c, _ = client(monkeypatch, None)
    assert c.post("/offers", json={"counterparty_id": "BUYER-1", "documents": [DOC]}).status_code == 200
