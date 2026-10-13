"""Typed operations, the Tier-2 approvals queue and the circuit breaker. The executor decides; this
layer only authenticates the owner and never trusts a body's claim to be the owner."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.alerts import Alert, alerts
from app.api.approval_lines import FUNDING_KINDS, NO_LINES, approval_lines
from app.api.approval_review import approval_review
from app.api.auth import is_bank_feed, log_refusal, require_owner, require_owner_or_agent
from app.api.decisions import approval_decision, execution_view, load_context, quote_for, record_fact
from app.api.home import cure_after
from app.api.presentation import (
    COMMERCIAL_KINDS,
    agreement_terms,
    approval_reason_words,
    approval_result_state,
    approval_words,
    business_text,
    decided_headline,
    executed_words,
    find_agreement,
    last_read,
    party_name,
    quote_not_recorded,
    result_words,
    short_kind,
    t,
    when_text,
)
from app.api.quotes import FUNDING_OPS, build_shown_quote, reason_rate
from app.api.receipt import approval_receipt
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.decisions.identity import decision_id_for
from app.domain.models import Actor, Operation, OperationResult, OperationStatus, RepayFacility
from app.domain.money import fmt_yuan
from app.financial import EngineError
from app.funding.recommend import cost_lines_by_leg, runnable_plan
from app.operations import security_summary
from app.operations.log import read_entries
from app.persistence import ApprovalAlreadyDecided

log = logging.getLogger("termsledger.decisions")
router = APIRouter()
_OP: TypeAdapter[Operation] = TypeAdapter(Operation)


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
    return run_operation(rt, body)


def run_operation(rt: Runtime, body: dict) -> dict:
    """Type the body and hand it to the executor: the part of POST /operations after who is asking is settled. The demo's seed
    replay (`app.api.demo_seed`) calls it with an agent's body, so a seeded operation is queued exactly as the route queues one."""
    body.setdefault("day", rt.day)
    try:
        op = _OP.validate_json(json.dumps(body))
    except ValidationError as e:  # malformed operations never reach the executor
        raise HTTPException(422, f"not a typed operation: {e.__class__.__name__}") from None
    with rt.lock:
        result = rt.executor.execute(op)
        recorded = _record_direct_quote(rt, op, result)
    out: dict = {"result": _result(result)}
    if recorded is not None:
        out["decision_id"], out["decision_recorded"] = recorded
    return out


def _record_direct_quote(rt, op: Operation, result: OperationResult) -> tuple[str, bool | str] | None:
    """A funding operation posted directly that the executor queued for the owner is a decision with no alert and no chat plan behind it
    (`approval:{id}`). After the executor returned, store its own figures as the QUOTED fact so that its decided card shows what it was:
    the amount, the facility, the landing day and the executor's own cost line (the rate in its reason for queueing). API layer only; a
    failure is logged and answered with False, never raised (ADR-0011 section 4, ticket #84)."""
    if result.status != OperationStatus.PENDING_APPROVAL or not result.approval_id or not isinstance(op, FUNDING_OPS):
        return None
    try:
        did = decision_id_for(op.model_dump(mode="json"), op.idempotency_key, rt.store.commitments(), approval_id=result.approval_id)
        if did is None or not did.startswith("approval:"):  # an alert's or a chat plan's operations have their own decision
            return None
        approval = rt.store.get_approval(result.approval_id)
        rate, above = reason_rate(approval.reason if approval is not None else None)
        state, mandate = rt.store.get_state(), rt.store.get_mandate()
        kind = "FACILITY_REPAYABLE" if isinstance(op, RepayFacility) else "OPERATION"
        return did, record_fact(
            rt, did, did,
            lambda: build_shown_quote(state, mandate, [op], max(rt.day, state.as_of_day), decision_id=did, alert_kind=kind, rates=[rate],
                                      above_ceiling=[above], needs_owner=True),
            state_version=state.state_version, day=rt.day)
    except Exception:
        log.exception("the quote of the direct operation %s could not be recorded", op.op_id)
        return None


