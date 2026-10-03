"""Regression tests for the fifth red team of 3 Oct 2026 (docs/research/redteam-2026-10-03e), operations side: F3
(scenario events), F4 (the early-pay promise: day and portions), F5 (owner repayment after expiry) and F6 (a queued
receipt keeps its reported day). F1 and F2 are in tests/verifier/test_redteam_e.py.

Each test asserts the stored state (the store's FinancialState, commitments, approvals and log).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.fixtures import load_scenario
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
RCV_A = 42_000_000


def _runtime(store: Any = None) -> Runtime:
    return Runtime(settings=get_settings(), store=store or InMemoryLedgerStore(),
                   owner_key_hex=demo_owner_public_key_hex())


@pytest.fixture
def rt() -> Any:
    r = _runtime()
    r.reset()
    set_runtime(r)
    reset_sessions()
    yield r
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def client(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app)


def post_op(client: TestClient, rt: Runtime, headers: dict, body: dict) -> dict:
    body = {"mandate_version": rt.store.get_mandate().version, "day": rt.day, **body}
    body.setdefault("idempotency_key", body["op_id"])
    r = client.post("/operations", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()["result"]


def move(client: TestClient, day: int) -> None:
    assert client.post("/clock/advance", json={"to_day": day}, headers=OWNER).status_code == 200


def rcv(rt: Runtime, rid: str = "RCV-A") -> Any:
    return next(r for r in rt.store.get_state().receivables if r.id == rid)


def flows(rt: Runtime) -> set[str]:
    return {f.id for f in rt.store.get_state().flows}


# ================================================================ F3: scenario events stay with their scenario


def test_f3_the_demo_seed_stores_its_scenario_and_the_golden_payroll_still_arrives(rt: Runtime) -> None:
    s = rt.store.get_state()
    assert s.scenario == "golden_sme" and json.loads(s.model_dump_json())["scenario"] == "golden_sme"
    rt.advance_to(30)
    assert "F-PAYROLL-M2" in flows(rt) and rt.store.get_state().scenario == "golden_sme"


def test_f3_a_fixture_state_names_no_scenario_and_serialises_as_before() -> None:
    state, _ = load_scenario()
    assert state.scenario is None and "scenario" not in json.loads(state.model_dump_json())


def test_f3_provisioned_books_get_no_scenario_events(rt: Runtime) -> None:
    own, _ = load_scenario()  # stands in for any business's provisioned books: no scenario stored
    rt.store.put_state(own)
    rt.advance_to(30)
    assert "F-PAYROLL-M2" not in flows(rt) and rt.store.get_state().scenario is None
    adv = [json.loads(o.payload_json) for o in rt.store.operations() if o.kind == "ADVANCE_CLOCK"][-1]
    assert "F-PAYROLL-M2" not in json.dumps(adv)


def test_f3_outside_demo_mode_even_seeded_books_get_no_scenario_events(rt: Runtime,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "0")
    rt.advance_to(30)
    assert "F-PAYROLL-M2" not in flows(rt)


def test_f3_a_restart_hydrates_the_scenario_and_applies_only_its_events(rt: Runtime) -> None:
    rt.reset("short_facilities")
    rt.advance_to(20)
    again = _runtime(rt.store)  # what get_runtime() does on start-up with a store that already holds books
    again.hydrate()
    assert (again.scenario, again.day) == ("short_facilities", 20)
    again.advance_to(30)
    assert "F-PAYROLL-M2" not in flows(again) and again.store.get_state().scenario == "short_facilities"


# ================================================================ F4: the early-pay promise names its day; portions


FACE_A = 25_720_000  # Counter A: up to ¥257,200 of RCV-A at 0.85%, paid on or before day 2


def _counter_a(client: TestClient, rt: Runtime) -> Any:
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    cm = rt.store.get_commitment(n["commitment"]["id"])
    [ep] = [o for o in cm.obligations if o.type.value == "IMMEDIATE_DISCOUNT"]
    return cm, ep


def _bank(client: TestClient, rt: Runtime, op_id: str, amount: int) -> dict:
    return post_op(client, rt, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": op_id, "requested_by": "SYSTEM",
                                      "receivable_id": "RCV-A", "amount_fen": amount})


def _early_events(rt: Runtime) -> list[tuple[int, str, int]]:
    from app.books import current_books
    from app.domain.models import Mode
    from app.financial import project

    books = current_books(rt.store.get_state(), rt.store.commitments())
    t = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, 40)
    return [(p.day, e.kind.value, e.amount_fen) for p in t.days for e in p.events
            if e.kind.value in ("EARLY_RECEIPT", "DISCOUNT") or (e.kind.value == "RECEIPT" and e.ref == "RCV-A")]


def test_f4_counter_a_names_its_day_and_keeps_its_figures(client: TestClient, rt: Runtime) -> None:
    cm, ep = _counter_a(client, rt)
    assert (ep.rate_bp, ep.base.amount_fen, ep.effective_day) == (85, FACE_A, 2)
    assert ep.spans[0].text == ("We will accept early settlement on up to ¥257,200 of this invoice at 0.85%, paid on "
                                "or before day 2.")
    v = rt.store.get_verdict(cm.verdict_id)
    a = next(k for k in v.counters if k.label == "Option A")
    assert "¥2,186.20" in a.formula and "¥3,027.77" in a.formula


def test_f4_a_portion_paid_early_settles_its_face_and_the_rest_may_follow_by_the_day(client: TestClient,
                                                                                      rt: Runtime) -> None:
    cm, ep = _counter_a(client, rt)
    move(client, 1)
    # ¥100,000 of face at 0.85%: discount post(850.00) = ¥850.00, receipt ¥99,150.00
    r1 = _bank(client, rt, "rx-part-1", 10_000_000 - 85_000)
    assert r1["status"] == "EXECUTED" and "settles ¥100,000.00 at the agreed 0.85%" in r1["message"]
    a = rcv(rt)
    assert (a.settled_fen, a.outstanding_fen, a.early_paid_fen) == (10_000_000, 32_000_000, {ep.id: 10_000_000})
    assert rt.store.get_commitment(cm.id).status.value == "ACTIVE"
    # the projection carries the rest of the promise: ¥157,200 on day 2 less post(0.85% × 157,200) = ¥1,336.20
    assert _early_events(rt) == [(2, "EARLY_RECEIPT", 15_720_000), (2, "DISCOUNT", -133_620),
                                 (32, "RECEIPT", 16_280_000)]
    move(client, 2)
    r2 = _bank(client, rt, "rx-part-2", 15_720_000 - 133_620)
    assert r2["status"] == "EXECUTED" and "settles ¥157,200.00" in r2["message"]
    a = rcv(rt)
    assert (a.settled_fen, a.early_paid_fen) == (FACE_A, {ep.id: FACE_A})
    assert _early_events(rt) == [(32, "RECEIPT", 42_000_000 - FACE_A)]
    from app.alerts import MatchStatus, PromiseStatus, reconcile

    rep = reconcile(rt.store, day=rt.day)
    assert [m.status for m in rep.receipts] == [MatchStatus.MATCHED, MatchStatus.MATCHED]
    assert [m.agreed_discount_fen for m in rep.receipts] == [85_000, 133_620]
    [row] = rep.promised
    assert (row.status, row.face_fen, row.discount_fen, row.receipt_seq) == (
        PromiseStatus.RECEIVED, FACE_A, 218_620, rep.receipts[-1].seq)


def test_f4_a_partial_promise_row_shows_the_portion_received(client: TestClient, rt: Runtime) -> None:
    _, ep = _counter_a(client, rt)
    move(client, 1)
    _bank(client, rt, "rx-part", 10_000_000 - 85_000)
    from app.alerts import PromiseStatus, reconcile

    [row] = reconcile(rt.store, day=rt.day).promised
    assert (row.status, row.face_fen, row.discount_fen, row.expected_fen) == (
        PromiseStatus.RECEIVED, 10_000_000, 85_000, 9_915_000)
    assert "¥157,200.00 may still be settled early by day 2" in row.detail


def test_f4_after_the_named_day_the_agreed_amount_is_a_plain_receipt(client: TestClient, rt: Runtime) -> None:
    _counter_a(client, rt)
    move(client, 5)
    r = _bank(client, rt, "rx-late", FACE_A - 218_620)
    assert r["status"] == "EXECUTED" and "early-payment" not in r["message"]
    a = rcv(rt)
    assert (a.settled_fen, a.early_paid_fen) == (FACE_A - 218_620, {})


# ================================================================ F5: the owner repays after the mandate expired


def test_f5_the_owner_repays_after_expiry_and_the_agent_may_not(client: TestClient, rt: Runtime) -> None:
    d = post_op(client, rt, OWNER, {"kind": "DRAW_FACILITY", "op_id": "own-draw", "requested_by": "OWNER",
                                    "facility_id": "FAC-LINE", "amount_fen": 10_000_000})
    assert d["status"] == "EXECUTED"
    rt.advance_to(91)
    assert rt.store.get_mandate().expires_day < rt.day
    agent = post_op(client, rt, AGENT, {"kind": "REPAY_FACILITY", "op_id": "agent-repay", "requested_by": "AGENT",
                                        "facility_id": "FAC-LINE", "amount_fen": 10_000_000})
    assert agent["status"] == "REFUSED" and [v["code"] for v in agent["violations"]] == ["MANDATE_EXPIRED"]
    for rid in ("RCV-A", "RI:BUYER-1:2"):  # the buyer's money arrives (a fact the expired mandate does not stop)
        assert post_op(client, rt, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": f"rx-{rid}", "requested_by": "SYSTEM",
                                          "receivable_id": rid, "amount_fen": RCV_A})["status"] == "EXECUTED"
    cash0 = rt.store.get_state().cash_fen
    r = post_op(client, rt, OWNER, {"kind": "REPAY_FACILITY", "op_id": "own-repay", "requested_by": "OWNER",
                                    "facility_id": "FAC-LINE", "amount_fen": 10_000_000})
    assert r["status"] == "EXECUTED", r["message"]
    s = rt.store.get_state()
    line = next(f for f in s.facilities if f.id == "FAC-LINE")
    assert line.drawn_fen == 0 and s.cash_fen < cash0 - 10_000_000  # principal plus the interest accrued
    assert not [x for x in s.lots if x.facility_id == "FAC-LINE"]


# ================================================================ F6: a queued receipt keeps the day it was reported


def test_f6_an_on_time_report_approved_late_earns_the_discount(client: TestClient, rt: Runtime) -> None:
    cm, ep = _counter_a(client, rt)
    move(client, 2)
    agreed = FACE_A - 218_620
    q = post_op(client, rt, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rx", "requested_by": "AGENT",
                                    "receivable_id": "RCV-A", "amount_fen": agreed})
    assert q["status"] == "PENDING_APPROVAL"
    move(client, 3)  # the clock closes day 2 with the report still queued: the agreement is ended as lapsed
    assert rt.store.get_commitment(cm.id).lapsed_obligations == [ep.id]
    cash0 = rt.store.get_state().cash_fen
    d = client.post(f"/approvals/{q['approval_id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
    assert d["status"] == "EXECUTED"
    assert "reported on day 2, booked on day 3" in d["message"] and "settles ¥257,200.00" in d["message"]
    a = rcv(rt)
    assert (a.settled_fen, a.outstanding_fen, a.early_paid_fen) == (FACE_A, 42_000_000 - FACE_A, {ep.id: FACE_A})
    assert rt.store.get_state().cash_fen == cash0 + agreed  # cash on the approval day
    c = rt.store.get_commitment(cm.id)
    assert (c.status.value, c.settled_obligations, c.lapsed_obligations) == ("EXPIRED", [ep.id], [])
    entry = [o for o in rt.store.operations() if o.kind == "RECEIVE_PAYMENT"][-1]
    payload = json.loads(entry.payload_json)
    assert (payload["day"], payload["reported_day"]) == (3, 2)
    from app.alerts import MatchStatus, PromiseStatus, reconcile

    rep = reconcile(rt.store, day=rt.day)
    [m] = [m for m in rep.receipts if m.status != MatchStatus.UNMATCHED]
    assert m.status == MatchStatus.MATCHED and m.agreed_discount_fen == 218_620 and m.day == 3
    [row] = rep.promised
    assert row.status == PromiseStatus.RECEIVED and row.face_fen == FACE_A


def test_f6_a_request_may_not_carry_its_own_reported_day(client: TestClient, rt: Runtime) -> None:
    _counter_a(client, rt)
    move(client, 5)
    r = post_op(client, rt, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-backdated", "requested_by": "SYSTEM",
                                   "receivable_id": "RCV-A", "amount_fen": FACE_A - 218_620, "reported_day": 1})
    assert r["status"] == "REFUSED" and rcv(rt).settled_fen == 0


def test_f6_an_agent_cannot_backdate_a_queued_report(client: TestClient, rt: Runtime) -> None:
    _counter_a(client, rt)
    move(client, 5)
    q = post_op(client, rt, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-bd", "requested_by": "AGENT",
                                    "receivable_id": "RCV-A", "amount_fen": FACE_A - 218_620, "reported_day": 1})
    assert q["status"] == "PENDING_APPROVAL"
    d = client.post(f"/approvals/{q['approval_id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
    assert d["status"] == "EXECUTED" and "early-payment" not in d["message"]  # dated to day 5, the day it was queued
    assert rcv(rt).early_paid_fen == {}
