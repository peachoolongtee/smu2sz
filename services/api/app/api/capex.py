"""POST /capex/evaluate (flag FEATURE_CAPEX; spec v2 §7.7). Mounted by the main architect.

Returns a `displayed()` CapexView and queues an ApplyForFacility for the selected structure through
the executor, as the AGENT. A new facility is Tier 2, so the executor answers PENDING_APPROVAL and
nothing happens until the owner approves it on /approvals/{id}.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_owner
from app.api.display import displayed
from app.api.runtime import get_runtime
from app.capex import CapexDisabled, CapexRequest, CapexResult, evaluate_capex
from app.domain.models import Actor, ApplyForFacility, OperationResult

router = APIRouter(dependencies=[Depends(require_owner)])


def _with_null_displays(x: Any) -> Any:
    """Give every null `<name>_fen` a null `<name>_display`, so the UI always finds the key."""
    if isinstance(x, list):
        return [_with_null_displays(v) for v in x]
    if not isinstance(x, dict):
        return x
    out = {k: _with_null_displays(v) for k, v in x.items()}
    for k, v in x.items():
        if v is None and k.endswith("_fen"):
            out.setdefault(k[:-4] + "_display", None)
    return out


def _application_key(result: CapexResult, day: int) -> str:
    """Same request on the same verified state, mandate and day -> same key (the executor then
    returns DUPLICATE with the original approval id instead of queueing it twice)."""
    basis = json.dumps({"request": json.loads(result.request.model_dump_json()),
                        "selected": result.selected_id, "state_version": result.state_version,
                        "mandate_version": result.mandate_version, "day": day}, sort_keys=True)
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def _queue_application(result: CapexResult) -> OperationResult | None:
    """ApplyForFacility for the selected structure, requested by the agent and dated today."""
    if not result.worth_doing or result.selected_facility_id is None:
        return None
    rt = get_runtime()
    key = _application_key(result, rt.day)
    op = ApplyForFacility(
        op_id=f"capex-apply-{key}", idempotency_key=f"capex:{key}", mandate_version=result.mandate_version,
        requested_by=Actor.AGENT, day=rt.day, facility_id=result.selected_facility_id,
        amount_fen=result.request.price_fen,
    )
    return rt.executor.execute(op)


def capex_view(result: CapexResult, applied: OperationResult | None, approval_status: str | None) -> dict:
    body = json.loads(result.model_dump_json())
    body["approval_id"] = applied.approval_id if applied else None
    body["approval_status"] = approval_status
    body["application"] = json.loads(applied.model_dump_json()) if applied else None
    return _with_null_displays(displayed(body))


@router.post("/capex/evaluate")
def post_capex_evaluate(body: CapexRequest | None = None) -> dict:
    request = body or CapexRequest()
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            result = evaluate_capex(request, state, mandate, commitments=rt.store.commitments())
        except CapexDisabled as exc:
            raise HTTPException(403, detail={"code": exc.code.value, "message": str(exc)}) from None
        applied = _queue_application(result)
        status = None
        if applied is not None and applied.approval_id:
            rec = rt.store.get_approval(applied.approval_id)
            status = str(getattr(rec.status, "value", rec.status)) if rec is not None else None
    return capex_view(result, applied, status)
