"""Verifier view contracts. Strict, frozen, reject unknown fields (same rules as app.domain.models).

`VerdictBundle` is what `evaluate()` returns: the `Verdict` (the domain contract the executor and the
API store) plus what the screens need beside it: the conservative trajectory, the committed and
expected plans, the security events to log and the predicates that held.
"""

from __future__ import annotations

from pydantic import Field

from app.domain.models import (
    Contract,
    FundingPlan,
    Obligation,
    SecurityEvent,
    Trajectory,
    Verdict,
)
from app.funding import ComparisonRow

CALC_VERSION = "tl-v2.0"


class BindNote(Contract):
    """What `bind()` resolved, could not resolve, or only flagged."""

    obligation_id: str | None  # None for offer-level notes (e.g. an unresolved reference)
    field: str  # e.g. "base.receivable_id", "days_delta", "unresolved_reference"
    resolved: bool
    material: bool  # an unresolved material field gives UNRESOLVED_SCOPE
    message: str


class PassedCheck(Contract):
    """A predicate that HELD, shown on the verdict screen beside the violations."""

    code: str  # e.g. "DSCR_MIN", "LEVERAGE_MAX", "CLEAN_DOWN", "MIN_CASH", "MAX_APR"
    label: str
    observed: str
    limit: str
    formula: str
    inputs: dict[str, str] = Field(default_factory=dict)


class OwnerConstraints(Contract):
    """A goal the owner states for one evaluation, stricter than the mandate (e.g. EX12: "get paid early
    without giving anything away next quarter"). It can only tighten a verdict: a package that violates it
    gets COUNTER (or REJECT when no counter satisfies it), with the verifier's own counters filtered or
    adjusted to satisfy it. None on a field means no limit."""

    max_early_pay_bp: int | None = Field(default=None, ge=0)  # highest early-settlement discount
    zero_forward_concessions: bool = False  # no obligation may carry a positive forward value
    max_terms_days: int | None = Field(default=None, ge=0)  # longest payment terms


class VerdictBundle(Contract):
    verdict: Verdict
    trajectory: Trajectory | None = None  # conservative, under the bookable obligations, no new funding
    plan_committed: FundingPlan | None = None
    plan_expected: FundingPlan | None = None  # shown only, never relied on (INVARIANT 11)
    security_events: list[SecurityEvent] = Field(default_factory=list)
    passed_checks: list[PassedCheck] = Field(default_factory=list)
    bound_obligations: list[Obligation] = Field(default_factory=list)
    notes: list[BindNote] = Field(default_factory=list)
    cure_plan: FundingPlan | None = None  # permanent-capable sources only (RESERVE_BREACH cure)
    comparison: list[ComparisonRow] = Field(default_factory=list)  # spec §7.4 rows at the offered rate
