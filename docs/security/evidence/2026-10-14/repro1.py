"""Accept/decline adversarial repros (in-process, memory store)."""
import json, sys
from fastapi.testclient import TestClient
from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
ZHUHAI, DONGGUAN = "EX09_TERMS_BUYER3", "EX08B_JOINT_BUYER2"


def fresh():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()
    from app.main import app
    c = TestClient(app)
    assert c.post("/demo/reset", params={"scenario": "busy"}, headers=OWNER).status_code == 200
    return rt, c


def evaluate(c, fx):
    oid = c.post("/offers", json={"fixture_id": fx}, headers=OWNER).json()["offer"]["offer_id"]
    v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": fx}, headers=OWNER).json()
    return oid, v


def snap(rt):
    return {"commitments": [(x.id[:14], x.status.value) for x in rt.store.commitments()],
            "approvals": [(a.id, str(getattr(a.status, "value", a.status))) for a in rt.store.approvals()],
            "ops": len(rt.store.operations()), "state_version": rt.store.get_state().state_version,
            "sec": len(rt.store.security_events())}


print("=== A: agent opens a buyer's circuit; owner accept leaves an orphan PROPOSED commitment ===")
rt, c = fresh()
oid, v = evaluate(c, ZHUHAI)
print("verdict", v["id"], v["outcome"], "sv", v["state_version"])
for i in range(3):
    r = c.post("/operations", headers=AGENT, json={"kind": "COUNTER_OFFER", "op_id": f"x{i}", "idempotency_key": "x",
                                                   "mandate_version": 1, "requested_by": "AGENT", "offer_id": oid, "counter_id": "CTR-none"})
    print("agent counter", r.status_code, r.json().get("result", {}).get("status") if r.status_code == 200 else r.text[:200])
before = snap(rt)
print("before", before)
body = {"verdict_id": v["id"], "state_version": v["state_version"]}
for n in range(2):
    r = c.post(f"/offers/{oid}/accept", headers=OWNER, json=body)
    print("owner accept", r.status_code, r.json()["detail"]["code"] if r.status_code != 200 else "OK",
          (r.json()["detail"].get("reason_text") or "")[:120] if r.status_code != 200 else "")
r = c.post(f"/offers/{oid}/decline", headers=OWNER, json=body)
print("owner decline", r.status_code, r.json()["detail"]["code"] if r.status_code != 200 else "OK")
print("after ", snap(rt))
r = c.get(f"/offers/{oid}/picture", headers=OWNER).json()["accept"]
print("picture accept block available:", r["available"], r["reason_text"])

print("\n=== B: agent pre-claims the deterministic decline idempotency key ===")
rt, c = fresh()
oid, v = evaluate(c, DONGGUAN)
key = f"decline-{oid}-{v['id']}"
r = c.post("/operations", headers=AGENT, json={"kind": "REJECT_OFFER", "op_id": key, "idempotency_key": key, "mandate_version": 1,
                                               "requested_by": "OWNER", "offer_id": oid, "reason_codes": []})
print("agent RejectOffer under owner's key:", r.status_code, r.json()["result"]["status"])
before = snap(rt)
r = c.post(f"/offers/{oid}/decline", headers=OWNER, json={"verdict_id": v["id"], "state_version": v["state_version"]})
d = r.json().get("detail", {})
print("owner decline:", r.status_code, d.get("code"), (d.get("reason_text") or "")[:160])
print("before", before); print("after ", snap(rt))
print("last sec event:", rt.store.security_events()[-1].kind, rt.store.security_events()[-1].detail[:160])
r = c.get(f"/decisions/deal:{oid}", headers=OWNER).json()
print("decision state", r.get("state"))

print("\n=== C: agent cannot decide; double decide ===")
rt, c = fresh()
oid, v = evaluate(c, ZHUHAI)
cm = rt.executor.propose_commitment(v["id"], expires_day=rt.day + 7)
r = c.post("/operations", headers=AGENT, json={"kind": "ACCEPT_OFFER", "op_id": "ag", "idempotency_key": "ag", "mandate_version": 1,
                                               "requested_by": "AGENT", "offer_id": oid, "offer_version": 1, "source_verdict_id": v["id"],
                                               "terms_hash": cm.terms_hash, "nonce": cm.nonce})
aid = r.json()["result"]["approval_id"]; print("agent accept ->", r.json()["result"]["status"], aid)
r = c.post(f"/approvals/{aid}", headers=AGENT, json={"decision": "APPROVE"}); print("agent approve ->", r.status_code, r.json()["result"]["status"])
r = c.post(f"/approvals/{aid}", headers=OWNER, json={"decision": "APPROVE"}); print("owner approve ->", r.status_code, r.json()["result"]["status"])
r = c.post(f"/approvals/{aid}", headers=OWNER, json={"decision": "APPROVE"}); print("owner approve again ->", r.status_code, r.text[:100])
