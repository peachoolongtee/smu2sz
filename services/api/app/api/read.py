"""Read views and demo control."""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.api.auth import require_owner
from app.api.decide import _counter_allow
from app.api.display import displayed
from app.api.runtime import get_runtime
from app.api.views import Money, TrajectoryView, trajectory_view
from app.books import current_books
from app.domain.models import Mode
from app.financial import project
from app.mandate import MandatePolicyImpl
from app.operations import security_summary
from app.security.scoreboard import scoreboard
from app.verifier import REFUSAL_REPLY

router = APIRouter(dependencies=[Depends(require_owner)])


def _op_view(o) -> dict:
    res = json.loads(o.result_json)
    try:
        op = json.loads(o.payload_json)
    except ValueError:
        op = {}
    v = displayed(res)
    v.update({"seq": o.seq, "entry_hash": o.entry_hash, "prev_hash": o.prev_hash,
              "day": res.get("effective_day", op.get("day")), "requested_by": op.get("requested_by"),
              "summary": res.get("message") or o.kind.replace("_", " ").lower()})
    return v


@router.get("/state")
def get_state() -> dict:
    rt = get_runtime()
    s = rt.store.get_state()
    return {"state": displayed(json.loads(s.model_dump_json())), "scenario_id": rt.scenario, "day": rt.day,
            "cash": Money.of(s.cash_fen).model_dump()}


@router.get("/mandate")
def get_mandate() -> dict:
    rt = get_runtime()
    m = rt.store.get_mandate()
    policy = MandatePolicyImpl(trusted_public_key_hex=rt.owner_key_hex)
    problems = policy.check_validity(m, rt.day, m.version)
    codes = {v.code.value for v in problems}
    sig = "UNSIGNED" if not m.signature_hex else ("INVALID" if "BAD_SIGNATURE" in codes else "VALID")
    status = "REVOKED" if m.revoked else ("EXPIRED" if "MANDATE_EXPIRED" in codes else "ACTIVE")
    return {
        "mandate": displayed(json.loads(m.model_dump_json())),
        "signature": {"status": sig, "algorithm": "Ed25519",
                      "key_fingerprint": hashlib.sha256(bytes.fromhex(rt.owner_key_hex)).hexdigest()[:16]},
        "validity": {"status": status, "current_day": rt.day, "expires_day": m.expires_day,
                     "days_remaining": max(0, m.expires_day - rt.day)},
        "valid": not problems,
        "problems": [json.loads(v.model_dump_json()) for v in problems],
    }


class TodayTrajectoryView(TrajectoryView):
    today: int  # the first open day of the books (`state.as_of_day`): earlier days are closed


@router.get("/trajectory", response_model=TodayTrajectoryView)
def get_trajectory(mode: str = "CONSERVATIVE") -> TodayTrajectoryView:
    """The projection on current books (ADR-0006): the state plus the live commitments' obligations."""
    rt = get_runtime()
    with rt.lock:
        s, m = rt.store.get_state(), rt.store.get_mandate()
        b = current_books(s, rt.store.commitments())
    t = project(b.state, b.with_([]), [], Mode(mode), m.horizon_days, m.min_cash_fen)
    return TodayTrajectoryView(**trajectory_view(t, m.min_cash_fen).model_dump(), today=s.as_of_day)


@router.get("/ledger")
def get_ledger() -> dict:
    rt = get_runtime()
    ops = rt.store.operations()
    return {
        "commitments": [displayed(json.loads(c.model_dump_json())) for c in rt.store.commitments()],
        "operations": [_op_view(o) for o in ops],
        "chain_valid": rt.store.verify_chain(),
        "chain_length": len(ops),
        "head_hash": ops[-1].entry_hash if ops else None,
    }


@router.get("/audit")
def get_audit() -> dict:
    rt = get_runtime()
    ops = rt.store.operations()
    refusals = [_op_view(o) for o in ops if json.loads(o.result_json).get("status") == "REFUSED"]
    s = security_summary(rt.store)
    events = rt.store.security_events()
    doc_ids = {sp.doc_id for e in events for sp in e.spans}
    extraction = any(e.kind.value == "DATA_EXTRACTION" for e in events)
    board = scoreboard(rt.store, allow_for=_counter_allow)  # computed from every stored verdict, not asserted
    return {
        "events": [displayed(json.loads(e.model_dump_json())) for e in events],
        "refusals": refusals,
        "documents": [json.loads(d.model_dump_json()) for i, d in rt.documents.items() if i in doc_ids],
        "summary": displayed({
            "facilities_added": s.get("facilities_added_by_non_owner", 0),
            "commitments_booked": len(rt.store.commitments()),
            **board,
            "reply_text": REFUSAL_REPLY if extraction else None,
            **{k: v for k, v in s.items() if isinstance(v, (int, str, bool))},
        }),
    }


@router.get("/evidence", response_class=PlainTextResponse)
def get_evidence() -> str:
    from app.api.evidence import build

    rt = get_runtime()
    rt.store.export_evidence()  # records the export (count, head hash) in evidence_exports
    return build(rt)


@router.post("/demo/reset")
def demo_reset(scenario: str = "golden_sme") -> dict:
    rt = get_runtime()
    rt.reset(scenario)
    return {"ok": True, "scenario": scenario, "day": rt.day}
