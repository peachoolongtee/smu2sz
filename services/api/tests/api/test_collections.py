"""Wave 5 part A (map #65, ticket #74): the collection handoff for one invoice (F15) and the four named facts on the
reconciliation receipts (F25). The walk is the audit's: reset, the EX01 package, a cooperative buyer, day 2, optionally a
receipt (half of what the server expected, or all), day 34."""

from __future__ import annotations

import re

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
OWNER = {"X-Owner-Token": "demo-owner-token"}


def _walk(client, *, receipt: str | None = None, to: int = 34) -> None:
    client.post("/demo/reset", json={})
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative"})
    client.post("/clock/advance", json={"to_day": 2})
    if receipt:
        promise = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
        version = client.get("/mandate").json()["mandate"]["version"]
        amount = promise["expected_fen"] // 2 if receipt == "half" else promise["expected_fen"]
        r = client.post("/operations", headers=BANK, json={
            "kind": "RECEIVE_PAYMENT", "op_id": "rc-1", "idempotency_key": "rc-1", "mandate_version": version,
            "requested_by": "SYSTEM", "receivable_id": promise["receivable_id"], "amount_fen": amount, "bank_reference": "BANK-1"})
        assert r.json()["result"]["status"] == "EXECUTED"
    if to > 30:
        client.post("/clock/advance", json={"to_day": 30})
    if to > 2:
        client.post("/clock/advance", json={"to_day": to})


def test_chase_on_the_half_receipt_walk_carries_the_balance_the_lateness_and_the_promise(client):
    _walk(client, receipt="half")
    r = client.get("/receivables/RCV-A/chase")
    assert r.status_code == 200
    c = r.json()
    assert c["buyer_name"] == "Foshan Home Retail Co."
    assert c["face_display"] == "¥420,000.00" and c["outstanding_display"] == "¥290,000.00"
    assert c["past_due"] is True and c["late_days"] == 2 and c["terms_days"] == 45
    assert c["due_when"] == "2 days ago" and c["issued_when"] == "47 days ago"
    assert [p["status"] for p in c["promises"]] == ["RECEIVED"]
    assert c["promises"][0]["amount_display"] == "¥128,895.00" and c["promises"][0]["promised_when"] == "32 days ago"
    assert c["window_open"] is False  # the early-payment window ended on day 2
    assert c["thread_href"] == "/deals?buyer=BUYER-1"
    text = c["request_text"]
    for figure in ("Foshan Home Retail Co.", "¥420,000.00", "¥290,000.00", "47 days ago", "fell due 2 days ago", "45 days"):
        assert figure in text, figure
    assert "Please confirm the payment date" in text
    # the owner's words: no record ids, no day numbers, anywhere in the payload
    blob = r.text
    assert not re.search(r"CMT-|RCV-|APR-|OP-|RI:|\bday \d", c["request_text"] + " ".join(f["value"] for f in c["facts"]))
    assert "CMT-" not in blob
    facts = {f["id"]: f for f in c["facts"]}
    assert facts["outstanding"]["value"] == "¥290,000.00" and facts["late"]["value"] == "2 days" and facts["terms"]["value"] == "45 days"
    # the same figure the reconciliation (the Receivables page) shows for the invoice
    row = next(o for o in client.get("/reconciliation").json()["reconciliation"]["outstanding"] if o["receivable_id"] == "RCV-A")
    assert row["face_display"] == c["outstanding_display"]


def test_chase_on_an_invoice_not_yet_due_says_when_and_has_no_lateness(client):
    _walk(client, to=2)
    c = client.get("/receivables/RCV-A/chase").json()
    assert c["past_due"] is False and c["late_days"] == 0
    assert c["outstanding_display"] == "¥420,000.00"
    assert "is due in 30 days" in c["request_text"]
    assert {f["id"]: f["value"] for f in c["facts"]}["late"] == "Not yet due"
    # the early-payment promise is still ahead and its window is open: the request says so, with a deadline
    assert c["window_open"] is True and "may be settled early by today" in c["request_text"]
    assert [p["status"] for p in c["promises"]] == ["AWAITED"]


def test_chase_before_any_deal_has_no_thread_and_no_promise(client):
    client.post("/demo/reset", json={})
    c = client.get("/receivables/RCV-A/chase").json()
    assert c["thread_href"] is None and c["promises"] == [] and c["window_open"] is False
    assert c["late_days"] == 0 and "is due in" in c["request_text"]


def test_chase_in_chinese(client):
    _walk(client, receipt="half")
    c = client.get("/receivables/RCV-A/chase?lang=zh").json()
    text = c["request_text"]
    assert text.startswith("尊敬的Foshan Home Retail Co.：")
    assert "¥290,000.00" in text and "已于 2 天前到期" in text and "请确认付款日期" in text
    assert c["due_when"] == "2 天前"
    assert {f["id"]: f["label"] for f in c["facts"]}["outstanding"] == "未付余额"
    assert not re.search(r"[A-Za-z]{2,} (?:remains|fell|issued)", text)


def test_chase_unknown_and_paid_and_bad_language(client):
    _walk(client, to=2)
    missing = client.get("/receivables/NOPE/chase")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "RECEIVABLE_NOT_FOUND"
    assert client.get("/receivables/RCV-A/chase?lang=fr").status_code == 422
    # the route needs the owner
    from fastapi.testclient import TestClient

    from app.main import app
    assert TestClient(app).get("/receivables/RCV-A/chase").status_code in (401, 403)


def test_reconciliation_receipts_carry_the_four_facts_and_the_window(client):
    _walk(client, receipt="half")
    receipt = client.get("/reconciliation").json()["reconciliation"]["receipts"][0]
    assert receipt["received_display"] == "¥128,895.00"
    assert receipt["face_cleared_display"] == "¥130,000.00"
    assert receipt["discount_display"] == "¥1,105.00"
    assert receipt["remaining_display"] == "¥290,000.00"
    assert receipt["window_state"] == "ended"


def test_the_window_is_open_on_the_day_of_the_receipt(client):
    _walk(client, receipt="half", to=2)
    receipt = client.get("/reconciliation").json()["reconciliation"]["receipts"][0]
    assert receipt["window_state"] == "open"
    assert receipt["remaining_display"] == "¥290,000.00"


def test_a_receipt_with_no_agreed_discount_has_no_facts(client):
    client.post("/demo/reset", json={})
    version = client.get("/mandate").json()["mandate"]["version"]
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "rc-plain", "idempotency_key": "rc-plain", "mandate_version": version,
        "requested_by": "SYSTEM", "receivable_id": "RCV-A", "amount_fen": 1_000_000, "bank_reference": "BANK-2"})
    assert r.json()["result"]["status"] == "EXECUTED"
    receipt = client.get("/reconciliation").json()["reconciliation"]["receipts"][0]
    assert "window_state" not in receipt and "face_cleared_display" not in receipt
