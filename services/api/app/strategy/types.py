"""The three shared types of the strategy MVP (docs/STRATEGY_MVP_BRIEF.md section 3).

All are frozen `Contract` models. Money is integer fen, rates are integer bp, days are absolute (INVARIANT 9).
A display string is never stored: the routes add `*_display` siblings through `app.api.display.displayed`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.domain.models import Bp, Contract, Day, Fen, FinancialState
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


class Concentration(Contract):
    """How much of what the supplier is owed sits with one buyer: four separate shares, never combined into a score
    (brief G.1; mission section 17). Exact fractions of integer fen, shown at 1 dp, half-up (ADR-0002), "100%" only when the
    share is exactly 1; the `*_bp` fields are the same shares as integer basis points in [0, 10000] with the display
    rounding of ADR-0002, never rounding a part-share up to 10000 or a nonzero share down to 0. Parts are never adjusted
    to add to 100. Aggregate counterparties (an owner-entered `aggregate` input) are left out of every denominator and are
    named in `aggregate_note`; `ar_all_fen` keeps the firm's whole receivable.

    Context, not mandate: nothing here changes an outcome, a tier, a code, a counter, a cap or a plan. A concentration may
    add a fact line to a verdict, order which buyer's stress appears first, and raise an existing alert's wording; it is never
    an input to the verifier, the mandate or the router. The sentences are written for `lang` and are the only words."""

    buyer_id: str
    buyer_name: str
    day: Day
    lang: Literal["en", "zh"]
    is_aggregate: bool = False
    excluded_aggregates: list[str] = Field(default_factory=list)  # counterparty ids left out of the denominators
    aggregate_note: str | None = None
    # share of current open AR: face less settled, over OPEN and FINANCED receivables (overdue counts, unissued does not)
    ar_buyer_fen: Fen = 0
    ar_total_fen: Fen = 0  # without the aggregates: the denominator
    ar_all_fen: Fen = 0  # with them
    ar_share_bp: Bp | None = Field(default=None, ge=0, le=10_000)
    ar_text: str
    # share of the receipts due on [receipts_from_day, receipts_to_day) in the conservative projection of the current books
    receipts_from_day: Day
    receipts_to_day: Day
    receipts_buyer_fen: Fen = 0
    receipts_total_fen: Fen = 0
    receipts_share_bp: Bp | None = Field(default=None, ge=0, le=10_000)
    receipts_text: str
    # Phase 2 fills these from the inputs; in Phase 1 they are None with the reason
    annual_sales_share_bp: Bp | None = Field(default=None, ge=0, le=10_000)
    annual_sales_reason: str
    contribution_share_bp: Bp | None = Field(default=None, ge=0, le=10_000)
    contribution_reason: str
    sentence: str  # the AR line and the receipts line, as the deal surface shows them


class PaymentOpen(Contract):
    """An invoice still unpaid past its due day: a lower bound ("at least N days"), never counted as a completed payment."""

    receivable_id: str
    due_day: Day
    days_overdue: int  # day less due day, so far
    outstanding_fen: Fen


class PaymentInvoice(Contract):
    """A completed invoice (settled, its last receipt inside the 365 days). `late_days` is the face-weighted signed lateness
    of its receipts, rounded half-up to a whole day for display; `last_late_days` is the lateness of the last receipt."""

    receivable_id: str
    face_fen: Fen
    late_days: int
    last_late_days: int
    last_receipt_day: Day


class PaymentBehaviour(Contract):
    """How a buyer has paid, from the operations log (brief G.2; map #88 r2 section 5): only EXECUTED RECEIVE_PAYMENT entries,
    replayed by `alerts.reconcile` (no second matcher); the receipt day is `reported_day` else the entry day; the due day is the
    one in force on the invoice. The unit is a completed invoice; its lateness is the exact face-weighted mean of its receipts'
    signed lateness, shown in whole days half-up (ADR-0002). Early payment never offsets lateness (the average is over
    max(0, late)). Portions paid early under an agreement are excluded from lateness and counted apart. Open overdue invoices are
    censored: listed, never counted.

    A statistic below its minimum number of completed invoices is None (average and median 3, P75 4, P90 10, trend 12); below
    the minimum nothing called "typical" exists and `insufficient_text` says so. Median, never mean, is what any surface shows.
    Observed outranks owner-entered: an owner's `typical_delay_days` stands in only below 3 completed invoices."""

    buyer_id: str
    buyer_name: str
    day: Day
    lang: Literal["en", "zh"]
    window_days: int
    completed: int  # completed invoices in the window
    invoices: list[PaymentInvoice] = Field(default_factory=list)
    average_days_late: int | None = None
    median_days_late: int | None = None
    p75_days_late: int | None = None
    p90_days_late: int | None = None
    on_time_count: int | None = None  # completed invoices whose last receipt came on or before the due day
    on_time_share_bp: Bp | None = Field(default=None, ge=0, le=10_000)  # by count
    on_time_face_bp: Bp | None = Field(default=None, ge=0, le=10_000)  # by face
    max_recent_delay_days: int | None = None  # the worst last-receipt delay among invoices completed in the last 90 days
    trend: Literal["later", "earlier", "about_the_same"] | None = None  # newest 6 against the 6 before, medians
    early_agreed_count: int = 0  # receipts that paid a portion early under an agreement, on time by definition
    early_agreed_missed: int = 0  # early payments promised for this buyer that lapsed
    open_overdue: list[PaymentOpen] = Field(default_factory=list)
    survivorship: bool = False  # an open invoice is later than P75 (the median below 4 invoices)
    survivorship_text: str | None = None
    # the stress test's "typical" delay: the observed median from 3 completed invoices, else the owner's figure, else None
    typical_delay_days: int | None = None
    delay_basis: Literal["OBSERVED", "OWNER_ENTERED", "NONE"] = "NONE"
    owner_delay_days: int | None = None
    owner_delay_text: str | None = None  # the owner's figure in words: used (below 3 invoices) or set beside the median (5+ days apart)
    insufficient: bool
    insufficient_text: str | None = None
    sentence: str  # the headline


__all__ = ["CandidatePackage", "Concentration", "MarginalImpact", "PaymentBehaviour", "PaymentInvoice", "PaymentOpen",
           "ScenarioState"]
