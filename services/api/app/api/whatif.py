"""What-if sandbox routes. DISPLAY-ONLY: they read the current state and mandate, run the verifier on
a hypothetical package and return a view marked `hypothetical: true`. Nothing is written, logged as
an operation or executed. Mounted by the main architect in app/main.py:

    from app.api.whatif import router as whatif_router
    app.include_router(whatif_router)
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.runtime import get_runtime
from app.domain.models import FinancialState, Mandate
from app.whatif import PRESETS, WhatIfParamError, WhatIfParams, presets, simulate

router = APIRouter(tags=["whatif"])

_warm_lock = threading.Lock()
_warmed: set[str] = set()


def _prewarm(state: FinancialState, mandate: Mandate, key_hex: str, day: int) -> None:
    """Fill the cache for the preset positions in the background, so the preset buttons answer from
    the cache. Best effort: a failure here only means a cold request later."""
    for p in PRESETS.values():
        try:
            simulate(state, mandate, p, trusted_owner_key_hex=key_hex, day=day)
        except Exception:  # noqa: BLE001 - warm-up must never break a request
            return


def _start_prewarm() -> None:
    rt = get_runtime()
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    tag = hashlib.sha256(f"{state.model_dump_json()}|{mandate.model_dump_json()}|{rt.day}".encode()).hexdigest()
    with _warm_lock:
        if tag in _warmed:
            return
        _warmed.add(tag)
    threading.Thread(target=_prewarm, args=(state, mandate, rt.owner_key_hex, rt.day), daemon=True,
                     name="whatif-prewarm").start()


@router.get("/whatif/presets")
def get_presets() -> dict[str, Any]:
    rt = get_runtime()
    try:
        out = presets(rt.store.get_state(), rt.day)
    except WhatIfParamError as e:
        raise HTTPException(422, str(e)) from e
    _start_prewarm()
    return {"hypothetical": True, **out}


@router.post("/whatif")
def post_whatif(params: WhatIfParams) -> dict[str, Any]:
    rt = get_runtime()
    try:
        result = simulate(rt.store.get_state(), rt.store.get_mandate(), params,
                          trusted_owner_key_hex=rt.owner_key_hex, day=rt.day)
    except WhatIfParamError as e:
        raise HTTPException(422, str(e)) from e
    return result.model_dump()
