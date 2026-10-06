"""Canonical money arithmetic. The only place rounding happens (ADR-0002).

- Amounts are integer fen (1 yuan = 100 fen). Never float.
- Rates are integer basis points (1% = 100 bp) on input; derived rates are exact Fractions.
- Intermediate results are exact Fractions measured in fen.
- A value is rounded to fen, half-up, exactly once: when it is posted as a cash movement,
  or when a valuation is reported. Totals are sums of already-rounded fen amounts.
- Day count is Actual/365, simple interest.
"""

from __future__ import annotations

from decimal import Decimal, getcontext
from fractions import Fraction

from pydantic import BaseModel, ConfigDict

FEN_PER_YUAN = 100
BP_DENOM = 10_000
DAYS_PER_YEAR = 365

getcontext().prec = 50


def round_half_up(x: Fraction) -> int:
    """Round an exact quantity to the nearest integer, halves away from zero."""
    sign = -1 if x < 0 else 1
    ax = abs(x)
    q, r = divmod(ax.numerator, ax.denominator)
    if 2 * r >= ax.denominator:
        q += 1
    return sign * q


def post(x: Fraction) -> int:
    """Round an exact fen quantity to integer fen. Call once, at posting or reporting."""
    return round_half_up(x)


def bp(n: int) -> Fraction:
    """Basis points to an exact fraction (640 bp -> 16/250)."""
    return Fraction(n, BP_DENOM)


def yuan(amount: int | str) -> int:
    """Yuan literal to fen, exactly. yuan('841.64') -> 84164. Rejects sub-fen input."""
    d = Decimal(str(amount)) * FEN_PER_YUAN
    if d != d.to_integral_value():
        raise ValueError(f"sub-fen amount: {amount}")
    return int(d)


def simple_interest(principal_fen: int, rate: Fraction, days: int) -> Fraction:
    """Exact Actual/365 simple interest, in fen. Not rounded."""
    return Fraction(principal_fen) * rate * days / DAYS_PER_YEAR


def pct_of(amount_fen: int, rate: Fraction) -> Fraction:
    """Exact rate x amount, in fen. Not rounded."""
    return Fraction(amount_fen) * rate


def gross_up_face(net_fen: int, discount: Fraction) -> int:
    """Invoice face whose early payment at `discount` nets `net_fen`; rounded half-up."""
    return post(Fraction(net_fen) / (1 - discount))


def annualise(cost_share: Fraction, days: int) -> Fraction:
    """A cost share over `days`, expressed as a simple annual rate."""
    return cost_share * DAYS_PER_YEAR / days


def fmt_yuan(fen: int) -> str:
    """84164 -> '¥841.64'; -4504000 -> '−¥45,040.00'."""
    sign = "−" if fen < 0 else ""
    y, f = divmod(abs(fen), FEN_PER_YUAN)
    return f"{sign}¥{y:,}.{f:02d}"


def fmt_yuan_short(fen: int) -> str:
    """Overview precision, half-up to whole thousands of yuan: 24000000 -> '¥240k', -10500000 -> '−¥105k'; under
    ¥1,000 the exact figure. For a glance only, never for a cost or a ledger figure, which keep the fen."""
    sign = "−" if fen < 0 else ""
    yuan = abs(fen) // FEN_PER_YUAN
    if yuan < 1000:
        return fmt_yuan(fen)
    thousands = (yuan + 500) // 1000
    return f"{sign}¥{thousands:,}k"


def fmt_pct(x: Fraction, places: int = 2) -> str:
    """Exact fraction to a half-up percentage string: 0.108417 -> '10.84%'."""
    scaled = round_half_up(x * 100 * 10**places)
    s = f"{abs(scaled) // 10**places}.{abs(scaled) % 10**places:0{places}d}" if places else str(abs(scaled))
    return f"{'-' if scaled < 0 else ''}{s}%"


class Ratio(BaseModel):
    """An exact ratio (DSCR, leverage, all-in rates). Compare on num/den; display with `text`."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    num: int
    den: int

    @classmethod
    def of(cls, x: Fraction) -> Ratio:
        return cls(num=x.numerator, den=x.denominator)

    @property
    def value(self) -> Fraction:
        return Fraction(self.num, self.den)

    @property
    def text(self) -> str:
        """Two decimals, half-up, signed: '1.92', '−0.50' (same minus sign as `fmt_yuan`)."""
        q = round_half_up(self.value * 100)
        sign = "−" if q < 0 else ""
        q = abs(q)
        return f"{sign}{q // 100}.{q % 100:02d}"


def ratio_from_bp(n: int) -> Ratio:
    """12500 bp -> 1.25x."""
    return Ratio.of(bp(n))
