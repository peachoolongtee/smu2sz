"""Audit findings A12 / A13 on capex: F-FIN-03, F-FIN-04, F-FIN-05, F-FIN-12 and flows F3, F4.

Every case is the audit's reproduction (docs/research/independent-audit-evidence-2026-10-03/financial-repro.py)
with its numbers derived by hand in the comment above the assertion. Money is integer fen: ¥1 = 100.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.capex import CapexCandidate, CapexRequest, evaluate_capex
from app.capex.models import CHARGES_BASIS
from app.covenants import ratios, ratios_or_undefined
from app.domain.fixtures import load_scenario
from app.domain.models import CashFlow, FacilityKind, FacilityStatus, FlowKind, ViolationCode
from app.domain.money import Ratio
from app.mandate import load_signed_mandate

YUAN = 100


@pytest.fixture
def golden():
    return load_scenario("golden_sme")[0]


@pytest.fixture
def mandate():
    return load_signed_mandate()


@pytest.fixture
def clean(golden):
    """The audit's clean books: ¥1,000,000 cash, ¥100,000 monthly EBITDA, no debts, flows or receivables."""
    return golden.model_copy(update={"flows": [], "receivables": [], "recurring_invoices": [], "debts": [],
                                     "facilities": [], "cash_fen": 1_000_000 * YUAN,
                                     "monthly_ebitda_fen": 100_000 * YUAN})


@pytest.fixture
def permissive(mandate):
    return mandate.model_copy(update={"min_cash_fen": 0, "min_dscr_bp": 10000, "max_leverage_bp": 100000,
                                      "max_apr_bp": 100000})


@pytest.fixture
def loan(golden):
    """A committed amortising term loan with nothing drawn, no covenants, no lead time: the audit's template."""
    base = next(f for f in golden.facilities if f.kind == FacilityKind.EQUIPMENT_TERM_LOAN)
    return base.model_copy(update={"status": FacilityStatus.COMMITTED, "rate_bp": 0, "upfront_fee_bp": 0,
                                   "term_months": 12, "lead_time_days": 0, "covenants": [],
                                   "limit_fen": 1_000_000 * YUAN})


def request(*candidates: CapexCandidate, uplift: int = 20_000 * YUAN, **kw) -> CapexRequest:
    return CapexRequest(price_fen=600_000 * YUAN, monthly_uplift_fen=uplift, uplift_start_month=1, life_months=60,
                        candidates=list(candidates), include_cash_line=kw.pop("include_cash_line", False),
                        extension_target_terms_days=None, **kw)


def by_id(result):
    return {s.id: s for s in result.structures}


# ---------------------------------------------------------------- F-FIN-03


def test_f_fin_03_existing_drawn_loan_counts_in_dscr_and_leverage(clean, permissive, loan):
    # Existing zero-rate 12-month amortising loan drawn ¥1,200,000 -> ¥100,000 a month of service.
    # New zero-rate 12-month ¥600,000 loan -> ¥50,000 a month. EBITDA ¥100,000 + ¥20,000 uplift from month 1.
    #   DSCR 1 = 120,000 / (100,000 + 50,000) = 0.80 (was 2.40: the existing service was dropped)
    #   leverage at month-1 end (day 30) of the structure's projection, both loans after their first ¥100,000 and
    #   ¥50,000 payments: (1,100,000 + 550,000) / (12 × 100,000) = 1.375 -> 1.38 (was 1.50, today's 1,800,000
    #   read as month-end debt; 0.50 before F-FIN-03). The estimate before the structure is projected: the current
    #   books' month-1 debt 1,100,000 + the 600,000 principal = 1,700,000 / 1,200,000 = 1.417 -> 1.42.
    existing = loan.model_copy(update={"id": "EXISTING", "drawn_fen": 1_200_000 * YUAN, "limit_fen": 1_200_000 * YUAN})
    new = loan.model_copy(update={"id": "NEW"})
    r = evaluate_capex(request(CapexCandidate(facility_id="NEW", term_months=12)),
                       clean.model_copy(update={"facilities": [existing, new]}), permissive)
    s = by_id(r)["loan_12m"]
    assert s.dscr_by_month[0].dscr.text == "0.80"
    assert s.dscr_by_month[0].debt_service_fen == 150_000 * YUAN
    assert s.leverage.text == "1.38" and r.leverage_financed.text == "1.42"
    assert not s.feasible and ViolationCode.DSCR_BREACH in [v.code for v in s.violations]
    assert r.selected_id is None
    assert "Finance with" not in r.recommendation


