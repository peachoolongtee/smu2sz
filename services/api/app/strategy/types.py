"""The three shared types of the strategy MVP (docs/STRATEGY_MVP_BRIEF.md section 3).

All are frozen `Contract` models. Money is integer fen, rates are integer bp, days are absolute (INVARIANT 9).
A display string is never stored: the routes add `*_display` siblings through `app.api.display.displayed`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.domain.models import Bp, Contract, Day, Fen, FinancialState, FundingPlan
from app.whatif.params import (
    DISCOUNT_MAX_BP,
    FACE_STEP_FEN,
    PRICE_MAX_BP,
    RATE_STEP_BP,
    REBATE_MAX_BP,
    TERMS_MAX,
    TERMS_MIN,
    TERMS_STEP,
)


class ScenarioState(Contract):
    """A labelled copy of the books under one assumption. Never stored, never the owner's actual position."""

    state: FinancialState
    label: str  # short: "RCV-A received today"
    assumption: str  # the sentence the UI may show: "assumes the ¥162,800 from Foshan arrives today"
    hypothetical: Literal[True] = True
    source_state_version: int
    day: Day


class CandidatePackage(Contract):
    """A buyer-addressed package with no inbound offer: a `WhatIfParams` plus a buyer id."""

    buyer_id: str
    terms_days: int = Field(ge=TERMS_MIN, le=TERMS_MAX)
    price_bp: Bp = Field(default=0, ge=0, le=PRICE_MAX_BP)
    early_pay_bp: Bp = Field(default=0, ge=0, le=DISCOUNT_MAX_BP)
    early_pay_face_fen: Fen | None = Field(default=None, gt=0)  # None: the whole open invoice
    rebate_bp: Bp = Field(default=0, ge=0, le=REBATE_MAX_BP)

    @field_validator("terms_days")
    @classmethod
    def _terms_grid(cls, v: int) -> int:
        if v % TERMS_STEP:
            raise ValueError(f"terms_days must be a multiple of {TERMS_STEP}")
        return v

    @field_validator("price_bp", "early_pay_bp", "rebate_bp")
    @classmethod
    def _rate_grid(cls, v: int) -> int:
        if v % RATE_STEP_BP:
            raise ValueError(f"rates move in {RATE_STEP_BP} bp steps")
        return v

    @field_validator("early_pay_face_fen")
    @classmethod
    def _face_grid(cls, v: int | None) -> int | None:
        if v is not None and v % FACE_STEP_FEN:
            raise ValueError("early_pay_face_fen must be a whole multiple of ¥100 (10000 fen)")
        return v


class MarginalImpact(Contract):
    """The delta between two books (after minus before). A negative `posted_cost_delta_fen` is a saving; a positive
    one is a cost and is kept as it is, never clamped."""

    label: str
    need_delta_fen: Fen
    posted_cost_delta_fen: Fen
    first_breach_before: Day | None
    first_breach_after: Day | None
    lowest_headroom_delta_fen: Fen
    budget_used_delta_fen: Fen
    breach_days_removed: int
    alerts_removed: list[str] = Field(default_factory=list)  # alert codes
    alerts_added: list[str] = Field(default_factory=list)
    before_needs_owner: bool
    after_needs_owner: bool
    before_executable_now: bool
    after_executable_now: bool
    before_cost_fen: Fen
    after_cost_fen: Fen
    before_need_fen: Fen
    after_need_fen: Fen


# ---------------------------------------------------------------- capacity (map #88, ticket #96, brief section F)

CapacityDimension = Literal[
    "cash_buffer", "credit_line", "invoice_finance", "concession", "concession_buyer", "dscr_room", "leverage_room"]
CapacityReading = Literal["TODAY", "AS_ISSUED"]


