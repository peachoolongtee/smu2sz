"""The deal summary (brief 03 §5.2): one card per buyer, composed read-only from the owner-confirmed contract and the
current books. Owner only: it discloses a buyer's contract terms."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_feature, require_owner
from app.api.deal_offers import with_offers
from app.api.exposure_words import customer_back, query_buyer
from app.api.runtime import get_runtime
from app.api.selection import Selection, build_context, selection
from app.api.worklist import queue
from app.config import get_settings
from app.deals import deal_summary, deals
from app.deals.purchases import purchases
from app.decisions.identity import deal_id

router = APIRouter(dependencies=[Depends(require_owner), Depends(require_feature("contracts"))])


def _with_back(rt: Any, rows: list[dict[str, Any]], lang: Literal["en", "zh"], customer: str | None, invoice: str | None,
               path: str | None) -> None:
    """`open_offer.context.back` on the open offer of the buyer the query names (`customer`, or the owner of `invoice`): back to that
    customer's page, built the way the Customer overview builds its own (`exposure_words.customer_back`). Nothing without either."""
    if not customer and not invoice:
        return
    state = rt.store.get_state()
    buyer = query_buyer(state, customer, invoice)
    for row in rows:
        offer = row.get("open_offer")
        if offer is None or row["counterparty_id"] != buyer:
            continue
        back = customer_back(rt, state, lang, customer=customer, invoice=invoice, decision=deal_id(offer["offer_id"]), path=path)
        if back is not None:
            offer["context"] = {"back": back}


@router.get("/deals")
def list_deals(lang: Literal["en", "zh"] = "en", *, sel: Annotated[Selection, Depends(selection)]) -> dict:
    rt = get_runtime()
    with rt.lock:
        rows = with_offers(rt, deals(rt.store, rt.day, lang), lang)
        _with_back(rt, rows, lang, sel.customer, sel.invoice, sel.path)
        out = {"day": rt.day, "lang": lang, "deals": rows, "queue": queue(rt, lang),
               "context": build_context(rt, lang, sel, page="deals")}
        if get_settings().features.capex_contracts:  # ADR-0013: the buying side, only when it is switched on and only
            bought = purchases(rt.store, rt.day, lang)  # when there is a capex contract, so every other read is unchanged
            if bought:
                out["purchases"] = bought
        return out


@router.get("/deals/{counterparty_id}")
def get_deal(counterparty_id: str, lang: Literal["en", "zh"] = "en", *, sel: Annotated[Selection, Depends(selection)]) -> dict:
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        if not any(c.id == counterparty_id and c.role == "BUYER" for c in state.counterparties):
            raise HTTPException(404, {"code": "UNKNOWN_BUYER", "message": f"{counterparty_id} is not a buyer on your "
                                                                          f"registry"})
        rows = with_offers(rt, [deal_summary(rt.store, counterparty_id, rt.day, lang)], lang)
        _with_back(rt, rows, lang, sel.customer, sel.invoice, sel.path)
        return {"day": rt.day, "lang": lang, "deal": rows[0], "context": build_context(rt, lang, sel, page="deals", buyer=counterparty_id)}
