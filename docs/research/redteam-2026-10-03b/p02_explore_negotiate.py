"""Explore: EX02 evaluated and negotiated by the owner console; what the agent then executes."""
import json

from _harness import *  # noqa: F403

rt, c = fresh()
r = c.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"})
offer_id = r.json()["offer"]["offer_id"]
v = c.post(f"/offers/{offer_id}/evaluate", headers=OWNER, json={"fixture_id": "EX02_EARLY_1_5"}).json()
print("verdict", v["outcome"], [(k["id"], k["label"], k.get("text", "")[:120]) for k in v["counters"]])
n = c.post(f"/negotiate/{offer_id}", headers=OWNER, json={"buyer_profile": "cooperative"}).json()
print("negotiate", n["outcome"], n["accepted_counter_id"], n["message"])
for o in n["operations"]:
    print("  op", o["kind"], o["status"], o["message"][:200])
print("plan", json.dumps(n["plan"].get("actions"), ensure_ascii=False)[:600])
for cm in rt.store.commitments():
    print("commitment", cm.id, cm.status.value, [(o.type.value, o.base.receivable_id, o.base.amount_fen, o.rate_bp,
                                                 o.effective_day) for o in cm.obligations])
snap(rt, "after negotiate")
print(lots(rt))
