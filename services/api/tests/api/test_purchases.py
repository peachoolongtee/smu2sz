"""ADR-0013, phase 8: the buying side of Deals. GET /deals is unchanged with the flag off; with it on, it carries `purchases`,
one row per capex contract through REVIEW, READY, AWAITING_APPROVAL, COMMITTED and PAID."""

from __future__ import annotations

import pytest

TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


def _row(client, doc_id: str) -> dict:  # type: ignore[no-untyped-def]
    return client.get(f"/purchases/{doc_id}").json()["purchase"]


def test_deals_has_no_purchases_key_with_the_flag_off(client):
    assert "purchases" not in client.get("/deals").json()
    assert client.get("/purchases").status_code == 403


def test_deals_has_no_purchases_key_until_there_is_a_capex_contract(client, on):
    assert "purchases" not in client.get("/deals").json()  # so every recorded read without one is unchanged


def test_a_purchase_moves_through_its_stages(client, on):
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    row = _row(client, d["id"])
    assert (row["direction"], row["stage"], row["price_display"]) == ("BUY", "REVIEW", "¥600,000.00")
    assert row["vendor_name"] == "Guangzhou Precision Machinery Co., Ltd." and row["vendor_registered"] is False

    client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    assert _row(client, d["id"])["stage"] == "READY"

    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    aid = client.post(f"/capex/contracts/{d['id']}/commit", json={
        "timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]}).json()["approval_id"]
    row = _row(client, d["id"])
    assert row["stage"] == "AWAITING_APPROVAL" and row["approval_id"] == aid

    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    row = _row(client, d["id"])
    assert row["stage"] == "COMMITTED" and row["vendor_registered"] is True
    assert [(p["day"], p["amount_display"], p["paid"]) for p in row["payments"]] == [
        (20, "¥180,000.00", False), (105, "¥360,000.00", False), (440, "¥60,000.00", False)]
    assert row["next_action"] == "Next payment ¥180,000.00 in 20 days" and row["to_pay_display"] == "¥600,000.00"

    client.post("/clock/advance", json={"to_day": 21})
    row = _row(client, d["id"])
    assert [p["paid"] for p in row["payments"]] == [True, False, False]
    assert row["paid_display"] == "¥180,000.00" and row["to_pay_display"] == "¥420,000.00"

    assert client.post("/clock/advance", json={"to_day": 300}).status_code == 200  # the clock moves at most 366 days a step
    assert client.post("/clock/advance", json={"to_day": 441}).status_code == 200
    assert _row(client, d["id"])["stage"] == "PAID"


def test_deals_lists_purchases_beside_the_buyers(client, on):
    before = client.get("/deals").json()
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    after = client.get("/deals").json()
    assert [p["document_id"] for p in after["purchases"]] == [d["id"]]
    assert [x["counterparty_id"] for x in after["deals"]] == [x["counterparty_id"] for x in before["deals"]]


def test_a_rejected_reading_is_said_so(client, on):
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    client.post(f"/documents/{d['id']}/reject", json={"doc_hash": d["doc_hash"]})
    assert _row(client, d["id"])["stage"] == "REJECTED"


def test_unknown_or_not_a_purchase_is_a_404(client, on):
    assert client.get("/purchases/DOC-404").status_code == 404
    buyer = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    assert client.get(f"/purchases/{buyer['id']}").status_code == 404


def test_the_row_speaks_chinese(client, on):
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    assert client.get(f"/purchases/{d['id']}?lang=zh").json()["purchase"]["next_action"] == "审核代理对合同的读取"
