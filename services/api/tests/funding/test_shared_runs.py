"""The speed-ups of one evaluation change no figure: shared router searches, the exact pruning bound and the
rank comparison that builds action keys only on a tie."""

from __future__ import annotations

from fractions import Fraction
from random import Random
from unittest.mock import patch

import pytest

import app.funding.router as router_mod
from app.domain.models import FundingAction, FundingActionKind
from app.funding import compare, plan
from app.funding.router import shared_runs
from app.funding.search import Probe, Search, _Bound, _rank_not_before
from tests.funding import cases

NAMES = ["bill_held", "dear_line", "cheap_early_pay", "leverage_tight", "long_gap"]


class _Counted(Search):
    runs = 0

    def run(self) -> None:
        type(self).runs += 1
        super().run()


@pytest.mark.parametrize("name", NAMES)
def test_shared_runs_change_no_plan_and_no_row(name):
    s, m = getattr(cases, name)()
    alone = (plan(s, [], m), plan(s, [], m, "EXPECTED"), compare(s, [], m))
    with shared_runs():
        shared = (plan(s, [], m), plan(s, [], m, "EXPECTED"), compare(s, [], m))
        again = (plan(s, [], m), plan(s, [], m, "EXPECTED"), compare(s, [], m))
    assert shared == alone == again


def test_shared_runs_search_once_per_input_and_only_inside_the_block():
    s, m = cases.bill_held()
    _Counted.runs = 0
    with patch.object(router_mod, "Search", _Counted):
        plan(s, [], m)
        plan(s, [], m)
        assert _Counted.runs == 2  # outside the block every call runs its own search
        _Counted.runs = 0
        with shared_runs():
            plan(s, [], m)
            compare(s, [], m)  # the same books, the same basis: the finished search is reused
            plan(s, [], m, "EXPECTED")  # another basis is another question
            with shared_runs():  # a nested block joins the outer one
                plan(s, [], m)
            assert _Counted.runs == 2
        _Counted.runs = 0
        plan(s, [], m)
        assert _Counted.runs == 1  # nothing outlives the block


def test_shared_runs_do_not_mix_different_books():
    s, m = cases.bill_held()
    s2, _ = cases.dear_line()
    with shared_runs():
        a, b = plan(s, [], m), plan(s2, [], m)
    assert a == plan(s, [], m) and b == plan(s2, [], m) and a != b


def test_bound_is_the_fraction_it_stands_for():
    rng = Random(7)
    for _ in range(500):
        unit = Fraction(rng.randint(0, 10_000_000), rng.randint(1, 10_000_000))
        amount, other, cost = rng.randint(1, 9_000_000), rng.randint(1, 9_000_000), rng.randint(0, 5_000_000)
        d = unit.denominator * 100
        one = _Bound(unit.numerator * amount * 98 - 2 * d, d)
        exact = unit * amount * Fraction(98, 100) - 2
        two = one + _Bound(unit.numerator * other * 98 - 2 * d, d)
        assert (one > cost) == (exact > cost)
        assert (two > cost) == (exact + (unit * other * Fraction(98, 100) - 2) > cost)
        assert (cost + one > cost + 5) == (cost + exact > cost + 5)


def _probe(rng: Random) -> Probe:
    act = FundingAction(kind=FundingActionKind.DRAW, facility_id=f"F{rng.randint(0, 2)}", day=0,
                        amount_fen=rng.randint(1, 3) * 100_000)
    return Probe((act,) * rng.randint(1, 2), ok=True, cost=rng.randint(0, 2), peak_debt=rng.randint(0, 2),
                 needs_approval=bool(rng.randint(0, 1)), unrunnable=bool(rng.randint(0, 1)))


def test_rank_comparison_equals_the_full_rank_tuple_comparison():
    rng = Random(3)
    for _ in range(2000):
        a, b = _probe(rng), _probe(rng)
        assert _rank_not_before(a, b) == (a.rank() >= b.rank())
