"""Capex mode on the golden fixture, exact against golden_values()["capex"] (spec v2 §7.7)."""

import pytest
from pydantic import ValidationError

from app.capex import (
    OWNER_ESTIMATE,
    CapexCandidate,
    CapexDisabled,
    CapexRequest,
    evaluate_capex,
)
from app.domain.models import DebtPosition, Tier, ViolationCode


@pytest.fixture
def result(state, mandate):
    return evaluate_capex(CapexRequest(), state, mandate)


def by_id(result):
    return {s.id: s for s in result.structures}


def test_npv_and_payback_match_golden(result, g):
    assert result.npv_fen == g["npv"] == 38088577
    assert result.payback_month == g["payback_month"] == 31
    assert result.npv_positive and result.payback_within_limit and result.worth_doing


def test_owner_estimate_is_labelled(result):
    assert result.estimate_note.startswith("Owner's estimate")
    labelled = {w.label for w in result.workings if w.evidence == OWNER_ESTIMATE}
    assert {"NPV at the hurdle", "Simple payback"} <= labelled


def test_18_month_loan_rejected_on_dscr_in_month_1(result, g):
    s = by_id(result)["loan_18m"]
    assert s.monthly_payment_fen == g["loan_18m"]["monthly_payment"] == 3483060
    assert s.total_interest_fen == g["loan_18m"]["total_interest"] == 2695084
    assert s.dscr_by_month[0].dscr.text == g["loan_18m"]["dscr_m1_3"] == "1.13"
    assert s.dscr_by_month[3].dscr.text == g["loan_18m"]["dscr_m4_on"] == "1.40"
    assert [m.passes for m in s.dscr_by_month[:4]] == [False, False, False, True]
    assert not s.feasible and s.result == "REJECTED"
    v = s.violations[0]
    assert v.code == ViolationCode.DSCR_BREACH and v.month == 1
    # the 18-month term is not the facility's (36): shown as an illustration only
    assert s.hypothetical
    assert s.note == ("Illustration at 18 months, not the facility's actual term; never selected or applied for. "
                      "Rejected: DSCR_BREACH@month 1 (1.13× < 1.25×).")
    assert v.formula and v.inputs["new_payment"] == "¥34,830.60"


def test_36_month_loan_holds_dscr_but_breaches_the_reserve_on_its_first_payment(result, g):
    s = by_id(result)["loan_36m"]
    assert s.monthly_payment_fen == g["loan_36m"]["monthly_payment"] == 1814462
    assert s.total_interest_fen == g["loan_36m"]["total_interest"] == 5320614
    assert s.dscr_by_month[0].dscr.text == g["loan_36m"]["dscr_m1_3"] == "1.43"
    assert s.dscr_by_month[3].dscr.text == g["loan_36m"]["dscr_m4_on"] == "1.77"
    assert len(s.dscr_by_month) == 36 and all(m.passes for m in s.dscr_by_month)
    # Liquidity: before the first instalment the books close at 400,000 − 340,000 − 120,000 − 45,000 (the day-30
    # debt payment) + 420,000 (RCV-A, day 32) = 315,000; the first instalment on day 44 (14-day lead + 30) takes it
    # to 315,000 − 18,144.62 = 296,855.38, below the 300,000 reserve the books keep without it
    assert not s.feasible and s.result == "REJECTED"
    assert [(v.code, v.day, v.observed) for v in s.violations] == [(ViolationCode.RESERVE_BREACH, 44, "¥296,855.38")]
    assert result.selected_id == g["selected"] == "lease_48m" and result.selected_facility_id == "FAC-LEASE"


def test_lease_selected_though_dearer(result, g):
    s = by_id(result)["lease_48m"]
    assert s.monthly_payment_fen == g["lease_48m"]["monthly_payment"] == 1442349
    assert s.total_interest_fen == g["lease_48m"]["total_interest"] == 9232732
    assert s.dscr_by_month[0].dscr.text == g["lease_48m"]["dscr_m1_3"]
    assert s.dscr_by_month[3].dscr.text == g["lease_48m"]["dscr_m4_on"]
    # its first payment (day 40: 10-day lead + 30) leaves 315,000 − 14,423.49 = 300,576.51, above the reserve
    assert s.feasible and s.result == "SELECTED" and s.violations == []
    assert s.extra_cost_vs_selected_fen is None
    loan = by_id(result)["loan_36m"]
    assert s.total_interest_fen - loan.total_interest_fen == g["lease_minus_36m_interest"] == 3912118
    assert "36-month term loan, 5.60% is rejected (RESERVE_BREACH)" in result.recommendation


