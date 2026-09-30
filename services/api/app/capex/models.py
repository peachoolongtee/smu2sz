"""Capex-mode contracts (spec v2 §7.7). Strict, frozen, reject unknown fields, like app.domain.models.

Money is integer fen, rates are integer bp and ratios are exact `Ratio`s. Every number carries the
formula and inputs that produced it (`Working`), so the UI can show the arithmetic verbatim.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models import Contract, Tier, Violation
from app.domain.money import Ratio

StructureKind = Literal["CASH_LINE", "LOAN", "LEASE"]
StructureResult = Literal["SELECTED", "ADMISSIBLE", "REJECTED", "INFEASIBLE"]

OWNER_ESTIMATE = "OWNER_ESTIMATE"  # evidence label: the owner entered it; the system did not observe it


class CapexCandidate(Contract):
    """One financing structure to test: an owner-approved menu facility at a given term."""

    facility_id: str
    term_months: int = Field(ge=1, le=360)


DEFAULT_CANDIDATES = (
    CapexCandidate(facility_id="FAC-ETL", term_months=18),
    CapexCandidate(facility_id="FAC-ETL", term_months=36),
    CapexCandidate(facility_id="FAC-LEASE", term_months=48),
)


class CapexRequest(Contract):
    """The owner's question and estimate. Defaults are the spec §7.7 case: a ¥600,000 line earning
    +¥22,000 a month from month 4 over 5 years, 10% hurdle, 36-month payback limit."""

    label: str = "¥600k die-cutting line"
    price_fen: int = Field(default=60_000_000, gt=0)
    monthly_uplift_fen: int = Field(default=2_200_000, ge=0)  # owner's estimate of operating cash flow
    uplift_start_month: int = Field(default=4, ge=1)
    life_months: int = Field(default=60, ge=1, le=600)
    hurdle_bp: int = Field(default=1000, ge=0)
    payback_limit_months: int = Field(default=36, ge=1)
    candidates: list[CapexCandidate] = Field(default_factory=lambda: list(DEFAULT_CANDIDATES))
    include_cash_line: bool = True  # also test "cash + credit line"
    # The pending decision reported alongside: the recurring buyer's terms moved to this many days
    # (spec §6, 45 → 60) and funded permanently. None leaves it out.
    extension_target_terms_days: int | None = Field(default=60, ge=0)
    extension_counterparty_id: str | None = None  # None: the only recurring invoice's buyer


class Working(Contract):
    """One reported number with its arithmetic."""

    label: str
    value: str  # display string ("¥380,885.77", "1.43×", "month 31")
    formula: str
    inputs: dict[str, str] = Field(default_factory=dict)
    evidence: str | None = None  # OWNER_ESTIMATE when a figure rests on the owner's entry


class DscrMonth(Contract):
    month: int
    dscr: Ratio | None  # None when debt service is zero
    passes: bool
    ebitda_fen: int
    debt_service_fen: int


class CapexStructure(Contract):
    id: str  # "cash_line", "loan_18m", "loan_36m", "lease_48m"
    label: str
    kind: StructureKind
    facility_id: str | None
    term_months: int | None
    rate_bp: int | None
    monthly_payment_fen: int | None
    total_interest_fen: int | None
    feasible: bool
    result: StructureResult
    violations: list[Violation] = Field(default_factory=list)
    dscr_by_month: list[DscrMonth] = Field(default_factory=list)
    min_dscr: Ratio | None = None
    leverage: Ratio | None = None
    extra_cost_vs_selected_fen: int | None = None
    note: str = ""
    workings: list[Working] = Field(default_factory=list)


class CapexResult(Contract):
    request: CapexRequest
    npv_fen: int
    payback_month: int | None  # None: no payback within the life
    npv_positive: bool
    payback_within_limit: bool
    worth_doing: bool
    estimate_note: str
    structures: list[CapexStructure]
    selected_id: str | None
    selected_facility_id: str | None
    leverage_financed: Ratio
    leverage_with_extension: Ratio | None
    extension_extra_receivables_fen: int | None
    dscr_limit_bp: int
    leverage_limit_bp: int
    required_tier: Tier
    recommendation: str
    workings: list[Working] = Field(default_factory=list)
    mandate_version: int
    state_version: int
