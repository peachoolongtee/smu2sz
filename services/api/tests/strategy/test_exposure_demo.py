"""The buyer-exposure Demo's headline figures, in one place (map #88, ticket #96, brief J.2): Foshan, EX01, the golden books on
day 0. Each figure is derived in docs/research/customer-economics-2026-10-10 (r4 sections 3 and 7 for capacity, r2 for the stress)
and recomputed here from the kernel.

Only the two figures the brief quotes are repeated here. The detail lives where it is tested: the capacity windows (the credit
line's ¥13.80 to day 31, the ¥81,000 finance headroom) in test_capacity.py, the spare-capacity search in test_spare_capacity.py,
the stress and the day-34 overdue invoice in test_stress.py, the shares in test_concentration.py, how Foshan has paid in
test_payments.py, and the whole block through the routes in tests/api/test_exposure_routes.py."""

from __future__ import annotations

from app.strategy.capacity import spare_capacity
from app.strategy.impact import stress

from .exposure_books import ASKED, OPTION_A, OPTION_B, OWNER_KEY, financed_golden, golden

FOSHAN = "BUYER-1"


def test_foshan_thirty_days_late_has_no_admissible_committed_plan():
    books, mandate = golden()
    row = stress(books, mandate, FOSHAN, (30,), 0, ())[0]
    assert row.lowest_fen == -25_000_000 and row.lowest_day == 60  # -¥250,000 on day 60 (30 Nov)
    assert row.breach_days == 65  # 65 days below the minimum (20 on the contractual terms)
    assert row.need_fen == 55_000_000  # a ¥550,000 need
    assert row.plan_admissible is False and row.plan_cost_fen is None  # no admissible committed plan


def test_the_unfinanced_demo_figures_do_not_move_when_a_financed_invoice_is_modelled():
    """Ticket #107: a financed invoice is now stressed too. The Demo's day-0 books finance nothing, so the figures above stand
    unchanged; the same stress on the books with RCV-A's advance arranged (ARRANGED, landing on day 3) has the lender paid
    out of the late receipt, with the extra period's charges, and reads:"""
    row = stress(financed_golden(False), golden()[1], FOSHAN, (30,), 0, ())[0]
    assert (row.lowest_fen, row.lowest_day, row.breach_days, row.need_fen) == (500_000, 60, 57, 29_500_000)
    assert row.plan_admissible is False


def test_the_additional_need_flow_could_still_support():
    books, mandate = golden()

    def x(package) -> int | None:
        return spare_capacity(books, mandate, 0, (), package, trusted_owner_key_hex=OWNER_KEY).x_star_fen

    assert x(None) == 8_100_000  # ¥81,000: the finance advance-rate cap on RCV-A
    assert x(ASKED) == 1_400_000  # ¥14,000 if EX01 is accepted as asked: the line's ¥14,960 of room
    assert x(OPTION_A) == 200_000  # ¥2,000 under Option A: the line has ¥2,790 until 1 Nov (face rounded to ¥260,000, R-10)
    assert x(OPTION_B) == 6_200_000  # ¥62,000 under Option B: the line in the second gap
