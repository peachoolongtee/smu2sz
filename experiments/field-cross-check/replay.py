"""Controlled replay of recorded readers through old/new checks and the unchanged verifier.

No provider calls, HTTP calls, database or product writes. This is a regression
experiment on known items, not a fresh live run or a complete workflow evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
os.environ["TERMSLEDGER_NO_DOTENV"] = "1"
os.environ["DATABASE_URL"] = "memory"
os.environ["LLM_MODE"] = "cache"
sys.path.insert(0, str(ROOT / "services/api"))

import structlog
import yaml
from app.compiler.cross_check import check_against_rules
from app.domain.fixtures import load_scenario
from app.domain.models import CompiledOffer
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate
from evals.live_frozen.run import score

BASE = "03215a2073a49e9bd72603561fcad67c3810c902"
SOURCE = ROOT / "services/api/evals/live_frozen"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore(item: dict[str, Any], row: dict[str, Any]) -> CompiledOffer:
    rec = row["record"]["reading"]
    obs = []
    for ob in rec["obligations"]:
        ob = {**ob, "counterparty_id": item["counterparty_id"]}
        ob["base"] = {k: v for k, v in ob["base"].items() if k != "amount_display"}
        obs.append(ob)
    return CompiledOffer.model_validate_json(json.dumps({
        **{k: rec[k] for k in ("offer_id", "compiler", "prompt_version", "status", "data_requests", "authority_claims",
                               "funding_claims", "autonomy_eligible", "autonomy_notes")},
        "counterparty_id": item["counterparty_id"], "received_day": 0,
        "doc_ids": [d["doc_id"] for d in item["documents"]], "obligations": obs,
        "abstentions": [{k: a[k] for k in ("field", "reason", "spans")} for a in rec["abstentions"]],
    }))


def assess(item: dict[str, Any], offer: CompiledOffer) -> dict[str, Any]:
    state, _ = load_scenario()
    state_before = state.model_dump_json()
    bundle = evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex())
    assert state.model_dump_json() == state_before, "evaluation changed the books"
    v = bundle.verdict
    rec = {
        "reading": {"kind": "offer", **offer.model_dump(mode="json")},
        "verdict": {"outcome": v.outcome.value, "codes": [x.code.value for x in v.violations],
                    "bound_obligations": [o.model_dump(mode="json") for o in bundle.bound_obligations],
                    "accepted_alone": False},
        "docs_sent": {d["doc_id"]: d["text"] for d in item["documents"]},
        "security_events": [], "books_delta": {},
    }
    result = score(item, rec)
    return {"class": result["class"], "score_notes": result["notes"], "compile_status": offer.status.value,
            "verdict": v.outcome.value, "autonomy_eligible": offer.autonomy_eligible,
            "codes": rec["verdict"]["codes"], "obligations": rec["reading"]["obligations"],
            "abstentions": rec["reading"]["abstentions"], "autonomy_notes": offer.autonomy_notes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    labels_path = SOURCE / "items.yaml"
    inputs = yaml.safe_load(labels_path.read_text())
    recordings = {}
    files = [labels_path]
    for mode in ("live_raw", "rules_baseline", "live"):
        path = SOURCE / f"results_{mode}_2026-10-18.json"
        files.append(path)
        result = json.loads(path.read_text())
        assert result["items_sha256"] == digest(labels_path), "labels do not match the recordings"
        recordings[mode] = result
    raw = {r["id"]: r for r in recordings["live_raw"]["items"]}
    rules = {r["id"]: r for r in recordings["rules_baseline"]["items"]}
    source = subprocess.check_output(["git", "show", f"{BASE}:services/api/app/compiler/cross_check.py"], cwd=ROOT, text=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix="flow-baseline-") as tmp:
        baseline_path = Path(tmp) / "baseline.py"
        baseline_path.write_text(source)
        spec = importlib.util.spec_from_file_location("flow_baseline_check", baseline_path)
        assert spec is not None and spec.loader is not None
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        for item in inputs["items"]:
            if item["channel"] == "contract":
                continue
            m, r = restore(item, raw[item["id"]]), restore(item, rules[item["id"]])
            rows.append({"id": item["id"], "lang": item["lang"], "category": item["category"],
                         "before": assess(item, old.check_against_rules(m, r)),
                         "after": assess(item, check_against_rules(m, r))})
    report = {
        "evidence_class": "known-item recorded-reader replay through unchanged verifier",
        "base_commit": BASE, "experiment_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_patch_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "--", "services/api/app"], cwd=ROOT)).hexdigest(),
        "limitations": ["Not a fresh live-model or blind evaluation; no provider calls.",
                        "No chat, execution, owner approvals, receipts or bank settlement exercised.",
                        "Contracts excluded; identical recorded reader outputs used for both checks.",
                        "Historical live/raw/checked runs were separate provider samples; their totals are not this replay's baseline.",
                        "The six unseen items and newer submission tag are unavailable at the fallback base."],
        "provider_calls": 0, "executed_operations": 0,
        "input_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files},
        "historical_totals": {mode: result["totals"] for mode, result in recordings.items()},
        "replay_totals": {mode: dict(Counter(row[mode]["class"] for row in rows)) for mode in ("before", "after")},
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"items": len(rows), "provider_calls": 0, "replay_totals": report["replay_totals"],
                      "changed": [{"id": r["id"], "before": r["before"]["class"], "after": r["after"]["class"]}
                                  for r in rows if r["before"]["class"] != r["after"]["class"]]}, indent=2))
    return int(any(r["after"]["class"] == "wrong" for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
