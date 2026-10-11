"""Shared domain contracts. Owned by the main architect; do not edit from a module.

Conventions (see docs/ARCHITECTURE.md):
- Money is integer fen (`*_fen`). Rates are integer basis points (`*_bp`). Ratios are `Ratio`.
- Time is an integer day offset from the fixture's `as_of` date (day 0). Month m covers days
  30(m-1)+1 .. 30m.
- Every model is strict, rejects unknown fields and is immutable. Use `model_copy(update=...)`.
- Change requests go through INTERFACE_CHANGE_REQUEST (docs/SUBAGENT_TASKBOARD.md).
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from app.domain.money import Ratio

Fen = int
Bp = int
Day = int


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


def _omit_empty(data: object, model: BaseModel, names: tuple[str, ...]) -> object:
    """ADR-0009 fields are left out of the serialised form while they hold their default (None / []), so a state
    without accepted adjustments serialises (and hashes: verdict ids, state digests) exactly as it did before."""
    if isinstance(data, dict):
        for n in names:
            if getattr(model, n) in (None, [], {}):
                data.pop(n, None)
    return data


# ---------------------------------------------------------------- evidence


class SourceSpan(Contract):
    """A character range in one source document. `text` must equal doc[start:end]."""

    doc_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str

    @model_validator(mode="after")
    def _ordered(self) -> SourceSpan:
        if self.end < self.start:
            raise ValueError("span end before start")
        return self


class SourceDocument(Contract):
    """An inbound message or attachment. Always untrusted data."""

    doc_id: str
    channel: Literal["chat", "email", "portal", "attachment", "term_sheet", "owner"]
    sender_id: str
    received_day: Day
    text: str
    parent_doc_id: str | None = None
    filename: str | None = None


# ---------------------------------------------------------------- obligations (Terms Guard)


class ObligationType(StrEnum):
    IMMEDIATE_DISCOUNT = "IMMEDIATE_DISCOUNT"
    TERMS_EXTENSION = "TERMS_EXTENSION"  # days_delta > 0 lengthens terms; < 0 shortens
    CONTINGENT_REBATE = "CONTINGENT_REBATE"
    VOLUME_COMMITMENT = "VOLUME_COMMITMENT"
    OPERATIONAL_CONCESSION = "OPERATIONAL_CONCESSION"
    PRICE_ADJUSTMENT = "PRICE_ADJUSTMENT"  # rate_bp > 0: price increase the buyer pays on future invoices (Counter B)
    CLAIMED_PRIOR_CONCESSION = "CLAIMED_PRIOR_CONCESSION"


class Contingency(StrEnum):
    FIRM = "FIRM"
    CONTINGENT = "CONTINGENT"  # counted at maximum under conservative mode
    CLAIMED_UNEVIDENCED = "CLAIMED_UNEVIDENCED"  # never booked


class BaseKind(StrEnum):
    INVOICE = "INVOICE"  # one named invoice (receivable_id)
    FUTURE_INVOICES = "FUTURE_INVOICES"  # recurring invoices to this buyer
    PERIOD_PURCHASES = "PERIOD_PURCHASES"  # e.g. next quarter's purchases (amount_fen = cap)
    PER_EVENT = "PER_EVENT"  # e.g. per shipment
    UNSPECIFIED = "UNSPECIFIED"


class ObligationBase(Contract):
    kind: BaseKind
    amount_fen: Fen | None = None  # face or cap of the base, if stated
    receivable_id: str | None = None
    events_per_year: int | None = None  # PER_EVENT only


class DurationKind(StrEnum):
    ONE_OFF = "ONE_OFF"
    RECURRING_PERPETUAL = "RECURRING_PERPETUAL"  # until an end date is extracted
    RECURRING_BOUNDED = "RECURRING_BOUNDED"  # `invoices` or `end_day` is set


class Duration(Contract):
    kind: DurationKind
    invoices: int | None = None
    end_day: Day | None = None


class Obligation(Contract):
    """One typed promise the supplier would make. Proposed by the compiler; decided by code."""

    id: str
    type: ObligationType
    counterparty_id: str
    rate_bp: Bp | None = None  # discount / rebate / price-adjustment rate
    amount_fen: Fen | None = None  # fixed amount, e.g. ¥150 per shipment
    days_delta: int | None = None  # payment-terms change in days
    target_terms_days: int | None = None  # terms the text states ("60 days"); the verifier derives days_delta
    effective_day: Day | None = None  # when it takes effect / is settled
    base: ObligationBase
    contingency: Contingency
    duration: Duration
    spans: list[SourceSpan] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    unresolved: list[str] = Field(default_factory=list)


class Abstention(Contract):
    field: str
    reason: str
    spans: list[SourceSpan] = Field(default_factory=list)


class DataRequestKind(StrEnum):
    MANDATE_VALUE = "MANDATE_VALUE"
    RESERVE_FLOOR = "RESERVE_FLOOR"
    FACILITY_LIMIT = "FACILITY_LIMIT"
    FUNDING_MENU = "FUNDING_MENU"
    OTHER_COUNTERPARTY_TERMS = "OTHER_COUNTERPARTY_TERMS"
    RESERVATION_VALUE = "RESERVATION_VALUE"
    SYSTEM_PROMPT = "SYSTEM_PROMPT"
    OTHER_PRIVATE = "OTHER_PRIVATE"


class DataRequest(Contract):
    """A counterparty asking for protected state. Always refused and logged."""

    kind: DataRequestKind
    span: SourceSpan


class AuthorityClaim(Contract):
    """Text asserting authority it cannot have: pre-approval, prior agreement, urgency, 'ignore rules'."""

    kind: Literal["PRE_APPROVAL", "PRIOR_AGREEMENT", "INSTRUCTION_OVERRIDE", "URGENCY", "IMPERSONATION"]
    span: SourceSpan


class UnsolicitedFundingClaim(Contract):
    """A lender offer found in a message. Never enters the funding menu."""

    lender_name: str
    amount_fen: Fen | None = None
    rate_bp: Bp | None = None
    span: SourceSpan


class CompileStatus(StrEnum):
    COMPILED = "COMPILED"
    ABSTAINED = "ABSTAINED"  # a material field had no span
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"


class CompiledOffer(Contract):
    """Compiler output for a buyer message: a proposal, never a decision."""

    offer_id: str
    version: int = 1
    counterparty_id: str
    doc_ids: list[str]
    received_day: Day
    status: CompileStatus
    obligations: list[Obligation] = Field(default_factory=list)
    abstentions: list[Abstention] = Field(default_factory=list)
    data_requests: list[DataRequest] = Field(default_factory=list)
    authority_claims: list[AuthorityClaim] = Field(default_factory=list)
    funding_claims: list[UnsolicitedFundingClaim] = Field(default_factory=list)
    compiler: str  # e.g. "fixture-cache" | "claude-sonnet-5-5" | "deepseek-flash"
    prompt_version: str
    # Positive proof that the whole message is explained by `obligations`: every amount, rate, day count
    # and invoice reference is accounted for and no other request is left unread. False by default: only
    # a proven offer can be accepted without the owner (docs/adr/0005-autonomy-requires-proof.md).
    autonomy_eligible: bool = False
    autonomy_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- facilities (Debt Desk)


class FacilityKind(StrEnum):
    CREDIT_LINE = "CREDIT_LINE"
    INVOICE_FINANCING = "INVOICE_FINANCING"
    BUYER_EARLY_PAY = "BUYER_EARLY_PAY"
    GOV_GUARANTEED_LOAN = "GOV_GUARANTEED_LOAN"
    EQUIPMENT_TERM_LOAN = "EQUIPMENT_TERM_LOAN"
    EQUIPMENT_LEASE = "EQUIPMENT_LEASE"
    BANK_ACCEPTANCE_BILL = "BANK_ACCEPTANCE_BILL"  # 银票 discounting
    EQUITY = "EQUITY"  # reference only; Tier 3


class FacilityStatus(StrEnum):
    COMMITTED = "COMMITTED"  # usable for hard constraints
    PENDING = "PENDING"  # applied / approved in principle: ZERO for hard constraints
    NOT_APPLIED = "NOT_APPLIED"
    REFERENCE_ONLY = "REFERENCE_ONLY"


class Repayment(StrEnum):
    BULLET = "BULLET"
    AMORTISING = "AMORTISING"
    ON_RECEIPT = "ON_RECEIPT"  # repaid from the financed receivable


class CovenantKind(StrEnum):
    DSCR_MIN = "DSCR_MIN"
    LEVERAGE_MAX = "LEVERAGE_MAX"
    CLEAN_DOWN = "CLEAN_DOWN"


class Covenant(Contract):
    """A facility-specific covenant. `definition` is shown on screen with its inputs."""

    id: str
    facility_id: str
    kind: CovenantKind
    threshold_bp: Bp | None = None  # DSCR 1.25x -> 12500; leverage 2.5x -> 25000
    clean_down_days: int | None = None  # consecutive zero-balance days per year
    definition: str  # e.g. "monthly EBITDA / scheduled debt service (principal + interest)"
    formula: str  # e.g. "EBITDA_m / DS_m >= 1.25"


class Facility(Contract):
    """An owner-approved funding source. Only the owner adds these; messages never can."""

    id: str
    name: str
    kind: FacilityKind
    lender_id: str
    status: FacilityStatus
    owner_approved: bool
    limit_fen: Fen
    drawn_fen: Fen = 0
    advance_rate_bp: Bp | None = None  # invoice financing: 8000 = 80% of eligible receivables
    rate_bp: Bp  # nominal annual rate; monthly schedules (loans and leases) use rate/12, not an effective rate
    fee_bp_per_advance: Bp = 0  # e.g. 25 bp per 30-day advance
    fee_period_days: int | None = None
    upfront_fee_bp: Bp = 0
    lead_time_days: int  # time to cash once used / approved
    term_months: int | None = None
    repayment: Repayment
    collateral: bool = False
    personal_guarantee: bool = False
    counts_in_leverage: bool = True
    counts_in_debt_service: bool = True
    covenants: list[Covenant] = Field(default_factory=list)
    source_note: str = ""  # e.g. "synthetic fixture" or facility-letter reference


class TermSheetClause(Contract):
    field: Literal["principal", "rate", "fee", "tenor", "lead_time", "guarantee", "collateral", "equity", "covenant",
                   "advance_rate"]
    value_text: str
    span: SourceSpan


class CompiledTermSheet(Contract):
    """Compiler output for a lender term sheet. The owner must approve before it becomes a Facility."""

    doc_id: str
    lender_name: str
    proposed_facility: Facility | None
    all_in_rate_bp: Bp | None  # fees folded in, 12-month basis
    clauses: list[TermSheetClause]
    abstentions: list[Abstention] = Field(default_factory=list)
    tier3_clauses: list[TermSheetClause] = Field(default_factory=list)
    authority_claims: list[AuthorityClaim] = Field(default_factory=list)
    data_requests: list[DataRequest] = Field(default_factory=list)
    status: CompileStatus
    compiler: str
    prompt_version: str


# ---------------------------------------------------------------- contracts (read by the agent, confirmed by the owner)
#
# docs/handover/03_contract_ingestion_brief.md. A contract reading is shown and confirmed, nothing more: no term of
# it is projected, verified or executed, and a confirmed contract never writes the books (the language model never
# sets the starting state). Every term carries the span it was read from; no span, no term.


class ContractField(StrEnum):
    PARTY_SUPPLIER = "PARTY_SUPPLIER"
    PARTY_BUYER = "PARTY_BUYER"
    CONTRACT_REFERENCE = "CONTRACT_REFERENCE"
    SIGNED_DATE = "SIGNED_DATE"
    START_DATE = "START_DATE"
    END_DATE = "END_DATE"
    DURATION = "DURATION"
    PRICE = "PRICE"  # per delivery or per unit, or a lump sum
    INVOICING = "INVOICING"  # cadence, and the first scheduled invoice date when stated
    SCHEDULED_INVOICE = "SCHEDULED_INVOICE"  # an invoice the contract schedules on a stated date
    PAYMENT_TERMS = "PAYMENT_TERMS"  # days, with what they count from (invoice, delivery, acceptance)
    EARLY_PAYMENT = "EARLY_PAYMENT"  # a discount for settling early, and its window
    MILESTONE = "MILESTONE"  # a share of the price due on a trigger
    RETENTION = "RETENTION"
    LATE_INTEREST = "LATE_INTEREST"
    DELIVERABLE = "DELIVERABLE"  # what the supplier must deliver (display only)
    REQUIRED_DOCUMENT = "REQUIRED_DOCUMENT"  # a document payment depends on (display only)
    AMENDMENT = "AMENDMENT"  # how the contract may be changed


# Fields a contract may state several times with different values (each is its own term); every other field has one
# value, and two clauses stating different values for it are conflicting sources.
MULTI_VALUED_CONTRACT_FIELDS = frozenset({
    ContractField.SCHEDULED_INVOICE, ContractField.MILESTONE, ContractField.DELIVERABLE, ContractField.REQUIRED_DOCUMENT,
})


class PaymentBasis(StrEnum):
    """What payment terms count from. The books count every term from the invoice date."""

    INVOICE = "INVOICE"
    DELIVERY = "DELIVERY"
    ACCEPTANCE = "ACCEPTANCE"
    MONTH_END = "MONTH_END"  # the end of the month of the invoice (月结)


class PriceUnit(StrEnum):
    PER_DELIVERY = "PER_DELIVERY"  # per batch, delivery or shipment
    PER_UNIT = "PER_UNIT"
    PER_MONTH = "PER_MONTH"
    LUMP_SUM = "LUMP_SUM"


class ContractTerm(Contract):
    """One term read from a contract. Every value is parsed by code from a fragment inside `span`; the model supplies
    no number, date or classification of its own."""

    field: ContractField
    span: SourceSpan
    clause: str | None = None  # where the span sits, as the document numbers it ("4.2", "6.1(b)", "Schedule 1, 1")
    value_text: str | None = None  # the fragment that states the value, as written
    amount_fen: Fen | None = None
    rate_bp: Bp | None = None
    days: int | None = None
    months: int | None = None
    date: str | None = None  # ISO yyyy-mm-dd; converted to a day number only against the books' own anchor
    basis: PaymentBasis | None = None
    unit: PriceUnit | None = None
    reference: str | None = None  # an invoice or document reference, as written
    text: str | None = None  # a name, description or requirement, as written
    business_days: bool = False  # a day count stated in business days (the engine counts calendar days)


class CompiledContract(Contract):
    """Compiler output for a buyer contract: a proposal the owner confirms or rejects, never a decision."""

    doc_id: str
    status: CompileStatus
    terms: list[ContractTerm] = Field(default_factory=list)
    not_found: list[ContractField] = Field(default_factory=list)  # fields no clause states (shown as "not found")
    abstentions: list[Abstention] = Field(default_factory=list)
    authority_claims: list[AuthorityClaim] = Field(default_factory=list)
    data_requests: list[DataRequest] = Field(default_factory=list)
    chunks: int = 1
    compiler: str
    prompt_version: str


class DocumentKind(StrEnum):
    BUYER_CONTRACT = "BUYER_CONTRACT"
    LENDER_AGREEMENT = "LENDER_AGREEMENT"


class DocumentStatus(StrEnum):
    PROPOSED = "PROPOSED"  # read by the agent, waiting for the owner
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class DocumentFlag(Contract):
    """Text in a document the owner sees before deciding. A blocking flag (an instruction addressed to the agent)
    means the document cannot be confirmed at all; the others are warnings."""

    kind: str  # an AuthorityClaim kind, or "DATA_REQUEST:<DataRequestKind>"
    span: SourceSpan
    blocking: bool
    note: str


def text_hash(text: str) -> str:
    """The sha256 (hex) of a document's text as UTF-8: the one function that binds an owner's decision to the exact text
    shown. A `ContractRecord` is built with it and refuses to load when its stored hash is not this of its stored text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ContractRecord(Contract):
    """A document the agent read: its text, the reading, and the owner's decision on it. Confirmation is logged in
    the hash chain (CONFIRM_DOCUMENT) and changes no money state."""

    id: str  # "DOC-000001", assigned by the store
    kind: DocumentKind
    counterparty_id: str
    title: str
    document: SourceDocument  # untrusted text; every span indexes into document.text
    doc_hash: str  # sha256 of document.text (UTF-8): what the owner's decision is bound to
    source: str  # "fixture:<id>", "upload:<filename>" or "text"
    uploaded_day: Day
    contract: CompiledContract | None = None  # BUYER_CONTRACT
    term_sheet: CompiledTermSheet | None = None  # LENDER_AGREEMENT
    flags: list[DocumentFlag] = Field(default_factory=list)
    suggested_facility_id: str | None = None  # LENDER_AGREEMENT: the existing facility it appears to describe
    linked_facility_id: str | None = None  # LENDER_AGREEMENT: the facility the owner linked it to on confirmation
    status: DocumentStatus = DocumentStatus.PROPOSED
    decided_day: Day | None = None
    decided_seq: int | None = None  # the log entry of the owner's decision
    superseded_by: str | None = None  # BUYER_CONTRACT: the later confirmed contract of this buyer that replaced it

    @model_validator(mode="after")
    def _reading_matches_kind(self) -> ContractRecord:
        if self.kind == DocumentKind.BUYER_CONTRACT and (self.contract is None or self.term_sheet is not None):
            raise ValueError("a buyer contract record holds a contract reading and no term sheet")
        if self.kind == DocumentKind.LENDER_AGREEMENT and (self.term_sheet is None or self.contract is not None):
            raise ValueError("a lender agreement record holds a term-sheet reading and no contract")
        if self.kind == DocumentKind.BUYER_CONTRACT and (self.linked_facility_id or self.suggested_facility_id):
            raise ValueError("only a lender agreement links to a facility")
        return self

    @model_validator(mode="after")
    def _hash_matches_text(self) -> ContractRecord:
        """The hash the owner's decision is bound to is the hash of the text stored beside it: a row edited in the database
        fails to load rather than vouch for other text."""
        if self.doc_hash != text_hash(self.document.text):
            raise ValueError("the stored document hash is not the hash of the stored document text")
        return self

    @property
    def blocked(self) -> bool:
        return any(f.blocking for f in self.flags)