def test_leverage_financed_and_with_extension(result, g):
    assert result.leverage_financed.text == g["leverage_financed"] == "2.08"
    assert result.leverage_with_extension.text == g["leverage_financed_plus_extension"] == "2.28"
    assert all(s.leverage.text == "2.08" for s in result.structures if s.kind != "CASH_LINE")


def test_cash_plus_line_infeasible_with_reserve_breach(result, g):
    s = by_id(result)["cash_line"]
    assert not s.feasible and s.result == "INFEASIBLE"
    v = s.violations[0]
    assert v.code == ViolationCode.RESERVE_BREACH and v.day == 0
    assert v.inputs["available_above_reserve"] == "¥250,000.00"
    assert g["cash_above_reserve"] == 25000000
    assert v.observed == "−¥50,000.00"


def test_required_tier_is_2_and_every_number_has_its_working(result):
    assert result.required_tier == Tier.TIER_2
    for s in result.structures:
        assert s.workings and all(w.formula for w in s.workings)
        for v in s.violations:
            assert v.formula and v.inputs
    assert result.dscr_limit_bp == 12500 and result.leverage_limit_bp == 25000


def test_flag_off_gives_feature_disabled(state, mandate, monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX", "0")
    with pytest.raises(CapexDisabled) as e:
        evaluate_capex(CapexRequest(), state, mandate)
    assert e.value.code == ViolationCode.FEATURE_DISABLED


def test_request_is_strict():
    with pytest.raises(ValidationError):
        CapexRequest(price_fen=60_000_000, surprise=1)
    with pytest.raises(ValidationError):
        CapexRequest(price_fen="60000000")
    with pytest.raises(ValidationError):
        CapexRequest(price_fen=0)


def test_default_request_is_the_spec_case():
    r = CapexRequest()
    assert (r.price_fen, r.monthly_uplift_fen, r.uplift_start_month, r.life_months, r.hurdle_bp,
            r.payback_limit_months) == (60_000_000, 2_200_000, 4, 60, 1000, 36)
    assert [(c.facility_id, c.term_months) for c in r.candidates] == [("FAC-ETL", 18), ("FAC-ETL", 36),
                                                                       ("FAC-LEASE", 48)]


def test_no_admissible_structure_selects_nothing(state, mandate):
    r = evaluate_capex(CapexRequest(candidates=[CapexCandidate(facility_id="FAC-ETL", term_months=18)]),
                       state, mandate)
    assert r.selected_id is None and r.selected_facility_id is None
    assert "No structure holds" in r.recommendation


def test_weak_estimate_is_not_worth_doing(state, mandate):
    r = evaluate_capex(CapexRequest(monthly_uplift_fen=1_000_000), state, mandate)
    assert r.npv_fen < 0 and not r.worth_doing
    assert r.payback_month is None or r.payback_month > 36


def test_leverage_breach_rejects_every_financed_structure(state, mandate):
    heavy = state.model_copy(update={"debts": [*state.debts, DebtPosition(
        id="D-X", facility_id=None, label="Other loan", principal_fen=60_000_000, monthly_debt_service_fen=0)]})
    r = evaluate_capex(CapexRequest(), heavy, mandate)
    for s in r.structures:
        if s.kind != "CASH_LINE":
            assert ViolationCode.LEVERAGE_BREACH in [v.code for v in s.violations]
    assert r.selected_id is None


def test_unknown_facility_cannot_be_a_candidate(state, mandate):
    r = evaluate_capex(CapexRequest(candidates=[CapexCandidate(facility_id="FAC-FASTCAPITAL", term_months=36)]),
                       state, mandate)
    s = next(s for s in r.structures if s.facility_id == "FAC-FASTCAPITAL")
    assert not s.feasible and s.violations[0].code == ViolationCode.PRECONDITION_FAILED
    assert r.selected_id is None
