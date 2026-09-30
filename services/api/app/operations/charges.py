"""Interest and fee postings for the simulated bank.

These follow the financial engine's rules (docs/ARCHITECTURE.md "Engine semantics" §4) exactly and
use only `app.domain.money` primitives, which is where every rounding happens (ADR-0002):
- a line draw posts Actual/365 simple interest per drawn lot at repayment, rounded once per lot;
- invoice financing bills interest and fee in whole fee periods (30 days by default);
- an upfront fee is `upfront_fee_bp` of the amount, posted when the cash lands.

`app.financial` keeps these rules in private helpers, so they are restated here and
tests/operations/test_charges.py cross-checks them against `app.financial.project`.
"""

from __future__ import annotations

from app.domain.models import Facility
from app.domain.money import bp, post, simple_interest

DEFAULT_FEE_PERIOD_DAYS = 30


def line_interest_fen(principal_fen: int, rate_bp: int, days: int) -> int:
    """Simple interest on one drawn lot, posted at repayment."""
    return post(simple_interest(principal_fen, bp(rate_bp), days))


def whole_periods(days: int, period_days: int) -> int:
    """Number of whole periods billed for `days` (at least one)."""
    return max(1, -(-days // period_days))


def financing_charges(facility: Facility, advance_fen: int, days: int) -> tuple[int, int, int]:
    """(interest_fen, fee_fen, periods) for an invoice-financing advance outstanding `days` days."""
    period = facility.fee_period_days or DEFAULT_FEE_PERIOD_DAYS
    periods = whole_periods(days, period)
    interest = post(simple_interest(advance_fen, bp(facility.rate_bp), periods * period))
    fee = post(bp(facility.fee_bp_per_advance) * advance_fen * periods)
    return interest, fee, periods


def upfront_fee_fen(facility: Facility, amount_fen: int) -> int:
    return post(bp(facility.upfront_fee_bp) * amount_fen) if facility.upfront_fee_bp else 0
