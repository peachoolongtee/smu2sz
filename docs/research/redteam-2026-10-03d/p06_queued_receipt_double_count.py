"""A receipt reported by the agent waits for the owner (Tier 2). The bank feed then books the same money. Approving
the queued report books it a second time: cash and the invoice's settled face move twice for one payment."""
from _harness import *

rt, c = fresh()
advance(c, 10)
# the buyer tells the agent it has paid ¥200,000 of RCV-A; the agent reports it (Tier 2: queued)
q = op(c, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rx", "requested_by": "AGENT", "receivable_id": "RCV-A",
                  "amount_fen": 20000000})
print("agent report:", q["status"], q.get("approval_id"), q["message"][:160])
b0 = snap(rt, "queued")
# the bank feed books the actual credit
r = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "bank-rx", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                 "amount_fen": 20000000, "bank_reference": "STMT-0001"})
print("bank feed:", r["status"], r["message"][:160])
b1 = snap(rt, "after bank receipt")
# the owner approves the queued item later the same day
d = c.post(f"/approvals/{q['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
print("owner approves:", d["status"], d["message"][:200])
b2 = snap(rt, "after approval")
rx = c.get("/reconciliation", headers=OWNER).json()["reconciliation"]
for row in rx.get("receipts", rx.get("rows", []))[:5]:
    print("  recon", {k: row.get(k) for k in ("receivable_id", "amount_fen", "status", "seq")})
print("chain ok:", rt.store.verify_chain())
check("one ¥200,000 payment booked twice (cash +¥400,000, settled ¥400,000)",
      b2["cash"] - b0["cash"] == 40000000 and b2["receivables"]["RCV-A"][2] == 40000000)
