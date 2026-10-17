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

    GET /buyers/{buyer_id}/exposure?lang=en|zh&spare=0|1

The buyer-keyed read (no deal needed): the same block for the buyer on the books as they stand (`buyer_exposure` with no offer), flattened to
what the Receivables aside and the Customer page read: `concentration`, `payments`, `stress` (its 30-day row carries `net_later_text`, what
the buyer's open invoices leave the owner a month later, from `net_at_collection`), `capacity` ({before, spare}) and the band's sentences.
Cached like the Customer overview (the books, the mandate, the day, the commitments, the buyer, the language, `spare`, the inputs, the
store's change marker and the flag). With the flag off it answers 404 with a sentence. When the query carries `customer`, `invoice` or
`decision` (with `path`) the read also carries `context.back` {label, href}, built after the cache and following the origin: a `decision`
back to the deal (`/deals?decision=&path=&customer=`), else an `invoice` back to Receivables (`/receivables?invoice=&customer=`), else
`customer` back to the Customer page (`app.api.exposure_words.origin_back`), unless `from=deal|invoice|customer` names the origin; a part that names another buyer is ignored.

The deal reads also carry, per path, the Deals queue's words (`paths[*].lowest_display`, `lowest_when`, `lowest_when_text`, `limit_word`,
`limit_text`, `share_after_text`; `app.api.exposure_words`) and a `do_nothing` path, `customer_context` (the Customer overview's own
contribution function), all worked out once with the cached block (`deal_words`), and, when the query carries `customer` or `invoice`,
`context.back` to the customer's page. Both also echo the three selections beside `context.back` (so only when the query carries `customer` or `invoice`; a bare read has no
`context`): `customer` (the offer's buyer), `deal` (the deal's decision id) and `scenario` (the path read, `asked` for the decision read). `limit_word` is null (with `limit_text`) for a reply the picture cannot draw or price and for
`do_nothing`. `do_nothing` carries words only: its entries in `stress.paths`, `capacity` and `band.by_path` are explicit nulls.

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

from app.api.caches import books_generation
from app.api.customer_overview import customer_context
from app.api.decisions import is_lapsed, lapsed_by_agreement, latest_verdict_for
from app.api.display import displayed
from app.api.exposure_words import customer_back, net_later, origin_back
from app.api.features import _MESSAGES, require_feature
from app.api.presentation import lapsed_offer_text, t
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.config import get_settings
from app.decisions.identity import deal_id, offer_id_of
from app.domain.models import CompiledOffer
from app.financial import EngineError
from app.strategy import exposure as assembly
from app.strategy.cache import AnswerCache, cache_key
from app.strategy.inputs import inputs_from_store

router = APIRouter()
log = logging.getLogger(__name__)

_RESPONSE = re.compile(r"^(asked|counter:[0-9]{1,3})$")


_BUYER_CACHE: AnswerCache[dict[str, Any]] = AnswerCache(assembly.CACHE_SIZE)
# The offer and decision reads' assembled block, by everything it is read from (the books, the mandate, the day, the commitments in force
# so the state version moves the key, the verdict, the log's change marker, the customer inputs, the language, `spare`, the lead path and
# the flag the route is behind), so a repeated read (the Deals page asks for the same block again and again) neither rebuilds the books
# nor reaches the assembly.
_ANSWERS: AnswerCache[dict[str, Any]] = AnswerCache(64)


def clear_cache() -> None:
    assembly.clear_cache()
    _BUYER_CACHE.clear()
    _ANSWERS.clear()


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


