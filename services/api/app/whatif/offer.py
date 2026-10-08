"""Build a synthetic CompiledOffer straight from typed obligations: no text in, no compiler.

The verifier needs a span on every obligation (INVARIANT 10), so the sandbox writes a short
description document ("WHATIF") clause by clause and points each obligation at its own clause.
The description is generated from the typed parameters; it is never parsed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import overload

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    CompileStatus,
    Contingency,
    Duration,
    DurationKind,
    ExpectedOrder,
    FinancialState,
    Obligation,
    ObligationBase,
    ObligationType,
    Receivable,
    RecurringInvoice,
    SourceSpan,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.whatif.params import WhatIfParamError, WhatIfParams

DOC_ID = "WHATIF"
COMPILER = "whatif-sandbox"
PROMPT_VERSION = "whatif-v1"


@dataclass(frozen=True)
class Context:
    """The rows of the verified state the sliders act on."""

    counterparty_id: str
    receivable: Receivable
    recurring: RecurringInvoice
    order: ExpectedOrder | None


@dataclass(frozen=True)
class EarlyPayContext:
    """A buyer with an open receivable and no recurring invoice: the early-payment lever only (no terms, price or rebate)."""

    counterparty_id: str
    receivable: Receivable
    order: ExpectedOrder | None


@dataclass(frozen=True)
class RebateOnlyContext:
    """A buyer with an expected order and no open receivable to pay early: the rebate lever only (no terms, price or
    early payment). It has no invoice, so asking it for one (`receivable`) is a `WhatIfParamError`: code written for an
    invoice refuses the buyer as it always did, and code that knows this case reads `order`."""

    counterparty_id: str
    order: ExpectedOrder

    @property
    def receivable(self) -> Receivable:
        raise WhatIfParamError(f"{self.counterparty_id} has no open invoice: only the rebate on its expected order can be valued")


def _context_of(state: FinancialState, cp: str, rec: RecurringInvoice | None, day: int, not_yet_due: bool = False,
                rebate_only: bool = False) -> Context | EarlyPayContext | RebateOnlyContext | None:
    opens = sorted((r for r in state.receivables if r.counterparty_id == cp and r.status == "OPEN"),
                   key=lambda r: (r.due_day, r.id))
    orders = sorted((o for o in state.expected_orders if o.counterparty_id == cp and o.start_day >= day),
                    key=lambda o: (o.start_day, o.label))
    order = orders[0] if orders else None
    if not opens:  # nothing to pay early: the rebate on an expected order is the only lever left, if there is an order
        return RebateOnlyContext(cp, order) if order is not None and rebate_only else None
    if not_yet_due:  # an early payment on an overdue invoice means nothing: the earliest one still to fall due, if any
        opens = [r for r in opens if r.due_day >= day] or opens
    if rec is not None:
        return Context(cp, opens[0], rec, order)
    return EarlyPayContext(cp, opens[0], order)


@overload
def context(state: FinancialState, day: int = 0, buyer_id: None = None) -> Context: ...


@overload
def context(state: FinancialState, day: int, buyer_id: str) -> Context | EarlyPayContext | RebateOnlyContext: ...


@overload
def context(state: FinancialState, day: int = 0, *, buyer_id: str) -> Context | EarlyPayContext | RebateOnlyContext: ...


def context(state: FinancialState, day: int = 0,
            buyer_id: str | None = None) -> Context | EarlyPayContext | RebateOnlyContext:
    """Without a buyer id: the buyer with a recurring invoice and an open receivable (golden: BUYER-1, RCV-A).
    With one: that buyer's single recurring invoice and its earliest open receivable not yet past due (the earliest open
    one when every open receivable is overdue); a buyer with open receivables and no recurring invoice gets an
    `EarlyPayContext`; a buyer with no open receivable but an expected order gets a `RebateOnlyContext`; a buyer with
    none of the three (recurring invoice, open receivable, expected order) is refused."""
    if buyer_id is not None:
        recs = [r for r in state.recurring_invoices if r.counterparty_id == buyer_id]
        found = _context_of(state, buyer_id, recs[0] if len(recs) == 1 else None, day, not_yet_due=True,
                              rebate_only=True)
        if found is None:
            name = next((c.name for c in state.counterparties if c.id == buyer_id), buyer_id)
            raise WhatIfParamError(f"FLOW has no terms, payment or rebate lever to value for {name} yet.")
        return found
    for rec in state.recurring_invoices:
        cp = rec.counterparty_id
        if sum(1 for r in state.recurring_invoices if r.counterparty_id == cp) != 1:
            continue
        found = _context_of(state, cp, rec, day)
        if isinstance(found, Context):
            return found
    raise WhatIfParamError("the state has no buyer with a recurring invoice and an open receivable")


class _Doc:
    def __init__(self) -> None:
        self.text = "What-if (hypothetical, nothing is booked):"

    def clause(self, sentence: str) -> SourceSpan:
        self.text += " "
        start = len(self.text)
        self.text += sentence
        return SourceSpan(doc_id=DOC_ID, start=start, end=len(self.text), text=sentence)


def offer_id(params: WhatIfParams) -> str:
    key = params.model_dump_json()
    return "WHATIF-" + hashlib.sha256(key.encode()).hexdigest()[:10]


def build(params: WhatIfParams, ctx: Context | EarlyPayContext | RebateOnlyContext,
          day: int = 0) -> tuple[CompiledOffer, str]:
    """(synthetic offer, its description text). Obligations are FIRM except the rebate, which is
    CONTINGENT and so counted at maximum (INVARIANT 5). An `EarlyPayContext` carries the early payment only: the
    terms, rebate and price clauses need a recurring invoice and are left out. A `RebateOnlyContext` carries the
    rebate on its expected order only (the same clause as the recurring path); an early payment asked of it is refused."""
    recurring = ctx.recurring if isinstance(ctx, Context) else None
    cp = ctx.counterparty_id
    doc = _Doc()
    obs: list[Obligation] = []
    oid = offer_id(params)

    def add(t: ObligationType, span: SourceSpan, **kw: object) -> None:
        obs.append(Obligation(id=f"{oid}-O{len(obs) + 1}", type=t, counterparty_id=cp, spans=[span],
                              confidence=1.0, **kw))  # type: ignore[arg-type]

    if params.discount_bp > 0:
        rcv = ctx.receivable  # a rebate-only buyer has no invoice to settle early: refused
        face = params.settle_face_fen if params.settle_face_fen is not None else rcv.face_fen
        if face > rcv.face_fen:
            raise WhatIfParamError(f"settle_face_fen {face} is above the open face of {rcv.id} ({rcv.face_fen})")
        whole = "the whole" if face == rcv.face_fen else "part of"
        span = doc.clause(f"early settlement of {whole} {rcv.id}, {fmt_yuan(face)} at "
                          f"{fmt_pct(bp(params.discount_bp))} off.")
        add(ObligationType.IMMEDIATE_DISCOUNT, span, rate_bp=params.discount_bp,
            base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=face, receivable_id=rcv.id),
            contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF))

    current = recurring.terms_days if recurring is not None else params.terms_days
    if recurring is not None and params.terms_days != current:
        span = doc.clause(f"payment terms {params.terms_days} days going forward (now {current} days).")
        add(ObligationType.TERMS_EXTENSION, span, days_delta=params.terms_days - current,
            target_terms_days=params.terms_days, effective_day=None,
            base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
            contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.RECURRING_PERPETUAL))

    if (recurring is not None or isinstance(ctx, RebateOnlyContext)) and params.rebate_bp > 0:
        amount = ctx.order.amount_fen if ctx.order is not None else None
        what = (f"the expected {ctx.order.label} order of {fmt_yuan(ctx.order.amount_fen)}"
                if ctx.order is not None else "next quarter's purchases")
        span = doc.clause(f"{fmt_pct(bp(params.rebate_bp))} rebate on {what}.")
        add(ObligationType.CONTINGENT_REBATE, span, rate_bp=params.rebate_bp,
            base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES, amount_fen=amount),
            contingency=Contingency.CONTINGENT, duration=Duration(kind=DurationKind.ONE_OFF))

    if recurring is not None and params.price_adjustment_bp > 0:
        span = doc.clause(f"{fmt_pct(bp(params.price_adjustment_bp))} price adjustment on future invoices "
                          f"of {fmt_yuan(recurring.face_fen)}.")
        add(ObligationType.PRICE_ADJUSTMENT, span, rate_bp=params.price_adjustment_bp,
            base=ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=recurring.face_fen),
            contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.RECURRING_PERPETUAL))

    if not obs:
        doc.clause("no change to the current terms.")

    offer = CompiledOffer(
        offer_id=oid, counterparty_id=cp, doc_ids=[DOC_ID], received_day=day, status=CompileStatus.COMPILED,
        obligations=obs, compiler=COMPILER, prompt_version=PROMPT_VERSION,
    )
    return offer, doc.text
