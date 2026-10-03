"""An on-time early payment reported by the agent (Tier 2) and approved by the owner the next day is booked on the
approval day: the agreed discount is lost and the buyer is shown as owing it.

Day 0: EX01 -> /negotiate, the buyer accepts Option A (early settlement of ¥257,200 of RCV-A at 0.85%, promised for
day 2). Day 2: the money arrives; the agent reports it (RECEIVE_PAYMENT requested_by AGENT -> queued for the
owner). The owner approves on day 3. The executor re-runs the receipt dated day 3: past the promised day, so it is a
plain receipt and ¥2,186.20 stays "due" from the buyer; the commitment was already ended as lapsed by the clock."""
from _harness import *  # noqa
from app.alerts import reconcile

rt, c = fresh()
oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
cm = rt.store.get_commitment(n["commitment"]["id"])
ep = next(o for o in cm.obligations if o.type.value == "IMMEDIATE_DISCOUNT")
agreed = ep.base.amount_fen - (ep.base.amount_fen * ep.rate_bp + 5000) // 10000
print("deal:", n["outcome"], "promised day", ep.effective_day, "agreed amount", agreed)
advance(c, 2)
r = op(c, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rx", "requested_by": "AGENT",
                  "receivable_id": "RCV-A", "amount_fen": agreed})
print("day 2 agent reports the receipt:", r["status"], r["message"][:160])
advance(c, 3)
print("commitment after closing day 2:", rt.store.get_commitment(cm.id).status.value)
d = c.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
print("day 3 owner approves:", d["status"], d["message"])
rcv = next(x for x in rt.store.get_state().receivables if x.id == "RCV-A")
print(f"RCV-A settled {rcv.settled_fen} outstanding {rcv.outstanding_fen}")
for m in reconcile(rt.store, rt.day).receipts:
    print("RECON", m.status.value, m.detail)
check("an on-time early payment, reported on the promised day and approved the next, loses its agreed discount",
      rcv.outstanding_fen == 42_000_000 - agreed)
