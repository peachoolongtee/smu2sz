"""API gaps the web app worked around: decision day and result on the approvals queue (G1), the landing day on plan
actions (G2), the approval id on the executed ledger row (G3), the short_facilities demo scenario (G4)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.alerts import AlertKind
from app.api.alerts import router as alerts_router
from app.api.auth import DEMO_OWNER_TOKEN
from app.api.clock import router as clock_router
from app.api.decide import router as decide_router
from app.api.operations import router as operations_router
from app.api.read import router as read_router
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.domain.fixtures import load_scenario
from app.domain.models import FundingActionKind, Mode
from app.financial import project
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore


@pytest.fixture
def client():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    app = FastAPI()
    for r in (alerts_router, decide_router, operations_router, clock_router, read_router):
        app.include_router(r)
    yield TestClient(app, headers={"X-Owner-Token": DEMO_OWNER_TOKEN})
    set_runtime(None)


def _exhaust_line(rt: Runtime) -> None:
    state, _ = load_scenario()
    rt.store.put_state(state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen}) if f.id in ("FAC-LINE", "FAC-IF") else f
        for f in state.facilities]}))


def _queue_one(client: TestClient) -> str:
    _exhaust_line(get_runtime())
    [breach] = [a for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    [res] = client.post(f"/alerts/{breach['id']}/act").json()["results"]
    assert res["status"] == "PENDING_APPROVAL"
    return res["approval_id"]


# ---------------------------------------------------------------- G1 + G3


def test_the_queue_carries_the_decision_day_and_the_decision_runs_message(client):
    aid = _queue_one(client)
    [pending] = client.get("/approvals/queue").json()["approvals"]
    assert pending["id"] == aid and pending["status"] == "PENDING"
    assert pending["decided_day"] is None and pending["result_message"] is None

    rt = get_runtime()
    r = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    day = rt.store.get_state().as_of_day

    rec = rt.store.get_approval(aid)  # stored state: the record itself keeps the day
    assert rec.decided_day == day and rec.status == "APPROVED"
    [item] = client.get("/approvals/queue").json()["approvals"]
    assert item["status"] == "APPROVED" and item["decided_day"] == day
    assert item["result_message"] == result["message"] and item["result_message"]


def test_a_declined_approval_reports_its_day_and_its_message(client):
    aid = _queue_one(client)
    client.post(f"/approvals/{aid}", json={"decision": "REJECT"})
    [item] = client.get("/approvals/queue").json()["approvals"]
    assert item["status"] == "REJECTED"
    assert item["decided_day"] == get_runtime().store.get_state().as_of_day
    assert "Declined by the owner" in item["result_message"]


def test_a_queue_item_decided_before_the_record_kept_its_day_falls_back_to_the_log(client):
    """An old row has no `decided_day`; the DECIDE log entry's `effective_day` stands in."""
    from dataclasses import replace

    aid = _queue_one(client)
    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    rt = get_runtime()
    day = rt.store.get_approval(aid).decided_day
    rt.store._approvals[aid] = replace(rt.store.get_approval(aid), decided_day=None)  # the pre-field shape
    [item] = client.get("/approvals/queue").json()["approvals"]
    assert item["decided_day"] == day


def test_the_ledger_row_of_the_executed_decision_carries_the_approval_id(client):
    aid = _queue_one(client)
    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    ops = client.get("/ledger").json()["operations"]
    queued, decided = [o for o in ops if o["approval_id"] == aid]
    assert queued["status"] == "PENDING_APPROVAL" and decided["status"] in ("EXECUTED", "REFUSED")
    stored = json.loads(get_runtime().store.operations()[decided["seq"] - 1].result_json)
    assert stored["approval_id"] == aid  # the log entry itself, not a response patch
    assert client.get("/ledger").json()["chain_valid"] is True


# ---------------------------------------------------------------- G2


def test_plan_actions_carry_the_day_their_cash_lands(client):
    plan = client.post("/router/plan").json()["committed"]
    state = get_runtime().store.get_state()
    fac = {f.id: f for f in state.facilities}
    rcv = {r.id: r for r in state.receivables}
    acts = plan["actions"]
    assert {a["kind"] for a in acts} >= {"DRAW", "FINANCE_INVOICE"}
    for a in acts:
        if a["kind"] == "DRAW":
            assert a["lands_day"] == a["day"] + fac[a["facility_id"]].lead_time_days
        elif a["kind"] == "FINANCE_INVOICE":
            issue = rcv[a["receivable_id"]].issue_day
            assert a["lands_day"] == max(a["day"], issue) + fac[a["facility_id"]].lead_time_days
        else:
            assert a["lands_day"] is None
    advance = next(a for a in acts if a["kind"] == "FINANCE_INVOICE")
    assert advance["lands_day"] == 3  # FAC-IF lead time (ADR-0010): the advance lands on day 3, not today


def test_lands_day_agrees_with_the_engine():
    """The engine books the cash on the day the plan says it lands."""
    from app.domain.models import LedgerEventKind
    from app.funding.router import plan

    state, mandate = load_scenario()
    p = plan(state, [], mandate)
    traj = project(state, [], p.actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    kinds = {FundingActionKind.DRAW: LedgerEventKind.DRAW, FundingActionKind.FINANCE_INVOICE: LedgerEventKind.ADVANCE}
    checked = 0
    for a in p.actions:
        if a.kind in kinds:
            landed = [e for d in traj.days for e in d.events
                      if e.kind == kinds[a.kind] and e.ref == a.facility_id and e.amount_fen == a.amount_fen]
            assert landed and {e.day for e in landed} == {a.lands_day}, (a.kind, a.facility_id, a.lands_day)
            checked += 1
    assert checked == 2


# ---------------------------------------------------------------- G4


def test_short_facilities_scenario_is_the_golden_books_with_two_short_limits():
    gold, gold_m = load_scenario()
    state, mandate = load_scenario("short_facilities")
    assert mandate == gold_m
    limits = {f.id: f.limit_fen for f in state.facilities}
    assert limits["FAC-LINE"] == limits["FAC-IF"] == 6_000_000
    rest = lambda s: s.model_copy(update={"facilities": [f for f in s.facilities if f.id not in ("FAC-LINE", "FAC-IF")]})  # noqa: E731
    assert rest(state) == rest(gold)
    assert [f.model_copy(update={"limit_fen": 0}) for f in state.facilities if f.id in ("FAC-LINE", "FAC-IF")] == \
        [f.model_copy(update={"limit_fen": 0}) for f in gold.facilities if f.id in ("FAC-LINE", "FAC-IF")]


def test_demo_reset_loads_short_facilities_and_the_zero_floor_alert_fires(client):
    r = client.post("/demo/reset", params={"scenario": "short_facilities"})
    assert r.status_code == 200 and r.json()["scenario"] == "short_facilities"
    assert client.get("/state").json()["scenario_id"] == "short_facilities"
    alerts = client.get("/alerts").json()["alerts"]
    [b] = [a for a in alerts if a["kind"] == AlertKind.RESERVE_BREACH_AHEAD.value]
    zero_day = int(b["inputs"]["zero_day"])
    assert b["title"] == f"cash goes below zero on day {zero_day} without action"
    assert b["inputs"]["cure_restores_reserve"] == "false"
    assert b["committed_cure"] is False and b["actionable"] is True
    # and the golden scenario is back on request
    client.post("/demo/reset")
    [g] = [a for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    assert g["inputs"].get("cure_restores_reserve") != "false"
