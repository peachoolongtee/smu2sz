"""Financial engine: daily cash recursion, debt ledger, forward-concession valuation, amortisation.

Pure and deterministic. Money is integer fen; rounding happens only through app.domain.money.
"""

from app.financial.amortisation import AmortisationRow, amortisation_schedule, annuity_payment
from app.financial.concessions import if_all_in_rate, value_concessions
from app.financial.engine import Engine
from app.financial.errors import EngineError, FundingActionError, ObligationError, UncommittedFacilityError
from app.financial.trajectory import project, recurring_receivable_id

__all__ = [
    "AmortisationRow",
    "Engine",
    "EngineError",
    "FundingActionError",
    "ObligationError",
    "UncommittedFacilityError",
    "amortisation_schedule",
    "annuity_payment",
    "if_all_in_rate",
    "project",
    "recurring_receivable_id",
    "value_concessions",
]