# ---------------------------------------------------------------- mandate


class Tier(StrEnum):
    TIER_1 = "TIER_1"  # autonomous inside the mandate
    TIER_2 = "TIER_2"  # owner approval
    TIER_3 = "TIER_3"  # never


class Mandate(Contract):
    """Owner-signed limits. Versioned, revocable, expiring. The agent can never edit it."""

    org_id: str
    version: int = Field(ge=1)
    min_cash_fen: Fen
    max_aggregate_forward_concession_fen: Fen
    forward_concession_horizon_days: int = 365
    per_buyer_caps_fen: dict[str, Fen] = Field(default_factory=dict)
    max_immediate_discount_bp: Bp | None = None
    min_dscr_bp: Bp
    max_leverage_bp: Bp
    max_apr_bp: Bp
    require_clean_down: bool = True
    allow_new_borrowing: bool = True
    tier2_single_commitment_fen: Fen  # any single commitment above this is Tier 2
    horizon_days: int
    issued_day: Day
    expires_day: Day
    revoked: bool = False
    public_key_hex: str | None = None
    signature_hex: str | None = None


# ---------------------------------------------------------------- financial state


class FlowKind(StrEnum):
    PAYROLL = "PAYROLL"
    SUPPLIER = "SUPPLIER"
    OPERATING = "OPERATING"
    RECEIVABLE = "RECEIVABLE"
    DEBT_SERVICE = "DEBT_SERVICE"
    OTHER = "OTHER"


