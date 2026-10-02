"""Offer intents: EVALUATE_OFFER, NEGOTIATE, COUNTERPARTY_MESSAGE, EXPLAIN and WHAT_IF.

A buyer's words only ever reach the compiler as a document; the verifier reads the compiled typed
obligations; operations are built from the stored verdict. A counterparty's text is never parsed for
intents: whatever it says, it is an inbound offer to compile and verify (INVARIANTS 1 and 2).
"""

from __future__ import annotations

from contextvars import ContextVar

from app.compiler import compile_offer, compile_term_sheet
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    SecurityEventKind,
    SourceDocument,
    Verdict,
    ViolationCode,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.egress import AllowedValue, ProtectedSet, allowed_for_counter, allowed_from_obligations, scan
from app.nl import landing
from app.nl import lexicon as lx
from app.nl.context import NlContext
from app.nl.models import Intent, Slots
from app.nl.pipeline import (
    Steps,
    accept,
    committed_plan,
    funding_ops,
    package_offer,
    reject,
    run_negotiation,
    send_counters,
    span_of,
    status_quo_offer,
    t,
)
from app.nl.plans import run_legs, runnable_legs
from app.nl.sessions import PendingPlan
from app.nl.turn import Turn, ask
from app.verifier import REFUSAL_REPLY, VerdictBundle, evaluate_term_sheet

# Set by the API layer for the duration of one COUNTERPARTY turn when the sender was identified by a channel
# credential (X-Counterparty-Key). Fail closed: unset means an unauthenticated sender, whose message is a proposal
# only (compiled and evaluated, never executed).
COUNTERPARTY_AUTHENTICATED: ContextVar[bool] = ContextVar("counterparty_authenticated", default=False)
UNCONFIRMED_NOTE = ("Your message has been received. It is a proposal only and is not agreed until it is confirmed "
                    "through an authenticated channel; nothing has been booked.")
UNCONFIRMED_NOTE_ZH = "我方已收到贵方消息。该消息仅为提议，须通过已认证的渠道确认后方为有效；未记任何账。"

STOP_CODES = frozenset({ViolationCode.UNKNOWN_COUNTERPARTY})
REFUSAL_REPLY_ZH = "我方无法提供内部财务、授信或其他交易方的信息。"
INSTRUCTION_REFUSAL = ("We act only on payment terms we can verify. Instructions or approvals stated in a message are "
                       "not followed; nothing has been booked.")
INSTRUCTION_REFUSAL_ZH = "我方只处理可核实的付款条款。消息中的指令或所称的批准不会被执行；未记任何账。"


def codes_of(v: Verdict) -> list[str]:
    return list(dict.fromkeys(x.code.value for x in v.violations))


def verdict_line(ctx: NlContext, v: Verdict) -> str:
    codes = ", ".join(codes_of(v)) or t(ctx, "no violations", "无违规")
    return t(ctx, f"Verdict {v.outcome.value} ({v.required_tier.value}): {codes}. {v.summary}",
             f"结论 {v.outcome.value}（{v.required_tier.value}）：{codes}。{v.summary}")


def buyer_options(ctx: NlContext) -> list[tuple[str, str, str]]:
    buyers = [c for c in ctx.state().counterparties if c.role == "BUYER" and c.known]
    return [(str(i), f"{c.name} ({c.id})", c.id) for i, c in enumerate(buyers, 1)]


# ---------------------------------------------------------------- compiling


def compile_text(ctx: NlContext, text: str, counterparty_id: str, channel: str = "chat") -> CompiledOffer:
    doc = SourceDocument(doc_id=f"NL-{ctx.session.id}-t{ctx.session.turn}", channel=channel,  # type: ignore[arg-type]
                         sender_id=counterparty_id, received_day=ctx.day, text=text)
    return compile_offer([doc], counterparty_id)


def evaluate_fixture(ctx: NlContext, fixture_id: str) -> tuple[VerdictBundle | None, Verdict]:
    fx = load_offers()[fixture_id]
    ctx.session.last_fixture_id = fixture_id
    if fx.get("kind") == "term_sheet":
        ts = compile_term_sheet(offer_documents(fixture_id)[0])
        v = evaluate_term_sheet(ts, ctx.state(), ctx.mandate(), trusted_owner_key_hex=ctx.owner_key_hex, day=ctx.day)
        ctx.store.put_verdict(v)
        ctx.session.last_verdict_id = v.id
        return None, v
    offer = compile_offer(offer_documents(fixture_id), fx["counterparty_id"])
    ctx.session.offer_fixtures[offer.offer_id] = fixture_id
    b = ctx.evaluate(offer)
    return b, b.verdict


def log_authority_claims(ctx: NlContext, offer: CompiledOffer) -> None:
    for claim in offer.authority_claims:
        ctx.new_event(SecurityEventKind.INJECTION, offer.counterparty_id,
                      f"{claim.kind} in message {offer.offer_id}: treated as data; no instruction followed",
                      spans=[claim.span])


# ---------------------------------------------------------------- the verdict -> operations decision


