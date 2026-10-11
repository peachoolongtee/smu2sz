"""The demo's starting point (brief 03, option B): POST /demo/reset and a fresh start open on the three demo documents
read by the agent and confirmed by the owner, so the deal summary is ready the moment a deal is agreed on Deals. The
confirmations are the owner's logged operations (CONFIRM_DOCUMENT, Tier 2, the first three entries of the chain) and
change no books. The bare `Runtime.reset()` that tests and harnesses use still leaves the chain empty."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.api.runtime as rtmod
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
    assert foshan["stages"][0]["state"] == "done"


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


# ---------------------------------------------------------------- starting without them


@pytest.fixture(params=["memory", "sqlite"])
def cold_start(request, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """A process start on an empty store (DEMO_MODE on), the runtime not yet built."""
    monkeypatch.setenv("DATABASE_URL", "memory" if request.param == "memory" else f"sqlite:///{tmp_path / 'ledger.db'}")
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("OWNER_PUBLIC_KEY_HEX", raising=False)
    set_runtime(None)
    yield monkeypatch
    rt = rtmod._runtime
    if rt is not None and hasattr(rt.store, "dispose"):
        rt.store.dispose()
    set_runtime(None)


def _fails_on(monkeypatch, nth: int):  # type: ignore[no-untyped-def]
    """Make the nth reading of a demo document fail, as a missing or changed fixture would."""
    import app.api.documents as documents

    real, calls = documents.read_document, []

    def flaky(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(1)
        if len(calls) == nth:
            raise ValueError("the demo document cannot be read")
        return real(*args, **kwargs)

    monkeypatch.setattr(documents, "read_document", flaky)


@pytest.mark.parametrize("nth", [1, 2, 3])
def test_a_start_where_a_demo_document_cannot_be_read_goes_on_without_any_of_them(cold_start, caplog, nth):
    _fails_on(cold_start, nth)
    with caplog.at_level("WARNING", logger=rtmod.__name__):
        rt = get_runtime()  # does not raise
    assert [r.levelname for r in caplog.records if r.name == rtmod.__name__] == ["WARNING"]
    assert "starting without them" in caplog.records[-1].getMessage() and caplog.records[-1].exc_info is not None
    # all or none: the confirmations that came before the failure are rolled back with it
    assert rt.store.contract_records() == [] and rt.store.operations() == []
    from app.main import app

    client = TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})
    assert client.get("/documents").json()["documents"] == []
    assert client.get("/state").status_code == 200


def test_a_demo_reset_where_the_documents_cannot_be_read_still_resets(cold_start, caplog):
    from app.main import app

    client = TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})
    assert len(client.get("/documents").json()["documents"]) == 3  # a normal start has them
    _fails_on(cold_start, 1)
    with caplog.at_level("WARNING", logger=rtmod.__name__):
        r = client.post("/demo/reset")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert client.get("/documents").json()["documents"] == [] and client.get("/ledger").json()["operations"] == []
    assert any("starting without them" in rec.getMessage() for rec in caplog.records)


def test_a_normal_start_still_opens_on_the_three_confirmed_documents(cold_start, caplog):
    with caplog.at_level("WARNING", logger=rtmod.__name__):
        rt = get_runtime()
    assert [d.status.value for d in rt.store.contract_records()] == ["CONFIRMED"] * 3
    assert not [r for r in caplog.records if r.name == rtmod.__name__]
