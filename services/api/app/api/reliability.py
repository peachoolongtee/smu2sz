"""GET /reliability: what the agent has learned about how each buyer pays, and the open deals ranked by it.

Read-only and advisory (app.reliability): it never changes a verdict, a counter or the books. `offer_id` (repeatable)
names the deals to rank; each comes with the business action of its latest verdict when it has one.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_owner
from app.api.presentation import business_action
from app.api.runtime import get_runtime
from app.reliability import profiles, rank_deals

router = APIRouter(dependencies=[Depends(require_owner)])


@router.get("/reliability")
def get_reliability(lang: str = "en", offer_id: Annotated[list[str] | None, Query()] = None) -> dict[str, Any]:
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        today = max(rt.day, state.as_of_day)
        buyers = profiles(state, mandate, rt.store, today, lang)
        latest = {v.offer_id: v for v in rt.store.verdicts()}  # first-stored order: the last one per offer wins
        deals = []
        for oid in dict.fromkeys(offer_id or []):
            offer = rt.store.get_offer(oid)
            if offer is None:
                continue
            v = rt.store.get_verdict(rt.latest_verdict[oid]) if oid in rt.latest_verdict else latest.get(oid)
            deals.append({"offer_id": oid, "counterparty_id": offer.counterparty_id,
                          "business_action": business_action(v.outcome.value, len(v.counters)) if v else None})
        buyer_ids = {b["counterparty_id"] for b in buyers}
        ranked = rank_deals(buyers, [d for d in deals if d["counterparty_id"] in buyer_ids], lang)
    return {"as_of_day": today, "buyers": buyers, "deals": ranked,
            "method": ("Learned from each buyer's invoices: imported history before the books started and every receipt "
                       "from the bank feed since. Recent payments count more (a year-old payment counts half). Advisory "
                       "only: the deal check itself never uses this score.")}
