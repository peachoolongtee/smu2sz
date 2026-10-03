"""EX01 evaluated and negotiated on days other than 0: do the counters' promises hold once accepted?

For each start day: the clock is run there with exactly the projected receipts; EX01 is posted, evaluated and
negotiated with the cooperative buyer. Printed: the verdict, each counter, what /negotiate executed, and the
conservative projection on current books right after the deal (first reserve breach, low), plus whether the
accepted counter re-verifies on the books it was accepted on."""
import sys

from _harness import *  # noqa
from app.domain.models import Commitment

days = [int(x) for x in sys.argv[1:]] or [0, 10, 25, 29, 30, 31, 34, 44, 59]
for start in days:
    print("=" * 30, "day", start)
    rt, c = fresh()
    t0 = projection(rt)
    live(c, rt, t0, start, tag=f"pre{start}")
    r = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"})
    oid = r.json()["offer"]["offer_id"]
    v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()
    print("verdict", v["outcome"], "| codes", sorted({x["code"] for x in v["violations"]}))
    for k in v["counters"]:
        print("  COUNTER", k["label"], "|", k["text"])
    before = projection(rt)
    print(f"  before deal: first breach {before.first_breach_day}, low {before.min_cash_fen} on day {before.min_cash_day}")
    if not v["counters"]:
        continue
    n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    print("  NEGOTIATION", n["outcome"], "|", n["message"])
    for o in n["operations"]:
        print("    op", o["kind"], o["status"], o["message"][:160])
    after = projection(rt)
    print(f"  after deal: first breach {after.first_breach_day}, low {after.min_cash_fen} on day {after.min_cash_day}; "
          f"commitments {[(x.id, x.status.value) for x in rt.store.commitments()]}")
    if n.get("commitment"):
        cm = rt.store.get_commitment(n["commitment"]["id"])
        for o in cm.obligations:
            print("    obl", o.type.value, o.rate_bp, o.base.amount_fen, o.base.receivable_id, "eff", o.effective_day,
                  "dd", o.days_delta)
    check(f"day {start}: a deal leaves the conservative projection below the reserve with nothing executed to cure it",
          n["outcome"] == "DEAL" and after.first_breach_day is not None
          and not any(o["kind"] in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING") and o["status"] == "EXECUTED"
                      for o in n["operations"]))
    print("  chain", rt.store.verify_chain(), "conservation", conservation(rt))
