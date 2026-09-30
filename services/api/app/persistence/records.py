"""Immutable records returned by the stores. Mutating one raises `FrozenInstanceError`."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One row of the operations log. Satisfies `app.domain.ports.OperationRecord`."""

    seq: int
    op_id: str
    kind: str
    idempotency_key: str
    payload_json: str
    result_json: str
    prev_hash: str
    entry_hash: str


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
