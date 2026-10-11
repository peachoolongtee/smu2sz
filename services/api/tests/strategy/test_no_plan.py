"""The shared "no committed plan" state (map #58, ticket #79) on the golden books: there is always a plan to price
against on day 0 and day 34, so nothing the oracles pin is a no-plan answer."""

from __future__ import annotations

from app.api.runtime import Runtime
from app.books import Books
from app.funding import plan
from app.strategy.no_plan import no_committed_plan, plan_is_missing
from app.strategy.price_curve import NO_PLAN_SENTENCE, PriceCurve, price_sentence


def test_the_golden_books_have_a_committed_plan_on_day_0_and_day_34(
        books_day0: Books, rt_day0: Runtime, books_day34: Books, rt_day34: Runtime) -> None:
    assert not no_committed_plan(books_day0, rt_day0.store.get_mandate())
    assert not no_committed_plan(books_day34, rt_day34.store.get_mandate())
    assert not plan_is_missing(plan(books_day34.state, books_day34.with_([]), rt_day34.store.get_mandate()))


def test_a_curve_with_no_plan_is_one_sentence_in_each_language() -> None:
    curve = PriceCurve(day=14, bands=[], flat=False, no_plan=True, source_state_version=1)
    assert price_sentence(curve, today=14, lang="en") == NO_PLAN_SENTENCE[0]
    assert price_sentence(curve, today=14, lang="zh") == NO_PLAN_SENTENCE[1]
    assert "saves you nothing" not in NO_PLAN_SENTENCE[0]
