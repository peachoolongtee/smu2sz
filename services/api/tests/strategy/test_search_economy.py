"""The envelope and the worth ranking read the same figures with fewer verifier and planner runs (map #58, ticket #78).

Three savings, each pinned by what it must not change: (1) the envelope's searches read a setting's verdict without the
counters the verifier builds only for a refused offer (`_Verifier.quick`); (2) the rebate search starts from the
forward-concession arithmetic even when the verifier's totals are rounded to the fen; (3) the early-payment ceiling is
found from the bottom of the rate grid (`collections._last_true`), and the books as they stand are read once for every
receipt the ranking measures. The figures themselves are pinned by the oracle fixtures, `test_envelope`, `test_collections`
and the backtest; these tests pin that the shortcuts agree with the long way."""

from __future__ import annotations

import itertools
from functools import partial
from typing import Any

import pytest

from app.api.runtime import Runtime
from app.books import Books
from app.strategy import envelope as E
from app.strategy.collections import _last_true
from app.strategy.impact import marginal_impact, read_books, scenario_received


def _bisect_from_the_top(values: list[int], ok: Any) -> int | None:
    """The search `_last_true` replaced (the collections spike's)."""
    if not ok(values[0]):
        return None
    lo, hi = 0, len(values) - 1
    if not ok(values[hi]):
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(values[mid]):
                lo = mid
            else:
                hi = mid
    else:
        lo = hi
    return values[lo]


@pytest.mark.parametrize("n", [2, 3, 4, 7, 16, 17, 31, 40])
def test_the_rate_search_finds_every_boundary_the_bisection_from_the_top_finds(n: int) -> None:
    values = list(range(0, 5 * n, 5))
    for boundary in range(-1, n):  # -1: nothing but rate 0 passes ... n-1: every rate passes
        passes = lambda v, b=boundary: v == 0 or v <= 5 * b
        assert _last_true(values, passes) == _bisect_from_the_top(values, passes), (n, boundary)


def test_the_rate_search_reads_a_boundary_near_zero_in_about_three_evaluations() -> None:
    seen: list[int] = []

    def ok(v: int) -> bool:
        seen.append(v)
        return v == 0 or v <= 10

    assert _last_true(list(range(0, 80, 5)), ok) == 10
    assert len(seen) <= 4, seen  # rate 0, then 5, 15 (fails), 10: a bisection from the top took six


def test_a_rate_search_with_nothing_above_zero_reads_one_rate() -> None:
    assert _last_true([0, 5, 10], lambda v: v == 0) == 0
    assert _last_true([0], lambda v: True) == 0
    assert _last_true([0, 5], lambda v: False) is None


@pytest.fixture(scope="module")
def verifiers(rt_day0: Runtime, books_day0: Books) -> Any:
    mandate, held = rt_day0.store.get_mandate(), tuple(rt_day0.store.commitments())
    ctx = E.open_context(books_day0.state, rt_day0.day, "BUYER-1")
    ranges = E.ranges_for(ctx, mandate)

    def make() -> E._Verifier:
        return E._Verifier(books_day0, mandate, rt_day0.owner_key_hex, rt_day0.day, held, ctx, ranges)

    return make


SETTINGS = [
    E.Setting(45), E.Setting(50), E.Setting(55), E.Setting(60), E.Setting(55, price=30),
    E.Setting(45, discount=85, face=26_000_000), E.Setting(45, discount=100), E.Setting(45, rebate=125),
    E.Setting(45, rebate=130), E.Setting(55, price=30, rebate=40),
]
SAME = ("passes", "approved", "liquidity_only", "forward_total_fen", "codes", "binding", "reserve_day", "reserve_curable",
        "cure_cost_fen", "cure_needs_owner", "cure_cannot_run_today", "plan_cost_fen", "recheck")


