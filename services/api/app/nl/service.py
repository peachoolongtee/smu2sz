"""`handle()`: one /nl turn. Parse (rules first, then the optional classifier), resolve a pending
clarification or correction, dispatch to the intent handler, guard the reply, update the session.

The owner is authenticated by the caller (the API layer checks the owner token); this module never
sees the token. A COUNTERPARTY request is never parsed for intents.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.models import (
    Actor,
    ChangeMandate,
    CompiledOffer,
    FinancialState,
    IssueEquity,
    Mandate,
    OperationResult,
    OperationStatus,
    PledgeCollateral,
    SecurityEventKind,
    SignPersonalGuarantee,
)
from app.domain.ports import LedgerStore
from app.nl import capabilities as cap
from app.nl import classifier as clf
from app.nl import landing, plans
from app.nl import lexicon as lx
from app.nl.alerts import alerts_intent, alerts_turn, confirm_cure
from app.nl.context import NlContext
from app.nl.funding import (
    accelerate,
    fund_gap,
    repay,
    reprice_accelerate,
    reprice_fund_gap,
    reprice_repay,
    run_accelerate,
    status,
)
from app.nl.models import Intent, NlRequest, NlResponse, Parsed, Slots
from app.nl.offers import (
    counterparty_message,
    evaluate_offer,
    execute_decision,
    explain,
    followup_text,
    negotiate_intent,
    what_if,
)
from app.nl.pipeline import Steps, committed_plan, package_offer, status_quo_offer, t
from app.nl.rules import parse
from app.nl.sessions import SESSIONS, Session, SessionStore
from app.nl.turn import Turn, ask
from app.operations import Executor
from app.operations.log import parse_operation
from app.verifier import OwnerConstraints, VerdictBundle

# (bundle, offer, state, mandate) -> extra keys for an OWNER verdict; injected by the API layer, never used for
# a counterparty (the counterparty response carries no verdict at all).
VerdictExtras = Callable[[VerdictBundle, CompiledOffer, FinancialState, Mandate], dict[str, Any]]

MIN_LLM_CONFIDENCE = 0.6
APPROVAL_ID = re.compile(r"APR-\d{6}", re.IGNORECASE)
CAPABILITIES_EN = ("I can evaluate a buyer's offer, negotiate with counters, get an invoice paid early, fund a "
                   "projected cash gap, repay a facility, show cash status, explain a verdict, run a what-if, compare "
                   "financing options, reconcile receipts, show the covenant ratios, evaluate an equipment purchase, "
                   "prepare a borrower file, and approve or reject pending operations.")
CAPABILITIES_ZH = ("我可以评估买家报价、发送反报价谈判、提前收款、为资金缺口融资、偿还额度、查看现金状况、解释结论、"
                   "做假设分析、比较融资方案、核对回款、查看契约指标、评估设备购置、准备借款人资料，以及批准或驳回待审批操作。")


@dataclass
class _TurnContext(NlContext):
    """NlContext that remembers each bundle the verifier produced this turn (with the offer, state and mandate it
    was evaluated on), so the owner's response can carry its passed checks and autonomy proof."""

    extras: VerdictExtras | None = None
    seen: dict[str, tuple[VerdictBundle, CompiledOffer, FinancialState, Mandate]] = field(default_factory=dict)
    zero_forward: bool = False  # the owner asked for a negotiation "without giving anything away": a constraint

    def evaluate(self, offer: CompiledOffer, **kw: Any) -> VerdictBundle:
        if self.zero_forward and kw.get("owner_constraints") is None:
            kw["owner_constraints"] = OwnerConstraints(zero_forward_concessions=True)
        state, mandate = kw.get("state") or self.state(), self.mandate()
        bundle = super().evaluate(offer, **kw)
        self.seen[bundle.verdict.id] = (bundle, offer, state, mandate)
        return bundle


