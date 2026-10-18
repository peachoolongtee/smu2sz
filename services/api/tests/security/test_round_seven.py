"""Round seven (Security Lead review of dev 5941e95a, 18 Oct).

PAUSE-1: the owner's pause exempted every SYSTEM caller, and anyone holding the bank-feed key could speak as SYSTEM for any kind, so the
bank-feed key could still draw a line or finance an invoice while the agent was paused. The bank feed now speaks as SYSTEM only to
report a receipt, and the pause exempts SYSTEM only for receipts.
APR-1: an agent key posting a decision to /approvals/{id} was told the owner's decision on that approval in the owner's words."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


@pytest.fixture
def client():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def op(kind: str, key: str, by: str, **kw) -> dict:
    return {"kind": kind, "op_id": key, "idempotency_key": key, "mandate_version": get_runtime().store.get_mandate().version,
            "requested_by": by, **kw}


def test_the_bank_feed_key_cannot_borrow_while_the_agent_is_paused(client):
    assert client.post("/agent/pause", headers=OWNER, json={}).status_code == 200
    drawn = sum(f.drawn_fen for f in get_runtime().store.get_state().facilities)
    r = client.post("/operations", headers=BANK, json=op("DRAW_FACILITY", "p1-draw", "SYSTEM", facility_id="FAC-LINE",
                                                          amount_fen=1_000_000)).json()["result"]
    assert r["status"] == "REFUSED", r
    assert sum(f.drawn_fen for f in get_runtime().store.get_state().facilities) == drawn


def test_the_bank_feed_speaks_as_system_only_for_a_receipt(client):
    r = client.post("/operations", headers=BANK, json=op("DRAW_FACILITY", "p1-draw2", "SYSTEM", facility_id="FAC-LINE",
                                                          amount_fen=1_000_000)).json()["result"]
    entry = get_runtime().store.operations()[-1]
    assert '"requested_by":"AGENT"' in entry.payload_json, entry.payload_json  # the draw is the agent's, at the agent's tier
    rec = next(x for x in get_runtime().store.get_state().receivables if x.status == "OPEN")
    ok = client.post("/operations", headers=BANK, json=op("RECEIVE_PAYMENT", "p1-rcpt", "SYSTEM", receivable_id=rec.id,
                                                          amount_fen=100_00, bank_reference="BANK-R7")).json()["result"]
    assert ok["status"] == "EXECUTED" and ok["tier"] == "TIER_1", (r, ok)


def test_a_receipt_from_the_bank_feed_still_runs_while_paused(client):
    client.post("/agent/pause", headers=OWNER, json={})
    rec = next(x for x in get_runtime().store.get_state().receivables if x.status == "OPEN")
    ok = client.post("/operations", headers=BANK, json=op("RECEIVE_PAYMENT", "p1-rcpt2", "SYSTEM", receivable_id=rec.id,
                                                          amount_fen=100_00, bank_reference="BANK-R7b")).json()["result"]
    assert ok["status"] == "EXECUTED"


def test_the_agent_key_is_not_told_the_owners_decision(client):
    q = client.post("/operations", headers=AGENT, json=op("APPLY_FOR_FACILITY", "a1-apply", "AGENT", facility_id="FAC-GGL",
                                                          amount_fen=20_000_000)).json()["result"]
    aid = q["approval_id"]
    assert client.post(f"/approvals/{aid}", headers=OWNER, json={"decision": "APPROVE"}).status_code == 200
    r = client.post(f"/approvals/{aid}", headers=AGENT, json={"decision": "APPROVE"})
    body = r.json()
    if r.status_code == 200:
        assert body["approval"]["decision"] is None and body["approval"]["ran"] is False, body
        assert "approved" not in body["approval"]["text"].lower()
    else:
        assert "APPROVED" not in r.text
