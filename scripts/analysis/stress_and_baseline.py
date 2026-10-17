#!/usr/bin/env python3
"""Evidence pack sections 5 and 7, read-only, on the golden books (no product code changes).

stress:   the golden state (`app.domain.fixtures.load_scenario`) and the signed demo mandate; each stress is a copy of the
          state (pydantic model_copy), read by the same kernel the product uses (`app.strategy.impact._read_kernel_uncached`:
          the router's committed plan + the CONSERVATIVE trajectory), plus `covenants.evaluate` on the funded projection.
baseline: the 26 funding scenarios of `evals/suites/funding.py` (10 designed + 16 seeded random, seed 20261001); the
          suite's own `line_first_baseline`, once as the suite runs it (every committed lever, including a buyer's early
          payment and bills, which no operation executes) and once restricted to the levers the agent can pull today
          (`levers(o, runnable_only=True)`), against the router's `plan`.

  LLM_MODE=cache TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 \
    uv run --project services/api python scripts/analysis/stress_and_baseline.py --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
os.environ.setdefault("LLM_MODE", "cache")
os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")


def yuan(f):
    return None if f is None else f"¥{f / 100:,.2f}"


def read(state, m):
    from app.covenants.evaluate import evaluate as cov
    from app.domain.models import Mode
    from app.financial import project
    from app.funding import plan
    from app.strategy.impact import _read_kernel_uncached

    r = _read_kernel_uncached(state, [], m)
    p = plan(state, [], m)
    funded = project(state, [], list(p.actions), Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen) if p.admissible else None
    fl = [d for d in funded.days if d.day >= state.as_of_day] if funded else []
    unf = project(state, [], [], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    covs = cov(funded or unf, list(state.facilities), m)
    months = [(mo.month, str(getattr(mo, "dscr", None)), str(getattr(mo, "leverage", None))) for mo in (funded or unf).months][:4]
    return {
        "lowest_unfunded": yuan(r.lowest_cash_fen), "lowest_day": r.lowest_day, "first_breach_day": r.first_breach_day,
        "breach_days": r.breach_days, "max_shortfall": yuan(max(0, m.min_cash_fen - r.lowest_cash_fen)),
        "need": yuan(r.need_fen), "plan_admissible": p.admissible, "plan_cost": yuan(p.total_cost_fen) if p.admissible else None,
        "plan_label": p.label, "plan_executable_now": p.executable_now, "plan_needs_owner": p.needs_owner_approval,
        "plan_actions": [(a.kind.value, a.facility_id, yuan(a.amount_fen), a.receivable_id, a.repay_day) for a in p.actions],
        "lowest_funded": yuan(min((d.closing_fen for d in fl), default=None)) if fl else None,
        "covenant_violations": [(v.code.value, str(v.observed), str(v.limit)) for v in covs],
        "months_dscr_leverage": months,
    }


def stresses(out: Path) -> dict:
    from app.books import current_books
    from app.domain.fixtures import load_scenario
    from app.mandate import load_signed_mandate
    from app.strategy.impact import stress

    s, _ = load_scenario()
    m = load_signed_mandate()
    rcv = next(r for r in s.receivables if r.id == "RCV-A")

    def with_rcv(**kw):
        recs = [r.model_copy(update=kw) if r.id == "RCV-A" else r for r in s.receivables]
        return s.model_copy(update={"receivables": recs})

    res = {
        "facts": {"RCV-A": {"face": yuan(rcv.face_fen), "issue_day": rcv.issue_day, "terms_days": rcv.terms_days,
                            "due_day": rcv.issue_day + rcv.terms_days, "status": rcv.status},
                  "monthly_ebitda": yuan(s.monthly_ebitda_fen), "min_cash": yuan(m.min_cash_fen), "as_of_day": s.as_of_day},
        "base": read(s, m),
        "rcv_a_10_days_late": read(with_rcv(terms_days=rcv.terms_days + 10), m),
        "rcv_a_half_received": read(with_rcv(face_fen=rcv.face_fen // 2), m),
        "ebitda_minus_20pct": read(s.model_copy(update={"monthly_ebitda_fen": s.monthly_ebitda_fen * 8 // 10}), m),
    }
    rows = stress(current_books(s, []), m, "BUYER-1", delays=(0, 10), day=s.as_of_day)
    res["product_stress_buyer1_all_invoices_late"] = [r.model_dump() for r in rows]
    return res


def baseline(out: Path) -> dict:
    import evals.suites.funding as F
    from app.funding import plan
    from evals.common import quiet

    quiet()
    rows = []
    for spec in F.scenarios(16):
        s, m = F.build(spec)
        p = plan(s, [], m)
        o = F.Oracle(s, m)
        bl_all = F.line_first_baseline(o)
        orig = F.levers
        with patch.object(F, "levers", lambda o_, runnable_only=False: orig(o_, runnable_only=True)):
            bl_run = F.line_first_baseline(F.Oracle(s, m))
        kinds = {a.kind.value for a in p.actions}
        future = [a.receivable_id for a in p.actions if a.receivable_id and a.receivable_id not in o.financeable
                  and a.kind.value == "FINANCE_INVOICE"]
        no_op = sorted(k for k in kinds if k in ("EARLY_PAY", "DISCOUNT_BILL"))
        if not p.admissible:
            cat = "no admissible plan"
        elif no_op:
            cat = "modelled, no operation exists (cannot run today)"
        elif future:
            cat = "needs a future event (invoice not yet issued)"
        elif p.needs_owner_approval:
            cat = "needs the owner"
        elif not p.executable_now:
            cat = "cannot run today (other)"
        else:
            cat = "executable now"
        rows.append({
            "id": spec["id"], "need": p.need_fen, "router_admissible": p.admissible,
            "router_cost": p.total_cost_fen if p.admissible else None, "router_executable_now": p.executable_now,
            "router_needs_owner": p.needs_owner_approval, "router_kinds": sorted(kinds), "future_receivables": future,
            "category": cat,
            "line_first_all_cost": bl_all["cost"], "line_first_all_actions": bl_all["actions"],
            "line_first_runnable_cost": bl_run["cost"], "line_first_runnable_actions": bl_run["actions"],
        })
    return {"rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", choices=["stress", "baseline"])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sys.stdout.reconfigure(encoding="utf-8")
    if a.only in (None, "stress"):
        r = stresses(out)
        (out / "stress.json").write_text(json.dumps(r, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        print(json.dumps(r, indent=1, ensure_ascii=False, default=str)[:6000])
    if a.only in (None, "baseline"):
        r = baseline(out)
        (out / "baseline.json").write_text(json.dumps(r, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        for x in r["rows"]:
            print(x["id"], x["category"], x["router_cost"], x["line_first_all_cost"], x["line_first_runnable_cost"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
