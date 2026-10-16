import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from app.operations.log import read_entries
rt, api, app = fresh()
oid, v, m = sent(api)
agent = TestClient(app, headers={"X-Agent-Key": AGENT})
def ops(): 
    e,_ = read_entries(rt.store.operations()); return [(x.kind, x.result.status.value, x.payload.get("requested_by"), x.payload.get("offer_id")) for x in e]
for who, c in (("agent", agent), ("owner", api)):
    for text in ("accept this offer", "accept the buyer's request as asked", "send the counter to the buyer", "decline this offer"):
        r = c.post("/nl", json={"text": text, "context": {"page": "/deals", "offer_id": oid, "decision_id": v["id"]}})
        print(who, text, "->", r.status_code, r.json().get("intent") if r.status_code==200 else r.text[:100], [ (p.get("kind"), p.get("status")) for p in r.json().get("plan", [])] if r.status_code==200 else "")
print("ops:", ops())
d = decision(api, oid); print("state:", d["state"], "history:", [h["kind"] for h in d["history"]])
# simulated negotiate while awaiting
r = api.post(f"/offers/{oid}/negotiate", json={"verdict_id": v["id"], "counter_id": m["counter_id"], "state_version": rt.store.get_state().state_version})
print("negotiate:", r.status_code, r.text[:120])
# history before withdraw after refused yes
cash = set_cash(rt, 1)
print("refused yes:", accepted(api, oid, v, m, rt).status_code)
d = decision(api, oid); print("awaiting after refused yes; history:", [h["kind"] for h in d["history"]], "accepted_as_asked text:", [h["text"] for h in d["history"] if h["kind"]=="accepted_as_asked"])
set_cash(rt, cash)
# --- reply doc-id pre-claim by anonymous caller
rt2, api2, app2 = fresh()
oid2, v2, m2 = sent(api2)
offer = rt2.store.get_offer(oid2)
text = "Thanks. Could you do 60-day payment terms on future invoices instead?"
digest = hashlib.sha256(f"{oid2}|{text}".encode()).hexdigest()[:16]
anon = TestClient(app2)
r = anon.post("/offers", json={"counterparty_id": "BUYER-1", "documents": [{"doc_id": f"reply-{digest}", "channel": "email", "sender_id": "BUYER-1", "received_day": rt2.day, "text": text + " "}]})
print("anon preclaim (different doc):", r.status_code)
r = api2.post(f"/offers/{oid2}/buyer-reply", json={"verdict_id": v2["id"], "counter_id": m2["counter_id"], "text": text})
print("owner paste after preclaim:", r.status_code, r.text[:160])
# identical-doc variant
rt3, api3, app3 = fresh()
oid3, v3, m3 = sent(api3)
offer3 = rt3.store.get_offer(oid3)
digest = hashlib.sha256(f"{oid3}|{text}".encode()).hexdigest()[:16]
same = {"doc_id": f"reply-{digest}", "channel": "email", "sender_id": "BUYER-1", "received_day": rt3.day, "text": text, "parent_doc_id": offer3.doc_ids[0]}
r = TestClient(app3).post("/offers", json={"counterparty_id": "BUYER-1", "documents": [same]})
print("anon identical preclaim:", r.status_code, r.json().get("offer", {}).get("offer_id"))
r = api3.post(f"/offers/{oid3}/buyer-reply", json={"verdict_id": v3["id"], "counter_id": m3["counter_id"], "text": text})
print("owner paste after identical preclaim:", r.status_code, r.text[:160])
if r.status_code == 200:
    print("received facts:", [(f.fact_key) for f in rt3.store.decision_facts(f"deal:{r.json()['reply_offer_id']}") if f.fact=="RECEIVED"])