def handle(req: NlRequest, *, store: LedgerStore, executor: Executor, day: int, owner_key_hex: str,
           owner_authenticated: bool, sessions: SessionStore = SESSIONS,
           classifier_backends: Sequence[clf.IntentBackend] | None = None,
           verdict_extras: VerdictExtras | None = None) -> NlResponse:
    session, _new = sessions.get_or_create(req.session_id, req.actor,
                                           owner_auth=owner_authenticated and req.actor == "OWNER")
    session.turn += 1
    lang = req.lang or lx.detect_lang(req.text)
    session.lang = lang
    if req.actor == "OWNER" and req.counterparty_id:
        session.counterparty_id = req.counterparty_id
    if req.buyer_profile:
        session.buyer_profile = req.buyer_profile
    ctx = _TurnContext(store=store, executor=executor, day=day, owner_key_hex=owner_key_hex,
                       owner_authenticated=owner_authenticated and req.actor == "OWNER", session=session, lang=lang,
                       trace_id=f"{session.id}:{session.turn}", request_id=req.request_id, extras=verdict_extras)

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

    if turn.pending is not None and turn.pending.state_version is None:
        turn.pending.bind(ctx)  # the books this proposal was made on (a plan the handler did not bind itself)
        if turn.pending.intent == Intent.NEGOTIATE:
            turn.pending.data["followups"] = _followups(ctx, turn.pending.data.get("verdict_id"))
            turn.pending.data["zero_forward"] = isinstance(ctx, _TurnContext) and ctx.zero_forward  # as it was shown
    if not turn.guarded:
        turn.reply, _ok = ctx.guard(turn.reply, turn.recipient, allow=turn.allow)
    _update_session(session, turn)
    if req.actor == "OWNER":
        _remember_shown(ctx, turn)
    if req.request_id:
        session.requests[req.request_id] = list(ctx.sent)
    session.history.append((session.turn, turn.intent.value))
    return _response(ctx, turn, parse_source, before)


