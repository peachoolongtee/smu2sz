"""Run the held-out contract set and write its report (brief 03 §6.8).

    DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/evaluate_contracts.py

Reads `fixtures/contracts_heldout/labels.yaml`, reads each contract with the configured compiler chain (offline by
default: a recorded reading if there is one, else the rules grammar; LLM_MODE=live for the model) and writes
`services/api/evals/contracts_heldout_report.md` and `.json`. With no contracts the report says the set is pending.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("LLM_MODE", "cache")
os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")
sys.path.insert(0, str(ROOT / "services" / "api"))

import yaml  # noqa: E402

from app.compiler import compile_contract  # noqa: E402
from app.compiler.contract import contract_document  # noqa: E402
from app.contracts.heldout import ContractResult, report, score  # noqa: E402
from app.domain.models import DocumentKind  # noqa: E402
from app.ingest import extract_text  # noqa: E402

FOLDER = ROOT / "fixtures" / "contracts_heldout"
OUT = ROOT / "services" / "api" / "evals" / "contracts_heldout_report"


def main() -> int:
    labels = yaml.safe_load((FOLDER / "labels.yaml").read_text(encoding="utf-8")) or {}
    entries = labels.get("contracts") or []
    results: list[ContractResult] = []
    for e in entries:
        path = FOLDER / e["file"]
        doc = contract_document(extract_text(path.name, path.read_bytes()), DocumentKind(e.get("kind", "BUYER_CONTRACT")),
                                e["counterparty_id"])
        reading = compile_contract(doc)
        results.append(ContractResult(id=e["id"], compiler=reading.compiler, status=reading.status.value,
                                      fields=score(reading, e.get("expected") or {}),
                                      unsupported=list(e.get("unsupported") or [])))
    text = report(results, pending=not entries)
    OUT.with_suffix(".md").write_text(text, encoding="utf-8", newline="\n")
    OUT.with_suffix(".json").write_text(json.dumps({"pending": not entries,
                                                    "contracts": [dataclasses.asdict(r) for r in results]},
                                                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
