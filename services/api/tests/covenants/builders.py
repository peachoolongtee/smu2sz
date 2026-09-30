"""Hand-built Trajectory objects (the financial engine is built in parallel; never imported here)."""

from __future__ import annotations

from app.covenants.ratios import dscr_value, leverage_value
from app.domain.models import DayPoint, LedgerEvent, LedgerEventKind, Mode, MonthPoint, Trajectory
from app.domain.money import Ratio


def month(m: int, ebitda: int, ds: int, debt: int) -> MonthPoint:
    d = dscr_value(ebitda, ds)
    lev = leverage_value(debt, ebitda)
    return MonthPoint(
        month=m,
        ebitda_fen=ebitda,
        debt_service_fen=ds,
        total_debt_fen=debt,
        dscr=Ratio.of(d) if d is not None else None,
        leverage=Ratio.of(lev) if lev is not None else Ratio(num=0, den=1),
    )


def draw(day: int, ref: str, amount: int) -> LedgerEvent:
    return LedgerEvent(day=day, kind=LedgerEventKind.DRAW, amount_fen=amount, label="draw", ref=ref)


def repay(day: int, ref: str, amount: int) -> LedgerEvent:
    return LedgerEvent(day=day, kind=LedgerEventKind.REPAYMENT, amount_fen=-amount, label="repay", ref=ref)


def interest(day: int, ref: str, amount: int) -> LedgerEvent:
    return LedgerEvent(day=day, kind=LedgerEventKind.INTEREST, amount_fen=-amount, label="interest", ref=ref)


def trajectory(
    horizon: int,
    events: list[LedgerEvent] | None = None,
    months: list[MonthPoint] | None = None,
    closings: dict[int, int] | None = None,
    default_closing: int = 40_000_000,
) -> Trajectory:
    """Days 0..horizon inclusive. `closings` overrides closing cash on given days."""
    by_day: dict[int, list[LedgerEvent]] = {}
    for e in events or []:
        by_day.setdefault(e.day, []).append(e)
    closings = closings or {}
    days = []
    prev = default_closing
    for d in range(horizon + 1):
        close = closings.get(d, default_closing)
        days.append(
            DayPoint(
                day=d,
                opening_fen=prev,
                closing_fen=close,
                debt_outstanding_fen=0,
                forward_concession_fen=0,
                events=by_day.get(d, []),
            )
        )
        prev = close
    low = min(days, key=lambda p: (p.closing_fen, p.day))
    return Trajectory(
        mode=Mode.CONSERVATIVE,
        horizon_days=horizon,
        days=days,
        months=months or [],
        min_cash_fen=low.closing_fen,
        min_cash_day=low.day,
        first_breach_day=None,
        interest_posted_fen=0,
        fees_posted_fen=0,
        discounts_posted_fen=0,
    )
