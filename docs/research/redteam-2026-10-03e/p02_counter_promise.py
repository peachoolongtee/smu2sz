"""Counter A's written promise versus what the executor honours.

EX01 on day 0 -> /negotiate (cooperative buyer) -> the buyer accepts a counter. Print the counter text the buyer saw
and the commitment's obligations. Then the buyer pays the agreed discounted amount on days 3 and 5 (after the
commitment's hidden effective day but long before the invoice's due day 32), and, separately, a smaller early
settlement inside the "up to" face. Show how the books treat each."""
import sys

from _harness import *  # noqa
from app.alerts import reconcile

which = sys.argv[1] if len(sys.argv) > 1 else "late"


def setup():
    rt, c = fresh()
    r = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"})
    oid = r.json()["offer"]["offer_id"]
    v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()
    for k in v["counters"]:
        print("COUNTER", k["label"], "|", k["text"], "| blocked:", k["outbound_blocked"])
    n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    print("NEGOTIATION", n["outcome"], n["accepted_counter_id"], n["message"])
    for rd in n["rounds"]:
        print("  round", rd["round"], rd["counter_label"], rd["buyer_response"], "|", rd["buyer_text"][:160])
    for o in n["operations"]:
        print("  op", o["kind"], o["status"], o["message"][:200])
    return rt, c, n


rt, c, n = setup()
cm = rt.store.get_commitment(n["commitment"]["id"])
print("COMMITMENT", cm.id, cm.status.value)
for o in cm.obligations:
    print("  obligation", o.type.value, "rate_bp", o.rate_bp, "face", o.base.amount_fen, "on", o.base.receivable_id,
          "effective_day", o.effective_day, "| span:", o.spans[0].text)
ep = next(o for o in cm.obligations if o.type.value == "IMMEDIATE_DISCOUNT")
face = ep.base.amount_fen
disc = (face * ep.rate_bp + 5000) // 10000
agreed = face - disc
print(f"agreed early payment: face {face} - discount {disc} = {agreed}")
s0 = snap(rt, "after deal")

if which == "late":
    pay_day = 5
    advance(c, pay_day)
    print("commitment after closing day", pay_day - 1, ":", rt.store.get_commitment(cm.id).status.value,
          rt.store.get_commitment(cm.id).lapsed_obligations)
    res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-early", "requested_by": "SYSTEM",
                       "receivable_id": "RCV-A", "amount_fen": agreed, "bank_reference": "BR-1"})
    print("RECEIPT on day", pay_day, res["status"], res["message"])
else:
    pay_day = 1
    advance(c, pay_day)
    part = 10_000_000  # ¥100,000 of face settled early at the agreed rate, inside the "up to" face
    pdisc = (part * ep.rate_bp + 5000) // 10000
    res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-part", "requested_by": "SYSTEM",
                       "receivable_id": "RCV-A", "amount_fen": part - pdisc, "bank_reference": "BR-2"})
    print(f"RECEIPT on day {pay_day} of {part - pdisc} (¥100,000 face at the agreed rate):", res["status"], res["message"])

r = next(x for x in rt.store.get_state().receivables if x.id == "RCV-A")
print(f"RCV-A face {r.face_fen} settled {r.settled_fen} outstanding {r.outstanding_fen} status {r.status}")
rep = reconcile(rt.store, rt.day)
for m in rep.receipts:
    print("RECON", m.op_id, m.status.value, m.detail)
for p in rep.promised:
    print("PROMISE", p.status.value, p.detail)
c2 = rt.store.get_commitment(cm.id)
print("commitment now", c2.status.value, "lapsed", c2.lapsed_obligations)
check("the counter text the buyer accepted names no settlement day", f"day {ep.effective_day}" not in
      next(k for k in rt.store.get_verdict(cm.verdict_id).counters if k.id == n["accepted_counter_id"]).text.lower())
if which == "late":
    check(f"an early settlement on day {pay_day} (due day {r.due_day}) at the agreed rate leaves the agreed discount "
          f"{disc} owed by the buyer", r.outstanding_fen == 42_000_000 - agreed)
else:
    check("a partial early settlement inside the 'up to' face is not honoured: the discount stays owed",
          r.outstanding_fen == 42_000_000 - (part - pdisc))
print("chain", rt.store.verify_chain())
