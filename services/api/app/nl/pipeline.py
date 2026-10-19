"""Deterministic plan -> typed operation builders shared by the intent handlers.

Every builder takes a stored `Verdict` (or the verifier's funding plan inside one) and emits typed
Operations through `NlContext.execute`. No builder reads free text; amounts, ids and rates come from
the verdict, its counters, or the router's plan (INVARIANT 1).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from app.api.presentation import no_simulated_reply_text
from app.counterparties import BuyerKernel, CounterpartyError, UnknownBuyerProfile, negotiate
from app.counterparties.books import fitted_profile
from app.counterparties.profiles import get_profile
from app.domain.claims import restate_not_on_record
from app.domain.models import (
    AcceptOffer,
    CompiledOffer,
    CompileStatus,
    CounterOffer,
    CounterProposal,
    FinancialState,
    FundingActionKind,
    FundingPlan,
    OperationResult,
    OperationStatus,
    Outcome,
    RejectOffer,
    SourceDocument,
    SourceSpan,
    Verdict,
)
from app.domain.money import fmt_yuan
from app.egress import allowed_for_counter
from app.nl.context import NlContext
from app.nl.models import PlanStep
from app.verifier import VerdictBundle

COMMITMENT_DAYS = 14
PROMPT_VERSION = "nl-v1"
LIVE_STATUSES = (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL, OperationStatus.DUPLICATE)


def t(ctx: NlContext, en: str, zh: str) -> str:
    return zh if ctx.lang == "zh" else en


def counter_text(ctx: NlContext, text: str, offer_id: str | None) -> str:
    """A counter's English text as the reader gets it. `offer_id` is the offer the counter answers: a lead that says "No rebate is on
    record" for a claimed prior agreement names what the buyer claimed instead ("No payment-terms agreement is on record"), and only
    that clause changes. A counter that is sent passes through here before the egress guard (LOG-2), so the text scanned is the text
    the plan step records and the buyer reads."""
    if offer_id is not None and (offer := ctx.store.get_offer(offer_id)) is not None:
        return restate_not_on_record(text, offer.obligations)
    return text


def counter_line(ctx: NlContext, label: str, text: str, offer_id: str | None = None) -> str:
    """A counter as one line, "Option A: <terms>", in the reader's language; in Chinese the line is the same English text through the
    translation layer, so a Chinese buyer or owner reads "方案 A：<条款>" with the same figures.

    With `offer_id` (a counter only shown, never sent) the lead is named for the claim here (`counter_text`). A sent counter's text
    comes from `send_counters` already in its final English words, the ones the egress guard scanned: it is passed without `offer_id`."""
    text = counter_text(ctx, text, offer_id)
    if ctx.lang != "zh":
        return f"{label}: {text}"
    from app.api.engine_zh import translate
    from app.api.presentation import option_label
    return f"{option_label(label, 'zh')}：{translate(text)}"


@dataclass
class Steps:
    """Accumulates plan steps with running numbers."""

    items: list[PlanStep] = field(default_factory=list)

    def add(self, kind: str, description: str, status: str = "PROPOSED", op_id: str | None = None,
            condition: str | None = None) -> PlanStep:
        s = PlanStep(step=len(self.items) + 1, kind=kind, description=description, status=status,  # type: ignore[arg-type]
                     op_id=op_id, condition=condition)
        self.items.append(s)
        return s

    def result(self, kind: str, description: str, r: OperationResult, condition: str | None = None) -> PlanStep:
        status = {OperationStatus.EXECUTED: "EXECUTED", OperationStatus.REFUSED: "REFUSED",
                  OperationStatus.PENDING_APPROVAL: "PENDING_APPROVAL",
                  OperationStatus.DUPLICATE: "DUPLICATE"}[r.status]
        text = description if r.status != OperationStatus.REFUSED else f"{description} — refused: {r.message}"
        return self.add(kind, text, status, r.op_id, condition)


# ---------------------------------------------------------------- synthetic offers (typed, no free text)


def owner_doc(ctx: NlContext, text: str, suffix: str = "") -> SourceDocument:
    return SourceDocument(doc_id=f"NL-{ctx.session.id}-t{ctx.session.turn}{suffix}", channel="owner",
                          sender_id="OWNER", received_day=ctx.day, text=text)


def status_quo_offer(ctx: NlContext, state: FinancialState, label: str = "SQ") -> CompiledOffer:
    """The 'no new terms' offer: the verifier's verdict on it carries the router's committed plan for any
    projected gap under the current (or a hypothetical) state."""
    basis = f"{state.state_version}|{state.cash_fen}|{len(state.flows)}|{ctx.day}|{label}"
    oid = f"NL-{label}-" + hashlib.sha256(basis.encode()).hexdigest()[:12]
    return CompiledOffer(offer_id=oid, counterparty_id="OWNER", doc_ids=[oid], received_day=ctx.day,
                         status=CompileStatus.COMPILED, obligations=[], compiler="nl-status-quo",
                         prompt_version=PROMPT_VERSION)


def package_offer(ctx: NlContext, source: CompiledOffer, counter: CounterProposal) -> CompiledOffer:
    """The accepted counter as an offer, so the verifier checks exactly what was agreed."""
    oid = f"{source.offer_id}-{counter.id}"
    obs = [o.model_copy(update={"id": f"{oid}-O{i}"}) for i, o in enumerate(counter.obligations, 1)]
    doc_ids = sorted({sp.doc_id for o in obs for sp in o.spans}) or [oid]
    return CompiledOffer(offer_id=oid, counterparty_id=source.counterparty_id, doc_ids=doc_ids,
                         received_day=ctx.day, status=CompileStatus.COMPILED, obligations=obs,
                         compiler=f"counter:{counter.label}", prompt_version=PROMPT_VERSION)


def span_of(doc: SourceDocument, start: int, end: int) -> SourceSpan:
    return SourceSpan(doc_id=doc.doc_id, start=start, end=end, text=doc.text[start:end])


# ---------------------------------------------------------------- operations from a verdict


def sent_outside(ctx: NlContext, offer_id: str) -> str | None:
    """The owner's sentence when they sent the buyer a counter on this request themself (an OFFERED fact, OUT-1), else None. From then on
    the buyer's answer is recorded on the deal, and no chat path accepts, declines, counters or negotiates on the request: the rule is
    `app.api.decisions.sent_outside_conflict`, the one the accept and simulated-buyer routes apply, and the sentence is its own (en, zh).
    The helper reads only `.store`, which the context carries. Every chat turn runs under `rt.lock` (POST /nl, /nl/opener)."""
    from app.api.decisions import sent_outside_conflict

    hit = sent_outside_conflict(cast(Any, ctx), offer_id, ctx.lang)
    return None if hit is None else str(cast(dict, hit.detail)["message"])


def nonce_for(key: str, verdict_id: str) -> str:
    return "nln-" + hashlib.sha256(f"nonce|{key}|{verdict_id}".encode()).hexdigest()[:32]


def accept(ctx: NlContext, steps: Steps, verdict: Verdict, counter: CounterProposal | None = None,
           condition: str | None = None) -> OperationResult | None:
    """Propose the commitment the verdict (or one of its counters) allows, then send AcceptOffer. The
    executor computes the tier: Tier 2 comes back PENDING_APPROVAL. Nothing is proposed or sent on a request the owner answered
    outside FLOW (`sent_outside`)."""
    if (said := sent_outside(ctx, verdict.offer_id)) is not None:
        steps.add("ACCEPT_OFFER", said, "SKIPPED", condition=condition)
        return None
    base = ctx.base("ACCEPT_OFFER")
    expires = min(ctx.day + COMMITMENT_DAYS, ctx.mandate().expires_day)
    try:
        c = ctx.executor.propose_commitment(verdict.id, expires_day=expires,
                                            counter_id=counter.id if counter else None,
                                            nonce=nonce_for(base["idempotency_key"], verdict.id))
    except (LookupError, ValueError) as e:
        steps.add("ACCEPT_OFFER", t(ctx, f"Not accepted: {e}", f"未接受：{e}"), "SKIPPED", condition=condition)
        return None
    op = AcceptOffer(**base, source_verdict_id=verdict.id, offer_id=c.offer_id, offer_version=c.offer_version,
                     terms_hash=c.terms_hash, nonce=c.nonce)
    r = ctx.execute(op)
    what = f"{counter.label} " if counter else ""
    steps.result("ACCEPT_OFFER", t(ctx, f"Record commitment {c.id} ({what}nonce, expires day {c.expires_day})",
                                   f"记录承诺 {c.id}（{what}一次性随机数，第 {c.expires_day} 天到期）"), r, condition)
    return r


def reject(ctx: NlContext, steps: Steps, verdict: Verdict) -> OperationResult | None:
    """Send RejectOffer on the verdict's offer; None, with nothing sent, on a request the owner answered outside FLOW."""
    if (said := sent_outside(ctx, verdict.offer_id)) is not None:
        steps.add("REJECT_OFFER", said, "SKIPPED")
        return None
    codes = list(dict.fromkeys(v.code for v in verdict.violations))
    op = RejectOffer(**ctx.base("REJECT_OFFER"), source_verdict_id=verdict.id, offer_id=verdict.offer_id,
                     reason_codes=codes)
    r = ctx.execute(op)
    steps.result("REJECT_OFFER", t(ctx, f"Reject offer {verdict.offer_id} ({', '.join(c.value for c in codes) or 'no code'})",
                                   f"拒绝报价 {verdict.offer_id}"), r)
    return r