def test_existing_service_stops_when_its_term_ends(clean, permissive, loan):
    # The existing loan has 12 payments; a 24-month new loan (¥25,000 a month at 0%) sees DSCR 120/125 = 0.96 in
    # months 1-12 and 120/25 = 4.80 from month 13.
    existing = loan.model_copy(update={"id": "EXISTING", "drawn_fen": 1_200_000 * YUAN, "limit_fen": 1_200_000 * YUAN})
    new = loan.model_copy(update={"id": "NEW", "term_months": 24})
    r = evaluate_capex(request(CapexCandidate(facility_id="NEW", term_months=24)),
                       clean.model_copy(update={"facilities": [existing, new]}), permissive)
    months = by_id(r)["loan_24m"].dscr_by_month
    assert months[11].dscr.text == "0.96" and months[12].dscr.text == "4.80"


# ---------------------------------------------------------------- F-FIN-04


def test_f_fin_04_upfront_fee_reverses_the_cost_ranking(clean, permissive, loan):
    # ¥600,000 over 12 months. ZERO: 0% interest, 10% upfront fee -> charges 0 + 60,000 = ¥60,000.
    # ONE: 1% nominal, no fee -> annuity interest ¥3,254.95. Interest alone picks ZERO; charges pick ONE.
    zero = loan.model_copy(update={"id": "ZERO", "upfront_fee_bp": 1000})
    one = loan.model_copy(update={"id": "ONE", "rate_bp": 100})
    r = evaluate_capex(request(CapexCandidate(facility_id="ZERO", term_months=12),
                               CapexCandidate(facility_id="ONE", term_months=12)),
                       clean.model_copy(update={"facilities": [zero, one]}), permissive)
    s = by_id(r)
    assert s["loan_12m"].facility_id == "ZERO" and s["loan_12m"].total_interest_fen == 0
    assert s["loan_12m"].upfront_fee_fen == 60_000 * YUAN and s["loan_12m"].charges_total_fen == 60_000 * YUAN
    assert s["one_12m"].total_interest_fen == 325_495 and s["one_12m"].charges_total_fen == 325_495
    assert r.selected_facility_id == "ONE"
    assert s["loan_12m"].extra_cost_vs_selected_fen == 60_000 * YUAN - 325_495
    assert CHARGES_BASIS in r.recommendation and "cheapest" not in r.recommendation.lower()
    assert "Finance with the 12-month term loan" in r.recommendation


@pytest.mark.parametrize("fee_bp", [0, 50, 100, 500, 1000, 2500])
def test_adding_a_fee_never_lowers_the_ranked_cost(clean, permissive, loan, fee_bp):
    # Charges = interest + fee; at 1% over 12 months interest is ¥3,254.95 and the fee is price × fee_bp / 10,000.
    one = loan.model_copy(update={"id": "ONE", "rate_bp": 100, "upfront_fee_bp": fee_bp})
    r = evaluate_capex(request(CapexCandidate(facility_id="ONE", term_months=12)),
                       clean.model_copy(update={"facilities": [one]}), permissive)
    s = r.structures[0]
    assert s.total_interest_fen == 325_495
    assert s.upfront_fee_fen == 600_000 * YUAN * fee_bp // 10_000
    assert s.charges_total_fen == 325_495 + 600_000 * YUAN * fee_bp // 10_000
    assert s.charges_total_fen >= 325_495  # the zero-fee cost: a fee can only add


# ---------------------------------------------------------------- F-FIN-05


def _line_books(clean, golden, mandate):
    line = next(f for f in golden.facilities if f.kind == FacilityKind.CREDIT_LINE).model_copy(
        update={"covenants": [], "limit_fen": 1_000_000 * YUAN, "rate_bp": 5000, "lead_time_days": 0})
    state = clean.model_copy(update={"cash_fen": 0, "facilities": [line]})
    mand = mandate.model_copy(update={"min_cash_fen": 0, "min_dscr_bp": 10000, "max_leverage_bp": 100000,
                                      "max_apr_bp": 100000})
    return state, mand


