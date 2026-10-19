"""Score old/new checks and rules using identical captured fresh model responses.

Inputs come from temporary API instrumentation, never from a credential file.
This is known-item, post-fix evaluation; no model call or operation is executed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("field_check_replay", HERE / "replay.py")
assert spec is not None and spec.loader is not None
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def original_checker():
    source = subprocess.check_output(["git", "show", f"{replay.BASE}:services/api/app/compiler/cross_check.py"],
                                     cwd=replay.ROOT, text=True)
    with tempfile.TemporaryDirectory(prefix="flow-shadow-check-") as directory:
        path = Path(directory) / "original.py"
        path.write_text(source)
        spec = importlib.util.spec_from_file_location("field_check_original", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module.check_against_rules


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    inputs = replay.yaml.safe_load((replay.SOURCE / "items.yaml").read_text())
    labels_hash = replay.digest(replay.SOURCE / "items.yaml")
    budget_path = args.input / "provider-budget.json"
    budget = json.loads(budget_path.read_text())
    result_paths = list(args.input.glob("results_field_cross_check_live_*.json"))
    assert len(result_paths) == 1, "need exactly one fresh evaluation result"
    api = json.loads(result_paths[0].read_text())
    assert labels_hash == api["items_sha256"] == budget["items_sha256"]
    shadow_path = args.input / "reader-shadow.jsonl"
    captured = [json.loads(line) for line in shadow_path.read_text().splitlines() if line]
    api_rows = {row["id"]: row for row in api["items"]}
    rows = []
    original = original_checker()
    for item in inputs["items"]:
        if item["channel"] == "contract":
            continue
        docs = {(d["doc_id"], d["text"]) for d in item["documents"]}
        candidates = [r for r in captured if {(d["doc_id"], d["text"]) for d in r["documents"]} == docs]
        assert len(candidates) == 1, f"{item['id']}: missing or duplicated primary model capture"
        capture = candidates[0]
        model = replay.CompiledOffer.model_validate_json(json.dumps(capture["model"]))
        rules = replay.CompiledOffer.model_validate_json(json.dumps(capture["rules"]))
        before = original(model, rules)
        after = replay.check_against_rules(model, rules)
        assert before == replay.CompiledOffer.model_validate_json(json.dumps(capture["before"]))
        assert after == replay.CompiledOffer.model_validate_json(json.dumps(capture["after"]))
        row = {"id": item["id"], "lang": item["lang"], "category": item["category"],
               "api_observed_class": api_rows[item["id"]]["score"]["class"]}
        for mode in ("rules", "before", "after"):
            offer = replay.CompiledOffer.model_validate_json(json.dumps(capture[mode]))
            row[mode] = replay.assess(item, offer)
        assert row["after"]["class"] == row["api_observed_class"], f"{item['id']}: API/shadow scoring differs"
        rows.append(row)
    totals = {mode: dict(Counter(r[mode]["class"] for r in rows)) for mode in ("rules", "before", "after")}
    deltas = {k: sum((r["record"].get("books_delta") or {}).get(k, 0) for r in api["items"])
              for k in ("commitments_booked", "operations", "money_moved_fen", "facilities_added", "unauthorised_executions")}
    report = {
        "evidence_class": "known-item fresh-provider run with matched-reader old/new shadow checks",
        "implementation_commit": budget["code_commit"], "base_commit": replay.BASE,
        "provider_budget": budget, "items_sha256": labels_hash,
        "input_sha256": {p.name: replay.digest(p) for p in (shadow_path, budget_path, result_paths[0])},
        "shadow_scoring_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "17 offer readings through unchanged verifier; API run separately observed all 20 items, including 3 contracts and 3 extra chat readings",
        "limitations": ["Known labels and targeted fixes, not blind generalization evidence.",
                        "Shadow decisions are evaluated, not executed; product after-path is exercised by the API run.",
                        "Provider returned only the deepseek-flash alias, not an immutable underlying model version.",
                        "This is not security certification or a production/deployment test."],
        "paired_offer_totals": totals, "api_full20_totals": api["totals"], "api_books_delta_totals": deltas,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"paired_offers": len(rows), "totals": totals, "api_full20": api["totals"],
                      "api_books_delta": deltas,
                      "changed": [{"id": r["id"], "before": r["before"]["class"], "after": r["after"]["class"]}
                                  for r in rows if r["before"]["class"] != r["after"]["class"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
