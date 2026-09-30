"""Server-formatted view models for the UI. The UI never computes money: every amount ships as
integer fen (for chart axes) plus a display string."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.models import Trajectory
from app.domain.money import fmt_yuan


class Money(BaseModel):
    fen: int
    text: str

    @classmethod
    def of(cls, fen: int) -> Money:
        return cls(fen=fen, text=fmt_yuan(fen))


class DayView(BaseModel):
    day: int
    closing: Money
    debt: Money
    forward_concession: Money
    below_floor: bool
    events: list[dict]


class MonthView(BaseModel):
    month: int
    dscr: str | None
    leverage: str | None
    debt_service: Money
    total_debt: Money


class TrajectoryView(BaseModel):
    mode: str
    floor: Money
    min_cash: Money
    min_cash_day: int
    first_breach_day: int | None
    days: list[DayView]
    months: list[MonthView]
    interest: Money
    fees: Money
    discounts: Money


def trajectory_view(t: Trajectory, floor_fen: int) -> TrajectoryView:
    return TrajectoryView(
        mode=t.mode.value,
        floor=Money.of(floor_fen),
        min_cash=Money.of(t.min_cash_fen),
        min_cash_day=t.min_cash_day,
        first_breach_day=t.first_breach_day,
        days=[
            DayView(
                day=d.day,
                closing=Money.of(d.closing_fen),
                debt=Money.of(d.debt_outstanding_fen),
                forward_concession=Money.of(d.forward_concession_fen),
                below_floor=d.closing_fen < floor_fen,
                events=[
                    {"kind": e.kind.value, "amount": Money.of(e.amount_fen).model_dump(), "label": e.label,
                     "ref": e.ref, "formula": e.formula}
                    for e in d.events
                ],
            )
            for d in t.days
        ],
        months=[
            MonthView(
                month=m.month,
                dscr=m.dscr.text + "x" if m.dscr else None,
                leverage=m.leverage.text + "x" if m.leverage else None,
                debt_service=Money.of(m.debt_service_fen),
                total_debt=Money.of(m.total_debt_fen),
            )
            for m in t.months
        ],
        interest=Money.of(t.interest_posted_fen),
        fees=Money.of(t.fees_posted_fen),
        discounts=Money.of(t.discounts_posted_fen),
    )
