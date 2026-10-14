"""Step 1 of capex mode: is the investment worth doing? (spec v2 §7.7, ADR-0002)

NPV discounts each month at the effective monthly rate (1+h)^(1/12) − 1. That rate is irrational,
so it is carried in 50-digit Decimal and the NPV is rounded to the fen exactly once (money.post).
Payback is the first month the undiscounted cumulative cash flow is no longer negative.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction

from app.domain.money import BP_DENOM, post

NPV_PRECISION = 50


def uplift_in_month(month: int, monthly_uplift_fen: int, start_month: int, life_months: int) -> int:
    """The owner's estimated operating cash flow in `month` (1-based): flat from `start_month`
    through `life_months`, zero otherwise."""
    return monthly_uplift_fen if start_month <= month <= life_months else 0


def npv_fen(price_fen: int, monthly_uplift_fen: int, start_month: int, life_months: int, hurdle_bp: int) -> int:
    """−price + Σ_{m=start}^{life} uplift / (1 + r_m)^m, r_m = (1 + hurdle)^(1/12) − 1; rounded once."""
    with localcontext() as ctx:
        ctx.prec = NPV_PRECISION
        h = Decimal(hurdle_bp) / Decimal(BP_DENOM)
        rm = (1 + h) ** (Decimal(1) / Decimal(12)) - 1
        total = -Decimal(price_fen)
        for m in range(start_month, life_months + 1):
            total += Decimal(monthly_uplift_fen) / (1 + rm) ** m
        return post(Fraction(total))


def effective_monthly_rate_text(hurdle_bp: int, places: int = 6) -> str:
    """(1 + h)^(1/12) − 1 as a percentage string, for the formula display only."""
    with localcontext() as ctx:
        ctx.prec = NPV_PRECISION
        rm = (1 + Decimal(hurdle_bp) / Decimal(BP_DENOM)) ** (Decimal(1) / Decimal(12)) - 1
        return f"{(rm * 100).quantize(Decimal(1).scaleb(-places))}%"


def payback_month(price_fen: int, monthly_uplift_fen: int, start_month: int, life_months: int) -> int | None:
    """First month m with −price + Σ_{k≤m} uplift_k ≥ 0, or None if it never happens within the life."""
    cumulative = -price_fen
    for m in range(1, life_months + 1):
        cumulative += uplift_in_month(m, monthly_uplift_fen, start_month, life_months)
        if cumulative >= 0:
            return m
    return None


# ---------------------------------------------------------------- ADR-0013: the price paid on a schedule


def payment_month(day: int, today: int, month_days: int = 30) -> int:
    """The month (from today) a payment on `day` falls in: 0 for today, else ceil((day − today) / 30), so month m covers
    days today + 30(m−1) + 1 .. today + 30m, the engine's own month."""
    return 0 if day <= today else -(-(day - today) // month_days)


def npv_schedule_fen(payments: list[tuple[int, int]], monthly_uplift_fen: int, start_month: int, life_months: int,
                     hurdle_bp: int) -> int:
    """−Σ payment_k / (1 + r_m)^(month_k) + Σ_{m=start}^{life} uplift / (1 + r_m)^m; `payments` are (month, fen). One
    payment in month 0 is exactly `npv_fen`. 50-digit Decimal, rounded once."""
    with localcontext() as ctx:
        ctx.prec = NPV_PRECISION
        h = Decimal(hurdle_bp) / Decimal(BP_DENOM)
        rm = (1 + h) ** (Decimal(1) / Decimal(12)) - 1
        total = Decimal(0)
        for month, fen in payments:
            total -= Decimal(fen) / (1 + rm) ** month
        for m in range(start_month, life_months + 1):
            total += Decimal(monthly_uplift_fen) / (1 + rm) ** m
        return post(Fraction(total))


def payback_month_schedule(payments: list[tuple[int, int]], monthly_uplift_fen: int, start_month: int,
                           life_months: int) -> int | None:
    """The first month m from which the undiscounted cumulative cash flow (uplift in, payments out as they fall) stays at
    or above zero through the life; None if it never does. One payment in month 0 is exactly `payback_month`."""
    by_month: dict[int, int] = {}
    for month, fen in payments:
        by_month[month] = by_month.get(month, 0) + fen
    cumulative = -by_month.get(0, 0)
    points: list[tuple[int, int]] = []
    for m in range(1, life_months + 1):
        cumulative += uplift_in_month(m, monthly_uplift_fen, start_month, life_months) - by_month.get(m, 0)
        points.append((m, cumulative))
    late = sum(fen for month, fen in by_month.items() if month > life_months)  # paid after the life: never recovered
    first: int | None = None
    for m, c in points:
        if c - late >= 0:
            first = m if first is None else first
        else:
            first = None
    return first