def _answer(rt: Runtime, offer: CompiledOffer, response: str, lang: Literal["en", "zh"], spare: bool, deal_words: bool = True) -> dict[str, Any]:
    """The block for the offer's buyer: the books (without this offer's own commitments), the mandate, the day, the verdict and the
    owner's inputs are read together under the runtime's lock; the assembly is cached and does its own locking for the log."""
    with rt.lock:
        state = rt.store.get_state()
        mandate = rt.store.get_mandate()
        held_all = tuple(rt.store.commitments())
        held = tuple(c for c in held_all if c.offer_id != offer.offer_id)  # the offer as asked, not as booked later
        day = rt.day
        inputs = inputs_from_store(rt.store)
        verdict = latest_verdict_for(rt, offer.offer_id)
        lapsed = verdict is not None and is_lapsed(state, mandate, held_all, offer.offer_id, verdict)
        marker = rt.store.change_marker()
    if lapsed:  # the same rule as the picture's "no longer drawn" and the decision's LAPSED: there is nothing to read, and nothing to retry
        said = lapsed_offer_text(lang, lapsed_by_agreement(held_all, offer.offer_id, verdict))
        raise HTTPException(409, detail={"code": "OFFER_LAPSED", "message": said, "message_when": said})
    if not any(c.id == offer.counterparty_id for c in state.counterparties):
        raise _not_found("BUYER_NOT_FOUND", f"There is no buyer {offer.counterparty_id} on the books.")
    try:
        lead = assembly.lead_key(verdict, response)  # the counters can change between the check of `response` and this read
    except ValueError:
        raise _not_found("COUNTER_NOT_FOUND", f"Offer {offer.offer_id} has no {response} any more: its counter-offers changed "
                                              "while you were reading. Read it again.") from None
    key = cache_key(state, mandate, day, held_all, "offer-exposure", offer.offer_id, verdict.id if verdict is not None else "", marker,
                    inputs.digest(), lang, bool(spare), lead, deal_words, books_generation())  # the log's counts start again after a reset

    def build() -> dict[str, Any]:
        books = current_books(state, held)
        return assembly.exposure(rt, books, mandate, day, offer, verdict, lang, held, inputs, response=response, spare=spare,
                                 deal_words=deal_words)

    try:
        core = _ANSWERS.get_or_compute(key, build)
    except EngineError as exc:
        raise HTTPException(422, f"cannot project: {exc}") from None
    return {"buyer_id": offer.counterparty_id, "buyer_name": core["buyer"]["name"], "response": response, "lang": lang, **core,
            "state_version": state.state_version, "day": day}


def _respond(core: dict[str, Any], started: float, back: dict[str, str] | None = None, echo: dict[str, str] | None = None,
             **ids: str) -> dict[str, Any]:
    """The body, with `context` only when the query asked for a way back (as before): {back, customer, deal, scenario}, the last three
    being the selections Home V2 keeps in its URL (`echo`: the offer's buyer, the deal and the scenario read). A bare read has no context."""
    body = displayed({**ids, **core, "computed_in_seconds": round(time.perf_counter() - started, 3)})
    if back is None:
        return body
    return {**body, "context": {"back": back, **(echo or {})}}


def _selected(offer: CompiledOffer, scenario: str) -> dict[str, str]:
    """The three selections this read is about: the offer's buyer, the deal (its decision id) and the scenario (the path whose stress and
    capacity sentences lead: `asked` or a counter key)."""
    return {"customer": offer.counterparty_id, "deal": deal_id(offer.offer_id), "scenario": scenario}


def _back(rt: Runtime, offer: CompiledOffer, lang: Literal["en", "zh"], customer: str | None, invoice: str | None, path: str | None
          ) -> dict[str, str] | None:
    """`context.back`: only when the query carries `customer` or `invoice`; the deal itself is this read's offer."""
    if not customer and not invoice:
        return None
    with rt.lock:
        return customer_back(rt, rt.store.get_state(), lang, customer=customer, invoice=invoice, decision=deal_id(offer.offer_id), path=path)


@router.get("/offers/{offer_id}/exposure")
def get_offer_exposure(offer_id: str, response: str = Query("asked"), lang: Literal["en", "zh"] = Query("en"),
                       spare: int = Query(1, ge=0, le=1), customer: str | None = Query(None, max_length=120),
                       invoice: str | None = Query(None, max_length=120), path: str | None = Query(None, max_length=120)) -> dict[str, Any]:
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer = _offer(rt, offer_id)
    _check_response(rt, offer_id, response)
    core = _answer(rt, offer, response, lang, bool(spare))
    return _respond(core, started, _back(rt, offer, lang, customer, invoice, path), _selected(offer, response), offer_id=offer_id)


@router.get("/decisions/{decision_id}/exposure")
def get_decision_exposure(decision_id: str, lang: Literal["en", "zh"] = Query("en"), spare: int = Query(0, ge=0, le=1),
                          customer: str | None = Query(None, max_length=120), invoice: str | None = Query(None, max_length=120),
                          path: str | None = Query(None, max_length=120)) -> dict[str, Any]:
    """A deal decision (`deal:<offer_id>`) is about that offer's buyer, asked as it was. Any other decision (a funding
    decision) is about no buyer: 404."""
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer_id = offer_id_of(decision_id)
    offer = rt.store.get_offer(offer_id) if offer_id else None
    if offer is None:
        raise _not_found("DECISION_NOT_FOUND", f"There is no deal decision {decision_id}, so there is no buyer to show exposure for.")
    core = _answer(rt, offer, "asked", lang, bool(spare))
    return _respond(core, started, _back(rt, offer, lang, customer, invoice, path), _selected(offer, "asked"), decision_id=decision_id,
                    offer_id=offer.offer_id)


