"""Build a synthetic CompiledOffer straight from typed obligations: no text in, no compiler.

The verifier needs a span on every obligation (INVARIANT 10), so the sandbox writes a short
description document ("WHATIF") clause by clause and points each obligation at its own clause.
The description is generated from the typed parameters; it is never parsed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

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


def context(state: FinancialState, day: int = 0) -> Context:
    """The buyer with a recurring invoice and an open receivable (golden: BUYER-1, RCV-A)."""
    for rec in state.recurring_invoices:
        cp = rec.counterparty_id
        if sum(1 for r in state.recurring_invoices if r.counterparty_id == cp) != 1:
            continue
        opens = sorted((r for r in state.receivables if r.counterparty_id == cp and r.status == "OPEN"),
                       key=lambda r: (r.due_day, r.id))
        if not opens:
            continue
        orders = sorted((o for o in state.expected_orders if o.counterparty_id == cp and o.start_day >= day),
                        key=lambda o: (o.start_day, o.label))
        return Context(cp, opens[0], rec, orders[0] if orders else None)
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


def build(params: WhatIfParams, ctx: Context, day: int = 0) -> tuple[CompiledOffer, str]:
    """(synthetic offer, its description text). Obligations are FIRM except the rebate, which is
    CONTINGENT and so counted at maximum (INVARIANT 5)."""
    cp = ctx.counterparty_id
    rcv = ctx.receivable
    doc = _Doc()
    obs: list[Obligation] = []
    oid = offer_id(params)

    def add(t: ObligationType, span: SourceSpan, **kw: object) -> None:
        obs.append(Obligation(id=f"{oid}-O{len(obs) + 1}", type=t, counterparty_id=cp, spans=[span],
                              confidence=1.0, **kw))  # type: ignore[arg-type]

    if params.discount_bp > 0:
        face = params.settle_face_fen if params.settle_face_fen is not None else rcv.face_fen
        if face > rcv.face_fen:
            raise WhatIfParamError(f"settle_face_fen {face} is above the open face of {rcv.id} ({rcv.face_fen})")
        whole = "the whole" if face == rcv.face_fen else "part of"
        span = doc.clause(f"early settlement of {whole} {rcv.id}, {fmt_yuan(face)} at "
                          f"{fmt_pct(bp(params.discount_bp))} off.")
        add(ObligationType.IMMEDIATE_DISCOUNT, span, rate_bp=params.discount_bp,
            base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=face, receivable_id=rcv.id),
            contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF))

    current = ctx.recurring.terms_days
    if params.terms_days != current:
        span = doc.clause(f"payment terms {params.terms_days} days going forward (now {current} days).")
        add(ObligationType.TERMS_EXTENSION, span, days_delta=params.terms_days - current,
            target_terms_days=params.terms_days, effective_day=None,
            base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
            contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.RECURRING_PERPETUAL))

    if params.rebate_bp > 0:
        amount = ctx.order.amount_fen if ctx.order is not None else None
        what = (f"the expected {ctx.order.label} order of {fmt_yuan(ctx.order.amount_fen)}"
                if ctx.order is not None else "next quarter's purchases")
        span = doc.clause(f"{fmt_pct(bp(params.rebate_bp))} rebate on {what}.")
        add(ObligationType.CONTINGENT_REBATE, span, rate_bp=params.rebate_bp,
            base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES, amount_fen=amount),
            contingency=Contingency.CONTINGENT, duration=Duration(kind=DurationKind.ONE_OFF))

    if params.price_adjustment_bp > 0:
        span = doc.clause(f"{fmt_pct(bp(params.price_adjustment_bp))} price adjustment on future invoices "
                          f"of {fmt_yuan(ctx.recurring.face_fen)}.")
        add(ObligationType.PRICE_ADJUSTMENT, span, rate_bp=params.price_adjustment_bp,
            base=ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=ctx.recurring.face_fen),
            contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.RECURRING_PERPETUAL))

    if not obs:
        doc.clause("no change to the current terms.")

    offer = CompiledOffer(
        offer_id=oid, counterparty_id=cp, doc_ids=[DOC_ID], received_day=day, status=CompileStatus.COMPILED,
        obligations=obs, compiler=COMPILER, prompt_version=PROMPT_VERSION,
    )
    return offer, doc.text
