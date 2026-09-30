"""Record fixture-cache entries for every document set in fixtures/offers/offers.yaml.

    cd services/api && uv run python -m app.compiler.record_cache [--source rules|live]

`rules` (default) records the deterministic grammar's extraction; `live` records Claude/DeepSeek output
(needs API keys). Review the diff of fixtures/compiler_cache/ before committing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from app.compiler.backends import ClaudeBackend, DeepSeekBackend
from app.compiler.base import BackendError
from app.compiler.cache import write_entry
from app.compiler.prompts import PROMPT_VERSION, TERM_SHEET_PROMPT_VERSION
from app.compiler.rules import RULES_MODEL_ID, rules_offer, rules_term_sheet
from app.compiler.service import cache_dir
from app.config import get_settings
from app.domain.models import SourceDocument


def offer_sets(fixture_dir: Path) -> list[tuple[str, str, list[SourceDocument]]]:
    data = yaml.safe_load((fixture_dir / "offers" / "offers.yaml").read_text(encoding="utf-8"))
    out = []
    for o in data["offers"]:
        docs = [SourceDocument.model_validate_json(json.dumps(d)) for d in o["documents"]]
        out.append((o["id"], o.get("kind", "offer"), docs))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["rules", "live"], default="rules")
    args = ap.parse_args()
    settings = get_settings()
    fixture_dir = Path(settings.fixture_dir).resolve()
    target = cache_dir(settings)
    for oid, kind, docs in offer_sets(fixture_dir):
        if kind == "term_sheet":
            if args.source == "live":
                for b in (ClaudeBackend(), DeepSeekBackend()):
                    try:
                        res = b.extract_term_sheet(docs[0])
                        write_entry(target, TERM_SHEET_PROMPT_VERSION, docs, res.extraction, res.model_id, oid)
                        break
                    except BackendError:
                        continue
            else:
                write_entry(target, TERM_SHEET_PROMPT_VERSION, docs, rules_term_sheet(docs[0]), RULES_MODEL_ID, oid)
            continue
        if args.source == "live":
            for b in (ClaudeBackend(), DeepSeekBackend()):
                try:
                    r = b.extract_offer(docs)
                    write_entry(target, PROMPT_VERSION, docs, r.extraction, r.model_id, oid)
                    break
                except BackendError:
                    continue
        else:
            write_entry(target, PROMPT_VERSION, docs, rules_offer(docs), RULES_MODEL_ID, oid)
        print(f"recorded {oid}")


if __name__ == "__main__":
    main()
