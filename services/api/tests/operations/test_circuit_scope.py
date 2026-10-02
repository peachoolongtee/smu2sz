"""Red team 3 Oct: the circuit breaker stops a counterparty's refused offers; it must never block a bank receipt,
and a refusal must not burn an idempotency key."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import Settings
from app.main import app
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {**AGENT, "X-Bank-Feed-Key": "demo-bank-feed-key"}


@pytest.fixture
def api():
    rt = Runtime(Settings(), InMemoryLedgerStore(), demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    yield rt, TestClient(app)
    set_runtime(None)


def post(c, key, headers, actor, **fields):
    r = c.post("/operations", headers=headers, json={"kind": "RECEIVE_PAYMENT", "op_id": key, "idempotency_key": key,
                                                     "mandate_version": 1, "requested_by": actor, **fields})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def test_agent_refusals_cannot_block_the_bank_feed(api):
    rt, c = api
    for i in range(4):  # misdated agent receipts on the buyer's invoice: each is refused
        res = post(c, f"junk-{i}", AGENT, "AGENT", receivable_id="RCV-A", amount_fen=100, day=1)
        assert res["status"] == "REFUSED"
    assert rt.executor.circuit_open("BUYER-1") is False
    res = post(c, "bank-1", BANK, "SYSTEM", receivable_id="RCV-A", amount_fen=42_000_000)
    assert res["status"] == "EXECUTED"
    assert rt.store.get_state().cash_fen == 40_000_000 + 42_000_000


def test_a_refused_key_can_run_again(api):
    rt, c = api
    assert post(c, "bank-2", BANK, "SYSTEM", receivable_id="RCV-A", amount_fen=42_000_000, day=1)["status"] == "REFUSED"
    res = post(c, "bank-2", BANK, "SYSTEM", receivable_id="RCV-A", amount_fen=42_000_000)
    assert res["status"] == "EXECUTED"
    again = post(c, "bank-2", BANK, "SYSTEM", receivable_id="RCV-A", amount_fen=42_000_000)
    assert again["status"] == "DUPLICATE"
    assert rt.store.get_state().cash_fen == 40_000_000 + 42_000_000
