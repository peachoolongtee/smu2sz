"""Alerts and reconciliation endpoints (flag `alerts`). To be mounted by the main architect.

GET /alerts projects the verified state plus live commitments (and, with `offer_id`, the latest
verdict's bound obligations) in CONSERVATIVE mode. Suggested operations are data only; POST /alerts/{id}/act
submits the cure to the executor as the agent (nothing here executes one itself). GET /reconciliation matches the log's receipts to receivables and commitments.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.alerts import Alert, Severity, alerts, cure_operations, reconcile
from app.api.auth import require_owner
from app.api.display import displayed
from app.api.presentation import business_text
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.domain.models import Obligation, OperationStatus, SecurityEvent, SecurityEventKind
from app.financial import EngineError
from app.funding.recommend import plan_operations, plan_suggestions, recommend_for_alert
from app.verifier import bind

router = APIRouter(dependencies=[Depends(require_owner)])


class ActSuggestion(BaseModel):
    """One suggestion as the web received it: only the fields that decide what runs are read (the web may send the
    whole suggestion object back)."""

    model_config = ConfigDict(extra="ignore")
    operation_kind: str
    facility_id: str | None = None
    receivable_id: str | None = None
    amount_fen: int | None = None


class ActRequest(BaseModel):
    """What the owner was shown when they pressed the button: the state version of the GET /alerts they read and,
    optionally, the alert's suggestions in order (kind, facility, receivable, amount)."""

    model_config = ConfigDict(extra="forbid")
    state_version: int | None = None
    suggestions: list[ActSuggestion] | None = None


def _signature(alert: Alert) -> list[dict[str, Any]]:
    return [{"operation_kind": s.operation_kind, "facility_id": s.facility_id, "receivable_id": s.receivable_id,
             "amount_fen": s.amount_fen} for s in alert.suggested]


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
        "state_version": state.state_version,
        "projected_offer_id": offer_id,
        "counts": _counts(found),
        "alerts": displayed([json.loads(a.model_dump_json()) for a in found]),
        "note": ("A suggested operation is executed only through POST /alerts/{id}/act or POST /operations, "
                 "never by itself."),
    }


def _counts(found: list[Alert]) -> dict[str, int]:
    return {s.value: sum(1 for a in found if a.severity == s) for s in Severity}


@router.post("/alerts/{alert_id}/act")
def act_on_alert(alert_id: str, body: ActRequest | None = None) -> dict[str, Any]:
    """Submit the alert's suggested cure to the executor as the agent. Tier 1 executes; Tier 2 waits in the
    approvals queue. This route never writes state itself.

    The button is bound to what was shown: the body carries `state_version` (from GET /alerts) and optionally the
    `suggestions` the web received. When the state version differs from the current one, or the suggestions (kind,
    facility, receivable, amount, in order) no longer match the recomputed alert, nothing runs and the answer is
    409 ALERT_CHANGED with the current alert (null when it is gone), so the owner sees the new cure before acting.
    The body is optional for one release: when it is absent (or names neither field) the request is unbound, a
    security event "unbound act" is logged and the route still acts on the recomputed alert, as before."""
    rt = get_runtime()
    _require_enabled(rt)
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            found = alerts(state, mandate, rt.store, rt.day)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        alert = next((a for a in found if a.id == alert_id), None)
        shown_version = body.state_version if body is not None else None
        shown_suggestions = ([s.model_dump() for s in body.suggestions]
                             if body is not None and body.suggestions is not None else None)
        plan = None
        if shown_version is None and shown_suggestions is None:
            key = f"unbound-act|{alert_id}|{rt.day}|{len(rt.store.security_events())}"
            rt.store.add_security_event(SecurityEvent(
                id="SEC-ACT-" + hashlib.sha256(key.encode()).hexdigest()[:12], day=rt.day,
                kind=SecurityEventKind.PRIVILEGE_ESCALATION, counterparty_id=None,
                action_taken="acted on the recomputed alert; the request was not bound to what the owner was shown",
                detail=f"unbound act: POST /alerts/{alert_id}/act carried no state_version and no suggestions"))
        else:
            # What was shown is either the alert's own cure or the router's runnable plan the home recommends
            # (app.funding.recommend); both are recomputed now and compared leg by leg (kind, facility, receivable,
            # amount, in order). Anything else means the books moved since the owner read it.
            if shown_suggestions is not None and alert is not None and shown_suggestions != _signature(alert):
                books = current_books(state, rt.store.commitments())
                rec = recommend_for_alert(alert, books.state, books.with_([]), mandate, enabled=rt.settings.features.debt_desk)
                if rec.plan is not None and shown_suggestions == plan_suggestions(rec.plan):
                    plan = rec.plan
            changed = ((shown_version is not None and shown_version != state.state_version)
                       or (shown_suggestions is not None
                           and (alert is None or (shown_suggestions != _signature(alert) and plan is None))))
            if changed:
                raise HTTPException(409, detail={
                    "code": "ALERT_CHANGED", "alert_id": alert_id, "state_version": state.state_version,
                    "message": "The alert changed since you read it; nothing was run. Review the current cure.",
                    "alert": displayed(json.loads(alert.model_dump_json())) if alert is not None else None})
        if alert is None:
            raise HTTPException(404, detail={"code": "ALERT_NOT_FOUND", "alert_id": alert_id})
        # One fix per alert. A repeat of the same fix replays the executor's DUPLICATE (idempotent, as before); the OTHER
        # family (the router plan while the cure waits, or the cure while the plan waits) carries different operation ids,
        # so it is refused here rather than queued beside the first.
        waiting = next((a for a in rt.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"
                        and (a.op_id or "").startswith(f"alert:{alert.id}:")), None)
        if waiting is not None and (":plan:" in (waiting.op_id or "")) != (plan is not None):
            raise HTTPException(409, detail={"code": "ALREADY_QUEUED", "alert_id": alert_id, "approval_id": waiting.id,
                                             "message": "Another fix for this alert is already waiting for your approval; nothing was run."})
        ops = (plan_operations(alert.id, plan, day=rt.day, mandate_version=mandate.version, state_version=state.state_version)
               if plan is not None else
               cure_operations(alert, day=rt.day, mandate_version=mandate.version, state_version=state.state_version))
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

    books_now = rt.store.get_state()
    return {
        "alert_id": alert_id,
        "day": rt.day,
        # `message` is the executor's sentence; `message_when` says it as the Business home does (names, the owner's
        # words for the ceiling, distances from today). A presentation read, English only.
        "results": [{**json.loads(r.model_dump_json()), "message_when": business_text(books_now, r.message, rt.day, "en")}
                    for r in results],
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
