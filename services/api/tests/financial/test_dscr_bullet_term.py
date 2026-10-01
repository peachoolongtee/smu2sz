"""ADR-0008: monthly debt service counts a bullet term loan on a level basis (principal + interest + fees
spread evenly over `term_months`, the remainder in the last month). Nothing else about debt service moves."""

from __future__ import annotations

from fractions import Fraction

from app.covenants import evaluate
from app.domain.models import FacilityStatus, Mode, ViolationCode
from app.financial import amortisation_schedule, project
from app.financial.charges import line_interest
from tests.financial.builders import draw, early_pay, finance

C = Mode.CONSERVATIVE
BASE = 4_500_000  # existing debt service, fen a month
PRINCIPAL = 50_000_000
MONTH = 30


def _with(state, **per_facility):
    """The state with the named facilities COMMITTED and optionally changed: FAC=dict(update)."""
    out = []
    for f in state.facilities:
        if f.id in per_facility:
            f = f.model_copy(update={"status": FacilityStatus.COMMITTED, **per_facility[f.id]})
        out.append(f)
    return state.model_copy(update={"facilities": out})


def _extra(t, first, last):
    """Debt service above the existing debt's, for months first..last."""
    return [t.months[m - 1].debt_service_fen - BASE for m in range(first, last + 1)]


def _level(total: int, n: int) -> list[int]:
    q, r = divmod(total, n)
    return [q] * (n - 1) + [q + r]


# ---------------------------------------------------------------- 1. the ADR's case


def test_adr_case_500k_12_month_guaranteed_loan(state):
    s = _with(state, **{"FAC-GGL": {}})
    t = project(s, [], [draw("FAC-GGL", PRINCIPAL, repay_day=None)], C, 120, 0)
    # the loan lands on day 21 (21-day lead time) and is repaid 360 days later, as the ADR counts
    interest = t.interest_posted_fen
    assert t.fees_posted_fen == 0
    assert interest == line_interest(PRINCIPAL, 500, 360) == 2_465_753  # ¥24,657.53
    assert t.horizon_days == 21 + 360 + 1 and len(t.months) == 13

    level = _level(PRINCIPAL + interest, 12)
    assert level[0] == 4_372_146  # ¥43,721.46
    assert _extra(t, 1, 12) == level
    assert all(t.months[m - 1].debt_service_fen == BASE + level[m - 1] for m in range(1, 13))
    assert sum(_extra(t, 1, 12)) == PRINCIPAL + interest + t.fees_posted_fen  # exact
    assert t.months[12].debt_service_fen == BASE  # the repayment month holds nothing more

    for m in range(1, 13):
        dscr = t.months[m - 1].dscr.value
        assert dscr < Fraction(5, 4)
        assert Fraction(101, 100) < dscr < Fraction(102, 100)  # about 1.014
    assert t.months[0].dscr.value == Fraction(9_000_000, BASE + 4_372_146)


def test_upfront_fee_is_part_of_the_level_amount(state):
    s = _with(state, **{"FAC-GGL": {"upfront_fee_bp": 100}})
    t = project(s, [], [draw("FAC-GGL", PRINCIPAL, repay_day=None)], C, 120, 0)
    assert t.fees_posted_fen == 500_000
    assert _extra(t, 1, 12) == _level(PRINCIPAL + t.interest_posted_fen + 500_000, 12)
    assert sum(_extra(t, 1, 12)) == PRINCIPAL + t.interest_posted_fen + t.fees_posted_fen


# ---------------------------------------------------------------- 2. nothing else moves (hard-coded from dev)

_TWO = Fraction(2)
_BEFORE = {
    "none": [(4_500_000, 150_000_000, _TWO)] * 4,
    "v2": [(4_500_000, 186_000_000, _TWO), (4_771_294, 150_000_000, Fraction(4_500_000, 2_385_647)),
           (4_500_000, 150_000_000, _TWO), (4_500_000, 150_000_000, _TWO)],
    "v1": [(4_500_000, 165_000_000, _TWO), (4_584_164, 150_000_000, Fraction(2_250_000, 1_146_041)),
           (4_500_000, 150_000_000, _TWO), (4_500_000, 150_000_000, _TWO)],
    "line45": [(4_500_000, 165_000_000, _TWO), (4_618_356, 150_000_000, Fraction(750_000, 384_863)),
               (4_500_000, 150_000_000, _TWO), (4_500_000, 150_000_000, _TWO)],
}


def _months(t):
    return [(p.debt_service_fen, p.total_debt_fen, p.dscr.value) for p in t.months]


