"""Existing debt (`FinancialState.debts`): the one payment schedule, read by the projection, the clock, capex and the
borrower file alike (docs/FINANCIAL_SEMANTICS.md §5; ADR-0010, "existing debt").

A `DebtPosition` is paid every `payment_every_days` from `next_payment_day`. On each payment day d on or after today,
while principal is left:

    interest  = post(principal × rate × (days since the last payment) / 365)
    principal part = min(principal, service − interest)   (never below zero)
    payment   = interest + principal part

so the last payment clears the principal and may be smaller than the service. The fixed `monthly_debt_service_fen`
stays the service figure of the debt-service ratio for the months the schedule covers (zero once the principal is
cleared); this schedule is the cash side.

Pure: no I/O, no clock. Nothing is ever dated before today: a payment day already behind the books (a state stored
before the schedule existed) is skipped, never posted late.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import DebtPosition
from app.financial.charges import line_interest


@dataclass(frozen=True, slots=True)
class DebtPayment:
    """One scheduled payment of an existing debt: `principal` and `interest` fall due on `day`; `remaining` is the
    principal left after it."""

    debt_id: str
    day: int
    principal: int
    interest: int
    remaining: int

    @property
    def amount(self) -> int:
        return self.principal + self.interest


def first_payment_day(debt: DebtPosition, today: int) -> int:
    """The first payment day on or after `today` (`next_payment_day`, rolled forward by whole periods)."""
    every = debt.payment_every_days
    if every <= 0:
        raise ValueError(f"debt {debt.id} has payment_every_days <= 0")
    d = debt.next_payment_day
    if d < today:
        d += -(-(today - d) // every) * every
    return d


def debt_payments(debt: DebtPosition, today: int, until_day: int) -> list[DebtPayment]:
    """The payments of `debt` dated in [today, until_day), in day order, while principal is left. A payment of zero
    (no rate, no service) is not a payment."""
    out: list[DebtPayment] = []
    principal = debt.principal_fen
    every = debt.payment_every_days
    d = first_payment_day(debt, today)
    while principal > 0 and d < until_day:
        interest = line_interest(principal, debt.rate_bp, every)
        part = max(0, min(principal, debt.monthly_debt_service_fen - interest))
        if part == 0 and interest == 0:
            break
        principal -= part
        out.append(DebtPayment(debt.id, d, part, interest, principal))
        d += every
    return out


def service_months_end(debt: DebtPosition, today: int, until_day: int) -> int | None:
    """The last day whose month still carries the debt's fixed service in the ratio: the day the schedule clears the
    principal, or None when it is not cleared before `until_day`. A debt with nothing left is cleared today."""
    if debt.principal_fen <= 0:
        return today
    pays = debt_payments(debt, today, until_day)
    if pays and pays[-1].remaining == 0:
        return pays[-1].day
    return None


__all__ = ["DebtPayment", "debt_payments", "first_payment_day", "service_months_end"]
