"""The envelope shows only what passes its own re-check (ticket #98 with #97's envelope items, P2; brief E.2).

The displayed packages and the zone's smallest price are filtered by `approved` (the verifier passes the package and the counter
re-check, `counters.infeasibility`, finds nothing wrong), not by `passes`; a failure is kept only in the full grid. And the
wall a step runs into is named for what it is: with the caps ignored, a covenant or a funding code is never called "the cap for
this buyer".

No fixture's books today have a package the verifier passes and the re-check refuses: the verifier's own curable reading
already refuses a fix that cannot land by the shortfall day on every variant tried (the invoice dates moved, the opening cash
lowered). So the books here are the golden ones with the day-47 fix made late the way such books make it: the invoice the
advance is drawn on is issued after the shortfall (`counters.late_legs`, the re-check's own test, reports it so), and the
re-check then refuses every package that leans on that fix.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

import pytest

from app.api.runtime import Runtime
from app.books import Books
from app.strategy.envelope import EnvelopeAnswer, Probe, Setting, envelope_answer, envelope_facts, wall_of
from app.verifier.evaluate import clear_caches

GOLDEN_BUYER = "BUYER-1"
counter_module = importlib.import_module("app.verifier.counters")  # the module: the package re-exports a function of that name


def _late(plan: Any, state: Any, day: int) -> list[str]:
    """The fix's advance is drawn on an invoice issued after the shortfall day: it cannot land in time."""
    if plan is None or getattr(plan, "executable_now", True):
        return []
    return [f"RI:BUYER-1:62 is issued on day {day + 15}"]


@pytest.fixture(scope="module")
def late_fix(rt_day0: Runtime, books_day0: Books) -> Iterator[EnvelopeAnswer]:
    mp = pytest.MonkeyPatch()
    mp.setattr(counter_module, "late_legs", _late)
    clear_caches()  # the verifier's memo must not hand these verdicts to another module, nor take its own from one
    try:
        facts = envelope_facts(books_day0, rt_day0.store.get_mandate(), store=rt_day0.store, day=rt_day0.day,
                               buyer_id=GOLDEN_BUYER, trusted_owner_key_hex=rt_day0.owner_key_hex,
                               commitments=tuple(rt_day0.store.commitments()), zone=True)
        yield envelope_answer(facts, "en")
    finally:
        mp.undo()
        clear_caches()


def test_a_package_whose_fix_cannot_land_in_time_is_not_shown(late_fix):
    shown = [*late_fix.packages, *late_fix.more]
    assert shown, "the packages that need no fix are still shown"
    assert all(p.approved and p.authority in ("flow_may", "needs_owner") for p in shown)
    # every 50- and 55-day package leans on the day-47 fix: none is shown; the terms in force are
    assert {p.package.terms_days for p in shown} == {45}
    assert any(p.package.early_pay_bp == 85 and p.package.early_pay_face_fen == 26_000_000 for p in shown)  # Option A


def test_the_zones_smallest_price_counts_only_approved_packages(late_fix):
    zone = {z.terms_days: z for z in late_fix.zone}
    for days in (50, 55):
        z = zone[days]
        assert z.min_price_bp is None and not z.passes_within_range and z.lowest_price_words == "none works"
        assert not z.at_that_price.approved
    assert zone[45].min_price_bp == 0 and zone[45].lowest_price_words == "no price rise needed"


def test_the_longest_terms_with_a_price_rise_fall_back_to_the_terms_in_force(late_fix):
    lever = next(lv for lv in late_fix.levers if lv.key == "terms_with_price")
    assert lever.maximum == 45


# ---------------------------------------------------------------- the wall's label


def _failing(*codes: str) -> Probe:
    return Probe(setting=Setting(60), outcome="REJECT", tier="TIER_1", passes=False, liquidity_only=False, codes=codes,
                 binding=codes, forward_total_fen=0, reserve_day=None, reserve_curable=None, cure_cost_fen=None,
                 cure_needs_owner=False, cure_cannot_run_today=False, counters=(), counter_costs_fen=(), plan_cost_fen=None,
                 recheck=None)


@pytest.mark.parametrize(("codes", "wall"), [
    (("DSCR_BREACH",), "covenant"),
    (("LEVERAGE_BREACH",), "covenant"),
    (("CLEAN_DOWN_BREACH",), "covenant"),
    (("UNCOMMITTED_FACILITY",), "funding"),
    (("LEAD_TIME_TOO_LONG",), "funding"),
    (("TIER3_COLLATERAL",), None),
    (("AGG_CONCESSION_EXCEEDED",), None),
    (("RESERVE_BREACH", "DSCR_BREACH"), "liquidity"),
])
def test_with_the_caps_ignored_no_wall_is_called_a_cap(codes, wall):
    assert wall_of(_failing(*codes), ignore_caps=True) == wall


def test_with_the_caps_counted_the_caps_still_come_first():
    assert wall_of(_failing("PER_BUYER_CAP_EXCEEDED", "DSCR_BREACH")) == "buyer cap"
    assert wall_of(_failing("AGG_CONCESSION_EXCEEDED")) == "forward budget"
    assert wall_of(_failing("LEVERAGE_BREACH")) == "covenant"


def test_the_new_walls_are_worded_in_both_languages():
    from app.strategy.envelope import _WALL_TEXT, _WALL_WORDS

    for table in (_WALL_TEXT, _WALL_WORDS):
        assert table["covenant"] == ("your loan covenants", "您的贷款契约")
        assert table["funding"] == ("funding that can arrive in time", "能及时到位的资金")