def clarification_request(ctx: NlContext, v: Verdict) -> str:
    """One specific question for a NO_VERDICT, from the typed violation fields only (a fixed template: no
    value from the message is echoed back)."""
    what = " ".join([x.observed or "" for x in v.violations] + [k for x in v.violations for k in x.inputs])
    if any(x.code == ViolationCode.CONFLICTING_SOURCES for x in v.violations):
        return t(ctx, "Your message and the attached document state different values. Please confirm which one is "
                      "correct.", "贵方消息与附件中的数值不一致，请确认以哪一个为准。")
    if "alternatives" in what:
        return t(ctx, "Your message offers more than one value for a term. Please confirm the single value you propose.",
                 "贵方消息中同一条款给出了多个数值，请确认贵方提议的具体数值。")
    if "scope" in what or "base" in what or "receivable_id" in what:
        return t(ctx, "Please confirm what the discount or rebate applies to: which invoice, or which period's "
                      "purchases, and for how long.", "请确认该折扣或返利适用于哪张发票或哪一期的采购，以及适用多长时间。")
    return t(ctx, "Please clarify the terms: we cannot establish them from your message.",
             "请澄清条款：我方无法从贵方消息中确定这些条款。")


def acceptance_allow(b: VerdictBundle) -> list[AllowedValue]:
    """What the acceptance reply may repeat: the buyer's own offered rates, amounts and day counts."""
    out = allowed_from_obligations(b.bound_obligations)
    out += [AllowedValue.days(abs(o.days_delta)) for o in b.bound_obligations if o.days_delta]
    return out


def _restated(ctx: NlContext, o: Obligation) -> str:
    """One bound obligation in words, from its typed fields only (never the buyer's text)."""
    pct = fmt_pct(bp(o.rate_bp)) if o.rate_bp is not None else None
    if o.type == ObligationType.IMMEDIATE_DISCOUNT:
        what = o.base.receivable_id or t(ctx, "the invoice", "该发票")
        face = f" ({fmt_yuan(o.base.amount_fen)})" if o.base.amount_fen is not None else ""
        day = t(ctx, f" on day {o.effective_day}", f"于第{o.effective_day}天") if o.effective_day is not None else ""
        rate = t(ctx, f" at a {pct} discount", f"，折扣{pct}") if pct else ""
        return t(ctx, f"payment of invoice {what}{face}{day}{rate}", f"发票 {what}{face}{day}付款{rate}")
    if o.type == ObligationType.TERMS_EXTENSION and o.days_delta is not None:
        return t(ctx, f"a payment-terms change of {o.days_delta:+d} days", f"付款账期变更{o.days_delta:+d}天")
    if o.type == ObligationType.CONTINGENT_REBATE and pct:
        return t(ctx, f"a {pct} rebate", f"{pct}返利")
    kind = o.type.value.lower().replace("_", " ")
    return t(ctx, f"a {kind}" + (f" at {pct}" if pct else ""), f"{kind}" + (f"，{pct}" if pct else ""))


def acceptance_line(ctx: NlContext, b: VerdictBundle, recipient: str) -> str:
    """The reply to an executed acceptance: the typed terms we agreed, and that nothing else is. If the egress guard
    would block that restatement, a fixed sentence without values."""
    fallback = t(ctx, "Agreed on the terms we confirmed in writing; nothing else in your message is agreed.",
                 "同意我方书面确认的条款；贵方消息中的其他内容均未同意。")
    if not b.bound_obligations:
        return fallback
    terms = t(ctx, "; ", "；").join(_restated(ctx, o) for o in b.bound_obligations)
    text = t(ctx, f"Agreed: {terms}. Nothing else in your message is agreed.", f"同意：{terms}。贵方消息中的其他内容均未同意。")
    if scan(text, ProtectedSet.build(ctx.state(), ctx.mandate()), recipient_id=recipient, allow=acceptance_allow(b)):
        return fallback
    return text


