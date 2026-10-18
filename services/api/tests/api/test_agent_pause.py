"""The owner's pause (app/api/agent_pause.py, R-14 "a write switch"): while paused, nothing runs on the agent's or a buyer's authority;
the owner's own operations and the bank feed's receipts still run; the switch is on the hash-chained log and survives a restart."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.agent_pause import PAUSE_KIND, PAUSED_MESSAGE, RESUME_KIND, pause_state
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import Actor, DrawFacility
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def draw(key: str, by: str = "AGENT", amount_fen: int = 1_000_000) -> dict:
    return {"kind": "DRAW_FACILITY", "op_id": key, "idempotency_key": key, "mandate_version": 1, "requested_by": by,
            "facility_id": "FAC-LINE", "amount_fen": amount_fen}


@pytest.fixture
def rt() -> Iterator[Runtime]:
    r = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    r.reset()
    set_runtime(r)
    yield r
    set_runtime(None)


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app)


def status(r) -> str:  # type: ignore[no-untyped-def]
    assert r.status_code == 200, r.text
    return r.json()["result"]["status"]


def test_an_agent_write_is_refused_while_paused_and_runs_after_resume(api: TestClient, rt: Runtime) -> None:
    assert api.get("/agent/pause", headers=OWNER).json()["paused"] is False
    p = api.post("/agent/pause", headers=OWNER)
    assert p.status_code == 200 and p.json()["paused"] is True and p.json()["changed"] is True
    before, ops_before = rt.store.get_state(), len(rt.store.operations())

    r = api.post("/operations", json=draw("pause-draw-1"), headers=AGENT)
    assert status(r) == "REFUSED" and r.json()["result"]["message"] == PAUSED_MESSAGE
    assert r.json()["result"]["violations"][0]["code"] == "INSUFFICIENT_AUTHORITY"
    assert rt.store.get_state() == before and len(rt.store.operations()) == ops_before  # nothing booked, nothing on the log
    assert not [a for a in rt.store.approvals() if "pause-draw-1" in a.op_json]  # not queued either
    events = [e for e in rt.store.security_events() if e.id.startswith("SEC-PAUSE-")]
    assert len(events) == 1 and "AGENT DRAW_FACILITY pause-draw-1" in events[0].detail and events[0].kind.value == "REVOKED"

    assert api.post("/agent/resume", headers=OWNER).json() == {**api.get("/agent/pause", headers=OWNER).json(), "changed": True}
    assert api.get("/agent/pause", headers=OWNER).json()["paused"] is False
    assert status(api.post("/operations", json=draw("pause-draw-2"), headers=AGENT)) in ("EXECUTED", "PENDING_APPROVAL")
    assert rt.store.get_state() != before or rt.store.approvals()  # the agent's write ran again (executed or queued for the owner)


def test_the_owners_own_operations_and_the_bank_feed_still_run_while_paused(api: TestClient, rt: Runtime) -> None:
    api.post("/agent/pause", headers=OWNER)
    owner = api.post("/operations", json=draw("pause-owner-draw", by="OWNER"), headers=OWNER)
    assert status(owner) == "EXECUTED", owner.json()
    rec = next(r for r in rt.store.get_state().receivables if r.status == "OPEN" and r.face_fen - r.settled_fen > 100_00)
    feed = {"kind": "RECEIVE_PAYMENT", "op_id": "pause-feed", "idempotency_key": "pause-feed", "mandate_version": 1,
            "requested_by": "SYSTEM", "receivable_id": rec.id, "amount_fen": 100_00}
    assert status(api.post("/operations", json=feed, headers=BANK)) == "EXECUTED"
    assert api.get("/activity", headers=OWNER).status_code == 200  # the switch's log entries read in the owner's feed


def test_a_buyer_operation_is_refused_too(rt: Runtime) -> None:
    rt.store.append_operation("p", PAUSE_KIND, "p", '{"kind":"PAUSE_AGENT","op_id":"p","requested_by":"OWNER","day":0}',
                              '{"op_id":"p","kind":"PAUSE_AGENT","status":"EXECUTED","tier":"TIER_2","effective_day":0}')
    op = DrawFacility(op_id="pause-cp", idempotency_key="pause-cp", mandate_version=1, requested_by=Actor.COUNTERPARTY, day=rt.day,
                      facility_id="FAC-LINE", amount_fen=1_000_000)
    assert rt.executor.execute(op).message == PAUSED_MESSAGE


def test_only_the_owner_switches_and_a_repeat_writes_nothing(api: TestClient, rt: Runtime) -> None:
    for headers in ({}, AGENT, {"X-Owner-Token": "wrong"}):
        assert api.post("/agent/pause", headers=headers).status_code == 401
        assert api.post("/agent/resume", headers=headers).status_code == 401
    assert pause_state(rt.store) is None
    api.post("/agent/pause", headers=OWNER)
    n = len(rt.store.operations())
    assert api.post("/agent/pause", headers=OWNER).json()["changed"] is False and len(rt.store.operations()) == n
    api.post("/agent/resume", headers=OWNER)
    assert api.post("/agent/resume", headers=OWNER).json()["changed"] is False
    kinds = [r.kind for r in rt.store.operations()]
    assert kinds.count(PAUSE_KIND) == 1 and kinds.count(RESUME_KIND) == 1 and rt.store.verify_chain()


def test_the_pause_survives_a_restart_on_the_same_store(api: TestClient, rt: Runtime) -> None:
    api.post("/agent/pause", headers=OWNER)
    again = Runtime(settings=get_settings(), store=rt.store, owner_key_hex=demo_owner_public_key_hex())
    again.hydrate()
    op = DrawFacility(op_id="pause-restart", idempotency_key="pause-restart", mandate_version=1, requested_by=Actor.AGENT,
                      day=again.day, facility_id="FAC-LINE", amount_fen=1_000_000)
    assert again.executor.execute(op).message == PAUSED_MESSAGE
