#!/usr/bin/env python3
"""Autonomy funnel on the held-out offer sets (evidence pack, section 2). Read-only: no product code changes.

Runs the same pipeline as `evals/suites/offers.py` (compile_offer in LLM_MODE=cache, then the verifier on the golden
state with the signed demo mandate) and, per offer, also records the verdict's required tier and the funding plan's
needs-owner flag, which is how the product decides "FLOW may act" vs "needs your approval"
(`app/api/offer_picture.py::_asked_authority`).

Usage (repo root):
  LLM_MODE=cache TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 \
    uv run --project services/api python scripts/analysis/autonomy_funnel.py fixtures/heldout3 fixtures/heldout2 --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
os.environ.setdefault("LLM_MODE", "cache")
os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")

ESCALATE = {"NO_VERDICT", "NEEDS_OWNER_APPROVAL"}


def run_set(path: str) -> dict:
    from app.compiler import compile_offer
    from app.domain.fixtures import load_scenario
    from app.domain.models import Tier
    from app.mandate import demo_owner_public_key_hex, load_signed_mandate
    from app.verifier import evaluate
    from app.verifier.evaluate import autonomy_gaps
    from evals.common import quiet
    from evals.suites.offers import UNLABELLED, compare, documents, load

    quiet()
    items, _ = load(ROOT / path)
    state, _ = load_scenario()
    m = load_signed_mandate()
    key = demo_owner_public_key_hex()
    rows = []
    for it in items:
        exp = it["expect"]
        cp = it.get("counterparty_id", "BUYER-1")
        offer = compile_offer(documents(it), cp)
        b = evaluate(offer, state, m, trusted_owner_key_hex=key, owner_declared=it.get("declared_costs"))
        v = b.verdict
        out = v.outcome.value
        booked = [] if out == "NO_VERDICT" else list(b.bound_obligations)
        labels = exp.get("booked", [])
        errs = [] if out == "NO_VERDICT" else compare(booked, labels)
        tier1 = v.required_tier == Tier.TIER_1
        plan_owner = bool(v.plan is not None and getattr(v.plan, "needs_owner_approval", False))
        autonomous = out == "ACCEPT" and tier1 and not plan_owner
        # eligible: labelled ACCEPT, the booked label is a pure early-pay (IMMEDIATE_DISCOUNT only), no claims
        pure_ep = bool(labels) and all(lb["type"] == "IMMEDIATE_DISCOUNT" for lb in labels) and not exp.get("claims")
        eligible = exp["outcome"] == "ACCEPT" and pure_ep
        if autonomous:
            handling = "autonomous_accept"
        elif out in ESCALATE or out == "ACCEPT":  # ACCEPT that needs Tier 2 / owner plan = an escalation
            handling = "escalated"
        else:
            handling = "autonomous_" + out.lower()  # COUNTER / REJECT / NO_DEAL handled without the owner
        rows.append({
            "id": it["id"], "kind": it["kind"], "label": exp["outcome"], "label_abstain": bool(exp.get("abstain")),
            "eligible": eligible, "outcome": out, "required_tier": v.required_tier.value if v.required_tier else None,
            "plan_needs_owner": plan_owner, "autonomous": autonomous, "handling": handling,
            "compiler": offer.compiler, "material_errors": [e["what"] for e in errs],
            "codes": sorted({x.code.value for x in v.violations}),
            "autonomy_gaps": autonomy_gaps(offer, booked, state) if booked else [],
            "summary": str(getattr(v, "summary", ""))[:300],
        })
    elig = [r for r in rows if r["eligible"]]
    auto_acc = [r for r in rows if r["handling"] == "autonomous_accept"]
    esc = [r for r in rows if r["handling"] == "escalated"]
    f = {
        "set": path, "offers": len(rows),
        "labelled": sum(r["label"] != UNLABELLED for r in rows),
        "eligible_pure_early_pay_accept": len(elig),
        "eligible_handled_autonomously_correctly": sum(r["autonomous"] and not r["material_errors"] for r in elig),
        "eligible_escalated_unnecessarily": sum(r["handling"] == "escalated" for r in elig),
        "eligible_other": {r["id"]: r["outcome"] for r in elig if r["handling"] not in ("escalated", "autonomous_accept")},
        "escalations_total": len(esc),
        "escalated_correctly": sum(not r["eligible"] for r in esc),
        "escalated_correctly_label_also_escalates": sum(r["label"] in ESCALATE for r in esc),
        "autonomous_accepts_total": len(auto_acc),
        "wrong_autonomous_accepts": [r["id"] for r in auto_acc if r["label"] != "ACCEPT" or r["material_errors"]],
        "non_accept_autonomous": {k: sum(r["handling"] == k for r in rows)
                                  for k in sorted({r["handling"] for r in rows}) if k not in ("escalated", "autonomous_accept")},
        "owner_interactions_1_per_escalation": len(esc),
        "compilers": sorted({r["compiler"] for r in rows}),
    }
    return {"funnel": f, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sets", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for s in a.sets:
        r = run_set(s)
        (out / f"funnel_{Path(s).name}.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(r["funnel"], indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