def send_counters(ctx: NlContext, steps: Steps, verdict: Verdict, counters: Sequence[CounterProposal],
                  recipient_id: str) -> list[tuple[CounterProposal, str]]:
    """Guard each counter's final English text (its lead named for the claim, `counter_text`), then send CounterOffer. Returns (counter,
    text sent), the text the guard scanned and the plan step records: none on a request the owner answered outside FLOW (`sent_outside`).
    A hit withholds the counter: nothing is sent for it."""
    sent: list[tuple[CounterProposal, str]] = []
    if (said := sent_outside(ctx, verdict.offer_id)) is not None:
        steps.add("COUNTER_OFFER", said, "SKIPPED")
        return sent
    for c in counters:
        text, ok = ctx.guard(counter_text(ctx, c.text, verdict.offer_id), recipient_id, allow=allowed_for_counter(c))
        if not ok:
            steps.add("COUNTER_OFFER", t(ctx, f"{c.label} withheld by the egress guard",
                                         f"{c.label} 被出站防护拦截"), "SKIPPED")
            continue
        op = CounterOffer(**ctx.base("COUNTER_OFFER"), source_verdict_id=verdict.id, offer_id=verdict.offer_id,
                          counter_id=c.id)
        r = ctx.execute(op)
        steps.result("COUNTER_OFFER", counter_line(ctx, c.label, text), r)  # `text` is final: no rewrite after the scan
        if r.status in LIVE_STATUSES:
            sent.append((c, text))
    return sent


