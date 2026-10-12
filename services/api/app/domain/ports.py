"""Module interfaces. Each module implements its port as plain functions/classes with these
signatures. Owned by the main architect; request changes via INTERFACE_CHANGE_REQUEST.

Dependency direction (no cycles):
  domain  <-  financial  <-  covenants, mandate  <-  funding  <-  verifier  <-  operations
  domain  <-  compiler (reads documents only; never state, mandate or menu)
  persistence/commitments store what operations decide; they decide nothing.
  counterparties (buyer kernel, mock lenders) talk through typed messages only.
  nl orchestrates: compiler -> verifier -> operations. It never skips the verifier.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from app.domain.models import (
    Commitment,
    CompiledOffer,
    CompiledTermSheet,
    ConcessionValue,
    ContractRecord,
    ContractTerm,
    CounterProposal,
    Facility,
    FinancialState,
    FundingAction,
    FundingPlan,
    Mandate,
    Mode,
    Obligation,
    Operation,
    OperationResult,
    SecurityEvent,
    SourceDocument,
    Tier,
    Trajectory,
    Verdict,
    Violation,
)
from app.domain.money import Ratio

if TYPE_CHECKING:  # the record is persistence's; a runtime import would close a cycle (persistence implements this port)
    from app.persistence.records import CustomerInputRecord


@dataclass(frozen=True, slots=True)
class ContractGuardRow:
    """A contract record without its document text: who it is with, where it stands, and the typed readings the outbound
    guard protects (the terms with their quotes, the proposed facility, the clauses' quotes). It is what every caller that does
    not show the document reads (`LedgerStore.contract_guard_rows`); the text, its spans and its hash check are not loaded."""

    id: str
    kind: str  # DocumentKind value
    counterparty_id: str
    status: str  # DocumentStatus value
    doc_hash: str
    superseded_by: str | None
    decided_day: int | None
    decided_seq: int | None = None
    terms: tuple[ContractTerm, ...] = ()
    facility: Facility | None = None
    clause_quotes: tuple[str, ...] = ()


def guard_row(record: ContractRecord) -> ContractGuardRow:
    """The slim projection of a full record (the in-memory store's, and the reference the SQL store is tested against)."""
    ts = record.term_sheet
    return ContractGuardRow(
        id=record.id, kind=record.kind.value, counterparty_id=record.counterparty_id, status=record.status.value,
        doc_hash=record.doc_hash, superseded_by=record.superseded_by, decided_day=record.decided_day,
        decided_seq=record.decided_seq,
        terms=tuple(record.contract.terms) if record.contract else (),
        facility=ts.proposed_facility if ts else None,
        clause_quotes=tuple(c.span.text for c in ts.clauses) if ts else ())


class TrajectoryEngine(Protocol):
    """app.financial -- pure, deterministic."""

    def project(
        self,
        state: FinancialState,
        obligations: list[Obligation],
        actions: list[FundingAction],
        mode: Mode,
        horizon_days: int,
        min_cash_fen: int | None = None,
    ) -> Trajectory:
        """Daily cash recursion over [0, horizon_days]. Conservative mode ignores unconfirmed
        inflows, counts contingent concessions at maximum and ignores non-COMMITTED facilities.
        Posts interest/fees/discounts via app.domain.money only."""
        ...

    def value_concessions(
        self,
        obligations: list[Obligation],
        state: FinancialState,
        funding_rate: Ratio,
        basis_label: str,
        horizon_days: int,
    ) -> list[ConcessionValue]:
        """Forward value of each obligation over the concession horizon. Terms extensions are
        priced as a loan at `funding_rate`; contingent rebates at maximum; immediate discounts
        are not forward concessions (value 0 here, reported separately)."""
        ...


class CovenantEvaluator(Protocol):
    """app.covenants -- pure."""

    def evaluate(self, trajectory: Trajectory, facilities: list[Facility], mandate: Mandate) -> list[Violation]:
        """Every projected month against every facility covenant and mandate ratio limit;
        clean-down on the daily balance of each CREDIT_LINE."""
        ...


class MandatePolicy(Protocol):
    """app.mandate -- canonical serialisation, signing, tiers, predicates."""

    def canonical_bytes(self, mandate: Mandate) -> bytes: ...
    def verify_signature(self, mandate: Mandate, trusted_public_key_hex: str | None = None) -> bool: ...
    def check_validity(
        self, mandate: Mandate, day: int, expected_version: int | None, trusted_public_key_hex: str | None = None
    ) -> list[Violation]: ...
    def tier_for(
        self,
        operation: Operation,
        mandate: Mandate,
        state: FinancialState,
        *,
        accepts_terms_change: bool = False,
        commitment_value_fen: int | None = None,
    ) -> Tier:
        """Both keyword facts can only raise the tier. The executor pins the owner's key."""
        ...
    def check_predicates(
        self,
        trajectory: Trajectory,
        obligations: list[Obligation],
        concession_values: list[ConcessionValue],
        state: FinancialState,
        mandate: Mandate,
        counterparty_id: str | None,
    ) -> list[Violation]:
        """min cash every day (RESERVE_BREACH, curable left None for the verifier), aggregate +
        per-buyer forward concession caps (existing + net new; only FIRM gains net), immediate
        discount cap."""
        ...

    def check_apr(self, annual_rate: Ratio, mandate: Mandate, label: str) -> Violation | None: ...


class FundingRouter(Protocol):
    """app.funding -- grid search over the owner-approved menu."""

    def plan(
        self,
        state: FinancialState,
        obligations: list[Obligation],
        mandate: Mandate,
        basis: str = "COMMITTED",
    ) -> FundingPlan:
        """Cheapest admissible plan. COMMITTED basis may use only COMMITTED facilities and
        respects lead times and clean-down; EXPECTED basis may include PENDING ones."""
        ...

    def compare(self, state: FinancialState, obligations: list[Obligation], mandate: Mandate) -> list[Any]:
        """Spec §7.4 rows (app.funding.ComparisonRow). Also exported from app.funding:
        menu_view(), break_even_discount(), extension_cost_bases()."""
        ...

    def marginal_cost(self, state: FinancialState, mandate: Mandate) -> tuple[Ratio, str]:
        """All-in annual rate of the cheapest committed source able to carry a *permanent*
        need (clean-down excludes the credit line), and its facility id."""
        ...


class OfferCompiler(Protocol):
    """app.compiler -- untrusted. Sees only documents; holds no secrets."""

    def compile_offer(self, docs: list[SourceDocument], counterparty_id: str) -> CompiledOffer: ...
    def compile_term_sheet(self, doc: SourceDocument) -> CompiledTermSheet: ...


class Verifier(Protocol):
    """app.verifier -- reads typed rows only, never free text."""

    def evaluate(self, offer: CompiledOffer, state: FinancialState, mandate: Mandate) -> Verdict: ...
    def counters(self, offer: CompiledOffer, verdict: Verdict, state: FinancialState, mandate: Mandate) -> list[CounterProposal]: ...


class Executor(Protocol):
    """app.operations -- the only writer of commitments and the operations log."""

    def execute(self, op: Operation) -> OperationResult: ...


class OperationRecord(Protocol):
    @property
    def seq(self) -> int: ...
    @property
    def op_id(self) -> str: ...
    @property
    def kind(self) -> str: ...
    @property
    def idempotency_key(self) -> str: ...
    @property
    def payload_json(self) -> str: ...  # canonical JSON of the typed operation
    @property
    def result_json(self) -> str: ...  # canonical JSON of the OperationResult
    @property
    def prev_hash(self) -> str: ...
    @property
    def entry_hash(self) -> str: ...  # sha256(prev_hash + payload_json + result_json)


class LedgerStore(Protocol):
    """app.persistence -- storage only, no business decisions. The executor is the only caller
    of the write methods for commitments and operations."""

    # unit of work: every write inside the block is kept together or none is; a nested block joins the open one
    def transaction(self) -> AbstractContextManager[Any]: ...

    # operations log: append-only, hash-chained
    def append_operation(self, op_id: str, kind: str, idempotency_key: str, payload_json: str, result_json: str) -> OperationRecord: ...
    def find_by_idempotency_key(self, key: str) -> OperationRecord | None: ...
    def operations(self) -> list[OperationRecord]: ...
    def verify_chain(self) -> bool: ...
    def nonce_used(self, nonce: str) -> bool: ...
    def mark_nonce_used(self, nonce: str) -> None: ...

    # commitments
    def put_commitment(self, c: Commitment) -> None: ...
    def get_commitment(self, commitment_id: str) -> Commitment | None: ...
    def commitments(self) -> list[Commitment]: ...

    # state, mandate, menu (owner/fixture writes only)
    def get_state(self) -> FinancialState: ...
    def put_state(self, state: FinancialState, expected_version: int | None = None) -> None:
        """Store a new version of the books. With `expected_version` a compare-and-swap: it raises
        `StateVersionConflict` (a `ConcurrentWriteConflict`), writing nothing, unless the stored state has that version."""
        ...
    def get_mandate(self) -> Mandate: ...
    def put_mandate(self, mandate: Mandate) -> None: ...

    # offers, verdicts, security events, approvals
    def put_offer(self, offer: CompiledOffer) -> None: ...
    def get_offer(self, offer_id: str) -> CompiledOffer | None: ...
    def put_verdict(self, verdict: Verdict) -> None: ...
    def get_verdict(self, verdict_id: str) -> Verdict | None: ...
    def verdicts(self) -> list[Verdict]: ...  # every stored verdict, in first-stored order
    def add_security_event(self, event: SecurityEvent) -> None: ...
    def security_events(self) -> list[SecurityEvent]: ...
    def reset(self, include_telemetry: bool = False) -> None: ...

    # Tier-2 approvals queue (the executor/API enforce owner-only decisions)
    def add_approval(self, op_json: str, reason: str) -> str: ...
    def get_approval(self, approval_id_: str) -> Any: ...
    def approvals(self, status: Any = None) -> list[Any]: ...
    def decide_approval(self, approval_id_: str, approved: bool, by: str, day: int | None = None) -> Any: ...

    # contract records: documents the agent read (brief 03). Only the executor decides one (CONFIRM_DOCUMENT).
    def add_contract_record(self, record: ContractRecord) -> str:
        """Store a PROPOSED record under a new id ("DOC-000001"), which it returns; the record's own id is ignored."""
        ...
    def get_contract_record(self, record_id: str) -> ContractRecord | None: ...
    def contract_records(self) -> list[ContractRecord]: ...  # in upload order
    def contract_guard_rows(self) -> list[ContractGuardRow]:
        """Every record in upload order without its document text (see `ContractGuardRow`): for the outbound guard and for
        reads that need only the status. The full record is `get_contract_record`."""
        ...
    def decide_contract_record(self, record: ContractRecord) -> ContractRecord:
        """Replace a PROPOSED record by its decided version. Compare-and-swap on the status: a record already decided
        raises `DocumentAlreadyDecided`, an unknown one `NotFound`, and a decision that changes anything but the
        decision fields (status, day, log seq, linked facility) raises `ValueError`. Confirming a buyer contract sets
        `superseded_by` on the buyer's earlier confirmed contract, in the same unit of work."""
        ...

    # customer inputs: what the owner told FLOW about a buyer or the firm (map #88, brief H.4). Append-only context, never
    # part of the state, the operations or the hash chain; `reset()` clears it.
    def add_customer_input(self, record: CustomerInputRecord) -> CustomerInputRecord:
        """Append one row and return the stored one (the store assigns `seq` and `recorded_at`). Nothing is updated or deleted."""
        ...
    def customer_inputs(self, counterparty_id: str | None) -> list[CustomerInputRecord]:
        """The history of one buyer's rows, oldest first; `None` is the firm's rows."""
        ...
    def all_customer_inputs(self) -> list[CustomerInputRecord]: ...  # every row, oldest first
    def latest_customer_inputs(self) -> dict[tuple[str | None, str], CustomerInputRecord]:
        """The row in force for each (counterparty id or None for the firm, field): the latest stored wins."""
        ...

    # evidence
    def export_evidence(self) -> str: ...
