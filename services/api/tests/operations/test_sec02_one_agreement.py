"""SEC-02 / SEC-03 (security register, 14 Oct): one buyer request carries at most one live agreement.

The executor's exclusivity covered only obligations naming a receivable, so a request whose obligations name none (payment terms on the next
invoice) could be accepted twice: two ACTIVE commitments, the forward concession and the invoice adjustment booked twice. A refused owner accept
also left a fresh PROPOSED commitment behind on every attempt, the raw material for the second agreement."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import CommitmentStatus
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
ZHUHAI = "EX09_TERMS_BUYER3"  # a terms request whose obligations name no receivable


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


def _evaluate(c: TestClient) -> tuple[str, dict]:
    oid = c.post("/offers", json={"fixture_id": ZHUHAI}, headers=OWNER).json()["offer"]["offer_id"]
    v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": ZHUHAI}, headers=OWNER).json()
    return oid, v


def _live(rt: Runtime, oid: str) -> list:
    return [x for x in rt.store.commitments() if x.offer_id == oid and x.status in (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)]


def test_a_second_agreement_for_the_same_request_is_refused_even_when_the_owner_approves_it(env):
    rt, c = env
    oid, v = _evaluate(c)
    body = {"verdict_id": v["id"], "state_version": v["state_version"]}
    assert c.post(f"/offers/{oid}/accept", headers=OWNER, json=body).status_code == 200
    assert len(_live(rt, oid)) == 1
    fc_before = list(rt.store.get_state().forward_concessions)

    other = rt.executor.propose_commitment(v["id"], expires_day=rt.day + 7)  # a second proposal for the same request
    r = c.post("/operations", headers=AGENT, json={
        "kind": "ACCEPT_OFFER", "op_id": "dbl", "idempotency_key": "dbl", "mandate_version": 1, "requested_by": "AGENT", "offer_id": oid,
        "offer_version": 1, "source_verdict_id": v["id"], "terms_hash": other.terms_hash, "nonce": other.nonce}).json()["result"]
    if r["status"] == "PENDING_APPROVAL":
        r = c.post(f"/approvals/{r['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
    assert r["status"] == "REFUSED"
    assert any(x["code"] == "CONFLICTING_COMMITMENT" for x in r["violations"])
    assert len(_live(rt, oid)) == 1
    assert rt.store.get_state().forward_concessions == fc_before


def test_refused_owner_accepts_do_not_pile_up_proposals_and_a_later_accept_leaves_none_behind(env):
    rt, c = env
    oid, v = _evaluate(c)
    for i in range(3):  # three refused agent ops open the buyer's circuit, so the owner's accept is refused after it proposed
        c.post("/operations", headers=AGENT, json={"kind": "COUNTER_OFFER", "op_id": f"x{i}", "idempotency_key": f"x{i}", "mandate_version": 1,
                                                 "requested_by": "AGENT", "offer_id": oid, "counter_id": "CTR-none"})
    body = {"verdict_id": v["id"], "state_version": v["state_version"]}
    refused = [c.post(f"/offers/{oid}/accept", headers=OWNER, json=body).status_code for _ in range(2)]
    proposed = [x for x in rt.store.commitments() if x.offer_id == oid and x.status == CommitmentStatus.PROPOSED]
    if refused == [409, 409]:
        assert len(proposed) <= 1
    cp = rt.store.get_offer(oid).counterparty_id
    c.post(f"/circuit/{cp}/reset", headers=OWNER)
    assert c.post(f"/offers/{oid}/accept", headers=OWNER, json=body).status_code == 200
    assert len(_live(rt, oid)) == 1
    assert not [x for x in rt.store.commitments() if x.offer_id == oid and x.status == CommitmentStatus.PROPOSED]