def decide(ctx: NlContext, steps: Steps, b: VerdictBundle, *, execute: bool, recipient: str) -> list[str]:
    """Tier-1 response to a verified offer. Returns outbound lines for the counterparty.

    NO_VERDICT, an unknown sender, and a message with nothing bookable produce no operation: they are
    stopped at the verifier and appear in the evidence as security events."""
    v = b.verdict
    codes = {x.code for x in v.violations}
    offer = ctx.store.get_offer(v.offer_id)
    if v.outcome == Outcome.NO_VERDICT and ViolationCode.CONFLICTING_SOURCES in codes:
        steps.add("VERIFY", t(ctx, "No verdict: clarification requested; nothing booked", "无结论：已请求澄清，未记账"), "INFO")
        return [t(ctx, "Please confirm the order amount and terms: the documents you sent disagree.",
                  "请确认订单金额与条款：贵方发送的文件内容不一致。")]
    if (v.outcome == Outcome.NO_VERDICT and not b.bound_obligations and offer is not None
            and (offer.authority_claims or offer.funding_claims)):
        # Instructions or claimed authority with nothing bookable: refused, logged, nothing booked.
        steps.add("VERIFY", t(ctx, "Refused: the message carries instructions or claimed authority and no bookable "
                                   "term; logged as security events, nothing booked, nothing executed",
                              "已拒绝：消息包含指令或声称的授权，且没有可记账条款；已记录安全事件，未记账、未执行"), "INFO")
        return [INSTRUCTION_REFUSAL_ZH if ctx.lang == "zh" else INSTRUCTION_REFUSAL]
    asked = any(x.inputs.get("clarification") == "requested" for x in v.violations)  # the compiler abstained
    if v.outcome == Outcome.NO_VERDICT and ViolationCode.UNRESOLVED_SCOPE in codes and not b.bound_obligations and not asked:
        steps.add("VERIFY", t(ctx, "No bookable terms in the message; nothing booked", "消息中没有可记账的条款；未记账"),
                  "INFO")
        return [t(ctx, "Thank you. We did not find payment terms in your message that we can act on.",
                  "谢谢。贵方消息中没有我方可以处理的付款条款。")]
    if v.outcome == Outcome.NO_VERDICT:
        steps.add("VERIFY", t(ctx, "No verdict: clarification requested; nothing booked", "无结论：已请求澄清，未记账"), "INFO")
        return [clarification_request(ctx, v)]
    if codes & STOP_CODES:
        steps.add("VERIFY", t(ctx, "Stopped at the verifier: sender not on the owner's registry; nothing booked, "
                              "no facility added, nothing disclosed", "在验证器处拦截：发送方不在登记册中；未记账"), "INFO")
        return [REFUSAL_REPLY_ZH if ctx.lang == "zh" else REFUSAL_REPLY]
    if not b.bound_obligations and not v.counters:
        steps.add("VERIFY", t(ctx, "No bookable terms in the message: nothing to accept, counter or book "
                                   "(an empty offer violates nothing, so no operation follows)",
                              "消息中没有可记账的条款"), "INFO")
        if ViolationCode.DATA_EXTRACTION_REFUSED in codes:
            return [REFUSAL_REPLY_ZH if ctx.lang == "zh" else REFUSAL_REPLY]
        return [t(ctx, "Thank you. We did not find payment terms in your message that we can act on.",
                  "谢谢。贵方消息中没有我方可以处理的付款条款。")]
    if v.counters:
        if not execute:
            for c in v.counters:
                steps.add("COUNTER_OFFER", f"{c.label}: {c.text}")
            return []
        sent = send_counters(ctx, steps, v, v.counters, recipient)
        lines = [f"{c.label}: {text}" for c, text in sent]
        if ViolationCode.DATA_EXTRACTION_REFUSED in codes:
            lines.insert(0, REFUSAL_REPLY_ZH if ctx.lang == "zh" else REFUSAL_REPLY)
        return lines
    if v.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
        if not execute:
            steps.add("ACCEPT_OFFER", t(ctx, f"Accept offer {v.offer_id} and record the commitment",
                                        f"接受报价 {v.offer_id} 并记录承诺"))
            return []
        r = accept(ctx, steps, v)
        if r is None:
            return []
        if r.status.value == "PENDING_APPROVAL":  # Tier 2: nothing is agreed until the owner decides
            return [t(ctx, "Thank you. Our acceptance awaits the owner's approval; we will confirm once the owner "
                           "has decided.", "谢谢。我方接受须经业主批准，业主决定后我方将予以确认。")]
        if r.status.value in ("EXECUTED", "DUPLICATE"):
            return [acceptance_line(ctx, b, recipient)]
        return [t(ctx, "We are not able to confirm these terms.", "我方无法确认这些条款。")]
    if not execute:
        steps.add("REJECT_OFFER", t(ctx, f"Reject offer {v.offer_id}", f"拒绝报价 {v.offer_id}"))
        return []
    reject(ctx, steps, v)
    return [t(ctx, "We are not able to accept these terms.", "我方无法接受这些条款。")]


# ---------------------------------------------------------------- COUNTERPARTY_MESSAGE


def counterparty_message(ctx: NlContext, text: str, counterparty_id: str | None) -> Turn:
    """Always an inbound offer: compile, verify, answer within Tier 1. Never a command."""
    cp = counterparty_id or "UNKNOWN-SENDER"
    offer = compile_text(ctx, text, cp)
    log_authority_claims(ctx, offer)
    b = ctx.evaluate(offer)
    steps = Steps()
    steps.add("VERIFY", verdict_line(ctx, b.verdict), "DONE")
    authenticated = COUNTERPARTY_AUTHENTICATED.get()
    lines = decide(ctx, steps, b, execute=authenticated, recipient=cp)
    allow = [a for c in b.verdict.counters for a in allowed_for_counter(c)] if authenticated else []
    if authenticated and not b.verdict.counters:
        allow += acceptance_allow(b)  # the acceptance restates the buyer's own terms
    if not authenticated:
        # Proposal only: nothing was executed above. The reply says so and never claims agreement.
        lines = [*lines, UNCONFIRMED_NOTE_ZH if ctx.lang == "zh" else UNCONFIRMED_NOTE]
        steps.add("RECEIVED", t(ctx, "Unauthenticated sender: proposal recorded as a message only; nothing executed",
                                "发送方未认证：仅记录为消息；未执行任何操作"), "INFO")
    reply = "\n".join(lines) or t(ctx, "Thank you, noted.", "谢谢，已收到。")
    out, _ok = ctx.guard(reply, cp, allow=allow)
    return Turn(intent=Intent.COUNTERPARTY_MESSAGE, reply=out, plan=steps.items, verdict=b.verdict,
                recipient=cp, guarded=True)