def opener(session_id: str | None, lang: str | None, *, store: LedgerStore, executor: Executor, day: int,
           owner_key_hex: str, sessions: SessionStore = SESSIONS,
           verdict_extras: VerdictExtras | None = None) -> tuple[NlResponse, bool]:
    """An agent-initiated turn in the owner's session (the API layer has checked the owner token): the agent says
    what needs the owner, if anything, and proposes the cure as a pending plan. It executes nothing; the owner's
    next direct "go ahead" in this session confirms it. Returns (the response, whether anything needs the owner)."""
    session, _new = sessions.get_or_create(session_id, "OWNER", owner_auth=True)
    session.turn += 1
    if lang:
        session.lang = lang
    ctx = _TurnContext(store=store, executor=executor, day=day, owner_key_hex=owner_key_hex, owner_authenticated=True,
                       session=session, lang=session.lang, trace_id=f"{session.id}:{session.turn}",
                       extras=verdict_extras)
    before = {e.id for e in store.security_events()}
    turn, has_news = alerts_turn(ctx)
    turn.reply, _ok = ctx.guard(turn.reply, turn.recipient, allow=turn.allow)
    _update_session(session, turn)
    _remember_shown(ctx, turn)
    session.history.append((session.turn, turn.intent.value))
    return _response(ctx, turn, "opener", before), has_news


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
        if parsed.slots.quoted_approval:
            ctx.new_event(SecurityEventKind.INJECTION, parsed.slots.counterparty_id or "OWNER",
                          "quoted text contained an approval instruction; ignored", action="ignored; nothing approved")
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
    if llm and p.intent in (Intent.APPROVE, Intent.REJECT):  # the classifier can never decide an approval or confirm a plan
        return _consent_turn(ctx, p, "approval_llm", text)
    if p.intent in (Intent.APPROVE, Intent.REJECT) and not llm and not _direct_command(ctx, text):
        return _not_a_direct_command(ctx, p)
    if "confirm_unclear" in p.matched and s.pending_plan is not None:
        return Turn(intent=Intent.AMBIGUOUS, awaiting=True, reply=t(
            ctx, "I have not run anything. The plan above is still waiting: reply just 'go ahead' to run it, or "
                 "'cancel'.", "我没有执行任何操作。上面的方案仍在等待：请只回复“执行”以运行，或回复“取消”。"))
    if p.confirm_plan and s.pending_plan is not None:
        return _confirm(ctx, p.intent == Intent.APPROVE, text)
    if not llm and (tag := next((m for m in p.matched if m.startswith("consent:")), None)):
        return _consent_turn(ctx, p, tag.split(":", 1)[1], text)
    if p.intent == Intent.AMBIGUOUS and p.source == "clarification" and s.pending_clarification is not None:
        pc = s.pending_clarification
        t_ = ask(pc.intent, pc.slot, t(ctx, "Sorry, which one?", "抱歉，请问是哪一个？"),
                 [(o.id, o.label, pc.values[o.id]) for o in pc.options], pc.slots)
        return t_
    slots = p.slots
    if slots.counterparty_id is None and s.counterparty_id:
        slots = slots.model_copy(update={"counterparty_id": s.counterparty_id})
    if p.intent in cap.OWNER_ONLY and not ctx.owner_authenticated:
        return cap.needs_sign_in(ctx, p.intent)
    match p.intent:
        case Intent.EVALUATE_OFFER:
            return evaluate_offer(ctx, slots)
        case Intent.NEGOTIATE:
            _constrain(ctx, slots)
            return _negotiation_proposal(ctx, negotiate_intent(ctx, slots, execute=False))  # never from free text
        case Intent.ACCELERATE_RECEIPT:
            return accelerate(ctx, slots, text)
        case Intent.FUND_GAP:
            return fund_gap(ctx, slots, execute=slots.execute_now and not llm and not p.tentative)
        case Intent.REPAY_FACILITY:
            return repay(ctx, slots, execute=slots.execute_now and not llm)
        case Intent.SHOW_STATUS:
            return status(ctx)
        case Intent.RECORD_FACT:
            return cap.record_fact(ctx, slots)
        case Intent.SHOW_ALERTS:
            return alerts_intent(ctx)
        case Intent.COMPARE_FINANCING:
            return cap.compare_financing(ctx)
        case Intent.RECONCILE:
            return cap.reconcile_receipts(ctx)
        case Intent.SHOW_RATIOS:
            return cap.show_ratios(ctx)
        case Intent.CAPEX:
            return cap.capex_intent(ctx, slots)
        case Intent.BORROWER_FILE:
            return cap.borrower_file(ctx, slots, text)
        case Intent.SHOW_DEAL:
            return cap.show_deal(ctx, slots)
        case Intent.EXPLAIN:
            return explain(ctx, slots, text)
        case Intent.WHAT_IF:
            return what_if(ctx, slots, text)
        case Intent.APPROVE | Intent.REJECT:
            return _decide_approval(ctx, slots, p.intent == Intent.APPROVE, text, bare="bare_confirm" in p.matched)
        case Intent.AMBIGUOUS:
            return ask(Intent.AMBIGUOUS, "intent", t(ctx, "What would you like me to do?", "您希望我做什么？"),
                       [("1", t(ctx, "show cash status", "查看现金状况"), Intent.SHOW_STATUS.value),
                        ("2", t(ctx, "fund the projected gap", "为资金缺口融资"), Intent.FUND_GAP.value),
                        ("3", t(ctx, "get an invoice paid early", "提前收款"), Intent.ACCELERATE_RECEIPT.value)],
                       slots)
        case _:
            return _out_of_scope(ctx, slots, text)


MAX_COMMAND_CHARS = 80
_PASTE_MARKS = re.compile(r"^\s*>|[:：]\s*\S|\b(forward(ed)?|attach(ed|ment)?|document|paste[d]?|wrote|writes|says?|said|sent|from)\b"
                          r"|转发|附件|粘贴|来自|发来|说[:：]?", re.IGNORECASE)


