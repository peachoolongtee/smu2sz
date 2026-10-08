"""The collections route of the strategy MVP (flag `collections_worth`; docs/STRATEGY_MVP_BRIEF.md sections 4 and 5.3).

GET /receivables/worth ranks the open receivables by what collecting each saves, net of the discount that earns it, with
the action for each. Read-only: every receipt is a hypothetical projection on a copy of the books; nothing is written,
logged as an operation or stored as a verdict.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException

from app.api.display import displayed
from app.api.features import require_feature
from app.api.runtime import get_runtime
from app.books import books_from_store
from app.financial import EngineError
from app.funding import NoPermanentSourceError
from app.strategy.cache import CACHE_SIZE, AnswerCache, cache_key
from app.strategy.collections import WorthAnswer, receivables_worth, saving_text

router = APIRouter()

_cache: AnswerCache[WorthAnswer] = AnswerCache(CACHE_SIZE)


def clear_cache() -> None:
    _cache.clear()


def _payload(answer: WorthAnswer, lang: str) -> dict[str, Any]:
    """The answer as JSON with the server-formatted strings; a saving that is zero or negative reads "no saving" (the raw
    figure stays beside it). The `impact` objects are left out: each effect already carries the figures that matter."""
    body = answer.model_dump(mode="json", exclude={"rows": {"__all__": {"effects": {"__all__": {"impact"}}}}})
    out: dict[str, Any] = displayed(body)
    for row in out["rows"]:
        if row["no_saving"]:
            row["net_saving_display"] = row["net_saving_text"]
        for effect in row["effects"]:
            if effect["no_saving"]:
                effect["saving_display"] = saving_text(effect["saving_fen"], lang)
    return out


@router.get("/receivables/worth")
def get_receivables_worth(lang: Literal["en", "zh"] = "en") -> dict[str, Any]:
    require_feature("collections_worth")
    started = time.perf_counter()
    rt = get_runtime()
    with rt.lock:  # read the books, the mandate, the day and the commitments together; the ranking is computed outside
        books = books_from_store(rt.store)
        mandate = rt.store.get_mandate()
        commitments = tuple(rt.store.commitments())
        day = rt.day

    def compute() -> WorthAnswer:
        try:
            return receivables_worth(books, mandate, store=rt.store, day=day, lang=lang)
        except (EngineError, NoPermanentSourceError) as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None

    answer = _cache.get_or_compute(cache_key(books.state, mandate, day, commitments, lang), compute)
    return {"hypothetical": True, "state_version": books.state.state_version, "day": day, **_payload(answer, lang),
            "computed_in_seconds": round(time.perf_counter() - started, 3)}
