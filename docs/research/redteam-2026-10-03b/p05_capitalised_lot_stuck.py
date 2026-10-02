"""A receipt that repays an advance's principal but not all its charges capitalises the unpaid charges as a new
lot on the invoice and keeps it FINANCED. When that receipt is the invoice's last (nothing left outstanding), no
later receipt can be booked and an on-receipt facility cannot be repaid: the lot and the drawn balance can never
clear. Reached with a facility whose advance rate allows the whole face (no advance-rate cap)."""
from _harness import *  # noqa: F403

FAC = {"id": "FAC-IF100", "name": "Full-face invoice financing", "kind": "INVOICE_FINANCING", "lender_id": "PLATFORM-1",
       "status": "COMMITTED", "owner_approved": True, "limit_fen": 50000000, "advance_rate_bp": None, "rate_bp": 780,
       "fee_bp_per_advance": 25, "fee_period_days": 30, "lead_time_days": 0, "repayment": "ON_RECEIPT"}

rt, c = fresh()
res = op(c, OWNER, {"kind": "ADD_FACILITY", "op_id": "add-if100", "requested_by": "OWNER", "facility": FAC})
print("add facility:", c.post(f"/approvals/{res['approval_id']}", headers=OWNER,
                              json={"decision": "APPROVE"}).json()["result"]["status"])
res = op(c, OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-full", "requested_by": "OWNER",
                    "facility_id": "FAC-IF100", "receivable_id": "RCV-A", "advance_fen": 42000000})
print("finance full face:", res["status"], res["message"][:200])
snap(rt, "financed")
advance(c, 32)  # RCV-A is due on day 32
res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-full", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                   "amount_fen": 42000000})
print("buyer pays the whole face on the due day:", res["status"], res["message"])
s1 = snap(rt, "after receipt")
print("lots", lots(rt), "| conservation:", conservation(rt))
res2 = opj(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-more", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                     "amount_fen": 100000})
print("any further receipt:", res2[1]["status"], res2[1]["message"][:160])
res3 = opj(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": "repay-left", "requested_by": "OWNER",
                      "facility_id": "FAC-IF100", "amount_fen": rt.store.get_state().lots[0].remaining_fen})
print("owner repays the rest:", res3[1]["status"], res3[1]["message"][:160])
advance(c, 120)
s2 = snap(rt, "day 120")
print("lots", lots(rt))
t = projection(rt)
pay = [(p.day, e.label, e.amount_fen) for p in t.days for e in p.events if e.ref == "FAC-IF100"]
print("projection on day 120 repays it on:", pay)
check("FINANCED invoice with nothing outstanding and a live lot that no operation can clear",
      s2["receivables"]["RCV-A"][0] == "FINANCED" and s2["drawn"].get("FAC-IF100", 0) > 0
      and res2[1]["status"] == "REFUSED" and res3[1]["status"] == "REFUSED")
