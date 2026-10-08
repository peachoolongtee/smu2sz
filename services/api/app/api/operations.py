"""Typed operations, the Tier-2 approvals queue and the circuit breaker. The executor decides; this
layer only authenticates the owner and never trusts a body's claim to be the owner."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.alerts import alerts
from app.api.auth import is_bank_feed, log_refusal, require_owner, require_owner_or_agent
from app.api.decisions import approval_decision, execution_view, load_context, quote_for
from app.api.home import cure_after
from app.api.presentation import (
    COMMERCIAL_KINDS,
    agreement_terms,
    approval_reason_words,
    approval_words,
    business_text,
    find_agreement,
    party_name,
    quote_not_recorded,
    relative_days,
    result_words,
    t,
    when_text,
)
from app.api.runtime import get_runtime
from app.books import current_books
from app.domain.models import Actor, Operation, OperationStatus
from app.domain.money import fmt_yuan
from app.financial import EngineError
from app.funding.recommend import cost_lines_by_leg, runnable_plan
from app.operations import security_summary
from app.operations.log import read_entries
from app.persistence import ApprovalAlreadyDecided

log = logging.getLogger("termsledger.decisions")
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


def _decision_runs(records) -> dict:
    """Per approval id, the log entry of the owner's decision run: the first non-PENDING row that ran under it
    (an owner-approved re-run or a decline). A non-owner's refused attempt (key `#decide:`) is not the decision."""
    entries, _ = read_entries(records)
    out: dict = {}
    for e in entries:
        aid = e.result.approval_id
        if aid and aid not in out and e.result.status != OperationStatus.PENDING_APPROVAL and "#decide:" not in e.idempotency_key:
            out[aid] = e
    return out


def _execution_status(approval_status: str, run_status: str | None) -> str:
    """What came of an approval, as one word the card can switch on: PENDING (waiting, or nothing ran yet), EXECUTED, REFUSED (the
    owner approved but the run was refused), DUPLICATE, or DECLINED (the owner said no)."""
    if approval_status == "REJECTED":
        return "DECLINED"
    return run_status if run_status in ("EXECUTED", "REFUSED", "DUPLICATE") else "PENDING"


def _quoted_cost(view: dict, op_id: str) -> dict | None:
    return next((x for x in view.get("lines", []) if x["op_id"] == op_id), None)


def _decision_fields(ctx, rt, a, op: dict, status: str, pres: dict, run, lang: str = "en") -> dict:
    """The decision record's part of a queue row: its id and state, the stored quote (a decided row never shows a price taken from
    today's alerts), what ran, and the summary. An approval with no stored quote says so."""
    did = approval_decision(a, ctx.commitments)
    found = ctx.states().get(did) if did else None
    out: dict = {"decision_id": did, "decision_state": None, "quote": None, "execution": None}
    pending = status == "PENDING"
    ds = found[0] if found else None
    if ds is not None:
        out["decision_state"] = ds.state.value
    if a.kind not in COMMERCIAL_KINDS:
        if ds is not None and ds.quote is not None:
            view = quote_for(ctx, ds, lang, decided=not pending)
            line = _quoted_cost(view, str(op.get("op_id") or ""))
            if pending:
                shown = pres.get("cost_display")
                if line is not None and shown and line["cost_display"] and shown != line["cost_display"]:
                    view["text"] = t(lang, f"Quoted when requested: {line['cost_display']}; today's price is {shown}.",
                                     f"提交时的报价：{line['cost_display']}；今日价格为 {shown}。")
            else:  # the price the owner approved is the one they were quoted
                if line is not None:
                    pres["cost_display"], pres["rate_text"], pres["cost_due_day"] = line["cost_display"], line["rate_text"], None
                    pres["cost_due_day"] = next((q.cost_end_day for q in ds.quote.legs if q.op_id == line["op_id"]), None)
                pres["protects"] = view["after"]
                pres["residual"] = ({"shortfall_display": fmt_yuan(ds.quote.residual_shortfall_fen),
                                     "from_when": when_text(ds.quote.after_first_short_day, ctx.today, lang),
                                     "restores_reserve": False}
                                    if ds.quote.restores_reserve is False and ds.quote.residual_shortfall_fen is not None
                                    and ds.quote.after_first_short_day is not None else None)
            out["quote"] = view
        else:
            out["quote"] = quote_not_recorded(not pending, lang)
    exec_status = pres.get("execution_status")
    summary: str | None
    if pending:
        summary = t(lang, "Waiting for your approval. Nothing has run.", "等待您批准，尚未执行。")
    else:
        summary = pres.get("result_message") or (execution_view(ctx, ds, lang)["summary_text"] if ds is not None else None)
    out["execution"] = {"status": exec_status, "summary_text": summary}
    return out


