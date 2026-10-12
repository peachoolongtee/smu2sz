"""The buyer-exposure Demo figures, in one place (map #88, ticket #96, brief J.2). Foshan, EX01, golden books on day 0, and
the demo path at day 34. Each figure is derived in docs/research/customer-economics-2026-10-10 (r4 section 3 and 7 for
capacity, r2 for the stress) and recomputed here from the kernel; the detailed tests live in test_capacity.py,
test_spare_capacity.py and test_stress.py.

PART A (this ticket's capacity and stress half). Part B (concentration, payments, the inputs) adds its own section below."""

from __future__ import annotations

from app.books import Books
from app.strategy.capacity import capacity_before_after, snapshot, spare_capacity
from app.strategy.impact import scenario_paid_late, stress

from .exposure_books import ASKED, OPTION_A, OPTION_B, OWNER_KEY, golden

FOSHAN = "BUYER-1"


# ---------------------------------------------------------------- part A: capacity and the late-payment stress


def test_part_a_foshan_thirty_days_late_has_no_admissible_committed_plan():
    books, mandate = golden()
    row = stress(books, mandate, FOSHAN, (30,), 0, ())[0]
    assert row.lowest_fen == -25_000_000 and row.lowest_day == 60  # -¥250,000 on day 60 (30 Nov)
    assert row.breach_days == 65  # 65 days below the minimum (20 on the contractual terms)
    assert row.need_fen == 55_000_000  # a ¥550,000 need
    assert row.plan_admissible is False and row.plan_cost_fen is None  # no admissible committed plan


def test_part_a_additional_need_flow_could_still_support():
    books, mandate = golden()

    def x(package) -> int | None:
        return spare_capacity(books, mandate, 0, (), package, trusted_owner_key_hex=OWNER_KEY).x_star_fen

    assert x(None) == 8_100_000  # ¥81,000: the finance advance-rate cap on RCV-A
    assert x(ASKED) == 1_400_000  # ¥14,000 if EX01 is accepted as asked: the line's ¥14,960 of room
    assert x(OPTION_A) == 0  # ¥0 under Option A: the line has ¥13.80 until 1 Nov
    assert x(OPTION_B) == 6_200_000  # ¥62,000 under Option B: the line in the second gap


def test_part_a_option_a_keeps_thirteen_yuan_eighty_of_the_line_to_day_31():
    books, mandate = golden()
    after = capacity_before_after(books, mandate, OPTION_A, 0, (), trusted_owner_key_hex=OWNER_KEY).after
    assert after is not None
    line = next(w for w in after.windows if w.dimension == "credit_line")
    assert (line.today_fen, line.through_day, line.recovers_day) == (1_380, 31, 32)


def test_part_a_the_finance_headroom_is_336000_less_255000():
    books, mandate = golden()
    today = next(w for w in snapshot(books, mandate, 0).windows if w.dimension == "invoice_finance" and w.reading == "TODAY")
    assert today.today_fen == 33_600_000 - 25_500_000 == 8_100_000


def test_part_a_day_34_rcv_a_is_two_days_overdue_and_a_zero_day_stress_does_not_move_it(books_day34: Books):
    state = books_day34.state
    rcv_a = next(r for r in state.receivables if r.id == "RCV-A")
    assert (state.as_of_day, rcv_a.due_day) == (34, 32)
    sc = scenario_paid_late(books_day34, FOSHAN, 0, 34)
    assert any(r.id == "RCV-A" for r in sc.state.receivables)
    assert "LATE:RCV-A" not in {f.id for f in sc.state.flows}
