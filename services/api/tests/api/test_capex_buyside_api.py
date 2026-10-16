"""ADR-0013, phase 3: POST /capex/contracts/{id}/evaluate, owner only, behind FEATURE_CAPEX and FEATURE_CAPEX_CONTRACTS,
read-only, every money figure displayed by the server."""

from __future__ import annotations

import pytest

TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


def _upload(client, confirm: bool = True) -> dict:  # type: ignore[no-untyped-def]
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    if confirm:
        d = client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}).json()["document"]
    return d


def test_the_route_needs_both_flags(client, monkeypatch):
    assert client.post("/capex/contracts/DOC-000001/evaluate", json={}).status_code == 403
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")
    monkeypatch.setenv("FEATURE_CAPEX", "0")
    assert client.post("/capex/contracts/DOC-000001/evaluate", json={}).status_code == 403


def test_the_route_is_owner_only(client, on):
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).post("/capex/contracts/DOC-000001/evaluate", json={}, headers={"X-Agent-Key": "demo-agent-key"})
    assert r.status_code == 401


def test_unknown_and_wrong_kind_documents(client, on):
    assert client.post("/capex/contracts/DOC-000404/evaluate", json={}).status_code == 404
    buyer = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    r = client.post(f"/capex/contracts/{buyer['id']}/evaluate", json={})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NOT_A_CAPEX_CONTRACT"


def test_evaluation_on_the_owners_timeline_is_displayed_and_writes_nothing(client, on):
    from app.api.runtime import get_runtime

    d = _upload(client)
    rt = get_runtime()
    state, ops = rt.store.get_state(), len(rt.store.operations())
    r = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reading_confirmed"] is True and body["schedule"]["derivable"] is True
    pays = body["schedule"]["schedule"]["payments"]
    assert [(p["day"], p["amount_display"]) for p in pays] == [(20, "¥180,000.00"), (105, "¥360,000.00"),
                                                               (440, "¥60,000.00")]
    assert body["evaluation"]["selected_id"] == "loan_36m"
    assert body["evaluation"]["beyond_horizon_display"] == "¥60,000.00"
    assert body["early_pay"]["take"] is True
    assert (body["early_pay"]["return_share_display"], body["early_pay"]["cost_share_display"]) == ("2.04%", "1.78%")
    assert body["schedule"]["schedule"]["early_pay"]["implied_annual_rate_display"] == "18.62%"
    assert rt.store.get_state() == state and len(rt.store.operations()) == ops


def test_an_unconfirmed_reading_can_be_screened_and_says_so(client, on):
    d = _upload(client, confirm=False)
    body = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    assert body["reading_confirmed"] is False and body["evaluation"] is not None


def test_a_missing_day_is_asked_for_not_guessed(client, on):
    d = _upload(client)
    body = client.post(f"/capex/contracts/{d['id']}/evaluate", json={}).json()
    assert body["evaluation"] is None and body["schedule"]["needs"] == ["delivery_day", "acceptance_day"]


def test_a_bad_timeline_is_a_422(client, on):
    d = _upload(client)
    r = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": {"delivery_day": -1}})
    assert r.status_code == 422
    r = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE, "price_fen": 1})
    assert r.status_code == 422
