"""Can the orphan PROPOSED commitment be activated beside the owner's ACTIVE agreement (double booking)?"""
import json
exec(open(__file__.replace("repro3.py", "repro2.py")).read().split('print("=== D')[0])
rt, c = fresh()
oid = c.post("/offers", json={"fixture_id": ZHUHAI}, headers=OWNER).json()["offer"]["offer_id"]
v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": ZHUHAI}, headers=OWNER).json()
for i in range(3):
    c.post("/operations", headers=AGENT, json={"kind": "COUNTER_OFFER", "op_id": f"x{i}", "idempotency_key": "x", "mandate_version": 1,
                                             "requested_by": "AGENT", "offer_id": oid, "counter_id": "CTR-none"})
body = {"verdict_id": v["id"], "state_version": v["state_version"]}
c.post(f"/offers/{oid}/accept", headers=OWNER, json=body)
cp = rt.store.get_offer(oid).counterparty_id
c.post(f"/circuit/{cp}/reset", headers=OWNER)
print("owner accept", c.post(f"/offers/{oid}/accept", headers=OWNER, json=body).status_code)
led = c.get("/ledger", headers=OWNER).json()["commitments"]
orphan = next(x for x in led if x["offer_id"] == oid and x["status"] == "PROPOSED")
print("ledger exposes nonce to owner:", "nonce" in orphan)
fc0 = [(f.commitment_id[:14], f.value_fen) for f in rt.store.get_state().forward_concessions]
for who, hdr in (("AGENT", AGENT),):
    r = c.post("/operations", headers=hdr, json={"kind": "ACCEPT_OFFER", "op_id": "dbl", "idempotency_key": "dbl", "mandate_version": 1,
                                               "requested_by": who, "offer_id": oid, "offer_version": 1, "source_verdict_id": v["id"],
                                               "terms_hash": orphan["terms_hash"], "nonce": orphan.get("nonce", "?")})
    res = r.json()["result"]; print(who, "accept orphan ->", res["status"], res.get("approval_id"), res["message"][:200])
    if res.get("approval_id"):
        r = c.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"})
        res = r.json()["result"]; print("owner approves in /approvals ->", res["status"], res["message"][:300])
print("commitments", [(x.id[:14], x.status.value) for x in rt.store.commitments() if x.offer_id == oid])
print("forward concessions before", fc0)
print("forward concessions after ", [(f.commitment_id[:14], f.value_fen) for f in rt.store.get_state().forward_concessions])
print("adjustments", [(a.id[:40]) for a in rt.store.get_state().invoice_adjustments])
