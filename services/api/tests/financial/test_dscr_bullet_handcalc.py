"""Independent check of ADR-0008 (DSCR counts bullet term loan principal).

Every figure below is hard-coded from a hand derivation (docs/research/dscr-handcalc-2026-10-01.md), written from the ADR,
ADR-0002, the engine semantics and fixtures/scenarios/golden_sme.json BEFORE the implementation was read. No helper from
the implementation (line_interest, _level) is used to compute an expected value.

Books: EBITDA 9,000,000 fen a month; existing debt service 4,500,000 a month; FAC-GGL 5%, 12 months, lead 21 days,
bullet. Month m covers days 30(m-1)+1 .. 30m. A lot requested on day 0 lands on day 21 (month 1) and is repaid on day 381
(month 13). Interest = half-up(principal x 5% x 360/365).
"""

from __future__ import annotations

from fractions import Fraction

from app.covenants import evaluate
from app.domain.models import FacilityStatus, Mode, ViolationCode
from app.financial import project
from tests.financial.builders import draw

C = Mode.CONSERVATIVE
EBITDA = 9_000_000
BASE = 4_500_000


def _with(state, **per_facility):
    out = []
    for f in state.facilities:
        if f.id in per_facility:
            f = f.model_copy(update={"status": FacilityStatus.COMMITTED, **per_facility[f.id]})
        out.append(f)
    return state.model_copy(update={"facilities": out})


def _ds(t):
    return [p.debt_service_fen for p in t.months]


def _run(state, amounts_days, horizon=120, **ggl):
    s = _with(state, **{"FAC-GGL": ggl})
    actions = [draw("FAC-GGL", a, day=d, repay_day=None) for a, d in amounts_days]
    return s, project(s, [], actions, C, horizon, 0)


# ------------------------------------------------------------------ 2a  500,000 yuan, 12 months


def test_2a_500k_12_month_level_service(state):
    # 50,000,000 x 0.05 x 360/365 = 900,000,000 / 365 = 2,465,753.42 -> 2,465,753
    # total 52,465,753 / 12 = 4,372,146.08 -> level 4,372,146, 12 x level = 52,465,752, remainder 1 -> month 12
    _s, t = _run(state, [(50_000_000, 0)])
    assert t.interest_posted_fen == 2_465_753
    assert t.fees_posted_fen == 0
    assert t.horizon_days == 382  # last repayment day 21 + 360 = 381, plus 1
    assert len(t.months) == 13  # day 382 falls in month 13 (days 361-390)
    ds = _ds(t)
    assert ds[0:11] == [8_872_146] * 11  # 4,500,000 + 4,372,146
    assert ds[11] == 8_872_147  # + remainder 1 fen
    assert ds[12] == 4_500_000  # repayment month 13 carries nothing extra
    assert sum(ds[:12]) - 12 * BASE == 52_465_753  # exact: principal + interest


def test_2a_dscr_values_and_covenant_failure(state, mandate):
    s, t = _run(state, [(50_000_000, 0)])
    # 9,000,000 / 8,872,146 = 1.0144107 ; 9,000,000 / 8,872,147 = 1.0144106 ; month 13: 9,000,000 / 4,500,000 = 2
    for m in range(1, 12):
        assert t.months[m - 1].dscr.value == Fraction(9_000_000, 8_872_146)
    assert t.months[11].dscr.value == Fraction(9_000_000, 8_872_147)
    assert t.months[12].dscr.value == Fraction(2)
    for m in range(1, 13):
        assert Fraction(1014, 1000) <= t.months[m - 1].dscr.value < Fraction(1015, 1000)  # 1.014 to 3 dp
    breaches = [v for v in evaluate(t, s.facilities, mandate) if v.code == ViolationCode.DSCR_BREACH]
    assert {v.month for v in breaches} == set(range(1, 13))  # months 1-12 fail, month 13 passes
    assert all(v.observed == "1.01x" and v.limit == "1.25x" for v in breaches)


def test_2f_annual_ratio_matches_the_monthly_one(state):
    # 12 x 9,000,000 = 108,000,000 ; 12 x 4,500,000 + 52,465,753 = 106,465,753 ; ratio 1.0144106
    _s, t = _run(state, [(50_000_000, 0)])
    annual = Fraction(12 * EBITDA, sum(_ds(t)[:12]))
    assert sum(_ds(t)[:12]) == 106_465_753
    assert annual == Fraction(108_000_000, 106_465_753)
    assert abs(annual - t.months[0].dscr.value) < Fraction(1, 10**6)  # only the 1 fen remainder differs
    assert Fraction(101, 100) < annual < Fraction(102, 100)  # "about 1.01x"


# ------------------------------------------------------------------ 2b  6 months


