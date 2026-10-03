"""Baseline: golden books at day 0, projection, months, alerts, router plan."""
from _harness import *

rt, c = fresh()
s = snap(rt, "start")
t = projection(rt)
print("first breach", t.first_breach_day, "min", t.min_cash_fen, t.min_cash_day, "H", t.horizon_days)
for m in t.months:
    print(" month", m.month, "DS", m.debt_service_fen, "debt", m.total_debt_fen, "dscr", m.dscr, "lev", m.leverage)
r = c.get("/alerts", headers=OWNER).json()
print(type(r), list(r.keys()) if isinstance(r, dict) else None)
al = r if isinstance(r, list) else r.get("alerts", [])
for a in al:
    print(" alert", {k: a.get(k) for k in ("id", "kind", "severity", "title")})
r = c.post("/router/plan", headers=OWNER).json()
print(" plan", {k: v for k, v in r["committed"].items() if k in ("actions", "total_cost_fen", "cost_fen", "admissible")})
