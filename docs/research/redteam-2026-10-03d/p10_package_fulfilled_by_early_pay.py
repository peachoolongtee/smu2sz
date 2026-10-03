"""A package (early pay on RCV-A + perpetual terms extension + price change) is approved by the owner. The buyer's
early payment marks the WHOLE commitment FULFILLED, although its perpetual terms are still written onto every new
invoice. A FULFILLED commitment cannot be revoked, so the owner has lost the compensating action for the terms."""
from _harness import *

rt, c = fresh()
text = ("We can pay invoice RCV-A of ¥420,000 early at 0.6% if you extend our standard terms to 50 days going forward "
        "with a 0.5% price increase.")
c.post("/nl", headers=BUYER1, json={"text": text, "actor": "COUNTERPARTY"})
apr = rt.store.approvals()[0]
r = approve(c, apr.id)
cm = rt.store.commitments()[0]
print("owner approves:", r["status"], r["message"][:120])
print("obligations:", [(o.type.value, o.base.receivable_id, o.days_delta, o.rate_bp, o.duration.kind.value)
                       for o in cm.obligations])
# the buyer pays the discounted amount on day 1 (promised day 2)
advance(c, 1)
amt = 42000000 - 42000000 * 60 // 10000
res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-early", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                   "amount_fen": amt})
print("early receipt:", res["status"], res["message"][:160])
cm = rt.store.get_commitment(cm.id)
s = rt.store.get_state()
print("commitment status:", cm.status.value, "| adjustments still in state:",
      [(a.days_delta, a.price_bp, a.from_issue_day, a.until_issue_day) for a in s.invoice_adjustments if a.commitment_id == cm.id])
advance(c, 3)
inv = next(x for x in rt.store.get_state().receivables if x.id == "RI:BUYER-1:2")
print("RI:BUYER-1:2 issued on day 2:", inv.face_fen, "fen,", inv.terms_days, "day terms, applied", inv.applied)
rv = c.post(f"/commitments/{cm.id}/revoke", headers=OWNER).json()["result"]
print("owner revokes:", rv["status"], rv["message"][:200])
advance(c, 33)
inv2 = next(x for x in rt.store.get_state().receivables if x.id == "RI:BUYER-1:32")
print("RI:BUYER-1:32 issued on day 32:", inv2.face_fen, inv2.terms_days, inv2.applied)
print("chain ok:", rt.store.verify_chain())
check("commitment FULFILLED while its perpetual terms keep being written, and the owner cannot revoke them",
      cm.status.value == "FULFILLED" and rv["status"] == "REFUSED" and inv2.terms_days == 50)