def test_a_quick_reading_agrees_with_the_whole_answer_on_everything_a_search_reads(verifiers: Any) -> None:
    quick, whole = verifiers(), verifiers()
    outcomes = set()
    for s in SETTINGS:
        q, w = quick.quick(s), whole.probe(s)
        outcomes.add(w.passes)
        assert {k: getattr(q, k) for k in SAME} == {k: getattr(w, k) for k in SAME}, s
        if w.passes:  # nothing is refused, so nothing was left out: the same probe, counters and all
            assert q == w and quick.memo[quick.norm(s)] == w
        else:
            assert q.counters == () and quick.norm(s) in quick.failed
    assert outcomes == {True, False}, "the list holds settings that pass and settings that do not"


def test_a_refused_setting_is_read_whole_when_it_is_shown_and_then_equals_the_direct_reading(verifiers: Any) -> None:
    again, direct = verifiers(), verifiers()
    for s in SETTINGS:
        again.quick(s)
    for s in SETTINGS:
        assert again.probe(s) == direct.probe(s), s
    assert not again.failed and not again.routers
    assert again.evaluations == direct.evaluations == len({again.norm(s) for s in SETTINGS})


def test_the_rebate_hint_survives_totals_the_verifier_rounds_to_the_fen(verifiers: Any) -> None:
    v = verifiers()
    base = v.quick(E.Setting(v.cur))
    hint = v.rebate_hint(base)
    assert hint == 125  # the oracle's largest rebate (1.25%); the totals are 500,000 fen at 125 bp and not a whole step apart
    assert v.probe(E.Setting(v.cur, rebate=hint)).passes and not v.probe(E.Setting(v.cur, rebate=hint + 5)).passes


def test_marginal_impact_is_the_same_with_the_books_read_beforehand(rt_day0: Runtime, books_day0: Books) -> None:
    mandate = rt_day0.store.get_mandate()
    before = read_books(books_day0, mandate, rt_day0.store, rt_day0.day)
    open_ids = [r.id for r in books_day0.state.receivables if r.status == "OPEN" and r.outstanding_fen > 0]
    assert open_ids
    for rid in itertools.islice(open_ids, 2):
        scenario = scenario_received(books_day0, rid, rt_day0.day)
        plain = marginal_impact(books_day0, scenario, mandate, store=rt_day0.store, day=rt_day0.day)
        given = marginal_impact(books_day0, scenario, mandate, store=rt_day0.store, day=rt_day0.day, before_reading=before)
        assert plain == given


@pytest.mark.parametrize("n", [1, 2, 3, 7, 12])
def test_the_terms_search_with_top_first_reads_the_same_maximum_in_at_most_four_runs(n: int) -> None:
    """P5 (ticket #98): a passing top is checked by one middle probe and the neighbour below it, so a lever with no wall costs four
    runs instead of two (fewer than the plain search on the 13-step terms range; the weekly scan guards the rest)."""
    values = [90 + 5 * i for i in range(n)]
    for boundary in range(-1, n):  # -1: nothing passes ... n-1: every value passes
        plain: list[int] = []
        quick: list[int] = []

        def counting(seen: list[int], v: int, at: int = boundary) -> bool:
            seen.append(v)
            return v <= 90 + 5 * at

        whole = E.last_true(values, partial(counting, plain), gallop=True)
        shortcut = E.last_true(values, partial(counting, quick), gallop=True, top_first=True)
        assert whole == shortcut, (n, boundary)
        if boundary == n - 1 and n > 1:
            assert len(quick) <= 4  # the first value, the top, the middle and the neighbour below the top, and nothing past the top
            if n >= 12:
                assert len(quick) < len(plain)


def test_the_early_payment_search_from_the_bottom_reads_the_same_maximum(verifiers: Any) -> None:
    discounts = list(range(0, 155, 5))
    for boundary in (0, 5, 10, 15, 60, 150):
        passes = lambda d, b=boundary: d <= b
        assert E.last_true(discounts, passes, gallop=True) == E.last_true(discounts, passes), boundary
