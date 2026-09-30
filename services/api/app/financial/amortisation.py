"""Level-payment amortisation (ADR-0002).

Monthly rate is r/12. The payment is rounded half-up once. Each month's interest is
post(balance × r/12). Every payment but the last is the level payment; the last clears the balance.
"""

from __future__ import annotations

from fractions import Fraction
from typing import NamedTuple

from app.domain.money import bp, post


class AmortisationRow(NamedTuple):
    month: int
    payment: int
    interest: int
    principal: int
    balance: int  # after this payment


def _check(principal_fen: int, rate_bp: int, months: int) -> None:
    if months < 1:
        raise ValueError("months must be at least 1")
    if principal_fen < 0:
        raise ValueError("principal must not be negative")
    if rate_bp < 0:
        raise ValueError("rate must not be negative")


def annuity_payment(principal_fen: int, rate_bp: int, months: int) -> int:
    """Level monthly payment in fen: P·r/(1 − (1+r)^−n) with r = rate/12, rounded half-up."""
    _check(principal_fen, rate_bp, months)
    r = bp(rate_bp) / 12
    if r == 0:
        return post(Fraction(principal_fen, months))
    return post(Fraction(principal_fen) * r / (1 - 1 / (1 + r) ** months))


def amortisation_schedule(principal_fen: int, rate_bp: int, months: int) -> list[AmortisationRow]:
    """Rows of (month, payment, interest, principal, balance). The final payment clears the balance."""
    payment = annuity_payment(principal_fen, rate_bp, months)
    r = bp(rate_bp) / 12
    balance = principal_fen
    rows: list[AmortisationRow] = []
    for m in range(1, months + 1):
        interest = post(balance * r)
        principal = payment - interest if m < months else balance
        balance -= principal
        rows.append(AmortisationRow(m, interest + principal, interest, principal, balance))
    return rows
