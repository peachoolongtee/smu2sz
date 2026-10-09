"""Record fixture-cache entries for every document set in fixtures/offers/offers.yaml and every demo document in
fixtures/contracts/contracts.yaml.

    cd services/api && uv run python -m app.compiler.record_cache [--source rules|live] [--only all|offers|contracts]

`rules` (default) records the deterministic grammar's extraction; `live` records Claude/DeepSeek output
(needs API keys). A buyer contract is recorded chunk by chunk (one entry per chunk, as `compile_contract` reads it);
a lender agreement as one term sheet. Review the diff of fixtures/compiler_cache/ before committing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from app.compiler.backends import ClaudeBackend, DeepSeekBackend
from app.compiler.base import BackendError
from app.compiler.cache import write_entry
from app.compiler.contract import chunk_document, chunk_source, contract_document
from app.compiler.contract_rules import rules_contract
from app.compiler.prompts import CONTRACT_PROMPT_VERSION, PROMPT_VERSION, TERM_SHEET_PROMPT_VERSION
from app.compiler.rules import RULES_MODEL_ID, rules_offer, rules_term_sheet
from app.compiler.service import cache_dir
from app.config import get_settings
from app.domain.models import DocumentKind, SourceDocument


def offer_sets(fixture_dir: Path) -> list[tuple[str, str, list[SourceDocument]]]:
    data = yaml.safe_load((fixture_dir / "offers" / "offers.yaml").read_text(encoding="utf-8"))
    out = []
    for o in data["offers"]:
        docs = [SourceDocument.model_validate_json(json.dumps(d)) for d in o["documents"]]
        out.append((o["id"], o.get("kind", "offer"), docs))
    return out


def contract_documents(fixture_dir: Path) -> list[tuple[str, DocumentKind, SourceDocument]]:
    """(fixture id, kind, canonical document) for every demo contract, read exactly as the API reads it (the same
    text extraction and the same canonical document, so the recorded keys are the ones the API looks up)."""
    from app.ingest import extract_text

    folder = fixture_dir / "contracts"
    registry = yaml.safe_load((folder / "contracts.yaml").read_text(encoding="utf-8"))["contracts"]
    out = []
    for c in registry:
        kind = DocumentKind(c["kind"])
        path = folder / c["file"]
        out.append((c["id"], kind, contract_document(extract_text(path.name, path.read_bytes()), kind,
                                                     c["counterparty_id"])))
    return out


def _live(call):  # type: ignore[no-untyped-def]
    for b in (ClaudeBackend(), DeepSeekBackend()):
        try:
            return call(b)
        except BackendError:
            continue
    return None


def record_offers(target: Path, fixture_dir: Path, source: str) -> None:
    for oid, kind, docs in offer_sets(fixture_dir):
        if kind == "term_sheet":
            if source == "live":
                res = _live(lambda b, d=docs[0]: b.extract_term_sheet(d))
                if res is not None:
                    write_entry(target, TERM_SHEET_PROMPT_VERSION, docs, res.extraction, res.model_id, oid)
            else:
                write_entry(target, TERM_SHEET_PROMPT_VERSION, docs, rules_term_sheet(docs[0]), RULES_MODEL_ID, oid)
            continue
        if source == "live":
            r = _live(lambda b, d=docs: b.extract_offer(d))
            if r is not None:
                write_entry(target, PROMPT_VERSION, docs, r.extraction, r.model_id, oid)
        else:
            write_entry(target, PROMPT_VERSION, docs, rules_offer(docs), RULES_MODEL_ID, oid)
        print(f"recorded {oid}")


def record_contracts(target: Path, fixture_dir: Path, source: str) -> None:
    for fid, kind, doc in contract_documents(fixture_dir):
        if kind == DocumentKind.LENDER_AGREEMENT:
            if source == "live":
                res = _live(lambda b, d=doc: b.extract_term_sheet(d))
                if res is not None:
                    write_entry(target, TERM_SHEET_PROMPT_VERSION, [doc], res.extraction, res.model_id, fid)
            else:
                write_entry(target, TERM_SHEET_PROMPT_VERSION, [doc], rules_term_sheet(doc), RULES_MODEL_ID, fid)
            print(f"recorded {fid}")
            continue
        for chunk in chunk_document(doc):
            cdoc = chunk_source(doc, chunk)
            label = f"{fid}#{chunk.index}"
            if source == "live":
                res = _live(lambda b, d=cdoc: b.extract_contract(d))
                if res is not None:
                    write_entry(target, CONTRACT_PROMPT_VERSION, [cdoc], res.extraction, res.model_id, label)
            else:
                write_entry(target, CONTRACT_PROMPT_VERSION, [cdoc], rules_contract(cdoc), RULES_MODEL_ID, label)
            print(f"recorded {label}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["rules", "live"], default="rules")
    ap.add_argument("--only", choices=["all", "offers", "contracts"], default="all")
    args = ap.parse_args()
    settings = get_settings()
    target = cache_dir(settings)
    fixture_dir = Path(settings.fixture_dir).resolve()
    if args.only in ("all", "offers"):
        record_offers(target, fixture_dir, args.source)
    if args.only in ("all", "contracts"):
        record_contracts(target, fixture_dir, args.source)


if __name__ == "__main__":
    main()
