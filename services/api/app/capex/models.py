"""Capex-mode contracts (spec v2 §7.7). Strict, frozen, reject unknown fields, like app.domain.models.

Money is integer fen, rates are integer bp and ratios are exact `Ratio`s. Every number carries the
formula and inputs that produced it (`Working`), so the UI can show the arithmetic verbatim.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from app.domain.models import Contract, Tier, Violation
from app.domain.money import Ratio


def _omit_unset(data: object, model: Contract, names: tuple[str, ...]) -> object:
    """ADR-0013 fields are left out of the serialised form while unset, so a request or result without a payment
    schedule serialises (and hashes: the application key) exactly as it did before."""
    if isinstance(data, dict):
        for n in names:
            if getattr(model, n) is None:
                data.pop(n, None)
    return data

StructureKind = Literal["CASH_LINE", "LOAN", "LEASE"]
StructureResult = Literal["SELECTED", "ADMISSIBLE", "REJECTED", "INFEASIBLE"]

CHARGES_BASIS = "lowest total financing charges (interest + fees, not discounted)"
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


class CapexPayment(Contract):
    """One dated payment of the purchase price (ADR-0013): a row of a capex contract's derived payment schedule."""

    day: int = Field(ge=0)
    amount_fen: int = Field(gt=0)
    label: str = ""


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
    # ADR-0013: the purchase paid on these days (a capex contract's schedule) instead of all at once. They must sum to
    # `price_fen`. None: the original single payment (on the day the financing lands, or today from cash).
    payments: list[CapexPayment] | None = None

    @model_validator(mode="after")
    def _payments_sum_to_the_price(self) -> CapexRequest:
        if self.payments is not None:
            if not self.payments:
                raise ValueError("payments, when given, list at least one payment")
            if sum(p.amount_fen for p in self.payments) != self.price_fen:
                raise ValueError("the payments must sum to price_fen exactly")
        return self

    @model_serializer(mode="wrap")
    def _serialise(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]
        return _omit_unset(handler(self), self, ("payments",))


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
    upfront_fee_fen: int | None = None
    # Ranked quantity: total interest + upfront fee, not discounted (CHARGES_BASIS). None when not computable.
    charges_total_fen: int | None = None
    # True when the candidate term differs from the facility's actual term_months: shown as an illustration,
    # never selected and never applied for.
    hypothetical: bool = False
    feasible: bool
    result: StructureResult
    violations: list[Violation] = Field(default_factory=list)
    dscr_by_month: list[DscrMonth] = Field(default_factory=list)
    min_dscr: Ratio | None = None
    leverage: Ratio | None = None  # None when EBITDA <= 0 (undefined)
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
    leverage_financed: Ratio | None  # None when EBITDA <= 0 (undefined)
    leverage_with_extension: Ratio | None
    extension_extra_receivables_fen: int | None
    dscr_limit_bp: int
    leverage_limit_bp: int
    required_tier: Tier
    recommendation: str
    workings: list[Working] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    as_of_day: int = 0  # the day the books were read: this result is a snapshot of that day
    mandate_version: int
    state_version: int
    # ADR-0013, only with a payment schedule (omitted otherwise): the last day the daily cash test sees, and what the
    # schedule pays after it, which no structure's daily cash test covers.
    horizon_end_day: int | None = None
    beyond_horizon_fen: int | None = None

    @model_serializer(mode="wrap")
    def _serialise(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]
        return _omit_unset(handler(self), self, ("horizon_end_day", "beyond_horizon_fen"))