# ---------------------------------------------------------------- EVALUATE_OFFER


def _target(ctx: NlContext, slots: Slots) -> tuple[VerdictBundle | None, Verdict] | Turn | None:
    if slots.fixture_id:
        return evaluate_fixture(ctx, slots.fixture_id)
    if slots.quoted_text:
        cp = slots.counterparty_id or ctx.session.counterparty_id
        if cp is None:
            hits = lx.find_counterparty(slots.quoted_text, ctx.state())
            cp = hits[0] if len(hits) == 1 else None
        if cp is None:
            return ask(Intent.EVALUATE_OFFER, "counterparty_id",
                       t(ctx, "Which buyer sent this message?", "这条消息是哪位买家发的？"), buyer_options(ctx), slots)
        offer = compile_text(ctx, slots.quoted_text, cp)
        b = ctx.evaluate(offer)
        return b, b.verdict
    return None


def evaluate_offer(ctx: NlContext, slots: Slots, *, execute: bool = False) -> Turn:
    target = _target(ctx, slots)
    if isinstance(target, Turn):
        return target
    if target is None:
        return ask(Intent.EVALUATE_OFFER, "fixture_id",
                   t(ctx, "Which offer should I evaluate? Paste the buyer's message in quotes, or pick one:",
                     "要评估哪条报价？请用引号粘贴买家原文，或选择："),
                   [("1", "EX01 (Foshan package)", "EX01_PACKAGE"), ("2", "EX02 (early pay 1.5%)", "EX02_EARLY_1_5"),
                    ("3", "SEC_DEMO (FastCapital)", "SEC_DEMO_FASTCAPITAL")], slots)
    b, v = target
    steps = Steps()
    steps.add("VERIFY", verdict_line(ctx, v), "DONE")
    if b is None:  # a term sheet: the owner decides; Tier-3 clauses are never accepted
        return Turn(intent=Intent.EVALUATE_OFFER, reply=verdict_line(ctx, v), plan=steps.items, verdict=v)
    offer = ctx.store.get_offer(v.offer_id)
    decide(ctx, steps, b, execute=execute, recipient=offer.counterparty_id if offer else "UNKNOWN")
    reply = [verdict_line(ctx, v)]
    proposed = [s for s in steps.items if s.status == "PROPOSED"]
    pending = None
    if proposed:
        if v.counters:
            steps.add("NEGOTIATE", t(ctx, "Bounded rounds with the buyer (max 3)", "与买方有限轮次谈判（最多 3 轮）"))
            follow = followups(ctx, steps, offer, v.counters) if offer is not None else {}
            pending = PendingPlan(intent=Intent.NEGOTIATE, slots=slots, steps=steps.items,
                                  data={"verdict_id": v.id, **follow})
            if follow_text := followup_text(ctx, follow):
                reply.append(follow_text)
            reply.append(t(ctx, "Reply 'go ahead' to negotiate: I will then send the counters. Nothing is sent before that.",
                           "回复“执行”开始谈判，届时我才会发送反报价；在此之前不会发送任何内容。"))
        else:
            pending = PendingPlan(intent=Intent.EVALUATE_OFFER, slots=slots, steps=steps.items,
                                  data={"verdict_id": v.id})
            reply.append(t(ctx, "Reply 'go ahead' to execute this, or 'cancel'.", "回复“执行”以执行，或“取消”。"))
    return Turn(intent=Intent.EVALUATE_OFFER, reply="\n".join(reply), plan=steps.items, verdict=v,
                awaiting=pending is not None, pending=pending)


