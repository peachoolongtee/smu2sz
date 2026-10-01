"""POST /alerts/{id}/act: the alert's suggested cure goes to the executor as the agent (tracker row C2)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.alerts import Alert, AlertKind, Severity, SuggestedAction, cure_operations
from app.api.alerts import router as alerts_router
from app.api.auth import DEMO_OWNER_TOKEN
from app.api.clock import router as clock_router
from app.api.decide import router as decide_router
from app.api.offers import router as offers_router
from app.api.operations import router as operations_router
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import Features, Settings, get_settings
from app.domain.fixtures import load_scenario
from app.domain.models import Actor, ApplyForFacility, DrawFacility, SubmitInvoiceForFinancing
from app.domain.money import bp, post
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.alerts.test_alerts import _run, _store

BANK = {"X-Bank-Feed-Key": "demo-bank-feed-key"}


def _client(settings: Settings, owner: bool = True) -> TestClient:
    rt = Runtime(settings=settings, store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    app = FastAPI()
    for r in (alerts_router, offers_router, decide_router, operations_router, clock_router):
        app.include_router(r)
    return TestClient(app, headers={"X-Owner-Token": DEMO_OWNER_TOKEN} if owner else {})


@pytest.fixture
def client():
    yield _client(get_settings())
    set_runtime(None)


def _log(rt) -> list:
    return list(rt.store.operations())


def _day34(client: TestClient) -> tuple[dict, int, str]:
    """The demo path: EX01, cooperative deal, the agreed receipt on the commitment's day, clock to day 34."""
    rt = get_runtime()
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    ob = rt.store.get_commitment(n["commitment"]["id"]).obligations[0]
    agreed = ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
    client.post("/clock/advance", json={"to_day": ob.effective_day})
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "t-receipt-1", "idempotency_key": "t-receipt-1",
        "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
        "receivable_id": ob.base.receivable_id, "amount_fen": agreed}).json()
    assert r["result"]["status"] == "EXECUTED"
    client.post("/clock/advance", json={"to_day": 30})
    client.post("/clock/advance", json={"to_day": 34})
    breach = next(a for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")
    return breach, ob.base.amount_fen, ob.base.receivable_id


def test_act_executes_the_committed_cure_on_the_demo_path(client):
    rt = get_runtime()
    breach, _face, _rid = _day34(client)
    assert breach["severity"] == "CRITICAL" and breach["committed_cure"] is True and breach["actionable"] is True
    [s] = breach["suggested"]
    assert s["operation_kind"] == "SUBMIT_INVOICE_FOR_FINANCING" and s["receivable_id"] == "RI:BUYER-1:2"
    amount = s["amount_fen"]
    assert 19_000_000 <= amount <= 21_000_000  # about ¥200,000
    before = rt.store.get_state()
    logged = len(_log(rt))

    r = client.post(f"/alerts/{breach['id']}/act")
    assert r.status_code == 200
    body = r.json()
    [res] = body["results"]
    assert res["status"] == "EXECUTED" and res["kind"] == "SUBMIT_INVOICE_FOR_FINANCING"
    assert (body["executed"], body["pending_approval"], body["refused"]) == (1, 0, 0)
    assert body["cured"] is True and body["alert_id"] == breach["id"] and body["day"] == 34
    assert body["alerts_after"]["counts"]["CRITICAL"] == 0

    after = client.get("/alerts").json()
    assert after["counts"]["CRITICAL"] == 0 and all(a["severity"] != "CRITICAL" for a in after["alerts"])
    st = rt.store.get_state()
    fb, fa = (next(f for f in x.facilities if f.id == s["facility_id"]) for x in (before, st))
    assert fa.drawn_fen - fb.drawn_fen == amount
    rb, ra = (next(v for v in x.receivables if v.id == s["receivable_id"]) for x in (before, st))
    assert ra.advance_fen - rb.advance_fen == amount

    entries = _log(rt)
    assert len(entries) == logged + 1
    assert json.loads(entries[-1].payload_json)["requested_by"] == Actor.AGENT.value
    assert entries[-1].entry_hash == res["entry_hash"] and entries[-1].prev_hash == entries[-2].entry_hash


def test_act_again_after_a_cure_is_alert_not_found(client):
    breach, _, _ = _day34(client)
    assert client.post(f"/alerts/{breach['id']}/act").status_code == 200
    again = client.post(f"/alerts/{breach['id']}/act")
    assert again.status_code == 404 and again.json()["detail"]["code"] == "ALERT_NOT_FOUND"


def test_act_unknown_alert_is_404(client):
    r = client.post("/alerts/ALERT-NOPE/act")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "ALERT_NOT_FOUND"


def test_act_on_an_alert_with_only_receive_payment_is_409_and_logs_nothing(client):
    rt = get_runtime()
    _day34(client)
    client.post("/clock/advance", json={"to_day": 60})  # the residual invoice is now past due
    past_due = next(a for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RECEIVABLE_PAST_DUE")
    assert {s["operation_kind"] for s in past_due["suggested"]} == {"RECEIVE_PAYMENT"}
    assert past_due["actionable"] is False
    logged = len(_log(rt))
    r = client.post(f"/alerts/{past_due['id']}/act")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NO_EXECUTABLE_CURE"
    assert len(_log(rt)) == logged


def _exhausted_state() -> object:
    state, _ = load_scenario()
    return state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen}) if f.id in ("FAC-LINE", "FAC-IF") else f
        for f in state.facilities]})


