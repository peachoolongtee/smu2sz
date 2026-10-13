"""What-if sandbox routes. DISPLAY-ONLY: they read the current state and mandate, run the verifier on
a hypothetical package and return a view marked `hypothetical: true`. Nothing is written, logged as
an operation or executed. Mounted by the main architect in app/main.py:

    from app.api.whatif import router as whatif_router
    app.include_router(whatif_router)
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_owner
from app.api.presentation import invoice_words, party_name, t, when_text
from app.api.runtime import get_runtime
from app.domain.models import Commitment, FinancialState, Mandate
from app.strategy.words import buyer_short
from app.whatif import PRESETS, WhatIfParamError, WhatIfRequest, presets, resolve, simulate

router = APIRouter(tags=["whatif"], dependencies=[Depends(require_owner)])

_warm_lock = threading.Lock()
_warmed: set[str] = set()


def _prewarm(state: FinancialState, mandate: Mandate, key_hex: str, day: int,
             commitments: Sequence[Commitment] = (), buyer_id: str | None = None) -> None:
    """Fill the cache for the preset positions in the background, so the preset buttons answer from
    the cache. Best effort: a failure here only means a cold request later."""
    for p in PRESETS.values():
        try:
            simulate(state, mandate, p, trusted_owner_key_hex=key_hex, day=day, commitments=commitments, buyer_id=buyer_id)
        except Exception:  # noqa: BLE001 - warm-up must never break a request
            return


def _start_prewarm(buyer_id: str | None = None) -> None:
    rt = get_runtime()
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    commitments = tuple(rt.store.commitments())
    held = "|".join(c.model_dump_json() for c in commitments)
    tag = hashlib.sha256(f"{state.model_dump_json()}|{mandate.model_dump_json()}|{rt.day}|{held}|{buyer_id}".encode()).hexdigest()
    with _warm_lock:
        if tag in _warmed:
            return
        _warmed.add(tag)
    threading.Thread(target=_prewarm, args=(state, mandate, rt.owner_key_hex, rt.day, commitments, buyer_id), daemon=True,
                     name="whatif-prewarm").start()


def _buyer_for(rt: Any, state: FinancialState, offer_id: str | None, buyer_id: str | None) -> str | None:
    """The buyer the sandbox runs on: the named negotiation's, else the named buyer. None when neither is named (the books' first buyer with a
    recurring invoice, as before). A negotiation or a buyer the books do not have is a 404, never a guess."""
    if offer_id is not None:
        offer = rt.store.get_offer(offer_id)
        if offer is None:
            raise HTTPException(404, {"code": "OFFER_NOT_FOUND", "offer_id": offer_id})
        return str(offer.counterparty_id)
    if buyer_id is not None:
        if not any(c.id == buyer_id and c.role == "BUYER" for c in state.counterparties):
            raise HTTPException(404, {"code": "BUYER_NOT_FOUND", "buyer_id": buyer_id})
        return buyer_id
    return None


def _scope(state: FinancialState, today: int, buyer_id: str | None, lang: str) -> dict[str, Any]:
    """Which buyer and invoice the sandbox ran on, in words: `invoice_text` names the invoice the sliders act on ("the ¥150,000.00 invoice to
    Zhuhai Kitchenware Wholesale Co., due in 57 days", no id), and `scope_text` says why there is none when the buyer has no recurring invoice to
    extend (null when the sandbox ran). `available` says whether it did."""
    lang = "zh" if lang == "zh" else "en"
    try:
        ctx = resolve(state, today, buyer_id)
    except WhatIfParamError:
        if buyer_id is None:
            raise  # nothing was addressed and the books have no buyer to simulate: the route's own 422
        who = party_name(state, buyer_id)
        short = buyer_short(who)
        opens = sorted((r for r in state.receivables if r.counterparty_id == buyer_id and r.status == "OPEN"), key=lambda r: (r.due_day, r.id))
        recurring = sum(1 for r in state.recurring_invoices if r.counterparty_id == buyer_id)
        if recurring > 1:
            reason = t(lang, f"{short} has more than one recurring invoice; the sandbox needs exactly one.", f"{short}有多张经常性发票，沙盘只能处理一张。")
        elif recurring == 1:
            reason = t(lang, f"{short} has no open invoice for the sandbox to act on.", f"{short}没有沙盘可操作的未结发票。")
        else:
            reason = t(lang, f"{short} has no recurring invoice to extend; the sandbox needs one.", f"{short}没有可延期的经常性发票，沙盘需要一张。")
        return {"available": False, "buyer_id": buyer_id, "buyer_name": who,
                "invoice_text": (_invoice_text(state, opens[0].id, opens[0].due_day, today, lang) if opens else None), "scope_text": reason}
    due = ctx.receivable.due_day
    return {"available": True, "buyer_id": ctx.counterparty_id, "buyer_name": party_name(state, ctx.counterparty_id),
            "invoice_text": _invoice_text(state, ctx.receivable.id, due, today, lang), "scope_text": None}


def _invoice_text(state: FinancialState, receivable_id: str, due_day: int, today: int, lang: str) -> str:
    when = when_text(due_day, today, "zh" if lang == "zh" else "en")
    return t("zh" if lang == "zh" else "en", f"{invoice_words(state, receivable_id, 'en')}, due {when}",
             f"{invoice_words(state, receivable_id, 'zh')}，{when}到期")


@router.get("/whatif/presets")
def get_presets(offer_id: str | None = Query(None, max_length=120), buyer_id: str | None = Query(None, max_length=120),
                lang: str = Query("en")) -> dict[str, Any]:
    """The slider positions and grid, on the invoice of the negotiation named by `offer_id` (else `buyer_id`; neither: the books' first buyer
    with a recurring invoice). `invoice_text`, `scope_text`, `available` as on `POST /whatif`; a buyer the sandbox cannot value as a whole has
    `available` false, a `scope_text` that says why and no presets."""
    rt = get_runtime()
    state = rt.store.get_state()
    buyer = _buyer_for(rt, state, offer_id, buyer_id)
    try:
        scope = _scope(state, rt.day, buyer, lang)
    except WhatIfParamError as e:
        raise HTTPException(422, str(e)) from e
    if not scope["available"]:
        return {"hypothetical": True, **scope}
    try:
        out = presets(state, rt.day, buyer)
    except WhatIfParamError as e:
        raise HTTPException(422, str(e)) from e
    _start_prewarm(buyer)
    return {"hypothetical": True, **scope, **out}


@router.post("/whatif")
def post_whatif(request: WhatIfRequest, lang: str = Query("en")) -> dict[str, Any]:
    """The hypothetical verdict for the sliders, plus `controls` (presets, slider grid and server-formatted slider labels) so one call gives the
    page everything it shows. It runs on the invoice of the negotiation named by `offer_id` (else the buyer `buyer_id`; neither: the books' first
    buyer with a recurring invoice). `buyer_id`, `buyer_name`, `invoice_text`, `scope_text` and `available` say which buyer and invoice it ran
    on, in words; a buyer with no recurring invoice to extend has `available` false and a `scope_text` that says why, and no verdict."""
    rt = get_runtime()
    state = rt.store.get_state()
    buyer = _buyer_for(rt, state, request.offer_id, request.buyer_id)
    try:
        scope = _scope(state, rt.day, buyer, lang)
    except WhatIfParamError as e:
        raise HTTPException(422, str(e)) from e
    if not scope["available"]:
        return {"hypothetical": True, **scope, "controls": None}
    params = request.sliders()
    try:
        result = simulate(state, rt.store.get_mandate(), params, trusted_owner_key_hex=rt.owner_key_hex,
                          day=rt.day, commitments=rt.store.commitments(), buyer_id=buyer)
        controls = presets(state, rt.day, buyer)
    except WhatIfParamError as e:
        raise HTTPException(422, str(e)) from e
    _start_prewarm(buyer)
    return {**result.model_dump(), **scope, "controls": {"hypothetical": True, **controls}}
