"""Engine side, part 2: the questions the headline figures leave open.

1. Option B's own funding on current books (the counter says "supplier cost ¥0", but the books still need funding).
2. The capex lease on books where FLOW's standing plan has run (its ¥3,113.93 is paid in cash on day 32).
3. The demo story replayed day by day through the API in process (TestClient, memory database, cached compiler):
   the cash the owner actually sees each day and every charge actually posted.

Run from the repo root (no server, no port, no live model):

    DEMO_MODE=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \
        uv run --project services/api python docs/deliverables/submission/work/fin/engine_probe2.py

Writes engine_values2.json next to this file. Read-only for application code and fixtures.
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

from fastapi.testclient import TestClient  # noqa: E402

from app.api.runtime import get_runtime  # noqa: E402
from app.capex import CapexRequest, evaluate_capex  # noqa: E402
from app.compiler import compile_offer  # noqa: E402
from app.domain.fixtures import load_scenario, offer_documents  # noqa: E402
from app.domain.models import CashFlow, FlowKind, Mode  # noqa: E402
from app.domain.money import bp, post  # noqa: E402
from app.financial import project  # noqa: E402
from app.funding import plan  # noqa: E402
from app.main import app  # noqa: E402
from app.mandate import demo_owner_public_key_hex, load_signed_mandate  # noqa: E402
from app.verifier import evaluate  # noqa: E402

OUT = Path(__file__).with_name("engine_values2.json")
OWNER = {"X-Owner-Token": "demo-owner-token"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def ev_days(traj, lo=0, hi=200):
    return [{"day": p.day, "closing_fen": p.closing_fen,
             "events": [(e.kind.value, e.amount_fen, e.label) for e in p.events]}
            for p in traj.days if lo <= p.day <= hi and p.events]


def closings(traj):
    return [p.closing_fen for p in traj.days]


def main() -> None:
    state, _ = load_scenario()
    m = load_signed_mandate()
    key = demo_owner_public_key_hex()
    H = m.horizon_days
    out: dict = {}

    # 1. Option B
    ex01 = compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1")
    v = evaluate(ex01, state, m, trusted_owner_key_hex=key).verdict
    ob = next(c for c in v.counters if c.label == "Option B")
    oa = next(c for c in v.counters if c.label == "Option A")
    for name, c in (("option_a", oa), ("option_b", ob)):
        p = plan(state, list(c.obligations), m)
        t0 = project(state, list(c.obligations), [], Mode.CONSERVATIVE, H, m.min_cash_fen)
        t1 = project(state, list(c.obligations), list(p.actions), Mode.CONSERVATIVE, H, m.min_cash_fen)
        out[name] = {
            "plan_total_fen": p.total_cost_fen, "need_fen": p.need_fen,
            "costs": {x.facility_id: x.fen for x in p.costs},
            "actions": [{"kind": a.kind.value, "facility": a.facility_id, "day": a.day, "amount_fen": a.amount_fen,
                         "repay_day": a.repay_day, "receivable": a.receivable_id} for a in p.actions],
            "unfunded": {"min": t0.min_cash_fen, "min_day": t0.min_cash_day, "first_breach": t0.first_breach_day,
                         "days": ev_days(t0, 0, 125), "closings": closings(t0)},
            "funded": {"min": t1.min_cash_fen, "min_day": t1.min_cash_day, "first_breach": t1.first_breach_day,
                       "discounts": t1.discounts_posted_fen, "interest": t1.interest_posted_fen,
                       "fees": t1.fees_posted_fen, "days": ev_days(t1, 0, 125), "closings": closings(t1),
                       "months": [(mm.month, mm.debt_service_fen, mm.total_debt_fen,
                                   mm.dscr.text if mm.dscr else None, mm.leverage.text if mm.leverage else None)
                                  for mm in t1.months]},
        }

    # standing plan closings and EX01 closings (for the chart)
    sp = plan(state, [], m)
    out["standing_plan_closings"] = closings(project(state, [], list(sp.actions), Mode.CONSERVATIVE, H, m.min_cash_fen))
    out["baseline_closings"] = closings(project(state, [], [], Mode.CONSERVATIVE, H, m.min_cash_fen))
    b1 = evaluate(ex01, state, m, trusted_owner_key_hex=key)
    out["ex01_closings"] = closings(b1.trajectory)

    # 2. capex on books where the standing plan's cash is in the books (as dated flows: the draws, the repayments and
    # the charges exactly as the plan posts them)
    line_int, if_int, if_fee = 84164, 163479, 63750
    flows = [
        CashFlow(id="AUDIT-LINE-IN", day=0, amount_fen=15_000_000, kind=FlowKind.OTHER, label="line draw (plan)"),
        CashFlow(id="AUDIT-IF-IN", day=3, amount_fen=25_500_000, kind=FlowKind.OTHER, label="IF advance (plan)"),
        CashFlow(id="AUDIT-LINE-OUT", day=32, amount_fen=-(15_000_000 + line_int), kind=FlowKind.OTHER,
                 label="line repay + interest (plan)"),
        CashFlow(id="AUDIT-IF-OUT", day=32, amount_fen=-(25_500_000 + if_int + if_fee), kind=FlowKind.OTHER,
                 label="IF repay + interest + fee (plan)"),
    ]
    planned = state.model_copy(update={"flows": [*state.flows, *flows]})
    cap0 = evaluate_capex(CapexRequest(), state, m)
    cap1 = evaluate_capex(CapexRequest(), planned, m)

    def summary(cap):
        return {"selected": cap.selected_id, "npv_fen": cap.npv_fen, "payback": cap.payback_month,
                "structures": [{"id": s.id, "result": str(s.result), "feasible": s.feasible,
                                "charges_fen": s.charges_total_fen, "payment_fen": s.monthly_payment_fen,
                                "violations": [(x.code.value, x.day, x.observed, x.message) for x in s.violations]}
                               for s in cap.structures]}
    out["capex_untouched_books"] = summary(cap0)
    out["capex_with_standing_plan_cash"] = summary(cap1)

    # 3. the demo replayed day by day
    rt = get_runtime()
    rt.reset()
    c = TestClient(app)
    log: list[dict] = []
    daily: dict[int, int] = {}

    def snap(label: str) -> None:
        s = rt.store.get_state()
        log.append({"day": s.as_of_day, "label": label, "cash_fen": s.cash_fen,
                    "drawn": {f.id: f.drawn_fen for f in s.facilities if f.drawn_fen}})
        daily[s.as_of_day] = s.cash_fen

    def advance(to: int) -> None:
        cur = rt.store.get_state().as_of_day
        for d in range(cur + 1, to + 1):
            c.post("/clock/advance", json={"to_day": d}, headers=OWNER)
            snap(f"clock to day {d}")

    def receipt(key_: str, rid: str, amount: int) -> dict:
        r = c.post("/operations", headers=BANK, json={
            "kind": "RECEIVE_PAYMENT", "op_id": key_, "idempotency_key": key_,
            "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
            "receivable_id": rid, "amount_fen": amount, "bank_reference": f"BANK-{key_}"}).json()
        res = r.get("result", r)
        log.append({"day": rt.store.get_state().as_of_day, "label": f"receipt {rid}", "message": res.get("message")})
        snap(f"after receipt {rid}")
        return res

    snap("day 0 open")
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
    n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    snap("after DEAL on Option A (line drawn)")
    com = rt.store.get_commitment(n["commitment"]["id"])
    obl = com.obligations[0]
    agreed = obl.base.amount_fen - post(bp(obl.rate_bp) * obl.base.amount_fen)
    advance(obl.effective_day)
    receipt("audit-r1", obl.base.receivable_id, agreed)
    advance(34)
    alerts34 = c.get("/alerts", headers=OWNER).json()
    log.append({"day": 34, "label": "alerts", "alerts": [(a["id"], a["title"], a["detail"]) for a in alerts34["alerts"]]})
    s34 = rt.store.get_state()
    t34 = project(s34, [], [], Mode.CONSERVATIVE, H, m.min_cash_fen)
    out["day34_projection"] = ev_days(t34, 34, 70)
    c.post("/nl/opener", json={"session_id": "audit", "lang": "en"}, headers=OWNER)
    g = c.post("/nl", json={"session_id": "audit", "actor": "OWNER", "text": "go ahead"}, headers=OWNER).json()
    aid = next(x["approval_id"] for x in g["operations"] if x.get("approval_id"))
    c.post("/nl", json={"session_id": "audit", "actor": "OWNER", "text": f"approve {aid}"}, headers=OWNER)
    snap("after approval of the cure")
    advance(36)
    rcva = next(r for r in rt.store.get_state().receivables if r.id == obl.base.receivable_id)
    receipt("audit-r2", rcva.id, rcva.outstanding_fen)
    advance(47)
    fin = next(r for r in rt.store.get_state().receivables if r.status == "FINANCED")
    receipt("audit-r3", fin.id, fin.outstanding_fen)
    c.post("/nl/opener", json={"session_id": "audit", "lang": "en"}, headers=OWNER)
    rp = c.post("/nl", json={"session_id": "audit", "actor": "OWNER", "text": "go ahead"}, headers=OWNER).json()
    log.append({"day": 47, "label": "repay line", "reply": rp["reply"]})
    snap("after line repayment")
    advance(62)
    ledger = c.get("/ledger", headers=OWNER).json()["operations"]
    out["demo_log"] = log
    out["demo_daily_cash"] = daily
    out["demo_ledger"] = ledger
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
