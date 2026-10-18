"""Deterministic buyer kernel with a hidden reservation (spec v2 §5.1, §6.5-6.6).

The kernel decides with integer-fen arithmetic from `app.domain.money`; wording happens after,
through the template verbaliser. A buyer's surplus from a package is

    discount received + declared benefits + rebate received + value of extra payment days
    - its own funding cost of paying early - price adjustments it pays

(no invented relationship value). It ACCEPTs when every reservation gate holds and the surplus
is at least its reservation; otherwise it COUNTERs one concession step toward, but never onto,
its reservation; in its last round it REJECTs; past `max_rounds` it REJECTs with
"rounds exhausted".

Isolation (INVARIANTS 7): from a `CounterProposal` the kernel reads only `id`, `label` and
`obligations`, never the supplier's `supplier_cost_fen`, `rationale` or `formula`. Nothing in a
`BuyerResponse` is derived from the reservation except the decision itself and the counter's
public terms, which always sit strictly above the reservation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.counterparties.profiles import BuyerProfile, get_profile
from app.counterparties.verbaliser import (
    LANGS,
    YOUR_PROPOSAL,
    Clause,
    Lang,
    PublicMessageFields,
    Rendered,
    ReplyKind,
    VerbaliserHook,
    public_label,
    verbalise,
)
from app.domain.models import (
    BaseKind,
    Contingency,
    Contract,
    CounterProposal,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceDocument,
    SourceSpan,
)
from app.domain.money import bp, fmt_pct, fmt_yuan, pct_of, post, simple_interest

ROUNDS_EXHAUSTED = "rounds exhausted"
FINAL_ROUND = "final round"
NOT_ACCEPTABLE = "not acceptable as proposed"


class BuyerDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    COUNTER = "COUNTER"


class BuyerResponse(Contract):
    """What the buyer sends back. Public: carries no reservation value."""

    response_id: str
    counterparty_id: str
    round: int = Field(ge=1)
    decision: BuyerDecision
    responding_to: list[str] = Field(default_factory=list)  # supplier counter ids
    accepted_counter_id: str | None = None
    obligations: list[Obligation] = Field(default_factory=list)  # COUNTER only
    reply_en: str
    reply_zh: str
    reason: str | None = None
    verbaliser: Literal["template", "hook"] = "template"

    @model_validator(mode="after")
    def _shape(self) -> BuyerResponse:
        if (self.decision is BuyerDecision.COUNTER) != bool(self.obligations):
            raise ValueError("a COUNTER carries obligations and nothing else does")
        if self.accepted_counter_id is not None and self.decision is not BuyerDecision.ACCEPT:
            raise ValueError("only an ACCEPT names an accepted counter")
        return self

    def reply(self, lang: Lang = "en") -> str:
        return self.reply_en if lang == "en" else self.reply_zh

    def reply_doc_id(self, lang: Lang = "en") -> str:
        return f"{self.response_id}:{lang}"

    def source_document(self, lang: Lang = "en", received_day: int = 0) -> SourceDocument:
        """The reply as an inbound, untrusted document (for the compiler or the inbox)."""
        return SourceDocument(
            doc_id=self.reply_doc_id(lang),
            channel="chat",
            sender_id=self.counterparty_id,
            received_day=received_day,
            text=self.reply(lang),
        )


# ---------------------------------------------------------------- buyer-private assessment


@dataclass(frozen=True)
class BuyerAssessment:
    """Buyer-private valuation of a package. Never serialise it or send it anywhere."""

    surplus_fen: int
    components: tuple[tuple[str, int], ...]
    failed_gates: tuple[str, ...]

    @property
    def acceptable(self) -> bool:
        return not self.failed_gates


def _invoices(profile: BuyerProfile, o: Obligation) -> int:
    d = o.duration
    if d.kind is DurationKind.ONE_OFF:
        return 1
    if d.kind is DurationKind.RECURRING_BOUNDED and d.invoices is not None:
        return min(d.invoices, profile.invoices_per_year)
    return profile.invoices_per_year  # perpetual: the buyer's own 12-month view


def assess(profile: BuyerProfile, obligations: Sequence[Obligation]) -> BuyerAssessment:
    """The buyer's surplus (integer fen, each component posted once) and reservation gates."""
    parts: list[tuple[str, int]] = []
    types = {o.type for o in obligations}
    discounts: list[int] = []
    rebates: list[int] = []
    days_delta = 0

    for o in obligations:
        rate = bp(o.rate_bp or 0)
        if o.type is ObligationType.IMMEDIATE_DISCOUNT:
            face = o.base.amount_fen if o.base.amount_fen is not None else profile.invoice_face_fen
            discount = post(pct_of(face, rate))
            settle = o.effective_day if o.effective_day is not None else profile.early_settlement_day
            due = profile.invoice_due_day if profile.invoice_due_day is not None else settle
            days_early = max(0, due - settle)
            cost = post(simple_interest(face - discount, bp(profile.funding_cost_bp), days_early))
            parts += [(f"{o.id}:discount_received", discount), (f"{o.id}:early_funding_cost", -cost)]
            discounts.append(o.rate_bp or 0)
        elif o.type is ObligationType.TERMS_EXTENSION:
            delta = o.days_delta or 0
            days_delta += delta
            parts.append((f"{o.id}:payment_days", delta * profile.payment_day_value_fen * _invoices(profile, o)))
        elif o.type is ObligationType.PRICE_ADJUSTMENT:
            face = o.base.amount_fen if o.base.amount_fen is not None else profile.invoice_face_fen
            per_invoice = post(pct_of(face, rate)) if o.rate_bp is not None else (o.amount_fen or 0)
            parts.append((f"{o.id}:price_adjustment", -per_invoice * _invoices(profile, o)))
        elif o.type is ObligationType.CONTINGENT_REBATE:
            base = o.base.amount_fen if o.base.amount_fen is not None else profile.next_quarter_purchases_fen
            value = post(pct_of(base, rate)) if o.rate_bp is not None else (o.amount_fen or 0)
            parts.append((f"{o.id}:rebate_received", value))
            rebates.append(o.rate_bp or 0)
        # VOLUME_COMMITMENT, OPERATIONAL_CONCESSION, CLAIMED_PRIOR_CONCESSION: no price term;
        # an operational change counts only through a benefit the buyer itself declared.

    for benefit in profile.declared_benefits:
        if benefit.obligation_type in types:
            parts.append((f"declared:{benefit.id}", benefit.value_fen))

    surplus = sum(v for _, v in parts)
    failed: list[str] = []
    if profile.requires_early_pay and not discounts:
        failed.append("early_pay_required")
    if any(d < profile.min_early_pay_discount_bp for d in discounts):
        failed.append("discount_below_minimum")
    if profile.insists_on_terms_extension and profile.current_terms_days + days_delta < profile.min_terms_days:
        failed.append("terms_below_minimum")
    if profile.min_rebate_bp and max(rebates, default=0) < profile.min_rebate_bp:
        failed.append("rebate_below_minimum")
    if surplus < profile.min_surplus_fen:
        failed.append("surplus_below_reservation")
    return BuyerAssessment(surplus_fen=surplus, components=tuple(parts), failed_gates=tuple(failed))


