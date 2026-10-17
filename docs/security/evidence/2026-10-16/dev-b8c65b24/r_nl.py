import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from app.operations.log import read_entries
rt, api, app = fresh()
oid, v, m = sent(api)
def ops():
    e,_ = read_entries(rt.store.operations()); return [(x.kind, x.result.status.value, x.payload.get("requested_by"), x.payload.get("offer_id")) for x in e]
r = api.post(f"/negotiate/{oid}", json={"verdict_id": v["id"], "counter_id": m["counter_id"], "state_version": rt.store.get_state().state_version})
print("negotiate:", r.status_code, r.text[:140])
ctx = {"page": "/deals", "offer_id": oid, "decision_id": v["id"]}
r1 = api.post("/nl", json={"text": "send the counter to the buyer", "context": ctx}).json()
sid = r1["session_id"]; print("t1", r1["intent"], r1["reply"][:200])
for t in ("yes, go ahead", "confirm", "do it"):
    r2 = api.post("/nl", json={"session_id": sid, "text": t, "context": ctx}).json()
    print("t2", t, r2["intent"], r2["reply"][:200], [(p.get("kind"), p.get("status")) for p in r2.get("plan", [])])
print("ops:", ops())
d = decision(api, oid); print("state:", d["state"], [h["kind"] for h in d["history"]])
print("commitments:", [(c.id, c.offer_id, c.status.value) for c in rt.store.commitments()])
