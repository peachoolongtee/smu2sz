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

from typing import Protocol

from app.domain.models import (
    CompiledOffer,
    CompiledTermSheet,
    ConcessionValue,
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
    SourceDocument,
    Tier,
    Trajectory,
    Verdict,
    Commitment,
    SecurityEvent,
    Violation,
)
from app.domain.money import Ratio


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
    seq: int
    op_id: str
    kind: str
    idempotency_key: str
    payload_json: str  # canonical JSON of the typed operation
    result_json: str  # canonical JSON of the OperationResult
    prev_hash: str
    entry_hash: str  # sha256(prev_hash + payload_json + result_json)


class LedgerStore(Protocol):
    """app.persistence -- storage only, no business decisions. The executor is the only caller
    of the write methods for commitments and operations."""

    # operations log: append-only, hash-chained
    def append_operation(self, op_id: str, kind: str, idempotency_key: str, payload_json: str, result_json: str) -> OperationRecord: ...
    def find_by_idempotency_key(self, key: str) -> OperationRecord | None: ...
    def operations(self) -> list[OperationRecord]: ...
    def verify_chain(self) -> bool: ...
    def nonce_used(self, nonce: str) -> bool: ...
    def mark_nonce_used(self, nonce: str) -> None: ...

    # commitments
    def put_commitment(self, c: "Commitment") -> None: ...
    def get_commitment(self, commitment_id: str) -> "Commitment | None": ...
    def commitments(self) -> list["Commitment"]: ...

    # state, mandate, menu (owner/fixture writes only)
    def get_state(self) -> FinancialState: ...
    def put_state(self, state: FinancialState) -> None: ...
    def get_mandate(self) -> Mandate: ...
    def put_mandate(self, mandate: Mandate) -> None: ...

    # offers, verdicts, security events, approvals
    def put_offer(self, offer: CompiledOffer) -> None: ...
    def get_offer(self, offer_id: str) -> CompiledOffer | None: ...
    def put_verdict(self, verdict: Verdict) -> None: ...
    def get_verdict(self, verdict_id: str) -> Verdict | None: ...
    def add_security_event(self, event: "SecurityEvent") -> None: ...
    def security_events(self) -> list["SecurityEvent"]: ...
    def reset(self) -> None: ...
