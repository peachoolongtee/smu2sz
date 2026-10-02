"""Alert and reconciliation contracts. Strict, frozen, integer fen (docs/ARCHITECTURE.md conventions)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.domain.models import Contract, Day, Fen
from app.domain.money import Ratio


class Severity(StrEnum):
    CRITICAL = "CRITICAL"  # a hard limit fails on the conservative trajectory
    WARNING = "WARNING"  # a limit is close, or something needs the owner's attention
    INFO = "INFO"


class AlertKind(StrEnum):
    RESERVE_BREACH_AHEAD = "RESERVE_BREACH_AHEAD"
    RESERVE_HEADROOM_LOW = "RESERVE_HEADROOM_LOW"
    COVENANT_HEADROOM_LOW = "COVENANT_HEADROOM_LOW"
    CLEAN_DOWN_AT_RISK = "CLEAN_DOWN_AT_RISK"
    COMMITMENT_EXPIRING = "COMMITMENT_EXPIRING"
    RECEIVABLE_PAST_DUE = "RECEIVABLE_PAST_DUE"
    CONCESSIONS_NEAR_CAP = "CONCESSIONS_NEAR_CAP"
    FACILITY_REPAYABLE = "FACILITY_REPAYABLE"  # a drawn credit-line balance the books can repay today
    FUNDING_IN_TRANSIT = "FUNDING_IN_TRANSIT"  # a draw or advance requested but not yet landed (ADR-0010)


# Typed operation kinds an alert may suggest. A suggestion is never executed automatically: the
# owner or the agent must submit it to POST /operations, where the executor computes its tier.
SuggestedKind = Literal[
    "DRAW_FACILITY",
    "REPAY_FACILITY",
    "SUBMIT_INVOICE_FOR_FINANCING",
    "RECEIVE_PAYMENT",
    "APPLY_FOR_FACILITY",
    "ACCEPT_OFFER",
    "RECORD_COMMITMENT",
    "COUNTER_OFFER",
    "GENERATE_BORROWER_FILE",
]


# The kinds POST /alerts/{id}/act may turn into typed operations (the executor still decides the tier).
EXECUTABLE_KINDS = frozenset({"DRAW_FACILITY", "REPAY_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING", "APPLY_FOR_FACILITY"})


class SuggestedAction(Contract):
    operation_kind: SuggestedKind
    facility_id: str | None = None
    receivable_id: str | None = None
    commitment_id: str | None = None
    offer_id: str | None = None
    amount_fen: Fen | None = None
    note: str = ""
    # What a committed cure costs, read from the engine (never a formula of its own): the interest and fees the
    # books post over the horizon with this action minus without it. Empty when the cost is not known.
    cost_fen: Fen | None = None
    cost_days: int | None = None  # days the money is out: arrival to the repayment the projection shows
    annual_rate: Ratio | None = None  # cost / amount × 365 / cost_days, exact
    cost_formula: str = ""
    # annual_rate is above the mandate's max APR: the agent may not run it alone, so the executor queues it for
    # the owner's approval (Tier 2); it runs only after the owner approves
    above_apr_cap: bool = False
    executes_automatically: Literal[False] = False


class Alert(Contract):
    id: str
    kind: AlertKind
    severity: Severity
    title: str
    detail: str
    formula: str
    day: Day | None = None
    month: int | None = None
    amount_fen: Fen | None = None  # shortfall, past-due face, concession total ...
    committed_cure: bool | None = None  # reserve breaches: can COMMITTED facilities cure it?
    commitment_id: str | None = None  # past-due kind: the commitment whose early payment did not arrive
    receivable_id: str | None = None  # past-due kind: the receivable concerned
    inputs: dict[str, str] = Field(default_factory=dict)
    suggested: list[SuggestedAction] = Field(default_factory=list)
    actionable: bool = False  # at least one suggestion POST /alerts/{id}/act can submit to the executor
    basis: Literal["CONSERVATIVE"] = "CONSERVATIVE"


class MatchStatus(StrEnum):
    MATCHED = "MATCHED"  # amount equals what is owed (face, or face less an accepted discount)
    SHORT_PAYMENT = "SHORT_PAYMENT"  # received < face − agreed discount
    DISCOUNT_IGNORED = "DISCOUNT_IGNORED"  # an accepted early-pay discount was not honoured as agreed
    UNEXPECTED_AMOUNT = "UNEXPECTED_AMOUNT"  # between face − discount and face, matching neither
    UNMATCHED = "UNMATCHED"  # no open receivable or commitment explains the receipt


class ReceiptMatch(Contract):
    seq: int
    entry_hash: str
    op_id: str
    day: Day | None
    receivable_id: str
    counterparty_id: str | None
    received_fen: Fen
    face_fen: Fen | None
    agreed_discount_fen: Fen = 0
    expected_fen: Fen | None  # what the accepted terms say should arrive on this day
    difference_fen: Fen | None  # received − expected
    commitment_id: str | None = None
    status: MatchStatus
    flagged: bool
    detail: str
    formula: str


class OutstandingReceivable(Contract):
    receivable_id: str
    counterparty_id: str
    face_fen: Fen
    due_day: Day
    status: str
    past_due: bool


class PromiseStatus(StrEnum):
    AWAITED = "AWAITED"  # commitment live, obligation still binds, its day has not passed
    RECEIVED = "RECEIVED"  # the agreed amount arrived (commitment FULFILLED / matched receipt)
    LAPSED = "LAPSED"  # its day passed with the receivable unpaid; receivable back on its due day
    SETTLED_OTHERWISE = "SETTLED_OTHERWISE"  # the receivable was settled, but not by the agreed early-pay amount


class PromisedReceipt(Contract):
    """An early payment a live commitment promised, and what became of it."""

    commitment_id: str
    obligation_id: str
    receivable_id: str
    counterparty_id: str
    promised_day: Day | None
    face_fen: Fen  # the portion P of the invoice the discount covers
    discount_fen: Fen  # posted discount d on P
    expected_fen: Fen  # P − d
    status: PromiseStatus
    receipt_seq: int | None = None  # log seq of the receipt that paid it, when RECEIVED
    detail: str
    formula: str


class ReconciliationReport(Contract):
    as_of_day: Day
    receipts: list[ReceiptMatch]
    outstanding: list[OutstandingReceivable]
    matched: int
    flagged: int
    received_total_fen: Fen
    expected_total_fen: Fen
    chain_head_hash: str | None
    chain_valid: bool
    promised: list[PromisedReceipt] = Field(default_factory=list)
    lapsed_promises: int = 0
