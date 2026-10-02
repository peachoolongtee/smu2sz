"""P01: an agent-key caller trips BUYER-1's circuit breaker with three misdated operations; the bank feed's real
receipt from BUYER-1 is then REFUSED, and the bank feed's retry under the same idempotency key is answered
DUPLICATE of the refusal, so the money that reached the bank is never booked under that key."""

from _harness import AGENT, BANK, OWNER, advance, check, fresh, op, snap

rt, c = fresh()
advance(c, 5)
before = snap(rt, "before")

# 1. the agent key sends three operations that name BUYER-1's receivable, each dated one day in the future
for i in range(3):
    r = op(c, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": f"junk-{i}", "requested_by": "AGENT",
                      "receivable_id": "RCV-A", "amount_fen": 1, "day": rt.day + 1})
    print("  agent junk:", r["status"], r["violations"][0]["code"])
print("  circuit open for BUYER-1:", rt.executor.circuit_open("BUYER-1"))

# 2. BUYER-1 actually pays ¥100,000 into the bank: the bank feed reports it
r1 = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "bank-rcpt-1", "requested_by": "SYSTEM",
                  "receivable_id": "RCV-A", "amount_fen": 10_000_000})
print("  bank receipt:", r1["status"], r1["message"][:120])
mid = snap(rt, "after bank receipt")

# 3. the owner resets the circuit; the bank feed retries the same receipt (same idempotency key)
rs = c.post("/circuit/BUYER-1/reset", headers=OWNER).json()["result"]
print("  owner reset:", rs["status"])
r2 = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "bank-rcpt-1", "requested_by": "SYSTEM",
                  "receivable_id": "RCV-A", "amount_fen": 10_000_000})
print("  bank retry:", r2["status"], r2["message"][:140])
after = snap(rt, "after retry")

print("\nRESULT")
broken = [
    check("agent key alone opened the buyer's circuit", rt.executor.circuit_open("BUYER-1") is False and r1["status"] == "REFUSED"),
    check("a real bank receipt was refused (cash unchanged)", r1["status"] == "REFUSED" and mid["cash"] == before["cash"]),
    check("retry with the same key never books it, even after the owner reset",
          r2["status"] == "DUPLICATE" and after["cash"] == before["cash"]
          and after["receivables"]["RCV-A"][2] == 0),
]
print("BROKEN" if any(broken) else "HELD")
