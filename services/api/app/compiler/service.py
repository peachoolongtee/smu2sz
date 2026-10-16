"""The compiler entry points: `compile_offer`, `compile_term_sheet` and `compile_contract`.

Backend chain:
- LLM_MODE=cache (default): fixture cache, then the rules grammar.
- LLM_MODE=live: Claude, then DeepSeek on error, then the rules grammar (LLM_PRIMARY=deepseek swaps the
  first two).
Whatever backend answers, its extraction goes through the same grounding (span validation, value
parsing, lexicon union, conflict detection). The output is a proposal only.

A contract is read chunk by chunk (`compiler.contract.chunk_document`); each chunk takes the backend chain on its own,
so a recorded chunk replays even when another chunk of the same document falls through to the rules grammar.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

import structlog

from app.compiler.backends import ClaudeBackend, DeepSeekBackend
from app.compiler.base import BackendError, ContractResult, LLMBackend, OfferResult, TermSheetResult
from app.compiler.cache import CacheBackend
from app.compiler.contract import MAX_CHUNKS, ContractTooLong, build_contract, chunk_document, chunk_source
from app.compiler.grounding import build_offer, build_term_sheet, docs_hash
from app.compiler.prompts import CONTRACT_PROMPT_VERSION, PROMPT_VERSION, TERM_SHEET_PROMPT_VERSION
from app.compiler.rules import RulesBackend
from app.config import Settings, get_settings
from app.domain.models import CompiledContract, CompiledOffer, CompiledTermSheet, DocumentKind, SourceDocument

log = structlog.get_logger("termsledger.compiler")
R = TypeVar("R", OfferResult, TermSheetResult, ContractResult)


def _extract_contract(backend: LLMBackend, chunk: SourceDocument) -> ContractResult:
    fn = getattr(backend, "extract_contract", None)
    if fn is None:  # a backend written before contracts: the chain moves on
        raise BackendError(f"{getattr(backend, 'name', 'backend')} cannot read contracts")
    return fn(chunk)


def cache_dir(settings: Settings) -> Path:
    return Path(settings.fixture_dir).resolve() / "compiler_cache"


def default_backends(settings: Settings | None = None) -> list[LLMBackend]:
    s = settings or get_settings()
    if s.llm_mode == "live":
        claude = ClaudeBackend(model=s.claude_model, hard_model=s.claude_hard_model)
        deepseek = DeepSeekBackend(model=s.deepseek_model)
        first: list[LLMBackend] = [deepseek, claude] if s.llm_primary == "deepseek" else [claude, deepseek]
        return [*first, RulesBackend()]
    return [CacheBackend(cache_dir(s)), RulesBackend()]


class Compiler:
    """Implements the OfferCompiler port. Holds no state, mandate or funding menu."""

    def __init__(self, backends: Sequence[LLMBackend] | None = None) -> None:
        self.backends: list[LLMBackend] = list(backends) if backends is not None else default_backends()
        if not any(isinstance(b, RulesBackend) for b in self.backends):
            self.backends.append(RulesBackend())  # the chain always ends in a backend that cannot fail

    def _run(self, call: Callable[[LLMBackend], R], prompt_version: str, doc_hash: str) -> R:
        last: Exception | None = None
        for b in self.backends:
            t0 = time.perf_counter()
            try:
                res = call(b)
            except BackendError as e:
                log.info("compiler.call", backend=b.name, outcome="fallback", error=type(e).__name__,
                         prompt_version=prompt_version, doc_hash=doc_hash,
                         latency_ms=round((time.perf_counter() - t0) * 1000, 1))
                last = e
                continue
            log.info("compiler.call", backend=b.name, model=res.model_id, outcome="ok",
                     prompt_version=prompt_version, doc_hash=doc_hash,
                     latency_ms=round((time.perf_counter() - t0) * 1000, 1))
            return res
        raise RuntimeError("no compiler backend produced an extraction") from last

    def compile_offer(self, docs: list[SourceDocument], counterparty_id: str) -> CompiledOffer:
        if not docs:
            raise ValueError("compile_offer needs at least one document")
        h = docs_hash(docs)
        res = self._run(lambda b: b.extract_offer(docs), PROMPT_VERSION, h)
        return build_offer(docs, counterparty_id, res.extraction, res.model_id, PROMPT_VERSION)

    def compile_term_sheet(self, doc: SourceDocument) -> CompiledTermSheet:
        h = docs_hash([doc])
        res = self._run(lambda b: b.extract_term_sheet(doc), TERM_SHEET_PROMPT_VERSION, h)
        return build_term_sheet(doc, res.extraction, res.model_id, TERM_SHEET_PROMPT_VERSION)

    def compile_contract(self, doc: SourceDocument,
                         kind: DocumentKind = DocumentKind.BUYER_CONTRACT) -> CompiledContract:
        """A buyer contract (or, ADR-0013, a capex contract), read chunk by chunk and grounded as one document. A proposal
        for the owner only. The kind changes only which fields are material; the reading and its cache keys do not."""
        chunks = chunk_document(doc)
        if len(chunks) > MAX_CHUNKS:  # every chunk is a model call in live mode: refuse before the first
            raise ContractTooLong(len(chunks))
        parts = []
        models: list[str] = []
        for chunk in chunks:
            cdoc = chunk_source(doc, chunk)
            res = self._run(lambda b, d=cdoc: _extract_contract(b, d), CONTRACT_PROMPT_VERSION, docs_hash([cdoc]))
            parts.append((chunk, res.extraction))
            models.append(res.model_id)
        return build_contract(doc, parts, "+".join(dict.fromkeys(models)), CONTRACT_PROMPT_VERSION, kind)


@lru_cache(maxsize=1)
def _default_compiler() -> Compiler:
    return Compiler()


def compile_offer(docs: list[SourceDocument], counterparty_id: str) -> CompiledOffer:
    return _default_compiler().compile_offer(docs, counterparty_id)


def compile_term_sheet(doc: SourceDocument) -> CompiledTermSheet:
    return _default_compiler().compile_term_sheet(doc)


def compile_contract(doc: SourceDocument, kind: DocumentKind = DocumentKind.BUYER_CONTRACT) -> CompiledContract:
    return _default_compiler().compile_contract(doc, kind)
