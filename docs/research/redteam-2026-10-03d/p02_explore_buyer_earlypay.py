"""Explore: what a buyer can get accepted alone on the counterparty channel (early pay on RCV-A)."""
from _harness import *

texts = [
    "We can pay invoice RCV-A of ¥420,000 early at 0.6%. Nothing else changes.",
    "We can pay this one early at 0.6%. Nothing else changes.",
    "We can pay the ¥420,000 invoice early at 0.6%. Nothing else changes.",
    "We can pay this one early at 0.5%. Nothing else changes.",
]
for text in texts:
    rt, c = fresh()
    r = c.post("/nl", headers=BUYER1, json={"text": text, "actor": "COUNTERPARTY"})
    out = r.json()
    print("TEXT:", text)
    print("  status", r.status_code, "reply:", out.get("reply", "")[:300].replace("\n", " | "))
    for cm in rt.store.commitments():
        print("  commitment", cm.id, cm.status.value, [(o.type.value, o.base.receivable_id, o.base.amount_fen, o.rate_bp,
                                                       o.effective_day) for o in cm.obligations])
    for a in rt.store.approvals():
        print("  approval", a.id, a.status, a.kind)
    v = rt.store.get_verdict(next(iter(rt.latest_verdict.values()))) if rt.latest_verdict else None
    ops = [(e.kind, e.result_json[:200] if hasattr(e, "result_json") else "") for e in rt.store.operations()]
    for o in rt.store.operations():
        print("  log", o.seq, o.kind, o.result_json[:220] if hasattr(o, "result_json") else "")
