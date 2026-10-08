"""The internal extraction schema a backend (model or rules) fills.

Design rules:
- extra='forbid' everywhere; every field is required (nullable where optional), so the JSON schema is
  strict and the model must state each field explicitly.
- Every item quotes its evidence as an exact substring (`quote` / `quotes[].text`) of a named document.
  Code finds the offsets and builds the SourceSpan. The model never supplies offsets, ids or numbers:
  every number is a `*_text` fragment that must itself sit inside the item's quotes, and code parses it.
- There is no field that can express an operation, an approval, a tier or a facility to add.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.models import (
    BaseKind,
    Contingency,
    ContractField,
    DataRequestKind,
    DurationKind,
    FacilityKind,
    ObligationType,
)


class _X(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Quote(_X):
    doc_id: str
    text: str  # exact substring of the document's text


UnresolvedKey = Literal[
    "current_terms_days",  # target terms stated, current terms not: the verifier binds them from state
    "receivable_id",
    "base_amount",
    "base",
    "per_event_cost_fen",
    "events_per_year",
    "end_date",
    "scope",
]


class XObligation(_X):
    type: ObligationType
    quotes: list[Quote]  # >= 1; the first is the primary evidence
    rate_text: str | None  # e.g. "1.2%"; must sit inside a quote
    amount_text: str | None  # fixed amount of the obligation itself, e.g. "¥150 per shipment"
    base_kind: BaseKind
    base_amount_text: str | None  # face or cap of the base, e.g. "¥420k", "up to ¥400,000"
    events_per_year_text: str | None
    target_terms_text: str | None  # e.g. "60 days"
    current_terms_text: str | None  # e.g. "30" in "instead of 30"; only if the text states it
    contingency: Contingency
    duration_kind: DurationKind
    bounded_invoices_text: str | None  # e.g. "three" in "next three invoices"
    confidence: float
    unresolved: list[UnresolvedKey]


class XQuantity(_X):
    """A quantity a document states, used to detect conflicting sources (e.g. order size)."""

    kind: Literal["order_size", "invoice_amount"]
    doc_id: str
    quote: str
    amount_text: str


class XMissing(_X):
    """A discount/rebate/early payment mentioned without its material value."""

    obligation_type: ObligationType
    missing_field: Literal["rate_bp", "amount_fen"]
    doc_id: str
    quote: str


class XDataRequest(_X):
    kind: DataRequestKind
    doc_id: str
    quote: str


class XAuthorityClaim(_X):
    kind: Literal["PRE_APPROVAL", "PRIOR_AGREEMENT", "INSTRUCTION_OVERRIDE", "URGENCY", "IMPERSONATION"]
    doc_id: str
    quote: str


class XFundingClaim(_X):
    lender_name: str  # must sit inside the quote; otherwise the sender id is used
    doc_id: str
    quote: str
    amount_text: str | None
    rate_text: str | None


class OfferExtraction(_X):
    obligations: list[XObligation]
    quantities: list[XQuantity]
    unresolved_references: list[Quote]  # "as usual", "same arrangement": nothing is booked for these
    missing_material: list[XMissing]
    data_requests: list[XDataRequest]
    authority_claims: list[XAuthorityClaim]
    funding_claims: list[XFundingClaim]


ClauseField = Literal["principal", "rate", "fee", "tenor", "lead_time", "guarantee", "collateral", "covenant", "equity",
                      "advance_rate"]


class XClause(_X):
    field: ClauseField
    quote: str  # exact substring of the term sheet
    value_text: str  # must sit inside the quote


class TermSheetExtraction(_X):
    lender_name: str | None  # must sit inside the document; otherwise the sender id is used
    facility_kind: FacilityKind
    repayment: Literal["BULLET", "AMORTISING", "ON_RECEIPT"] | None
    clauses: list[XClause]
    authority_claims: list[XAuthorityClaim]


class XContractTerm(_X):
    """One term of a buyer contract, read from one chunk of it. `quote` is an exact substring of the chunk; every
    `*_text` fragment that is not null must sit inside `quote`. Code parses all of them; which fragment a field
    needs is fixed (see CONTRACT_SYSTEM_PROMPT)."""

    field: ContractField
    quote: str
    value_text: str | None  # the amount, rate, name, reference or description as written
    date_text: str | None  # a calendar date as written ("1 September 2026")
    period_text: str | None  # a length of time or a cadence ("forty-five (45) days", "every thirty (30) days")
    basis_text: str | None  # what payment terms count from ("after the Invoice Date")
    unit_text: str | None  # what a price is for ("for each Batch")
    trigger_text: str | None  # what a milestone payment waits for ("on acceptance")
    reference_text: str | None  # an invoice or document reference ("RCV-A")
    confidence: float


class ContractExtraction(_X):
    terms: list[XContractTerm]
    authority_claims: list[XAuthorityClaim]
    data_requests: list[XDataRequest]


def empty_offer_extraction() -> OfferExtraction:
    return OfferExtraction(
        obligations=[], quantities=[], unresolved_references=[], missing_material=[],
        data_requests=[], authority_claims=[], funding_claims=[],
    )


def empty_contract_extraction() -> ContractExtraction:
    return ContractExtraction(terms=[], authority_claims=[], data_requests=[])
