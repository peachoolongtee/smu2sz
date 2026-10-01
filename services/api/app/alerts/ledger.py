"""Read-only views of the store the alerts need: parsed log entries and committed obligations.

Only `app.domain` contracts are used to parse the log (typed `Operation` + `OperationResult`), so
this package does not depend on the executor's internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.books import current_books
from app.domain.models import (
    Commitment,
    FinancialState,
    Obligation,
    Operation,
    OperationResult,
)
from app.domain.ports import LedgerStore

_OP: TypeAdapter[Any] = TypeAdapter(Operation)



@dataclass(frozen=True, slots=True)
class Entry:
    seq: int
    kind: str
    op: Any  # a typed Operation, or None
    result: OperationResult
    entry_hash: str

    @property
    def day(self) -> int | None:
        if self.result.effective_day is not None:
            return self.result.effective_day
        d = getattr(self.op, "day", None)
        return d if isinstance(d, int) else None


def entries(store: LedgerStore) -> list[Entry]:
    out = []
    for r in store.operations():
        try:
            op = _OP.validate_json(r.payload_json)
        except ValidationError:
            op = None
        try:
            res = OperationResult.model_validate_json(r.result_json)
        except ValidationError:  # a corrupted row is an integrity failure, reported by /audit, not a crash (F-12)
            continue
        out.append(Entry(r.seq, r.kind, op, res, r.entry_hash))
    return out


def head(store: LedgerStore) -> str | None:
    ops = store.operations()
    return ops[-1].entry_hash if ops else None


def committed_obligations(state: FinancialState, commitments: list[Commitment]) -> list[Obligation]:
    """Cash-relevant obligations of ACCEPTED/ACTIVE commitments that still bind to the state: the live
    obligations of the current books (`app.books`, ADR-0006)."""
    return list(current_books(state, commitments).obligations)
