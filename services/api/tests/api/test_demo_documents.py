"""The demo's starting point (brief 03, option B): POST /demo/reset and a fresh start open on the three demo documents
read by the agent and confirmed by the owner, so the home page shows the deal card at once. The confirmations are the
owner's logged operations (CONFIRM_DOCUMENT, Tier 2, the first three entries of the chain) and change no books. The
bare `Runtime.reset()` that tests and harnesses use still leaves the chain empty."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.runtime import get_runtime, set_runtime

FIXTURES = ["FHR_SUPPLY_AGREEMENT", "MB_CREDIT_LINE_AGREEMENT", "GBR_INVOICE_FINANCING_AGREEMENT"]


def _books(client) -> dict:  # type: ignore[no-untyped-def]
    return client.get("/state").json()["state"]


def test_the_demo_reset_opens_on_the_three_confirmed_documents_and_the_deal(client):
    bare_books = _books(client)  # the fixture's bare reset: no documents, empty chain
    assert client.get("/documents").json()["documents"] == []
    assert client.get("/ledger").json()["operations"] == []

    assert client.post("/demo/reset").status_code == 200
    docs = client.get("/documents").json()["documents"]
    assert [d["source"] for d in docs] == [f"fixture:{f}" for f in FIXTURES]
    assert [(d["id"], d["status"], d["decided_day"], d["decided_seq"]) for d in docs] == [
        ("DOC-000001", "CONFIRMED", 0, 1), ("DOC-000002", "CONFIRMED", 0, 2), ("DOC-000003", "CONFIRMED", 0, 3)]
    assert [d["linked_facility_id"] for d in docs] == [None, "FAC-LINE", "FAC-IF"]

    ledger = client.get("/ledger").json()
    assert [(o["seq"], o["kind"], o["status"], o["tier"], o["requested_by"]) for o in ledger["operations"]] == [
        (n, "CONFIRM_DOCUMENT", "EXECUTED", "TIER_2", "OWNER") for n in (1, 2, 3)]
    assert ledger["chain_valid"] is True
    assert all("nothing in the books changed" in o["message"] for o in ledger["operations"])
    assert _books(client) == bare_books  # confirming writes no books

    foshan = next(d for d in client.get("/deals").json()["deals"] if d["counterparty_id"] == "BUYER-1")
    assert foshan["has_contract"] is True and foshan["contract"]["reference"] == "FHR-2026-07"
    assert [s["state"] for s in foshan["stages"]][0] == "done"


def test_every_demo_reset_starts_over_from_the_same_three_confirmations(client):
    client.post("/demo/reset")
    first = client.get("/ledger").json()["operations"]
    read = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    assert read["id"] == "DOC-000004" and read["status"] == "PROPOSED"  # reading a demo document again is a new reading
    client.post("/demo/reset")
    assert client.get("/ledger").json()["operations"] == first
    assert [d["id"] for d in client.get("/documents").json()["documents"]] == ["DOC-000001", "DOC-000002", "DOC-000003"]


def test_the_bare_reset_keeps_an_empty_chain_and_no_documents(client):
    client.post("/demo/reset")
    get_runtime().reset()
    assert client.get("/ledger").json()["operations"] == []
    assert client.get("/documents").json()["documents"] == []


def test_no_documents_when_contract_ingestion_is_off_or_for_another_scenario(client, monkeypatch):
    assert client.post("/demo/reset", params={"scenario": "short_facilities"}).status_code == 200
    assert get_runtime().store.contract_records() == [] and get_runtime().store.operations() == []
    monkeypatch.setenv("FEATURE_CONTRACTS", "0")
    assert client.post("/demo/reset").status_code == 200
    assert get_runtime().store.contract_records() == [] and get_runtime().store.operations() == []


def test_a_fresh_start_opens_where_the_demo_reset_does(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "memory")
    monkeypatch.setenv("DEMO_MODE", "1")
    set_runtime(None)
    try:
        rt = get_runtime()
        assert [r.status.value for r in rt.store.contract_records()] == ["CONFIRMED"] * 3
        assert [o.kind for o in rt.store.operations()] == ["CONFIRM_DOCUMENT"] * 3
        assert rt.store.verify_chain()
        from app.main import app

        deals = TestClient(app, headers={"X-Owner-Token": "demo-owner-token"}).get("/deals").json()["deals"]
        assert next(d for d in deals if d["counterparty_id"] == "BUYER-1")["has_contract"] is True
    finally:
        set_runtime(None)