class CapacityWindow(Contract):
    """One dimension of capacity on one set of books, as a day series read down to its lowest point and back.

    Money is integer fen and days are absolute. A negative figure is kept (`over_by`), never clamped. `today_fen` is the
    figure on the books' first day; `lowest_fen` / `lowest_day` its lowest point (the first day it is reached);
    `through_day` the last day of the run that stays at that low (a cash buffer: the run below the floor); `recovers_day`
    the next day, when the figure rises, and `after_fen` the figure on that day (both None when it never does). A
    figure that is a point value (the concession budget, a covenant month) has no recovery. `reason` is a code
    (`capacity.reason_text` words it), never a sentence."""

    dimension: CapacityDimension
    facility_id: str | None
    today_fen: Fen
    after_fen: Fen | None
    lowest_fen: Fen
    lowest_day: Day
    recovers_day: Day | None
    through_day: Day
    over_by: bool
    reason: str | None = None
    buyer_id: str | None = None  # `concession_buyer`: the buyer whose cap this is
    reading: CapacityReading | None = None  # `invoice_finance`: TODAY (issued invoices) or AS_ISSUED (labelled)
    month: int | None = None  # `dscr_room` / `leverage_room`: the worst month
    recovery_assumed: bool = False  # the recovery rests on a discretionary repayment (ADR-0010 section 5)


class CovenantRoom(Contract):
    """The covenant room of one month, in money: how much more debt service (DSCR) or month-end debt (leverage) the
    month could carry. `None`: the covenant has nothing to test that month (no debt service). Room >= 0 exactly when
    the month has no DSCR / LEVERAGE breach."""

    month: int
    dscr_room_fen: Fen | None
    leverage_room_fen: Fen


class CapacitySnapshot(Contract):
    """The five capacity dimensions on one set of books, on the CONSERVATIVE trajectory under the router's committed
    plan (the cash buffer on the unfunded trajectory). `need_first_day` / `need_last_day` is the window in which cash is
    below the floor without funding: the router draws today for a later need, so the plan-based series are read
    beside it."""

    day: Day
    through_day: Day  # the last day of the series (the trajectory's end)
    windows: list[CapacityWindow]
    covenant_months: list[CovenantRoom] = Field(default_factory=list)
    no_borrowing_reason: str | None = None  # a code, when `allow_new_borrowing` is false
    plan_admissible: bool = True  # False: no admissible plan, the series are the unfunded ones
    need_first_day: Day | None = None
    need_last_day: Day | None = None


class CapacityBeforeAfter(Contract):
    """The snapshot for the books as they stand, and for the labelled copy with the package in force (None: no package)."""

    before: CapacitySnapshot
    after: CapacitySnapshot | None = None
    label: str = ""


SpareShape = Literal["S1"]
SpareCriterion = Literal["R-TODAY", "R-AS-ISSUED"]


class SpareCapacity(Contract):
    """The additional working-capital need FLOW could still support (brief F.3): X*, the largest one-off payment of X today
    (on a YUAN_STEP grid) for which the router still returns a plan that is admissible, needs no owner approval and can
    run (today, or as issued). `x_star_fen` is None when today's books already have no such plan (`refused_text`)."""

    shape: SpareShape
    criterion: SpareCriterion
    step_fen: Fen
    x_star_fen: Fen | None
    plan_at_x: FundingPlan | None
    plan_next: FundingPlan | None  # the plan at X* + one step
    binding_reason: str  # the router's own words for why the next step fails; "" when refused
    shape_text: str  # the shape and criterion sentence, always printed with the figure
    refused_text: str | None
    ceiling_fen: Fen  # the largest X the search considered
    evaluations: int  # router runs
    scanned: bool  # a neighbour of the boundary disagreed and the grid was scanned
    seconds: float


# ---------------------------------------------------------------- the late-payment stress (brief G.3)


class StressRow(Contract):
    """One fixed delay of the buyer-wide stress: what the unfunded projection and the router's committed plan say about
    the copy of the books in which the buyer pays every invoice `delay_days` late. A test, never a forecast."""

    delay_days: int
    lowest_fen: Fen
    lowest_day: Day
    breach_days: int
    need_fen: Fen
    plan_admissible: bool
    plan_cost_fen: Fen | None
    needs_owner: bool
    executable_now: bool
    first_breach_day: Day | None
    assumption: str
    funding_text: str


__all__ = [
    "CandidatePackage",
    "CapacityBeforeAfter",
    "CapacityDimension",
    "CapacityReading",
    "CapacitySnapshot",
    "CapacityWindow",
    "CovenantRoom",
    "MarginalImpact",
    "ScenarioState",
    "SpareCapacity",
    "SpareCriterion",
    "SpareShape",
    "StressRow",
]
