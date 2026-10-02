"""Designed FinancialState variants where the router's search matters (spec §7.3–7.4)."""

from __future__ import annotations

from app.domain.models import CovenantKind, FacilityStatus, FinancialState, Mandate
from tests.funding.variants import (
    add_flow,
    golden,
    with_debt_principal,
    with_facility,
    with_flow_day,
    with_receivable,
    without_facilities,
)


def bill_held() -> tuple[FinancialState, Mandate]:
    """A cheap 银票 is held: ¥400,000 of bills discountable at 0.58%."""
    s, m = golden()
    return with_facility(s, "FAC-BILL", limit_fen=40_000_000), m


def dear_line() -> tuple[FinancialState, Mandate]:
    """The line costs 11.5%: invoice financing (≈10.84%) is cheaper for the 32-day gap."""
    s, m = golden()
    return with_facility(s, "FAC-LINE", rate_bp=1150), m


def cheap_early_pay() -> tuple[FinancialState, Mandate]:
    """The buyer offers 0.3% for payment 30 days early (≈3.7% a year): cheaper than the line."""
    s, m = golden()
    return with_facility(s, "FAC-EARLYPAY", rate_bp=30), m


def leverage_tight() -> tuple[FinancialState, Mandate]:
    """Existing debt of ¥2.5m: more than ¥200,000 of new debt breaks the 2.5x leverage covenant,
    so part of the gap must come from early payment, which is not debt."""
    s, m = golden()
    return with_debt_principal(s, 250_000_000), m


def no_new_borrowing() -> tuple[FinancialState, Mandate]:
    """The mandate forbids new borrowing: only the buyer's early payment is allowed."""
    s, m = golden()
    return s, m.model_copy(update={"allow_new_borrowing": False})


def long_gap() -> tuple[FinancialState, Mandate]:
    """Receivable A pays on day 100; no recurring invoices, no day-47 bill and no existing loan (its ¥45,000 payments
    on days 30, 60 and 90 would make the gap ¥495,000, more than any committed source can carry until day 100): a
    line drawn until day 100 cannot rest at zero for 30 days within the 120-day horizon (clean-down)."""
    s, m = golden()
    s = s.model_copy(update={"recurring_invoices": [], "flows": [f for f in s.flows if f.id != "F-BILL47"],
                             "debts": []})
    s = with_receivable(s, "RCV-A", terms_days=113)
    return s, m


def late_cheap_loan(payroll_day: int = 12) -> tuple[FinancialState, Mandate]:
    """A committed guaranteed loan at 1% for one month, but it lands on day 21."""
    s, m = golden()
    s = with_facility(s, "FAC-GGL", status=FacilityStatus.COMMITTED, rate_bp=100, term_months=1)
    return with_flow_day(s, "F-PAYROLL", payroll_day), m


def uncovered_gap() -> tuple[FinancialState, Mandate]:
    """Only the ¥150,000 line is usable: it cannot cover the ¥405,000 gap."""
    s, m = golden()
    return without_facilities(s, "FAC-IF", "FAC-EARLYPAY"), m


def expected_only_gap() -> tuple[FinancialState, Mandate]:
    """Payroll moves to day 30, invoice financing and early payment are gone: committed sources
    cannot cover the gap, but the (not yet applied) guaranteed loan would, from day 21."""
    s, m = golden()
    s = without_facilities(s, "FAC-IF", "FAC-EARLYPAY")
    return with_flow_day(s, "F-PAYROLL", 30), m


def permanent_need() -> tuple[FinancialState, Mandate]:
    """A ¥300,000 outflow on day 5 that nothing recovers within the 120-day horizon (a ¥500,000
    inflow arrives only on day 300). The clean-down line is cheapest (3%) but cannot carry it; a
    committed guaranteed loan (same-day, 12 months) can."""
    s, m = golden()
    # the books are cleared to this one need, the existing loan included (its ¥45,000 a month would run on to the
    # 12-month loan's maturity with nothing coming in before day 300)
    s = s.model_copy(update={"recurring_invoices": [], "receivables": [], "flows": [], "debts": []})
    s = without_facilities(s, "FAC-IF", "FAC-EARLYPAY")
    s = with_facility(s, "FAC-LINE", rate_bp=300)
    s = with_facility(s, "FAC-GGL", status=FacilityStatus.COMMITTED, lead_time_days=0)
    s = add_flow(s, "F-BIG", 5, -30_000_000)
    s = add_flow(s, "F-LATE", 300, 50_000_000)
    return s, m