def _direct_command(ctx: NlContext, text: str) -> bool:
    """An approval, a decline or a "go ahead" counts only as the owner's own short instruction: one line, at most
    MAX_COMMAND_CHARS, naming no counterparty and carrying no mark of forwarded, attached or pasted content.
    Anything longer may hold someone else's words, however it is formatted, so it decides nothing (fail closed)."""
    body = text.strip()
    if "\n" in body or len(body) > MAX_COMMAND_CHARS or _PASTE_MARKS.search(body):
        return False
    return not lx.find_counterparty(body, ctx.state())


def _not_a_direct_command(ctx: NlContext, p: Parsed) -> Turn:
    ctx.new_event(SecurityEventKind.INJECTION, "OWNER",
                  "quoted text contained an approval instruction; ignored (it sat inside a longer or forwarded message)",
                  action="ignored; nothing approved or executed")
    aid = p.slots.approval_id
    how = (f"approve {aid}" if aid else "go ahead") if p.intent == Intent.APPROVE else (f"reject {aid}" if aid else "cancel")
    return Turn(intent=Intent.AMBIGUOUS, awaiting=ctx.session.pending_plan is not None, reply=t(
        ctx, "That message holds more than a short instruction from you, so I have not approved or run anything. "
             f"If you mean it, reply with just: {how}",
        f"这条消息不只是您本人的简短指令，因此我没有批准或执行任何操作。如确有此意，请只回复：{how}"))


def _consent_turn(ctx: NlContext, p: Parsed, why: str, text: str = "") -> Turn:
    """A financial instruction or an approval that is not in the closed consent grammar (app/nl/consent.py). It
    runs nothing: a negation clears the plan; an unreadable amount, a condition or a later time is answered; an
    approval that is not a plain approve or reject is clarified. No operation is sent, whatever the caller."""
    if why == "negated":
        return Turn(intent=p.intent, clear_pending=True, reply=t(
            ctx, "Understood. I have not done anything, and no plan is waiting for your go-ahead.",
            "明白，我没有执行任何操作，也没有待确认的方案。"))
    if why == "bad_amount":
        return Turn(intent=p.intent, reply=t(
            ctx, "I could not read exactly one amount in RMB (at most two decimals, for example ¥ or 元 or 万) in that, so "
                 "I have not done anything and nothing is waiting for a go-ahead. Please say it again with one RMB amount.",
            "我无法从中读出唯一的人民币金额（最多两位小数，例如带 ¥、元或万），因此没有执行任何操作，也没有待确认的方案。"
            "请用一个人民币金额重新说明。"))
    if why == "deferred":
        return Turn(intent=p.intent, reply=t(
            ctx, "I only act on an instruction that is unconditional and for now, so I have not done anything. "
                 "When you want it, tell me plainly, for example: draw an amount on the credit line.",
            "我只执行无条件、立即生效的明确指令，因此没有执行任何操作。需要时请直接说明，例如：从授信额度提款某金额。"))
    if why == "approval_unclear" and not _direct_command(ctx, text):  # a cue inside a longer, forwarded or pasted message
        return _not_a_direct_command(ctx, p.model_copy(update={"intent": Intent.APPROVE}))
    return Turn(intent=Intent.AMBIGUOUS, reply=t(
        ctx, "I have not approved or declined anything. To decide an approval, say exactly 'approve' or 'reject' "
             "followed by its id (for example: approve APR-nnnnnn).",
        "我没有批准或驳回任何事项。要处理审批，请只说“批准”或“拒绝”加审批编号（例如：批准 APR-nnnnnn）。"))


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
    if new.zero_forward:
        update["zero_forward"] = True
    for k in ("counterparty_id", "amount_fen", "buyer_profile", "facility_id"):
        if getattr(new, k) is not None:
            update[k] = getattr(new, k)
    slots = pending.slots.model_copy(update=update)
    if pending.intent == Intent.NEGOTIATE:
        _constrain(ctx, slots)
    if pending.intent == Intent.ACCELERATE_RECEIPT:
        # a bare constraint carries no request of its own: the plan is built again from the owner's original words
        again = pending.data.get("text") or text if "constraint" in p.matched else text
        turn = accelerate(ctx, slots, again, amended=True)
    elif pending.intent == Intent.FUND_GAP:
        turn = fund_gap(ctx, slots, execute=False)
    elif pending.intent == Intent.REPAY_FACILITY:
        turn = repay(ctx, slots, execute=False)
    elif pending.intent == Intent.NEGOTIATE:
        turn = _negotiation_proposal(ctx, negotiate_intent(ctx, slots, execute=False, data=pending.data))
    else:
        turn = Turn(intent=pending.intent, reply=t(ctx, "That plan can't be amended; say 'cancel' or 'go ahead'.",
                                                   "该方案无法修改；请回复“取消”或“执行”。"), plan=pending.steps,
                    awaiting=True)
    if turn.pending is not None:
        turn.amended = True
    return turn


