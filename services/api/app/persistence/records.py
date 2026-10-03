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