def followups(ctx: NlContext, steps: Steps, offer: CompiledOffer, counters: list) -> dict:
    """The funding that may follow a negotiation, built now so that the owner sees it and a go-ahead sends exactly
    these legs (app/nl/plans.py): the router's plan if the buyer refuses, and for each counter the plan for the rest
    of the gap if the buyer accepts it. Returns what is stored with the plan; the legs are shown as plan steps."""
    fallback = committed_plan(ctx.evaluate(status_quo_offer(ctx, ctx.state()), remember=False))
    out: dict = {"refuse_ops": [], "refuse_label": None, "refuse_note": "", "accept_ops": {}, "accept_labels": {},
                 "accept_notes": {}}
    if fallback is not None:
        out["refuse_ops"], out["refuse_note"] = runnable_legs(ctx, fallback)
        out["refuse_label"] = fallback.label
        funding_ops(ctx, steps, fallback, condition=t(ctx, "if the buyer refuses (NO DEAL)", "若买方拒绝"),
                    status="PROPOSED" if fallback.executable_now else "SKIPPED")
    for c in counters:
        plan = committed_plan(ctx.evaluate_accepted(package_offer(ctx, offer, c)))
        legs, note = runnable_legs(ctx, plan)
        if plan is not None and (legs or note):
            if legs:
                out["accept_ops"][c.label] = legs
            out["accept_labels"][c.label] = plan.label
            out["accept_notes"][c.label] = note
            funding_ops(ctx, steps, plan, condition=t(ctx, f"if the buyer accepts {c.label}: remaining gap",
                                                      f"若买方接受 {c.label}：剩余缺口"),
                        status="PROPOSED" if plan.executable_now else "SKIPPED")
    return out


def followup_text(ctx: NlContext, follow: dict) -> str:
    """What would follow the counters, in words, with the day each leg's cash lands, and what the router flagged on
    it: a leg above the ceiling waits for the owner, a plan that cannot run today is not stored and says why."""
    parts: list[str] = []
    if follow.get("refuse_ops") or follow.get("refuse_note"):
        when = landing.line(ctx, follow["refuse_ops"], executed=False) if follow.get("refuse_ops") else ""
        parts.append(t(ctx, f"If the buyer refuses: {follow['refuse_label']}. {when}",
                       f"若买方拒绝：{follow['refuse_label']}。{when}").strip()
                     + (" " + follow["refuse_note"] if follow.get("refuse_note") else ""))
    for label, note in follow.get("accept_notes", {}).items():
        legs = follow.get("accept_ops", {}).get(label, [])
        when = landing.line(ctx, legs, executed=False) if legs else ""
        parts.append(t(ctx, f"If the buyer accepts {label}, the rest of the gap: {follow['accept_labels'][label]}. {when}",
                       f"若买方接受 {label}，其余缺口：{follow['accept_labels'][label]}。{when}").strip()
                     + (" " + note if note else ""))
    return " ".join(parts)


def execute_decision(ctx: NlContext, verdict_id: str) -> Turn:
    """The owner confirmed an ACCEPT or REJECT proposed on a stored verdict: re-verify, then act."""
    v = ctx.store.get_verdict(verdict_id)
    offer = ctx.store.get_offer(v.offer_id) if v is not None else None
    if v is None or offer is None:
        return Turn(intent=Intent.EVALUATE_OFFER, reply=t(ctx, "That verdict is no longer on record.", "该结论已不存在。"),
                    clear_pending=True)
    b = ctx.evaluate(offer)  # re-verify against the state and mandate in force now
    steps = Steps()
    steps.add("VERIFY", verdict_line(ctx, b.verdict), "DONE")
    decide(ctx, steps, b, execute=True, recipient=offer.counterparty_id)
    reply = [verdict_line(ctx, b.verdict), *awaiting_owner(ctx)]
    return Turn(intent=Intent.EVALUATE_OFFER, reply="\n".join(reply), plan=steps.items,
                verdict=b.verdict, clear_pending=True)


def awaiting_owner(ctx: NlContext) -> list[str]:
    """Owner-facing lines for every acceptance this turn queued at Tier 2: it is not agreed yet."""
    return [t(ctx, f"The acceptance awaits the owner's approval ({r.approval_id}): nothing is committed until the "
                   f"owner approves it.", f"该接受须经业主批准（{r.approval_id}）：业主批准前不作任何承诺。")
            for r in ctx.results if r.kind == "ACCEPT_OFFER" and r.status.value == "PENDING_APPROVAL"]


# ---------------------------------------------------------------- NEGOTIATE


