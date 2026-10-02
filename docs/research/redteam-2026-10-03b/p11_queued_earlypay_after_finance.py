"""A queued (Tier-2) early-pay acceptance approved by the owner after the agent financed the same invoice."""
from _harness import *  # noqa: F403

rt, c = fresh()
out = nl(c, BUYER1, "We can pay this one early at 0.5%. Nothing else changes.", actor="COUNTERPARTY")
print("buyer:", out["reply"])
apr = [a for a in rt.store.approvals()][0]
print("queued:", apr.id, apr.reason)
res = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-1", "requested_by": "AGENT",
                    "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 33600000})
print("agent finances RCV-A:", res["status"], res["message"][:100])
d = c.post(f"/approvals/{apr.id}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
print("owner approves the early pay:", d["status"], d["message"][:300])
snap(rt, "after")
print({x.id: x.status.value for x in rt.store.commitments()})
check("an early-pay agreement became ACTIVE on an invoice already pledged to the lender",
      any(x.status.value == "ACTIVE" for x in rt.store.commitments()))
