"""Engine side of the financial audit: read every audited figure from the engine's own modules, in process.

Run from the repo root (no server, no port, no live model):

    DEMO_MODE=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \
        uv run --project services/api python docs/deliverables/submission/work/fin/engine_probe.py

Writes engine_values.json next to this file. Read-only: it changes no application code and no fixture.
The independent recomputation is independent.py (pure Python, reads only the fixture JSON).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for k, v in {"DEMO_MODE": "1", "TERMSLEDGER_NO_DOTENV": "1", "DATABASE_URL": "memory", "LLM_MODE": "cache"}.items():
    os.environ.setdefault(k, v)
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.capex import CapexRequest, evaluate_capex  # noqa: E402
from app.compiler import compile_offer  # noqa: E402
from app.covenants import pro_forma, ratios_for  # noqa: E402
from app.domain.fixtures import load_scenario, offer_documents  # noqa: E402
from app.domain.models import FundingActionKind, Mode, ObligationType  # noqa: E402
from app.financial import project  # noqa: E402
from app.funding import break_even_discount, marginal_cost, plan  # noqa: E402
from app.mandate import demo_owner_public_key_hex, load_signed_mandate  # noqa: E402
from app.verifier import evaluate  # noqa: E402

OUT = Path(__file__).with_name("engine_values.json")


def days(traj, lo=0, hi=None):
    hi = traj.horizon_days if hi is None else hi
    return [{"day": p.day, "closing_fen": p.closing_fen, "debt_fen": p.debt_outstanding_fen,
             "events": [(e.kind.value, e.amount_fen, e.label, e.ref) for e in p.events]}
            for p in traj.days if lo <= p.day <= hi]


def months(traj):
    return [{"month": m.month, "ebitda_fen": m.ebitda_fen, "debt_service_fen": m.debt_service_fen,
             "total_debt_fen": m.total_debt_fen, "dscr": m.dscr.text if m.dscr else None,
             "leverage": m.leverage.text if m.leverage else None} for m in traj.months]


def actions(acts):
    return [{"kind": a.kind.value, "facility": a.facility_id, "day": a.day, "amount_fen": a.amount_fen,
             "repay_day": getattr(a, "repay_day", None), "receivable": getattr(a, "receivable_id", None)}
            for a in acts]


def main() -> None:
    state, _ = load_scenario()
    m = load_signed_mandate()
    key = demo_owner_public_key_hex()
    H = m.horizon_days
    out: dict = {}

    base = project(state, [], [], Mode.CONSERVATIVE, H, m.min_cash_fen)
    out["baseline"] = {"min_cash_fen": base.min_cash_fen, "min_cash_day": base.min_cash_day,
                       "first_breach_day": base.first_breach_day, "days": days(base), "months": months(base)}

    p = plan(state, [], m)
    out["standing_plan"] = {"total_cost_fen": p.total_cost_fen, "need_fen": p.need_fen,
                            "costs": {c.facility_id: c.fen for c in p.costs}, "actions": actions(p.actions)}
    tp = project(state, [], list(p.actions), Mode.CONSERVATIVE, H, m.min_cash_fen)
    out["standing_plan"]["trajectory"] = {"min_cash_fen": tp.min_cash_fen, "min_cash_day": tp.min_cash_day,
                                          "first_breach_day": tp.first_breach_day,
                                          "interest": tp.interest_posted_fen, "fees": tp.fees_posted_fen,
                                          "days": days(tp), "months": months(tp)}

    d, be_bp = break_even_discount(state, m)
    rate, src = marginal_cost(state, m)
    out["break_even"] = {"exact": str(d.value), "bp_trunc": be_bp, "marginal_rate": str(rate.value), "source": src}

    ex01 = compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1")
    b1 = evaluate(ex01, state, m, trusted_owner_key_hex=key)
    v = b1.verdict
    out["ex01"] = {
        "outcome": v.outcome.value if hasattr(v.outcome, "value") else str(v.outcome),
        "codes": [x.code.value for x in v.violations],
        "forward_concession_total_fen": v.forward_concession_total_fen,
        "concession_values": [{"id": cv.obligation_id, "value_fen": cv.value_fen, "per_invoice_fen": cv.per_invoice_fen,
                               "basis": cv.basis, "formula": cv.formula} for cv in v.concession_values],
        "violations": [{"code": x.code.value, "observed": x.observed, "limit": x.limit, "formula": x.formula,
                        "inputs": x.inputs, "cure_cost_fen": getattr(x, "cure_cost_fen", None),
                        "day": getattr(x, "day", None)} for x in v.violations],
        "passed": [{"code": pc.code, "observed": pc.observed, "inputs": pc.inputs} for pc in b1.passed_checks],
        "obligations": [{"type": o.type.value, "rate_bp": o.rate_bp, "days_delta": o.days_delta,
                         "amount_fen": o.amount_fen, "base_amount_fen": o.base.amount_fen,
                         "receivable": o.base.receivable_id} for o in b1.bound_obligations],
        "comparison": [{"key": r.key, "cost_fen": r.cost_fen, "actions": actions(r.actions)} for r in b1.comparison],
    }
    t1 = b1.trajectory
    out["ex01"]["trajectory"] = {"min_cash_fen": t1.min_cash_fen, "min_cash_day": t1.min_cash_day,
                                 "first_breach_day": t1.first_breach_day, "days": days(t1), "months": months(t1)}
    counters = []
    for c in v.counters:
        row = {"label": c.label, "text": getattr(c, "text", None), "supplier_cost_fen": c.supplier_cost_fen,
               "obligations": [{"type": o.type.value, "rate_bp": o.rate_bp, "days_delta": o.days_delta,
                                "base_amount_fen": o.base.amount_fen, "receivable": o.base.receivable_id}
                               for o in c.obligations]}
        for attr in ("funding_actions", "plan_actions", "actions"):
            if getattr(c, attr, None):
                row["actions"] = actions(getattr(c, attr))
        extra = {k: val for k, val in c.model_dump().items()
                 if k not in ("obligations", "text", "label") and not isinstance(val, (list, dict))}
        row["fields"] = extra
        cb = evaluate(c.offer, state, m, trusted_owner_key_hex=key) if getattr(c, "offer", None) else None
        if cb is not None and cb.trajectory is not None:
            row["reeval"] = {"outcome": str(cb.verdict.outcome), "codes": [x.code.value for x in cb.verdict.violations],
                             "forward_total": cb.verdict.forward_concession_total_fen,
                             "concession_values": [(cv.obligation_id, cv.value_fen, cv.formula)
                                                   for cv in cb.verdict.concession_values],
                             "min_cash_fen": cb.trajectory.min_cash_fen, "min_cash_day": cb.trajectory.min_cash_day,
                             "days": days(cb.trajectory)}
        counters.append(row)
    out["ex01"]["counters"] = counters

    dscr_b, _ = pro_forma(state)
    _, lev_b = ratios_for(base.months[0])
    out["covenants"] = {"dscr_pro_forma": dscr_b.text if dscr_b else None, "leverage_month1_untouched": lev_b.text,
                        "plan_months": months(tp)}

    cap = evaluate_capex(CapexRequest(), state, m)
    out["capex"] = json.loads(cap.model_dump_json())
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
