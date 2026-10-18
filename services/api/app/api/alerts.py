"""Alerts and reconciliation endpoints (flag `alerts`). To be mounted by the main architect.

GET /alerts projects the verified state plus live commitments (and, with `offer_id`, the latest
verdict's bound obligations) in CONSERVATIVE mode. Suggested operations are data only; POST /alerts/{id}/act
submits the cure to the executor as the agent (nothing here executes one itself). GET /reconciliation matches the log's receipts to receivables and commitments.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.alerts import Alert, Severity, alerts, cure_operations, reconcile
from app.api.auth import require_owner
from app.api.decisions import record_fact
from app.api.display import displayed
from app.api.funding_report import act_summary, leg_views
from app.api.presentation import (
    business_text,
    executed_words,
    last_read,
    live_windows,
    party_name,
    reconciliation_words,
    t,
    window_is_live,
)
from app.api.quotes import build_quote
from app.api.receipt_facts import receipt_facts
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.decisions.identity import alert_cure_id, alert_plan_id
from app.domain.models import (
    FinancialState,
    Obligation,
    OperationResult,
    OperationStatus,
    SecurityEvent,
    SecurityEventKind,
)
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


def _language(lang: str) -> str:
    return "zh" if lang == "zh" else "en"


def _require_enabled(rt: Runtime, lang: str = "en") -> None:
    if not rt.settings.features.alerts:
        raise HTTPException(403, detail={
            "code": "FEATURE_DISABLED", "feature": "alerts", "message": "Alerts and reconciliation are switched off (FEATURE_ALERTS).",
            "message_when": t(lang, "Alerts and reconciliation are switched off.", "提醒与对账功能已关闭。")})


def _alert_view(state: FinancialState, alert: Alert, today: int, lang: str, agreements: dict[str, str]) -> dict[str, Any]:
    """One alert as the page reads it: the engine's `title`, `detail`, `formula` and each suggestion's `note` stay as written (the audit
    level), and `title_when`, `detail_when` and `note_when` say them as a Business page does, in the page's language."""
    view = displayed(json.loads(alert.model_dump_json()))
    view["title_when"] = business_text(state, alert.title, today, lang, agreements)
    view["detail_when"] = business_text(state, alert.detail, today, lang, agreements)
    for row, suggestion in zip(view.get("suggested") or [], alert.suggested, strict=False):
        row["note_when"] = business_text(state, suggestion.note, today, lang, agreements) if suggestion.note else None
    return view


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
def get_alerts(offer_id: str | None = None, lang: str = "en") -> dict[str, Any]:
    """The alerts on today's books. `lang` (en | zh, additive) is the language of every sentence the server writes for the page
    (`title_when`, `detail_when`, each suggestion's `note_when`, `note_when`); the engine's own `title`, `detail` and `formula` stay as written."""
    rt = get_runtime()
    lang = _language(lang)
    _require_enabled(rt, lang)
    with rt.lock:
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        try:
            found = alerts(state, mandate, rt.store, rt.day, obligations=_offer_obligations(rt, offer_id))
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None
        today = max(rt.day, state.as_of_day)
        agreements = {c.id: party_name(state, c.counterparty_id) for c in rt.store.commitments()}
        views = [_alert_view(state, a, today, lang, agreements) for a in found]
    return {
        "day": rt.day,
        "lang": lang,
        "basis": "CONSERVATIVE",
        "state_version": state.state_version,
        "projected_offer_id": offer_id,
        "counts": _counts(found),
        "alerts": views,
        "note": ("A suggested operation is executed only through POST /alerts/{id}/act or POST /operations, "
                 "never by itself."),
        "note_when": t(lang, "A suggested step runs only when you choose it. Nothing runs by itself.",
                       "建议的步骤只有在您选择后才会执行，不会自动执行。"),
        **last_read(today, lang),
    }


def _counts(found: list[Alert]) -> dict[str, int]:
    return {s.value: sum(1 for a in found if a.severity == s) for s in Severity}


