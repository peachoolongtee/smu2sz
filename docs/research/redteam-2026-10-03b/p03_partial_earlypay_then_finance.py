"""Seam: an accepted partial early-pay agreement (the agent's own counter on EX02) + an advance on the rest of the
same invoice.

The projection (admission, planner, alerts) books the early receipt to the owner and the advance landing as two
independent inflows. The executor applies a receipt on a FINANCED invoice to the advance first, and a receipt that
arrives before the advance lands cancels the advance outright. Let exactly the projected receipts happen, one day at
a time, and compare the actual closing cash with the projection the advance was admitted on.
"""
from _harness import *  # noqa: F403


def setup(finance_day: int):
    rt, c = fresh()
    r = c.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"})
    offer = r.json()["offer"]
    v = c.post(f"/offers/{offer['offer_id']}/evaluate", headers=OWNER, json={"fixture_id": "EX02_EARLY_1_5"}).json()
    counter = v["counters"][0]
    print("verdict", v["outcome"], "counter:", counter["label"], counter["text"])
    # what the agent does when the buyer takes Option A (app/nl/pipeline.accept): propose, then AcceptOffer
    cm = rt.executor.propose_commitment(v["id"], expires_day=7, counter_id=counter["id"])
    res = op(c, AGENT, {"kind": "ACCEPT_OFFER", "op_id": "acc-1", "requested_by": "AGENT", "source_verdict_id": v["id"],
                        "offer_id": cm.offer_id, "offer_version": cm.offer_version, "terms_hash": cm.terms_hash,
                        "nonce": cm.nonce})
    ob = cm.obligations[0]
    print("accept:", res["status"], res["tier"], "|", ob.type.value, ob.base.receivable_id, fmt_yuan(ob.base.amount_fen),
          f"{ob.rate_bp}bp", "settles day", ob.effective_day)
    if finance_day:
        advance(c, finance_day)
    # the residual of RCV-A (face 420,000 less the 211,900 settled early) at the facility's 80% advance rate
    res = op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-rest", "requested_by": "AGENT",
                        "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 16648000})
    print("finance residual:", res["status"], res["tier"], res["message"])
    return rt, c


rt, c = setup(0)
snap(rt, "day 0 after both")
t = projection(rt)
m = rt.store.get_mandate()
print("projection on day 0: day 2", fmt_yuan(closing(t, 2)), "| day 3", fmt_yuan(closing(t, 3)), "| day 12 (payroll)",
      fmt_yuan(closing(t, 12)), "| day 20", fmt_yuan(closing(t, 20)), "| first reserve breach", t.first_breach_day,
      "| reserve", fmt_yuan(m.min_cash_fen))
diffs = live(c, rt, t, 33)
snap(rt, "day 33")
print("lots", lots(rt), "conservation", conservation(rt))
for d, want, got in diffs:
    if d in (2, 3, 12, 20, 31, 32):
        print(f"  day {d}: projected closing {fmt_yuan(want)}  actual {fmt_yuan(got)}  (actual - projected "
              f"{fmt_yuan(got - want)})")
worst = min((got for _, _, got in diffs), default=None)
check("actual daily closings equal the projection the advance was admitted on", bool(diffs))
check("actual cash fell below the reserve on a day the projection said it would hold",
      worst is not None and worst < m.min_cash_fen and t.first_breach_day is None)
alerts = c.get("/alerts", headers=OWNER).json()
print("alerts on day 33:", [(a.get("kind"), a.get("severity")) for a in alerts.get("alerts", [])][:8])

print("\nB. Same rule without any agreement: a 1-fen receipt before landing deletes a ¥336,000 advance")
rt, c = fresh()
op(c, AGENT, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "fin-A", "requested_by": "AGENT",
              "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 33600000})
advance(c, 1)
before = snap(rt, "day 1 (advance requested day 0, lands day 3)")
lots_before = lots(rt)
res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-1fen", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
                   "amount_fen": 1})
print("bank feed: 1 fen from the buyer:", res["status"], res["message"])
after = snap(rt, "after the 1-fen receipt")
al = c.get("/alerts", headers=OWNER).json().get("alerts", [])
print("alerts right after:", [(a.get("kind"), a.get("severity"), (a.get("title") or "")[:80]) for a in al])
advance(c, 4)
landed = snap(rt, "day 4 (the advance was due to land on day 3)")
print("lots before", lots_before, "after", lots(rt))
check("a 1-fen receipt cancelled the whole pledged ¥336,000 advance; no cash landed on day 3",
      not lots(rt) and landed["cash"] == before["cash"] + 1)
