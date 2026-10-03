"""The buyer pays the discounted amount one day after the promised day. The executor books a plain receipt (A09: the
discount is not earned; the difference stays due). Reconciliation replays it as the agreed early payment: the promise
row says RECEIVED, the replay settles the whole face, and the buyer's later payment of the difference is flagged as
an unexpected amount although the executor books it as the payment that settles the invoice."""
from _harness import *

rt, c = fresh()
c.post("/nl", headers=BUYER1, json={"text": "We can pay invoice RCV-A of ¥420,000 early at 0.6%. Nothing else changes.",
                                    "actor": "COUNTERPARTY"})
cm = rt.store.commitments()[0]
print("commitment", cm.status.value, "promised day", cm.obligations[0].effective_day)
advance(c, 3)  # one day late
disc = 42000000 * 60 // 10000
r1 = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-late", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                  "amount_fen": 42000000 - disc})
print("late discounted receipt:", r1["status"], r1["message"][:160])
advance(c, 10)
r2 = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-rest", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                  "amount_fen": disc})
print("difference paid:", r2["status"], r2["message"][:160])
s = snap(rt, "books")
print("commitment now:", rt.store.get_commitment(cm.id).status.value)
rec = c.get("/reconciliation", headers=OWNER).json()["reconciliation"]
for m in rec["receipts"]:
    print("  receipt seq", m["seq"], m["received_fen"], m["status"], "expected", m["expected_fen"], "|", m["detail"][:120])
for p in rec["promised"]:
    print("  promise", p["status"], "|", p["detail"][:140])
st = [m["status"] for m in rec["receipts"]]
check("reconciliation calls the late early payment RECEIVED and flags the settling receipt as UNEXPECTED_AMOUNT",
      any(p["status"] == "RECEIVED" for p in rec["promised"]) and st[-1] != "MATCHED"
      and s["receivables"]["RCV-A"][0] == "SETTLED")