def test_a_tier2_cure_is_pending_approval_and_queued(client):
    rt = get_runtime()
    rt.store.put_state(_exhausted_state())
    [breach] = [a for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    assert breach["committed_cure"] is False and breach["actionable"] is True
    assert [s["operation_kind"] for s in breach["suggested"]] == ["APPLY_FOR_FACILITY"]
    cash = rt.store.get_state().cash_fen
    r = client.post(f"/alerts/{breach['id']}/act")
    assert r.status_code == 200
    body = r.json()
    [res] = body["results"]
    assert res["status"] == "PENDING_APPROVAL" and res["approval_id"]
    assert (body["executed"], body["pending_approval"], body["refused"]) == (0, 1, 0)
    assert body["cured"] is False
    queue = client.get("/approvals/queue").json()["approvals"]
    [item] = queue
    assert item["operation"]["kind"] == "APPLY_FOR_FACILITY" and item["operation"]["requested_by"] == "AGENT"
    assert res["approval_id"] in item.values()
    assert rt.store.get_state().cash_fen == cash
    # the alert persists on an unchanged state: a second call replays the executor's DUPLICATE, never re-queues
    again = client.post(f"/alerts/{breach['id']}/act")
    assert again.status_code == 200
    assert [x["status"] for x in again.json()["results"]] == ["DUPLICATE"]
    assert len(client.get("/approvals/queue").json()["approvals"]) == 1


def test_act_without_the_owner_token_is_refused_and_executes_nothing():
    c = _client(get_settings(), owner=False)
    try:
        rt = get_runtime()
        logged = len(_log(rt))
        r = c.post("/alerts/ALERT-RESERVE-12/act")
        assert r.status_code in (401, 403)
        assert len(_log(rt)) == logged
    finally:
        set_runtime(None)


def test_feature_flag_off_is_feature_disabled():
    c = _client(Settings(features=Features(alerts=False)))
    try:
        r = c.post("/alerts/ALERT-RESERVE-12/act")
        assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"
    finally:
        set_runtime(None)


def test_mandate_forbidding_new_borrowing_leaves_no_committed_cure():
    store = _store()
    store.put_mandate(store.get_mandate().model_copy(update={"allow_new_borrowing": False}))
    [breach] = [a for a in _run(store) if a.kind == AlertKind.RESERVE_BREACH_AHEAD]
    assert breach.committed_cure is False and breach.actionable is False and breach.suggested == []
    assert "does not allow new borrowing" in breach.detail


def test_actionable_is_set_only_for_executable_suggestions():
    found = _run(_store())
    breach = next(a for a in found if a.kind == AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.actionable is True
    assert all(a.actionable is False for a in found if a.kind != AlertKind.RESERVE_BREACH_AHEAD)


# ---------------------------------------------------------------- cure_operations


def _alert(*suggested: SuggestedAction) -> Alert:
    return Alert(id="ALERT-X-1", kind=AlertKind.RESERVE_BREACH_AHEAD, severity=Severity.CRITICAL, title="t",
                 detail="d", formula="f", suggested=list(suggested))


def test_cure_operations_maps_the_executable_kinds_in_order_and_skips_the_rest():
    a = _alert(
        SuggestedAction(operation_kind="RECEIVE_PAYMENT", receivable_id="R1", amount_fen=5),
        SuggestedAction(operation_kind="DRAW_FACILITY", facility_id="FAC-LINE", amount_fen=100),
        SuggestedAction(operation_kind="COUNTER_OFFER"),
        SuggestedAction(operation_kind="SUBMIT_INVOICE_FOR_FINANCING", facility_id="FAC-IF", receivable_id="R2",
                        amount_fen=200),
        SuggestedAction(operation_kind="APPLY_FOR_FACILITY", facility_id="FAC-LEASE", amount_fen=300),
    )
    ops = cure_operations(a, day=7, mandate_version=3, state_version=9)
    assert [type(o) for o in ops] == [DrawFacility, SubmitInvoiceForFinancing, ApplyForFacility]
    draw, fin, apply_ = ops
    assert (draw.facility_id, draw.amount_fen) == ("FAC-LINE", 100)
    assert (fin.facility_id, fin.receivable_id, fin.advance_fen) == ("FAC-IF", "R2", 200)
    assert (apply_.facility_id, apply_.amount_fen) == ("FAC-LEASE", 300)
    assert [o.op_id for o in ops] == ["alert:ALERT-X-1:v9:1", "alert:ALERT-X-1:v9:3", "alert:ALERT-X-1:v9:4"]
    assert all(o.idempotency_key == o.op_id for o in ops)
    assert all(o.requested_by == Actor.AGENT and o.day == 7 and o.mandate_version == 3 for o in ops)
    again = cure_operations(a, day=7, mandate_version=3, state_version=9)
    assert [o.model_dump() for o in again] == [o.model_dump() for o in ops]


def test_cure_operations_of_a_non_executable_alert_is_empty():
    a = _alert(SuggestedAction(operation_kind="REPAY_FACILITY", facility_id="F", amount_fen=1))
    assert cure_operations(a, day=0, mandate_version=1, state_version=1) == []
