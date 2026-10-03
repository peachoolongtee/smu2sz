"""A buyer's early-pay agreement that lapses unpaid keeps its invoice out of financing for ever, while the books,
the router, admission and the alert's cure all treat the invoice as financeable.

1. Day 0: BUYER-1 (its own channel key) offers to pay RCV-A early at 0.6%; the agent accepts alone (Tier 1).
2. The buyer never pays. The clock passes the promised day 2: current_books drops the obligation as
   EARLY_PAYMENT_MISSED and RCV-A is back on its due day 32.
3. The reserve-breach alert's cure (and the router's committed plan) finance RCV-A. The executor refuses the
   advance because the commitment is still ACTIVE and names RCV-A.
"""
from _harness import *
from app.books import current_books

rt, c = fresh()
r = c.post("/nl", headers=BUYER1, json={"text": "We can pay invoice RCV-A of ¥420,000 early at 0.6%. Nothing else changes.",
                                         "actor": "COUNTERPARTY"}).json()
print("buyer reply:", r["reply"][:160])
cm = rt.store.commitments()[0]
print("commitment", cm.id, cm.status.value, "obligation effective day", cm.obligations[0].effective_day)
snap(rt, "day 0 after accept")
advance(c, 3)
s = snap(rt, "day 3, buyer did not pay")
books = current_books(rt.store.get_state(), rt.store.commitments())
print("live obligations", [o.id for o in books.obligations], "lapsed", [(l.commitment_id, l.reason) for l in books.lapsed])
print("commitment status now", rt.store.get_commitment(cm.id).status.value)
t = projection(rt)
print("projection: first breach day", t.first_breach_day, "lowest", t.min_cash_fen, "on", t.min_cash_day)

plan = c.post("/router/plan", headers=OWNER).json()["committed"]
print("router plan:", [(a["kind"], a["facility_id"], a.get("receivable_id"), a["amount_fen"]) for a in plan["actions"]],
      "admissible", plan["admissible"], "executable_now", plan.get("executable_now"))

al = c.get("/alerts", headers=OWNER).json()
crit = [a for a in al["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
for a in crit:
    print("alert", a["id"], a["title"], [(x["operation_kind"], x.get("facility_id"), x.get("receivable_id"), x.get("amount_fen"))
                                         for x in a["suggested"]])
log0 = len(rt.store.operations())
if crit:
    a = crit[0]
    sig = [{k: x.get(k) for k in ("operation_kind", "facility_id", "receivable_id", "amount_fen")} for x in a["suggested"]]
    resp = c.post(f"/alerts/{a['id']}/act", headers=OWNER, json={"state_version": al["state_version"]})
    out = resp.json()
    print("act:", resp.status_code, {k: out.get(k) for k in ("executed", "pending_approval", "refused", "cured")})
    for res in out.get("results", []):
        print("   ", res["kind"], res["status"], res["message"][:260])
# The plan leg on RCV-A, directly through /operations, as the agent:
fin = [a for a in plan["actions"] if a["kind"] == "FINANCE_INVOICE" and a.get("receivable_id") == "RCV-A"]
if fin:
    code, res = opj(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "direct-fin", "requested_by": "AGENT",
                               "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": fin[0]["amount_fen"]})
    print("direct advance on RCV-A:", code, res["status"], res["message"][:260])
snap(rt, "after attempts")
t2 = projection(rt)
print("projection after attempts: first breach day", t2.first_breach_day, "lowest", t2.min_cash_fen, "on", t2.min_cash_day)
check("router/alert cure finances RCV-A but the executor refuses it while the lapsed agreement stays ACTIVE",
      bool(fin) and res["status"] == "REFUSED" and "early-payment agreement" in res["message"])
check("reserve breach still ahead after the owner pressed the cure button", t2.first_breach_day is not None)
