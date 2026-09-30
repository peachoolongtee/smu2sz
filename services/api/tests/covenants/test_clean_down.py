import pytest

from app.covenants import evaluate, line_balances, line_can_carry_permanent_need
from app.domain.fixtures import load_scenario
from app.domain.models import CovenantKind, FacilityKind, ViolationCode
from tests.covenants.builders import draw, interest, repay, trajectory

LINE = "FAC-LINE"


@pytest.fixture(scope="module")
def golden():
    return load_scenario()


@pytest.fixture(scope="module")
def line(golden):
    return next(f for f in golden[0].facilities if f.id == LINE)


def _clean_down(t, line, mandate):
    return [v for v in evaluate(t, [line], mandate) if v.code == ViolationCode.CLEAN_DOWN_BREACH]


def test_unused_line_holds(golden, line):
    assert _clean_down(trajectory(120), line, golden[1]) == []


def test_30_day_zero_run_passes(golden, line):
    # Days 0..59; drawn day 0, repaid day 30 -> zero on days 30..59 = 30 days.
    t = trajectory(59, events=[draw(0, LINE, 10_000_000), repay(30, LINE, 10_000_000)])
    assert _clean_down(t, line, golden[1]) == []


def test_29_day_zero_run_fails(golden, line):
    t = trajectory(59, events=[draw(0, LINE, 10_000_000), repay(31, LINE, 10_000_000)])
    [v] = _clean_down(t, line, golden[1])
    assert v.observed == "29 days" and v.limit == "30 days"
    assert v.inputs["covenant_id"] == "FAC-LINE-CD"
    assert v.inputs["longest_zero_run_from_day"] == "31"
    assert v.inputs["longest_zero_run_to_day"] == "59"
    assert v.inputs["peak_balance"] == "¥100,000.00"
    assert v.formula.startswith("max run of days with balance = 0 >= 30")


def test_zero_run_before_a_draw_counts(golden, line):
    # Zero on days 0..29, then drawn to the end: the 30-day run exists within the horizon.
    t = trajectory(120, events=[draw(30, LINE, 5_000_000)])
    assert _clean_down(t, line, golden[1]) == []


def test_permanent_draw_fails(golden, line):
    t = trajectory(120, events=[draw(5, LINE, 15_000_000)])
    [v] = _clean_down(t, line, golden[1])
    assert v.observed == "5 days" and v.day == 5


def test_opening_balance_never_repaid_fails(golden, line):
    drawn = line.model_copy(update={"drawn_fen": 1_000})
    [v] = _clean_down(trajectory(120), drawn, golden[1])
    assert v.observed == "0 days" and v.inputs["opening_balance"] == "¥10.00"


def test_horizon_shorter_than_clean_down_is_not_evaluated(golden, line):
    t = trajectory(29, events=[draw(0, LINE, 15_000_000)])
    assert _clean_down(t, line, golden[1]) == []


def test_intraday_draw_and_repay_breaks_the_run(golden, line):
    # Zero days 0..58 except day 29, which has a same-day draw and repay: longest run is 29.
    t = trajectory(58, events=[draw(29, LINE, 100), repay(29, LINE, 100)])
    [v] = _clean_down(t, line, golden[1])
    assert v.observed == "29 days"


def test_interest_and_other_facilities_do_not_move_the_balance(golden, line):
    t = trajectory(
        40,
        events=[draw(0, LINE, 500), repay(1, LINE, 500), interest(1, LINE, 7), draw(2, "FAC-IF", 9_999)],
    )
    balances = [d.balance_fen for d in line_balances(t, line)]
    assert balances[:3] == [500, 0, 0]
    assert _clean_down(t, line, golden[1]) == []


def test_clean_down_only_applies_to_credit_lines(golden, line):
    not_a_line = line.model_copy(update={"kind": FacilityKind.INVOICE_FINANCING})
    t = trajectory(120, events=[draw(5, LINE, 15_000_000)])
    assert _clean_down(t, not_a_line, golden[1]) == []


def test_line_cannot_carry_permanent_need(golden, line):
    assert line_can_carry_permanent_need(line) is False
    no_cd = line.model_copy(
        update={"covenants": [c for c in line.covenants if c.kind != CovenantKind.CLEAN_DOWN]}
    )
    assert line_can_carry_permanent_need(no_cd) is True
    fac_if = next(f for f in golden[0].facilities if f.id == "FAC-IF")
    assert line_can_carry_permanent_need(fac_if) is True
