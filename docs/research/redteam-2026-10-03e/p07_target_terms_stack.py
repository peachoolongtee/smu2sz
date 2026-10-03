"""A stated target term ("55-day terms", "50 days") is bound as a delta against the recurring invoice's ORIGINAL
terms, not against the contractual terms already in force, so a second agreement writes terms nobody agreed to.

1. Day 0: BUYER-1, on its authenticated channel, accepts the supplier's own Option B wording: 55-day terms with a
   0.30% price adjustment. The owner approves; future invoices are written at 55 days.
2. Day 1: BUYER-1 offers to SHORTEN terms back to 50 days ("Standard terms going forward: 50 days."). The verifier
   binds 50 - 45 (the recurring invoice's original terms) = +5 days and treats it as a further LENGTHENING; the owner
   approves "50-day terms".
3. The clock issues the next invoices: they carry 60-day terms (45 + 10 + 5), not the 50 days just agreed."""
import sys

from _harness import *  # noqa

second = sys.argv[1] if len(sys.argv) > 1 else "Standard terms going forward: 40 days."
rt, c = fresh()


def buyer_says(text, sid):
    out = nl(c, BUYER1, text, session_id=sid, actor="COUNTERPARTY")
    print(f"BUYER-1 > {text}\n   reply < {out['reply']}")
    for a in c.get("/approvals/queue", headers=OWNER).json()["approvals"]:
        if a["status"] != "PENDING":
            continue
        cm = next(x for x in rt.store.commitments() if x.status.value == "PROPOSED")
        v = rt.store.get_verdict(cm.verdict_id)
        print(f"   OWNER SEES {a['id']}: {a['reason']} | verdict {v.outcome.value}: {v.summary[:260]}")
        for o in cm.obligations:
            print(f"     obligation {o.type.value} target_terms {o.target_terms_days} days_delta {o.days_delta} "
                  f"rate_bp {o.rate_bp}")
        d = c.post(f"/approvals/{a['id']}", json={"decision": "APPROVE"}, headers=OWNER).json()["result"]
        print(f"   OWNER APPROVES {a['id']} -> {d['status']}: {d['message'][:200]}")


buyer_says("We accept 55-day terms with a 0.30% price adjustment on future invoices.", "b1-first")
s = rt.store.get_state()
print("adjustments in force:", [(a.id[-20:], a.days_delta, a.price_bp, a.from_issue_day) for a in s.invoice_adjustments])
advance(c, 1)
buyer_says(second, "b1-second")
s = rt.store.get_state()
print("adjustments in force:", [(a.id[-20:], a.days_delta, a.price_bp, a.from_issue_day) for a in s.invoice_adjustments])
t = projection(rt)
live(c, rt, t, 33, tag="s")
for r in rt.store.get_state().receivables:
    print(f"  {r.id}: issued day {r.issue_day}, terms {r.terms_days} days (base {r.base_terms_days}), face {r.face_fen} "
          f"(base {r.base_face_fen}), due day {r.due_day}, applied {[x[-8:] for x in r.applied]}")
ri = next(r for r in rt.store.get_state().receivables if r.id == "RI:BUYER-1:32")
import re  # noqa: E402

agreed = int(re.search(r"(\d+)[- ]days?", second).group(1))
sent = [e for e in rt.store.operations() if e.kind == "COUNTER_OFFER" and '"EXECUTED"' in e.result_json]
for e in sent:
    print("COUNTER SENT TO BUYER-1:", e.result_json[e.result_json.find('"message"'):][:200])
check("a counter sent to BUYER-1 says 'Terms stay at 45 days' while 55-day terms are in force",
      any("Terms stay at 45 days" in e.result_json for e in sent))
check(f"after agreeing 55-day terms and then '{second}', the next invoice is written with {ri.terms_days}-day terms, "
      f"not the {agreed} days agreed",
      len([x for x in rt.store.commitments() if x.status.value == "ACTIVE"]) == 2 and ri.terms_days != agreed)
print("chain", rt.store.verify_chain(), "conservation", conservation(rt))
