"""POST /capex/evaluate: the displayed view, and the Tier-2 application queued but never executed."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import DEMO_OWNER_TOKEN
from app.api.capex import router as capex_router
from app.api.operations import router as operations_router
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import FacilityStatus
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}


@pytest.fixture
def rt():
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


@pytest.fixture
def client(rt):
    app = FastAPI()
    app.include_router(capex_router)
    app.include_router(operations_router)
    return TestClient(app, headers={"X-Owner-Token": DEMO_OWNER_TOKEN})  # owner routes are gated


def etl_status(rt, fid: str = "FAC-ETL"):
    return next(f for f in rt.store.get_state().facilities if f.id == fid).status


def test_view_matches_capex_view(client, g):
    v = client.post("/capex/evaluate", json={"label": "¥600k machine", "price_fen": 60_000_000}).json()
    assert v["npv_fen"] == g["npv"] and v["npv_display"] == "¥380,885.77"
    assert v["payback_month"] == 31
    # the 36-month loan's first payment (day 44) would take cash to ¥296,855.38 once the day-30 debt payment is
    # cash: the 48-month lease is selected (compute_golden.py, capex "selected")
    assert v["selected_id"] == g["selected"] == "lease_48m" and v["required_tier"] == "TIER_2"
    assert v["leverage_financed"]["text"] == "2.08" and v["leverage_with_extension"]["text"] == "2.28"
    assert v["dscr_limit_display"] == "1.25×" and v["leverage_limit_display"] == "2.50×"
    assert v["request"]["price_display"] == "¥600,000.00"
    s = {x["id"]: x for x in v["structures"]}
    assert set(s) == {"cash_line", "loan_18m", "loan_36m", "lease_48m"}
    for x in s.values():
        for key in ("id", "label", "kind", "term_months", "monthly_payment_fen", "total_interest_fen", "feasible",
                    "violations", "dscr_by_month", "extra_cost_vs_selected_fen", "note",
                    "monthly_payment_display", "total_interest_display", "extra_cost_vs_selected_display"):
            assert key in x
    assert s["loan_18m"]["monthly_payment_display"] == "¥34,830.60"
    assert s["loan_18m"]["violations"][0]["code"] == "DSCR_BREACH"
    assert s["loan_18m"]["dscr_by_month"][0]["dscr"]["text"] == "1.13"
    assert s["loan_36m"]["monthly_payment_display"] == "¥18,144.62"
    assert s["loan_36m"]["total_interest_display"] == "¥53,206.14"
    assert s["loan_36m"]["violations"][0]["code"] == "RESERVE_BREACH"
    assert s["lease_48m"]["extra_cost_vs_selected_display"] is None  # it is the selected structure
    assert s["cash_line"]["feasible"] is False
    assert s["cash_line"]["violations"][0]["code"] == "RESERVE_BREACH"
    assert s["cash_line"]["monthly_payment_display"] is None


def test_default_body_is_the_spec_case(client, g):
    v = client.post("/capex/evaluate").json()
    assert v["npv_fen"] == g["npv"] and v["selected_id"] == g["selected"] == "lease_48m"


def test_application_is_pending_and_nothing_executes_without_the_owner(client, rt):
    v = client.post("/capex/evaluate", json={}).json()
    assert v["application"]["status"] == "PENDING_APPROVAL" and v["application"]["tier"] == "TIER_2"
    assert v["application"]["kind"] == "APPLY_FOR_FACILITY"
    aid = v["approval_id"]
    assert aid and v["approval_status"] == "PENDING"
    queue = client.get("/approvals/queue").json()["approvals"]
    queued = [a for a in queue if a["id"] == aid]
    assert queued and queued[0]["operation"]["facility_id"] == "FAC-LEASE"
    assert queued[0]["operation"]["requested_by"] == "AGENT"
    assert queued[0]["operation"]["amount_fen"] == 60_000_000
    assert etl_status(rt, "FAC-LEASE") == FacilityStatus.NOT_APPLIED  # nothing executed

    denied = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}, headers={"X-Owner-Token": "not-the-owner"})
    assert denied.status_code == 401  # the owner gate refuses before the executor
    assert etl_status(rt, "FAC-LEASE") == FacilityStatus.NOT_APPLIED

    ok = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
    assert ok["status"] == "EXECUTED"
    assert etl_status(rt, "FAC-LEASE") == FacilityStatus.PENDING  # applied: still counts as zero until committed


def test_repeat_evaluation_does_not_queue_twice(client):
    first = client.post("/capex/evaluate", json={}).json()
    again = client.post("/capex/evaluate", json={}).json()
    assert again["application"]["status"] == "DUPLICATE"
    assert again["approval_id"] == first["approval_id"]
    queue = client.get("/approvals/queue").json()["approvals"]
    assert len([a for a in queue if a["kind"] == "APPLY_FOR_FACILITY"]) == 1


def test_not_worth_doing_queues_nothing(client):
    v = client.post("/capex/evaluate", json={"monthly_uplift_fen": 1_000_000}).json()
    assert v["worth_doing"] is False and v["approval_id"] is None and v["application"] is None
    assert client.get("/approvals/queue").json()["approvals"] == []


def test_flag_off_returns_feature_disabled(client, monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX", "0")
    r = client.post("/capex/evaluate", json={})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "FEATURE_DISABLED"
    assert client.get("/approvals/queue").json()["approvals"] == []


def test_unknown_field_is_rejected(client):
    assert client.post("/capex/evaluate", json={"price_fen": 60_000_000, "tier": "TIER_1"}).status_code == 422


def test_f4_a_hypothetical_term_is_never_applied_for(client, rt):
    # ETL's menu term is 36 months: a 360-month candidate is an illustration, so nothing is selected or queued.
    v = client.post("/capex/evaluate", json={"candidates": [{"facility_id": "FAC-ETL", "term_months": 360}],
                                             "include_cash_line": False}).json()
    s = {x["id"]: x for x in v["structures"]}
    assert s["loan_360m"]["hypothetical"] is True
    assert v["selected_id"] is None and v["approval_id"] is None and v["application"] is None
    assert client.get("/approvals/queue").json()["approvals"] == []
    assert etl_status(rt) == FacilityStatus.NOT_APPLIED


def test_view_carries_the_charges_basis_assumptions_and_day(client):
    v = client.post("/capex/evaluate", json={}).json()
    s = {x["id"]: x for x in v["structures"]}
    assert s["loan_36m"]["upfront_fee_fen"] == 0 and s["loan_36m"]["charges_total_fen"] == 5_320_614
    assert s["loan_36m"]["charges_total_display"] == "¥53,206.14" and s["loan_18m"]["hypothetical"] is True
    assert v["as_of_day"] == 0 and v["estimate_note"].startswith("Owner's estimate")
    assert any("nominal annual rate" in a for a in v["assumptions"])
    assert "Finance with the 48-month lease" in v["recommendation"]
    assert "36-month term loan, 5.60% is rejected (RESERVE_BREACH)" in v["recommendation"]
