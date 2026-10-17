import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from app.operations.log import read_entries
rt, api, app = fresh()
oid, v, m = sent(api)
cash = set_cash(rt, 1)
r = accepted(api, oid, v, m, rt); print("yes:", r.status_code, r.json()["detail"]["code"])
d = decision(api, oid); print("after refused yes:", d["state"], d["terminal"], (d.get("outbound") or {}).get("answer"))
w = api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered/withdraw", json={"verdict_id": v["id"], "message_hash": m["message_hash"]})
print("withdraw:", w.status_code, w.json().get("status"), w.json().get("message_when"))
d = decision(api, oid)
print("after withdraw:", d["state"], "terminal", d["terminal"], "state_text:", d.get("state_text"), "outbound:", d.get("outbound"))
print("waiting:", d.get("waiting"))
print("history:", [h["kind"] for h in d["history"]])
print("commitments:", [(c.id, c.status.value, c.expires_day) for c in rt.store.commitments()])
ents,_ = read_entries(rt.store.operations()); print("ops:", [(e.kind, e.result.status.value, e.payload.get("op_id")) for e in ents])
print("facts:", [(f.fact, f.fact_key) for f in rt.store.decision_facts(f"deal:{oid}")])
print("approvals:", [(a.id, a.status) for a in rt.store.approvals()])
print("worklist/deals entries mention:", [x for x in api.get("/decisions").json().get("decisions", []) if x.get("id")==f"deal:{oid}"][:1])
# can owner continue?
set_cash(rt, cash)
v2 = api.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX02_EARLY_1_5"}).json()
print("re-evaluate:", v2.get("id"), v2.get("state_version"))
mm = api.get(f"/offers/{oid}/counters/{v2['counters'][0]['id']}/message")
print("message again:", mm.status_code, (mm.json().get("detail") or {}).get("code") if mm.status_code!=200 else mm.json()["blocked"])
if mm.status_code == 200:
    m2 = mm.json(); o2 = offered(api, oid, v2, m2); print("re-mark:", o2.status_code, o2.text[:200] if o2.status_code!=200 else "ok")
    d = decision(api, oid); print("after re-mark:", d["state"], d["outbound"]["answer"] if d.get("outbound") else None, d["outbound"].get("refusal_text") if d.get("outbound") else None)
    a2 = accepted(api, oid, v2, m2, rt); print("yes2:", a2.status_code, a2.json().get("status") if a2.status_code==200 else a2.text[:200])
    print("commitments:", [(c.id, c.status.value) for c in rt.store.commitments()])
# accept as asked path
acc = api.post(f"/offers/{oid}/accept", json={"verdict_id": v2["id"], "state_version": rt.store.get_state().state_version})
print("accept-as-asked:", acc.status_code, acc.text[:200])