def funding_ops(ctx: NlContext, steps: Steps, plan: FundingPlan, condition: str | None = None,
                status: str = "PROPOSED") -> None:
    """Show the router's committed plan as plan steps: DRAW -> a draw, FINANCE_INVOICE -> an invoice advance, each
    with the day its cash lands. It sends nothing: the operations a confirmation sends are the typed legs stored with
    the plan (`app.nl.plans.legs_from_plan`, run by `run_legs`); no path builds a funding plan after the owner's
    go-ahead. Early pay is a buyer acceptance, not a funding operation; repayments happen on their scheduled day.
    A plan that cannot run today is shown with `status` "SKIPPED": it is never one a go-ahead sends."""
    for a in plan.actions:
        if a.kind == FundingActionKind.DRAW:
            desc = t(ctx, f"Draw {fmt_yuan(a.amount_fen)} on {a.facility_id}" +
                     (f", repay day {a.repay_day}" if a.repay_day is not None else ""),
                     f"从 {a.facility_id} 提款 {fmt_yuan(a.amount_fen)}")
            steps.add("DRAW_FACILITY", desc + _lands(ctx, a.facility_id), status, condition=condition)
        elif a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id:
            desc = t(ctx, f"Submit {a.receivable_id} to {a.facility_id} for a {fmt_yuan(a.amount_fen)} advance",
                     f"将 {a.receivable_id} 提交 {a.facility_id} 融资，预付 {fmt_yuan(a.amount_fen)}")
            steps.add("SUBMIT_INVOICE_FOR_FINANCING", desc + _lands(ctx, a.facility_id), status, condition=condition)


