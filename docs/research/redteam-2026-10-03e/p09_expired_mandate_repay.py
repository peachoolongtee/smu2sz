"""After the mandate expires (day 90) the owner cannot repay the credit line: an owner-requested RepayFacility is
refused for the expired mandate, although the bank feed's receipts are still booked as facts. Interest keeps
accruing, the line's 30-day clean-down cannot be met, and the projection keeps assuming the repayment it cannot make.
"""
from _harness import *  # noqa

rt, c = fresh()
r = op(c, OWNER, {"kind": "DRAW_FACILITY", "op_id": "own-draw", "requested_by": "OWNER", "facility_id": "FAC-LINE",
                  "amount_fen": 10_000_000})
print("day 0 owner draw:", r["status"], r["message"])
t = projection(rt)
live(c, rt, t, 91, tag="x")
snap(rt, "day 91")
code, res = opj(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": "own-repay", "requested_by": "OWNER",
                           "facility_id": "FAC-LINE", "amount_fen": 10_000_000})
print("day 91 owner repay:", code, res["status"], res["message"])
s = rt.store.get_state()
print("cash", s.cash_fen, "line drawn", next(f.drawn_fen for f in s.facilities if f.id == "FAC-LINE"))
t2 = projection(rt)
assumed = [(p.day, e.amount_fen, e.formula) for p in t2.days for e in p.events
           if e.kind.value == "REPAYMENT" and e.ref == "FAC-LINE"]
print("projection still assumes:", assumed[:2])
check("the owner's own repayment of a drawn line is refused once the mandate has expired",
      res["status"] == "REFUSED" and any("expired" in v["message"] for v in res["violations"]))
rx = opj(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "late-rx", "requested_by": "SYSTEM",
                   "receivable_id": "RI:BUYER-1:62", "amount_fen": 100})
print("bank receipt the same day:", rx[1]["status"], rx[1]["message"][:120])
print("chain", rt.store.verify_chain())