@router.post("/alerts/{alert_id}/act")
def act_on_alert(alert_id: str, body: ActRequest | None = None, lang: str = "en") -> dict[str, Any]:
    """Submit the alert's suggested cure to the executor as the agent. Tier 1 executes; Tier 2 waits in the
    approvals queue. This route never writes state itself.

    The button is bound to what was shown: the body carries `state_version` (from GET /alerts) and optionally the
    `suggestions` the web received. When the state version differs from the current one, or the suggestions (kind,
    facility, receivable, amount, in order) no longer match the recomputed alert, nothing runs and the answer is
    409 ALERT_CHANGED with the current alert (null when it is gone), so the owner sees the new cure before acting.
    The body is optional for one release: when it is absent (or names neither field) the request is unbound, a
    security event "unbound act" is logged and the route still acts on the recomputed alert, as before.

    `lang` (en | zh, additive) is the language of the words the server writes for the answer (`message_when`, `event_text`,
    `event_detail`, and `message_when` of a refusal)."""
    rt = get_runtime()
    lang = _language(lang)
    _require_enabled(rt, lang)
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
            key = f"unbound-act|{alert_id}|{rt.day}|{uuid.uuid4().hex}"
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
                agreements_now = {c.id: party_name(state, c.counterparty_id) for c in rt.store.commitments()}
                raise HTTPException(409, detail={
                    "code": "ALERT_CHANGED", "alert_id": alert_id, "state_version": state.state_version,
                    "message": "The alert changed since you read it; nothing was run. Review the current cure.",
                    "message_when": t(lang, "The alert changed since you read it; nothing was run. Review the current plan.",
                                      "该提醒在您阅读之后已发生变化，未执行任何操作。请查看最新的方案。"),
                    "alert": (_alert_view(state, alert, max(rt.day, state.as_of_day), lang, agreements_now)
                              if alert is not None else None)})
        if alert is None:
            raise HTTPException(404, detail={"code": "ALERT_NOT_FOUND", "alert_id": alert_id})
        # One fix per alert. A repeat of the same fix replays the executor's DUPLICATE (idempotent, as before); the OTHER
        # family (the router plan while the cure waits, or the cure while the plan waits) carries different operation ids,
        # so it is refused here rather than queued beside the first.
        waiting = next((a for a in rt.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"
                        and (a.op_id or "").startswith(f"alert:{alert.id}:")), None)
        if waiting is not None and (":plan:" in (waiting.op_id or "")) != (plan is not None):
            raise HTTPException(409, detail={
                "code": "ALREADY_QUEUED", "alert_id": alert_id, "approval_id": waiting.id,
                "message": "Another fix for this alert is already waiting for your approval; nothing was run.",
                "message_when": t(lang, "Another fix for this alert is already waiting for your approval; nothing was run.",
                                  "该提醒的另一个处理方案已在等待您批准，未执行任何操作。")})
        ops = (plan_operations(alert.id, plan, day=rt.day, mandate_version=mandate.version, state_version=state.state_version)
               if plan is not None else
               cure_operations(alert, day=rt.day, mandate_version=mandate.version, state_version=state.state_version))
        if not ops:
            raise HTTPException(409, detail={
                "code": "NO_EXECUTABLE_CURE", "alert_id": alert_id, "message": "This alert suggests nothing the agent may execute.",
                "message_when": t(lang, "This alert suggests nothing that can be run for you.", "该提醒没有可替您执行的建议。")})
        # The quote is what the owner was shown: built now, from the alert and plan just recomputed and bound to the shown
        # suggestions, before anything runs (ADR-0011 section 4). Whether it can be stored is settled after the executor.
        did = alert_plan_id(alert.id, state.state_version) if plan is not None else alert_cure_id(alert.id, state.state_version)
        quote = None
        try:
            books_q = current_books(state, rt.store.commitments())
            quote = build_quote(books_q.state, books_q.with_([]), mandate, alert, plan, ops, max(rt.day, state.as_of_day))
        except Exception:
            logging.getLogger("termsledger.decisions").exception("the quote for %s could not be built", did)
        results = []
        for op in ops:
            r = rt.executor.execute(op)
            results.append(r)
            if r.status not in (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL):
                break
        recorded = (quote is not None and record_fact(rt, did, did, quote, state_version=state.state_version, day=rt.day))
        try:
            after = alerts(rt.store.get_state(), rt.store.get_mandate(), rt.store, rt.day)
        except EngineError as exc:
            raise HTTPException(422, f"cannot project: {exc}") from None

    def n(status: OperationStatus) -> int:
        return sum(1 for r in results if r.status == status)

    books_now = rt.store.get_state()
    agreements = {c.id: party_name(books_now, c.counterparty_id) for c in rt.store.commitments()}
    legs = leg_views(books_now, [json.loads(op.model_dump_json()) for op in ops], [json.loads(r.model_dump_json()) for r in results],
                     rt.day, lang)
    run_status, run_message = act_summary(lang, legs, len(results), len(ops))
    return {
        "alert_id": alert_id,
        "decision_id": did,
        "decision_recorded": recorded,
        "day": rt.day,
        "lang": lang,
        # `message` is the executor's sentence; `message_when` says it as the Business home does (names, the owner's
        # words for the ceiling, distances from today) in the page's language. A presentation read.
        # `event_text` / `event_detail`: the business sentence for what the operation did (`event_words`).
        "results": [_result_view(books_now, op, r, rt.day, lang, agreements) for op, r in zip(ops, results, strict=False)],
        # What became of the steps after they all ran (SEC-28): the outcome and each step's own sentence, so a queued or refused step is
        # never read as "done". Reporting only: the steps run as before.
        "run_status": run_status,
        "message_when": run_message,
        "executed": n(OperationStatus.EXECUTED),
        "pending_approval": n(OperationStatus.PENDING_APPROVAL),
        "refused": n(OperationStatus.REFUSED),
        "cured": all(a.id != alert_id for a in after),
        "alerts_after": {"counts": _counts(after)},
    }


