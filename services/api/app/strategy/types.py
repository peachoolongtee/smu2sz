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


__all__ = ["CandidatePackage", "MarginalImpact", "ScenarioState"]