def negotiate_intent(ctx: NlContext, slots: Slots, *, execute: bool = True, data: dict | None = None) -> Turn:
    v: Verdict | None = None
    if slots.fixture_id or slots.quoted_text:
        target = _target(ctx, slots)
        if isinstance(target, Turn):
            return target
        if target is not None:
            v = target[1]
    if v is None:
        vid = (data or {}).get("verdict_id") or ctx.session.last_verdict_id
        v = ctx.store.get_verdict(vid) if vid else None
    if v is None or not v.counters:
        why = t(ctx, "There are no counters to send. Evaluate an offer first (e.g. 'evaluate EX01').",
                "没有可发送的反报价。请先评估一条报价（例如“评估 EX01”）。")
        return Turn(intent=Intent.NEGOTIATE, reply=why, verdict=v)
    offer = ctx.store.get_offer(v.offer_id)
    if offer is None:
        return Turn(intent=Intent.NEGOTIATE, reply=t(ctx, "The offer is no longer on record.", "该报价已不存在。"))
    b = ctx.evaluate(offer)  # re-verify now: counters are sent only from a fresh verdict
    v = b.verdict
    steps = Steps()
    steps.add("VERIFY", verdict_line(ctx, v), "DONE")
    profile = slots.buyer_profile or ctx.session.buyer_profile or offer.counterparty_id
    if not execute:
        for c in v.counters:
            steps.add("COUNTER_OFFER", f"{c.label}: {c.text}")
        steps.add("NEGOTIATE", t(ctx, "Bounded rounds with the buyer", "与买方有限轮次谈判"))
        follow = followups(ctx, steps, offer, v.counters)
        ready = t(ctx, "Plan ready. Reply 'go ahead' to send the counters.", "计划已就绪。回复“执行”发送反报价。")
        return Turn(intent=Intent.NEGOTIATE, reply=ready, plan=steps.items, verdict=v, awaiting=True,
                    pending=PendingPlan(Intent.NEGOTIATE, slots, steps.items, {"verdict_id": v.id, **follow}))
    # The funding that follows is the one shown with the proposal and stored in it: the legs run through the same
    # runner as every other plan, and nothing is planned again after the owner's go-ahead.
    stored = data or {}
    neg = run_negotiation(ctx, steps, v, v.counters, profile)
    reply = [verdict_line(ctx, v)]
    if neg.accepted is not None:
        r = accept(ctx, steps, v, neg.accepted)
        reply.append(t(ctx, f"The buyer accepted {neg.accepted.label}.", f"买方接受了 {neg.accepted.label}。"))
        reply.extend(awaiting_owner(ctx))
        legs = stored.get("accept_ops", {}).get(neg.accepted.label, [])
        if r is not None and r.status.value in ("EXECUTED", "PENDING_APPROVAL", "DUPLICATE") and legs:
            lines, _ok = run_legs(ctx, steps, legs, t(ctx, "remaining gap after the accepted package", "成交后剩余缺口"))
            reply.append(t(ctx, "The rest of the gap, as I showed it:", "其余缺口，按之前给出的方案："))
            reply.extend(lines)
        elif r is not None and (note := stored.get("accept_notes", {}).get(neg.accepted.label)):
            reply.append(note)  # the rest of the gap has a plan, but not one that can run today
    elif neg.outcome == "NO_DEAL":
        legs = stored.get("refuse_ops", [])
        if legs:
            lines, _ok = run_legs(ctx, steps, legs, t(ctx, "NO DEAL: the router's plan", "未成交：融资路由方案"))
            reply.append(t(ctx, f"NO DEAL. The funding I showed for this case ({stored.get('refuse_label')}):",
                           f"未成交。按之前给出的该情形下的融资方案（{stored.get('refuse_label')}）："))
            reply.extend(lines)
        elif stored.get("refuse_note"):  # a plan exists but cannot run today: nothing was stored for it
            reply.append(t(ctx, "NO DEAL. ", "未成交。") + stored["refuse_note"])
        else:
            reply.append(t(ctx, "NO DEAL, and there is no gap to cover.", "未成交，且无资金缺口。"))
    return Turn(intent=Intent.NEGOTIATE, reply="\n".join(reply), plan=steps.items, verdict=v,
                negotiation=neg.summary, clear_pending=True)


# ---------------------------------------------------------------- EXPLAIN


# Plain definitions for the owner's "what does X mean" questions. Generic wording only: no mandate value, limit
# or other counterparty's term is ever part of a definition.
GLOSSARY: list[tuple[str, str, str]] = [
    (r"break[- ]?even|盈亏平衡|保本",
     "Break-even discount: the largest early-payment discount worth giving. Below it, taking the buyer's money early "
     "costs less than funding the same days from your cheapest committed source; at or above it the agent counters.",
     "盈亏平衡折扣：值得给出的最大提前付款折扣。低于它，提前收款比用最便宜的已承诺资金来源垫付同样天数更省；达到或高于它，代理会还价。"),
    (r"\bapr\b|年化",
     "APR: a discount expressed as a yearly rate, discount / (1 − discount) × 365 / days paid early, so offers with "
     "different timing can be compared.", "年化成本：把折扣换算成年利率，折扣 /（1 − 折扣）× 365 / 提前天数，便于比较不同时间的报价。"),
    (r"forward concession|远期让步",
     "Forward concession: a promise that costs money later (a rebate, longer terms, a price cut), valued over the "
     "mandate's horizon and capped per buyer and in total.", "远期让步：日后才产生成本的承诺（返利、延长账期、降价），按授权期限估值，并有单个买家和总额上限。"),
    (r"\btier\b|层级|级别",
     "Tiers: Tier 1 the agent may do on its own inside the mandate; Tier 2 waits for your approval; Tier 3 (guarantees, "
     "collateral, equity, mandate changes) the agent can never do.", "层级：一级在授权内由代理自行执行；二级须经您批准；三级（担保、抵押、股权、修改授权）代理永远不能执行。"),
    (r"covenant|dscr|leverage|契约|偿债覆盖|杠杆",
     "Covenants: conditions a lender sets, such as DSCR (monthly earnings over scheduled debt service) or leverage "
     "(debt over annualised earnings); every plan is checked against them.", "契约：贷款方设定的条件，例如偿债覆盖率（月度收益/应付本息）或杠杆率（负债/年化收益）；每个方案都会据此检查。"),
    (r"reserve|min(?:imum)? cash|floor|储备|底线|最低现金",
     "Reserve floor: the lowest cash balance the mandate allows on any day; a plan that dips below it is refused.",
     "最低现金储备：授权允许的任何一天的最低现金余额；低于它的方案会被拒绝。"),
    (r"no verdict|abstain|弃权|无结论",
     "No verdict: the message did not establish a term exactly (an amount, a scope, conflicting figures), so nothing is "
     "booked and the buyer is asked to clarify.", "无结论：消息没有准确确定条款（金额、范围或数字冲突），因此不记账，并请买方澄清。"),
    (r"early[- ]?pay|贴息|提前付款|折扣",
     "Early-payment discount: the buyer pays an open invoice before it is due and deducts a percentage of it.",
     "提前付款折扣（贴息）：买方在到期前支付未结发票，并扣除其中一定比例。"),
]


