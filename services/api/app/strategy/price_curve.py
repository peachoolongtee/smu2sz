"""The cash price curve: what ¥10,000 arriving 30 days earlier is worth, by arrival day (docs/STRATEGY_MVP_BRIEF.md
section 5.1), as bands and one sentence.

For an arrival day `d` the value is the collections spike's definition: the plan's cost with the money arriving on
`d + 30` less its cost with it arriving on `d` (`marginal_impact` of two `scenario_inflow` copies), so it is the saving
of having the same cash 30 days earlier. Read-only and hypothetical: nothing is booked, stored or executed.

The days are cut where the answer can change (the breach episodes' first and recovery days, the plan's repayment and
landing days, today and the end of the horizon, each with a day either side), the value is read at each band's two
ends and a band whose ends disagree is bisected until the step sits between two adjacent days. A band the evaluation
budget could not settle is reported `varies` with the smaller value.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import Literal

from app.alerts import AlertKind, alerts
from app.api.presentation import Lang, t, when_text
from app.books import Books
from app.domain.models import Contract, Mandate
from app.domain.money import fmt_pct, round_half_up
from app.domain.ports import LedgerStore
from app.funding import NoPermanentSourceError, plan
from app.funding.rates import break_even_cost_share
from app.funding.search import GRID_STEP_FEN
from app.strategy.impact import marginal_impact, scenario_inflow

WINDOW_DAYS = 30
MAX_EXTRA_EVALUATIONS = 120  # the bisection budget beyond the band ends (a band it cannot settle is `varies`)


class PriceBand(Contract):
    """Arrival days `from_day..to_day` (inclusive, absolute) share one value."""

    from_day: int
    to_day: int
    value_fen: int
    value_bp: int  # the value as bp of the amount
    varies: bool = False


class PriceCurve(Contract):
    amount_fen: int = GRID_STEP_FEN
    window_days: int = WINDOW_DAYS
    day: int  # today: the first arrival day the curve covers
    bands: list[PriceBand]
    flat: bool  # no arrival day is worth anything: earlier cash saves nothing today
    source_state_version: int
    hypothetical: Literal[True] = True


class _OutOfBudget(Exception):
    pass


# ---------------------------------------------------------------- the bands


def _boundaries(books: Books, mandate: Mandate, store: LedgerStore, day: int, end: int) -> list[int]:
    """The days a band starts on: today, today + 1, the end, every breach episode's first and recovery day, every
    plan action's repay and landing day, each with a day either side, kept inside `day..end`."""
    marks = {day, end}
    for a in alerts(books.state, mandate, store, day):
        if a.kind != AlertKind.RESERVE_BREACH_AHEAD:
            continue
        if a.day is not None:
            marks.add(a.day)
        last = a.inputs.get("last_day", "")
        if last.isdigit():
            marks.add(int(last) + 1)  # the recovery day: the first day back above the floor
    for action in plan(books.state, books.with_([]), mandate).actions:
        for d in (action.repay_day, action.lands_day):
            if d is not None:
                marks.add(d)
    starts = {day, day + 1} | {m + k for m in marks for k in (-1, 0, 1)}
    return sorted(s for s in starts if day <= s <= end)


def _settle(a: int, b: int, value: Callable[[int], int], seen: dict[int, int], budget: int) -> list[tuple[int, int, int, bool]]:
    """Bands covering `a..b` as (from, to, value, varies): equal ends take the value; unequal ends are bisected until the
    two sides of the step are adjacent days. Over budget, the span is one `varies` band with the smaller value."""
    va, vb = value(a), value(b)
    if va == vb:
        return [(a, b, va, False)]
    if b == a + 1:
        return [(a, a, va, False), (b, b, vb, False)]
    mid = (a + b) // 2
    if len(seen) + 2 > budget:
        return [(a, b, min(va, vb), True)]
    return _settle(a, mid, value, seen, budget) + _settle(mid + 1, b, value, seen, budget)


def _ceiling_fen(books: Books, mandate: Mandate, amount_fen: int) -> int | None:
    """The most a 30-day shift of `amount_fen` can save: the marginal source's cost of carrying the money for two billing
    periods (60 days). One period (30 days, ¥89.11 per ¥10,000 on the golden books) is the brief's bound, but invoice
    financing bills whole periods and the oracle's own day-34 point is ¥178.22, exactly two."""
    try:
        share, _, _ = break_even_cost_share(books.state, mandate, 2 * WINDOW_DAYS)
    except NoPermanentSourceError:
        return None
    return round_half_up(share * amount_fen)