def _decision_runs(store, entries=None) -> dict:
    """Per approval id, the log entry of the owner's decision run: the first non-PENDING row that ran under it
    (an owner-approved re-run or a decline). A non-owner's refused attempt (key `#decide:`) is not the decision.
    `entries` is the log already parsed by the caller, when it has it."""
    if entries is None:
        entries, _ = read_entries(store.operations())
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
                                     "restores_reserve": False, "text": view["after"]}
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
    state = rt.store.get_state()
    commitments = rt.store.commitments()
    agreements = {c.id: party_name(state, c.counterparty_id) for c in commitments}
    # The alerts whose cures are queued carry the engine's price for them; read once, only when something is pending. A decided
    # row is never priced from them: its quote is the fact stored when it was requested.
    open_alerts: dict = {}
    plan_costs: dict = {}
    obs: list = []
    found: Sequence[Alert] | None = None  # the alerts, once, when this request ran them; the decision record is handed them and does not run them again
    ctx = None
    with rt.lock:
        if any(str(getattr(a.status, "value", a.status)) == "PENDING" for a in rt.store.approvals()):
            try:
                try:
                    found = alerts(state, rt.store.get_mandate(), rt.store, rt.day)
                except EngineError:
                    found = ()  # as the decision record reads them when the engine cannot
                    raise
                open_alerts = {al.id: al for al in found}
                obs = current_books(state, rt.store.commitments()).with_([])
                if rt.settings.features.debt_desk:  # a queued leg of the recommended router plan carries its cost line
                    books = current_books(state, rt.store.commitments())
                    plan = runnable_plan(books.state, books.with_([]), rt.store.get_mandate())
                    plan_costs = cost_lines_by_leg(plan) if plan is not None else {}
            except EngineError:
                open_alerts = {}
        try:
            ctx = load_context(rt, found=found)
        except Exception:
            log.exception("the decision record could not be read for the approvals queue")
        # The log is parsed once for the request: the decision record's entries when it has them.
        entries = ctx.entries if ctx is not None else read_entries(rt.store.operations())[0]
        ran = _decision_runs(rt.store, entries)
        # the tier the executor judged, from the first log entry of each approval (as the decision record's `authorization` reads it)
        judged: dict[str, str] = {}
        for e in entries:
            if e.result.approval_id and e.result.approval_id not in judged:
                judged[e.result.approval_id] = e.result.tier.value
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
        # an approval exists only because the executor judged the operation Tier 2, so a record that kept no entry for it is that tier
        d.update({"tier": judged.get(a.id, "TIER_2"), "created_day": op.get("day"), "amount_fen": amt,
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
            d["presentation"].update(approval_lines(state, obs, rt.store.get_mandate(), a.op_json, alert, rt.day, lang)
                                     if pending and a.kind in FUNDING_KINDS else dict(NO_LINES))
            d["presentation"]["execution_status"] = _execution_status(d["status"], run.result.status.value if run is not None else None)
            if terms is not None and d["amount_display"] is None:
                d["amount_display"] = d["presentation"]["amount_display"]  # the agreement's scope, never ¥0.00
            d["presentation"]["reason"] = approval_reason_words(state, a.reason, rt.day, lang)
            d["presentation"]["next_step_text"] = d["presentation"]["next_step_href"] = None
            if not pending:
                (d["presentation"]["headline"], d["presentation"]["next_step_text"],
                 d["presentation"]["next_step_href"]) = decided_headline(
                    kind=a.kind or "", status=d["status"], execution_status=d["presentation"]["execution_status"],
                    amount_display=d["presentation"].get("amount_display") or d["amount_display"], what=short_kind(a.kind or "", lang),
                    buyer=(terms or {}).get("counterparty_name"), lang=lang)
            d["presentation"]["result_state_text"], d["presentation"]["result_tone"] = approval_result_state(
                kind=a.kind or "", status=d["status"], execution_status=d["presentation"]["execution_status"],
                lands_day=d["presentation"]["lands_day"], today=rt.day, lang=lang)
            d["presentation"]["result_message"] = (
                (result_words(state, kind=a.kind or "", status=run.result.status.value, payload=op, day=run.result.effective_day,
                              today=rt.day, lang=lang, approval_status=d["status"], message=run.result.message,
                              agreements=agreements) if run is not None else None)
                or (business_text(state, d["result_message"], rt.day, lang, agreements) if d["result_message"] else None))
            d["presentation"]["decided_when"] = (when_text(int(d["decided_day"]), rt.day, lang)
                                                 if d.get("decided_day") is not None else None)
            d["presentation"]["created_when"] = (when_text(int(d["created_day"]), rt.day, lang)
                                                 if d.get("created_day") is not None else None)
        except Exception:
            log.exception("approval %s could not be presented", a.id)
            d.setdefault("presentation", None)
        if d.get("presentation") is not None:
            d["result_state_text"] = d["presentation"].get("result_state_text")
            d["result_tone"] = d["presentation"].get("result_tone")
        d.update({"decision_id": None, "decision_state": None, "quote": None, "execution": None})
        if ctx is not None and d.get("presentation") is not None:
            try:
                d.update(_decision_fields(ctx, rt, a, op, d["status"], d["presentation"], ran.get(a.id), lang))
            except Exception:
                log.exception("approval %s: the decision record could not be read", a.id)
        d["receipt"] = approval_receipt(lang, item=d, pres=d["presentation"]) if d.get("presentation") is not None else None
        d.update(approval_review(lang, item=d))
        out.append(d)
    return {"approvals": out, "lang": lang, **last_read(rt.day, lang)}


class Decision(BaseModel):
    decision: str  # APPROVE | REJECT


@router.post("/approvals/{approval_id}", dependencies=[Depends(require_owner_or_agent)])
def decide(approval_id: str, body: Decision, request: Request, x_owner_token: str | None = Header(default=None),
           lang: str = "en") -> dict:
    """The owner's decision on a queued approval. `lang` (en | zh, additive) is the language of the words the server writes for the
    result (`message_when`, `event_text`, `event_detail`); the executor's `message` stays as written."""
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
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
    raw = _result(r)
    words: dict = {}
    try:  # the words are a presentation read: a failure here never changes the answer to the decision
        approval = rt.store.get_approval(approval_id)
        state = rt.store.get_state()
        words = executed_words(state, payload=json.loads(approval.op_json) if approval is not None else {}, result=raw, today=rt.day,
                               lang=lang, agreements={c.id: party_name(state, c.counterparty_id) for c in rt.store.commitments()})
    except Exception:
        log.exception("the words for the decision on %s could not be written", approval_id)
    return {"result": {**raw, **words}, "lang": lang}


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
