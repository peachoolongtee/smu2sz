"""OUT-1b (security register): the raw operations route refuses to answer a request the owner sent a counter on themself.

OUT-1 closed the chat paths and the accept, decline and simulated-buyer routes. `POST /operations` still handed RejectOffer and CounterOffer
from the owner token or the agent key straight to the executor, which ran them (EXECUTED), so the deal's log contradicted the owner's own
letter (Security Lead, 17 Oct, on 719c9dcf). It now answers 409 OFFER_SENT_OUTSIDE before the executor, as the other paths do."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
OFFER_KINDS = ("ACCEPT_OFFER", "REJECT_OFFER", "COUNTER_OFFER")


@pytest.fixture
def env():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield rt, TestClient(app)
    set_runtime(None)


def _evaluated(c: TestClient) -> tuple[str, dict[str, Any]]:
    oid = c.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}, headers=OWNER).json()["offer"]["offer_id"]
    return oid, c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX02_EARLY_1_5"}, headers=OWNER).json()


def _marked(c: TestClient) -> tuple[str, dict[str, Any]]:
    """The owner copies Option A's message and marks it sent outside FLOW (POST .../offered)."""
    oid, v = _evaluated(c)
    cid = v["counters"][0]["id"]
    m = c.get(f"/offers/{oid}/counters/{cid}/message", params={"lang": "en"}, headers=OWNER).json()
    r = c.post(f"/offers/{oid}/counters/{cid}/offered", headers=OWNER,
               json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": m["message_hash"], "lang": "en"})
    assert r.status_code == 200, r.text
    return oid, v


def _body(rt: Runtime, kind: str, oid: str, v: dict[str, Any], who: str) -> dict[str, Any]:
    key = f"probe-{kind}-{who}"
    base = {"kind": kind, "op_id": key, "idempotency_key": key, "requested_by": who.upper(), "day": rt.day,
            "mandate_version": rt.store.get_mandate().version, "source_verdict_id": v["id"], "offer_id": oid}
    if kind == "REJECT_OFFER":
        return {**base, "reason_codes": []}
    if kind == "COUNTER_OFFER":
        return {**base, "counter_id": v["counters"][0]["id"]}
    return {**base, "offer_version": 1, "terms_hash": "t" * 64, "nonce": "n" * 32}  # no proposal exists: refused before the executor


@pytest.mark.parametrize("who", ["owner", "agent"])
@pytest.mark.parametrize("kind", OFFER_KINDS)
def test_the_raw_route_does_not_answer_a_request_sent_outside(env, who: str, kind: str) -> None:
    rt, c = env
    oid, v = _marked(c)
    before = len(rt.store.operations())
    r = c.post("/operations", json=_body(rt, kind, oid, v, who), headers=OWNER if who == "owner" else AGENT)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "OFFER_SENT_OUTSIDE"
    assert len(rt.store.operations()) == before  # nothing reached the executor, nothing logged
    assert not [o for o in rt.store.operations() if o.kind in OFFER_KINDS]


def test_the_refusal_follows_the_language(env) -> None:
    rt, c = env
    oid, v = _marked(c)
    r = c.post("/operations", params={"lang": "zh"}, json=_body(rt, "REJECT_OFFER", oid, v, "owner"), headers=OWNER)
    assert r.status_code == 409 and r.json()["detail"]["message"] == "您已亲自向买方发出还价；请改为在这笔交易上记录对方的答复。"


def test_a_request_not_sent_outside_is_still_answered(env) -> None:
    rt, c = env
    oid, v = _evaluated(c)
    r = c.post("/operations", json=_body(rt, "REJECT_OFFER", oid, v, "owner"), headers=OWNER)
    assert r.status_code == 200 and r.json()["result"]["status"] == "EXECUTED"
