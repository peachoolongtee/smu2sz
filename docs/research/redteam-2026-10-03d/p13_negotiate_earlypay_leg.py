"""Finding F1 through /negotiate: on NO DEAL the route "funds the near-term gap" with the router's committed plan, but
`_ops_for_plan` drops the plan's buyer early-pay leg (no operation exists for it). On day 34 the whole plan is that leg:
no operation runs at all and the route still says the gap is funded; the reserve breach on day 42 stays.
(Started as a test of the `fund-<offer>-<profile>-<i>` keys, which carry no day: the key-reuse case did not arise
here because the line could not be repaid in between.)"""
import sys

from _harness import *

FX = sys.argv[1] if len(sys.argv) > 1 else "EX06_THREE_INVOICES"
PROFILE = sys.argv[2] if len(sys.argv) > 2 else "hard_line"


def negotiate(c, tag):
    v = evaluate_fixture(c, FX)
    print(f"[{tag}] verdict", v.get("outcome"), [k["label"] for k in v.get("counters", [])])
    n = c.post(f"/negotiate/{v['offer_id']}", headers=OWNER, json={"buyer_profile": PROFILE}).json()
    if "outcome" not in n:
        print(f"[{tag}] negotiate answered", n)
        return n
    print(f"[{tag}] outcome {n['outcome']}: {n['message']}")
    print(f"[{tag}] plan:", [(a["kind"], a["facility_id"], a.get("receivable_id"), a["amount_fen"]) for a in n["plan"]["actions"]])
    for o in n["operations"]:
        print(f"[{tag}]   op {o['op_id']} {o['kind']} {o['status']}: {o['message'][:170]}")
    return n


rt, c = fresh()
advance(c, 32)
op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-a", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
             "amount_fen": 42000000})
advance(c, 33)
t = projection(rt)
print("day 33: first breach", t.first_breach_day, "lowest", t.min_cash_fen, "on day", t.min_cash_day)
n1 = negotiate(c, "day 33")
t1 = projection(rt)
print("after the first negotiation: first breach", t1.first_breach_day, "lowest", t1.min_cash_fen)
# the owner repays the line the next day (the gap is still open), then negotiates the same offer again
advance(c, 34)
line = next(f for f in rt.store.get_state().facilities if f.id == "FAC-LINE")
r = opj(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": "repay-34", "requested_by": "OWNER", "facility_id": "FAC-LINE",
                   "amount_fen": line.drawn_fen})
print("owner repays the line on day 34:", r[1]["status"] if r[0] == 200 else r)
b = snap(rt, "day 34 before second negotiation")
n2 = negotiate(c, "day 34")
a = snap(rt, "day 34 after second negotiation")
t2 = projection(rt)
print("after the second negotiation: first breach", t2.first_breach_day, "lowest", t2.min_cash_fen)
stat = [o["status"] for o in n2.get("operations", [])]
check("day 34: the route says the gap is funded, its plan is only a buyer early-pay leg, and nothing is executed",
      "funds the near-term gap" in n2.get("message", "") and not n2.get("operations")
      and [x["kind"] for x in n2["plan"]["actions"]] == ["EARLY_PAY"] and t2.first_breach_day is not None)
check("a plan the route says funds the gap leaves a reserve breach (its buyer early-pay leg is never sent)",
      any(x["kind"] == "EARLY_PAY" for x in n1.get("plan", {}).get("actions", [])) and t1.first_breach_day is not None)
