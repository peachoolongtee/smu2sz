"""The deal summary (brief 03 §5.2): one card per buyer, composed read-only from the owner-confirmed contract and the
current books. Owner only: it discloses a buyer's contract terms."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_feature, require_owner
from app.api.deal_offers import with_offers
from app.api.runtime import get_runtime
from app.deals import deal_summary, deals

router = APIRouter(dependencies=[Depends(require_owner), Depends(require_feature("contracts"))])


@router.get("/deals")
def list_deals(lang: Literal["en", "zh"] = "en") -> dict:
    rt = get_runtime()
    with rt.lock:
        return {"day": rt.day, "lang": lang, "deals": with_offers(rt, deals(rt.store, rt.day, lang), lang)}


@router.get("/deals/{counterparty_id}")
def get_deal(counterparty_id: str, lang: Literal["en", "zh"] = "en") -> dict:
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        if not any(c.id == counterparty_id and c.role == "BUYER" for c in state.counterparties):
            raise HTTPException(404, {"code": "UNKNOWN_BUYER", "message": f"{counterparty_id} is not a buyer on your "
                                                                          f"registry"})
        return {"day": rt.day, "lang": lang, "deal": with_offers(rt, [deal_summary(rt.store, counterparty_id, rt.day, lang)], lang)[0]}