def test_2b_six_month_bullet(state):
    # repaid day 21 + 180 = 201 (month 7). interest 50,000,000 x 0.05 x 180/365 = 450,000,000/365 = 1,232,876.71 -> 1,232,877
    # total 51,232,877 / 6 = 8,538,812.83 -> level 8,538,812 (6 x = 51,232,872), remainder 5 -> month 6 = 8,538,817
    _s, t = _run(state, [(50_000_000, 0)], term_months=6)
    assert t.interest_posted_fen == 1_232_877
    ds = _ds(t)
    assert ds[0:5] == [13_038_812] * 5  # 4,500,000 + 8,538,812
    assert ds[5] == 13_038_817
    assert all(x == BASE for x in ds[6:])
    assert len(t.months) >= 7
    # 9,000,000 / 13,038,812 = 0.690247
    for m in range(1, 7):
        v = t.months[m - 1].dscr.value
        assert Fraction(690, 1000) <= v < Fraction(691, 1000)
    assert t.months[0].dscr.value == Fraction(9_000_000, 13_038_812)


# ------------------------------------------------------------------ 2c  360,000 yuan (borrower-file figures)


def test_2c_360k_month_one_is_1_18_and_headroom_minus_0_07(state, mandate):
    # 36,000,000 x 0.05 x 360/365 = 648,000,000/365 = 1,775,342.47 -> 1,775,342 ; total 37,775,342
    # / 12 = 3,147,945.17 -> level 3,147,945, remainder 2 ; month 1 DS = 4,500,000 + 3,147,945 = 7,647,945
    s, t = _run(state, [(36_000_000, 0)])
    assert t.interest_posted_fen == 1_775_342
    assert _ds(t)[0] == 7_647_945
    assert _ds(t)[11] == 7_647_947
    v1 = t.months[0].dscr.value
    assert v1 == Fraction(9_000_000, 7_647_945)  # 1.17679
    assert round(float(v1), 2) == 1.18
    assert round(float(v1 - Fraction(5, 4)), 2) == -0.07  # headroom -0.0732
    breaches = [v for v in evaluate(t, s.facilities, mandate) if v.code == ViolationCode.DSCR_BREACH]
    assert {v.month for v in breaches} == set(range(1, 13))
    assert all(v.observed == "1.18x" for v in breaches)


# ------------------------------------------------------------------ 2d  two lots


def test_2d_two_lots_months_1_to_15(state):
    # lot 1: 20,000,000, int 986,301.37 -> 986,301, total 20,986,301 / 12 = 1,748,858 r5 (month 12: 1,748,863), months 1-12
    # lot 2: 10,000,000, int 493,150.68 -> 493,151, total 10,493,151 / 12 =   874,429 r3 (month 14:   874,432), months 3-14
    # lot 2 requested day 40 -> lands day 61 (month 3)
    _s, t = _run(state, [(20_000_000, 0), (10_000_000, 40)])
    assert t.interest_posted_fen == 986_301 + 493_151
    expect = [
        6_248_858, 6_248_858,  # months 1-2: 4,500,000 + 1,748,858
        *[7_123_287] * 9,  # months 3-11: + 874,429
        7_123_292,  # month 12: 4,500,000 + 1,748,863 + 874,429
        5_374_429,  # month 13: 4,500,000 + 874,429
        5_374_432,  # month 14: 4,500,000 + 874,432
        4_500_000,  # month 15
    ]
    assert len(t.months) >= 15
    assert _ds(t)[:15] == expect
    assert all(x == BASE for x in _ds(t)[15:])
    # 9,000,000 / 6,248,858 = 1.44026 ; 9,000,000 / 7,123,287 = 1.26349 (passes 1.25)
    assert t.months[0].dscr.value == Fraction(9_000_000, 6_248_858)
    assert t.months[2].dscr.value == Fraction(9_000_000, 7_123_287)
    assert t.months[2].dscr.value > Fraction(5, 4)


# ------------------------------------------------------------------ 2e  maturity beyond the horizon


def test_2e_loan_maturing_after_a_90_day_horizon(state):
    # months 1-3 each: 4,500,000 + 4,372,146 = 8,872,146 (DSCR 1.014, not 2.00)
    _s, t = _run(state, [(50_000_000, 0)], horizon=90)
    assert _ds(t)[:3] == [8_872_146] * 3
    assert all(t.months[m].dscr.value == Fraction(9_000_000, 8_872_146) for m in range(3))


# ------------------------------------------------------------------ boundary: exactly 1.25x


def test_boundary_exactly_at_the_covenant_passes_and_one_fen_over_fails(state, mandate):
    # rate 0: no interest. level = 32,400,000 / 12 = 2,700,000 -> DS 7,200,000 -> 9,000,000 / 7,200,000 = 1.25 exactly (>= passes)
    s, t = _run(state, [(32_400_000, 0)], rate_bp=0)
    assert _ds(t)[:12] == [7_200_000] * 12
    assert t.months[0].dscr.value == Fraction(5, 4)
    assert not [v for v in evaluate(t, s.facilities, mandate) if v.code == ViolationCode.DSCR_BREACH]
    # 32,400,012 -> level 2,700,001 each month: DS 7,200,001 -> below 1.25
    s, t = _run(state, [(32_400_012, 0)], rate_bp=0)
    assert _ds(t)[:12] == [7_200_001] * 12
    breaches = [v for v in evaluate(t, s.facilities, mandate) if v.code == ViolationCode.DSCR_BREACH]
    assert {v.month for v in breaches} == set(range(1, 13))
