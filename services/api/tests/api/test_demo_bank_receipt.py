"""POST /demo/bank-receipt: the guided Demo's one synthetic receipt (wayfinder #65, ticket #75)."""

from fastapi.testclient import TestClient

from app.api.runtime import get_runtime


def _deal(client):
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    verdict = client.post(f"/offers/{offer}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    sent = client.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative", "verdict_id": verdict["id"],
                                                   "counter_id": verdict["counters"][0]["id"], "state_version": verdict["state_version"]})
    assert sent.json()["outcome"] == "DEAL"


def test_the_receipt_is_the_promised_amount_from_the_bank_feed_and_says_it_is_synthetic(client):
    _deal(client)
    assert client.post("/clock/advance", json={"to_day": 2}).status_code == 200
    # The clock alone records no receipt.
    assert client.get("/reconciliation").json()["reconciliation"]["promised"][0]["status"] == "AWAITED"
    r = client.post("/demo/bank-receipt")
    assert r.status_code == 200
    body = r.json()
    assert body["synthetic"] is True and body["bank_reference"] == "DEMO-RCPT-1"
    assert body["result"]["status"] == "EXECUTED"
    recon = client.get("/reconciliation").json()["reconciliation"]
    assert recon["promised"][0]["status"] == "RECEIVED"
    assert recon["receipts"][0]["bank_reference"] == "DEMO-RCPT-1" and recon["receipts"][0]["received_fen"] == recon["promised"][0]["expected_fen"]
    row = next(o for o in client.get("/ledger").json()["operations"] if o["kind"] == "RECEIVE_PAYMENT")
    assert row["requested_by"] == "SYSTEM"
    assert "Synthetic bank event, reference DEMO-RCPT-1" in row["event_detail"]
    zh = next(o for o in client.get("/ledger?lang=zh").json()["operations"] if o["kind"] == "RECEIVE_PAYMENT")
    assert "DEMO-RCPT-1" in zh["event_detail"]


def test_a_second_call_books_nothing_more(client):
    _deal(client)
    client.post("/clock/advance", json={"to_day": 2})
    assert client.post("/demo/bank-receipt").status_code == 200
    again = client.post("/demo/bank-receipt")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "NO_PROMISED_RECEIPT"
    assert len([o for o in client.get("/ledger").json()["operations"] if o["kind"] == "RECEIVE_PAYMENT"]) == 1


def test_no_agreement_means_no_receipt(client):
    r = client.post("/demo/bank-receipt")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NO_PROMISED_RECEIPT"


def test_it_needs_the_owner_and_demo_mode(client, monkeypatch):
    from app.main import app

    assert TestClient(app).post("/demo/bank-receipt").status_code == 401
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("OWNER_TOKEN", "x")
    r = TestClient(app).post("/demo/bank-receipt", headers={"X-Owner-Token": "x"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "DEMO_ONLY"
    assert get_runtime().day == 0
