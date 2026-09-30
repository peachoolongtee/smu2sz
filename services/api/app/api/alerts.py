"""Alerts and reconciliation endpoints (flag `alerts`). To be mounted by the main architect.

GET /alerts projects the verified state plus live commitments (and, with `offer_id`, the latest
verdict's bound obligations) in CONSERVATIVE mode. Suggested operations are data only; nothing here
executes one. GET /reconciliation matches the log's receipts to receivables and commitments.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import Severity, alerts, reconcile
from app.api.auth import require_owner
from app.api.display import displayed
from app.api.runtime import Runtime, get_runtime
from app.domain.models import Obligation
from app.financial import EngineError
from app.verifier import bind

router = APIRouter(dependencies=[Depends(require_owner)])


def _require_enabled(rt: Runtime) -> None:
    if not rt.settings.features.alerts:
        raise HTTPException(403, detail={"code": "FEATURE_DISABLED", "feature": "alerts",
                                         "message": "Alerts and reconciliation are switched off (FEATURE_ALERTS)."})


def _offer_obligations(rt: Runtime, offer_id: str | None) -> list[Obligation]:
    if not offer_id:
        return []
    verdict_id = rt.latest_verdict.get(offer_id)
    verdict = rt.store.get_verdict(verdict_id) if verdict_id else None
    offer = rt.store.get_offer(offer_id)
    if verdict is None or offer is None:
        raise HTTPException(404, "no verdict for this offer; POST /offers/{id}/evaluate first")
    if verdict.bound_obligations:
        return list(verdict.bound_obligations)
    # the stored Verdict may not carry its bound obligations; re-bind the typed offer deterministically
    bound, _notes = bind(offer, rt.store.get_state())
    return bound


@router.get("/alerts")
def get_alerts(offer_id: str | None = None) -> dict[str, Any]:
    rt = get_runtime()
    _require_enabled(rt)
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            found = alerts(state, mandate, rt.store, rt.day, obligations=_offer_obligations(rt, offer_id))
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
    return {
        "day": rt.day,
        "basis": "CONSERVATIVE",
        "projected_offer_id": offer_id,
        "counts": {s.value: sum(1 for a in found if a.severity == s) for s in Severity},
        "alerts": displayed([json.loads(a.model_dump_json()) for a in found]),
        "note": "Suggested operations are never executed automatically; submit them to POST /operations.",
    }


@router.get("/reconciliation")
def get_reconciliation() -> dict[str, Any]:
    rt = get_runtime()
    _require_enabled(rt)
    with rt.lock:
        report = reconcile(rt.store, day=rt.day)
    return {"reconciliation": displayed(json.loads(report.model_dump_json()))}
