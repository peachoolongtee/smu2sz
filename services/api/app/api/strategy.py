"""The strategy MVP's routes (wayfinder map #47, docs/STRATEGY_MVP_BRIEF.md section 4): one router that mounts the
three answers' sub-routers, and from map #88 the buyer-exposure routes and the customer-inputs routes. Every route calls
`require_feature()` first, so with the flags off (the default) each answers 403 FEATURE_DISABLED and nothing else in the app
changes. The answers are read-only: no route writes, logs an operation or stores a verdict. The one writer here is the
customer-inputs route, which appends context rows (not books) to its own table. Mounted in app/main.py as `strategy_router`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_owner
from app.api.customer_inputs import router as customer_inputs_router
from app.api.strategy_collections import router as collections_router
from app.api.strategy_compare import router as compare_router
from app.api.strategy_curve import router as curve_router
from app.api.strategy_envelope import router as envelope_router
from app.api.strategy_exposure import router as exposure_router

router = APIRouter(tags=["strategy"], dependencies=[Depends(require_owner)])
router.include_router(curve_router)
router.include_router(envelope_router)
router.include_router(collections_router)
router.include_router(exposure_router)
router.include_router(compare_router)
router.include_router(customer_inputs_router)
