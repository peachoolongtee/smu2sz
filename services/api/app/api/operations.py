"""Typed operations, the Tier-2 approvals queue and the circuit breaker. The executor decides; this
layer only authenticates the owner and never trusts a body's claim to be the owner."""

from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.api.auth import is_bank_feed, log_refusal, require_owner, require_owner_or_agent
from app.api.runtime import get_runtime
from app.domain.models import Actor, Operation
from app.domain.money import fmt_yuan
from app.operations import security_summary
from app.persistence import ApprovalAlreadyDecided

router = APIRouter()
_OP = TypeAdapter(Operation)


def _result(r) -> dict:
    return json.loads(r.model_dump_json())


@router.post("/operations", dependencies=[Depends(require_owner_or_agent)])
def post_operation(body: dict, x_owner_token: str | None = Header(default=None),
                   x_bank_feed_key: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    if body.get("requested_by") == Actor.OWNER.value and not rt.is_owner(x_owner_token):
        body = {**body, "requested_by": Actor.AGENT.value}  # unauthenticated owner claim -> agent
    if body.get("requested_by") == Actor.SYSTEM.value and not is_bank_feed(x_bank_feed_key):
        body = {**body, "requested_by": Actor.AGENT.value}  # only the bank feed speaks as SYSTEM (F-02)
    body.setdefault("day", rt.day)
    try:
        op = _OP.validate_json(json.dumps(body))
    except ValidationError as e:  # malformed operations never reach the executor
        raise HTTPException(422, f"not a typed operation: {e.__class__.__name__}") from None
    with rt.lock:
        return {"result": _result(rt.executor.execute(op))}


@router.get("/approvals/queue", dependencies=[Depends(require_owner)])
def approvals_queue() -> dict:
    rt = get_runtime()
    out = []
    for a in rt.store.approvals():
        d = asdict(a)
        d["status"] = str(getattr(a.status, "value", a.status))
        try:
            d["operation"] = json.loads(a.op_json)
        except ValueError:
            d["operation"] = None
        op = d["operation"] or {}
        amt = op.get("amount_fen", op.get("advance_fen"))
        d.update({"tier": "TIER_2", "created_day": op.get("day"), "amount_fen": amt,
                  "amount_display": fmt_yuan(amt) if isinstance(amt, int) else None,
                  "subject": f"{(a.kind or '').replace('_', ' ').lower()} {op.get('facility_id', '')}".strip()})
        out.append(d)
    return {"approvals": out}


class Decision(BaseModel):
    decision: str  # APPROVE | REJECT


@router.post("/approvals/{approval_id}", dependencies=[Depends(require_owner_or_agent)])
def decide(approval_id: str, body: Decision, request: Request, x_owner_token: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    actor = Actor.OWNER if rt.is_owner(x_owner_token) else Actor.AGENT
    if rt.store.get_approval(approval_id) is None:
        log_refusal(request, f"decision on unknown approval {approval_id}")
        raise HTTPException(404, {"code": "APPROVAL_NOT_FOUND", "approval_id": approval_id})
    try:
        with rt.lock:
            r = rt.executor.decide(approval_id, body.decision.upper() == "APPROVE", actor)
    except ApprovalAlreadyDecided:
        log_refusal(request, f"decision on already-decided approval {approval_id}")  # F-08
        raise HTTPException(409, {"code": "APPROVAL_ALREADY_DECIDED", "approval_id": approval_id}) from None
    return {"result": _result(r)}


@router.post("/circuit/{counterparty_id}/reset", dependencies=[Depends(require_owner_or_agent)])
def reset_circuit(counterparty_id: str, x_owner_token: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    actor = Actor.OWNER if rt.is_owner(x_owner_token) else Actor.AGENT
    with rt.lock:
        return {"result": _result(rt.executor.reset_circuit(counterparty_id, actor))}


@router.get("/security/summary", dependencies=[Depends(require_owner)])
def get_security_summary() -> dict:
    return security_summary(get_runtime().store)


@router.post("/commitments/{commitment_id}/revoke", dependencies=[Depends(require_owner)])
def revoke_commitment(commitment_id: str) -> dict:
    """The compensating action for a booked concession. Owner only; logged on the chain either way."""
    rt = get_runtime()
    if rt.store.get_commitment(commitment_id) is None:
        raise HTTPException(404, {"code": "COMMITMENT_NOT_FOUND", "commitment_id": commitment_id})
    with rt.lock:
        return {"result": _result(rt.executor.revoke_commitment(commitment_id, Actor.OWNER))}
