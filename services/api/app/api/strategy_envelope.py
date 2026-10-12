"""The Safe Deal Envelope route (flag `envelope`; docs/STRATEGY_MVP_BRIEF.md sections 4 and 5.2).

GET /buyers/{buyer_id}/envelope?zone=0|1&ask=T&lang=en|zh answers what the supplier can live with for one named buyer,
as approved packages, and with `ask` what makes the buyer's asked terms T work (P4: the smallest price, else the early
payment that does; read on demand and cached apart like the zone, 32 entries keyed by the sweep's key and T). Read-only and hypothetical: it never writes, logs an operation or stores a verdict. The sweep
is language-neutral and cached (32 entries each for the sweep and for the zone table, by the books, the mandate, the day,
the buyer and the commitments; the table is cached apart so that asking for it after a read without it adds only its own
cost; one request computes a key while the others wait for it); the sentences are worded per request. The books are read
under the runtime lock and the sweep runs outside it. A value off the levers' grids is answered with `refused`, never a 500.
"""

from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.display import displayed
from app.api.features import require_feature
from app.api.runtime import get_runtime
from app.books import books_from_store
from app.financial import EngineError
from app.strategy.cache import CACHE_SIZE, AnswerCache, cache_key
from app.strategy.envelope import (
    AskFacts,
    EnvelopeFacts,
    ZoneFacts,
    envelope_answer,
    envelope_ask,
    envelope_facts,
    envelope_zone,
    out_of_range_facts,
)

router = APIRouter()
log = logging.getLogger(__name__)

_cache: AnswerCache[EnvelopeFacts] = AnswerCache(CACHE_SIZE)
_zone_cache: AnswerCache[ZoneFacts] = AnswerCache(CACHE_SIZE)
_ask_cache: AnswerCache[AskFacts] = AnswerCache(CACHE_SIZE)


def clear_cache() -> None:
    _cache.clear()
    _zone_cache.clear()
    _ask_cache.clear()


@router.get("/buyers/{buyer_id}/envelope")
def get_envelope(buyer_id: str, zone: int = Query(0, ge=0, le=1), ask: int | None = Query(None, ge=1, le=365),
                 lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
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
                                  trusted_owner_key_hex=rt.owner_key_hex, commitments=commitments)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        except ValueError:  # WhatIfParamError or a value off the levers' grids: said in a sentence, never a 500
            log.warning("envelope for %s is outside the levers' ranges", buyer_id, exc_info=True)
            return out_of_range_facts(books, day=day, buyer_id=buyer_id)

    def zone_sweep() -> ZoneFacts:
        try:
            return envelope_zone(books, mandate, day=day, buyer_id=buyer_id, trusted_owner_key_hex=rt.owner_key_hex,
                                 commitments=commitments)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None

    key = cache_key(state, mandate, day, commitments, buyer_id)
    facts = _cache.get_or_compute(key, sweep)
    if zone and not facts.refused:  # the table is cached apart: a read of it after a read without it adds only its own cost
        try:
            z = _zone_cache.get_or_compute(key, zone_sweep)
            facts = replace(facts, zone=z.rows, evaluations=facts.evaluations + z.evaluations, seconds=facts.seconds + z.seconds)
        except ValueError:  # a table row off the levers' grids: the same refusal the whole sweep would have given
            log.warning("envelope zone for %s is outside the levers' ranges", buyer_id, exc_info=True)
            facts = out_of_range_facts(books, day=day, buyer_id=buyer_id)
    asked: AskFacts | None = None
    if ask is not None and not facts.refused:  # cached apart: the ask's searches are its own, read only when asked

        def ask_sweep() -> AskFacts:
            try:
                return envelope_ask(books, mandate, day=day, buyer_id=buyer_id, trusted_owner_key_hex=rt.owner_key_hex,
                                    terms=ask, commitments=commitments)
            except EngineError as exc:
                raise HTTPException(422, f"cannot project: {exc}") from None

        try:
            asked = _ask_cache.get_or_compute(f"{key}|ask={ask}", ask_sweep)
            facts = replace(facts, evaluations=facts.evaluations + asked.evaluations, seconds=facts.seconds + asked.seconds)
        except ValueError:  # an ask package off the levers' grids: the same refusal the whole sweep would have given
            log.warning("envelope ask for %s is outside the levers' ranges", buyer_id, exc_info=True)
            facts, asked = out_of_range_facts(books, day=day, buyer_id=buyer_id), None
    answer = envelope_answer(facts, lang, asked)
    return {**displayed(answer.model_dump(mode="json")), "state_version": state.state_version, "day": day,
            "computed_in_seconds": round(time.perf_counter() - started, 3)}
