"""Offer intents: EVALUATE_OFFER, NEGOTIATE, COUNTERPARTY_MESSAGE, EXPLAIN and WHAT_IF.

A buyer's words only ever reach the compiler as a document; the verifier reads the compiled typed
obligations; operations are built from the stored verdict. A counterparty's text is never parsed for
intents: whatever it says, it is an inbound offer to compile and verify (INVARIANTS 1 and 2).
"""

from __future__ import annotations

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
from app.domain.money import fmt_yuan
from app.egress import allowed_for_counter
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
from app.nl.sessions import PendingPlan
from app.nl.turn import Turn, ask
from app.verifier import REFUSAL_REPLY, VerdictBundle, evaluate_term_sheet

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
            return [t(ctx, "Agreed as proposed.", "同意贵方提议。")]
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
    lines = decide(ctx, steps, b, execute=True, recipient=cp)
    allow = [a for c in b.verdict.counters for a in allowed_for_counter(c)]
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
            fallback = committed_plan(ctx.evaluate(status_quo_offer(ctx, ctx.state()), remember=False))
            steps.add("NEGOTIATE", t(ctx, "Bounded rounds with the buyer (max 3)", "与买方有限轮次谈判（最多 3 轮）"))
            if fallback is not None:
                funding_ops(ctx, steps, fallback, condition=t(ctx, "if the buyer refuses (NO DEAL)", "若买方拒绝"),
                            execute=False)
            pending = PendingPlan(intent=Intent.NEGOTIATE, slots=slots, steps=steps.items,
                                  data={"verdict_id": v.id})
            reply.append(t(ctx, "Reply 'send the counters' (or 'go ahead') to negotiate.",
                           "回复“发送反报价”或“执行”开始谈判。"))
        else:
            pending = PendingPlan(intent=Intent.EVALUATE_OFFER, slots=slots, steps=steps.items,
                                  data={"verdict_id": v.id})
            reply.append(t(ctx, "Reply 'go ahead' to execute this, or 'cancel'.", "回复“执行”以执行，或“取消”。"))
    return Turn(intent=Intent.EVALUATE_OFFER, reply="\n".join(reply), plan=steps.items, verdict=v,
                awaiting=pending is not None, pending=pending)


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
        return Turn(intent=Intent.NEGOTIATE, reply=t(ctx, "Plan ready. Reply 'go ahead' to send the counters.",
                                                     "计划已就绪。回复“执行”发送反报价。"),
                    plan=steps.items, verdict=v, awaiting=True,
                    pending=PendingPlan(Intent.NEGOTIATE, slots, steps.items, {"verdict_id": v.id}))
    neg = run_negotiation(ctx, steps, v, v.counters, profile)
    reply = [verdict_line(ctx, v)]
    if neg.accepted is not None:
        r = accept(ctx, steps, v, neg.accepted)
        if r is not None and r.status.value in ("EXECUTED", "PENDING_APPROVAL", "DUPLICATE"):
            pkg = ctx.evaluate(package_offer(ctx, offer, neg.accepted), remember=False)
            plan = committed_plan(pkg)
            if plan is not None:
                funding_ops(ctx, steps, plan, condition=t(ctx, "remaining gap after the accepted package",
                                                          "成交后剩余缺口"))
        reply.append(t(ctx, f"The buyer accepted {neg.accepted.label}.", f"买方接受了 {neg.accepted.label}。"))
        reply.extend(awaiting_owner(ctx))
    elif neg.outcome == "NO_DEAL":
        sq = ctx.evaluate(status_quo_offer(ctx, ctx.state()), remember=False)
        plan = committed_plan(sq)
        if plan is not None:
            funding_ops(ctx, steps, plan, condition=t(ctx, "NO DEAL: the router's plan covers the gap",
                                                      "未成交：由融资路由方案覆盖缺口"))
            reply.append(t(ctx, f"NO DEAL. The gap is covered by the committed plan: {plan.label}.",
                           f"未成交。缺口由已承诺方案覆盖：{plan.label}。"))
        else:
            reply.append(t(ctx, "NO DEAL, and there is no gap to cover.", "未成交，且无资金缺口。"))
    return Turn(intent=Intent.NEGOTIATE, reply="\n".join(reply), plan=steps.items, verdict=v,
                negotiation=neg.summary, clear_pending=True)


# ---------------------------------------------------------------- EXPLAIN


def explain(ctx: NlContext, slots: Slots) -> Turn:
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


def owner_doc_for(ctx: NlContext, text: str) -> SourceDocument:
    return SourceDocument(doc_id=f"NL-{ctx.session.id}-t{ctx.session.turn}", channel="owner", sender_id="OWNER",
                          received_day=ctx.day, text=text)
