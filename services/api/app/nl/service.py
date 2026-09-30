"""`handle()`: one /nl turn. Parse (rules first, then the optional classifier), resolve a pending
clarification or correction, dispatch to the intent handler, guard the reply, update the session.

The owner is authenticated by the caller (the API layer checks the owner token); this module never
sees the token. A COUNTERPARTY request is never parsed for intents.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.domain.models import (
    Actor,
    ChangeMandate,
    IssueEquity,
    OperationResult,
    PledgeCollateral,
    SecurityEventKind,
    SignPersonalGuarantee,
)
from app.domain.ports import LedgerStore
from app.nl import classifier as clf
from app.nl import lexicon as lx
from app.nl.context import NlContext
from app.nl.funding import accelerate, fund_gap, repay, status
from app.nl.models import Intent, NlRequest, NlResponse, Parsed, Slots
from app.nl.offers import (
    counterparty_message,
    evaluate_offer,
    execute_decision,
    explain,
    negotiate_intent,
    what_if,
)
from app.nl.pipeline import Steps, t
from app.nl.rules import parse
from app.nl.sessions import SESSIONS, Session, SessionStore
from app.nl.turn import Turn, ask
from app.operations import Executor

MIN_LLM_CONFIDENCE = 0.6
CAPABILITIES_EN = ("I can evaluate a buyer's offer, negotiate with counters, get an invoice paid early, fund a "
                   "projected cash gap, repay a facility, show cash status, explain a verdict, run a what-if, and "
                   "approve or reject pending operations.")
CAPABILITIES_ZH = ("我可以评估买家报价、发送反报价谈判、提前收款、为资金缺口融资、偿还额度、查看现金状况、解释结论、"
                   "做假设分析，以及批准或驳回待审批操作。")


def handle(req: NlRequest, *, store: LedgerStore, executor: Executor, day: int, owner_key_hex: str,
           owner_authenticated: bool, sessions: SessionStore = SESSIONS,
           classifier_backends: Sequence[clf.IntentBackend] | None = None) -> NlResponse:
    session, _new = sessions.get_or_create(req.session_id, req.actor)
    session.turn += 1
    lang = req.lang or lx.detect_lang(req.text)
    session.lang = lang
    if req.actor == "OWNER" and req.counterparty_id:
        session.counterparty_id = req.counterparty_id
    if req.buyer_profile:
        session.buyer_profile = req.buyer_profile
    ctx = NlContext(store=store, executor=executor, day=day, owner_key_hex=owner_key_hex,
                    owner_authenticated=owner_authenticated and req.actor == "OWNER", session=session, lang=lang,
                    trace_id=f"{session.id}:{session.turn}", request_id=req.request_id)

    before = {e.id for e in store.security_events()}
    if req.request_id and req.request_id in session.requests:
        return _replay(ctx, session.requests[req.request_id], before)

    parse_source = "actor"
    if req.actor == "COUNTERPARTY":
        turn = counterparty_message(ctx, req.text, req.counterparty_id)
    else:
        parsed = _parse(ctx, req.text, classifier_backends)
        parse_source = parsed.source
        turn = _dispatch(ctx, parsed, req.text)

    if not turn.guarded:
        turn.reply, _ok = ctx.guard(turn.reply, turn.recipient, allow=turn.allow)
    _update_session(session, turn)
    if req.request_id:
        session.requests[req.request_id] = list(ctx.sent)
    session.history.append((session.turn, turn.intent.value))
    return _response(ctx, turn, parse_source, before)


# ---------------------------------------------------------------- parsing


def _parse(ctx: NlContext, text: str, backends: Sequence[clf.IntentBackend] | None) -> Parsed:
    s = ctx.session
    state = ctx.state()
    if s.pending_clarification is not None:
        resolved = _resolve_clarification(ctx, text)
        if resolved is not None:
            return resolved
    parsed = parse(text, state, pending_plan=s.pending_plan is not None)
    if parsed is not None:
        return parsed
    if s.pending_clarification is not None:  # still unanswered: ask again
        pc = s.pending_clarification
        return Parsed(intent=Intent.AMBIGUOUS, slots=pc.slots, source="clarification", matched=["re-ask"])
    got, rejected = clf.classify(text, backends)
    for r in rejected:
        if r.reason.startswith("canary:"):
            ctx.new_event(SecurityEventKind.DATA_EXTRACTION, "OWNER",
                          f"intent classifier output from {r.backend} contained {r.reason}; discarded",
                          action="classifier output discarded")
    if got is None or got.result.confidence < MIN_LLM_CONFIDENCE:
        return Parsed(intent=Intent.OUT_OF_SCOPE, source="fallback")
    ls = got.result.slots
    cps = lx.find_counterparty(ls.counterparty_name or "", state) if ls.counterparty_name else []
    from app.domain.fixtures import load_offers

    slots = Slots(counterparty_id=cps[0] if len(cps) == 1 else None, amount_fen=ls.amount_fen, rate_bp=ls.rate_bp,
                  terms_days=ls.terms_days, fixture_id=ls.fixture_id if ls.fixture_id in load_offers() else None,
                  zero_forward=ls.zero_forward, execute_now=False)
    return Parsed(intent=Intent(got.result.intent), slots=slots, source=f"llm:{got.model_id}")


def _resolve_clarification(ctx: NlContext, text: str) -> Parsed | None:
    pc = ctx.session.pending_clarification
    assert pc is not None
    choice: str | None = None
    n = lx.ordinal(text)
    ids = [o.id for o in pc.options]
    if n is not None:
        if n == 99:
            choice = next((o.id for o in pc.options if pc.values.get(o.id) == 99), None)
        elif 1 <= n <= len(ids):
            choice = ids[n - 1]
    if choice is None:
        low = lx.norm(text)
        for o in pc.options:
            v = pc.values.get(o.id)
            if isinstance(v, str) and v.lower() in low:
                choice = o.id
                break
        if choice is None and pc.slot == "counterparty_id":
            hits = lx.find_counterparty(text, ctx.state())
            if len(hits) == 1:
                choice = next((o.id for o in pc.options if pc.values.get(o.id) == hits[0]), None)
    if choice is None:
        return None
    value: Any = pc.values[choice]
    ctx.session.pending_clarification = None
    if pc.slot == "intent":
        return Parsed(intent=Intent(value), slots=pc.slots, source="clarification", matched=[f"option:{choice}"])
    slots = pc.slots.model_copy(update={pc.slot: value})
    return Parsed(intent=pc.intent, slots=slots, source="clarification", matched=[f"option:{choice}"])


# ---------------------------------------------------------------- dispatch


def _dispatch(ctx: NlContext, p: Parsed, text: str) -> Turn:
    s = ctx.session
    llm = p.source.startswith("llm:")
    if p.correction and s.pending_plan is not None:
        return _correct(ctx, p, text)
    if p.confirm_plan and s.pending_plan is not None:
        return _confirm(ctx, p.intent == Intent.APPROVE, text)
    if p.intent == Intent.AMBIGUOUS and p.source == "clarification" and s.pending_clarification is not None:
        pc = s.pending_clarification
        t_ = ask(pc.intent, pc.slot, t(ctx, "Sorry, which one?", "抱歉，请问是哪一个？"),
                 [(o.id, o.label, pc.values[o.id]) for o in pc.options], pc.slots)
        return t_
    slots = p.slots
    if slots.counterparty_id is None and s.counterparty_id:
        slots = slots.model_copy(update={"counterparty_id": s.counterparty_id})
    match p.intent:
        case Intent.EVALUATE_OFFER:
            return evaluate_offer(ctx, slots)
        case Intent.NEGOTIATE:
            return negotiate_intent(ctx, slots, execute=not llm)
        case Intent.ACCELERATE_RECEIPT:
            return accelerate(ctx, slots, text, execute=slots.execute_now and not llm)
        case Intent.FUND_GAP:
            return fund_gap(ctx, slots, execute=not llm and not p.tentative)
        case Intent.REPAY_FACILITY:
            return repay(ctx, slots, execute=not llm)
        case Intent.SHOW_STATUS:
            return status(ctx)
        case Intent.EXPLAIN:
            return explain(ctx, slots)
        case Intent.WHAT_IF:
            return what_if(ctx, slots, text)
        case Intent.APPROVE | Intent.REJECT:
            return _decide_approval(ctx, slots, p.intent == Intent.APPROVE)
        case Intent.AMBIGUOUS:
            return ask(Intent.AMBIGUOUS, "intent", t(ctx, "What would you like me to do?", "您希望我做什么？"),
                       [("1", t(ctx, "show cash status", "查看现金状况"), Intent.SHOW_STATUS.value),
                        ("2", t(ctx, "fund the projected gap", "为资金缺口融资"), Intent.FUND_GAP.value),
                        ("3", t(ctx, "get an invoice paid early", "提前收款"), Intent.ACCELERATE_RECEIPT.value)],
                       slots)
        case _:
            return _out_of_scope(ctx, slots)


HANDLERS_WITH_PLANS = (Intent.ACCELERATE_RECEIPT, Intent.FUND_GAP, Intent.REPAY_FACILITY, Intent.NEGOTIATE,
                       Intent.EVALUATE_OFFER)


def _correct(ctx: NlContext, p: Parsed, text: str) -> Turn:
    """Amend the pending plan: new typed slot values replace the old ones, then the plan is rebuilt and
    re-verified. It stays pending; nothing runs until the owner confirms."""
    pending = ctx.session.pending_plan
    assert pending is not None
    new = p.slots
    update: dict[str, Any] = {}
    if new.rate_bp is not None:
        update.update(rate_bp=new.rate_bp, use_financing=False)
    if new.use_financing:
        update["use_financing"] = True
    for k in ("counterparty_id", "amount_fen", "buyer_profile", "facility_id"):
        if getattr(new, k) is not None:
            update[k] = getattr(new, k)
    slots = pending.slots.model_copy(update=update)
    if pending.intent == Intent.ACCELERATE_RECEIPT:
        turn = accelerate(ctx, slots, text, execute=False, amended=True)
    elif pending.intent == Intent.FUND_GAP:
        turn = fund_gap(ctx, slots, execute=False)
    elif pending.intent == Intent.REPAY_FACILITY:
        turn = repay(ctx, slots, execute=False)
    elif pending.intent == Intent.NEGOTIATE:
        turn = negotiate_intent(ctx, slots, execute=False, data=pending.data)
    else:
        turn = Turn(intent=pending.intent, reply=t(ctx, "That plan can't be amended; say 'cancel' or 'go ahead'.",
                                                   "该方案无法修改；请回复“取消”或“执行”。"), plan=pending.steps,
                    awaiting=True)
    if turn.pending is not None:
        turn.amended = True
    return turn


def _confirm(ctx: NlContext, yes: bool, text: str) -> Turn:
    pending = ctx.session.pending_plan
    assert pending is not None
    if not yes:
        steps = [s.model_copy(update={"status": "SKIPPED"}) for s in pending.steps]
        return Turn(intent=Intent.REJECT, reply=t(ctx, "Cancelled. Nothing was executed.", "已取消，未执行任何操作。"),
                    plan=steps, clear_pending=True)
    slots = pending.slots.model_copy(update={"execute_now": True})
    match pending.intent:
        case Intent.ACCELERATE_RECEIPT:
            turn = accelerate(ctx, slots, text, execute=True)
        case Intent.FUND_GAP:
            turn = fund_gap(ctx, slots, execute=True)
        case Intent.REPAY_FACILITY:
            turn = repay(ctx, slots, execute=True)
        case Intent.NEGOTIATE:
            turn = negotiate_intent(ctx, slots.model_copy(update={"fixture_id": None, "quoted_text": None}),
                                    execute=True, data=pending.data)
        case Intent.EVALUATE_OFFER:
            turn = execute_decision(ctx, pending.data["verdict_id"])
        case _:
            turn = Turn(intent=pending.intent, reply=t(ctx, "Nothing to run.", "没有可执行的内容。"))
    turn.clear_pending = True
    return turn


def _decide_approval(ctx: NlContext, slots: Slots, approve: bool) -> Turn:
    """Owner decision on a queued Tier-2 operation. Without the owner token the request is the AGENT's,
    and the executor refuses it (logged as PRIVILEGE_ESCALATION)."""
    from app.persistence import ApprovalAlreadyDecided, NotFound

    pending = [a for a in ctx.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"]
    aid = slots.approval_id
    intent = Intent.APPROVE if approve else Intent.REJECT
    if aid is None:
        if not pending:
            return Turn(intent=intent, reply=t(ctx, "Nothing is waiting for approval.", "目前没有待审批的操作。"))
        if len(pending) > 1:
            return ask(intent, "approval_id", t(ctx, "Which pending operation?", "哪一项待审批操作？"),
                       [(str(i), f"{a.id}: {a.reason}", a.id) for i, a in enumerate(pending, 1)], slots)
        aid = pending[0].id
    actor = Actor.OWNER if ctx.owner_authenticated else Actor.AGENT
    steps = Steps()
    try:
        r: OperationResult = ctx.executor.decide(aid, approve, actor)
    except NotFound:
        return Turn(intent=intent, reply=t(ctx, f"{aid} is not in the approvals queue.", f"{aid} 不在审批队列中。"))
    except ApprovalAlreadyDecided:
        return Turn(intent=intent, reply=t(ctx, f"{aid} was already decided.", f"{aid} 已处理。"))
    ctx.results.append(r)
    verb = t(ctx, "Approve", "批准") if approve else t(ctx, "Decline", "驳回")
    steps.result("DECIDE_APPROVAL", f"{verb} {aid} ({r.kind})", r)
    if actor != Actor.OWNER:
        reply = t(ctx, f"Refused: only the owner can decide {aid}, and this request carries no owner credential. "
                       "Logged.", f"已拒绝：只有业主可以审批 {aid}，此请求没有业主凭证。已记录。")
    else:
        reply = r.message
    return Turn(intent=intent, reply=reply, plan=steps.items)


TIER3_OPS = {"SIGN_PERSONAL_GUARANTEE": SignPersonalGuarantee, "PLEDGE_COLLATERAL": PledgeCollateral,
             "ISSUE_EQUITY": IssueEquity, "CHANGE_MANDATE": ChangeMandate}


def _out_of_scope(ctx: NlContext, slots: Slots) -> Turn:
    steps = Steps()
    if slots.tier3:
        # The typed request goes to the executor so its refusal is on the hash-chained log: tiers are
        # enforced by code, not by this parser (INVARIANTS 6 and 12).
        kind = slots.tier3
        base = ctx.base(kind)
        facility = slots.facility_id or next((f.id for f in ctx.state().facilities), "UNSPECIFIED")
        if kind in ("SIGN_PERSONAL_GUARANTEE", "PLEDGE_COLLATERAL"):
            op = TIER3_OPS[kind](**base, facility_id=facility)
        elif kind == "ISSUE_EQUITY":
            op = IssueEquity(**base, amount_fen=slots.amount_fen or 0)
        else:
            op = ChangeMandate(**base, new_version=ctx.mandate().version + 1)
        r = ctx.execute(op)
        steps.result(kind, t(ctx, f"{kind} requested", f"请求 {kind}"), r)
        return Turn(intent=Intent.OUT_OF_SCOPE, plan=steps.items, reply=t(
            ctx, f"Refused: {kind.replace('_', ' ').lower()} is a Tier-3 action. The agent can never do it, whoever "
                 f"asks; it was refused by the executor and logged. " + CAPABILITIES_EN,
            f"已拒绝：{kind} 属于三级操作，代理在任何情况下都不能执行；执行器已拒绝并记录。" + CAPABILITIES_ZH))
    if slots.capex:
        return Turn(intent=Intent.OUT_OF_SCOPE, reply=t(
            ctx, "Capex decisions are not available through this assistant yet (feature 'capex'). " + CAPABILITIES_EN,
            "资本支出评估暂不支持。" + CAPABILITIES_ZH))
    return Turn(intent=Intent.OUT_OF_SCOPE, reply=t(ctx, "Sorry, that's outside what I can do. " + CAPABILITIES_EN,
                                                    "抱歉，这超出了我的能力范围。" + CAPABILITIES_ZH))


# ---------------------------------------------------------------- session and response


def _update_session(session: Session, turn: Turn) -> None:
    if turn.pending_clarification is not None:
        session.pending_clarification = turn.pending_clarification
    if turn.pending is not None:
        session.pending_plan = turn.pending
    elif turn.clear_pending:
        session.pending_plan = None


def _replay(ctx: NlContext, ops: list[Any], before: set[str]) -> NlResponse:
    """A retried request_id: re-send exactly the same typed operations. The executor answers DUPLICATE
    for each; nothing is re-planned or re-executed."""
    steps = Steps()
    for op in ops:
        r = ctx.executor.execute(op)
        ctx.results.append(r)
        steps.result(op.kind, t(ctx, f"Replay of {op.op_id}", f"重放 {op.op_id}"), r)
    turn = Turn(intent=Intent(ctx.session.history[-1][1]) if ctx.session.history else Intent.OUT_OF_SCOPE,
                reply=t(ctx, f"Replayed request: {len(ops)} operation(s), nothing executed twice.",
                        f"重放请求：{len(ops)} 项操作，未重复执行。"), plan=steps.items)
    return _response(ctx, turn, "replay", before, replayed=True)


def _response(ctx: NlContext, turn: Turn, parse_source: str, before: set[str],
              replayed: bool = False) -> NlResponse:
    events = list(ctx.events) + [e.id for e in ctx.store.security_events()
                                 if e.id not in before and e.id not in ctx.events]
    return NlResponse(
        session_id=ctx.session.id, turn=ctx.session.turn, reply=turn.reply, intent=turn.intent,
        lang=ctx.lang,  # type: ignore[arg-type]
        plan=turn.plan, verdict=turn.verdict.model_dump(mode="json") if turn.verdict is not None else None,
        operations=[r.model_dump(mode="json") for r in ctx.results], clarification=turn.clarification,
        awaiting_confirmation=turn.awaiting, amended=turn.amended, replayed=replayed, negotiation=turn.negotiation,
        security_events=events, parse_source=parse_source, trace_id=ctx.trace_id)
