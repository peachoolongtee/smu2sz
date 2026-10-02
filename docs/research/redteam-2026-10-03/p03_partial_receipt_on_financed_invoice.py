"""P03: a 1-fen bank receipt on a FINANCED invoice repays the WHOLE advance plus interest and fees out of the
supplier's own cash, with no cash check (cash may go negative), and the invoice returns to OPEN so it can be
financed a second time."""

from _harness import BANK, OWNER, advance, check, fresh, op, snap

rt, c = fresh()
advance(c, 10)
r = op(c, OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-1", "requested_by": "OWNER",
                  "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 33_600_000})
print("  finance:", r["status"])
advance(c, 25)  # payroll (day 12) and supplier (day 20) have gone out
s0 = snap(rt, "day 25 before 1-fen receipt")

rr = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rcpt-1fen", "requested_by": "SYSTEM",
                  "receivable_id": "RCV-A", "amount_fen": 1})
print("  1-fen receipt:", rr["status"], rr["message"])
s1 = snap(rt, "after 1-fen receipt")

r2 = op(c, OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-2", "requested_by": "OWNER",
                   "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 1_000_000})
print("  second financing of the same invoice:", r2["status"], r2["message"][:120])

print("\nRESULT")
broken = [
    check("a 1-fen receipt moved more than the advance out of cash",
          s0["cash"] - s1["cash"] > 33_600_000 - 1),
    check("cash went negative with no refusal", s1["cash"] < 0),
    check("invoice reopened (OPEN, advance cleared) after a 1-fen receipt",
          s1["receivables"]["RCV-A"][0] == "OPEN" and s1["receivables"]["RCV-A"][3] == 0),
    check("the same invoice was financed again", r2["status"] in ("EXECUTED", "PENDING_APPROVAL")),
]
print("BROKEN" if any(broken) else "HELD")
