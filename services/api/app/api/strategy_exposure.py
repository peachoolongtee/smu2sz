"""The buyer-exposure routes (map #88 Phase 1; flag `exposure`; brief H.5 and section K).

    GET /offers/{offer_id}/exposure?response=asked|counter:<k>&lang=en|zh&spare=0|1
    GET /decisions/{decision_id}/exposure?lang=en|zh&spare=0|1

What a deal does to the exposure to one buyer, for ALL the offer's paths at once (the offer as asked and each counter, under the
Deals page's own keys): the concentration, how the buyer has paid, the 30-day late-payment stress and the capacity before and after
each path, with the sentences of the Deals band written for `lang` (`app.strategy.exposure` assembles it). `response` names the path
whose stress and capacity sentences lead (`band`); switching the picked column needs no new request, so it is not part of the cache
key. Both ids resolve to the same buyer: an offer's counterparty, and for a `deal:<offer_id>` decision that offer's (read as asked).

`spare` says whether to run the spare-capacity search, "how much more FLOW could still cover alone": a router search that costs
about 0.6 s on the Demo (about 2.4 s cold for an offer with two counters, four searches) and about 30 s per search on the public SME,
for the books as they stand and for each path. With `spare=0` it is skipped and `capacity[*].spare` and the capacity sentences are
null; each search is cached once computed, so a later `spare=1` read pays only for what has not been searched. The offer read
defaults to `spare=1` (the Deals page shows the room), and a caller on a large book should pass `spare=0` for the light read. The
decision read defaults to `spare=0`: a decision page does not wait on a search, and asks for `spare=1` when it wants the room.

Read-only and hypothetical: nothing is written, logged or stored; concentration, payment behaviour, stress and capacity are context,
never a mandate, and change no verdict. The books are those without this offer's own commitments (the offer as asked, as the picture
draws it). Cached through `app.strategy.exposure` (32 entries, single-flight) by the books, the mandate, the day, the commitments, the
buyer, the verdict, the language and the customer inputs in force. Mounted through `app/api/strategy.py`, which carries the owner check.
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
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.decisions.identity import offer_id_of
from app.domain.models import CompiledOffer
from app.financial import EngineError
from app.strategy import exposure as assembly
from app.strategy.inputs import inputs_from_store

router = APIRouter()
log = logging.getLogger(__name__)

_RESPONSE = re.compile(r"^(asked|counter:[0-9]{1,3})$")


def clear_cache() -> None:
    assembly.clear_cache()


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


def _answer(rt: Runtime, offer: CompiledOffer, response: str, lang: Literal["en", "zh"], spare: bool) -> dict[str, Any]:
    """The block for the offer's buyer: the books (without this offer's own commitments), the mandate, the day, the verdict and the
    owner's inputs are read together under the runtime's lock; the assembly is cached and does its own locking for the log."""
    with rt.lock:
        state = rt.store.get_state()
        mandate = rt.store.get_mandate()
        held = tuple(c for c in rt.store.commitments() if c.offer_id != offer.offer_id)  # the offer as asked, not as booked later
        books = current_books(state, held)
        day = rt.day
        inputs = inputs_from_store(rt.store)
        verdict = latest_verdict_for(rt, offer.offer_id)
    if not any(c.id == offer.counterparty_id for c in state.counterparties):
        raise _not_found("BUYER_NOT_FOUND", f"There is no buyer {offer.counterparty_id} on the books.")
    try:
        assembly.lead_key(verdict, response)  # the counters can change between the check of `response` and this read
    except ValueError:
        raise _not_found("COUNTER_NOT_FOUND", f"Offer {offer.offer_id} has no {response} any more: its counter-offers changed "
                                              "while you were reading. Read it again.") from None
    try:
        core = assembly.exposure(rt, books, mandate, day, offer, verdict, lang, held, inputs, response=response, spare=spare)
    except EngineError as exc:
        raise HTTPException(422, f"cannot project: {exc}") from None
    return {"buyer_id": offer.counterparty_id, "buyer_name": core["buyer"]["name"], "response": response, "lang": lang, **core,
            "state_version": state.state_version, "day": day}


def _respond(core: dict[str, Any], started: float, **ids: str) -> dict[str, Any]:
    return displayed({**ids, **core, "computed_in_seconds": round(time.perf_counter() - started, 3)})


@router.get("/offers/{offer_id}/exposure")
def get_offer_exposure(offer_id: str, response: str = Query("asked"), lang: Literal["en", "zh"] = Query("en"),
                       spare: int = Query(1, ge=0, le=1)) -> dict[str, Any]:
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer = _offer(rt, offer_id)
    _check_response(rt, offer_id, response)
    return _respond(_answer(rt, offer, response, lang, bool(spare)), started, offer_id=offer_id)


@router.get("/decisions/{decision_id}/exposure")
def get_decision_exposure(decision_id: str, lang: Literal["en", "zh"] = Query("en"), spare: int = Query(0, ge=0, le=1)) -> dict[str, Any]:
    """A deal decision (`deal:<offer_id>`) is about that offer's buyer, asked as it was. Any other decision (a funding
    decision) is about no buyer: 404."""
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer_id = offer_id_of(decision_id)
    offer = rt.store.get_offer(offer_id) if offer_id else None
    if offer is None:
        raise _not_found("DECISION_NOT_FOUND", f"There is no deal decision {decision_id}, so there is no buyer to show exposure for.")
    return _respond(_answer(rt, offer, "asked", lang, bool(spare)), started, decision_id=decision_id, offer_id=offer.offer_id)
