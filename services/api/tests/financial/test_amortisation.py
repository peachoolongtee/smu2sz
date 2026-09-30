"""Amortisation schedules (ADR-0002) against the capex golden values."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.models import FacilityStatus, Mode
from app.financial import amortisation_schedule, annuity_payment, project
from tests.financial.builders import draw

PRINCIPAL = 60_000_000  # ¥600,000


@pytest.mark.parametrize(
    ("key", "rate_bp", "months"), [("loan_18m", 560, 18), ("loan_36m", 560, 36), ("lease_48m", 720, 48)]
)
def test_capex_schedules(g, key, rate_bp, months):
    want = g["capex"][key]
    assert annuity_payment(PRINCIPAL, rate_bp, months) == want["monthly_payment"]
    rows = amortisation_schedule(PRINCIPAL, rate_bp, months)
    assert len(rows) == months
    assert all(r.payment == want["monthly_payment"] for r in rows[:-1])
    assert sum(r.interest for r in rows) == want["total_interest"]
    assert rows[-1].balance == 0


def test_lease_minus_36m_interest(g):
    lease = sum(r.interest for r in amortisation_schedule(PRINCIPAL, 720, 48))
    loan = sum(r.interest for r in amortisation_schedule(PRINCIPAL, 560, 36))
    assert lease - loan == g["capex"]["lease_minus_36m_interest"]


def test_zero_rate():
    rows = amortisation_schedule(1000, 0, 3)
    assert [r.payment for r in rows] == [333, 333, 334]


@given(
    st.integers(min_value=100_000, max_value=10**10),
    st.integers(min_value=0, max_value=3000),
    st.integers(min_value=1, max_value=60),
)
def test_schedule_clears_and_conserves(principal, rate_bp, months):
    rows = amortisation_schedule(principal, rate_bp, months)
    assert sum(r.principal for r in rows) == principal
    assert rows[-1].balance == 0
    assert all(r.payment == r.interest + r.principal for r in rows)
    assert all(r.balance >= 0 for r in rows)


def test_amortising_draw_in_the_trajectory(state, g):
    # the 36-month equipment loan, marked PENDING to project it in EXPECTED mode
    etl = next(f for f in state.facilities if f.id == "FAC-ETL").model_copy(update={"status": FacilityStatus.PENDING})
    s = state.model_copy(update={"facilities": [etl if f.id == "FAC-ETL" else f for f in state.facilities]})
    t = project(s, [], [draw("FAC-ETL", PRINCIPAL, repay_day=None)], Mode.EXPECTED, 120)
    lands = etl.lead_time_days
    assert t.horizon_days == lands + 30 * 36 + 1
    assert t.interest_posted_fen == g["capex"]["loan_36m"]["total_interest"]
    # month 2 holds the first payment (day 44): existing debt service + one full instalment
    assert t.months[1].debt_service_fen == 4_500_000 + g["capex"]["loan_36m"]["monthly_payment"]
    assert t.days[-1].debt_outstanding_fen == 150_000_000