def _lands(ctx: NlContext, facility_id: str) -> str:
    """" (requested today, cash lands on day 3)" for a facility with a lead time, else nothing."""
    lead = next((f.lead_time_days for f in ctx.state().facilities if f.id == facility_id), 0)
    if lead <= 0:
        return ""
    return t(ctx, f" (requested today, cash lands on day {ctx.day + lead})", f"（今日申请，第 {ctx.day + lead} 天到账）")


def committed_plan(bundle: VerdictBundle) -> FundingPlan | None:
    """The verdict's committed plan for the gap. Only a verdict that is not a REJECT backs funding."""
    v = bundle.verdict
    if v.outcome in (Outcome.REJECT, Outcome.NO_VERDICT, Outcome.NO_DEAL):
        return None
    plan = bundle.plan_committed or v.plan
    if plan is None or not plan.admissible or plan.basis != "COMMITTED":
        return None
    return plan


# ---------------------------------------------------------------- negotiation


@dataclass
class NegotiationOutcome:
    outcome: str  # ACCEPT | NO_DEAL | NOT_STARTED
    summary: dict[str, Any]
    accepted: CounterProposal | None = None


def run_negotiation(ctx: NlContext, steps: Steps, verdict: Verdict, counters: Sequence[CounterProposal],
                    profile_id: str) -> NegotiationOutcome:
    """Send the counters (guarded), then bounded rounds with the deterministic buyer kernel. Not started on a request the owner
    answered outside FLOW: the buyer has the owner's counter, and the simulated buyer does not answer it as well."""
    if (said := sent_outside(ctx, verdict.offer_id)) is not None:
        steps.add("NEGOTIATE", said, "SKIPPED")
        return NegotiationOutcome("NOT_STARTED", {"reason": "OFFER_SENT_OUTSIDE"})
    offer = ctx.store.get_offer(verdict.offer_id)
    recipient = offer.counterparty_id if offer is not None else "UNKNOWN"
    sent = send_counters(ctx, steps, verdict, counters, recipient)
    if not sent:
        return NegotiationOutcome("NOT_STARTED", {"reason": "no counter could be sent"})
    try:
        # The buyer answers about the invoice in these books (on books the owner opened, never the golden demo's RCV-A).
        fitted = fitted_profile(get_profile(profile_id), ctx.store.get_state(), ctx.day, [c for c, _ in sent])
        kernel = BuyerKernel(profiles={profile_id: fitted})
        transcript = negotiate([c for c, _ in sent], profile_id, lambda _r: None, kernel=kernel)
    except CounterpartyError as e:
        # The owner's words, never the exception's class name: a buyer with no simulated profile gets the send's own sentence.
        said = (no_simulated_reply_text(ctx.store.get_state(), recipient, ctx.lang) if isinstance(e, UnknownBuyerProfile)
                else t(ctx, "The simulated buyer could not answer, so the negotiation did not start.", "模拟买方无法答复，因此谈判未开始。"))
        steps.add("NEGOTIATE", said, "SKIPPED")
        return NegotiationOutcome("NOT_STARTED", {"reason": type(e).__name__})
    accepted = next((c for c, _ in sent if c.id == transcript.accepted_counter_id), None)
    buyer_lines = [m.text_zh if ctx.lang == "zh" and m.text_zh else m.text_en
                   for m in transcript.messages if m.sender == "BUYER"]
    summary = {"outcome": transcript.outcome.value, "rounds": transcript.rounds_used,
               "accepted_counter": accepted.label if accepted else None, "ended_reason": transcript.ended_reason,
               "transcript_hash": transcript.transcript_hash, "buyer_replies": buyer_lines}
    label = accepted.label if accepted else None
    steps.add("NEGOTIATE", t(ctx, f"{transcript.rounds_used} round(s): " +
                             (f"the buyer accepted {label}" if label else "no deal"),
                             f"{transcript.rounds_used} 轮：" + (f"买方接受 {label}" if label else "未成交")), "DONE")
    return NegotiationOutcome(transcript.outcome.value, summary, accepted)
