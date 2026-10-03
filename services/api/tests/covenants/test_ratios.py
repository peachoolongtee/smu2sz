from fractions import Fraction

import pytest

from app.covenants import (
    Basis,
    book_basis,
    leverage_debt_fen,
    pro_forma,
    ratios,
    ratios_for,
    with_extra,
    worst_dscr,
    worst_leverage,
)
from app.covenants.ratios import fmt_x
from app.domain.fixtures import golden_values, load_scenario
from app.domain.models import FundingAction, FundingActionKind, Mode
from app.financial import project


@pytest.fixture(scope="module")
def state():
    return load_scenario()[0]


@pytest.fixture(scope="module")
def g():
    return golden_values()


def test_ratios_exact():
    dscr, lev = ratios(9_000_000, 4_500_000, 165_000_000)
    assert dscr.value == 2
    assert lev.value == Fraction(165_000_000, 108_000_000)


def test_ratios_dscr_none_without_debt_service():
    dscr, lev = ratios(9_000_000, 0, 0)
    assert dscr is None and lev.value == 0


@pytest.mark.parametrize("ebitda", [0, -1])
def test_ratios_refuse_undefined_leverage(ebitda):
    with pytest.raises(ValueError):
        ratios(ebitda, 100, 100)


def test_fmt_x_half_up_and_negative():
    assert fmt_x(Fraction(1125, 1000)) == "1.13x"
    assert fmt_x(Fraction(-113, 100)) == "-1.13x"


def _month1(state, actions=()):
    return project(state, [], list(actions), Mode.CONSERVATIVE, 120).months[0]


def test_book_basis_counts_drawn_balances_not_undrawn_room(state):
    # Golden books today: D-EQUIP 1,500,000 and nothing drawn; the ¥150,000 line's undrawn room is not debt.
    assert leverage_debt_fen(state) == 150_000_000
    drawn = state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": 5_000_000}) if f.id == "FAC-LINE" else f for f in state.facilities]})
    assert leverage_debt_fen(drawn) == 155_000_000
    assert book_basis(state) == Basis(9_000_000, 4_500_000, 150_000_000)


def test_golden_base(state, g):
    # DSCR on the books' service: 90,000 / 45,000 = 2.00. Leverage at month-1 end on untouched books, after the
    # existing loan's day-30 payment: 1,455,000 / (12 × 90,000) = 1.347 -> 1.35 (was 1.53, which added the undrawn
    # ¥150,000 line limit: 1,650,000 / 1,080,000).
    dscr, _ = pro_forma(state)
    assert dscr.text == g["dscr_base"] == "2.00"
    m1 = _month1(state)
    _, lev = ratios_for(m1)
    assert m1.total_debt_fen == 145_500_000 and lev.value == Fraction(145_500_000, 108_000_000)
    assert lev.text == g["leverage_base"] == "1.35" and m1.leverage == lev  # the projection's own figure


def test_golden_after_extension_dscr_estimate(state, g):
    # The steady-state estimate (unchanged): 90,000 / (45,000 + 1,871.30 per-invoice funding cost) = 1.92.
    dscr, _ = pro_forma(
        state,
        extra_debt_fen=g["extension_extra_receivables"],
        extra_monthly_debt_service_fen=g["extension_committed_per_invoice"],
    )
    assert dscr.text == g["dscr_after_extension"] == "1.92"


def test_golden_after_extension_leverage_from_the_funded_projection(state, g):
    # EX01's committed plan draws the deepest shortfall (¥135,040) on the line from day 0, repaid day 62: month 1 =
    # (1,455,000 + 135,040) / 1,080,000 = 1.472 -> 1.47 (was 1.72 with the line limit and the 210,000 estimate).
    draw = FundingAction(kind=FundingActionKind.DRAW, facility_id="FAC-LINE", day=0,
                         amount_fen=g["reserve_shortfall_max"], repay_day=62)
    _, lev = ratios_for(_month1(state, [draw]))
    assert lev.text == g["leverage_after_extension"] == "1.47"


def test_pro_forma_on_a_month_point_adds_the_estimate(state):
    m1 = _month1(state)
    _, lev = pro_forma(m1, extra_debt_fen=60_000_000)
    assert lev.value == Fraction(145_500_000 + 60_000_000, 108_000_000)
    assert with_extra(m1, 1, 2, 3) == Basis(m1.ebitda_fen + 3, m1.debt_service_fen + 2, m1.total_debt_fen + 1)


def test_worst_months_take_the_earliest_on_a_tie():
    a, b, c = Basis(100, 50, 1200), Basis(100, 40, 1200), Basis(100, 50, 600)
    assert worst_leverage([c, a, b]) is a and worst_dscr([c, a, b]) is c
    assert worst_leverage([Basis(0, 1, 5)]) is None and worst_dscr([Basis(1, 0, 5)]) is None


@pytest.mark.parametrize(
    "key, m1_3, m4_on",
    [("loan_18m", "1.13", "1.40"), ("loan_36m", "1.43", "1.77"), ("lease_48m", "1.51", "1.88")],
)
def test_golden_capex_dscr(state, g, key, m1_3, m4_on):
    cap = g["capex"][key]
    pay = cap["monthly_payment"]
    d13, _ = pro_forma(state, extra_debt_fen=60_000_000, extra_monthly_debt_service_fen=pay)
    d4, _ = pro_forma(
        state, extra_debt_fen=60_000_000, extra_monthly_debt_service_fen=pay, extra_monthly_ebitda_fen=2_200_000
    )
    assert d13.text == cap["dscr_m1_3"] == m1_3
    assert d4.text == cap["dscr_m4_on"] == m4_on
    assert (d13.value >= Fraction(125, 100)) is cap["dscr_m1_3_passes"]


def test_golden_capex_leverage(state, g):
    # Month-1 end of the untouched books (1,455,000) + the ¥600,000 principal: 2,055,000 / 1,080,000 = 1.90 (was 2.08
    # with the ¥150,000 line limit); + the extension's ¥210,000 estimate: 2,265,000 / 1,080,000 = 2.10 (was 2.28).
    m1 = _month1(state)
    _, lev = pro_forma(m1, extra_debt_fen=60_000_000)
    assert lev.text == g["capex"]["leverage_financed"] == "1.90"
    _, lev2 = pro_forma(m1, extra_debt_fen=60_000_000 + g["extension_extra_receivables"])
    assert lev2.text == g["capex"]["leverage_financed_plus_extension"] == "2.10"
