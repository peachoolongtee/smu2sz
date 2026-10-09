"""Immutable records returned by the stores. Mutating one raises `FrozenInstanceError`."""

from __future__ import annotations

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