def glossary_reply(ctx: NlContext, text: str) -> str | None:
    import re as _re

    for pat, en, zh in GLOSSARY:
        if _re.search(pat, text, _re.IGNORECASE):
            return t(ctx, en, zh)
    if lx.GLOSSARY.search(text):
        return t(ctx, "I can define: break-even discount, APR, forward concession, tiers, covenants, the reserve floor, "
                      "no verdict and early-payment discount.",
                 "我可以解释：盈亏平衡折扣、年化成本、远期让步、层级、契约、最低现金储备、无结论和提前付款折扣。")
    return None


def explain(ctx: NlContext, slots: Slots, text: str = "") -> Turn:
    if text and lx.GLOSSARY.search(text) and not slots.fixture_id:
        g = glossary_reply(ctx, text)
        if g is not None:
            return Turn(intent=Intent.EXPLAIN, reply=g)
    v = None
    if slots.fixture_id:
        _, v = evaluate_fixture(ctx, slots.fixture_id)
    elif ctx.session.last_verdict_id:
        v = ctx.store.get_verdict(ctx.session.last_verdict_id)
    if v is None:
        return Turn(intent=Intent.EXPLAIN, reply=t(ctx, "There is no verdict to explain yet. Evaluate an offer first.",
                                                   "还没有可解释的结论。请先评估一条报价。"))
    lines = [verdict_line(ctx, v)]
    for x in v.violations:
        inputs = "; ".join(f"{k}={val}" for k, val in list(x.inputs.items())[:5])
        where = f" day {x.day}" if x.day is not None else (f" month {x.month}" if x.month is not None else "")
        cure = f" Curable for {fmt_yuan(x.cure_cost_fen)}." if x.curable and x.cure_cost_fen is not None else ""
        lines.append(f"- {x.code.value}{where}: {x.message}. Observed {x.observed or '-'} vs limit {x.limit or '-'}. "
                     f"Formula: {x.formula or '-'}. Inputs: {inputs or '-'}.{cure}")
    for cv in v.concession_values:
        if cv.value_fen:
            lines.append(f"- Forward value {fmt_yuan(cv.value_fen)} ({cv.basis}): {cv.formula}")
    if v.concession_values or v.forward_concession_total_fen:
        lines.append(t(ctx, f"Forward concessions total {fmt_yuan(v.forward_concession_total_fen)} against the "
                       f"{fmt_yuan(ctx.mandate().max_aggregate_forward_concession_fen)} cap.",
                       f"远期让步合计 {fmt_yuan(v.forward_concession_total_fen)}，上限 "
                       f"{fmt_yuan(ctx.mandate().max_aggregate_forward_concession_fen)}。"))
    for c in v.counters:
        lines.append(f"- {c.label}: {c.rationale} Formula: {c.formula}")
    return Turn(intent=Intent.EXPLAIN, reply="\n".join(lines), verdict=v)


# ---------------------------------------------------------------- WHAT_IF