# ---------------------------------------------------------------- the buyer-keyed read (no deal needed)


def _buyer_block(rt: Runtime, buyer_id: str, lang: Literal["en", "zh"], spare: bool) -> dict[str, Any]:
    """The buyer's exposure on the books as they stand, flattened for the pages that have no deal. Raises `EngineError` when the books
    cannot be projected."""
    with rt.lock:
        state = rt.store.get_state()
        mandate = rt.store.get_mandate()
        held = tuple(rt.store.commitments())
        books = current_books(state, held)
        day = rt.day
        inputs = inputs_from_store(rt.store)
    core = assembly.buyer_exposure(rt, books, mandate, day, buyer_id, "", None, lang, held, inputs, spare=spare)
    today = max(day, state.as_of_day)
    stress = core["stress"]
    later = net_later(books.state, buyer_id, today, stress["delay_days"], lang) or {"net_later_fen": None, "net_later_text": None}
    stress = {**stress, "now": {**stress["now"], **later}}  # null when the buyer has no open invoice
    view = core["capacity"][assembly.ASKED]
    capacity = {"available": view["available"], "unavailable_text": view["unavailable_text"], "before": view.get("before"), "spare": view["spare"]}
    return {"buyer_id": buyer_id, "buyer_name": core["buyer"]["name"], "lang": lang, "buyer": core["buyer"],
            "concentration": core["concentration"], "payments": core["payments"], "payments_note": core["payments_note"],
            "stress": stress, "capacity": capacity, "band": {k: core["band"][k] for k in ("concentration", "stress", "capacity")},
            "flag": core["flag"], "spare_read": spare, "partial": False, "economics": None,
            "customer_context": customer_context(state, inputs, buyer_id, today, core["concentration"], lang),
            "state_version": state.state_version, "day": day}


@router.get("/buyers/{buyer_id}/exposure")
def get_buyer_exposure(buyer_id: str, lang: Literal["en", "zh"] = Query("en"), spare: int = Query(1, ge=0, le=1),
                       customer: str | None = Query(None, max_length=120), invoice: str | None = Query(None, max_length=120),
                       decision: str | None = Query(None, max_length=120), path: str | None = Query(None, max_length=120),
                       origin: Literal["deal", "invoice", "customer"] | None = Query(None, alias="from")) -> dict[str, Any]:
    if not get_settings().features.exposure:  # this route answers 404 with a sentence, so a page without the feature reads "no exposure"
        raise HTTPException(404, detail={"code": "FEATURE_DISABLED", "feature": "exposure",
                                         "message": t(lang, _MESSAGES["exposure"], "买家风险敞口功能尚未开启（FEATURE_EXPOSURE）。")})
    started = time.perf_counter()
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        if not any(c.id == buyer_id and c.role == "BUYER" for c in state.counterparties):
            raise _not_found("BUYER_NOT_FOUND", t(lang, "There is no such customer on your books.", "您的账目中没有这位客户。"))
        key = cache_key(state, mandate, max(rt.day, state.as_of_day), tuple(rt.store.commitments()), "buyer-exposure", buyer_id, lang, spare,
                        inputs_from_store(rt.store).digest(), rt.store.change_marker(), books_generation())
    try:
        body = _BUYER_CACHE.get_or_compute(key, lambda: displayed(_buyer_block(rt, buyer_id, lang, bool(spare))))
    except EngineError as exc:
        raise HTTPException(422, f"cannot project: {exc}") from None
    out = {**body, "computed_in_seconds": round(time.perf_counter() - started, 3)}
    if not (customer or invoice or decision):
        return out
    # `context.back`, built from the query after the cache (never cached) and following the origin: the deal, the invoice in Receivables or the
    # Customer page (`exposure_words.origin_back`; `from` = deal | invoice | customer names the origin and decides when the query supports it). A part that names another buyer's is ignored, never echoed.
    with rt.lock:
        back = origin_back(rt, rt.store.get_state(), lang, buyer_id, customer=customer, invoice=invoice, decision=decision, path=path, origin=origin)
    if back is None:
        return out
    return {**out, "context": {"back": back}}
