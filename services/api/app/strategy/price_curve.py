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

import logging
from bisect import bisect_left, bisect_right
from collections.abc import Callable
from fractions import Fraction
from itertools import pairwise
from typing import Literal, NamedTuple

from app.alerts import AlertKind, alerts
from app.api.presentation import Lang, t, when_text
from app.books import Books, current_books
from app.domain.models import Contract, FundingActionKind, Mandate
from app.domain.money import fmt_pct, fmt_yuan, round_half_up
from app.domain.ports import LedgerStore
from app.financial.concessions import recurring_issue_days
from app.financial.debts import debt_payments
from app.funding import NoPermanentSourceError, plan
from app.funding.rates import break_even_cost_share
from app.funding.router import shared_runs
from app.funding.search import GRID_STEP_FEN
from app.strategy.impact import scenario_inflow
from app.strategy.no_plan import plan_is_missing

log = logging.getLogger(__name__)

WINDOW_DAYS = 30
MIN_CARRY_DAYS = 30  # the shortest carry the ceiling prices: one billing period
MAX_EXTRA_EVALUATIONS = 120  # the bisection budget beyond the band ends (a band it cannot settle is `varies`)


class PriceBand(Contract):
    """Arrival days `from_day..to_day` (inclusive, absolute) share one value."""

    from_day: int
    to_day: int
    value_fen: int
    value_bp: int  # the value as bp of the amount
    varies: bool = False
    above_guard: bool = False  # the value is above the sanity ceiling (`_ceiling_fen`): kept, never refused


class PriceCurve(Contract):
    amount_fen: int = GRID_STEP_FEN
    window_days: int = WINDOW_DAYS
    day: int  # today: the first arrival day the curve covers
    bands: list[PriceBand]
    flat: bool  # no arrival day is worth anything: earlier cash saves nothing today
    no_plan: bool = False  # no committed plan covers the shortfall: nothing is priced, `bands` is empty and `flat` is false
    source_state_version: int
    hypothetical: Literal[True] = True


# ---------------------------------------------------------------- the costs and the bands


def _event_days(books: Books, day: int, last: int) -> set[int]:
    """Every day money moves on the books: a flow, a receivable's due day, a recurring invoice's issue day plus its
    terms, a payment of an existing debt."""
    state = books.state
    events = {f.day for f in state.flows}
    events |= {r.due_day for r in state.receivables if r.status in ("OPEN", "FINANCED") and r.outstanding_fen > 0}
    for rec in state.recurring_invoices:
        events |= {issue + rec.terms_days for issue in recurring_issue_days(rec, day, last + 1)}
    for debt in state.debts:
        events |= {p.day for p in debt_payments(debt, day, last + 1)}
    return events


def _sample_days(books: Books, mandate: Mandate, store: LedgerStore, day: int, last: int) -> list[int]:
    """The arrival days the plan's cost is read on first: today and the last day a value reads (`end + 30`), every
    breach episode's first and recovery day and every plan action's repay and landing day. Between two of them the
    cost is taken as settled when both read the same; when they differ the span is cut at the event days inside it
    (`_hints`) and then bisected."""
    marks = {day, last}
    for a in alerts(books.state, mandate, store, day):
        if a.kind != AlertKind.RESERVE_BREACH_AHEAD:
            continue
        if a.day is not None:
            marks.add(a.day)
        recovery = a.inputs.get("last_day", "")
        if recovery.isdigit():
            marks.add(int(recovery) + 1)  # the recovery day: the first day back above the floor
    for action in plan(books.state, books.with_([]), mandate).actions:
        marks |= {d for d in (action.repay_day, action.lands_day) if d is not None}
    return sorted(m for m in marks if day <= m <= last)


def _hints(books: Books, day: int, last: int) -> list[int]:
    """Where a span whose ends disagree is cut first: each event day and the day after it (an arrival after the money
    has moved is the one that no longer helps)."""
    return sorted({d for e in _event_days(books, day, last) for d in (e, e + 1) if day <= d <= last})


class _Run(NamedTuple):
    """Arrival days `first..last` whose cost is `costs`: one figure when settled, the two figures read at the span's ends
    when the budget could not settle it."""

    first: int
    last: int
    costs: tuple[int, ...]


