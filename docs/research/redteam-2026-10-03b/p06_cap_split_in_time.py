"""Cap evasion by splitting in time: the same extension on the same invoices, as one agreement versus one agreement per
invoice accepted after the previous invoice was issued (its commitment is then FULFILLED and its booked forward
concession leaves the aggregate, although the invoice carrying the extension is still unpaid)."""
from _harness import *  # noqa: F403


def offer(c, text: str) -> dict:
    docs = [{"doc_id": f"D-{abs(hash((text, get_runtime().day))) % 10**8}", "channel": "chat", "sender_id": "BUYER-1",
             "received_day": get_runtime().day, "text": text}]
    o = c.post("/offers", json={"counterparty_id": "BUYER-1", "documents": docs}).json()["offer"]
    v = c.post(f"/offers/{o['offer_id']}/evaluate", headers=OWNER, json={}).json()
    return v


def accept(c, rt, v: dict, tag: str) -> dict:
    cm = rt.executor.propose_commitment(v["id"], expires_day=rt.day + 7)
    res = op(c, AGENT, {"kind": "ACCEPT_OFFER", "op_id": f"acc-{tag}", "requested_by": "AGENT", "source_verdict_id": v["id"],
                        "offer_id": cm.offer_id, "offer_version": cm.offer_version, "terms_hash": cm.terms_hash,
                        "nonce": cm.nonce})
    if res["status"] == "PENDING_APPROVAL":  # lengthening terms is Tier 2: the owner approves
        res = c.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
    return res


def show(v):
    vals = [(cv["obligation_id"], cv["value_fen"], cv.get("formula", "")[:90]) for cv in v.get("concession_values", [])]
    print("   verdict", v["outcome"], "| forward total", v.get("forward_concession_total_fen"),
          "| codes", sorted({x["code"] for x in v.get("violations", [])}), "|", vals)


rt, c = fresh()
cap = rt.store.get_mandate().max_aggregate_forward_concession_fen
print("aggregate cap", fmt_yuan(cap))
print("A. one agreement: +15 days on the next three invoices")
v = offer(c, "Give us 60 days instead of 45 on the next three invoices. Nothing else changes.")
show(v)
if v["outcome"] in ("ACCEPT", "NEEDS_OWNER_APPROVAL"):
    print("   accept:", accept(c, rt, v, "A")["message"][:200])

print("B. the same, one invoice at a time")
rt, c = fresh()
written = []
for i in range(3):
    v = offer(c, "Give us 60 days instead of 45 on the next invoice. Nothing else changes.")
    show(v)
    if v["outcome"] not in ("ACCEPT", "NEEDS_OWNER_APPROVAL"):
        break
    r = accept(c, rt, v, f"B{i}")
    print(f"   day {rt.day} accept #{i + 1}:", r["status"], r["message"][:160])
    s = rt.store.get_state()
    print("   booked forward concessions", fmt_yuan(sum(fc.value_fen for fc in s.forward_concessions)))
    advance(c, rt.day + 30 if i else 3)  # the next recurring invoice issues; the one-off is consumed
    s = rt.store.get_state()
    print("   commitments", {x.id: x.status.value for x in rt.store.commitments()},
          "| booked after issue", fmt_yuan(sum(fc.value_fen for fc in s.forward_concessions)))
    written = [(r.id, r.terms_days, r.applied) for r in s.receivables if r.applied]
print("invoices carrying an accepted extension:", written)
