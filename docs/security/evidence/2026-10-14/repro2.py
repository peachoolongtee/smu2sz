"""Orphan aftermath, clock by bank feed key, demo routes under DEMO_MODE=0."""
import os
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


def fresh(scn="busy"):
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()
    from app.main import app
    c = TestClient(app)
    assert c.post("/demo/reset", params={"scenario": scn}, headers=OWNER).status_code == 200
    return rt, c


print("=== D: orphan PROPOSED commitments after a later successful accept ===")
rt, c = fresh()
oid = c.post("/offers", json={"fixture_id": ZHUHAI}, headers=OWNER).json()["offer"]["offer_id"]
v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": ZHUHAI}, headers=OWNER).json()
for i in range(3):
    c.post("/operations", headers=AGENT, json={"kind": "COUNTER_OFFER", "op_id": f"x{i}", "idempotency_key": "x", "mandate_version": 1,
                                             "requested_by": "AGENT", "offer_id": oid, "counter_id": "CTR-none"})
body = {"verdict_id": v["id"], "state_version": v["state_version"]}
print("accept #1", c.post(f"/offers/{oid}/accept", headers=OWNER, json=body).status_code)
cp = rt.store.get_offer(oid).counterparty_id
print("reset circuit", c.post(f"/circuit/{cp}/reset", headers=OWNER).json()["result"]["status"])
r = c.post(f"/offers/{oid}/accept", headers=OWNER, json=body)
print("accept #2", r.status_code)
print("commitments", [(x.id[:14], x.status.value, x.expires_day) for x in rt.store.commitments() if x.offer_id == oid])
r = c.post("/clock/advance", headers=OWNER, json={"days": 4})
al = c.get("/alerts", headers=OWNER).json()
print("expiry alerts:", [(a["id"][:28], a["title"]) for a in al["alerts"] if "EXPIRY" in a["id"]])

print("\n=== E: bank-feed key alone moves the clock arbitrarily far ===")
rt, c = fresh()
m = rt.store.get_mandate()
print("mandate expires_day", m.expires_day, "day", rt.day)
r = c.post("/operations", headers=BANK, json={})
print("bank key on /operations:", r.status_code)
for _ in range(3):
    r = c.post("/clock/advance", headers=BANK, json={"days": 366})
    print("advance", r.status_code, "day", r.json().get("day"))
last = rt.store.operations()[-1]
print("log kind", last.kind, "requested_by in payload:", '"actor"' in last.payload_json or last.payload_json[:160])
print("expired commitments:", sum(1 for x in rt.store.commitments() if x.status.value == "EXPIRED"))
from app.mandate import MandatePolicyImpl
print("mandate validity now:", [str(v.code) for v in (MandatePolicyImpl(trusted_public_key_hex=rt.owner_key_hex).check_validity(m, rt.day, m.version) or [])])
r = c.post("/operations", headers=AGENT, json={"kind": "REJECT_OFFER", "op_id": "z", "idempotency_key": "z", "mandate_version": 1,
                                             "requested_by": "AGENT", "offer_id": "OFF-x", "reason_codes": []})
print("agent op after advance:", r.json()["result"]["status"], r.json()["result"]["violations"][0]["code"] if r.json()["result"]["violations"] else "")
