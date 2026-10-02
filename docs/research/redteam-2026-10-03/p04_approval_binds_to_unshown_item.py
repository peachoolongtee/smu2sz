"""P04: the owner is shown APR-000001 in their chat session. That item is decided elsewhere and the agent key queues
a different one (an unverified ¥400,000 "receipt"). The owner's "approve the pending one" in the same session then
approves APR-000002, which this session never showed, and the cash is booked."""

from _harness import AGENT, OWNER, advance, check, fresh, op, snap

rt, c = fresh()
advance(c, 5)
s0 = snap(rt, "start")

a1 = op(c, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rcpt-1", "requested_by": "AGENT",
                   "receivable_id": "RCV-A", "amount_fen": 100})
print("  agent queues:", a1["status"], a1.get("approval_id"))

S = "owner-chat"
t1 = c.post("/nl", headers=OWNER, json={"session_id": S, "actor": "OWNER", "text": "approve it"}).json()
print("  owner 'approve it' ->", t1["intent"], "|", t1["reply"][:160])

# APR-000001 is declined on the owner console; the agent then queues a different, larger item
c.post(f"/approvals/{a1['approval_id']}", headers=OWNER, json={"decision": "REJECT"})
a2 = op(c, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rcpt-2", "requested_by": "AGENT",
                   "receivable_id": "RCV-A", "amount_fen": 40_000_000})
print("  agent queues:", a2["status"], a2.get("approval_id"))

t2 = c.post("/nl", headers=OWNER, json={"session_id": S, "actor": "OWNER", "text": "approve the pending one"}).json()
print("  owner 'approve the pending one' ->", t2["intent"], "|", t2["reply"][:200])
s1 = snap(rt, "after")

shown1 = a1["approval_id"] in t1["reply"] or any(a1["approval_id"] in o["label"]
                                                  for o in (t1.get("clarification") or {}).get("options", []))
print("\nRESULT")
broken = [
    check("session had shown only APR-000001", shown1 and a2["approval_id"] not in t1["reply"]),
    check("'approve the pending one' decided the never-shown item and booked ¥400,000",
          s1["approvals"].get(a2["approval_id"]) == "APPROVED" and s1["cash"] - s0["cash"] == 40_000_000),
]
print("BROKEN" if all(broken) else "HELD")
