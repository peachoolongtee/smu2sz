"""Read views and demo control."""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.api.runtime import get_runtime
from app.api.views import Money, TrajectoryView, trajectory_view
from app.domain.models import Mode
from app.financial import project
from app.mandate import MandatePolicyImpl

router = APIRouter()


@router.get("/state")
def get_state() -> dict:
    rt = get_runtime()
    s = rt.store.get_state()
    return {
        "day": rt.day,
        "state": json.loads(s.model_dump_json()),
        "cash": Money.of(s.cash_fen).model_dump(),
        "facilities": [
            {"id": f.id, "name": f.name, "kind": f.kind.value, "status": f.status.value,
             "limit": Money.of(f.limit_fen).model_dump(), "drawn": Money.of(f.drawn_fen).model_dump()}
            for f in s.facilities
        ],
    }


@router.get("/mandate")
def get_mandate() -> dict:
    rt = get_runtime()
    m = rt.store.get_mandate()
    problems = MandatePolicyImpl(trusted_public_key_hex=rt.owner_key_hex).check_validity(m, rt.day, m.version)
    return {
        "mandate": json.loads(m.model_dump_json()),
        "valid": not problems,
        "problems": [json.loads(v.model_dump_json()) for v in problems],
        "display": {
            "min_cash": Money.of(m.min_cash_fen).text,
            "max_aggregate_forward_concession": Money.of(m.max_aggregate_forward_concession_fen).text,
            "tier2_single_commitment": Money.of(m.tier2_single_commitment_fen).text,
            "min_dscr": f"{m.min_dscr_bp / 10000:.2f}x",
            "max_leverage": f"{m.max_leverage_bp / 10000:.2f}x",
            "max_apr": f"{m.max_apr_bp / 100:.2f}%",
        },
    }


@router.get("/trajectory", response_model=TrajectoryView)
def get_trajectory(mode: str = "CONSERVATIVE") -> TrajectoryView:
    rt = get_runtime()
    s, m = rt.store.get_state(), rt.store.get_mandate()
    t = project(s, [], [], Mode(mode), m.horizon_days, m.min_cash_fen)
    return trajectory_view(t, m.min_cash_fen)


@router.get("/ledger")
def get_ledger() -> dict:
    rt = get_runtime()
    ops = rt.store.operations()
    return {
        "chain_valid": rt.store.verify_chain(),
        "operations": [
            {"seq": o.seq, "op_id": o.op_id, "kind": o.kind, "idempotency_key": o.idempotency_key,
             "result": json.loads(o.result_json), "prev_hash": o.prev_hash, "entry_hash": o.entry_hash}
            for o in ops
        ],
        "commitments": [json.loads(c.model_dump_json()) for c in rt.store.commitments()],
    }


@router.get("/audit")
def get_audit() -> dict:
    rt = get_runtime()
    return {"security_events": [json.loads(e.model_dump_json()) for e in rt.store.security_events()]}


@router.get("/approvals")
def get_approvals() -> dict:
    rt = get_runtime()
    return {"approvals": [a.__dict__ if hasattr(a, "__dict__") else a for a in rt.store.approvals()]}


@router.get("/evidence", response_class=PlainTextResponse)
def get_evidence() -> str:
    return get_runtime().store.export_evidence()


@router.post("/demo/reset")
def demo_reset(scenario: str = "golden_sme") -> dict:
    rt = get_runtime()
    rt.reset(scenario)
    return {"ok": True, "scenario": scenario, "day": rt.day}