def price_curve(books: Books, mandate: Mandate, *, store: LedgerStore, day: int) -> PriceCurve:
    amount = GRID_STEP_FEN
    end = day + mandate.horizon_days
    seen: dict[int, int] = {}

    def value(d: int) -> int:
        if d not in seen:
            mi = marginal_impact(scenario_inflow(books, amount, d + WINDOW_DAYS), scenario_inflow(books, amount, d),
                                 mandate, store=store, day=day)
            seen[d] = -mi.posted_cost_delta_fen
        return seen[d]

    starts = _boundaries(books, mandate, store, day, end)
    spans = [(s, (starts[i + 1] - 1) if i + 1 < len(starts) else end) for i, s in enumerate(starts)]
    for s, e in spans:  # the ends of every band first: the bisection budget only gates what comes after
        value(s)
        value(e)
    budget = len(seen) + MAX_EXTRA_EVALUATIONS
    pieces = [p for s, e in spans for p in _settle(s, e, value, seen, budget)]
    merged: list[tuple[int, int, int, bool]] = []
    for a, b, v, varies in pieces:
        if merged and not varies and not merged[-1][3] and merged[-1][2] == v:
            merged[-1] = (merged[-1][0], b, v, False)
        else:
            merged.append((a, b, v, varies))
    ceiling = _ceiling_fen(books, mandate, amount)
    bands = []
    for a, b, v, varies in merged:
        if ceiling is not None and v > ceiling:
            raise RuntimeError(f"the cash price curve values days {a}..{b} at {v} fen, above the cost of funds "
                               f"for two billing periods ({ceiling} fen)")
        bands.append(PriceBand(from_day=a, to_day=b, value_fen=v, varies=varies,
                               value_bp=round_half_up(Fraction(v * 10_000, amount))))
    return PriceCurve(amount_fen=amount, day=day, bands=bands, flat=not any(b.value_fen > 0 for b in bands),
                      source_state_version=books.state.state_version)


# ---------------------------------------------------------------- the sentence


def _within(day_last: int, today: int, lang: Lang) -> str:
    """"within the next 30 days" for an arrival no later than `day_last` (today and tomorrow are said as such)."""
    n = day_last - today
    if n <= 1:
        return t(lang, f"by {when_text(day_last, today, 'en')}" if n == 1 else "today",
                 f"最迟{when_text(day_last, today, 'zh')}" if n == 1 else "今天")
    return t(lang, f"within the next {n} days", f"未来 {n} 天内")


def price_sentence(curve: PriceCurve, *, today: int, lang: Lang) -> str:
    """The curve in one sentence for the owner: the highest worth, until when, then nothing (Business words: distances
    from today, never a day number, never the engine's vocabulary)."""
    live = [b for b in curve.bands if b.value_fen > 0]
    if not live:
        return t(lang, "Earlier cash saves you nothing today.", "现在更早到账的现金不会为你节省任何费用。")
    first = live[0]
    if len(live) == 1:
        pct = fmt_pct(Fraction(first.value_bp, 10_000))
        return t(lang,
                 f"Cash arriving {_within(first.to_day, today, 'en')} is worth {pct} to you; after that, nothing.",
                 f"{_within(first.to_day, today, 'zh')}到账的现金对你价值 {pct}；之后则没有。")
    en = f"Cash arriving {_within(first.to_day, today, 'en')} is worth {fmt_pct(Fraction(first.value_bp, 10_000))} to you"
    zh = f"{_within(first.to_day, today, 'zh')}到账的现金对你价值 {fmt_pct(Fraction(first.value_bp, 10_000))}"
    for b in live[1:]:
        pct = fmt_pct(Fraction(b.value_bp, 10_000))
        en += f", then {pct} if it arrives {_within(b.to_day, today, 'en')}"
        zh += f"，{_within(b.to_day, today, 'zh')}到账的为 {pct}"
    return t(lang, en + "; after that, nothing.", zh + "；之后则没有。")


def money_line(curve: PriceCurve, lang: Lang) -> str:
    """The same sentence for the cards on the other two pages (the curve carries its own day)."""
    return price_sentence(curve, today=curve.day, lang=lang)


__all__ = ["PriceBand", "PriceCurve", "money_line", "price_curve", "price_sentence"]
