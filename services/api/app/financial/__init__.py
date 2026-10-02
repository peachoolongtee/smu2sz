"""Financial engine: daily cash recursion, debt ledger, forward-concession valuation, amortisation.

Pure and deterministic. Money is integer fen; rounding happens only through app.domain.money.
"""

from app.financial.amortisation import AmortisationRow, amortisation_schedule, annuity_payment
from app.financial.cashpath import CashPath, project_cash
from app.financial.charges import (
    DEFAULT_FEE_PERIOD_DAYS,
    advance_effective_rate,
    fee_period_days,
    finance_invoice_charges,
    line_interest,
    upfront_fee,
    whole_periods,
)
from app.financial.concessions import (
    ExtensionProForma,
    extension_extra_debt,
    extension_monthly_service,
    extension_pro_forma,
    if_all_in_rate,
    pro_forma_scale,
    recurring_issue_days,
    value_concessions,
    window,
)
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
    "ExtensionProForma",
    "FundingActionError",
    "ObligationError",
    "UncommittedFacilityError",
    "advance_effective_rate",
    "amortisation_schedule",
    "annuity_payment",
    "extension_extra_debt",
    "extension_monthly_service",
    "extension_pro_forma",
    "fee_period_days",
    "finance_invoice_charges",
    "if_all_in_rate",
    "line_interest",
    "materialise",
    "pro_forma_scale",
    "project",
    "project_cash",
    "recurring_issue_days",
    "recurring_receivable_id",
    "resolve_scope",
    "upfront_fee",
    "value_concessions",
    "whole_periods",
    "window",
]
