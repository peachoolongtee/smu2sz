"""Idempotency keys are one global namespace and a DUPLICATE is answered without comparing the operation: an
operation the agent logged first under a key makes a later, different operation with that key (here the bank feed's
receipt) a DUPLICATE. Nothing is booked, and the bank feed is told it already was."""
from _harness import *  # noqa: F403

rt, c = fresh()
advance(c, 32)  # RCV-A falls due
before = snap(rt, "day 32")
# the agent logs a harmless Tier-1 operation under the key the bank feed will use for today's receipt
r1 = op(c, AGENT, {"kind": "REJECT_OFFER", "op_id": "x-1", "idempotency_key": "BANKREF-RCV-A-32", "requested_by": "AGENT",
                   "offer_id": "nothing", "reason_codes": []})
print("agent:", r1["kind"], r1["status"], r1["message"])
r2 = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-A", "idempotency_key": "BANKREF-RCV-A-32",
                  "requested_by": "SYSTEM", "receivable_id": "RCV-A", "amount_fen": 42000000})
print("bank feed receipt:", r2["kind"], r2["status"], r2["message"][:200])
after = snap(rt, "after")
check("a bank receipt of ¥420,000 was answered DUPLICATE of an unrelated operation and never booked",
      r2["status"] == "DUPLICATE" and after["cash"] == before["cash"]
      and after["receivables"]["RCV-A"][2] == 0)