def _settle(a: int, b: int, cost: Callable[[int], int], hints: list[int], spent: Callable[[], bool]) -> list[_Run]:
    """The runs covering `a..b-1` (the cost at `a` and `b` is read): equal ends take the one figure; unequal ends are cut
    at an event day inside the span (the middle one; the middle day when there is none) until the two sides of the step
    are adjacent days. Out of budget, the span is one unsettled run."""
    ca, cb = cost(a), cost(b)
    if ca == cb:
        return [_Run(a, b - 1, (ca,))]
    if b == a + 1:
        return [_Run(a, a, (ca,))]
    if spent():
        return [_Run(a, b - 1, (ca, cb))]
    inside = hints[bisect_right(hints, a):bisect_left(hints, b)]
    mid = inside[len(inside) // 2] if inside else (a + b) // 2
    return _settle(a, mid, cost, hints, spent) + _settle(mid, b, cost, hints, spent)


def _carry_days(books: Books, mandate: Mandate, day: int) -> int:
    """The longest carry the plan holds on these books: the latest day a borrowing action is repaid (the horizon end when
    it is carried, because the router repays a credit-line draw only where every later closing stays above the floor,
    as `trajectory._repay_carried` does) less the earliest day one lands, at least `MIN_CARRY_DAYS`. An invoice advance
    is repaid on its receivable's receipt and is not counted: its carry is the two billing periods the ceiling never
    goes below."""
    end = day + mandate.horizon_days
    carries = [(a.repay_day if a.repay_day is not None else end, a.lands_day if a.lands_day is not None else a.day)
               for a in plan(books.state, books.with_([]), mandate).actions
               if a.kind in (FundingActionKind.DRAW, FundingActionKind.DISCOUNT_BILL)]
    if not carries:
        return MIN_CARRY_DAYS
    return max(MIN_CARRY_DAYS, max(repaid for repaid, _ in carries) - min(landed for _, landed in carries))


def _ceiling_fen(books: Books, mandate: Mandate, amount_fen: int, day: int) -> int | None:
    """A sanity guard on what a 30-day shift of `amount_fen` can save: the marginal source's cost of carrying the money
    for as long as the plan carries it on these books (`_carry_days`), never less than two billing periods (60 days).
    Two periods are the golden books' answer: invoice financing bills whole periods and the oracle's day-34 point
    (¥178.22) is exactly two. A bank line carried to the horizon end costs more than that, and the curve's value is
    then the whole carry."""
    try:
        two_periods, _, _ = break_even_cost_share(books.state, mandate, 2 * WINDOW_DAYS)
        share, _, _ = break_even_cost_share(books.state, mandate, _carry_days(books, mandate, day))
    except NoPermanentSourceError:
        return None
    return round_half_up(max(two_periods, share) * amount_fen)


def price_curve(books: Books, mandate: Mandate, *, store: LedgerStore, day: int) -> PriceCurve:
    amount = GRID_STEP_FEN
    end = day + mandate.horizon_days
    last = end + WINDOW_DAYS  # the latest arrival day a value reads
    held = store.commitments()
    with shared_runs():
        standing = plan(books.state, books.with_([]), mandate)
    if plan_is_missing(standing):  # a plan cost of 0 here is no plan, not a price: nothing can be priced against it
        return PriceCurve(amount_fen=amount, day=day, bands=[], flat=False, no_plan=True,
                          source_state_version=books.state.state_version)
    costs: dict[int, int] = {}

    def cost(arrival: int) -> int:
        """The plan's cost with `amount` arriving on `arrival`: what `marginal_impact` reads of one side, the router's
        COMMITTED plan for that copy of the books under the live commitments. Each arrival day is planned once."""
        if arrival not in costs:
            state = scenario_inflow(books, amount, arrival).state
            with shared_runs():
                costs[arrival] = plan(state, current_books(state, held).with_([]), mandate).total_cost_fen
        return costs[arrival]

    samples = _sample_days(books, mandate, store, day, last)
    hints = _hints(books, day, last)
    for x in samples:  # the sampled days first: the bisection budget only gates what comes after
        cost(x)
    budget = len(costs) + MAX_EXTRA_EVALUATIONS
    runs: list[_Run] = [r for a, b in pairwise(samples)
                        for r in _settle(a, b, cost, hints, lambda: len(costs) + 1 > budget)]
    runs.append(_Run(last, last, (cost(last),)))

    def costs_at(x: int) -> tuple[int, ...]:
        return runs[bisect_right([r.first for r in runs], x) - 1].costs

    # a value reads the cost on d + 30 less the cost on d, so it can step where either cost does
    starts = sorted({day} | {c for r in runs for c in (r.first, r.first - WINDOW_DAYS) if day <= c <= end})
    pieces: list[tuple[int, int, int, bool]] = []
    for i, a in enumerate(starts):
        b = (starts[i + 1] - 1) if i + 1 < len(starts) else end
        far, near = costs_at(a + WINDOW_DAYS), costs_at(a)
        # an unsettled run is read at both its ends (the smaller value is kept, the band is marked `varies`)
        pieces.append((a, b, min(far[0] - near[0], far[-1] - near[-1]), len(far) > 1 or len(near) > 1))
    merged: list[tuple[int, int, int, bool]] = []
    for a, b, v, varies in pieces:
        if merged and not varies and not merged[-1][3] and merged[-1][2] == v:
            merged[-1] = (merged[-1][0], b, v, False)
        else:
            merged.append((a, b, v, varies))
    ceiling = _ceiling_fen(books, mandate, amount, day)
    bands = [PriceBand(from_day=a, to_day=b, value_fen=v, varies=varies, value_bp=round_half_up(Fraction(v * 10_000, amount)),
                       above_guard=ceiling is not None and v > ceiling) for a, b, v, varies in merged]
    if any(b.above_guard for b in bands):  # never a refusal: the band keeps its value and the sentence stands
        log.warning("the cash price curve values days %s above the cost of funds for the plan's carry (%s fen)",
                    ", ".join(f"{b.from_day}..{b.to_day} at {b.value_fen} fen" for b in bands if b.above_guard), ceiling)
    return PriceCurve(amount_fen=amount, day=day, bands=bands, flat=not any(b.value_fen > 0 for b in bands),
                      source_state_version=books.state.state_version)


# ---------------------------------------------------------------- the sentence


NO_PLAN_SENTENCE = (
    "No committed funding plan covers the shortfall, so earlier cash cannot be priced against borrowing: collect first.",
    "目前没有已承诺的融资方案能补上缺口，所以无法拿更早到账的现金与借款成本比较：请先催收。")


def _next(day_last: int, today: int, lang: Lang) -> str:
    """"in the next 30 days" for an arrival no later than `day_last` (today and tomorrow are said as such)."""
    n = day_last - today
    if n <= 1:
        return t(lang, f"arriving by {when_text(day_last, today, 'en')}" if n == 1 else "arriving today",
                 f"最迟{when_text(day_last, today, 'zh')}到账" if n == 1 else "今天到账")
    return t(lang, f"in the next {n} days", f"未来 {n} 天内到账")


def price_sentence(curve: PriceCurve, *, today: int, lang: Lang) -> str:
    """The curve in one sentence for the owner: the funding cost that cash saves, in yuan first and the percentage in
    brackets, until when, then nothing (business words: distances from today, never a day number, never the engine's
    vocabulary; the cost is named so that it does not read as a rate charged)."""
    if curve.no_plan:
        return t(lang, *NO_PLAN_SENTENCE)
    live = [b for b in curve.bands if b.value_fen > 0]
    if not live:
        return t(lang, "Earlier cash saves you nothing today.", "现在更早到账的现金不会为你节省任何费用。")
    per = f"¥{curve.amount_fen // 100:,}"
    first = live[0]
    en_first = f"Cash {_next(first.to_day, today, 'en')} saves you {fmt_yuan(first.value_fen)} of funding cost per {per}"
    zh_first = f"{_next(first.to_day, today, 'zh')}的现金，每 {per} 为您节省 {fmt_yuan(first.value_fen)} 的融资成本"
    pct = fmt_pct(Fraction(first.value_bp, 10_000))
    if len(live) == 1:
        return t(lang, f"{en_first} ({pct}); after that, earlier cash saves nothing.",
                 f"{zh_first}（{pct}）；之后更早到账也不再节省。")
    en, zh = f"{en_first} ({pct})", f"{zh_first}（{pct}）"
    prev = first
    rest = live[1:]
    i = 0
    while i < len(rest):
        b = rest[i]
        # a run of one-day bands, each the day after the last, is one taper (the value moving a little each day, as
        # when early cash also retires a small drawn balance for one day fewer): one clause, not one per day
        j = i
        while (j + 1 < len(rest) and rest[j].from_day == rest[j].to_day and rest[j + 1].from_day == rest[j + 1].to_day
               and rest[j + 1].from_day == rest[j].to_day + 1):
            j += 1
        if b.from_day == prev.to_day + 1 and j > i:
            last = rest[j]
            n = last.to_day - prev.to_day
            lo, hi = fmt_pct(Fraction(b.value_bp, 10_000)), fmt_pct(Fraction(last.value_bp, 10_000))
            span = lo if lo == hi else f"{lo}–{hi}"
            en += f", then {fmt_yuan(b.value_fen)} falling day by day to {fmt_yuan(last.value_fen)} ({span}) over the {n} days after"
            zh += f"，随后的 {n} 天从 {fmt_yuan(b.value_fen)} 逐日降至 {fmt_yuan(last.value_fen)}（{span}）"
            prev, i = last, j + 1
            continue
        pct = fmt_pct(Fraction(b.value_bp, 10_000))
        n = b.to_day - prev.to_day
        if b.from_day == prev.to_day + 1:
            days = "day" if n == 1 else f"{n} days"  # "for the day after", never "for the 1 days after"
            en += f", then {fmt_yuan(b.value_fen)} ({pct}) for the {days} after"
            zh += f"，随后的 {n} 天为 {fmt_yuan(b.value_fen)}（{pct}）"
        else:  # a stretch worth nothing lies between the two
            en += f", then {fmt_yuan(b.value_fen)} ({pct}) {_next(b.to_day, today, 'en')}"
            zh += f"，{_next(b.to_day, today, 'zh')}的为 {fmt_yuan(b.value_fen)}（{pct}）"
        prev, i = b, i + 1
    return t(lang, en + "; later, nothing.", zh + "；再之后没有。")


def money_line(curve: PriceCurve, lang: Lang) -> str:
    """The same sentence for the cards on the other two pages (the curve carries its own day)."""
    return price_sentence(curve, today=curve.day, lang=lang)


__all__ = ["PriceBand", "PriceCurve", "money_line", "price_curve", "price_sentence"]
