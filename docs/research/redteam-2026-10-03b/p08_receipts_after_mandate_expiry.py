"""The bank feed's receipts go through the agent's mandate gate: after the owner's mandate expires (day 90 in the
fixture, inside its own 120-day horizon) no receipt can be booked, by the bank feed or the owner, while the clock
keeps posting payroll and loan payments. A financed invoice paid by the buyer then never repays the lender."""
from _harness import *  # noqa: F403

rt, c = fresh()
advance(c, 63)
res = op(c, OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-62", "requested_by": "OWNER",
                    "facility_id": "FAC-IF", "receivable_id": "RI:BUYER-1:62", "advance_fen": 30000000})
print("day 63 finance RI:BUYER-1:62:", res["status"], res["message"][:120])
advance(c, 107)  # RI:BUYER-1:62 is due on day 107; the mandate expired on day 90
before = snap(rt, "day 107")
code, res = opj(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-62", "requested_by": "SYSTEM",
                          "receivable_id": "RI:BUYER-1:62", "amount_fen": 42000000})
print("bank feed books the buyer's payment:", res["status"], res["message"][:200])
code, res2 = opj(c, OWNER, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-62-owner", "requested_by": "OWNER",
                            "receivable_id": "RI:BUYER-1:62", "amount_fen": 42000000})
print("the owner books it:", res2["status"], res2["message"][:200])
after = snap(rt, "after")
print("lots", lots(rt))
check("a real bank receipt cannot be booked by anyone once the agent's mandate has expired",
      res["status"] == "REFUSED" and res2["status"] == "REFUSED" and after["cash"] == before["cash"])
advance(c, 130)
snap(rt, "day 130 (clock kept posting outflows)")
