"""ADR-0013, phase 5: GET/POST /finance/health, owner only, behind FEATURE_CAPEX_CONTRACTS, reconciled to Home."""

from __future__ import annotations

import pytest


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


def test_the_route_is_behind_the_flag(client):
    r = client.get("/finance/health")
    assert r.status_code == 403 and r.json()["detail"]["feature"] == "capex_contracts"


def test_the_route_is_owner_only(client, on):
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/finance/health", headers={"X-Agent-Key": "demo-agent-key"}).status_code == 401


def test_cash_reconciles_to_home(client, on):
    h = client.get("/finance/health").json()
    home = client.get("/home").json()["cash"]
    assert h["cash"]["first_breach_day"] == home["first_breach_day"]
    assert h["cash"]["lowest_headroom_fen"] == home["lowest_headroom_fen"]
    assert h["cash"]["headroom_fen"] == home["headroom_fen"]


def test_the_view_is_displayed(client, on):
    h = client.get("/finance/health").json()
    assert h["coverage"]["ratio"]["display"] == "2.55×" and h["coverage"]["out_display"] == "¥650,000.00"
    assert h["covenants"]["dscr_room_monthly_display"] == "¥27,000.00"
    assert h["covenants"]["min_dscr"]["display"] == "1.25×"
    assert h["liquidity"]["available"] is False and h["liquidity"]["current_ratio"] is None


def test_the_owners_entries_give_the_current_and_quick_ratios(client, on):
    body = {"inputs": {"inventory_fen": 30_000_000, "other_current_assets_fen": 0, "trade_payables_fen": 25_000_000,
                       "other_current_liabilities_fen": 5_000_000}}
    li = client.post("/finance/health", json=body).json()["liquidity"]
    assert li["available"] is True and li["evidence"] == "OWNER_ESTIMATE"
    assert li["current_ratio"]["display"] == "1.33×" and li["quick_ratio"]["display"] == "0.98×"


def test_bad_entries_are_refused(client, on):
    assert client.post("/finance/health", json={"inputs": {"inventory_fen": -1}}).status_code == 422
    assert client.post("/finance/health", json={"inputs": {}, "extra": 1}).status_code == 422