class CashFlow(Contract):
    id: str
    day: Day
    amount_fen: Fen  # + inflow, - outflow
    kind: FlowKind
    label: str
    counterparty_id: str | None = None
    confirmed: bool = True  # unconfirmed inflows are ignored in conservative mode


class Receivable(Contract):
    id: str
    counterparty_id: str
    face_fen: Fen
    issue_day: Day
    terms_days: int
    status: Literal["OPEN", "FINANCED", "SETTLED", "FAILED"] = "OPEN"
    confirmed: bool = True  # buyer-confirmed (确权)
    settled_fen: Fen = 0  # face already settled by receipts; outstanding = face_fen - settled_fen (ADR-0006)
    advance_fen: Fen = 0  # financing advance still outstanding on this invoice (0 when not FINANCED)
    advance_facility_id: str | None = None
    # ADR-0009: face_fen / terms_days are contractual; these keep the values before accepted adjustments
    base_face_fen: Fen | None = None
    base_terms_days: int | None = None
    applied: list[str] = Field(default_factory=list)  # InvoiceAdjustment ids written onto this invoice
    # Red team e, F4: face settled early under each early-pay obligation (obligation id -> face), portion by portion;
    # what an obligation still covers is its face less this. Omitted while empty.
    early_paid_fen: dict[str, Fen] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _serialise(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]
        return _omit_empty(handler(self), self, ("base_face_fen", "base_terms_days", "applied", "early_paid_fen"))

    @property
    def outstanding_fen(self) -> Fen:
        return self.face_fen - self.settled_fen

    @property
    def due_day(self) -> Day:
        return self.issue_day + self.terms_days


