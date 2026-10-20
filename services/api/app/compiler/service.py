"""The compiler entry points: `compile_offer`, `compile_term_sheet` and `compile_contract`.

Backend chain:
- LLM_MODE=cache (default): fixture cache, then the rules grammar.
- LLM_MODE=live: fixture cache, then Claude, then DeepSeek on error, then the rules grammar (LLM_PRIMARY=deepseek
  swaps the two models). A recorded reading replays before any model is called, so the demo's documents cost no
  model call and read as they were tested; only text with no recording reaches a model.
Whatever backend answers, its extraction goes through the same grounding (span validation, value
parsing, lexicon union, conflict detection). The output is a proposal only.

In live mode a model's reading of a buyer message is also checked against the rules grammar's reading of the same
documents (`compiler.cross_check`): a term the two read differently is abstained on, never decided by either alone.
LLM_LIVE_RAW=1 keeps live mode as it was (no recording first, no check), to measure a model on its own.

A model never sees the identifiers FLOW does not read (accounts, phones, emails, credit codes, ID numbers, labelled
addresses): `compiler.redaction` wraps each model backend (LLM_REDACT, on by default) and maps the model's quotes back to
the original text before grounding. The recording is looked up, and the rules grammar reads, by the original text.

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
from app.compiler.cache import CACHE_MODEL_ID, CacheBackend
from app.compiler.contract import MAX_CHUNKS, ContractTooLong, build_contract, chunk_document, chunk_source
from app.compiler.cross_check import check_against_rules, held_for_owner
from app.compiler.folding import has_format_characters
from app.compiler.grounding import build_offer, build_term_sheet, docs_hash
from app.compiler.prompts import CONTRACT_PROMPT_VERSION, PROMPT_VERSION, TERM_SHEET_PROMPT_VERSION
from app.compiler.redaction import redacting
from app.compiler.rules import RULES_MODEL_ID, RulesBackend
from app.config import Settings, get_settings
from app.domain.models import CompiledContract, CompiledOffer, CompiledTermSheet, DocumentKind, SourceDocument

log = structlog.get_logger("termsledger.compiler")
R = TypeVar("R", OfferResult, TermSheetResult, ContractResult)
UNCHECKED = {CACHE_MODEL_ID, RULES_MODEL_ID}  # a recorded reading, or the rules grammar's own: nothing to check it against


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
        claude = ClaudeBackend(model=s.claude_model, hard_model=s.claude_hard_model, redact=s.llm_redact)
        deepseek = DeepSeekBackend(model=s.deepseek_model, redact=s.llm_redact)
        # Only the models see redacted text: each provider backend redacts its own input (compiler.redaction, PRIV-1), and
        # the recording and the rules grammar read the original.
        first = redacting([deepseek, claude] if s.llm_primary == "deepseek" else [claude, deepseek], s.llm_redact)
        recorded: list[LLMBackend] = [] if s.llm_live_raw else [CacheBackend(cache_dir(s))]
        return [*recorded, *first, RulesBackend()]
    return [CacheBackend(cache_dir(s)), RulesBackend()]


class Compiler:
    """Implements the OfferCompiler port. Holds no state, mandate or funding menu."""

    def __init__(self, backends: Sequence[LLMBackend] | None = None, *, cross_check: bool | None = None) -> None:
        """`cross_check` checks a model's reading of a buyer message against the rules grammar's. By default it is on for the
        configured live chain (unless LLM_LIVE_RAW) and off for a chain given here."""
        if backends is None:
            s = get_settings()
            self.backends: list[LLMBackend] = default_backends(s)
            checked = s.llm_mode == "live" and not s.llm_live_raw
        else:
            self.backends = list(backends)
            checked = False
        self.cross_check = checked if cross_check is None else cross_check
        if not any(isinstance(b, RulesBackend) for b in self.backends):
            self.backends.append(RulesBackend())  # the chain always ends in a backend that cannot fail

    def _run(self, call: Callable[[LLMBackend], R], prompt_version: str, doc_hash: str,
             backends: Sequence[LLMBackend] | None = None) -> R:
        last: Exception | None = None
        for b in (self.backends if backends is None else backends):
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
        if any(has_format_characters(d.text) for d in docs):
            # LIVE-1: hidden formatting characters (zero-width, bidi, soft hyphen). A model reads straight through them while the
            # rules grammar refuses, so the cross-check had nothing to compare and the model's reading went unchecked. Such a
            # message is read by the rules grammar alone, as in cache mode, and the coverage proof holds it for the owner.
            rules = [b for b in self.backends if isinstance(b, RulesBackend)]
            log.info("compiler.hidden_characters", outcome="rules_only", prompt_version=PROMPT_VERSION, doc_hash=h)
            res = self._run(lambda b: b.extract_offer(docs), PROMPT_VERSION, h, backends=rules)
            return build_offer(docs, counterparty_id, res.extraction, res.model_id, PROMPT_VERSION)
        res = self._run(lambda b: b.extract_offer(docs), PROMPT_VERSION, h)
        offer = build_offer(docs, counterparty_id, res.extraction, res.model_id, PROMPT_VERSION)
        if self.cross_check and res.model_id not in UNCHECKED:
            offer = self._checked(docs, counterparty_id, offer, h)
        return offer

    def _checked(self, docs: list[SourceDocument], counterparty_id: str, offer: CompiledOffer, doc_hash: str) -> CompiledOffer:
        """A model's reading, checked against the rules grammar's reading of the same documents (`compiler.cross_check`)."""
        rules = next(b for b in self.backends if isinstance(b, RulesBackend))
        try:
            res = rules.extract_offer(docs)
        except BackendError:  # the grammar read nothing: every term is the model's alone (LIVE-2)
            return held_for_owner(offer) if offer.obligations else offer
        checked = check_against_rules(offer, build_offer(docs, counterparty_id, res.extraction, res.model_id, PROMPT_VERSION))
        log.info("compiler.cross_check", model=offer.compiler, outcome="agree" if checked is offer else "disagree",
                 prompt_version=PROMPT_VERSION, doc_hash=doc_hash)
        return checked

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