def test_projections_without_a_bullet_term_facility_are_unchanged(state):
    cases = {
        "none": [],
        "v2": [draw(), finance()],
        "v1": [draw(), early_pay(21_000_000, 120)],
        "line45": [draw(repay_day=45)],
    }
    for name, actions in cases.items():
        t = project(state, [], actions, C, 120, 0)
        assert t.horizon_days == 120
        assert _months(t) == _BEFORE[name], name


# ---------------------------------------------------------------- 3. credit line, 4. amortising


def test_credit_line_draw_is_unchanged(state):
    # FAC-LINE: BULLET with no term_months. Principal is not debt service; interest counts when it posts.
    t = project(state, [], [draw("FAC-LINE", 15_000_000, repay_day=32)], C, 120, 0)
    assert t.interest_posted_fen > 0
    assert _extra(t, 1, 4) == [0, t.interest_posted_fen, 0, 0]
    assert t.interest_posted_fen == 84_164 and t.months[1].debt_service_fen == 4_584_164


def test_amortising_facility_is_unchanged(state):
    s = _with(state, **{"FAC-ETL": {}})
    etl = next(f for f in s.facilities if f.id == "FAC-ETL")
    t = project(s, [], [draw("FAC-ETL", 36_000_000, repay_day=None)], C, 120, 0)
    arrival = etl.lead_time_days
    expect: dict[int, int] = {}
    for row in amortisation_schedule(36_000_000, etl.rate_bp, etl.term_months):
        m = max(1, -(-(arrival + MONTH * row.month) // MONTH))
        expect[m] = expect.get(m, 0) + row.payment
    assert t.interest_posted_fen == sum(r.interest for r in amortisation_schedule(36_000_000, etl.rate_bp, etl.term_months))
    for m, p in enumerate(t.months, start=1):
        assert p.debt_service_fen == BASE + expect.get(m, 0)


# ---------------------------------------------------------------- 5. 6-month bullet, 6. beyond the horizon, 7. two lots


def test_six_month_bullet_is_spread_over_six_months(state):
    s = _with(state, **{"FAC-GGL": {"term_months": 6}})
    t = project(s, [], [draw("FAC-GGL", PRINCIPAL, repay_day=None)], C, 120, 0)
    interest = t.interest_posted_fen
    assert interest == line_interest(PRINCIPAL, 500, 180)
    level = _level(PRINCIPAL + interest, 6)
    assert _extra(t, 1, 6) == level
    assert sum(level) == PRINCIPAL + interest
    assert _extra(t, 7, len(t.months)) == [0] * (len(t.months) - 6)


def test_loan_maturing_after_the_horizon_is_still_tested(state):
    s = _with(state, **{"FAC-GGL": {}})
    t = project(s, [], [draw("FAC-GGL", PRINCIPAL, repay_day=None)], C, 30, 0)  # a 30-day look, a 360-day loan
    level = _level(PRINCIPAL + t.interest_posted_fen, 12)
    assert len(t.months) >= 12
    assert _extra(t, 1, 12) == level
    assert all(t.months[m - 1].dscr.value < Fraction(5, 4) for m in range(1, 13))


def test_two_lots_in_different_months_each_have_their_own_schedule(state):
    s = _with(state, **{"FAC-GGL": {}})
    a, b = 20_000_000, 10_000_000
    t = project(s, [], [draw("FAC-GGL", a, day=0, repay_day=None), draw("FAC-GGL", b, day=40, repay_day=None)],
                C, 120, 0)
    # lots land on days 21 (month 1) and 61 (month 3)
    la = _level(a + line_interest(a, 500, 360), 12)
    lb = _level(b + line_interest(b, 500, 360), 12)
    for m in range(1, len(t.months) + 1):
        expect = (la[m - 1] if 1 <= m <= 12 else 0) + (lb[m - 3] if 3 <= m <= 14 else 0)
        assert t.months[m - 1].debt_service_fen == BASE + expect, m
    assert sum(_extra(t, 1, len(t.months))) == a + b + t.interest_posted_fen


# ---------------------------------------------------------------- 8. the covenant sees it


def test_a_funded_trajectory_with_the_guaranteed_loan_breaches_dscr(state, mandate):
    s = _with(state, **{"FAC-GGL": {}})
    t = project(s, [], [draw("FAC-GGL", PRINCIPAL, repay_day=None)], C, 120, 0)
    v = evaluate(t, s.facilities, mandate)
    breaches = [x for x in v if x.code == ViolationCode.DSCR_BREACH]
    assert {x.month for x in breaches} == set(range(1, 13))
    assert all(x.observed == "1.01x" and x.limit == "1.25x" for x in breaches)
    # without the loan the same books raise none
    base = project(s, [], [], C, 120, 0)
    assert not [x for x in evaluate(base, s.facilities, mandate) if x.code == ViolationCode.DSCR_BREACH]
