"""Formula text for ledger events and valuations. Display only: never feeds a calculation."""

from __future__ import annotations

from fractions import Fraction

from app.domain.money import FEN_PER_YUAN, round_half_up


def y(fen: int) -> str:
    """84164 -> '841.64'; -4504000 -> '−45,040.00'. Yuan without the currency sign."""
    sign = "−" if fen < 0 else ""
    whole, part = divmod(abs(fen), FEN_PER_YUAN)
    return f"{sign}{whole:,}.{part:02d}"


def pct(rate: Fraction, places: int = 4) -> str:
    """Exact rate to a short percentage: 6.4%, 1.2%, ≈10.8417% (inexact values get '≈')."""
    scaled = rate * 100 * 10**places
    q = round_half_up(scaled)
    whole, part = divmod(abs(q), 10**places)
    text = f"{whole}.{part:0{places}d}".rstrip("0").rstrip(".")
    sign = "-" if q < 0 else ""
    approx = "" if Fraction(q) == scaled else "≈"
    return f"{approx}{sign}{text}%"


def day(d: int) -> str:
    return f"day {d}" if d >= 0 else f"day −{-d}"
