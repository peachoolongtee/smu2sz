"""Day-by-day: execute the router's plan, then each day do exactly what today's projection says happens today
(buyer receipts by the bank feed, the assumed line repayment by the owner) and check that the closing the
projection showed for today is the cash the books hold the next morning. Conservation of lots is checked too."""
import sys

from _harness import *
from app.domain.models import LedgerEventKind as K

END = int(sys.argv[1]) if len(sys.argv) > 1 else 90
rt, c = fresh()
r = c.post("/router/plan", headers=OWNER).json()["committed"]
for i, a in enumerate(r["actions"]):
    if a["kind"] == "DRAW":
        res = op(c, AGENT, {"kind": "DRAW_FACILITY", "op_id": f"plan-{i}", "requested_by": "AGENT",
                            "facility_id": a["facility_id"], "amount_fen": a["amount_fen"]})
    else:
        res = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": f"plan-{i}", "requested_by": "AGENT",
                            "facility_id": a["facility_id"], "receivable_id": a["receivable_id"],
                            "advance_fen": a["amount_fen"]})
    print(" leg", i, res["status"], res["message"][:160])
snap(rt, "after plan")
diffs = []
while rt.day < END:
    d = rt.day
    t = projection(rt)
    p = next(p for p in t.days if p.day == d)
    for e in p.events:
        if e.kind in (K.RECEIPT, K.EARLY_RECEIPT) and e.ref and e.amount_fen > 0:
            res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": f"rx-{e.ref}-{d}", "requested_by": "SYSTEM",
                               "receivable_id": e.ref, "amount_fen": e.amount_fen})
            print(f"  day {d}: receipt {e.amount_fen} on {e.ref}: {res['status']} {res['message'][:200]}")
    for e in p.events:
        if e.kind == K.REPAYMENT and e.ref == "FAC-LINE":
            res = op(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": f"repay-{d}", "requested_by": "OWNER",
                                "facility_id": "FAC-LINE", "amount_fen": -e.amount_fen})
            print(f"  day {d}: line repay {-e.amount_fen}: {res['status']} {res['message'][:200]}")
        if e.kind == K.REPAYMENT and e.ref == "FAC-IF" and "settled" in (e.formula or ""):
            res = op(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": f"orph-{d}", "requested_by": "OWNER",
                                "facility_id": "FAC-IF", "amount_fen": -e.amount_fen})
            print(f"  day {d}: orphan repay {-e.amount_fen}: {res['status']} {res['message'][:200]}")
    advance(c, d + 1)
    actual = rt.store.get_state().cash_fen
    if actual != p.closing_fen:
        diffs.append((d, p.closing_fen, actual))
        print(f"  DIFF day {d}: projected closing {p.closing_fen} actual {actual} ({actual - p.closing_fen:+d})")
        for e in p.events:
            print("     ev", e.kind.value, e.amount_fen, e.ref, e.label[:80])
    br = conservation(rt)
    if br:
        print("  CONSERVATION", d, br)
snap(rt, "end")
print("chain ok:", rt.store.verify_chain() if hasattr(rt.store, "verify_chain") else "n/a")
check("projected closing differs from actual cash on some day", bool(diffs))
