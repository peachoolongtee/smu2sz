"""Explore: buyer texts that become terms / price commitments (queued for the owner) and what approval writes."""
import sys

from _harness import *

texts = sys.argv[1:] or [
    "60-day terms on the next 3 invoices, with a 0.45% price adjustment on those invoices.",
    "Please move us to 60-day terms with a 0.45% price increase on future invoices.",
    "We accept a 0.5% price increase on the next 2 invoices.",
    "Extend terms to 60 days on the next 2 invoices.",
]
for text in texts:
    rt, c = fresh()
    out = c.post("/nl", headers=BUYER1, json={"text": text, "actor": "COUNTERPARTY"}).json()
    print("TEXT:", text, "\n  reply:", out["reply"][:220].replace("\n", " | "))
    for cm in rt.store.commitments():
        print("  commitment", cm.id, cm.status.value, cm.forward_value_fen,
              [(o.type.value, o.days_delta, o.rate_bp, o.duration.kind.value, o.duration.invoices, o.effective_day,
                o.contingency.value) for o in cm.obligations])
    for a in rt.store.approvals():
        print("  approval", a.id, a.status, a.kind, a.reason[:100])
        r = c.post(f"/approvals/{a.id}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
        print("  -> approve:", r["status"], r["message"][:200])
        s = rt.store.get_state()
        print("  adjustments", [(x.id[-12:], x.days_delta, x.price_bp, x.receivable_ids, x.from_issue_day, x.until_issue_day)
                                for x in s.invoice_adjustments])
        print("  fc", [(f.id[-10:], f.value_fen) for f in s.forward_concessions])