def _result_view(state: FinancialState, op: Any, r: OperationResult, today: int, lang: str,
                 agreements: dict[str, str]) -> dict[str, Any]:
    """One result of an act: the executor's result as it is, with the Business words for it (`executed_words`)."""
    raw = json.loads(r.model_dump_json())
    return {**raw, **executed_words(state, payload=json.loads(op.model_dump_json()), result=raw, today=today, lang=lang,
                                    agreements=agreements)}


@router.get("/reconciliation")
def get_reconciliation(lang: str = "en") -> dict[str, Any]:
    """The receipts matched to what was promised. `lang` (en | zh, additive) is the language of `detail_when` and the receipt facts' words;
    the engine's `detail` and `formula` stay as written."""
    rt = get_runtime()
    lang = _language(lang)
    _require_enabled(rt, lang)
    with rt.lock:
        report = reconcile(rt.store, day=rt.day)
        state = rt.store.get_state()
        live = live_windows(report, rt.store.commitments(), state)
        facts = receipt_facts(state, report, live, rt.day)
    out = displayed(json.loads(report.model_dump_json()))
    # `detail_when`: each promise's and receipt's sentence as a Business page reads it (names for ids, no commitment id,
    # distances from today). `detail` stays the engine's sentence for the audit level.
    agreements = {c.id: party_name(state, c.counterparty_id) for c in rt.store.commitments()}
    for key in ("promised", "receipts"):
        for row in out.get(key, []):
            row["detail_when"] = (reconciliation_words(state, row.get("detail"), rt.day, promise=key == "promised", lang=lang, agreements=agreements,
                                                       window_live=window_is_live(live, row.get("receivable_id"), row.get("commitment_id")))
                                  if row.get("detail") else None)
    for row in out.get("receipts", []):
        row.update(facts.get(row["seq"], {}))  # the four named facts and the window (F25) on the receipts that paid an agreed early payment
        if "window_state" in row:
            row["window_state_text"] = (t(lang, "The early-payment window is still open", "提前付款期限仍未结束") if row["window_state"] == "open"
                                        else t(lang, "The early-payment window has ended", "提前付款期限已结束"))
    return {"reconciliation": out, "lang": lang, **last_read(rt.day, lang)}
