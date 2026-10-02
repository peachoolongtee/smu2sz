"""A queued (Tier-2, above the APR ceiling) advance approved by the owner after the invoice was partly paid, fully
paid, or on a later day: the executor must re-check against the books at decision time."""
from _harness import *  # noqa: F403


def queue(c, rt, rid, amt, tag):
    r = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": f"q-{tag}", "requested_by": "AGENT",
                      "facility_id": "FAC-IF", "receivable_id": rid, "advance_fen": amt})
    return r


for case in ("partial receipt", "paid in full", "later day"):
    rt, c = fresh()
    advance(c, 25)  # RCV-A due 32: an advance now lands day 28, 4 days early -> far above the 15% ceiling
    r = queue(c, rt, "RCV-A", 33600000, case.replace(" ", "-"))
    print(f"[{case}] queued: {r['status']} {r.get('approval_id')} ({r['message'][:110]})")
    if case == "partial receipt":
        op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-p", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                     "amount_fen": 20000000})
    elif case == "paid in full":
        op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-f", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                     "amount_fen": 42000000})
    else:
        advance(c, 30)  # arrival would be day 33, after the due day 32
    d = c.post(f"/approvals/{r['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
    print(f"   owner approves: {d['status']} {d['message'][:160]}")
    s = snap(rt, "after")
    check(f"{case}: the queued advance executed against changed books", d["status"] == "EXECUTED")