# ---------------------------------------------------------------- counter plan


@dataclass(frozen=True)
class _Planned:
    clause: Clause
    type: ObligationType
    rate_bp: int | None = None
    days_delta: int | None = None
    effective_day: int | None = None
    base: ObligationBase | None = None
    contingency: Contingency = Contingency.FIRM
    duration: DurationKind = DurationKind.ONE_OFF


def counter_plan(profile: BuyerProfile, round_no: int) -> list[_Planned]:
    """The buyer's counter in `round_no`: one concession step per round from its ask, clamped
    one step above its reservation so the reservation itself is never stated."""
    plan: list[_Planned] = []
    ask = profile.ask
    if ask.discount_bp is not None and profile.receivable_id is not None:
        floor = profile.min_early_pay_discount_bp + profile.concession_step_bp
        rate = max(ask.discount_bp - profile.concession_step_bp * round_no, floor)
        if profile.invoice_words and profile.settle_words:  # books the owner opened: the invoice and the date in words
            clause = Clause(
                key="early_settlement_named",
                params={
                    "invoice_en": profile.invoice_words["en"],
                    "invoice_zh": profile.invoice_words["zh"],
                    "when_en": profile.settle_words["en"],
                    "when_zh": profile.settle_words["zh"],
                    "rate": fmt_pct(bp(rate)),
                },
            )
        else:
            clause = Clause(
                key="early_settlement",
                params={
                    "receivable": profile.receivable_id,
                    "face": fmt_yuan(profile.invoice_face_fen),
                    "day": str(profile.early_settlement_day),
                    "rate": fmt_pct(bp(rate)),
                },
            )
        plan.append(
            _Planned(
                clause=clause,
                type=ObligationType.IMMEDIATE_DISCOUNT,
                rate_bp=rate,
                effective_day=profile.early_settlement_day,
                base=ObligationBase(
                    kind=BaseKind.INVOICE,
                    amount_fen=profile.invoice_face_fen,
                    receivable_id=profile.receivable_id,
                ),
            )
        )
    if ask.terms_days is not None and ask.terms_days != profile.current_terms_days:
        plan.append(
            _Planned(
                clause=Clause(key="terms", params={"days": str(ask.terms_days)}),
                type=ObligationType.TERMS_EXTENSION,
                days_delta=ask.terms_days - profile.current_terms_days,
                base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
                duration=DurationKind.RECURRING_PERPETUAL,
            )
        )
    if profile.max_rebate_bp and profile.next_quarter_purchases_fen:  # no purchases to rebate: no rebate clause
        floor = profile.min_rebate_bp + profile.rebate_step_bp if profile.min_rebate_bp else 0
        rate = max(profile.max_rebate_bp - profile.rebate_step_bp * round_no, floor)
        if rate > 0:
            plan.append(
                _Planned(
                    clause=Clause(
                        key="rebate",
                        params={"rate": fmt_pct(bp(rate)), "base": fmt_yuan(profile.next_quarter_purchases_fen)},
                    ),
                    type=ObligationType.CONTINGENT_REBATE,
                    rate_bp=rate,
                    base=ObligationBase(
                        kind=BaseKind.PERIOD_PURCHASES, amount_fen=profile.next_quarter_purchases_fen
                    ),
                    contingency=Contingency.CONTINGENT,
                )
            )
    return plan


