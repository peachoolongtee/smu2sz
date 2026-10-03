"""Counterparty channel: BUYER-2 (its own key) names BUYER-1's invoice RCV-A in terms and price obligations."""
import sys

from _harness import *

texts = sys.argv[1:] or [
    "Extend invoice RCV-A to 60-day terms.",
    "We accept a 1% price increase on invoice RCV-A.",
    "Please extend the terms of invoice RCV-A by 30 days.",
    "We can pay invoice RCV-A of ¥420,000 early at 0.6%. Nothing else changes.",
]
for text in texts:
    rt, c = fresh()
    out = c.post("/nl", headers=BUYER2, json={"text": text, "actor": "COUNTERPARTY"}).json()
    print("TEXT:", text, "\n  reply:", out["reply"][:200].replace("\n", " | "))
    for o in rt.store.operations():
        print("  log", o.kind, o.result_json[:160])
    for cm in rt.store.commitments():
        print("  commitment", cm.counterparty_id, cm.status.value,
              [(o.type.value, o.counterparty_id, o.base.receivable_id, o.days_delta, o.rate_bp) for o in cm.obligations])
    for a in rt.store.approvals():
        print("  approval", a.id, a.reason[:120])
        r = approve(c, a.id)
        print("  -> owner approves:", r["status"], r["message"][:200])
        rc = next(x for x in rt.store.get_state().receivables if x.id == "RCV-A")
        print("  RCV-A now:", rc.counterparty_id, rc.face_fen, rc.terms_days, rc.applied)