# ---------------------------------------------------------------- EV-06: line repaid before the baseline recovers
# Seeded variants R01, R03, R05 and R15 of the evaluation suite (evals/suites/funding.py on agent/evals):
# the cheapest plan repays the line on day 32 (RCV-A's receipt) and covers days 32–47 with another source.


def _eval_variant(cash_fen: int, payroll_day: int, payroll_fen: int, fac: dict[str, dict],
                  clean_down_days: int | None = None) -> tuple[FinancialState, Mandate]:
    s, m = golden()
    s = with_flow_day(s.model_copy(update={"cash_fen": cash_fen}), "F-PAYROLL", payroll_day)
    s = s.model_copy(update={"flows": [f.model_copy(update={"amount_fen": payroll_fen}) if f.id == "F-PAYROLL" else f
                                       for f in s.flows]})
    for fid, update in fac.items():
        s = with_facility(s, fid, **update)
    if clean_down_days is not None:
        line = next(f for f in s.facilities if f.id == "FAC-LINE")
        covs = [c for c in line.covenants if c.kind != CovenantKind.CLEAN_DOWN] if clean_down_days == 0 else [
            c.model_copy(update={"clean_down_days": clean_down_days}) if c.kind == CovenantKind.CLEAN_DOWN else c
            for c in line.covenants]
        s = with_facility(s, "FAC-LINE", covenants=covs)
    return s, m


def r01_early_line_repayment() -> tuple[FinancialState, Mandate]:
    return _eval_variant(30_000_000, 10, -34_000_000, {
        "FAC-LINE": {"rate_bp": 550, "limit_fen": 15_000_000},
        "FAC-IF": {"rate_bp": 780, "fee_bp_per_advance": 40, "lead_time_days": 8, "advance_rate_bp": 7000},
        "FAC-EARLYPAY": {"rate_bp": 80, "lead_time_days": 1},
        "FAC-GGL": {"status": FacilityStatus.PENDING, "rate_bp": 100, "lead_time_days": 1}})


def r03_early_line_repayment() -> tuple[FinancialState, Mandate]:
    return _eval_variant(35_000_000, 18, -40_000_000, {
        "FAC-LINE": {"rate_bp": 640, "limit_fen": 20_000_000},
        "FAC-IF": {"rate_bp": 600, "fee_bp_per_advance": 25, "lead_time_days": 8, "advance_rate_bp": 9000},
        "FAC-EARLYPAY": {"rate_bp": 150, "lead_time_days": 1},
        "FAC-BILL": {"limit_fen": 40_000_000, "rate_bp": 150}}, clean_down_days=60)


def r05_early_line_repayment() -> tuple[FinancialState, Mandate]:
    return _eval_variant(35_000_000, 19, -40_000_000, {
        "FAC-LINE": {"rate_bp": 450, "limit_fen": 30_000_000},
        "FAC-IF": {"rate_bp": 780, "fee_bp_per_advance": 10, "lead_time_days": 8, "advance_rate_bp": 7000},
        "FAC-EARLYPAY": {"rate_bp": 120, "lead_time_days": 2}})


def r15_early_line_repayment() -> tuple[FinancialState, Mandate]:
    return _eval_variant(30_000_000, 16, -40_000_000, {
        "FAC-LINE": {"rate_bp": 800, "limit_fen": 30_000_000},
        "FAC-IF": {"rate_bp": 700, "fee_bp_per_advance": 40, "lead_time_days": 5, "advance_rate_bp": 9000},
        "FAC-EARLYPAY": {"rate_bp": 80, "lead_time_days": 1}}, clean_down_days=0)
