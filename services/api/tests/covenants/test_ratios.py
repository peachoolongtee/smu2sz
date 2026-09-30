from fractions import Fraction

import pytest

from app.covenants import pro_forma, ratios
from app.covenants.ratios import fmt_x
from app.domain.fixtures import golden_values, load_scenario

LINE_LIMIT = 15_000_000  # the ¥150,000 credit line


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


def test_golden_base(state, g):
    dscr, lev = pro_forma(state, base_extra_debt_fen=LINE_LIMIT)
    assert dscr.text == g["dscr_base"] == "2.00"
    assert lev.text == g["leverage_base"] == "1.53"


def test_golden_after_extension(state, g):
    dscr, lev = pro_forma(
        state,
        extra_debt_fen=g["extension_extra_receivables"],
        extra_monthly_debt_service_fen=g["extension_committed_per_invoice"],
        base_extra_debt_fen=LINE_LIMIT,
    )
    assert dscr.text == g["dscr_after_extension"] == "1.92"
    assert lev.text == g["leverage_after_extension"] == "1.72"


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
    _, lev = pro_forma(state, extra_debt_fen=60_000_000, base_extra_debt_fen=LINE_LIMIT)
    assert lev.text == g["capex"]["leverage_financed"] == "2.08"
    _, lev2 = pro_forma(
        state,
        extra_debt_fen=60_000_000 + g["extension_extra_receivables"],
        base_extra_debt_fen=LINE_LIMIT,
    )
    assert lev2.text == g["capex"]["leverage_financed_plus_extension"] == "2.28"
