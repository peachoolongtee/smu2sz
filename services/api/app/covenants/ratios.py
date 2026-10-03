"""Exact covenant ratios (ADR-0002: compared exactly, displayed to 2 dp half-up). The one place they are computed.

DSCR     = monthly EBITDA / monthly debt service (the engine's service: fixed service of existing debt, posted interest
           and fees, amortising principal, bullet term loans on a level basis, ADR-0008)
Leverage = month-end debt / (12 x monthly EBITDA), where debt = DebtPosition principal + the drawn balances of the
           facilities that count in leverage (a lot not yet landed counts from its request day, since it is owed from
           then). A committed line's undrawn room is not debt (docs/FINANCIAL_SEMANTICS.md section 5).

Every reported ratio is `ratios_for(basis)` of a basis that carries (ebitda_fen, debt_service_fen, total_debt_fen):
a projection's `MonthPoint` (the projection fills those figures by the rule above), or a `Basis` that `pro_forma`
builds from such a point (or from the books today) plus an estimated change, labelled as an estimate by its caller.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol

from app.domain.models import FinancialState
from app.domain.money import Ratio, round_half_up


class RatioBasis(Protocol):
    """What a ratio is computed from: a `MonthPoint` satisfies it, so does `Basis`."""

    @property
    def ebitda_fen(self) -> int: ...
    @property
    def debt_service_fen(self) -> int: ...
    @property
    def total_debt_fen(self) -> int: ...


@dataclass(frozen=True)
class Basis:
    """Monthly EBITDA, monthly debt service and debt, in fen: the inputs of one ratio reading."""

    ebitda_fen: int
    debt_service_fen: int
    total_debt_fen: int


def dscr_value(monthly_ebitda_fen: int, monthly_debt_service_fen: int) -> Fraction | None:
    """EBITDA / DS, exactly. None when debt service is zero (no debt to service)."""
    if monthly_debt_service_fen == 0:
        return None
    return Fraction(monthly_ebitda_fen, monthly_debt_service_fen)


def leverage_value(total_debt_fen: int, monthly_ebitda_fen: int) -> Fraction | None:
    """Debt / (12 x EBITDA), exactly. None when EBITDA <= 0 (leverage is undefined; a caller
    testing a leverage limit must treat that as a breach whenever there is debt)."""
    if monthly_ebitda_fen <= 0:
        return None
    return Fraction(total_debt_fen, 12 * monthly_ebitda_fen)


def ratios(
    monthly_ebitda_fen: int, monthly_debt_service_fen: int, total_debt_fen: int
) -> tuple[Ratio | None, Ratio]:
    """(DSCR, leverage), exact. DSCR is None when debt service is zero.

    Raises ValueError when EBITDA <= 0, because leverage is then undefined (a negative value would
    silently pass a maximum)."""
    lev = leverage_value(total_debt_fen, monthly_ebitda_fen)
    if lev is None:
        raise ValueError("leverage is undefined for non-positive EBITDA")
    d = dscr_value(monthly_ebitda_fen, monthly_debt_service_fen)
    return (Ratio.of(d) if d is not None else None), Ratio.of(lev)


def ratios_or_undefined(
    monthly_ebitda_fen: int, monthly_debt_service_fen: int, total_debt_fen: int
) -> tuple[Ratio | None, Ratio | None]:
    """(DSCR, leverage), exact, without raising. Leverage is None when EBITDA <= 0 (undefined); DSCR is
    None when debt service is zero. A caller testing a limit must treat an undefined leverage as a
    breach whenever there is debt."""
    lev = leverage_value(total_debt_fen, monthly_ebitda_fen)
    d = dscr_value(monthly_ebitda_fen, monthly_debt_service_fen)
    return (Ratio.of(d) if d is not None else None), (Ratio.of(lev) if lev is not None else None)


def ratios_for(basis: RatioBasis) -> tuple[Ratio | None, Ratio | None]:
    """(DSCR, leverage) of one basis: a projection's month point or a `pro_forma` basis. Never raises."""
    return ratios_or_undefined(basis.ebitda_fen, basis.debt_service_fen, basis.total_debt_fen)


def leverage_debt_fen(state: FinancialState) -> int:
    """Debt on the books today by the leverage rule: DebtPosition principal + every drawn balance of a facility that
    counts in leverage (the projection's opening position; its month points then move it day by day)."""
    return (sum(d.principal_fen for d in state.debts)
            + sum(f.drawn_fen for f in state.facilities if f.counts_in_leverage))


def book_basis(state: FinancialState) -> Basis:
    """The books today: monthly EBITDA, the fixed monthly service of `state.debts`, and `leverage_debt_fen`."""
    return Basis(state.monthly_ebitda_fen, sum(d.monthly_debt_service_fen for d in state.debts),
                 leverage_debt_fen(state))


def pro_forma(
    base: RatioBasis | FinancialState,
    extra_debt_fen: int = 0,
    extra_monthly_debt_service_fen: int = 0,
    extra_monthly_ebitda_fen: int = 0,
) -> tuple[Ratio | None, Ratio | None]:
    """(DSCR, leverage) of `base` plus an estimated change, by `ratios_for`. `base` is a projection's month point
    (preferred) or the books today (`book_basis`). The extras are estimates (a principal before its structure is
    projected, the receivables a terms extension ties up): the caller labels the result as an estimate."""
    b = book_basis(base) if isinstance(base, FinancialState) else base
    return ratios_for(with_extra(b, extra_debt_fen, extra_monthly_debt_service_fen, extra_monthly_ebitda_fen))


def with_extra(base: RatioBasis, extra_debt_fen: int = 0, extra_monthly_debt_service_fen: int = 0,
               extra_monthly_ebitda_fen: int = 0) -> Basis:
    """`base` plus an estimated change, as a `Basis` (for a caller that also shows the inputs)."""
    return Basis(base.ebitda_fen + extra_monthly_ebitda_fen, base.debt_service_fen + extra_monthly_debt_service_fen,
                 base.total_debt_fen + extra_debt_fen)


def worst_dscr[B: RatioBasis](months: Iterable[B]) -> B | None:
    """The month with the lowest defined DSCR (the earliest on a tie); None when no month has debt service."""
    best: tuple[Fraction, B] | None = None
    for m in months:
        d, _ = ratios_for(m)
        if d is not None and (best is None or d.value < best[0]):
            best = (d.value, m)
    return best[1] if best else None


def worst_leverage[B: RatioBasis](months: Iterable[B]) -> B | None:
    """The month with the highest defined leverage (the earliest on a tie); None when EBITDA <= 0 in every month."""
    best: tuple[Fraction, B] | None = None
    for m in months:
        _, lev = ratios_for(m)
        if lev is not None and (best is None or lev.value > best[0]):
            best = (lev.value, m)
    return best[1] if best else None


def fmt_x(x: Fraction) -> str:
    """Exact ratio to a 2 dp, half-up display string: 113/100 -> '1.13x'."""
    q = round_half_up(x * 100)
    sign = "-" if q < 0 else ""
    q = abs(q)
    return f"{sign}{q // 100}.{q % 100:02d}x"


def fmt_exact(x: Fraction) -> str:
    """The exact value, for violation inputs: '9000000/7983060'."""
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)
