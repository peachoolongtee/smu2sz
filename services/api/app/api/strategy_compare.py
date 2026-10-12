"""The scenario comparator routes (map #88 Phase 3, ticket #100; flag `exposure`, no new flag; brief section D).

    GET /offers/{offer_id}/compare?lang=en|zh&late=0|30
    GET /decisions/{decision_id}/compare?lang=en|zh&late=0|30

What each answer to an evaluated offer does to cash, row by row in the brief's order (the books as they stand, the offer as asked, each
counter, the buyer stopping), with `late` as an overlay on every row (`app.strategy.comparator` composes it; the 15-day delay is not
offered). A `deal:<offer_id>` decision reads its offer. The books are those without the offer's own commitments (the offer as asked,
as the picture draws it); the books, the mandate, the day, the commitments, the verdict and the owner's inputs are read together under
the runtime's lock and the comparison runs outside it. The economics context (a year's gross profit from the buyer, the Customer
overview's one function) is added only with FEATURE_CUSTOMER_ECONOMICS on and a contribution held.

Read-only and hypothetical: nothing is written, logged or stored; nothing here changes a verdict. Cached by
`app.strategy.comparator` (32 entries, single-flight). An offer not yet evaluated has nothing to compare: 404 with a sentence.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.customer_overview import share_of_year, twelve_months_of, year_held
from app.api.decisions import latest_verdict_for
from app.api.features import require_feature
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.config import get_settings
from app.decisions.identity import offer_id_of
from app.domain.models import CompiledOffer
from app.financial import EngineError
from app.strategy import comparator
from app.strategy.inputs import inputs_from_store

router = APIRouter()


def clear_cache() -> None:
    comparator.clear_cache()


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(404, detail={"code": code, "message": message})


def _compare(rt: Runtime, offer: CompiledOffer, lang: Literal["en", "zh"], late: int) -> dict[str, Any]:
    with rt.lock:
        state = rt.store.get_state()
        mandate = rt.store.get_mandate()
        held = tuple(c for c in rt.store.commitments() if c.offer_id != offer.offer_id)  # the offer as asked, not as booked later
        books = current_books(state, held)
        day = rt.day
        inputs = inputs_from_store(rt.store)
        verdict = latest_verdict_for(rt, offer.offer_id)
    if verdict is None:
        raise _not_found("NO_VERDICT_YET", "Evaluate the offer first: there is nothing to compare yet.")
    if not any(c.id == offer.counterparty_id for c in state.counterparties):
        raise _not_found("BUYER_NOT_FOUND", f"There is no buyer {offer.counterparty_id} on the books.")
    year: comparator.Year | None = None
    if get_settings().features.customer_economics:
        held_year = year_held(state, inputs, offer.counterparty_id, max(day, state.as_of_day))
        if held_year is not None:
            horizon, contribution = mandate.forward_concession_horizon_days, held_year.contribution_fen
            year = comparator.Year(contribution, held_year.sales_fen, held_year.assumed, held_year.gross,
                                   lambda fen: share_of_year(twelve_months_of(fen, horizon), contribution))
    try:
        body = comparator.compare(rt, books, mandate, day, offer, verdict, held, inputs, lang=lang, late=late, year=year)
    except EngineError as exc:
        raise HTTPException(422, f"cannot project: {exc}") from None
    return {**body, "state_version": state.state_version, "day": day}


def _late(late: int) -> int:
    if late not in comparator.LATE_DELAYS:
        raise HTTPException(422, detail={"code": "BAD_LATE", "message": "late is 0 or 30 (days)."})
    return late


@router.get("/offers/{offer_id}/compare")
def get_offer_compare(offer_id: str, lang: Literal["en", "zh"] = Query("en"), late: int = Query(0)) -> dict[str, Any]:
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer = rt.store.get_offer(offer_id)
    if offer is None:
        raise _not_found("OFFER_NOT_FOUND", f"There is no offer {offer_id}.")
    body = _compare(rt, offer, lang, _late(late))
    return {**body, "computed_in_seconds": round(time.perf_counter() - started, 3)}


@router.get("/decisions/{decision_id}/compare")
def get_decision_compare(decision_id: str, lang: Literal["en", "zh"] = Query("en"), late: int = Query(0)) -> dict[str, Any]:
    """A deal decision (`deal:<offer_id>`) compares that offer's answers. Any other decision is about no offer: 404."""
    require_feature("exposure")
    started = time.perf_counter()
    rt = get_runtime()
    offer_id = offer_id_of(decision_id)
    offer = rt.store.get_offer(offer_id) if offer_id else None
    if offer is None:
        raise _not_found("DECISION_NOT_FOUND", f"There is no deal decision {decision_id}, so there is no offer to compare.")
    body = _compare(rt, offer, lang, _late(late))
    return {**body, "decision_id": decision_id, "computed_in_seconds": round(time.perf_counter() - started, 3)}
