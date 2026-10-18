"""Engine side, part 3: the legs behind Table 7's early-payment test (C1 ¥6,508.05 against C0 ¥3,873.58).

    DEMO_MODE=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \
        uv run --project services/api python docs/deliverables/submission/work/fin/engine_probe3.py
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

from app.compiler import compile_offer  # noqa: E402
from app.domain.fixtures import load_scenario, offer_documents  # noqa: E402
from app.domain.models import Mode, ObligationType  # noqa: E402
from app.financial import project  # noqa: E402
from app.funding import plan  # noqa: E402
from app.mandate import demo_owner_public_key_hex, load_signed_mandate  # noqa: E402
from app.verifier import evaluate  # noqa: E402

state, _ = load_scenario()
m = load_signed_mandate()
b = evaluate(compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1"), state, m,
             trusted_owner_key_hex=demo_owner_public_key_hex())
obs = list(b.bound_obligations)
out = {}
for name, chosen in (("with_early_pay", obs), ("without_early_pay", [o for o in obs if o.type != ObligationType.IMMEDIATE_DISCOUNT])):
    p = plan(state, chosen, m)
    t = project(state, chosen, list(p.actions), Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    out[name] = {"total_fen": p.total_cost_fen, "costs": {c.facility_id: c.fen for c in p.costs},
                 "actions": [(a.kind.value, a.facility_id, a.day, a.amount_fen, a.repay_day, a.receivable_id)
                             for a in p.actions],
                 "discounts_fen": t.discounts_posted_fen, "min_cash_fen": t.min_cash_fen, "min_day": t.min_cash_day,
                 "events": [(pt.day, pt.closing_fen, [(e.kind.value, e.amount_fen, e.label[:40]) for e in pt.events])
                            for pt in t.days if pt.events and pt.day <= 95]}
Path(__file__).with_name("engine_values3.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
for k, v in out.items():
    print(k, v["total_fen"], v["costs"], v["actions"], v["discounts_fen"], v["min_cash_fen"], v["min_day"])
    for row in v["events"]:
        print("  ", row)
