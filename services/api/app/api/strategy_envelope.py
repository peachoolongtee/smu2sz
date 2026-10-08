"""The Safe Deal Envelope route (flag `envelope`; docs/STRATEGY_MVP_BRIEF.md sections 4 and 5.2).

GET /buyers/{buyer_id}/envelope?zone=0|1&lang=en|zh answers what the supplier can live with for one named buyer,
as approved packages. Read-only and hypothetical: it never writes, logs an operation or stores a verdict. The sweep
is language-neutral and cached (32 entries, by the books, the mandate, the day, the buyer, the commitments and
`zone`; one request computes a key while the others wait for it); the sentences are worded per request. The books are read
under the runtime lock and the sweep runs outside it. A value off the levers' grids is answered with `refused`, never a 500.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.display import displayed
from app.api.features import require_feature
from app.api.runtime import get_runtime
from app.books import books_from_store
from app.financial import EngineError
from app.strategy.cache import CACHE_SIZE, AnswerCache, cache_key
from app.strategy.envelope import EnvelopeFacts, envelope_answer, envelope_facts, out_of_range_facts

router = APIRouter()
log = logging.getLogger(__name__)

_cache: AnswerCache[EnvelopeFacts] = AnswerCache(CACHE_SIZE)


def clear_cache() -> None:
    _cache.clear()


@router.get("/buyers/{buyer_id}/envelope")
def get_envelope(buyer_id: str, zone: int = Query(0, ge=0, le=1), lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    require_feature("envelope")
    started = time.perf_counter()
    rt = get_runtime()
    with rt.lock:  # read the books, the mandate, the day and the commitments together; the sweep runs outside the lock
        books = books_from_store(rt.store)
        mandate = rt.store.get_mandate()
        commitments = tuple(rt.store.commitments())
        day = rt.day
    state = books.state
    if not any(c.id == buyer_id for c in state.counterparties):
        raise HTTPException(404, detail={"code": "BUYER_NOT_FOUND", "message": f"There is no buyer {buyer_id} on the books."})

    def sweep() -> EnvelopeFacts:
        try:
            return envelope_facts(books, mandate, store=rt.store, day=day, buyer_id=buyer_id,
                                  trusted_owner_key_hex=rt.owner_key_hex, commitments=commitments, zone=bool(zone))
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        except ValueError:  # WhatIfParamError or a value off the levers' grids: said in a sentence, never a 500
            log.warning("envelope for %s is outside the levers' ranges", buyer_id, exc_info=True)
            return out_of_range_facts(books, day=day, buyer_id=buyer_id)

    facts = _cache.get_or_compute(cache_key(state, mandate, day, commitments, buyer_id, zone), sweep)
    answer = envelope_answer(facts, lang)
    return {**displayed(answer.model_dump(mode="json")), "state_version": state.state_version, "day": day,
            "computed_in_seconds": round(time.perf_counter() - started, 3)}
