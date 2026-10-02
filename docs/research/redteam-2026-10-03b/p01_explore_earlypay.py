"""Explore: what an authenticated buyer's early-pay message does on an OPEN vs FINANCED invoice."""
from _harness import *  # noqa: F403

for financed in (False, True):
    rt, c = fresh()
    if financed:
        op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-1", "requested_by": "AGENT",
                      "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 33600000})
        advance(c, 4)
    for text in ("We can pay this one early at 0.5%. Nothing else changes.",
                 "We can pay RCV-A early at 0.4%. Nothing else changes."):
        out = nl(c, BUYER1, text, actor="COUNTERPARTY")
        print(financed, repr(text), "->", out["reply"][:300])
    for cm in rt.store.commitments():
        print("  commitment", cm.id, cm.status.value, [(o.type.value, o.base.receivable_id, o.rate_bp, o.effective_day,
                                                       o.contingency.value) for o in cm.obligations])
    snap(rt, f"financed={financed}")
    print("  log tail", [(x.kind, x.result_json[:160]) for x in rt.store.operations()[-3:]])
