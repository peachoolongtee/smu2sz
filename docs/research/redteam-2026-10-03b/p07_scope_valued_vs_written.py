"""Scope seam (ADR-0009 vs dated valuation): a "next invoice" terms extension accepted after day 0 is VALUED on the
next invoice to be issued (window starts today: `concessions.scoped_invoices` uses max(effective day, today)) but
WRITTEN at acceptance onto the oldest open invoice issued on or after day 0 (`invoices.scope_at` uses effective day
or 0): an invoice already issued, possibly overdue, possibly already carrying an extension. The projection follows
what was written, so an overdue invoice from the same buyer is revived as projected cash."""
from _harness import *  # noqa: F403

TEXT = "Give us 60 days instead of 45 on the next invoice. Nothing else changes."


def offer_and_accept(c, rt, tag):
    docs = [{"doc_id": f"D-{tag}", "channel": "chat", "sender_id": "BUYER-1", "received_day": rt.day, "text": TEXT}]
    o = c.post("/offers", json={"counterparty_id": "BUYER-1", "documents": docs}).json()["offer"]
    v = c.post(f"/offers/{o['offer_id']}/evaluate", headers=OWNER, json={}).json()
    print(f"  day {rt.day} verdict {v['outcome']}; valued: {v['concession_values'][0]['formula'][:80]}")
    cm = rt.executor.propose_commitment(v["id"], expires_day=rt.day + 7)
    res = op(c, AGENT, {"kind": "ACCEPT_OFFER", "op_id": f"acc-{tag}", "requested_by": "AGENT", "source_verdict_id": v["id"],
                        "offer_id": cm.offer_id, "offer_version": cm.offer_version, "terms_hash": cm.terms_hash,
                        "nonce": cm.nonce})
    print(f"  accept: {res['status']} {res.get('approval_id')} ({res['message'][:90]})")
    if res["status"] == "PENDING_APPROVAL":
        res = c.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
        print(f"  owner approves: {res['status']} {res['message']}")
    return v


def rcv(rt, rid):
    r = next(r for r in rt.store.get_state().receivables if r.id == rid)
    return (r.status, r.face_fen, r.terms_days, r.due_day, r.applied)


# --- 1. day 3: priced on the day-32 invoice, written onto the day-2 invoice
rt, c = fresh()
advance(c, 3)
v = offer_and_accept(c, rt, "a")
print("  RI:BUYER-1:2 ", rcv(rt, "RI:BUYER-1:2"))
advance(c, 33)
print("  RI:BUYER-1:32", rcv(rt, "RI:BUYER-1:32"))
check("the invoice the owner approved (issued day 32) did not get the extension; the day-2 invoice did",
      rcv(rt, "RI:BUYER-1:32")[2] == 45 and rcv(rt, "RI:BUYER-1:2")[2] == 60)

# --- 2. the buyer is late on RI:BUYER-1:2 (due day 47); on day 50 it offers +15 days on the next invoice
rt, c = fresh()
advance(c, 50)
t0 = projection(rt)
al0 = [(a.get("kind"), a.get("ref") or a.get("receivable_id"), a.get("severity"))
       for a in c.get("/alerts", headers=OWNER).json().get("alerts", [])]
print("  day 50 before: RI:BUYER-1:2", rcv(rt, "RI:BUYER-1:2"), "| alerts", al0)
inflow0 = sum(e.amount_fen for p in t0.days for e in p.events if e.ref == "RI:BUYER-1:2")
offer_and_accept(c, rt, "b")
t1 = projection(rt)
al1 = [(a.get("kind"), a.get("ref") or a.get("receivable_id"), a.get("severity"))
       for a in c.get("/alerts", headers=OWNER).json().get("alerts", [])]
inflow1 = [(p.day, e.amount_fen) for p in t1.days for e in p.events if e.ref == "RI:BUYER-1:2"]
print("  day 50 after: RI:BUYER-1:2", rcv(rt, "RI:BUYER-1:2"), "| alerts", al1)
print(f"  projected receipt from the overdue RI:BUYER-1:2: before {fmt_yuan(inflow0)}, after {inflow1}")
print(f"  projected minimum: before {fmt_yuan(t0.min_cash_fen)} (day {t0.min_cash_day}), after "
      f"{fmt_yuan(t1.min_cash_fen)} (day {t1.min_cash_day})")
check("an overdue invoice was turned back into projected cash by an agreement priced on a future invoice",
      inflow0 == 0 and bool(inflow1))
