"""Read-side helpers over the hash-chained operations log.

The log is the simulated bank's journal: idempotency, circuit-breaker refusals and the causal history
are derived from it, so both stores give the same answers and nothing lives only in executor memory.
Funding lots and their dates live in the state (ADR-0010, `app.financial.lots`), not here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.domain.models import (
    Operation,
    OperationResult,
    OperationStatus,
)
from app.domain.ports import OperationRecord

OPERATION_ADAPTER: TypeAdapter[Operation] = TypeAdapter(Operation)

# Log entries that are not typed Operations: the owner resetting a counterparty's circuit breaker,
# and the owner revoking a commitment (`Executor.revoke_commitment`).
RESET_CIRCUIT_KIND = "RESET_CIRCUIT"
REVOKE_COMMITMENT_KIND = "REVOKE_COMMITMENT"


@dataclass(frozen=True, slots=True)
class LoggedEntry:
    seq: int
    kind: str
    idempotency_key: str
    op: Any  # an Operation, or None for a non-operation entry (RESET_CIRCUIT)
    payload: dict[str, Any]
    result: OperationResult
    entry_hash: str

    @property
    def day(self) -> int | None:
        """The simulated day the executor ran this entry (older entries: the operation's own day)."""
        if self.result.effective_day is not None:
            return self.result.effective_day
        day = getattr(self.op, "day", None)
        return day if isinstance(day, int) else None


def parse_operation(payload_json: str) -> Any:
    """The typed Operation in a payload, or None when the payload is not one."""
    try:
        return OPERATION_ADAPTER.validate_json(payload_json)
    except ValidationError:
        return None


def parse_entry(record: OperationRecord) -> LoggedEntry:
    payload = json.loads(record.payload_json)
    return LoggedEntry(
        seq=record.seq,
        kind=record.kind,
        idempotency_key=record.idempotency_key,
        op=parse_operation(record.payload_json),
        payload=payload if isinstance(payload, dict) else {},
        result=OperationResult.model_validate_json(record.result_json),
        entry_hash=record.entry_hash,
    )


def read_entries(records: list[OperationRecord]) -> tuple[list[LoggedEntry], list[int]]:
    """Every record that parses, plus the seq of every one that does not (a corrupted row is an
    integrity failure to report, never a crash; F-12)."""
    entries: list[LoggedEntry] = []
    unreadable: list[int] = []
    for r in records:
        try:
            entries.append(parse_entry(r))
        except (ValueError, TypeError):  # JSON and pydantic validation errors are ValueErrors
            unreadable.append(r.seq)
    return entries, unreadable


class LogReader:
    """Parses store records once each (entries are immutable; the cache is keyed by entry hash).

    A row that does not parse is skipped and its seq kept in `unreadable` (for the last read), so
    callers that must fail closed on it (the idempotency check) can."""

    def __init__(self) -> None:
        self._cache: dict[str, LoggedEntry] = {}
        self.unreadable: set[int] = set()

    def entries(self, records: list[OperationRecord]) -> list[LoggedEntry]:
        out = []
        bad: set[int] = set()
        for r in records:
            e = self._cache.get(r.entry_hash)
            if e is None:
                try:
                    e = parse_entry(r)
                except (ValueError, TypeError):
                    bad.add(r.seq)
                    continue
                self._cache[r.entry_hash] = e
            out.append(e)
        self.unreadable = bad
        return out


def executed(entries: list[LoggedEntry]) -> list[LoggedEntry]:
    return [e for e in entries if e.result.status == OperationStatus.EXECUTED and e.op is not None]
