"""The router plans a cheap credit-line draw that cures a payroll breach; the executor refuses it.

Commit 11acc56 makes admission judge a line draw as "the carried lot it becomes": `_as_carried` adds the lot and the
drawn balance but not the lot's cash (a lead-0 lot is created `settled=True`, so the engine never lands it). The
admission's "after" projection is therefore short by the whole draw from today until the repayment, and the carried
lot is repaid at the horizon with 120 days of interest. Whenever the cash left at the horizon (without the draw) lies
between floor + the plan's interest and floor + a full horizon's interest, the plan the router presents as runnable
and needing no approval is refused at its first leg.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _harness import *  # noqa: E402,F403
from app.domain.models import CashFlow, FlowKind  # noqa: E402

rt, c = fresh()
s = rt.store.get_state()
payroll = next(f for f in s.flows if f.id == "F-PAYROLL").model_copy(update={"amount_fen": -20_000_000})
extra = CashFlow(id="F-TAX", day=40, amount_fen=-31_850_000, kind=FlowKind.OTHER, label="tax payment", confirmed=True)
rt.store.put_state(s.model_copy(update={"flows": [payroll, extra], "recurring_invoices": [ri.model_copy(update={"next_issue_day": 150}) for ri in s.recurring_invoices]}))
print("setup: cash 400k; payroll -200k day 12; RCV-A +420k day 32; tax -318.5k day 40; recurring invoices start day 150, past the horizon")
t0 = projection(rt)
print("before: lowest", t0.min_cash_fen, "on day", t0.min_cash_day, "| day-12 close", closing(t0, 12), "| day-120 close", closing(t0, 120))

p = c.post("/router/plan", headers=OWNER).json()["committed"]
print("router plan:", p["label"], "| admissible", p["admissible"], "| needs owner", p["needs_owner_approval"],
      "| executable now", p["executable_now"], "| cost", p["total_cost_fen"])
for a in p["actions"]:
    print("   leg", a["kind"], a["facility_id"], a.get("receivable_id"), a["amount_fen"], "day", a["day"], "repay", a.get("repay_day"))

# what the plan promises (its own projection with the plan's actions)
from app.funding import plan as route  # noqa: E402
books = current_books(rt.store.get_state(), rt.store.commitments())
m = rt.store.get_mandate()
acts = list(route(books.state, books.with_([]), m).actions)
tp = project(books.state, list(books.obligations), acts, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
print("plan projection: lowest", tp.min_cash_fen, "on day", tp.min_cash_day)

# the owner says "fund the gap" then "go ahead" in chat
r1 = nl(c, OWNER, "fund the gap", session_id="own-1", request_id="q1")
print("chat 1:", r1["reply"][:400])
r2 = nl(c, OWNER, "go ahead", session_id="own-1", request_id="q2")
print("chat 2:", r2["reply"][:600])
for o in r2["operations"]:
    print("   op", o["kind"], o["status"], o["message"][:300])
after = snap(rt, "after go-ahead")
t1 = projection(rt)
print("books after: lowest", t1.min_cash_fen, "on day", t1.min_cash_day)
refused = any(o["status"] == "REFUSED" for o in r2["operations"])
check("a runnable, unflagged router plan is refused by the executor at a line draw", refused and p["executable_now"]
      and not p["needs_owner_approval"] and tp.min_cash_fen >= m.min_cash_fen)
check("the payroll breach the plan cured is still on the books", t1.min_cash_fen < m.min_cash_fen)
print("verify_chain", rt.store.verify_chain())