def _confirm(ctx: NlContext, yes: bool, text: str) -> Turn:
    """A direct "go ahead" on the pending plan sends the operations that were shown (app/nl/plans.py): it never
    re-plans the goal. A void or no-longer-affordable plan runs nothing and is proposed again."""
    pending = ctx.session.pending_plan
    assert pending is not None
    if not yes:
        steps = [s.model_copy(update={"status": "SKIPPED"}) for s in pending.steps]
        return Turn(intent=Intent.REJECT, reply=t(ctx, "Cancelled. Nothing was executed.", "已取消，未执行任何操作。"),
                    plan=steps, clear_pending=True)
    if pending.intent == Intent.NEGOTIATE and isinstance(ctx, _TurnContext):
        ctx.zero_forward = bool(pending.data.get("zero_forward"))  # the constraint the counters were shown under
    fresh: list[Turn] = []  # the fresh proposal, built once if the gate needs it

    def rebuild() -> Turn:
        if not fresh:
            fresh.append(_rebuild(ctx, pending))
        return fresh[0]

    def accel_check() -> str | None:
        why, turn = reprice_accelerate(ctx, pending)
        if turn is not None:
            fresh.append(turn)
        return why

    check: Callable[[], str | None]
    send: Callable[[], Turn]
    match pending.intent:
        case Intent.SHOW_ALERTS:
            return _closed(confirm_cure(ctx, pending))  # it gates itself: it needs the alert recomputed
        case Intent.ACCELERATE_RECEIPT:
            check = accel_check
            send = (lambda: _send(ctx, pending)) if pending.slots.use_financing else (lambda: run_accelerate(ctx, pending))
        case Intent.FUND_GAP:
            check, send = (lambda: reprice_fund_gap(ctx, pending)), (lambda: _send(ctx, pending))
        case Intent.REPAY_FACILITY:
            check, send = (lambda: reprice_repay(ctx, pending)), (lambda: _send(ctx, pending))
        case Intent.NEGOTIATE:
            check = lambda: _reprice_negotiation(ctx, pending)
            send = lambda: negotiate_intent(
                ctx, pending.slots.model_copy(update={"fixture_id": None, "quoted_text": None, "execute_now": True}),
                execute=True, data=pending.data)
        case Intent.EVALUATE_OFFER:
            check = lambda: _reprice_decision(ctx, pending)
            send = lambda: execute_decision(ctx, pending.data["verdict_id"])
        case _:
            return _closed(Turn(intent=pending.intent, reply=t(ctx, "Nothing to run.", "没有可执行的内容。")))
    return _closed(_gate(ctx, pending, rebuild, check) or send())


def _constrain(ctx: NlContext, slots: Slots) -> None:
    """"Don't give anything away" constrains the counters of a negotiation (zero forward concessions); it does not
    cancel it. The constraint is part of the plan, so a confirmation applies it again."""
    if isinstance(ctx, _TurnContext):
        ctx.zero_forward = slots.zero_forward


