"""The router's committed plan can rely on the buyer's standing early-pay facility. No operation requests it: a
go-ahead sends the draw and the advance only, and says the plan ran. Does the breach the plan was sized for remain?"""
from _harness import *
from app.domain.models import LedgerEventKind as K

rt, c = fresh()
v = evaluate_fixture(c, "EX01_PACKAGE")
b = next(k for k in v["counters"] if "terms" in k["text"])
res, cm = commit_counter(c, v["id"], b["id"], "optB")
if res["status"] == "PENDING_APPROVAL":
    res = approve(c, res["approval_id"])
print("Option B:", res["status"], b["text"][:90])
plan = c.post("/router/plan", headers=OWNER).json()["committed"]
print("router plan:", [(a["kind"], a["facility_id"], a.get("receivable_id"), a["amount_fen"]) for a in plan["actions"]],
      "admissible", plan["admissible"], "executable_now", plan.get("executable_now"),
      "needs_owner_approval", plan.get("needs_owner_approval"))
t0 = projection(rt)
print("before: first breach", t0.first_breach_day, "lowest", t0.min_cash_fen, "day", t0.min_cash_day)

out = nl(c, OWNER, "fund the cash gap", session_id="p09")
print("proposal:", out["reply"][:400].replace("\n", " | "))
out = nl(c, OWNER, "3", session_id="p09")
print("pick 3:", out["reply"][:600].replace("\n", " | "))
out = nl(c, OWNER, "go ahead", session_id="p09")
print("go ahead:", out["reply"][:500].replace("\n", " | "))
print("ops:", [(o.get("kind"), o.get("status")) for o in out.get("operations", [])])
snap(rt, "after go-ahead")
t1 = projection(rt)
print("after: first breach", t1.first_breach_day, "lowest", t1.min_cash_fen, "day", t1.min_cash_day)
al = c.get("/alerts", headers=OWNER).json()
print("alerts:", [(a["kind"], a["title"]) for a in al["alerts"] if a["severity"] == "CRITICAL"])
ran = [o for o in out.get("operations", []) if o.get("status") == "EXECUTED"]
check("the go-ahead ran the plan's legs yet a reserve breach the plan was sized to cure is still projected",
      bool(ran) and t1.first_breach_day is not None and any(a["kind"] == "EARLY_PAY" for a in plan["actions"]))