def test_f_fin_05_cash_plus_line_is_infeasible_when_borrowing_is_forbidden(clean, golden, mandate):
    state, mand = _line_books(clean, golden, mandate)
    ok = evaluate_capex(request(include_cash_line=True), state, mand)
    assert by_id(ok)["cash_line"].feasible  # permitted borrowing, rate within the cap: the line pays for it
    r = evaluate_capex(request(include_cash_line=True), state, mand.model_copy(update={"allow_new_borrowing": False}))
    s = by_id(r)["cash_line"]
    assert not s.feasible and s.result == "INFEASIBLE"
    assert ViolationCode.NEW_BORROWING_NOT_ALLOWED in [v.code for v in s.violations]


def test_f_fin_05_cash_plus_line_is_infeasible_when_the_rate_is_above_the_cap(clean, golden, mandate):
    state, mand = _line_books(clean, golden, mandate)
    # the line's all-in rate is 50% (rate_bp 5000); the cap is 1%
    r = evaluate_capex(request(include_cash_line=True), state, mand.model_copy(update={"max_apr_bp": 100}))
    s = by_id(r)["cash_line"]
    assert not s.feasible and ViolationCode.MAX_APR_EXCEEDED in [v.code for v in s.violations]
    assert r.selected_id is None


def test_cash_plus_line_breaches_the_line_covenant(clean, golden, mandate):
    # Interest-only on the ¥600,000 drawn at 50%/12 = ¥25,000 a month; EBITDA ¥100,000 + ¥20,000 uplift
    # -> DSCR 120,000 / 25,000 = 4.80, above a 5.00 covenant floor: DSCR_BREACH.
    state, mand = _line_books(clean, golden, mandate)
    r = evaluate_capex(request(include_cash_line=True), state, mand.model_copy(update={"min_dscr_bp": 50000}))
    s = by_id(r)["cash_line"]
    assert not s.feasible and ViolationCode.DSCR_BREACH in [v.code for v in s.violations]


# ---------------------------------------------------------------- F3


def test_f3_a_known_10m_outflow_on_day_1_makes_the_loan_infeasible(golden, mandate):
    # Golden books: ¥400,000 cash, ¥300,000 reserve. A ¥10,000,000 outflow on day 1 leaves cash at
    # 400,000 − 10,000,000 = −¥9,600,000 from day 1. The loan funds the purchase only (net 0 on the landing
    # day), so its first payment on day 44 (14 + 30) makes cash lower than the books without it while it is
    # below the reserve: RESERVE_BREACH, nothing selected.
    flow = CashFlow(id="X-OUT", day=1, amount_fen=-10_000_000 * YUAN, kind=FlowKind.OTHER, label="known outflow")
    r = evaluate_capex(CapexRequest(), golden.model_copy(update={"flows": [*golden.flows, flow]}), mandate)
    loan = by_id(r)["loan_36m"]
    assert not loan.feasible and loan.result == "REJECTED"
    assert ViolationCode.RESERVE_BREACH in [v.code for v in loan.violations]
    assert r.selected_id is None and "Finance with" not in r.recommendation


def test_f3_the_golden_books_select_the_lease_once_the_debt_payment_is_cash(golden, mandate):
    # The golden books already dip below the reserve on days 12-31 (before any purchase). The loan's proceeds
    # and the purchase cancel on day 14; cash is back to 315,000 on day 32 (after the ¥45,000 day-30 payment on the
    # existing loan), so the 36-month loan's first payment on day 44 (¥18,144.62) takes it to ¥296,855.38, below
    # the reserve: it causes a breach. The lease's first payment (day 40, ¥14,423.49) leaves ¥300,576.51.
    r = evaluate_capex(CapexRequest(), golden, mandate)
    assert r.selected_id == "lease_48m" and "Finance with the 48-month lease" in r.recommendation


