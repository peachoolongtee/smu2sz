"""Hand-built obligations and funding actions (the compiler does not exist yet)."""

from __future__ import annotations

from app.domain.models import (
    BaseKind,
    Contingency,
    Duration,
    DurationKind,
    FundingAction,
    FundingActionKind,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceSpan,
)

SPAN = [SourceSpan(doc_id="TEST", start=0, end=4, text="test")]


def ob(
    oid: str,
    type_: ObligationType,
    *,
    cp: str = "BUYER-1",
    rate_bp: int | None = None,
    amount_fen: int | None = None,
    days_delta: int | None = None,
    effective_day: int | None = None,
    base_kind: BaseKind = BaseKind.FUTURE_INVOICES,
    base_amount: int | None = None,
    receivable_id: str | None = None,
    events_per_year: int | None = None,
    contingency: Contingency = Contingency.FIRM,
    duration: DurationKind = DurationKind.RECURRING_PERPETUAL,
    invoices: int | None = None,
    end_day: int | None = None,
) -> Obligation:
    return Obligation(
        id=oid,
        type=type_,
        counterparty_id=cp,
        rate_bp=rate_bp,
        amount_fen=amount_fen,
        days_delta=days_delta,
        effective_day=effective_day,
        base=ObligationBase(
            kind=base_kind, amount_fen=base_amount, receivable_id=receivable_id, events_per_year=events_per_year
        ),
        contingency=contingency,
        duration=Duration(kind=duration, invoices=invoices, end_day=end_day),
        spans=SPAN,
        confidence=1.0,
    )


def early_pay_discount(rate_bp: int = 120, receivable_id: str | None = "RCV-A", base_amount: int | None = None):
    return ob("OB-DISC", ObligationType.IMMEDIATE_DISCOUNT, rate_bp=rate_bp, base_kind=BaseKind.INVOICE,
              receivable_id=receivable_id, base_amount=base_amount, duration=DurationKind.ONE_OFF)


def extension(days: int = 15, **kw) -> Obligation:
    return ob("OB-EXT", ObligationType.TERMS_EXTENSION, days_delta=days, **kw)


def rebate(rate_bp: int = 100, cap_fen: int = 40_000_000, **kw) -> Obligation:
    return ob("OB-REB", ObligationType.CONTINGENT_REBATE, rate_bp=rate_bp, base_kind=BaseKind.PERIOD_PURCHASES,
              base_amount=cap_fen, contingency=Contingency.CONTINGENT, duration=DurationKind.ONE_OFF, **kw)


def ex01_package(keep_45_days: bool = False) -> list[Obligation]:
    obs = [early_pay_discount(), rebate()]
    if not keep_45_days:
        obs.insert(1, extension(15))
    return obs


def draw(facility_id: str = "FAC-LINE", amount: int = 15_000_000, day: int = 0, repay_day: int | None = 32):
    return FundingAction(kind=FundingActionKind.DRAW, facility_id=facility_id, day=day, amount_fen=amount,
                         repay_day=repay_day)


def finance(amount: int = 21_000_000, receivable_id: str = "RCV-A", day: int = 0, facility_id: str = "FAC-IF"):
    return FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id=facility_id, day=day,
                         amount_fen=amount, receivable_id=receivable_id)


def early_pay(face: int, rate_bp: int = 120, receivable_id: str = "RCV-A", day: int = 0):
    return FundingAction(kind=FundingActionKind.EARLY_PAY, facility_id="FAC-EARLYPAY", day=day, amount_fen=face,
                         receivable_id=receivable_id, rate_bp=rate_bp)