@router.get("/approvals/queue", dependencies=[Depends(require_owner)])
def approvals_queue(lang: str = "en") -> dict:
    """The Tier-2 queue, read once under one lock so every row is from the same books. `lang` (en | zh, additive) is the language of
    every sentence the server writes for the cards."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        return _approvals_queue(rt, lang)


def _approvals_queue(rt, lang: str) -> dict:
    out = []
    ran = _decision_runs(rt.store.operations())
    state = rt.store.get_state()
    commitments = rt.store.commitments()
    agreements = {c.id: party_name(state, c.counterparty_id) for c in commitments}
    # The alerts whose cures are queued carry the engine's price for them; read once, only when something is pending. A decided
    # row is never priced from them: its quote is the fact stored when it was requested.
    open_alerts: dict = {}
    plan_costs: dict = {}
    obs: list = []
    ctx = None
    with rt.lock:
        if any(str(getattr(a.status, "value", a.status)) == "PENDING" for a in rt.store.approvals()):
            try:
                open_alerts = {al.id: al for al in alerts(state, rt.store.get_mandate(), rt.store, rt.day)}
                obs = current_books(state, rt.store.commitments()).with_([])
                if rt.settings.features.debt_desk:  # a queued leg of the recommended router plan carries its cost line
                    books = current_books(state, rt.store.commitments())
                    plan = runnable_plan(books.state, books.with_([]), rt.store.get_mandate())
                    plan_costs = cost_lines_by_leg(plan) if plan is not None else {}
            except EngineError:
                open_alerts = {}
        try:
            ctx = load_context(rt)
        except Exception:
            log.exception("the decision record could not be read for the approvals queue")
    for a in rt.store.approvals():
        d = asdict(a)
        d["status"] = str(getattr(a.status, "value", a.status))
        pending = d["status"] == "PENDING"
        try:
            d["operation"] = json.loads(a.op_json)
        except ValueError:
            d["operation"] = None
        op = d["operation"] or {}
        amt = op.get("amount_fen", op.get("advance_fen"))
        d.update({"tier": "TIER_2", "created_day": op.get("day"), "amount_fen": amt,
                  "amount_display": fmt_yuan(amt) if isinstance(amt, int) else None,
                  "subject": f"{(a.kind or '').replace('_', ' ').lower()} {op.get('facility_id', '')}".strip()})
        try:
            run = ran.get(a.id)
            if d.get("decided_day") is None and run is not None:  # decided before the record kept the day
                d["decided_day"] = run.result.effective_day
            d["result_message"] = run.result.message if run is not None else None
            # Presentation fields (business words) for the owner's card: the question, names, cost and landing day.
            alert = (open_alerts.get((a.op_id or "").split(":")[1])
                     if pending and (a.op_id or "").startswith("alert:") else None)
            after, residual = (cure_after(state, obs, rt.store.get_mandate(), alert, rt.day, lang) if alert is not None else (None, None))
            # An agreement row carries its terms, resolved here from the commitment it refers to (F02).
            terms = agreement_terms(state, find_agreement(op, commitments), rt.day, lang,
                                     pending=pending,
                                     horizon_days=rt.store.get_mandate().forward_concession_horizon_days) if a.kind in COMMERCIAL_KINDS else None
            d["presentation"] = approval_words(state, op, a.kind, rt.day, alert, lang, plan_costs if pending else None, after=after,
                                               status=d["status"], agreement=terms)
            d["presentation"]["residual"] = residual
            d["presentation"]["execution_status"] = _execution_status(d["status"], run.result.status.value if run is not None else None)
            if terms is not None and d["amount_display"] is None:
                d["amount_display"] = d["presentation"]["amount_display"]  # the agreement's scope, never ¥0.00
            d["presentation"]["reason"] = approval_reason_words(state, a.reason, rt.day, lang)
            d["presentation"]["result_message"] = (
                (result_words(state, kind=a.kind or "", status=run.result.status.value, payload=op, day=run.result.effective_day,
                              today=rt.day, lang=lang, approval_status=d["status"], message=run.result.message,
                              agreements=agreements) if run is not None else None)
                or (business_text(state, d["result_message"], rt.day, lang, agreements) if d["result_message"] else None))
            d["presentation"]["decided_when"] = (relative_days(f"on day {d['decided_day']}", rt.day, lang)
                                                 if d.get("decided_day") is not None else None)
            d["presentation"]["created_when"] = (when_text(int(d["created_day"]), rt.day, lang)
                                                 if d.get("created_day") is not None else None)
        except Exception:
            log.exception("approval %s could not be presented", a.id)
            d.setdefault("presentation", None)
        d.update({"decision_id": None, "decision_state": None, "quote": None, "execution": None})
        if ctx is not None and d.get("presentation") is not None:
            try:
                d.update(_decision_fields(ctx, rt, a, op, d["status"], d["presentation"], ran.get(a.id), lang))
            except Exception:
                log.exception("approval %s: the decision record could not be read", a.id)
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