class RecurringInvoice(Contract):
    """A buyer invoiced every `every_days`; future receivables are generated from this."""

    counterparty_id: str
    face_fen: Fen
    every_days: int
    next_issue_day: Day
    terms_days: int


class DebtPosition(Contract):
    id: str
    facility_id: str | None
    label: str
    principal_fen: Fen
    monthly_debt_service_fen: Fen  # scheduled principal + interest
    # The payment schedule (`app.financial.debts.debt_payments`): simple annual interest on the principal since the
    # last payment (0: the whole payment is principal), paid every `payment_every_days` from `next_payment_day`.
    rate_bp: int = 0
    payment_every_days: int = 30
    next_payment_day: Day = 30  # the first month-end after day 0


class ForwardConcession(Contract):
    """A concession already committed (counts against the cap)."""

    id: str
    counterparty_id: str
    value_fen: Fen
    commitment_id: str | None = None
    label: str


class InvoiceAdjustment(Contract):
    """ADR-0009: an accepted terms extension or price adjustment, with its scope fixed at acceptance.

    Scope is either an explicit list of invoice ids (`receivable_ids`) or an issue-day range
    [`from_issue_day`, `until_issue_day`] (until None: perpetual) of the counterparty's invoices."""

    id: str  # "<commitment_id>:<obligation_id>"
    commitment_id: str
    obligation_id: str
    counterparty_id: str
    days_delta: int = 0
    price_bp: Bp = 0
    receivable_ids: list[str] | None = None
    from_issue_day: Day | None = None
    until_issue_day: Day | None = None
    contingent_gain: bool = False  # never written onto an invoice; only the EXPECTED projection applies it


