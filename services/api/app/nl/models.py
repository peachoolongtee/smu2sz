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
    SHOW_DEAL = "SHOW_DEAL"  # where a buyer's deal stands: the confirmed contract and the live books (read-only)
    EXPLAIN = "EXPLAIN"
    WHAT_IF = "WHAT_IF"
    RECORD_FACT = "RECORD_FACT"  # the owner states a new bill, invoice, delay or figure: read-only, nothing is recorded
    CHANGES = "CHANGES"  # "what changed today?": a read of the operations log, the forecast and what is still open
    # A question about the books that no other intent answers right (app/nl/ask.py): read-only and owner only. It never
    # proposes a plan, compiles an offer, queues or executes anything, or writes to the operations log.
    ASK_BOOKS = "ASK_BOOKS"
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
    # ASK_BOOKS only: the owner's own question, passed to the read-only answer layer (app.nl.answers). It never reaches the
    # verifier, the compiler or the executor.
    question: str | None = Field(default=None, max_length=4000)


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


class NlPageContext(BaseModel):
    """What the owner's page was showing when the question was asked: ids only, never an amount or a sentence. The
    server checks every id against its own stores and ignores what it cannot find (it trusts nothing but the id).
    `since_day` is the owner's last-visit marker (the same one GET /home takes); it only chooses where "what
    changed" starts, and a value in the future is dropped."""

    model_config = ConfigDict(extra="forbid")

    page: str = Field(max_length=64, pattern=r"^/[A-Za-z0-9/_-]{0,63}$")
    offer_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    decision_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    invoice_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    since_day: int | None = Field(default=None, ge=0, le=100_000)


class NlScope(BaseModel):
    """What the owner's question is about, from the URL contract (`customer`, `decision`, `invoice`, `scenario`; map #121, ticket #130). The
    page shows it before the question is asked and the request carries exactly this, so a request that sends a scope sends no stale
    offer: the scope replaces the offer, decision and invoice ids of `context`. An empty scope is the whole company. The server checks every key
    against its own stores and answers with a clarification, never a guess, for one it cannot honour."""

    model_config = ConfigDict(extra="forbid")

    customer: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    invoice: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    decision: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    scenario: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$")


class ScopeUsed(BaseModel):
    """The scope the server answered in: its kind (`company`, `customer`, `invoice`, `decision`) and its label in the owner's words."""

    kind: Literal["company", "customer", "invoice", "decision"]
    label: str


class CardFigure(BaseModel):
    """One key figure of an answer card: the server's value as it said it, a short label in the turn's language, and its tone."""

    label: str
    value: str
    tone: Literal["danger", "ok", "neutral"] = "neutral"


class CardAction(BaseModel):
    """A link under an answer card to the page that shows what the chip names. A link only: it never approves, sends or runs anything."""

    label: str
    href: str
    kind: Literal["link"] = "link"


class AnswerCard(BaseModel):
    """An answer that has structure, laid out (app/nl/answer_card.py): the lead sentence (the yes/no or the figure), the key figures, the rest of the
    reply, what it was worked out from, and links to the pages that show it. Every word and every href is the server's (INVARIANT 13). Owner only."""

    lead: str
    figures: list[CardFigure] = Field(default_factory=list)
    body: str = ""
    basis: str = ""
    all_figures: list[CardFigure] = Field(default_factory=list)
    actions: list[CardAction] = Field(default_factory=list)


class ContextEcho(BaseModel):
    """What the server actually used from the page context (so the panel can say "Discussing: the Foshan offer")."""

    offer_id: str | None = None
    counterparty_name: str | None = None
    decision_id: str | None = None
    invoice_id: str | None = None


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
    context: NlPageContext | None = None  # the owner's page; a counterparty's context is ignored
    scope: NlScope | None = None  # what the question is about (the URL contract); when sent it replaces the offer, decision and invoice of `context`


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
    context_echo: ContextEcho | None = None  # the validated page context this turn used (owner channel only)
    scope_used: ScopeUsed | None = None  # the scope this turn was answered in, when the request carried one (owner channel only)
    card: AnswerCard | None = None  # an answer with structure, laid out with links to the pages that show it (owner channel only)
