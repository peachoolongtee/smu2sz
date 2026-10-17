#!/usr/bin/env python3
"""Evidence pack section 6, read-only: the golden capex case's 36-month loan plus a small credit-line bridge, against the
selected 48-month lease. Uses the screen's own pieces (`app.capex.evaluate._Base`, `_purchase_flows`, the same granted
copy of FAC-ETL as `_liquidity`) and the engine's `project`; the bridge is an extra FundingAction DRAW on the committed
line. Nothing here is a product path: the capex screen itself never builds this combination.

  LLM_MODE=cache TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 \
    uv run --project services/api python scripts/analysis/capex_bridge.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from app.books import current_books
    from app.capex import CapexRequest, evaluate_capex
    from app.capex.evaluate import _Base, _purchase_flows
    from app.covenants.evaluate import evaluate as cov
    from app.domain.fixtures import load_scenario
    from app.domain.models import FacilityStatus, FundingAction, FundingActionKind, Mode
    from app.financial import project
    from app.mandate import load_signed_mandate

    s, _ = load_scenario()
    m = load_signed_mandate()
    req = CapexRequest()
    res = evaluate_capex(req, s, m)
    by = {x.id: x for x in res.structures}
    for k in ("cash_line", "loan_18m", "loan_36m", "lease_48m"):
        x = by.get(k)
        if x:
            print(k, x.result, "charges", x.charges_total_fen, "interest", x.total_interest_fen, "fee", getattr(x, "upfront_fee_fen", None),
                  "viol", [(v.code.value, v.day, v.observed) for v in x.violations])
    print("selected", res.selected_id)
    base = _Base(current_books(s, []), m)
    etl = next(f for f in s.facilities if f.id == "FAC-ETL")
    line = next(f for f in s.facilities if f.id == "FAC-LINE")
    print("FAC-LINE", line.status, line.limit_fen, line.drawn_fen, line.rate_bp, line.lead_time_days, line.repayment)
    land = s.as_of_day + etl.lead_time_days
    granted = etl.model_copy(update={"status": FacilityStatus.COMMITTED, "owner_approved": True, "term_months": 36})
    sc = s.model_copy(update={"flows": [*s.flows, *_purchase_flows(req, land)],
                              "facilities": [granted if x.id == etl.id else x for x in s.facilities]})
    loan = FundingAction(kind=FundingActionKind.DRAW, facility_id=etl.id, day=s.as_of_day, amount_fen=req.price_fen)

    def run(extra):
        t = project(sc, base.obligations, [loan, *extra], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
        days = [p for p in t.days if p.day >= s.as_of_day]
        return t, days, base.breach_day(days)

    t0, d0, b0 = run([])
    print("loan only: breach day", b0, "closing", {p.day: p.closing_fen / 100 for p in d0 if p.day in (40, 43, 44, 45, 62, 74)})
    best = None
    for repay in range(45, m.horizon_days):
        for amt in (314462, 400000, 500000, 1000000):
            act = FundingAction(kind=FundingActionKind.DRAW, facility_id=line.id, day=44, amount_fen=amt, repay_day=repay)
            try:
                t, d, b = run([act])
            except Exception as e:  # engine refusal
                print("refused", amt, repay, e)
                continue
            if b is None:
                interest = sum(c for c in [getattr(t, "posted_costs_fen", None)] if c) if False else None
                best = (amt, repay, t, d)
                break
        if best:
            break
    if not best:
        print("no bridge found on this grid")
        return 0
    amt, repay, t, d = best
    from app.financial.charges import line_interest
    li = line_interest(amt, line.rate_bp, repay - 44)
    covs = cov(t, list(sc.facilities), m)
    print(f"bridge: draw {amt/100:,.2f} on {line.id} day 44, repaid day {repay}; interest {li/100:,.2f} "
          f"(= {amt/100:,.2f} x {line.rate_bp/100}% x {repay-44}/365)")
    print("lowest after bridge", min(p.closing_fen for p in d) / 100, "covenant violations", [(v.code.value, v.month, str(v.observed)) for v in covs])
    loan36 = by["loan_36m"].charges_total_fen
    lease = by["lease_48m"].charges_total_fen
    print(f"36m loan charges {loan36/100:,.2f} + bridge {li/100:,.2f} = {(loan36+li)/100:,.2f} vs lease {lease/100:,.2f}; "
          f"difference {(lease-loan36-li)/100:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
