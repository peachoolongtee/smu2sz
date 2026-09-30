import pytest

from app.covenants import CovenantEvaluatorImpl, evaluate
from app.domain.fixtures import load_scenario
from app.domain.models import (
    Covenant,
    CovenantKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    Repayment,
    ViolationCode,
)
from app.domain.ports import CovenantEvaluator
from tests.covenants.builders import month, trajectory


@pytest.fixture(scope="module")
def golden():
    return load_scenario()


@pytest.fixture(scope="module")
def line(golden):
    return next(f for f in golden[0].facilities if f.id == "FAC-LINE")


def _codes(vs):
    return [v.code for v in vs]


def _line_without_clean_down(line: Facility) -> Facility:
    return line.model_copy(update={"covenants": [c for c in line.covenants if c.kind != CovenantKind.CLEAN_DOWN]})


def test_satisfies_port():
    evaluator: CovenantEvaluator = CovenantEvaluatorImpl()
    assert evaluator.evaluate is not None


def test_dscr_exactly_1_25_passes(golden, line):
    _, mandate = golden
    t = trajectory(10, months=[month(1, 12_500, 10_000, 0)])
    assert evaluate(t, [line], mandate) == []


def test_dscr_1_2499_fails_for_facility_and_mandate(golden, line):
    _, mandate = golden
    t = trajectory(10, months=[month(1, 12_499, 10_000, 0)])
    vs = evaluate(t, [line], mandate)
    assert _codes(vs) == [ViolationCode.DSCR_BREACH, ViolationCode.DSCR_BREACH]
    fac, man = vs
    assert fac.month == 1 and fac.limit == "1.25x"
    assert fac.inputs["source_id"] == "FAC-LINE-DSCR"
    assert fac.inputs["facility_id"] == "FAC-LINE"
    assert fac.inputs["dscr_exact"] == "12499/10000"
    assert fac.formula.startswith("EBITDA_m / DS_m >= 1.25")
    assert man.inputs["source"] == "mandate"


def test_dscr_display_and_formula_for_capex_loan(golden, line):
    _, mandate = golden
    # 18-month capex loan: DS = 45,000 + 34,830.60 -> 1.13x (spec §7.7).
    t = trajectory(10, months=[month(1, 9_000_000, 4_500_000 + 3_483_060, 0)])
    v = evaluate(t, [line], mandate)[0]
    assert v.observed == "1.13x" and v.limit == "1.25x"
    assert "¥90,000.00 / ¥79,830.60 = 1.13x < 1.25x" in v.formula
    assert v.inputs["definition"].startswith("monthly EBITDA / scheduled debt service")


def test_zero_debt_service_has_no_dscr_breach(golden, line):
    _, mandate = golden
    t = trajectory(10, months=[month(1, 1, 0, 0)])
    assert evaluate(t, [line], mandate) == []


def test_leverage_exactly_2_5_passes_and_one_fen_more_fails(golden, line):
    _, mandate = golden
    ebitda = 9_000_000
    ok = trajectory(10, months=[month(1, ebitda, 1, 30 * ebitda)])
    assert evaluate(ok, [line], mandate) == []
    bad = trajectory(10, months=[month(1, ebitda, 1, 30 * ebitda + 1)])
    vs = evaluate(bad, [line], mandate)
    assert _codes(vs) == [ViolationCode.LEVERAGE_BREACH, ViolationCode.LEVERAGE_BREACH]
    assert vs[0].limit == "2.50x" and vs[0].inputs["source_id"] == "FAC-LINE-LEV"


def test_non_positive_ebitda_with_debt_is_a_leverage_breach(golden):
    _, mandate = golden
    t = trajectory(10, months=[month(1, -100, 0, 1_000)])
    vs = evaluate(t, [], mandate)
    assert _codes(vs) == [ViolationCode.LEVERAGE_BREACH]
    assert vs[0].observed == "undefined"


def test_two_facilities_with_their_own_dscr_thresholds(golden, line):
    _, mandate = golden
    strict = Facility(
        id="FAC-TERM",
        name="Term loan",
        kind=FacilityKind.EQUIPMENT_TERM_LOAN,
        lender_id="BANK-2",
        status=FacilityStatus.COMMITTED,
        owner_approved=True,
        limit_fen=1,
        rate_bp=500,
        lead_time_days=0,
        repayment=Repayment.AMORTISING,
        covenants=[
            Covenant(
                id="FAC-TERM-DSCR",
                facility_id="FAC-TERM",
                kind=CovenantKind.DSCR_MIN,
                threshold_bp=14_000,
                definition="EBITDA less maintenance capex / total debt service",
                formula="(EBITDA_m - capex_m) / DS_m >= 1.40",
            )
        ],
    )
    t = trajectory(10, months=[month(1, 13_000, 10_000, 0), month(2, 14_000, 10_000, 0)])
    vs = evaluate(t, [_line_without_clean_down(line), strict], mandate)
    assert len(vs) == 1
    v = vs[0]
    assert v.code == ViolationCode.DSCR_BREACH and v.month == 1
    assert v.observed == "1.30x" and v.limit == "1.40x"
    assert v.inputs["source_id"] == "FAC-TERM-DSCR"
    assert v.inputs["definition"] == "EBITDA less maintenance capex / total debt service"
    assert v.formula.startswith("(EBITDA_m - capex_m) / DS_m >= 1.40")


def test_every_month_is_checked(golden):
    _, mandate = golden
    t = trajectory(
        100, months=[month(1, 9_000_000, 4_500_000, 0), month(2, 1, 1_000, 0), month(3, 1, 1_000, 0)]
    )
    assert [v.month for v in evaluate(t, [], mandate)] == [2, 3]


def test_missing_threshold_is_refused(golden):
    _, mandate = golden
    bad = Facility(
        id="X",
        name="x",
        kind=FacilityKind.CREDIT_LINE,
        lender_id="B",
        status=FacilityStatus.COMMITTED,
        owner_approved=True,
        limit_fen=1,
        rate_bp=1,
        lead_time_days=0,
        repayment=Repayment.BULLET,
        covenants=[
            Covenant(id="C", facility_id="X", kind=CovenantKind.DSCR_MIN, definition="d", formula="f"),
        ],
    )
    with pytest.raises(ValueError):
        evaluate(trajectory(10, months=[month(1, 1, 1, 0)]), [bad], mandate)
