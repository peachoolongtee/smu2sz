"""Security register, 14 Oct: a credential below the owner's cannot take the owner's decisions away.

SEC-04  the agent key pre-claimed the owner's decline (its idempotency key was predictable), so the owner's decline was refused as a REPLAY.
SEC-05  the agent's own refused offer operations opened a buyer's circuit, which then refused the owner's accept and decline.
SEC-09  the bank-feed key alone moved the clock up to 366 days a call, as often as it liked: it expired the mandate and closed days."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Bank-Feed-Key": "demo-bank-feed-key"}
ZHUHAI = "EX09_TERMS_BUYER3"


@pytest.fixture
def env():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()
    from app.main import app

    c = TestClient(app)
    assert c.post("/demo/reset", params={"scenario": "busy"}, headers=OWNER).status_code == 200
    yield rt, c
    set_runtime(None)


def _evaluate(c: TestClient, fixture: str) -> tuple[str, dict]:
    oid = c.post("/offers", json={"fixture_id": fixture}, headers=OWNER).json()["offer"]["offer_id"]
    return oid, c.post(f"/offers/{oid}/evaluate", json={"fixture_id": fixture}, headers=OWNER).json()


def _trip_circuit_as_agent(c: TestClient, oid: str) -> None:
    for i in range(3):
        r = c.post("/operations", headers=AGENT, json={"kind": "COUNTER_OFFER", "op_id": f"x{i}", "idempotency_key": "x", "mandate_version": 1,
                                                     "requested_by": "AGENT", "offer_id": oid, "counter_id": "CTR-none"})
        assert r.json()["result"]["status"] == "REFUSED"


def test_sec04_the_agent_cannot_preclaim_the_owners_decline(env):
    rt, c = env
    oid, v = _evaluate(c, ZHUHAI)
    key = f"decline-{oid}-{v['id']}"  # the key the route used to build
    c.post("/operations", headers=AGENT, json={"kind": "REJECT_OFFER", "op_id": key, "idempotency_key": key, "mandate_version": 1,
                                             "requested_by": "AGENT", "offer_id": oid, "reason_codes": []})
    r = c.post(f"/offers/{oid}/decline", headers=OWNER, json={"verdict_id": v["id"], "state_version": v["state_version"]})
    assert r.status_code == 200, r.text
    again = c.post(f"/offers/{oid}/decline", headers=OWNER, json={"verdict_id": v["id"], "state_version": v["state_version"]})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ALREADY_DECLINED"  # a second click still changes nothing


def test_sec05_an_agent_tripped_circuit_does_not_take_the_owners_accept(env):
    rt, c = env
    oid, v = _evaluate(c, ZHUHAI)
    _trip_circuit_as_agent(c, oid)
    cp = rt.store.get_offer(oid).counterparty_id
    assert rt.executor.circuit_open(cp)  # the circuit still stops the agent ...
    r = c.post("/operations", headers=AGENT, json={"kind": "REJECT_OFFER", "op_id": "ag-rej", "idempotency_key": "ag-rej", "mandate_version": 1,
                                                 "requested_by": "AGENT", "offer_id": oid, "reason_codes": []}).json()["result"]
    assert r["status"] == "REFUSED" and any(x["code"] == "CIRCUIT_OPEN" for x in r["violations"])
    # ... but the owner deciding is the owner looking: the accept runs
    assert c.post(f"/offers/{oid}/accept", headers=OWNER, json={"verdict_id": v["id"], "state_version": v["state_version"]}).status_code == 200


def test_sec05_an_agent_tripped_circuit_does_not_take_the_owners_decline(env):
    rt, c = env
    oid, v = _evaluate(c, ZHUHAI)
    _trip_circuit_as_agent(c, oid)
    assert c.post(f"/offers/{oid}/decline", headers=OWNER, json={"verdict_id": v["id"], "state_version": v["state_version"]}).status_code == 200


def test_sec09_the_bank_feed_cannot_move_the_clock(env):
    rt, c = env
    day = rt.day
    r = c.post("/clock/advance", headers=BANK, json={"days": 366})
    assert r.status_code == 403
    assert rt.day == day
    assert c.post("/clock/advance", headers=OWNER, json={"days": 1}).status_code == 200
