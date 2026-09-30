"""Typed operations, the Tier-2 approvals queue and the circuit breaker. The executor decides; this
layer only authenticates the owner and never trusts a body's claim to be the owner."""

from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.api.runtime import get_runtime
from app.domain.models import Actor, Operation
from app.operations import security_summary

router = APIRouter()
_OP = TypeAdapter(Operation)


def _result(r) -> dict:
    return json.loads(r.model_dump_json())


@router.post("/operations")
def post_operation(body: dict, x_owner_token: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    if body.get("requested_by") == Actor.OWNER.value and not rt.is_owner(x_owner_token):
        body = {**body, "requested_by": Actor.AGENT.value}  # unauthenticated owner claim -> agent
    body.setdefault("day", rt.day)
    try:
        op = _OP.validate_json(json.dumps(body))
    except ValidationError as e:  # malformed operations never reach the executor
        raise HTTPException(422, f"not a typed operation: {e.__class__.__name__}") from None
    with rt.lock:
        return {"result": _result(rt.executor.execute(op))}


@router.get("/approvals/queue")
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
        out.append(d)
    return {"approvals": out}


class Decision(BaseModel):
    decision: str  # APPROVE | REJECT


@router.post("/approvals/{approval_id}")
def decide(approval_id: str, body: Decision, x_owner_token: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    actor = Actor.OWNER if rt.is_owner(x_owner_token) else Actor.AGENT
    with rt.lock:
        r = rt.executor.decide(approval_id, body.decision.upper() == "APPROVE", actor)
    return {"result": _result(r)}


@router.post("/circuit/{counterparty_id}/reset")
def reset_circuit(counterparty_id: str, x_owner_token: str | None = Header(default=None)) -> dict:
    rt = get_runtime()
    actor = Actor.OWNER if rt.is_owner(x_owner_token) else Actor.AGENT
    with rt.lock:
        return {"result": _result(rt.executor.reset_circuit(counterparty_id, actor))}


@router.get("/security/summary")
def get_security_summary() -> dict:
    return security_summary(get_runtime().store)
