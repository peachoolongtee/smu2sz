"""Exact covenant ratios (ADR-0002: compared exactly, displayed to 2 dp half-up).

DSCR     = monthly EBITDA / monthly debt service
Leverage = total debt / (12 x monthly EBITDA)
"""

from __future__ import annotations

from fractions import Fraction

from app.domain.models import FinancialState
from app.domain.money import Ratio, round_half_up


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
    None when debt service is zero. For callers that must report an undefined basis instead of failing
    (capex, the extension pro-forma). A caller testing a limit must treat an undefined leverage as a
    breach whenever there is debt."""
    lev = leverage_value(total_debt_fen, monthly_ebitda_fen)
    d = dscr_value(monthly_ebitda_fen, monthly_debt_service_fen)
    return (Ratio.of(d) if d is not None else None), (Ratio.of(lev) if lev is not None else None)


def pro_forma(
    state: FinancialState,
    extra_debt_fen: int = 0,
    extra_monthly_debt_service_fen: int = 0,
    extra_monthly_ebitda_fen: int = 0,
    base_extra_debt_fen: int = 0,
) -> tuple[Ratio | None, Ratio]:
    """Pro-forma (DSCR, leverage) on the verified state plus a hypothetical change.

    Base debt = sum of `state.debts` principal + `base_extra_debt_fen` (e.g. a drawn line limit).
    Base debt service = sum of `state.debts` monthly debt service. EBITDA = state EBITDA + extra."""
    debt = sum(d.principal_fen for d in state.debts) + base_extra_debt_fen + extra_debt_fen
    ds = sum(d.monthly_debt_service_fen for d in state.debts) + extra_monthly_debt_service_fen
    ebitda = state.monthly_ebitda_fen + extra_monthly_ebitda_fen
    return ratios(ebitda, ds, debt)


def fmt_x(x: Fraction) -> str:
    """Exact ratio to a 2 dp, half-up display string: 113/100 -> '1.13x'."""
    q = round_half_up(x * 100)
    sign = "-" if q < 0 else ""
    q = abs(q)
    return f"{sign}{q // 100}.{q % 100:02d}x"


def fmt_exact(x: Fraction) -> str:
    """The exact value, for violation inputs: '9000000/7983060'."""
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)
