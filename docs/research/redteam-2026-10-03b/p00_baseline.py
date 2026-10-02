from _harness import *  # noqa: F403

rt, c = fresh()
snap(rt, "start")
t = projection(rt)
print("proj closings", [(p.day, p.closing_fen) for p in t.days if p.day in (0, 3, 12, 20, 32, 40, 47)])
r = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-1", "requested_by": "AGENT",
                  "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 33600000})
print(r["status"], r["message"])
snap(rt, "after finance")
print(lots(rt), conservation(rt))
