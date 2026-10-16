"""ADR-0013, phase 6: /lending/eligibility and the owner's add-to-menu (their own AddFacility, Tier 2), after which the buy-side
screen considers the new facility."""

from __future__ import annotations

import pytest


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


@pytest.fixture
def rt(client):
    from app.api.runtime import get_runtime

    return get_runtime()


def test_the_routes_are_behind_the_flag(client):
    assert client.get("/lending/eligibility").status_code == 403
    assert client.post("/lending/products/PRD-BANK1-TERM-60/add-to-menu", json={}).status_code == 403


def test_eligibility_is_displayed_and_indicative(client, on):
    e = client.post("/lending/eligibility", json={"inputs": {"months_trading": 48}}).json()
    assert e["indicative"].startswith("Indicative only")
    assert e["buyer_concentration_display"] == "100.00%" and e["largest_buyer_id"] == "BUYER-1"
    term = next(r for r in e["products"] if r["product"]["id"] == "PRD-BANK1-TERM-60")
    assert term["status"] == "ELIGIBLE_UP_TO" and term["all_in_rate_display"].endswith("%")
    assert term["max_eligible_display"].startswith("¥") and term["own_limits_max_display"] == "¥1,245,000.00"


def test_add_to_menu_is_the_owners_tier_2_add_facility(client, on, rt):
    r = client.post("/lending/products/PRD-BANK1-TERM-60/add-to-menu", json={"amount_fen": 60_000_000}).json()
    assert r["status"] == "PENDING_APPROVAL" and r["facility_id"] == "FAC-BANK1-TERM-60"
    assert r["result"]["kind"] == "ADD_FACILITY" and r["result"]["tier"] == "TIER_2"
    assert not any(f.id == "FAC-BANK1-TERM-60" for f in rt.store.get_state().facilities)
    ok = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    assert ok["status"] == "EXECUTED"
    f = next(f for f in rt.store.get_state().facilities if f.id == "FAC-BANK1-TERM-60")
    assert (f.status.value, f.owner_approved, f.limit_fen) == ("NOT_APPLIED", True, 60_000_000)
    again = client.post("/lending/products/PRD-BANK1-TERM-60/add-to-menu", json={})
    assert again.status_code == 409


def test_a_new_lender_is_registered_when_the_owner_adds_its_product(client, on, rt):
    r = client.post("/lending/products/PRD-LENDERNB-SECURED-84/add-to-menu", json={}).json()
    client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"})
    lender = next(c for c in rt.store.get_state().counterparties if c.id == "LENDER-NB")
    assert lender.role == "LENDER" and lender.known


def test_an_amount_outside_the_product_is_refused(client, on):
    r = client.post("/lending/products/PRD-BANK1-TERM-60/add-to-menu", json={"amount_fen": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "AMOUNT_OUT_OF_RANGE"
    assert client.post("/lending/products/PRD-NOPE/add-to-menu", json={}).status_code == 404


def test_the_buy_side_screen_considers_a_product_once_it_is_on_the_menu(client, on):
    r = client.post("/lending/products/PRD-BANK1-TERM-60/add-to-menu", json={"amount_fen": 60_000_000}).json()
    client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"})
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate",
                     json={"timeline": {"signing_day": 30, "delivery_day": 60, "acceptance_day": 80}}).json()
    ids = [s["facility_id"] for s in ev["evaluation"]["structures"] if s["facility_id"]]
    assert "FAC-BANK1-TERM-60" in ids
