"""Small wording helpers the exposure statements share (concentration, payment behaviour): a buyer's short name, a whole-yuan
amount, an exact share at 1 dp. Words only; nothing here prices or decides."""

from __future__ import annotations

from fractions import Fraction

from app.api.presentation import Lang, t
from app.domain.money import fmt_pct, fmt_yuan, round_half_up

BP_FULL = 10_000


def buyer_short(name: str) -> str:
    """The name an owner says aloud: its first word ("Foshan Home Retail Co." -> "Foshan"); a one-word name stays whole."""
    words = name.replace(",", " ").split()
    return words[0] if words else name


def whole_yuan(fen: int) -> str:
    """¥420,000 for a whole number of yuan, ¥420,000.50 otherwise: the figure as the brief's sentences write it."""
    return fmt_yuan(fen).removesuffix(".00")


def share_bp(x: Fraction) -> int:
    """An exact share in [0, 1] as integer basis points, half-up (ADR-0002), in [0, 10000]. A share below 1 is never shown
    as 10000 and a share above 0 never as 0: the rounding must not hide the difference between "all" and "nearly all"."""
    if x >= 1:
        return BP_FULL
    r = round_half_up(x * BP_FULL)
    if x > 0 and r == 0:
        return 1
    return min(r, BP_FULL - 1)


def share_text(x: Fraction, lang: Lang = "en") -> str:
    """An exact share at 1 dp, half-up: "33.3%". "100%" only when the share is exactly 1 and "0%" only at exactly 0; a share the
    rounding would push to 100.0% reads "over 99.9%" and one it would round to 0.0% reads "under 0.1%". Parts are never adjusted
    to add to 100."""
    if x >= 1:
        return "100%"
    if x <= 0:
        return "0%"
    text = fmt_pct(x, 1)
    if text == "100.0%":
        return t(lang, "over 99.9%", "高于 99.9%")
    if text == "0.0%":
        return t(lang, "under 0.1%", "低于 0.1%")
    return text