def _closed(turn: Turn) -> Turn:
    turn.clear_pending = True  # a fresh proposal on the turn replaces the plan; otherwise nothing stays pending
    return turn


def _send(ctx: NlContext, pending: Any) -> Turn:
    if not pending.ops:
        return Turn(intent=pending.intent, clear_pending=True, reply=t(
            ctx, "There is nothing in that plan to send.", "该方案中没有需要发送的操作。"))
    return plans.send(ctx, pending.intent, pending.ops, pending.quoted_cost_fen)


def _gate(ctx: NlContext, pending: Any, rebuild: Callable[[], Turn], reprice: Callable[[], str | None]) -> Turn | None:
    """None: the stored plan may be sent. Otherwise nothing runs: the reply says what changed and shows the plan as it
    stands on today's books, which needs its own go-ahead. The day or the mandate version moved: the plan is void.
    Only the state moved: the same operations are re-priced and stand when still feasible at no more than the quote."""
    why = plans.stale(ctx, pending)
    if why is None and plans.books_moved(ctx, pending):
        why = reprice()
    if why is None:
        return None
    turn = rebuild()
    turn.reply = plans.void_notice(ctx, why) + " " + turn.reply
    return turn


def _rebuild(ctx: NlContext, pending: Any) -> Turn:
    """The proposal for the same request on today's books (nothing executes)."""
    match pending.intent:
        case Intent.FUND_GAP:
            return fund_gap(ctx, pending.slots, execute=False)
        case Intent.REPAY_FACILITY:
            return repay(ctx, pending.slots, execute=False)
        case Intent.ACCELERATE_RECEIPT:
            return accelerate(ctx, pending.slots, pending.data.get("text", ""))
        case Intent.NEGOTIATE:
            return _negotiation_proposal(ctx, negotiate_intent(ctx, pending.slots, execute=False, data=pending.data))
        case Intent.EVALUATE_OFFER:
            return evaluate_offer(ctx, pending.slots)
        case _:
            return Turn(intent=pending.intent, reply=t(ctx, "Nothing to propose.", "没有可提出的方案。"))


def _reprice_negotiation(ctx: NlContext, pending: Any) -> str | None:
    """None when the offer, on today's books, still draws exactly the counters that were shown, each at no more cost."""
    old = ctx.store.get_verdict(pending.data["verdict_id"])
    offer = ctx.store.get_offer(old.offer_id) if old is not None else None
    if old is None or offer is None:
        return t(ctx, "that offer is no longer on record", "该报价已不在记录中")
    now = ctx.evaluate(offer, remember=False).verdict
    if _followups(ctx, old.id) != pending.data.get("followups"):  # what runs after the sends: the fallback, the remaining gap
        return t(ctx, "the books changed and what would follow the counters is no longer what I showed",
                 "账目已变化，发送反报价之后的后续操作已不再是我之前给出的内容")

    def cost(c: Any) -> int:
        return c.supplier_cost_fen + c.forward_value_fen

    if (len(now.counters) == len(old.counters)
            and all((a.label, a.text) == (b.label, b.text) and cost(a) <= cost(b)
                    for a, b in zip(now.counters, old.counters, strict=True))):
        return None
    return t(ctx, "the books changed and the counters I showed are no longer what I would send",
             "账目已变化，我之前给出的反报价已不再是我会发送的内容")


def _followups(ctx: NlContext, verdict_id: str | None) -> dict[str, Any]:
    """The funding that runs after a negotiation: the router's plan if the buyer refuses, and for each counter the
    plan for the rest of the gap if it is accepted. Signatures only; they are compared when the books have moved."""
    v = ctx.store.get_verdict(verdict_id) if verdict_id else None
    offer = ctx.store.get_offer(v.offer_id) if v is not None else None
    if v is None or offer is None:
        return {}
    out: dict[str, Any] = {"refuse": plans.plan_signature(committed_plan(ctx.evaluate(
        status_quo_offer(ctx, ctx.state()), remember=False)))}
    for c in v.counters:
        out[f"accept:{c.label}"] = plans.plan_signature(
            committed_plan(ctx.evaluate_accepted(package_offer(ctx, offer, c))))
    return out


