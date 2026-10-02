"""Third red team, 3 Oct: the owner sees the operation's own reason, never the requester's text; admission counts
the cash a line draw brings; a recreated chat session never reuses an old key."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import Settings
from app.domain.models import Actor, DrawFacility
from app.funding.admission import _as_carried
from app.main import app
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}


@pytest.fixture
def api():
    rt = Runtime(Settings(), InMemoryLedgerStore(), demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    yield rt, TestClient(app)
    set_runtime(None)


def _op(c, headers, **body):
    r = c.post("/operations", headers=headers, json={"mandate_version": 1, "requested_by": "AGENT", **body})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def test_the_owner_sees_the_operation_not_the_requesters_words(api):
    rt, c = api
    refused = _op(c, AGENT, kind="RECEIVE_PAYMENT", op_id="sync-1", idempotency_key="sync-1", receivable_id="RCV-A",
                  amount_fen=42_000_000, day=1)
    assert refused["status"] == "REFUSED"
    res = _op(c, AGENT, kind="REQUEST_OWNER_APPROVAL", op_id="ask-1", idempotency_key="ask-1", payload_op_id="sync-1",
              subject="Routine ledger sync with the bank statement (no payment, no borrowing)")
    assert res["status"] == "PENDING_APPROVAL"
    [approval] = rt.store.approvals()
    assert "Routine ledger sync" not in approval.reason and "no payment" not in approval.reason
    assert "receipt of ¥420,000.00 on RCV-A reported by AGENT" in approval.reason
    assert rt.store.get_state().cash_fen == 40_000_000


def test_an_operation_the_owner_cannot_approve_is_not_queued(api):
    rt, c = api
    assert _op(c, AGENT, kind="DRAW_FACILITY", op_id="d-1", idempotency_key="d-1", facility_id="FAC-LINE",
               amount_fen=10_000_000, day=1)["status"] == "REFUSED"  # misdated; a plain draw is Tier 1, not Tier 2
    res = _op(c, AGENT, kind="REQUEST_OWNER_APPROVAL", op_id="ask-2", idempotency_key="ask-2", payload_op_id="d-1",
              subject="please approve")
    assert res["status"] == "REFUSED" and not rt.store.approvals()


def test_admission_counts_the_cash_a_line_draw_brings(api):
    rt, _ = api
    state = rt.store.get_state()
    line = next(f for f in state.facilities if f.id == "FAC-LINE")
    op = DrawFacility(op_id="x", idempotency_key="x", mandate_version=1, requested_by=Actor.AGENT, day=0,
                      facility_id="FAC-LINE", amount_fen=15_000_000)
    carried = _as_carried(op, state)
    assert carried is not None
    landed_now = 15_000_000 if line.lead_time_days == 0 else 0
    assert carried.cash_fen == state.cash_fen + landed_now
    assert sum(lot.remaining_fen for lot in carried.lots if lot.facility_id == "FAC-LINE") == 15_000_000


def test_a_recreated_chat_session_does_not_reuse_old_keys(api):
    rt, c = api

    def say(text):
        r = c.post("/nl", headers=OWNER, json={"session_id": "owner-phone", "actor": "OWNER", "text": text})
        assert r.status_code == 200, r.text
        return r.json()

    first = say("draw ¥50,000 on the credit line")
    assert [o["status"] for o in first["operations"]] == ["EXECUTED"]
    reset_sessions()  # the session is lost (expiry, reset or restart); the log is not
    c.post("/clock/advance", headers=OWNER, json={"to_day": 5})
    again = say("draw ¥50,000 on the credit line")
    assert [o["status"] for o in again["operations"]] == ["EXECUTED"]
    assert next(f for f in rt.store.get_state().facilities if f.id == "FAC-LINE").drawn_fen == 10_000_000
    assert not [e for e in rt.store.security_events() if e.kind.value == "REPLAY"]
