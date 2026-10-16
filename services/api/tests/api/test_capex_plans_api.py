"""ADR-0013, phase 7: POST /capex/plans, owner only, behind FEATURE_CAPEX_CONTRACTS, read-only, labelled an estimate."""

from __future__ import annotations

import pytest

BODY = {"projects": [{"id": "robot", "label": "Packing robot", "price_fen": 40_000_000, "monthly_uplift_fen": 1_500_000,
                      "uplift_start_month": 4, "start_offsets": [0, 3]}]}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


def test_the_route_is_behind_the_flag(client):
    assert client.post("/capex/plans", json=BODY).status_code == 403


def test_plans_are_ranked_displayed_and_write_nothing(client, on):
    from app.api.runtime import get_runtime

    rt = get_runtime()
    state, ops = rt.store.get_state(), len(rt.store.operations())
    r = client.post("/capex/plans", json=BODY)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence"] == "OWNER_ESTIMATE" and body["combinations"] == 2 * 4
    best = body["best"][0]
    assert best["npv_display"].startswith("¥") and best["months"][0]["dscr"]["display"].endswith("×")
    assert rt.store.get_state() == state and len(rt.store.operations()) == ops


def test_a_contract_project_reads_the_stored_record(client, on):
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    body = {"projects": [{"id": "line", "document_id": d["id"], "monthly_uplift_fen": 2_200_000, "start_offsets": [0],
                          "timeline": {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}}]}
    r = client.post("/capex/plans", json=body).json()
    assert r["best"][0]["choices"][0]["first_payment_day"] == 20


def test_a_refused_plan_is_a_422_with_its_code(client, on):
    r = client.post("/capex/plans", json={"projects": [{"id": "a"}]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NO_PRICE"