class ExpectedOrder(Contract):
    """A buyer order the supplier expects (e.g. next quarter). Rebate bases bind to it."""

    counterparty_id: str
    label: str  # "next quarter"
    start_day: Day
    end_day: Day
    amount_fen: Fen
    firm: bool = False


class Counterparty(Contract):
    id: str
    name: str
    role: Literal["BUYER", "LENDER", "SUPPLIER", "OWNER"]
    known: bool = True  # on the owner's registry


class FundingLot(Contract):
    """ADR-0010: one draw or invoice advance with its dates. Over a facility's lots, the sum of `remaining_fen`
    equals its `drawn_fen`. Cash lands on `arrival_day` (request day + lead time); interest runs from it."""

    id: str  # the operation id that created it ("ASSUMED:..." for a balance older than the books)
    facility_id: str
    principal_fen: Fen
    remaining_fen: Fen
    request_day: Day
    arrival_day: Day
    receivable_id: str | None = None  # an invoice advance: the financed invoice
    maturity_day: Day | None = None  # bullet term loans: arrival + 30 × term months
    settled: bool = False  # the cash has been credited
    assumed_date: bool = False  # a balance that existed before the books started, dated to their first day


class FinancialState(Contract):
    """Verified starting state. A fixture or the ledger writes it; the compiler never does."""

    org_id: str
    as_of: str  # ISO date for day 0
    cash_fen: Fen
    flows: list[CashFlow] = Field(default_factory=list)
    receivables: list[Receivable] = Field(default_factory=list)
    recurring_invoices: list[RecurringInvoice] = Field(default_factory=list)
    facilities: list[Facility] = Field(default_factory=list)
    debts: list[DebtPosition] = Field(default_factory=list)
    forward_concessions: list[ForwardConcession] = Field(default_factory=list)
    expected_orders: list[ExpectedOrder] = Field(default_factory=list)
    counterparties: list[Counterparty] = Field(default_factory=list)
    invoice_adjustments: list[InvoiceAdjustment] = Field(default_factory=list)  # ADR-0009, in acceptance order
    monthly_ebitda_fen: Fen
    state_version: int = 1
    as_of_day: Day = 0  # the books are closed for every day before this one; cash_fen is cash at its start (ADR-0006)
    lots: list[FundingLot] = Field(default_factory=list)  # ADR-0010, in creation order
    # The demo scenario these books were seeded from (its dated outside-world events apply to them in DEMO_MODE
    # only). None for provisioned books and for a fixture loaded directly: no scenario events ever apply.
    scenario: str | None = None

    @model_serializer(mode="wrap")
    def _serialise(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]
        return _omit_empty(handler(self), self, ("invoice_adjustments", "lots", "scenario"))


# ---------------------------------------------------------------- funding actions and trajectory


class FundingActionKind(StrEnum):
    DRAW = "DRAW"  # credit line / loan draw
    REPAY = "REPAY"
    FINANCE_INVOICE = "FINANCE_INVOICE"  # advance against receivable; repaid on receipt
    EARLY_PAY = "EARLY_PAY"  # accept buyer early payment on (part of) a receivable
    DISCOUNT_BILL = "DISCOUNT_BILL"  # 银票 discounting


class FundingAction(Contract):
    kind: FundingActionKind
    facility_id: str
    day: Day
    amount_fen: Fen  # cash raised (net) for draws/advances; face for EARLY_PAY
    receivable_id: str | None = None
    repay_day: Day | None = None
    rate_bp: Bp | None = None  # EARLY_PAY discount rate
    # The day the cash lands, filled by the router for DRAW and FINANCE_INVOICE (request day + the facility's lead
    # time, the engine's own rule). Display only: no figure depends on it, and the engine ignores it.
    lands_day: Day | None = None
    # The first day the executor could run this leg: the invoice's issue day for an advance on an invoice not yet
    # issued, else the request day. Display only, like `lands_day`: nothing is priced or decided from it.
    available_from_day: Day | None = None


