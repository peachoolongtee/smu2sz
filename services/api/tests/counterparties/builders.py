"""Builders for supplier counters (spec v2 §6.5 Options A and B) and obligation packages."""

from __future__ import annotations

from app.domain.models import (
    BaseKind,
    Contingency,
    CounterProposal,
    Duration,
    DurationKind,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceSpan,
)

OPTION_A_TEXT = (
    "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥211,900 "
    "of this invoice at 0.85%."
)
OPTION_B_TEXT = "60-day terms accepted with a 0.45% price adjustment on future invoices, no rebate."
OPTION_A_FACE_FEN = 21_190_000
INVOICE_FACE_FEN = 42_000_000
NEXT_QUARTER_FEN = 40_000_000


def _span(doc_id: str, text: str) -> list[SourceSpan]:
    return [SourceSpan(doc_id=doc_id, start=0, end=len(text), text=text)]


def discount(
    rate_bp: int,
    face_fen: int = OPTION_A_FACE_FEN,
    *,
    oid: str = "OB-DISC",
    cp: str = "BUYER-1",
    effective_day: int | None = 2,
    receivable_id: str | None = "RCV-A",
) -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.IMMEDIATE_DISCOUNT,
        counterparty_id=cp,
        rate_bp=rate_bp,
        effective_day=effective_day,
        base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=face_fen, receivable_id=receivable_id),
        contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.ONE_OFF),
        spans=_span(oid, f"{rate_bp} bp"),
        confidence=1.0,
    )


def terms(days_delta: int, *, oid: str = "OB-TERMS", cp: str = "BUYER-1") -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.TERMS_EXTENSION,
        counterparty_id=cp,
        days_delta=days_delta,
        base=ObligationBase(kind=BaseKind.FUTURE_INVOICES),
        contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
        spans=_span(oid, f"{days_delta} days"),
        confidence=1.0,
    )


def price_adjustment(rate_bp: int, *, oid: str = "OB-PRICE", cp: str = "BUYER-1") -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.PRICE_ADJUSTMENT,
        counterparty_id=cp,
        rate_bp=rate_bp,
        base=ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=INVOICE_FACE_FEN),
        contingency=Contingency.FIRM,
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
        spans=_span(oid, f"{rate_bp} bp price"),
        confidence=1.0,
    )


def rebate(
    rate_bp: int, base_fen: int = NEXT_QUARTER_FEN, *, oid: str = "OB-REBATE", cp: str = "BUYER-1"
) -> Obligation:
    return Obligation(
        id=oid,
        type=ObligationType.CONTINGENT_REBATE,
        counterparty_id=cp,
        rate_bp=rate_bp,
        base=ObligationBase(kind=BaseKind.PERIOD_PURCHASES, amount_fen=base_fen),
        contingency=Contingency.CONTINGENT,
        duration=Duration(kind=DurationKind.ONE_OFF),
        spans=_span(oid, f"{rate_bp} bp rebate"),
        confidence=1.0,
    )


def counter(
    cid: str,
    label: str,
    obligations: list[Obligation],
    text: str = "Supplier counter.",
    *,
    supplier_cost_fen: int = 0,
    rationale: str = "priced from the marginal cost of funds",
    formula: str = "d/(1-d) < c",
) -> CounterProposal:
    return CounterProposal(
        id=cid,
        label=label,
        text=text,
        obligations=obligations,
        supplier_cost_fen=supplier_cost_fen,
        rationale=rationale,
        formula=formula,
    )


def option_a(rate_bp: int = 85, **kw: object) -> CounterProposal:
    """Option A: 45-day terms, no rebate, early settlement on up to ¥211,900 at 0.85%."""
    opts: dict[str, object] = {"supplier_cost_fen": 264_194, **kw}
    return counter("CTR-A", "Option A", [discount(rate_bp, oid="A-DISC")], OPTION_A_TEXT, **opts)  # type: ignore[arg-type]


def option_b(**kw: object) -> CounterProposal:
    """Option B: 60-day terms with a 0.45% price adjustment on future invoices, no rebate."""
    opts: dict[str, object] = {"supplier_cost_fen": 0, **kw}
    obligations = [terms(15, oid="B-TERMS"), price_adjustment(45, oid="B-PRICE")]
    return counter("CTR-B", "Option B", obligations, OPTION_B_TEXT, **opts)  # type: ignore[arg-type]
