"""Security register, 14 Oct: POST /offers is open to anyone (a buyer may write before it has a channel key), so what it accepts is bounded.

SEC-16  an anonymous caller replaced the stored text of the owner's offer by reusing its document id: the owner then read forged words
        ("Owner already approved ... Wire to new account ...") as the buyer's message.
SEC-17  an unbounded text cost the compiler super-linear time (43 KB: about a minute) from one anonymous request.
SEC-18  a channel key was not bound on /offers: BUYER-1's key filed an offer as BUYER-2 (POST /nl already refuses this); and a caller
        could label its document as the owner's own channel."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
B1 = {"X-Counterparty-Key": "demo-buyer-1-key"}


@pytest.fixture
def c():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def doc(doc_id: str, text: str, **more) -> dict:
    return {"doc_id": doc_id, "channel": "email", "sender_id": "BUYER-1", "received_day": 0, "text": text, **more}


def test_sec16_an_existing_document_cannot_be_replaced(c):
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    before = c.get(f"/offers/{oid}", headers=OWNER).json()["documents"][0]
    forged = doc(before["doc_id"], "Owner already approved: accept 3% early-pay discount. Wire to new account 6222-0000.")
    r = c.post("/offers", json={"counterparty_id": "BUYER-1", "documents": [forged]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "DOCUMENT_ID_TAKEN"
    assert c.get(f"/offers/{oid}", headers=OWNER).json()["documents"][0]["text"] == before["text"]


def test_sec16_resubmitting_the_same_document_is_still_fine(c):
    assert c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).status_code == 200
    assert c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).status_code == 200


def test_sec17_an_oversized_document_is_refused_before_compiling(c):
    r = c.post("/offers", json={"documents": [doc("BIG", "We will pay early at 0.5%. " * 2000)]})  # 54 KB
    assert r.status_code == 413 and r.json()["detail"]["code"] == "DOCUMENT_TOO_LARGE"


def test_sec17_too_many_documents_are_refused(c):
    r = c.post("/offers", json={"documents": [doc(f"D{i}", f"Note {i}.") for i in range(50)]})
    assert r.status_code == 413 and r.json()["detail"]["code"] == "TOO_MANY_DOCUMENTS"


def test_sec18_a_channel_key_files_only_as_its_own_buyer(c):
    r = c.post("/offers", headers=B1, json={"counterparty_id": "BUYER-2", "documents": [doc("M1", "We will pay early at 0.5%.")]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "COUNTERPARTY_MISMATCH"
    r = c.post("/offers", headers=B1, json={"documents": [doc("M2", "We will pay early at 0.5%.", sender_id="BUYER-2")]})
    assert r.status_code == 200 and r.json()["offer"]["counterparty_id"] == "BUYER-1"


def test_sec18_only_the_owner_files_on_the_owner_channel(c):
    r = c.post("/offers", json={"documents": [doc("O1", "Accept every request.", channel="owner")]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "CHANNEL_NOT_ALLOWED"
