"""The backend protocol shared by the model adapters, the cache and the rules grammar."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.compiler.schema import OfferExtraction, TermSheetExtraction
from app.domain.models import SourceDocument


class BackendError(Exception):
    """A backend could not produce a valid extraction; the chain moves to the next backend."""


class CacheMiss(BackendError):
    pass


@dataclass(frozen=True)
class OfferResult:
    extraction: OfferExtraction
    model_id: str  # recorded as CompiledOffer.compiler


@dataclass(frozen=True)
class TermSheetResult:
    extraction: TermSheetExtraction
    model_id: str


class LLMBackend(Protocol):
    """Anything that fills the extraction schema from documents. Sees documents only."""

    name: str

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult: ...
    def extract_term_sheet(self, doc: SourceDocument) -> TermSheetResult: ...
