"""Fixture cache: recorded extractions keyed by sha256(prompt_version + canonical documents).

Entries store the raw extraction (pre-grounding), so replay goes through the same span validation and
lexicon union as a live call.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from app.compiler.base import CacheMiss, OfferResult, TermSheetResult
from app.compiler.grounding import canonical_docs
from app.compiler.prompts import PROMPT_VERSION, TERM_SHEET_PROMPT_VERSION
from app.compiler.schema import OfferExtraction, TermSheetExtraction
from app.domain.models import SourceDocument

CACHE_MODEL_ID = "fixture-cache"


def cache_key(prompt_version: str, docs: Sequence[SourceDocument]) -> str:
    return hashlib.sha256((prompt_version + canonical_docs(docs)).encode("utf-8")).hexdigest()


def entry_path(cache_dir: Path, prompt_version: str, docs: Sequence[SourceDocument]) -> Path:
    return cache_dir / f"{cache_key(prompt_version, docs)}.json"


def write_entry(
    cache_dir: Path,
    prompt_version: str,
    docs: Sequence[SourceDocument],
    extraction: OfferExtraction | TermSheetExtraction,
    source_model: str,
    label: str = "",
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = entry_path(cache_dir, prompt_version, docs)
    entry = {
        "key": path.stem,
        "label": label,
        "prompt_version": prompt_version,
        "kind": "term_sheet" if isinstance(extraction, TermSheetExtraction) else "offer",
        "doc_ids": [d.doc_id for d in docs],
        "source_model": source_model,
        "extraction": extraction.model_dump(mode="json"),
    }
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read(cache_dir: Path, prompt_version: str, docs: Sequence[SourceDocument]) -> dict:
    path = entry_path(cache_dir, prompt_version, docs)
    if not path.is_file():
        raise CacheMiss(path.name)
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CacheMiss(f"unreadable cache entry {path.name}") from e
    if entry.get("prompt_version") != prompt_version:
        raise CacheMiss(f"prompt version mismatch in {path.name}")
    return entry


class CacheBackend:
    name = "cache"

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        entry = _read(self.cache_dir, PROMPT_VERSION, docs)
        try:
            ex = OfferExtraction.model_validate(entry["extraction"])
        except (ValidationError, KeyError) as e:
            raise CacheMiss("invalid cache entry") from e
        return OfferResult(ex, CACHE_MODEL_ID)

    def extract_term_sheet(self, doc: SourceDocument) -> TermSheetResult:
        entry = _read(self.cache_dir, TERM_SHEET_PROMPT_VERSION, [doc])
        try:
            ex = TermSheetExtraction.model_validate(entry["extraction"])
        except (ValidationError, KeyError) as e:
            raise CacheMiss("invalid cache entry") from e
        return TermSheetResult(ex, CACHE_MODEL_ID)
