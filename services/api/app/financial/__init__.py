"""Financial engine: daily cash recursion, debt ledger, forward-concession valuation, amortisation.

Pure and deterministic. Money is integer fen; rounding happens only through app.domain.money.
"""

from app.financial.amortisation import AmortisationRow, amortisation_schedule, annuity_payment
from app.financial.cashpath import CashPath, project_cash
from app.financial.charges import (
    DEFAULT_FEE_PERIOD_DAYS,
    fee_period_days,
    finance_invoice_charges,
    line_interest,
    upfront_fee,
    whole_periods,
)
from app.financial.concessions import if_all_in_rate, value_concessions
from app.financial.engine import Engine
from app.financial.errors import EngineError, FundingActionError, ObligationError, UncommittedFacilityError
from app.financial.invoices import materialise, resolve_scope
from app.financial.trajectory import project, recurring_receivable_id

__all__ = [
    "DEFAULT_FEE_PERIOD_DAYS",
    "AmortisationRow",
    "CashPath",
    "Engine",
    "EngineError",
    "FundingActionError",
    "ObligationError",
    "UncommittedFacilityError",
    "amortisation_schedule",
    "annuity_payment",
    "fee_period_days",
    "finance_invoice_charges",
    "if_all_in_rate",
    "line_interest",
    "materialise",
    "project",
    "project_cash",
    "recurring_receivable_id",
    "resolve_scope",
    "upfront_fee",
    "value_concessions",
    "whole_periods",
]