# ---------------------------------------------------------------- kernel


@dataclass(frozen=True)
class _Inbound:
    counter_id: str | None
    label: str
    obligations: tuple[Obligation, ...]


def _inbound(proposal: CounterProposal | Sequence[Obligation]) -> _Inbound:
    # Reads only the public parts of a CounterProposal: never supplier_cost_fen, rationale, formula.
    if isinstance(proposal, CounterProposal):
        return _Inbound(proposal.id, public_label(proposal.label), tuple(proposal.obligations))
    return _Inbound(None, YOUR_PROPOSAL, tuple(proposal))


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


class BuyerKernel:
    """Deterministic buyer. The same profile, proposals and round always give the same response."""

    def __init__(
        self, verbaliser_hook: VerbaliserHook | None = None, profiles: Mapping[str, BuyerProfile] | None = None
    ) -> None:
        """`profiles` stands in for the fixture profile of the same id: a profile fitted to the books in use
        (`app.counterparties.books.fitted_profile`). Any other id is read from the fixtures."""
        self._hook = verbaliser_hook
        self._profiles = dict(profiles or {})

    def _profile(self, profile_id: str) -> BuyerProfile:
        fitted = self._profiles.get(profile_id)
        return fitted if fitted is not None else get_profile(profile_id)

    def max_rounds(self, profile_id: str) -> int:
        return self._profile(profile_id).max_rounds

    def respond(
        self, profile_id: str, proposal: CounterProposal | list[Obligation], round: int
    ) -> BuyerResponse:
        return self.respond_to_many(profile_id, [proposal], round)

    def respond_to_many(
        self, profile_id: str, proposals: Sequence[CounterProposal | list[Obligation]], round: int
    ) -> BuyerResponse:
        """Answer every proposal made in one round with a single response. If several are
        acceptable, the buyer accepts the one with the highest surplus (first on a tie)."""
        if round < 1:
            raise ValueError("rounds start at 1")
        if not proposals:
            raise ValueError("nothing to respond to")
        profile = self._profile(profile_id)
        inbound = [_inbound(p) for p in proposals]
        labels = list(dict.fromkeys(i.label for i in inbound))
        responding_to = [i.counter_id for i in inbound if i.counter_id is not None]

        accepted: _Inbound | None = None
        plan: list[_Planned] = []
        if round > profile.max_rounds:
            kind, reason = ReplyKind.REJECT_EXHAUSTED, ROUNDS_EXHAUSTED
        else:
            best: tuple[int, _Inbound] | None = None
            for item in inbound:
                a = assess(profile, item.obligations)
                if a.acceptable and (best is None or a.surplus_fen > best[0]):
                    best = (a.surplus_fen, item)
            if best is not None:
                accepted = best[1]
                kind, reason, labels = ReplyKind.ACCEPT, None, [accepted.label]
            elif round >= profile.max_rounds:
                kind, reason = ReplyKind.REJECT_FINAL, FINAL_ROUND
            else:
                plan = counter_plan(profile, round)
                kind, reason = (ReplyKind.COUNTER, NOT_ACCEPTABLE) if plan else (ReplyKind.REJECT, NOT_ACCEPTABLE)

        fields = PublicMessageFields(kind=kind, round=round, labels=labels, clauses=[p.clause for p in plan])
        response_id = "BR-" + _digest(
            {
                "counterparty": profile.counterparty_id,
                "round": round,
                "kind": kind.value,
                "to": responding_to,
                "inbound": [[o.model_dump(mode="json") for o in i.obligations] for i in inbound],
                "fields": fields.model_dump(mode="json"),
            }
        )
        rendered: dict[Lang, Rendered] = {lang: verbalise(fields, lang, self._hook) for lang in LANGS}
        obligations = [
            self._obligation(profile, response_id, n, p, rendered) for n, p in enumerate(plan, start=1)
        ]
        decision = {
            ReplyKind.ACCEPT: BuyerDecision.ACCEPT,
            ReplyKind.COUNTER: BuyerDecision.COUNTER,
        }.get(kind, BuyerDecision.REJECT)
        return BuyerResponse(
            response_id=response_id,
            counterparty_id=profile.counterparty_id,
            round=round,
            decision=decision,
            responding_to=responding_to,
            accepted_counter_id=accepted.counter_id if accepted else None,
            obligations=obligations,
            reply_en=rendered["en"].text,
            reply_zh=rendered["zh"].text,
            reason=reason,
            verbaliser="hook" if any(r.source == "hook" for r in rendered.values()) else "template",
        )

    @staticmethod
    def _obligation(
        profile: BuyerProfile, response_id: str, n: int, p: _Planned, rendered: dict[Lang, Rendered]
    ) -> Obligation:
        spans = []
        for lang in LANGS:
            start, end = rendered[lang].clause_spans[n - 1]
            spans.append(
                SourceSpan(
                    doc_id=f"{response_id}:{lang}", start=start, end=end, text=rendered[lang].text[start:end]
                )
            )
        return Obligation(
            id=f"{response_id}-OB{n}",
            type=p.type,
            counterparty_id=profile.counterparty_id,
            rate_bp=p.rate_bp,
            days_delta=p.days_delta,
            effective_day=p.effective_day,
            base=p.base or ObligationBase(kind=BaseKind.UNSPECIFIED),
            contingency=p.contingency,
            duration=Duration(kind=p.duration),
            spans=spans,
            confidence=1.0,
        )
