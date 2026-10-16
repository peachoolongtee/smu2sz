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
from app.capex.buyside import BuySideEvaluation, CapexEstimate, NotACapexContract, evaluate_contract
from app.capex.schedule import Timeline, derive_schedule, early_schedule
from app.config import get_settings
from app.domain.models import Actor, ApplyForFacility, CommitPurchase, DocumentKind, DocumentStatus
from app.domain.money import Ratio, fmt_pct

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


# ---------------------------------------------------------------- ADR-0013: the buy side of one capex contract


class ContractEvaluateIn(BaseModel):
    """The owner's timeline (the days the contract cannot fix) and estimate (what the equipment earns)."""

    model_config = ConfigDict(extra="forbid")

    timeline: Timeline = Field(default_factory=Timeline)
    estimate: CapexEstimate = Field(default_factory=CapexEstimate)


def _require_buy_side() -> None:
    features = get_settings().features
    if not features.capex or not features.capex_contracts:
        raise HTTPException(403, {"code": "FEATURE_DISABLED", "feature": "capex_contracts",
                                  "message": "Capex contracts are switched off (FEATURE_CAPEX / FEATURE_CAPEX_CONTRACTS)."})


def _rate_text(r: Ratio | None) -> str | None:
    return fmt_pct(r.value) if r is not None else None


def buyside_view(ev: BuySideEvaluation) -> dict:
    """The evaluation with every money field displayed; rates (exact ratios) are said as percentages."""
    view = _with_null_displays(displayed(json.loads(ev.model_dump_json())))
    sched = view["schedule"].get("schedule")
    if sched and sched.get("early_pay") and ev.schedule.schedule and ev.schedule.schedule.early_pay:
        sched["early_pay"]["implied_annual_rate_display"] = _rate_text(ev.schedule.schedule.early_pay.implied_annual_rate)
    if view.get("early_pay") and ev.early_pay is not None:
        e = ev.early_pay
        view["early_pay"].update({"return_share_display": _rate_text(e.return_share),
                                  "cost_share_display": _rate_text(e.cost_share),
                                  "marginal_rate_display": _rate_text(e.marginal_rate)})
    return view


@router.post("/capex/contracts/{document_id}/evaluate")
def post_capex_contract_evaluate(document_id: str, body: ContractEvaluateIn | None = None) -> dict:
    """Read-only: the contract's payment schedule on the owner's timeline, the capex screen on it, and the vendor's
    early-payment discount. Nothing is written. An unconfirmed reading may be screened (`reading_confirmed` says so);
    only a confirmed one can be committed."""
    _require_buy_side()
    body = body or ContractEvaluateIn()
    rt = get_runtime()
    with rt.lock:
        record = rt.store.get_contract_record(document_id)
        if record is None:
            raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": f"no document {document_id}"})
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            ev = evaluate_contract(record, body.timeline, body.estimate, state, mandate,
                                   commitments=rt.store.commitments())
        except NotACapexContract as exc:
            raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from None
        except CapexDisabled as exc:
            raise HTTPException(403, detail={"code": exc.code.value, "message": str(exc)}) from None
    return buyside_view(ev)


class ContractCommitIn(BaseModel):
    """What the owner commits to: the timeline the schedule was shown on, whether the early-payment discount is taken,
    and the hash of the schedule shown (from the evaluation: `schedule.schedule.schedule_hash`, or
    `early_pay_schedule.schedule_hash` when the discount is taken)."""

    model_config = ConfigDict(extra="forbid")

    timeline: Timeline
    take_early_pay: bool = False
    schedule_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/capex/contracts/{document_id}/commit")
def post_capex_contract_commit(document_id: str, body: ContractCommitIn) -> dict:
    """Queue the owner's commitment to a confirmed capex contract's payment schedule (ADR-0013): one CommitPurchase,
    requested by the owner (this route is owner-only; the executor refuses any other requester, CAPEX-2), always Tier 2;
    nothing is booked until the owner approves it on /approvals/{id}. The schedule
    is checked here first, so a stale one is answered at once (409) instead of queued; the executor checks it again on
    approval."""
    _require_buy_side()
    rt = get_runtime()
    with rt.lock:
        record = rt.store.get_contract_record(document_id)
        if record is None:
            raise HTTPException(404, {"code": "UNKNOWN_DOCUMENT", "message": f"no document {document_id}"})
        if record.kind != DocumentKind.CAPEX_CONTRACT or record.contract is None:
            raise HTTPException(422, {"code": "NOT_A_CAPEX_CONTRACT",
                                      "message": f"{document_id} is not a capex contract"})
        if record.status != DocumentStatus.CONFIRMED:
            raise HTTPException(422, {"code": "NOT_CONFIRMED",
                                      "message": "confirm the agent's reading of the contract before committing to it"})
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        derived = derive_schedule(record.contract, body.timeline, anchor_iso=state.as_of, today=state.as_of_day)
        if not derived.derivable or derived.schedule is None:
            raise HTTPException(422, {"code": "NO_SCHEDULE", "message": " ".join(derived.reasons),
                                      "message_zh": " ".join(derived.reasons_zh) or None, "needs": derived.needs})
        schedule = early_schedule(derived.schedule) if body.take_early_pay else derived.schedule
        if schedule is None:
            raise HTTPException(422, {"code": "NO_EARLY_PAYMENT",
                                      "message": "the contract offers no early-payment discount the schedule could take"})
        if schedule.schedule_hash != body.schedule_hash:
            raise HTTPException(409, {"code": "SCHEDULE_CHANGED", "schedule_hash": schedule.schedule_hash,
                                      "message": "the payment schedule is not the one shown; evaluate again and commit "
                                                 "what is shown"})
        key = f"capex-commit:{record.id}:{schedule.schedule_hash[:16]}"
        t = body.timeline
        op = CommitPurchase(
            op_id=f"capex-commit-{record.id}-{schedule.schedule_hash[:12]}", idempotency_key=key,
            mandate_version=mandate.version, requested_by=Actor.OWNER, day=rt.day, document_id=record.id,
            doc_hash=record.doc_hash, schedule_hash=schedule.schedule_hash, amount_fen=schedule.price_fen,
            signing_day=t.signing_day, delivery_day=t.delivery_day, acceptance_day=t.acceptance_day,
            invoice_day=t.invoice_day, retention_release_day=t.retention_release_day,
            take_early_pay=body.take_early_pay)
        result = rt.executor.execute(op)  # Tier 2: PENDING_APPROVAL; the owner decides on /approvals/{id}
    return {"approval_id": result.approval_id, "status": result.status.value,
            "result": json.loads(result.model_dump_json()),
            "schedule": _with_null_displays(displayed(json.loads(schedule.model_dump_json())))}
