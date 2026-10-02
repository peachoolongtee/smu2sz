"""Exploration: what custom buyer texts compile to (cache backend + rules) and what the verifier says."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _harness import *  # noqa: E402,F403

TEXTS = sys.argv[1:] or [
    "Please take 2% off invoice RCV-A.",
    "We will pay invoice RCV-A early at 0.5% and want 1% off the next invoice.",
    "Give us 3% off the next invoice.",
    "Take 50% off invoice RCV-A.",
]
rt, c = fresh()
for i, text in enumerate(TEXTS):
    doc = {"doc_id": f"DOC-{i}", "channel": "email", "sender_id": "BUYER-1", "received_day": 0, "text": text}
    r = c.post("/offers", json={"documents": [doc], "counterparty_id": "BUYER-1"})
    if r.status_code != 200:
        print("offer", r.status_code, r.text[:300])
        continue
    off = r.json()["offer"]
    print("==", text)
    print("   compiled", off["status"], off.get("compiler"), [(o["type"], o.get("rate_bp"), o.get("amount_fen"), o["base"].get("receivable_id"), o["duration"]["kind"]) for o in off["obligations"]])
    v = c.post(f"/offers/{off['offer_id']}/evaluate", headers=OWNER, json={}).json()
    print("   verdict", v["outcome"], v.get("required_tier"), "fwd", v.get("forward_concession"), [(x["code"], x["message"][:100]) for x in v.get("violations", [])])
    for o in v["bound_obligations"]:
        print("   bound", o["type"], o.get("rate_bp"), o["base"].get("receivable_id"), o["base"].get("amount_fen"), o["duration"]["kind"], o.get("effective_day"))
    for k in v["counters"]:
        print("   counter", k["label"], k.get("forward_value_fen"), k.get("supplier_cost_fen"), [(o["type"], o.get("rate_bp"), o["base"].get("receivable_id"), o["duration"]["kind"]) for o in k["obligations"]])
    print("   concession values", [(x.get("obligation_id"), x.get("value_fen")) for x in v.get("concession_values", [])])
