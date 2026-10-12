"""Immutable records returned by the stores. Mutating one raises `FrozenInstanceError`."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import FrozenInstanceError, dataclass
from enum import StrEnum


@dataclass(slots=True)
class LedgerEntry:
    """One row of the operations log. Satisfies `app.domain.ports.OperationRecord`.

    Write-once rather than `frozen=True`: the port declares plain (settable) attributes, which a
    frozen dataclass does not match for mypy. Any assignment after construction still raises.
    """

    seq: int
    op_id: str
    kind: str
    idempotency_key: str
    payload_json: str
    result_json: str
    prev_hash: str
    entry_hash: str

    def __setattr__(self, name: str, value: object) -> None:
        try:
            object.__getattribute__(self, name)
        except AttributeError:
            object.__setattr__(self, name, value)
            return
        raise FrozenInstanceError(f"cannot assign to field {name!r}: operations log entries are immutable")

    def __delattr__(self, name: str) -> None:
        raise FrozenInstanceError(f"cannot delete field {name!r}: operations log entries are immutable")

    def __hash__(self) -> int:
        return hash(self.entry_hash)


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """A queued Tier-2 operation. `op_json` is the canonical JSON of the typed operation."""

    id: str
    op_id: str | None
    kind: str | None
    op_json: str
    reason: str
    status: ApprovalStatus
    decided_by: str | None = None
    decided_day: int | None = None  # the clock day the owner decided; None while PENDING and on rows decided before this field


@dataclass(frozen=True, slots=True)
class LlmCallRecord:
    id: int
    backend: str
    model: str
    prompt_version: str
    input_sha256: str
    status: str
    output_json: str | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cache_hit: bool
    trace_id: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class EvaluationRunRecord:
    id: int
    suite: str
    passed: int
    failed: int
    metrics_json: str
    git_sha: str | None
    notes: str


@dataclass(frozen=True, slots=True)
class EvidenceExportRecord:
    id: int
    operations: int
    head_hash: str
    chain_valid: bool
    content_sha256: str
    exported_at: str


@dataclass(frozen=True, slots=True)
class PilotJournalRecord:
    """One entry of the shadow pilot's journal (docs/pilot/JOURNAL_SPEC.md): what the owner did against an answer FLOW gave.
    No money field. `seq` is the append position; `state_version` and `day` stamp the books and the clock at the write."""

    seq: int
    week: int
    sme: str
    answer: str
    flow_said: str
    snapshot_hash: str
    owner_did: str
    choice: str
    recorded_on: str
    state_version: int
    day: int
    recorded_at: str


@dataclass(frozen=True, slots=True)
class DecisionFactRecord:
    """One fact of the durable decision record (ADR-0011): something the stores cannot re-derive later (the day a verdict
    was made, the counter that was sent, the economics the owner was shown). `body_json` is the canonical JSON of a strict
    fact model (ids, integer fen and days, exact rates; no sentence, no buyer text, no model output). `state_version` and
    `day` stamp the books and the clock at the write. A caller leaves `seq` and `recorded_at` at their defaults: the store
    assigns them, and returns the stored row."""

    decision_id: str
    family: str  # DEAL | FUNDING
    fact: str  # EVALUATED | SENT | QUOTED
    fact_key: str  # the canonical id the fact is about
    state_version: int
    day: int
    body_json: str
    recorded_at: str = ""
    seq: int = 0


class InputField(StrEnum):
    """What a customer-input row says (map #88, brief H.4). One enum over one table: a later phase adds no migration. The
    first two are the buyer's; the last two are the firm's (a row with no counterparty)."""

    ANNUAL_SALES_FEN = "annual_sales_fen"
    MARGIN_BP = "margin_bp"
    MARGIN_BASIS = "margin_basis"
    CLASSIFICATION = "classification"
    TYPICAL_DELAY_DAYS = "typical_delay_days"
    AGGREGATE = "aggregate"
    VAT_RATE_BP = "vat_rate_bp"
    COMPANY_GROSS_MARGIN_BP = "company_gross_margin_bp"


FIRM_FIELDS = frozenset({InputField.VAT_RATE_BP, InputField.COMPANY_GROSS_MARGIN_BP})


class InputProvenance(StrEnum):
    """Where a figure came from. The wording a surface may use follows the weakest of these (brief C.3)."""

    ACCOUNTING_HISTORY = "ACCOUNTING_HISTORY"
    INVOICE_HISTORY = "INVOICE_HISTORY"
    OWNER_ENTERED = "OWNER_ENTERED"
    ERP = "ERP"
    DERIVED = "DERIVED"
    ESTIMATED = "ESTIMATED"
    PROJECTED = "PROJECTED"


@dataclass(frozen=True, slots=True)
class CustomerInputRecord:
    """One entry of the customer-inputs table (brief H.4): a fact the owner (or an import) gave about a buyer, or about the
    firm when `counterparty_id` is None. Append-only: a newer row for the same (counterparty, field) supersedes the older one
    and the older one stays. `value_json` is the canonical JSON of the value (a number, a boolean or a short string); the
    field decides which. A caller leaves `seq` and `recorded_at` at their defaults: the store assigns them and returns the
    stored row. Context, not books: nothing here is part of the state, the operations or the hash chain."""

    org_id: str
    counterparty_id: str | None
    field: str  # an InputField value
    value_json: str
    provenance: str  # an InputProvenance value
    source_ref: str
    entered_by: str
    entered_day: int
    state_version: int
    recorded_at: str = ""
    seq: int = 0


def latest_inputs(rows: Iterable[CustomerInputRecord]) -> dict[tuple[str | None, str], CustomerInputRecord]:
    """The row in force for each (counterparty, field): the one stored last (highest `seq`). The one definition of
    "latest wins", shared by both stores."""
    out: dict[tuple[str | None, str], CustomerInputRecord] = {}
    for row in sorted(rows, key=lambda r: r.seq):
        out[(row.counterparty_id, row.field)] = row
    return out