class Mode(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"  # hard constraints use only this
    EXPECTED = "EXPECTED"  # shown beside it, never relied on


class LedgerEventKind(StrEnum):
    OPENING = "OPENING"
    FLOW = "FLOW"
    RECEIPT = "RECEIPT"
    EARLY_RECEIPT = "EARLY_RECEIPT"
    DISCOUNT = "DISCOUNT"
    DRAW = "DRAW"
    ADVANCE = "ADVANCE"
    FEE = "FEE"
    INTEREST = "INTEREST"
    REPAYMENT = "REPAYMENT"
    CONCESSION = "CONCESSION"


class LedgerEvent(Contract):
    day: Day
    kind: LedgerEventKind
    amount_fen: Fen  # signed effect on cash
    label: str
    ref: str | None = None  # flow / receivable / facility / obligation id
    formula: str | None = None


class DayPoint(Contract):
    day: Day
    opening_fen: Fen
    closing_fen: Fen
    debt_outstanding_fen: Fen
    forward_concession_fen: Fen
    events: list[LedgerEvent] = Field(default_factory=list)


class MonthPoint(Contract):
    month: int
    ebitda_fen: Fen
    debt_service_fen: Fen
    total_debt_fen: Fen
    dscr: Ratio | None  # None when debt service is zero
    leverage: Ratio | None  # None when EBITDA <= 0 (undefined; fails any maximum)


class Trajectory(Contract):
    mode: Mode
    horizon_days: int
    days: list[DayPoint]
    months: list[MonthPoint]
    min_cash_fen: Fen
    min_cash_day: Day
    first_breach_day: Day | None  # first day closing < mandate min cash, if a floor was given
    interest_posted_fen: Fen
    fees_posted_fen: Fen
    discounts_posted_fen: Fen


# ---------------------------------------------------------------- violations and verdicts


class ViolationCode(StrEnum):
    AGG_CONCESSION_EXCEEDED = "AGG_CONCESSION_EXCEEDED"
    PER_BUYER_CAP_EXCEEDED = "PER_BUYER_CAP_EXCEEDED"
    IMMEDIATE_DISCOUNT_EXCEEDED = "IMMEDIATE_DISCOUNT_EXCEEDED"
    RESERVE_BREACH = "RESERVE_BREACH"
    DSCR_BREACH = "DSCR_BREACH"
    LEVERAGE_BREACH = "LEVERAGE_BREACH"
    CLEAN_DOWN_BREACH = "CLEAN_DOWN_BREACH"
    MAX_APR_EXCEEDED = "MAX_APR_EXCEEDED"
    DISCOUNT_ABOVE_BREAK_EVEN = "DISCOUNT_ABOVE_BREAK_EVEN"  # early pay dearer than the SME's own marginal funding
    EARLY_PAY_NOT_NEEDED = "EARLY_PAY_NOT_NEEDED"  # early pay with no funding need: the discount buys nothing
    EARLY_PAY_DEARER_THAN_PLAN = "EARLY_PAY_DEARER_THAN_PLAN"  # costs at least as much as the router's plan without it
    UNCOMMITTED_FACILITY = "UNCOMMITTED_FACILITY"
    LEAD_TIME_TOO_LONG = "LEAD_TIME_TOO_LONG"
    TIER3_PERSONAL_GUARANTEE = "TIER3_PERSONAL_GUARANTEE"
    TIER3_COLLATERAL = "TIER3_COLLATERAL"
    TIER3_EQUITY = "TIER3_EQUITY"
    TIER3_MANDATE_CHANGE = "TIER3_MANDATE_CHANGE"
    UNKNOWN_COUNTERPARTY = "UNKNOWN_COUNTERPARTY"
    UNEVIDENCED_PRIOR_CONCESSION = "UNEVIDENCED_PRIOR_CONCESSION"
    DATA_EXTRACTION_REFUSED = "DATA_EXTRACTION_REFUSED"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    UNRESOLVED_SCOPE = "UNRESOLVED_SCOPE"  # e.g. perpetual term with no end, material field missing
    MANDATE_EXPIRED = "MANDATE_EXPIRED"
    MANDATE_REVOKED = "MANDATE_REVOKED"
    MANDATE_VERSION_MISMATCH = "MANDATE_VERSION_MISMATCH"
    BAD_SIGNATURE = "BAD_SIGNATURE"
    REPLAY = "REPLAY"
    COMMITMENT_EXPIRED = "COMMITMENT_EXPIRED"
    TERMS_CHANGED = "TERMS_CHANGED"
    INSUFFICIENT_AUTHORITY = "INSUFFICIENT_AUTHORITY"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    NEW_BORROWING_NOT_ALLOWED = "NEW_BORROWING_NOT_ALLOWED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"  # e.g. over limit, receivable not open
    STALE_OPERATION = "STALE_OPERATION"  # op dated to a different simulated day
    FEATURE_DISABLED = "FEATURE_DISABLED"
    STALE_VERDICT = "STALE_VERDICT"  # the books or mandate moved since the verdict and it no longer holds
    CONFLICTING_COMMITMENT = "CONFLICTING_COMMITMENT"  # another live commitment already covers the receivable


class Violation(Contract):
    code: ViolationCode
    message: str
    day: Day | None = None
    month: int | None = None
    observed: str | None = None  # display string, e.g. "¥26,455.62" or "1.13x"
    limit: str | None = None
    curable: bool | None = None
    cure_cost_fen: Fen | None = None
    cure_note: str | None = None
    formula: str | None = None
    inputs: dict[str, str] = Field(default_factory=dict)
    spans: list[SourceSpan] = Field(default_factory=list)


class CostLine(Contract):
    label: str
    fen: Fen
    facility_id: str | None = None
    formula: str
    # the leg costs more a year than the mandate lets the agent borrow alone: the owner must approve it
    needs_owner_approval: bool = False
    approval_reason: str = ""
    # the executor cannot run this leg today (an advance on an invoice that is not issued yet)
    executable_now: bool = True
    not_executable_reason: str = ""


class RejectedCandidate(Contract):
    label: str
    reasons: list[ViolationCode]
    note: str = ""


class FundingPlan(Contract):
    id: str
    basis: Literal["COMMITTED", "EXPECTED"]
    need_fen: Fen
    actions: list[FundingAction]
    costs: list[CostLine]
    total_cost_fen: Fen  # sum of posted fen amounts
    admissible: bool
    violations: list[Violation] = Field(default_factory=list)
    marginal_cost_annual: Ratio | None = None  # all-in annual rate of the marginal committed source
    marginal_facility_id: str | None = None
    rejected: list[RejectedCandidate] = Field(default_factory=list)
    label: str = ""
    # Admissible but not autonomous: some leg's effective annual cost is above the mandate's `max_apr_bp`, so the
    # executor queues it for the owner. `approval_reason` names each such leg (rate, days held, ceiling).
    needs_owner_approval: bool = False
    approval_reason: str = ""
    # Some leg cannot run today: the plan prices a financing the agent can only carry out once the invoice exists
    # (it ranks after every plan that can run today). `not_executable_reason` names each such leg.
    executable_now: bool = True
    not_executable_reason: str = ""
    # When `executable_now` is false: the first day every leg could run (the latest leg's `available_from_day`).
    # Display only.
    available_from_day: Day | None = None


class ConcessionValue(Contract):
    """Forward value of one obligation over the mandate's concession horizon."""

    obligation_id: str
    value_fen: Fen
    basis: str  # e.g. "committed marginal source: invoice financing 10.8417%"
    formula: str
    per_invoice_fen: Fen | None = None


class Outcome(StrEnum):
    ACCEPT = "ACCEPT"
    COUNTER = "COUNTER"
    REJECT = "REJECT"
    NO_DEAL = "NO_DEAL"
    NEEDS_OWNER_APPROVAL = "NEEDS_OWNER_APPROVAL"
    NO_VERDICT = "NO_VERDICT"  # abstained / conflicting sources / clarification needed


class CounterProposal(Contract):
    id: str
    label: str  # "Option A"
    text: str  # template-filled outbound wording; never free-generated with secrets
    obligations: list[Obligation]
    supplier_cost_fen: Fen  # immediate cost to the supplier (e.g. discount + line interest)
    forward_value_fen: Fen = 0  # forward-concession value the commitment would book
    rationale: str
    formula: str


class Verdict(Contract):
    id: str
    offer_id: str
    offer_version: int
    outcome: Outcome
    violations: list[Violation] = Field(default_factory=list)
    bound_obligations: list[Obligation] = Field(default_factory=list)  # what was verified; commit exactly these
    concession_values: list[ConcessionValue] = Field(default_factory=list)
    forward_concession_total_fen: Fen = 0
    counters: list[CounterProposal] = Field(default_factory=list)
    plan: FundingPlan | None = None
    required_tier: Tier
    mandate_version: int
    state_version: int
    calc_version: str
    summary: str


# ---------------------------------------------------------------- commitments and operations


class CommitmentStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    FULFILLED = "FULFILLED"


class Commitment(Contract):
    id: str
    offer_id: str
    offer_version: int
    counterparty_id: str
    verdict_id: str
    terms_hash: str  # sha256 of canonical obligations; changed terms cannot reuse it
    obligations: list[Obligation]
    status: CommitmentStatus
    nonce: str
    expires_day: Day
    mandate_version: int
    forward_value_fen: Fen
    # Red team d, F5: early-pay obligations already paid on time while the commitment stays ACTIVE for its other
    # live terms (a receipt is matched to an obligation once). F3: early-pay obligations whose day passed unpaid
    # when the clock ended the commitment (EXPIRED); they are still reported as lapsed. Omitted while empty.
    settled_obligations: list[str] = Field(default_factory=list)
    lapsed_obligations: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _serialise(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]
        return _omit_empty(handler(self), self, ("settled_obligations", "lapsed_obligations"))


class Actor(StrEnum):
    OWNER = "OWNER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    COUNTERPARTY = "COUNTERPARTY"


class _OpBase(Contract):
    op_id: str
    idempotency_key: str
    mandate_version: int
    requested_by: Actor
    source_verdict_id: str | None = None
    day: Day


class AcceptOffer(_OpBase):
    kind: Literal["ACCEPT_OFFER"] = "ACCEPT_OFFER"
    offer_id: str
    offer_version: int
    terms_hash: str
    nonce: str


class CounterOffer(_OpBase):
    kind: Literal["COUNTER_OFFER"] = "COUNTER_OFFER"
    offer_id: str
    counter_id: str


class RejectOffer(_OpBase):
    kind: Literal["REJECT_OFFER"] = "REJECT_OFFER"
    offer_id: str
    reason_codes: list[ViolationCode]


class RecordCommitment(_OpBase):
    kind: Literal["RECORD_COMMITMENT"] = "RECORD_COMMITMENT"
    commitment_id: str
    nonce: str


class DrawFacility(_OpBase):
    kind: Literal["DRAW_FACILITY"] = "DRAW_FACILITY"
    facility_id: str
    amount_fen: Fen = Field(gt=0)


class RepayFacility(_OpBase):
    kind: Literal["REPAY_FACILITY"] = "REPAY_FACILITY"
    facility_id: str
    amount_fen: Fen = Field(gt=0)


class SubmitInvoiceForFinancing(_OpBase):
    kind: Literal["SUBMIT_INVOICE_FOR_FINANCING"] = "SUBMIT_INVOICE_FOR_FINANCING"
    facility_id: str
    receivable_id: str
    advance_fen: Fen = Field(gt=0)


class ReceivePayment(_OpBase):
    kind: Literal["RECEIVE_PAYMENT"] = "RECEIVE_PAYMENT"
    receivable_id: str
    amount_fen: Fen = Field(gt=0)
    # The bank's own reference for the credit (a feed id, a statement line). When present, a second receipt on the same
    # receivable carrying the same reference is the same bank event under a new key and is refused, whatever its key.
    bank_reference: str | None = Field(default=None, min_length=1, max_length=64)
    # Red team e, F6: the day the receipt was reported, when the owner approves an agent's report later. Set only by
    # the executor when it re-runs a queued report (the request day); the early-pay deadline is tested on it, cash is
    # booked on the approval day. Omitted while None.
    reported_day: Day | None = None

    @model_serializer(mode="wrap")
    def _serialise(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]
        return _omit_empty(handler(self), self, ("reported_day",))


class RequestOwnerApproval(_OpBase):
    kind: Literal["REQUEST_OWNER_APPROVAL"] = "REQUEST_OWNER_APPROVAL"
    subject: str
    payload_op_id: str


class ApplyForFacility(_OpBase):
    """Always Tier 2: the agent prepares; only the owner applies."""

    kind: Literal["APPLY_FOR_FACILITY"] = "APPLY_FOR_FACILITY"
    facility_id: str
    amount_fen: Fen
    term_months: int | None = None


class SignPersonalGuarantee(_OpBase):
    kind: Literal["SIGN_PERSONAL_GUARANTEE"] = "SIGN_PERSONAL_GUARANTEE"
    facility_id: str


class PledgeCollateral(_OpBase):
    kind: Literal["PLEDGE_COLLATERAL"] = "PLEDGE_COLLATERAL"
    facility_id: str


class IssueEquity(_OpBase):
    kind: Literal["ISSUE_EQUITY"] = "ISSUE_EQUITY"
    amount_fen: Fen


class ChangeMandate(_OpBase):
    kind: Literal["CHANGE_MANDATE"] = "CHANGE_MANDATE"
    new_version: int


class AddFacility(_OpBase):
    """Owner-only. From AGENT or COUNTERPARTY it is refused (INVARIANT 3)."""

    kind: Literal["ADD_FACILITY"] = "ADD_FACILITY"
    facility: Facility


Operation = Annotated[
    AcceptOffer
    | CounterOffer
    | RejectOffer
    | RecordCommitment
    | DrawFacility
    | RepayFacility
    | SubmitInvoiceForFinancing
    | ReceivePayment
    | RequestOwnerApproval
    | ApplyForFacility
    | SignPersonalGuarantee
    | PledgeCollateral
    | IssueEquity
    | ChangeMandate
    | AddFacility,
    Field(discriminator="kind"),
]


class OperationStatus(StrEnum):
    EXECUTED = "EXECUTED"
    REFUSED = "REFUSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    DUPLICATE = "DUPLICATE"  # same idempotency key: original result returned, nothing re-run


class OperationResult(Contract):
    op_id: str
    kind: str
    status: OperationStatus
    tier: Tier
    violations: list[Violation] = Field(default_factory=list)
    seq: int | None = None  # position in the operations log
    entry_hash: str | None = None
    prev_hash: str | None = None
    effective_day: Day | None = None  # simulated day the executor ran it
    approval_id: str | None = None  # set when PENDING_APPROVAL
    message: str = ""


# ---------------------------------------------------------------- security events


class SecurityEventKind(StrEnum):
    INJECTION = "INJECTION"
    UNKNOWN_COUNTERPARTY = "UNKNOWN_COUNTERPARTY"
    DATA_EXTRACTION = "DATA_EXTRACTION"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    UNEVIDENCED_CLAIM = "UNEVIDENCED_CLAIM"
    REPLAY = "REPLAY"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    TERMS_CHANGED = "TERMS_CHANGED"
    TIER3 = "TIER3"


class SecurityEvent(Contract):
    id: str
    day: Day
    kind: SecurityEventKind
    counterparty_id: str | None
    action_taken: str  # e.g. "refused; nothing booked"
    detail: str
    spans: list[SourceSpan] = Field(default_factory=list)
    trace_id: str | None = None
