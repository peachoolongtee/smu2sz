"""Capex routes (flag FEATURE_CAPEX; spec v2 §7.7). Mounted by the main architect.

POST /capex/evaluate returns a `displayed()` CapexView and writes nothing. POST /capex/apply (owner only) is the
separate, explicit step: it re-evaluates, and for the selected non-hypothetical structure queues an
ApplyForFacility through the executor as the AGENT. A new facility is Tier 2, so the executor answers
PENDING_APPROVAL and nothing happens until the owner approves it on /approvals/{id}.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import require_owner
from app.api.display import displayed
from app.api.runtime import get_runtime
from app.capex import CapexDisabled, CapexRequest, CapexResult, evaluate_capex
from app.domain.models import Actor, ApplyForFacility

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


def capex_view(result: CapexResult) -> dict:
    return _with_null_displays(displayed(json.loads(result.model_dump_json())))


@router.post("/capex/evaluate")
def post_capex_evaluate(body: CapexRequest | None = None) -> dict:
    """Side-effect free: nothing is written, no operation, no approval."""
    request = body or CapexRequest()
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            result = evaluate_capex(request, state, mandate, commitments=rt.store.commitments())
        except CapexDisabled as exc:
            raise HTTPException(403, detail={"code": exc.code.value, "message": str(exc)}) from None
    return capex_view(result)


class CapexApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: str
    amount_fen: int = Field(gt=0)
    state_version: int  # the state version of the evaluation the owner saw
    # The estimate the owner evaluated, when it was not the spec case; its price must equal `amount_fen`.
    request: CapexRequest | None = None


@router.post("/capex/apply")
def post_capex_apply(body: CapexApplyIn) -> dict:
    """The owner's explicit application for the selected, non-hypothetical structure. Queues one Tier-2
    ApplyForFacility for the owner's approval on /approvals/{id}; nothing is applied for until then."""
    rt = get_runtime()
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        if body.state_version != state.state_version:
            raise HTTPException(409, detail={
                "code": "STATE_VERSION_MOVED", "state_version": state.state_version,
                "message": f"The books moved since the evaluation (state version {body.state_version}, now "
                           f"{state.state_version}); evaluate again before applying."})
        request = body.request or CapexRequest(price_fen=body.amount_fen)
        if request.price_fen != body.amount_fen:
            raise HTTPException(422, detail={"code": "AMOUNT_MISMATCH",
                                             "message": "amount_fen must equal the evaluated price."})
        try:
            result = evaluate_capex(request, state, mandate, commitments=rt.store.commitments())
        except CapexDisabled as exc:
            raise HTTPException(403, detail={"code": exc.code.value, "message": str(exc)}) from None
        selected = next((x for x in result.structures if x.id == result.selected_id), None)
        if (not result.worth_doing or selected is None or selected.hypothetical or selected.result != "SELECTED"
                or result.selected_facility_id is None or result.selected_facility_id != body.facility_id):
            raise HTTPException(422, detail={
                "code": "NOT_SELECTED",
                "message": f"{body.facility_id} is not the facility of this evaluation's selected structure."})
        key = _application_key(result, rt.day)
        op = ApplyForFacility(
            op_id=f"capex-apply-{key}", idempotency_key=f"capex:{key}", mandate_version=result.mandate_version,
            requested_by=Actor.AGENT, day=rt.day, facility_id=body.facility_id, amount_fen=body.amount_fen,
        )
        applied = rt.executor.execute(op)  # Tier 2: PENDING_APPROVAL; the owner decides on /approvals/{id}
        status = None
        if applied.approval_id:
            rec = rt.store.get_approval(applied.approval_id)
            status = str(getattr(rec.status, "value", rec.status)) if rec is not None else None
    return {"approval_id": applied.approval_id, "approval_status": status, "state_version": state.state_version,
            "application": json.loads(applied.model_dump_json())}
