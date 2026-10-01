"""Alerts and reconciliation endpoints (flag `alerts`). To be mounted by the main architect.

GET /alerts projects the verified state plus live commitments (and, with `offer_id`, the latest
verdict's bound obligations) in CONSERVATIVE mode. Suggested operations are data only; POST /alerts/{id}/act
submits the cure to the executor as the agent (nothing here executes one itself). GET /reconciliation matches the log's receipts to receivables and commitments.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import Alert, Severity, alerts, cure_operations, reconcile
from app.api.auth import require_owner
from app.api.display import displayed
from app.api.runtime import Runtime, get_runtime
from app.domain.models import Obligation, OperationStatus
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
        "counts": _counts(found),
        "alerts": displayed([json.loads(a.model_dump_json()) for a in found]),
        "note": ("A suggested operation is executed only through POST /alerts/{id}/act or POST /operations, "
                 "never by itself."),
    }


def _counts(found: list[Alert]) -> dict[str, int]:
    return {s.value: sum(1 for a in found if a.severity == s) for s in Severity}


@router.post("/alerts/{alert_id}/act")
def act_on_alert(alert_id: str) -> dict[str, Any]:
    """Submit the alert's suggested cure to the executor as the agent. Tier 1 executes; Tier 2 waits in the
    approvals queue. This route never writes state itself."""
    rt = get_runtime()
    _require_enabled(rt)
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            found = alerts(state, mandate, rt.store, rt.day)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        alert = next((a for a in found if a.id == alert_id), None)
        if alert is None:
            raise HTTPException(404, detail={"code": "ALERT_NOT_FOUND", "alert_id": alert_id})
        ops = cure_operations(alert, day=rt.day, mandate_version=mandate.version, state_version=state.state_version)
        if not ops:
            raise HTTPException(409, detail={"code": "NO_EXECUTABLE_CURE", "alert_id": alert_id,
                                             "message": "This alert suggests nothing the agent may execute."})
        results = []
        for op in ops:
            r = rt.executor.execute(op)
            results.append(r)
            if r.status not in (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL):
                break
        try:
            after = alerts(rt.store.get_state(), rt.store.get_mandate(), rt.store, rt.day)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None

    def n(status: OperationStatus) -> int:
        return sum(1 for r in results if r.status == status)

    return {
        "alert_id": alert_id,
        "day": rt.day,
        "results": [json.loads(r.model_dump_json()) for r in results],
        "executed": n(OperationStatus.EXECUTED),
        "pending_approval": n(OperationStatus.PENDING_APPROVAL),
        "refused": n(OperationStatus.REFUSED),
        "cured": all(a.id != alert_id for a in after),
        "alerts_after": {"counts": _counts(after)},
    }


@router.get("/reconciliation")
def get_reconciliation() -> dict[str, Any]:
    rt = get_runtime()
    _require_enabled(rt)
    with rt.lock:
        report = reconcile(rt.store, day=rt.day)
    return {"reconciliation": displayed(json.loads(report.model_dump_json()))}
