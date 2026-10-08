"""The Safe Deal Envelope route (flag `envelope`; docs/STRATEGY_MVP_BRIEF.md sections 4 and 5.2).

GET /buyers/{buyer_id}/envelope?zone=0|1&lang=en|zh answers what the supplier can live with for one named buyer,
as approved packages. Read-only and hypothetical: it never writes, logs an operation or stores a verdict. The sweep
is language-neutral and cached (32 entries, by the books, the mandate, the day, the buyer, the commitments and
`zone`); the sentences are worded per request.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.display import displayed
from app.api.features import require_feature
from app.api.runtime import get_runtime
from app.books import books_from_store
from app.financial import EngineError
from app.strategy.envelope import EnvelopeFacts, envelope_answer, envelope_facts

router = APIRouter()

CACHE_SIZE = 32
_cache: OrderedDict[str, EnvelopeFacts] = OrderedDict()
_cache_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _cached(key: str) -> EnvelopeFacts | None:
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
        return hit


def _remember(key: str, facts: EnvelopeFacts) -> None:
    with _cache_lock:
        _cache[key] = facts
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


@router.get("/buyers/{buyer_id}/envelope")
def get_envelope(buyer_id: str, zone: Literal[0, 1] = Query(0), lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    require_feature("envelope")
    rt = get_runtime()
    with rt.lock:  # read the books, the mandate, the day and the commitments together; the sweep runs outside the lock
        books = books_from_store(rt.store)
        mandate = rt.store.get_mandate()
        commitments = tuple(rt.store.commitments())
        day = rt.day
    state = books.state
    if not any(c.id == buyer_id for c in state.counterparties):
        raise HTTPException(404, detail={"code": "BUYER_NOT_FOUND", "message": f"There is no buyer {buyer_id} on the books."})
    held = "|".join(c.model_dump_json() for c in commitments)
    key = hashlib.sha256(
        f"{state.model_dump_json()}|{mandate.model_dump_json()}|{day}|{buyer_id}|{held}|{zone}".encode()).hexdigest()
    facts = _cached(key)
    if facts is None:
        try:
            facts = envelope_facts(books, mandate, store=rt.store, day=day, buyer_id=buyer_id,
                                   trusted_owner_key_hex=rt.owner_key_hex, commitments=commitments, zone=bool(zone))
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        _remember(key, facts)
    answer = envelope_answer(facts, lang)
    return {**displayed(answer.model_dump(mode="json")), "state_version": state.state_version, "day": day}
