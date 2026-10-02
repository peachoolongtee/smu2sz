"""GET /alerts and GET /reconciliation return displayed views; the flag switches them off."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.alerts import router as alerts_router
from app.api.auth import DEMO_OWNER_TOKEN
from app.api.decide import router as decide_router
from app.api.offers import router as offers_router
from app.api.operations import router as operations_router
from app.api.runtime import Runtime, set_runtime
from app.config import Features, Settings, get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore


def _client(settings: Settings) -> TestClient:
    rt = Runtime(settings=settings, store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    app = FastAPI()
    for r in (alerts_router, offers_router, decide_router, operations_router):
        app.include_router(r)
    return TestClient(app, headers={"X-Owner-Token": DEMO_OWNER_TOKEN})  # owner routes are gated


@pytest.fixture
def client():
    yield _client(get_settings())
    set_runtime(None)


def test_alerts_view(client):
    v = client.get("/alerts").json()
    assert v["basis"] == "CONSERVATIVE" and v["counts"]["CRITICAL"] >= 1
    first = v["alerts"][0]
    assert first["kind"] == "RESERVE_BREACH_AHEAD" and first["day"] == 12 and first["committed_cure"] is True
    assert first["amount_display"] == "¥240,000.00"
    assert all(s["executes_automatically"] is False for s in first["suggested"])


def test_alerts_with_an_evaluated_offer_show_the_day_47_breach(client):
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    v = client.get("/alerts", params={"offer_id": oid}).json()
    breach = [a for a in v["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    # day 47 closes at 209,960 (the day-30 debt payment taken): 300,000 − 209,960 = 90,040 (golden reserve_shortfall_day47)
    assert [a["day"] for a in breach] == [47] and breach[0]["amount_display"] == "¥90,040.00"
    assert client.get("/alerts", params={"offer_id": "OFF-NONE"}).status_code == 404


def test_reconciliation_view(client):
    pay = {"kind": "RECEIVE_PAYMENT", "op_id": "OP-R1", "idempotency_key": "r1", "mandate_version": 1,
           "requested_by": "SYSTEM", "receivable_id": "RCV-A", "amount_fen": 41_000_000}
    assert client.post("/operations", json=pay, headers={"X-Bank-Feed-Key": "demo-bank-feed-key"}).json()["result"]["status"] == "EXECUTED"
    rep = client.get("/reconciliation").json()["reconciliation"]
    [m] = rep["receipts"]
    assert m["status"] == "SHORT_PAYMENT" and m["flagged"] is True
    assert m["received_display"] == "¥410,000.00" and m["difference_display"] == "−¥10,000.00"
    assert rep["chain_valid"] is True


def test_flag_off_returns_feature_disabled():
    c = _client(Settings(features=Features(alerts=False)))
    try:
        for path in ("/alerts", "/reconciliation"):
            r = c.get(path)
            assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"
    finally:
        set_runtime(None)