def what_if(ctx: NlContext, slots: Slots, text: str) -> Turn:
    """A hypothetical terms or discount change, verified on synthetic typed obligations whose spans are
    the owner's own words. Nothing is executed."""
    state = ctx.state()
    cp = slots.counterparty_id or ctx.session.counterparty_id
    if cp is None and ctx.session.last_offer_id:
        last = ctx.store.get_offer(ctx.session.last_offer_id)
        cp = last.counterparty_id if last is not None and last.counterparty_id != "OWNER" else None
    implied = ""
    if cp is None:
        # An early-pay discount needs an open invoice: when exactly one buyer has one, the question names it.
        low = lx.norm(text)
        early_only = (any(w in low for w in ("early", "discount", "提前", "折扣", "贴现")) and not lx.days(text)
                      and not any(w in low for w in ("next quarter", "rebate", "off next", "返利", "下季度", "返点")))
        holders = sorted({x.counterparty_id for x in state.receivables if x.status == "OPEN"})
        if early_only and len(holders) == 1:
            cp = holders[0]
            name = next((c.name for c in state.counterparties if c.id == cp), cp)
            implied = t(ctx, f"For {name} ({cp}), the only buyer with an open invoice. ",
                        f"针对 {name}（{cp}），唯一有未结发票的买家。")
    if cp is None and not _buyer_what_if(text):
        # "what if payroll goes up 10%": not a change to a buyer's terms, so asking which buyer is the wrong question
        return Turn(intent=Intent.WHAT_IF, reply=t(
            ctx, "I can test changes to a buyer's terms: for example '60-day terms for Foshan', 'a 1% early-pay "
                 "discount' or '1% off next quarter'. Cost what-ifs (payroll, rent) aren't supported yet; nothing "
                 "was changed.",
            "我可以测试买家条款的变化，例如“给佛山 60 天账期”“1% 提前付款折扣”“下季度 1% 返利”。成本类假设（工资、房租）"
            "暂不支持；未做任何更改。"))
    if cp is None:
        return ask(Intent.WHAT_IF, "counterparty_id", t(ctx, "Which buyer is this for?", "针对哪位买家？"),
                   buyer_options(ctx), slots)
    doc = owner_doc_for(ctx, text)
    obs: list[Obligation] = []
    lowered = lx.norm(doc.text)
    for i, d in enumerate(lx.days(doc.text)):
        dur = (Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=slots.invoices) if slots.invoices
               else Duration(kind=DurationKind.RECURRING_PERPETUAL))
        obs.append(Obligation(id=f"{doc.doc_id}-T{i}", type=ObligationType.TERMS_EXTENSION, counterparty_id=cp,
                              target_terms_days=d.value, base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
                              contingency=Contingency.FIRM, duration=dur, spans=[span_of(doc, d.start, d.end)],
                              confidence=1.0))
        break
    rebate_cue = any(w in lowered for w in ("next quarter", "rebate", "off next", "返利", "下季度", "返点"))
    early_cue = any(w in lowered for w in ("early", "discount", "提前", "折扣", "贴现"))
    for i, r in enumerate(lx.rates(doc.text)):
        if rebate_cue:
            obs.append(Obligation(id=f"{doc.doc_id}-R{i}", type=ObligationType.CONTINGENT_REBATE, counterparty_id=cp,
                                  rate_bp=r.value, base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES),
                                  contingency=Contingency.CONTINGENT, duration=Duration(kind=DurationKind.ONE_OFF),
                                  spans=[span_of(doc, r.start, r.end)], confidence=1.0))
        elif early_cue:
            rcv = next((x for x in state.receivables if x.counterparty_id == cp and x.status == "OPEN"), None)
            obs.append(Obligation(id=f"{doc.doc_id}-D{i}", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id=cp,
                                  rate_bp=r.value, base=ObligationBase(kind=BaseKind.INVOICE,
                                                                       receivable_id=rcv.id if rcv else None,
                                                                       amount_fen=rcv.face_fen if rcv else None),
                                  contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF),
                                  spans=[span_of(doc, r.start, r.end)], confidence=1.0))
        break
    if not obs:
        return Turn(intent=Intent.WHAT_IF, reply=t(
            ctx, "Which change should I test? For example: '60-day terms for Foshan', 'a 1% early-pay discount', "
                 "or '1% off next quarter'.", "要测试哪种变化？例如“给佛山 60 天账期”“1% 提前付款折扣”“下季度 1% 返利”。"))
    offer = CompiledOffer(offer_id=f"WHATIF-{doc.doc_id}", counterparty_id=cp, doc_ids=[doc.doc_id],
                          received_day=ctx.day, status=CompileStatus.COMPILED, obligations=obs,
                          compiler="nl-what-if", prompt_version="nl-v1")
    b = ctx.evaluate(offer)
    v = b.verdict
    steps = Steps()
    steps.add("VERIFY", verdict_line(ctx, v), "DONE")
    reply = [t(ctx, "What-if (nothing executed): ", "假设分析（未执行任何操作）：") + implied + verdict_line(ctx, v)]
    reply.append(t(ctx, f"Forward concessions {fmt_yuan(v.forward_concession_total_fen)}.",
                   f"远期让步 {fmt_yuan(v.forward_concession_total_fen)}。"))
    return Turn(intent=Intent.WHAT_IF, reply="\n".join(reply), plan=steps.items, verdict=v)


_BUYER_TERMS_WORDS = ("early", "discount", "rebate", "terms", "days", "off next", "next quarter", "buyer", "invoice",
                      "提前", "折扣", "贴现", "返利", "返点", "账期", "天", "下季度", "买家", "发票")


def _buyer_what_if(text: str) -> bool:
    """True when the hypothetical is a change to a buyer's terms (days, a discount or a rebate)."""
    low = lx.norm(text)
    return bool(lx.days(text)) or any(w in low for w in _BUYER_TERMS_WORDS)


def owner_doc_for(ctx: NlContext, text: str) -> SourceDocument:
    return SourceDocument(doc_id=f"NL-{ctx.session.id}-t{ctx.session.turn}", channel="owner", sender_id="OWNER",
                          received_day=ctx.day, text=text)
