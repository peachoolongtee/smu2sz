"""The buyer-exposure routes (map #88 Phase 1; flag `exposure`; brief H.5 and section K).

    GET /offers/{offer_id}/exposure?response=asked|counter:<k>&lang=en|zh
    GET /decisions/{decision_id}/exposure?lang=en|zh

What a deal does to the exposure to one buyer: how much of what the supplier is owed sits with that buyer (`concentration`) and
how that buyer has paid (`payments`), each with the sentences written for `lang`. The stress test and the capacity statement
(`stress`, `capacity`) are the assembly's, a later pass: until it lands they are null and `partial` is true, so a client can
already read the block that exists. Both ids resolve to the same buyer: an offer's counterparty, and for a `deal:<offer_id>`
decision that offer's. `response` names which of the buyer's answers the block is for (what was asked, or the verdict's k-th
counter-offer) and is part of the cache key; the concentration and the payment behaviour do not depend on it.

Read-only and hypothetical: nothing is written, logged or stored; concentration and payment behaviour are context, never a
mandate, and change no verdict. The answer is cached through `app.strategy.cache` (32 entries, single-flight) keyed by the books,
the mandate, the day, the commitments, the buyer, the response, the language and the customer inputs in force. Mounted through
`app/api/strategy.py`, which carries the owner check.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.decisions import latest_verdict_for
from app.api.display import displayed
from app.api.features import require_feature
from app.api.presentation import party_name
from app.api.runtime import Runtime, get_runtime
from app.books import books_from_store
from app.decisions.identity import offer_id_of
from app.domain.models import CompiledOffer
from app.financial import EngineError
from app.strategy.cache import CACHE_SIZE, AnswerCache, cache_key
from app.strategy.concentration import concentration
from app.strategy.inputs import inputs_from_store
from app.strategy.payments import payment_behaviour

router = APIRouter()
log = logging.getLogger(__name__)

_cache: AnswerCache[dict[str, Any]] = AnswerCache(CACHE_SIZE)
_RESPONSE = re.compile(r"^(asked|counter:[0-9]{1,3})$")


def clear_cache() -> None:
    _cache.clear()


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(404, detail={"code": code, "message": message})


def _offer(rt: Runtime, offer_id: str) -> CompiledOffer:
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise _not_found("OFFER_NOT_FOUND", f"There is no offer {offer_id}.")
    return offer


def _check_response(rt: Runtime, offer_id: str, response: str) -> None:
    """`asked` always stands; `counter:<k>` needs the verdict's k-th counter-offer."""
    if not _RESPONSE.fullmatch(response):
        raise HTTPException(422, detail={"code": "BAD_RESPONSE", "message": "response is asked or counter:<k>, for example counter:0."})
    if response == "asked":
        return
    verdict = latest_verdict_for(rt, offer_id)
    if verdict is None or int(response.split(":")[1]) >= len(verdict.counters):
        raise _not_found("COUNTER_NOT_FOUND", f"Offer {offer_id} has no {response}.")


def _answer(rt: Runtime, buyer_id: str, response: str, lang: Literal["en", "zh"]) -> dict[str, Any]:
    """The block for one buyer, from the books, the log and the owner's inputs, cached. The stress test and the capacity
    statement are the assembly's (`app.strategy.exposure`, not written yet): until then they are null and `partial` is true."""
    with rt.lock:  # the books, the mandate, the day, the commitments and the inputs are read together
        books = books_from_store(rt.store)
        mandate = rt.store.get_mandate()
        commitments = tuple(rt.store.commitments())
        day = rt.day
        inputs = inputs_from_store(rt.store)
    state = books.state
    if not any(c.id == buyer_id for c in state.counterparties):
        raise _not_found("BUYER_NOT_FOUND", f"There is no buyer {buyer_id} on the books.")

    def compute() -> dict[str, Any]:
        try:
            with rt.lock:  # the log is replayed against the books just read
                shares = concentration(books, buyer_id, day, inputs, lang=lang)
                paid = payment_behaviour(rt.store, books, buyer_id, day, inputs, lang=lang)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        return {"buyer_id": buyer_id, "buyer_name": party_name(state, buyer_id), "response": response, "lang": lang,
                "concentration": shares.model_dump(mode="json"), "payments": paid.model_dump(mode="json"),
                "stress": None, "capacity": None, "partial": True, "state_version": state.state_version, "day": day}

    key = cache_key(state, mandate, day, commitments, buyer_id, response, lang, inputs.digest())
    return _cache.get_or_compute(key, compute)


def _respond(core: dict[str, Any], started: float, **ids: str) -> dict[str, Any]:
    return displayed({**ids, **core, "computed_in_seconds": round(time.perf_counter() - started, 3)})


@router.get("/offers/{offer_id}/exposure")
def get_offer_exposure(offer_id: str, response: str = Query("asked"), lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer = _offer(rt, offer_id)
    _check_response(rt, offer_id, response)
    return _respond(_answer(rt, offer.counterparty_id, response, lang), started, offer_id=offer_id)


@router.get("/decisions/{decision_id}/exposure")
def get_decision_exposure(decision_id: str, lang: Literal["en", "zh"] = Query("en")) -> dict[str, Any]:
    """A deal decision (`deal:<offer_id>`) is about that offer's buyer, asked as it was. Any other decision (a funding
    decision) is about no buyer: 404."""
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer_id = offer_id_of(decision_id)
    offer = rt.store.get_offer(offer_id) if offer_id else None
    if offer is None:
        raise _not_found("DECISION_NOT_FOUND", f"There is no deal decision {decision_id}, so there is no buyer to show exposure for.")
    return _respond(_answer(rt, offer.counterparty_id, "asked", lang), started, decision_id=decision_id, offer_id=offer.offer_id)
