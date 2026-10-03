"""Clock jumps versus single days over the same operations: Option B (perpetual terms + price) accepted on day 0,
the router's plan executed, receipts on their due days, existing-debt payments on 30/60/90, through the mandate's
expiry. Run A closes one day at a time; run B jumps between operation days. The books must be identical."""
from _harness import *


def setup(c, rt):
    v = evaluate_fixture(c, "EX01_PACKAGE")
    b = next(k for k in v["counters"] if "terms" in k["text"])
    res, cm = commit_counter(c, v["id"], b["id"], "optB")
    if res["status"] == "PENDING_APPROVAL":
        res = approve(c, res["approval_id"])
    print("  option B:", res["status"], res["message"][:120])
    plan = c.post("/router/plan", headers=OWNER).json()["committed"]
    for i, a in enumerate(plan["actions"]):
        if a["kind"] == "DRAW":
            r = op(c, AGENT, {"kind": "DRAW_FACILITY", "op_id": f"plan-{i}", "requested_by": "AGENT",
                              "facility_id": a["facility_id"], "amount_fen": a["amount_fen"]})
        else:
            r = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": f"plan-{i}", "requested_by": "AGENT",
                              "facility_id": a["facility_id"], "receivable_id": a["receivable_id"],
                              "advance_fen": a["amount_fen"]})
        print("  leg", a["kind"], a.get("receivable_id"), a["amount_fen"], r["status"], r["message"][:100])


DAYS = []


def receipts_today(c, rt):
    s = rt.store.get_state()
    for r in s.receivables:
        if r.status in ("OPEN", "FINANCED") and r.due_day == rt.day:
            res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": f"rx-{r.id}", "requested_by": "SYSTEM",
                               "receivable_id": r.id, "amount_fen": r.outstanding_fen})
            print(f"    day {rt.day} receipt {r.id} {r.outstanding_fen}: {res['status']}")
            DAYS.append(rt.day)


END = 125
rt, c = fresh()
setup(c, rt)
while rt.day < END:
    receipts_today(c, rt)
    advance(c, rt.day + 1)
receipts_today(c, rt)
A = state_digest(rt)
okA = rt.store.verify_chain()

rt, c = fresh()
setup(c, rt)
print("jump stops", sorted(set(DAYS)))
for d in sorted(set(DAYS)) + [END]:
    advance(c, d)
    receipts_today(c, rt)
B = state_digest(rt)
okB = rt.store.verify_chain()
diff = {k: (A[k], B[k]) for k in A if A[k] != B[k]}
for k, (a, b) in diff.items():
    print("DIFF", k, "\n   steps:", a, "\n   jumps:", b)
print("chains", okA, okB)
check("single days and jumps give different books", bool(diff))
