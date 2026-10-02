"""Exploration: what each fixture offer compiles to and what the verifier says on day 0."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _harness import *  # noqa: E402,F403

rt, c = fresh()
for fx in ["EX01_PACKAGE", "EX01B_REWORDED", "EX02_EARLY_1_5", "EX05_CONSOLIDATE", "EX06_THREE_INVOICES",
           "EX08A_JOINT_BUYER1", "EX08B_JOINT_BUYER2"]:
    r = c.post("/offers", json={"fixture_id": fx})
    off = r.json()["offer"]
    v = c.post(f"/offers/{off['offer_id']}/evaluate", headers=OWNER, json={"fixture_id": fx}).json()
    print("==", fx, off["offer_id"], off["counterparty_id"], "outcome", v["outcome"], "tier", v.get("required_tier"))
    for o in v["bound_obligations"]:
        print("   ob", o["id"], o["type"], o.get("rate_bp"), o.get("amount_fen"), o.get("days_delta"),
              o["base"].get("receivable_id"), o["base"].get("amount_fen"), o["duration"], o.get("effective_day"),
              o["contingency"])
    for k in v["counters"]:
        print("   counter", k["id"], k["label"], k.get("forward_value_fen"), k.get("supplier_cost_fen"),
              [(o["type"], o.get("rate_bp"), o.get("days_delta"), o["base"].get("receivable_id"),
                o["duration"]["kind"]) for o in k["obligations"]])