def _reprice_decision(ctx: NlContext, pending: Any) -> str | None:
    """None when the offer, on today's books, still gets the verdict that was shown."""
    old = ctx.store.get_verdict(pending.data["verdict_id"])
    offer = ctx.store.get_offer(old.offer_id) if old is not None else None
    if old is None or offer is None:
        return t(ctx, "that offer is no longer on record", "该报价已不在记录中")
    if ctx.evaluate(offer, remember=False).verdict.outcome != old.outcome:
        return t(ctx, "the books changed and the verdict on that offer is no longer the one I showed",
                 "账目已变化，该报价的结论已不再是我之前给出的结论")
    return None


def _negotiation_proposal(ctx: NlContext, turn: Turn) -> Turn:
    """A negotiation is proposed, never started from free text: say which counters would go to whom."""
    v = turn.verdict
    if turn.pending is None or v is None or not v.counters:
        return turn
    offer = ctx.store.get_offer(v.offer_id)
    who = offer.counterparty_id if offer is not None else t(ctx, "the buyer", "买方")
    listed = "; ".join(f"{c.label}: {c.text}" for c in v.counters)
    follow = followup_text(ctx, turn.pending.data)  # the funding that would follow, with the day its cash lands
    follow = (" " + follow) if follow else ""
    turn.reply = t(ctx, f"I would send {len(v.counters)} counter(s) to {who}: {listed}{follow} Nothing has been sent. "
                        f"Reply 'go ahead' to send them, or 'cancel'.",
                   f"我会向 {who} 发送 {len(v.counters)} 条反报价：{listed}{follow} 目前尚未发送任何内容。回复“执行”发送，或“取消”。")
    return turn


