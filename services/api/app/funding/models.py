"""View contracts the funding router returns to the UI and the verifier.

Strict, frozen, reject unknown fields (same rules as app.domain.models). Money is integer fen;
every display string is formatted here on the server (INVARIANT 13: the UI never computes money).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.domain.models import (
    Contract,
    FacilityKind,
    FacilityStatus,
    FundingAction,
    ViolationCode,
)
from app.domain.money import Ratio


class MenuRow(Contract):
    """One facility on the funding menu, costed on the same basis as every other source (spec §7.3)."""

    facility_id: str
    name: str
    kind: FacilityKind
    status: FacilityStatus
    committed: bool
    owner_approved: bool
    expected_only: bool  # PENDING / NOT_APPLIED: shown in the expected plan, never relied on
    all_in_rate: Ratio  # annual simple rate, fees folded in
    all_in_display: str  # e.g. "10.84%"
    rate_basis: str  # the same-basis formula, e.g. "7.8% + 0.25% × 365/30 = ≈10.8417%"
    time_to_cash_days: int
    limit_fen: int
    available_fen: int  # 0 unless COMMITTED (INVARIANT 4)
    limit_display: str
    available_display: str
    counts_in_leverage: bool
    counts_in_debt_service: bool
    is_debt: bool
    short_term_only: bool  # a clean-down line cannot carry a permanent need
    covenant_notes: list[str] = Field(default_factory=list)
    admissible_for_need: bool
    needs_owner_approval: bool = False  # the tariff itself is above the mandate's max APR: any use needs the owner
    reasons: list[ViolationCode] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ComparisonResult(StrEnum):
    SELECTED = "SELECTED"
    ADMISSIBLE = "ADMISSIBLE"
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"


class ComparisonRow(Contract):
    """One row of the spec §7.4 router table."""

    key: str  # stable id: "full_discount", "line_partial_early_pay", "router_optimum", ...
    label: str
    components: list[str]
    actions: list[FundingAction] = Field(default_factory=list)
    cost_fen: int | None  # None when no cost is computable (e.g. an uncommitted facility)
    cost_display: str  # e.g. "¥841.64 + ¥1,871.30 = ¥2,712.94" or "—"
    result: ComparisonResult
    reasons: list[ViolationCode] = Field(default_factory=list)
    breach_day: int | None = None
    note: str = ""
    needs_owner_approval: bool = False  # admissible, but a leg is above the max APR: the owner must approve
    approval_reason: str = ""
    executable_now: bool = True
    not_executable_reason: str = ""  # display only: why the agent cannot run an admissible row today (empty when it can)

    # For a candidate that breaks the reserve: the deepest shortfall below the floor and the day it is deepest
    # (the router's `Eval.shortfall`; display only, so an insufficient option can say what it leaves uncovered).
    shortfall_fen: int | None = None
    worst_day: int | None = None
