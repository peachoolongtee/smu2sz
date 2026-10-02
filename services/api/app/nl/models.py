"""/nl contracts: the enumerated intents, their typed slots, the request and the response.

The intent set is closed. Neither the rules parser nor the optional LLM classifier can name an action
outside it, and a slot is a typed value (an id, fen, bp, days), never free text that reaches the
verifier or the executor (INVARIANTS 1, 2 and 12).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Intent(StrEnum):
    EVALUATE_OFFER = "EVALUATE_OFFER"
    NEGOTIATE = "NEGOTIATE"
    ACCELERATE_RECEIPT = "ACCELERATE_RECEIPT"
    FUND_GAP = "FUND_GAP"
    REPAY_FACILITY = "REPAY_FACILITY"
    SHOW_STATUS = "SHOW_STATUS"
    SHOW_ALERTS = "SHOW_ALERTS"
    COMPARE_FINANCING = "COMPARE_FINANCING"
    RECONCILE = "RECONCILE"
    SHOW_RATIOS = "SHOW_RATIOS"
    CAPEX = "CAPEX"
    BORROWER_FILE = "BORROWER_FILE"
    EXPLAIN = "EXPLAIN"
    WHAT_IF = "WHAT_IF"
    RECORD_FACT = "RECORD_FACT"  # the owner states a new bill, invoice, delay or figure: read-only, nothing is recorded
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    COUNTERPARTY_MESSAGE = "COUNTERPARTY_MESSAGE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    AMBIGUOUS = "AMBIGUOUS"


Tier3Kind = Literal["SIGN_PERSONAL_GUARANTEE", "PLEDGE_COLLATERAL", "ISSUE_EQUITY", "CHANGE_MANDATE"]
Lang = Literal["en", "zh"]


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Slots(_Strict):
    """Typed values extracted from one request. Every id is checked against the registry or the
    fixtures before use; amounts are integer fen, rates integer bp."""

    fixture_id: str | None = None
    counterparty_id: str | None = None
    receivable_id: str | None = None
    facility_id: str | None = None
    amount_fen: int | None = Field(default=None, ge=1)
    rate_bp: int | None = Field(default=None, ge=0, le=10_000)
    terms_days: int | None = Field(default=None, ge=1, le=365)
    invoices: int | None = Field(default=None, ge=1, le=120)
    rebate_bp: int | None = Field(default=None, ge=0, le=10_000)
    approval_id: str | None = Field(default=None, pattern=r"^APR-\d{6}$")
    gap_index: int | None = Field(default=None, ge=1, le=20)
    buyer_profile: str | None = None
    quoted_text: str | None = Field(default=None, max_length=4000)
    zero_forward: bool = False
    use_financing: bool = False
    execute_now: bool = False
    tier3: Tier3Kind | None = None
    capex: bool = False
    quoted_approval: bool = False  # quoted/pasted text carried an approval instruction (ignored, logged)


class Parsed(_Strict):
    intent: Intent
    slots: Slots = Field(default_factory=Slots)
    correction: bool = False  # amends the session's pending plan
    confirm_plan: bool = False  # APPROVE/REJECT aimed at the pending plan, not an executor approval
    tentative: bool = False  # a loose reading (a need described, not an instruction): propose, never execute
    source: str = "rules"  # "rules" | "llm:<model>" | "clarification" | "fallback"
    matched: list[str] = Field(default_factory=list)


class ClarifyOption(_Strict):
    id: str
    label: str


class Clarification(_Strict):
    question: str
    options: list[ClarifyOption]


class PlanStep(_Strict):
    step: int
    kind: str  # an Operation kind (DRAW_FACILITY, ...) or a verification step (VERIFY, NEGOTIATE, ...)
    description: str
    status: Literal["PROPOSED", "EXECUTED", "REFUSED", "PENDING_APPROVAL", "DUPLICATE", "SKIPPED", "DONE", "INFO"]
    op_id: str | None = None
    condition: str | None = None  # e.g. "if the buyer refuses"


class NlRequest(BaseModel):
    """POST /nl body. `buyer_profile` picks the simulated buyer kernel in the sandbox (default: the
    counterparty's own profile). `request_id` makes a retried request replay-safe: the same id in the
    same session re-sends the same typed operations, which the executor returns as DUPLICATE."""

    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    actor: Literal["OWNER", "COUNTERPARTY"] = "OWNER"
    counterparty_id: str | None = Field(default=None, max_length=64)
    text: str = Field(min_length=1, max_length=4000)
    lang: Lang | None = None
    buyer_profile: str | None = Field(default=None, max_length=64)
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")


class NlResponse(BaseModel):
    session_id: str
    turn: int
    reply: str
    intent: Intent
    lang: Lang
    plan: list[PlanStep] = Field(default_factory=list)
    verdict: dict[str, Any] | None = None
    operations: list[dict[str, Any]] = Field(default_factory=list)
    clarification: Clarification | None = None
    awaiting_confirmation: bool = False
    amended: bool = False
    replayed: bool = False
    negotiation: dict[str, Any] | None = None
    security_events: list[str] = Field(default_factory=list)
    parse_source: str = "rules"
    trace_id: str
