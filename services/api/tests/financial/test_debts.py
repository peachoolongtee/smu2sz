"""The existing-debt schedule (`app.financial.debts`, docs/FINANCIAL_SEMANTICS.md §5): every payment worked by hand."""

from __future__ import annotations

import pytest

from app.domain.models import DebtPosition
from app.financial.debts import debt_payments, first_payment_day, service_months_end


def debt(principal: int, service: int, rate_bp: int = 0, every: int = 30, nxt: int = 30) -> DebtPosition:
    return DebtPosition(id="D", facility_id=None, label="loan", principal_fen=principal,
                        monthly_debt_service_fen=service, rate_bp=rate_bp, payment_every_days=every,
                        next_payment_day=nxt)


def test_defaults_keep_older_states_loading() -> None:
    d = DebtPosition(id="D", facility_id=None, label="loan", principal_fen=1, monthly_debt_service_fen=1)
    assert (d.rate_bp, d.payment_every_days, d.next_payment_day) == (0, 30, 30)


def test_rate_zero_pays_all_principal() -> None:
    # ¥100,000 at ¥45,000 a month, no interest: 45,000 + 45,000 + 10,000 (the last clears it and is smaller)
    pays = debt_payments(debt(10_000_000, 4_500_000), 0, 1_000)
    assert [(p.day, p.principal, p.interest, p.remaining) for p in pays] == [
        (30, 4_500_000, 0, 5_500_000), (60, 4_500_000, 0, 1_000_000), (90, 1_000_000, 0, 0)]


def test_a_positive_rate_splits_each_payment() -> None:
    # ¥100,000 at 7.3% a year, ¥45,000 every 30 days:
    #   day 30: interest 100,000 × 7.3% × 30/365 = 600.00; principal 45,000 − 600 = 44,400.00; left 55,600.00
    #   day 60: interest  55,600 × 7.3% × 30/365 = 333.60; principal 44,666.40; left 10,933.60
    #   day 90: interest  10,933.60 × 7.3% × 30/365 = 65.6016 → 65.60; principal min(10,933.60, 44,934.40)
    #           = 10,933.60 (the last payment, 10,999.20, is smaller than the service)
    pays = debt_payments(debt(10_000_000, 4_500_000, rate_bp=730), 0, 1_000)
    assert [(p.day, p.principal, p.interest, p.remaining) for p in pays] == [
        (30, 4_440_000, 60_000, 5_560_000), (60, 4_466_640, 33_360, 1_093_360), (90, 1_093_360, 6_560, 0)]
    assert pays[-1].amount == 1_099_920  # smaller than the ¥45,000 service


def test_nothing_is_dated_before_today() -> None:
    d = debt(10_000_000, 1_000_000)
    assert first_payment_day(d, 45) == 60  # 30 is behind the books: the next one is 60, never 30 posted late
    pays = debt_payments(d, 45, 200)
    assert [p.day for p in pays] == [60, 90, 120, 150, 180]
    assert all(p.day >= 45 for p in pays)
    assert first_payment_day(d, 30) == 30  # a payment day that is today is still due


def test_a_cleared_principal_stops_payments() -> None:
    assert debt_payments(debt(0, 4_500_000), 0, 1_000) == []
    assert service_months_end(debt(0, 4_500_000), 0, 1_000) == 0
    pays = debt_payments(debt(9_000_000, 4_500_000), 0, 1_000)
    assert [p.day for p in pays] == [30, 60] and pays[-1].remaining == 0
    assert service_months_end(debt(9_000_000, 4_500_000), 0, 1_000) == 60
    assert service_months_end(debt(9_000_000, 4_500_000), 0, 60) is None  # not cleared before day 60


def test_the_golden_loan_clears_in_34_payments() -> None:
    # ¥1,500,000 / ¥45,000 = 33 full payments (¥1,485,000) then ¥15,000 on day 34 × 30 = 1,020
    pays = debt_payments(debt(150_000_000, 4_500_000), 0, 2_000)
    assert len(pays) == 34 and pays[-1].day == 1_020 and pays[-1].principal == 1_500_000


def test_until_day_is_exclusive_and_service_below_interest_never_loops() -> None:
    assert [p.day for p in debt_payments(debt(10_000_000, 4_500_000), 0, 60)] == [30]
    # ¥1,000,000 at 36.5% pays 30,000 interest a period; a ¥10,000 service pays no principal: bounded by until_day
    pays = debt_payments(debt(100_000_000, 1_000_000, rate_bp=3_650), 0, 100)
    assert [(p.principal, p.interest) for p in pays] == [(0, 3_000_000)] * 3


def test_a_non_positive_period_is_refused() -> None:
    with pytest.raises(ValueError):
        debt_payments(debt(1, 1, every=0), 0, 100)