def _pending_approvals(ctx: NlContext) -> list[Any]:
    return [a for a in ctx.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"]


def _remember_shown(ctx: NlContext, turn: Turn) -> None:
    """The queue items this turn showed the owner (named in the reply or the clarification): the only ones the
    next bare "approve it" / "yes" / 好的办吧 may decide."""
    pending = {a.id for a in _pending_approvals(ctx)}
    text = turn.reply + " " + " ".join(o.label for o in (turn.clarification.options if turn.clarification else []))
    ctx.session.shown_approvals = [a for a in dict.fromkeys(x.upper() for x in lx.APPROVAL_ID_RE.findall(text)) if a in pending]


def _decide_approval(ctx: NlContext, slots: Slots, approve: bool, text: str = "", *, bare: bool = False) -> Turn:
    """Owner decision on a queued Tier-2 operation. Without the owner token the request is the AGENT's,
    and the executor refuses it (logged as PRIVILEGE_ESCALATION).

    An utterance that does not name the item ("approve it", "yes do it", 好的办吧) decides only the one item this
    session has just shown; it never reaches into the queue on its own. Otherwise the owner is asked which one,
    which shows the queue."""
    from app.persistence import ApprovalAlreadyDecided, NotFound

    pending = _pending_approvals(ctx)
    aid = slots.approval_id
    intent = Intent.APPROVE if approve else Intent.REJECT
    if aid is None:
        shown = [a for a in ctx.session.shown_approvals if a in {p.id for p in pending}]
        if len(shown) == 1:
            aid = shown[0]
        elif not pending:
            if bare:
                return ask(Intent.AMBIGUOUS, "intent", t(ctx, "What should I go ahead with? Nothing in this conversation "
                                                              "is waiting for a yes.", "请问要执行什么？本次对话中没有待确认的事项。"),
                           [("1", t(ctx, "show cash status", "查看现金状况"), Intent.SHOW_STATUS.value),
                            ("2", t(ctx, "fund the projected gap", "为资金缺口融资"), Intent.FUND_GAP.value),
                            ("3", t(ctx, "get an invoice paid early", "提前收款"), Intent.ACCELERATE_RECEIPT.value)],
                           slots)
            return Turn(intent=intent, reply=t(ctx, "Nothing is waiting for approval.", "目前没有待审批的操作。"))
        elif len(pending) == 1 and lx.APPROVAL_REF.search(text) and not bare:
            aid = pending[0].id  # "approve the pending one": the owner names the queue, which holds one item
        else:
            q = (t(ctx, "Nothing in this conversation is waiting for a yes. Which pending operation do you mean?",
                   "本次对话中没有待确认的事项。您指的是哪一项待审批操作？") if bare and not shown
                 else t(ctx, "Which pending operation?", "哪一项待审批操作？"))
            return ask(intent, "approval_id", q, [(str(i), f"{a.id}: {a.reason}", a.id) for i, a in enumerate(pending, 1)],
                       slots)
    actor = Actor.OWNER if ctx.owner_authenticated else Actor.AGENT
    steps = Steps()
    rec = ctx.store.get_approval(aid)
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
        funded = approve and rec is not None and r.status == OperationStatus.EXECUTED  # a funding leg: when its cash lands
        if funded and (note := landing.executor_note(ctx, parse_operation(rec.op_json), r.message)):  # type: ignore[union-attr]
            reply += f" ({note})"
        rest = [a for a in _pending_approvals(ctx) if a.id != aid]
        if rest:
            reply += t(ctx, " Still waiting for your decision: ", " 仍待您审批：") + "; ".join(f"{a.id} ({a.reason})" for a in rest)
    return Turn(intent=intent, reply=reply, plan=steps.items)


TIER3_OPS = {"SIGN_PERSONAL_GUARANTEE": SignPersonalGuarantee, "PLEDGE_COLLATERAL": PledgeCollateral,
             "ISSUE_EQUITY": IssueEquity, "CHANGE_MANDATE": ChangeMandate}


def _out_of_scope(ctx: NlContext, slots: Slots, text: str = "") -> Turn:
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
    return cap.nearest_reply(ctx, text, CAPABILITIES_EN, CAPABILITIES_ZH)


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


def scrub_approval_ids(reply: str) -> str:
    return APPROVAL_ID.sub("the owner's approval", reply)


def _response(ctx: NlContext, turn: Turn, parse_source: str, before: set[str],
              replayed: bool = False) -> NlResponse:
    events = list(ctx.events) + [e.id for e in ctx.store.security_events()
                                 if e.id not in before and e.id not in ctx.events]
    if ctx.session.actor == "COUNTERPARTY":
        # The counterparty channel returns the (already guarded) reply and nothing else: the verdict, plan and
        # operations carry the owner's floor, caps and rates. The turn itself ran and was logged as usual.
        return NlResponse(
            session_id=ctx.session.id, turn=ctx.session.turn, reply=scrub_approval_ids(turn.reply),
            intent=Intent.COUNTERPARTY_MESSAGE, lang=ctx.lang,  # type: ignore[arg-type]
            parse_source="actor", trace_id=ctx.trace_id)
    verdict = turn.verdict.model_dump(mode="json") if turn.verdict is not None else None
    if verdict is not None and isinstance(ctx, _TurnContext) and ctx.extras and turn.verdict.id in ctx.seen:
        verdict.update(ctx.extras(*ctx.seen[turn.verdict.id]))  # owner channel only: the branch above returns first
    return NlResponse(
        session_id=ctx.session.id, turn=ctx.session.turn, reply=turn.reply, intent=turn.intent,
        lang=ctx.lang,  # type: ignore[arg-type]
        plan=turn.plan, verdict=verdict,
        operations=[r.model_dump(mode="json") for r in ctx.results], clarification=turn.clarification,
        awaiting_confirmation=turn.awaiting, amended=turn.amended, replayed=replayed, negotiation=turn.negotiation,
        security_events=events, parse_source=parse_source, trace_id=ctx.trace_id)
