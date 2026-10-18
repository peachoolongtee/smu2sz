"""The owner's stop switch: pause and resume everything FLOW executes on the agent's or a buyer's authority (R-14, "a write switch").

    GET  /agent/pause    owner: whether the agent is paused, since which day and log entry
    POST /agent/pause    owner: pause; one PAUSE_AGENT entry on the hash-chained log (a second pause while paused writes nothing)
    POST /agent/resume   owner: resume; one RESUME_AGENT entry (a resume while running writes nothing)

While paused, every typed operation whose `requested_by` is AGENT or COUNTERPARTY is refused before it reaches the executor's gates:
nothing is executed, queued for approval or written to the books, and the refusal is recorded as a security event (kind REVOKED). That
covers the agent's tool channel (POST /operations), the agent's and a keyed buyer's chat (POST /nl), and the owner-side flows that FLOW
carries out under the agent's authority (acting on an alert, a chat funding plan, a capex draw). What still runs: operations the owner
requests as OWNER (accept, decline, receipts, repayments, revoking an agreement, deciding an approval already queued), and receipts from
the bank feed (SYSTEM), which record money that already moved.

The switch lives on the operations log, not in process memory: the state is the latest PAUSE_AGENT or RESUME_AGENT entry, so it
survives a restart, every process reading the same store sees it, and the pause and the resume are themselves on the chain the evidence
export verifies. A demo reset (`POST /demo/reset`, demo mode only) empties the log and so clears a pause.

It is enforced in `PausableExecutor.execute`, the one entry every typed operation takes (`Runtime.executor`), so a new route cannot miss
it. It does not change the mandate, the engine or the executor (app/operations is read-only for this change): it is a narrower,
reversible control than a mandate revocation, which also stops the owner's own operations and needs a newly signed mandate to undo.
Not covered: `Executor.propose_commitment` (a PROPOSED agreement moves no money; the acceptance that would bind it is refused while
paused)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.api.auth import require_owner
from app.api.runtime import get_runtime
from app.domain.models import (
    Actor,
    OperationResult,
    OperationStatus,
    SecurityEvent,
    SecurityEventKind,
    Tier,
    Violation,
    ViolationCode,
)
from app.domain.ports import LedgerStore
from app.operations import Executor
from app.persistence import canonical_json

log = logging.getLogger("termsledger.decisions")
router = APIRouter(dependencies=[Depends(require_owner)])

PAUSE_KIND = "PAUSE_AGENT"
RESUME_KIND = "RESUME_AGENT"
PAUSED_ACTORS = frozenset({Actor.AGENT.value, Actor.COUNTERPARTY.value})
PAUSED_MESSAGE = ("Refused: the owner has paused FLOW's agent; nothing done on the agent's or a buyer's authority runs until the owner "
                  "resumes it")


def pause_state(store: LedgerStore) -> dict[str, Any] | None:
    """The latest pause entry when the agent is paused ({"seq", "day", "entry_hash"}), else None. Newest entry first, so a long log is
    read only back to the last switch."""
    for r in reversed(store.operations()):
        if r.kind == RESUME_KIND:
            return None
        if r.kind == PAUSE_KIND:
            return {"seq": r.seq, "day": _day(r.result_json), "entry_hash": r.entry_hash}
    return None


def _day(result_json: str) -> int | None:
    try:
        return OperationResult.model_validate_json(result_json).effective_day
    except ValueError:
        return None


class PausableExecutor(Executor):
    """The executor, with the owner's pause in front of `execute`. Everything else is the executor's own."""

    def execute(self, op: Any) -> OperationResult:
        actor = str(getattr(getattr(op, "requested_by", None), "value", getattr(op, "requested_by", "")))
        kind = str(getattr(getattr(op, "kind", None), "value", getattr(op, "kind", "")))
        # PAUSE-1: the bank feed is exempt for what it exists to do, report a receipt; anything else it asks for is paused too
        if actor in PAUSED_ACTORS or (actor == Actor.SYSTEM.value and kind != "RECEIVE_PAYMENT"):
            paused = pause_state(self._store)
            if paused is not None:
                return self._refuse_paused(op, actor, paused)
        return super().execute(op)

    def _refuse_paused(self, op: Any, actor: str, paused: dict[str, Any]) -> OperationResult:
        now = self._clock()
        kind = str(getattr(op, "kind", type(op).__name__))
        op_id = str(getattr(op, "op_id", "?"))
        v = Violation(code=ViolationCode.INSUFFICIENT_AUTHORITY, message=PAUSED_MESSAGE, day=now, observed=f"paused at seq {paused['seq']}",
                      limit="not paused", formula="no PAUSE_AGENT entry after the latest RESUME_AGENT",
                      inputs={"requested_by": actor, "pause_seq": str(paused["seq"])})
        try:
            self._store.add_security_event(SecurityEvent(
                id="SEC-PAUSE-" + uuid.uuid4().hex[:16], day=now, kind=SecurityEventKind.REVOKED,
                counterparty_id=getattr(op, "counterparty_id", None) if actor == Actor.COUNTERPARTY.value else None,
                action_taken="refused before the executor; nothing executed, queued or booked",
                detail=f"{actor} {kind} {op_id} refused: the owner paused the agent (log seq {paused['seq']})"))
        except Exception:  # the refusal stands whether or not its event could be written
            log.exception("the pause refusal of %s could not be recorded as a security event", op_id)
        return OperationResult(op_id=op_id, kind=kind, status=OperationStatus.REFUSED, tier=Tier.TIER_2, violations=[v],
                               effective_day=now, message=PAUSED_MESSAGE)


def _view(store: LedgerStore) -> dict[str, Any]:
    p = pause_state(store)
    return {"paused": p is not None, "since_day": p["day"] if p else None, "pause_seq": p["seq"] if p else None,
            "refuses": sorted(PAUSED_ACTORS) if p else []}


def _switch(kind: str) -> dict[str, Any]:
    rt = get_runtime()
    with rt.lock:
        paused = pause_state(rt.store) is not None
        if paused == (kind == PAUSE_KIND):  # already where the owner asked: nothing to write
            return {**_view(rt.store), "changed": False}
        op_id = f"{kind.lower().replace('_', '-')}-{rt.day}-{uuid.uuid4().hex[:8]}"
        payload = {"kind": kind, "op_id": op_id, "requested_by": Actor.OWNER.value, "day": rt.day}
        words = ("Agent paused by the owner: nothing runs on the agent's or a buyer's authority until it is resumed"
                 if kind == PAUSE_KIND else "Agent resumed by the owner")
        result = OperationResult(op_id=op_id, kind=kind, status=OperationStatus.EXECUTED, tier=Tier.TIER_2, effective_day=rt.day,
                                 message=words)
        rt.store.append_operation(op_id, kind, op_id, canonical_json(payload), canonical_json(result))
        return {**_view(rt.store), "changed": True}


@router.get("/agent/pause")
def get_pause() -> dict[str, Any]:
    return _view(get_runtime().store)


@router.post("/agent/pause")
def post_pause() -> dict[str, Any]:
    return _switch(PAUSE_KIND)


@router.post("/agent/resume")
def post_resume() -> dict[str, Any]:
    return _switch(RESUME_KIND)