def test_f3_a_20_percent_upfront_fee_changes_the_ranked_cost_by_120000(golden, mandate):
    # ETL ¥600,000 at 20%: fee = 600,000 × 20% = ¥120,000 = 12,000,000 fen; interest (36 months) is unchanged.
    plain = by_id(evaluate_capex(CapexRequest(), golden, mandate))["loan_36m"]
    dear_state = golden.model_copy(update={"facilities": [
        f.model_copy(update={"upfront_fee_bp": 2000}) if f.id == "FAC-ETL" else f for f in golden.facilities]})
    r = evaluate_capex(CapexRequest(), dear_state, mandate)
    dear = by_id(r)["loan_36m"]
    assert dear.total_interest_fen == plain.total_interest_fen == 5_320_614
    assert dear.upfront_fee_fen == 12_000_000
    assert dear.charges_total_fen - plain.charges_total_fen == 12_000_000
    # 5,320,614 + 12,000,000 = 17,320,614 > the lease's 9,232,732: the loan no longer wins on charges
    assert r.selected_id != "loan_36m"


def test_f3_zero_uplift_selects_nothing_and_never_says_finance_with(golden, mandate):
    r = evaluate_capex(CapexRequest(monthly_uplift_fen=0), golden, mandate)
    assert not r.worth_doing and r.npv_fen < 0
    assert r.selected_id is None and r.selected_facility_id is None
    assert all(s.result != "SELECTED" for s in r.structures)
    assert "Finance with" not in r.recommendation and "No financing structure is recommended" in r.recommendation


# ---------------------------------------------------------------- F4


def test_f4_a_360_month_candidate_on_a_36_month_facility_is_hypothetical(golden, mandate):
    r = evaluate_capex(CapexRequest(candidates=[CapexCandidate(facility_id="FAC-ETL", term_months=360)],
                                    include_cash_line=False), golden, mandate)
    s = by_id(r)["loan_360m"]
    assert s.hypothetical and s.term_months == 360
    assert r.selected_id is None and r.selected_facility_id is None and s.result != "SELECTED"
    assert s.note.startswith("Illustration at 360 months")


def test_f4_the_facility_term_is_selectable_and_a_cheaper_other_term_is_not(clean, permissive, loan):
    # ZERO: 12-month facility, 10% fee, 0% interest: the 6-month candidate has the same charges (¥60,000) but is
    # not the facility's term; the tie-break by term would otherwise pick it. Only the 12-month one is selected.
    zero = loan.model_copy(update={"id": "ZERO", "upfront_fee_bp": 1000})
    r = evaluate_capex(request(CapexCandidate(facility_id="ZERO", term_months=6),
                               CapexCandidate(facility_id="ZERO", term_months=12)),
                       clean.model_copy(update={"facilities": [zero]}), permissive)
    s = by_id(r)
    assert s["loan_6m"].hypothetical and not s["loan_12m"].hypothetical
    assert s["loan_6m"].charges_total_fen == s["loan_12m"].charges_total_fen == 60_000 * YUAN
    assert r.selected_id == "loan_12m"


# ---------------------------------------------------------------- F-FIN-12


@pytest.mark.parametrize("ebitda", [0, -1, -10_000_000])
def test_f_fin_12_non_positive_ebitda_gives_a_structured_result(clean, permissive, loan, ebitda):
    state = clean.model_copy(update={"facilities": [loan], "monthly_ebitda_fen": ebitda})
    r = evaluate_capex(request(CapexCandidate(facility_id=loan.id, term_months=12), include_cash_line=True), state,
                       permissive)
    s = by_id(r)["loan_12m"]
    assert not s.feasible and s.leverage is None and s.dscr_by_month == [] and s.min_dscr is None
    assert any("undefined" in v.message for v in s.violations)
    assert r.leverage_financed is None and r.selected_facility_id is None  # the cash purchase needs no debt
    assert "Finance with" not in r.recommendation


def test_ratio_text_formats_negative_ratios_with_their_sign():
    assert Ratio.of(Fraction(-1, 2)).text == "−0.50"  # was −1.50
    assert Ratio.of(Fraction(-123, 100)).text == "−1.23"  # was −2.23
    assert Ratio.of(Fraction(113, 100)).text == "1.13" and Ratio.of(Fraction(0)).text == "0.00"
    assert Ratio.of(Fraction(-1, 1000)).text == "0.00"  # rounds to zero: no stray sign


def test_covenant_ratios_still_raise_but_the_non_raising_path_does_not():
    with pytest.raises(ValueError):
        ratios(0, 1_000, 1_000)
    dscr, lev = ratios_or_undefined(-5_000_000, 10_000_000, 1_000)
    assert lev is None and dscr.text == "−0.50"
    assert ratios_or_undefined(0, 0, 0) == (None, None)
