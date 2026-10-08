"""The strategy MVP's routes (wayfinder map #47, docs/STRATEGY_MVP_BRIEF.md section 4): one router that mounts the
three answers' sub-routers. Every route calls `require_feature()` first, so with the flags off (the default) each answers
403 FEATURE_DISABLED and nothing else in the app changes. Read-only: no route writes, logs an operation or stores a verdict.
Mounted in app/main.py as `strategy_router`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_owner
from app.api.strategy_collections import router as collections_router
from app.api.strategy_curve import router as curve_router
from app.api.strategy_envelope import router as envelope_router

router = APIRouter(tags=["strategy"], dependencies=[Depends(require_owner)])
router.include_router(curve_router)
router.include_router(envelope_router)
router.include_router(collections_router)
