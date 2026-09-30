"""Interest and fee postings for the simulated bank.

The rules live in `app.financial` (the trajectory engine posts with the same functions), so the
executor's cash effects and the engine's projections cannot drift apart. Re-exported here for the
executor and its tests.
"""

from __future__ import annotations

from app.financial import (
    DEFAULT_FEE_PERIOD_DAYS,
    finance_invoice_charges,
    line_interest,
    upfront_fee,
    whole_periods,
)

__all__ = ["DEFAULT_FEE_PERIOD_DAYS", "finance_invoice_charges", "line_interest", "upfront_fee", "whole_periods"]
