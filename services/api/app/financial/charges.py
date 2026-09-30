"""Interest and fee rules for funding actions, shared by the trajectory engine and the executor.

Every amount is posted once through `app.domain.money` (ADR-0002):
- a line draw accrues Actual/365 simple interest per drawn lot, posted at repayment;
- invoice financing bills interest and fee in whole fee periods (30 days by default);
- an upfront fee is `upfront_fee_bp` of the amount, posted when the cash lands.
"""

from __future__ import annotations

from app.domain.models import Facility
from app.domain.money import bp, post, simple_interest

DEFAULT_FEE_PERIOD_DAYS = 30


def line_interest(principal_fen: int, rate_bp: int, days: int) -> int:
    """Simple interest on one drawn lot outstanding `days` days, posted in fen."""
    return post(simple_interest(principal_fen, bp(rate_bp), days))


def fee_period_days(facility: Facility) -> int:
    return facility.fee_period_days or DEFAULT_FEE_PERIOD_DAYS


def whole_periods(days: int, period_days: int) -> int:
    """Whole periods billed for `days` outstanding; at least one."""
    return max(1, -(-days // period_days))


def finance_invoice_charges(facility: Facility, advance_fen: int, days: int) -> tuple[int, int, int]:
    """(interest_fen, fee_fen, periods) for an invoice-financing advance outstanding `days` days."""
    period = fee_period_days(facility)
    periods = whole_periods(days, period)
    interest = post(simple_interest(advance_fen, bp(facility.rate_bp), periods * period))
    fee = post(bp(facility.fee_bp_per_advance) * advance_fen * periods)
    return interest, fee, periods


def upfront_fee(facility: Facility, amount_fen: int) -> int:
    """Upfront fee on a draw or advance, in fen (0 when the facility has none)."""
    return post(bp(facility.upfront_fee_bp) * amount_fen) if facility.upfront_fee_bp else 0
