"""H: an early-payment agreement can be accepted on an invoice that is already FINANCED. The projection books the
early receipt as the owner's cash; the executor sends the whole receipt to the lender (it is smaller than the
advance and not final). Projection and books diverge."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _harness import *  # noqa: E402,F403

rt, c = fresh()
ADV = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000
res = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-a", "requested_by": "AGENT",
                    "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": ADV})
print("finance:", res["status"], res["message"][:200])
snap(rt, "after finance")
r = c.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"})
oid = r.json()["offer"]["offer_id"]
v = c.post(f"/offers/{oid}/evaluate", headers=OWNER, json={"fixture_id": "EX02_EARLY_1_5"}).json()
print("verdict", v["outcome"], [(k["label"], [(o["type"], o.get("rate_bp"), o["base"].get("amount_fen"), o.get("effective_day")) for o in k["obligations"]]) for k in v["counters"]])
print("violations", [(x["code"], x["message"][:120]) for x in v.get("violations", [])])
n = c.post(f"/negotiate/{oid}", headers=OWNER, json={"buyer_profile": "cooperative"}).json()
print("negotiate", n.get("outcome"), n.get("accepted_counter_id"))
for o in n.get("operations", []):
    print("   op", o["kind"], o["status"], o["message"][:200])
snap(rt, "after negotiate")
print("commitments", [(x.id, x.status.value, [(o.type.value, o.base.receivable_id, o.base.amount_fen, o.rate_bp, o.effective_day) for o in x.obligations]) for x in rt.store.commitments()])
t = projection(rt)
print("projected closings d0..d13:", [closing(t, d) for d in range(0, 14)])
print("projected min:", min(p.closing_fen for p in t.days), "floor", rt.store.get_mandate().min_cash_fen)
diffs = live(c, rt, t, 14)
print("diffs (day, projected, actual):", diffs[:6])
snap(rt, "day 14")
print("lots", lots(rt))
print("conservation", conservation(rt))
check("projection and actual cash diverge after an early receipt on a financed invoice", bool(diffs))
check("actual cash fell below the reserve the projection promised", any(a < rt.store.get_mandate().min_cash_fen <= p for _, p, a in diffs))
