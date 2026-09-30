"""Read-only views of the store the alerts need: parsed log entries and committed obligations.

Only `app.domain` contracts are used to parse the log (typed `Operation` + `OperationResult`), so
this package does not depend on the executor's internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.domain.models import (
    Commitment,
    CommitmentStatus,
    Contingency,
    FinancialState,
    Mode,
    Obligation,
    ObligationType,
    Operation,
    OperationResult,
)
from app.domain.ports import LedgerStore
from app.financial import EngineError, project

_OP: TypeAdapter[Any] = TypeAdapter(Operation)

LIVE = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)


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
        out.append(Entry(r.seq, r.kind, op, OperationResult.model_validate_json(r.result_json), r.entry_hash))
    return out


def head(store: LedgerStore) -> str | None:
    ops = store.operations()
    return ops[-1].entry_hash if ops else None


def _cash_relevant(o: Obligation) -> bool:
    """Obligations of a live commitment that still move cash. Rebates and operational concessions
    without an effective day live in `state.forward_concessions` already (booked at acceptance)."""
    if o.contingency == Contingency.CLAIMED_UNEVIDENCED or o.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
        return False
    if o.type in (ObligationType.CONTINGENT_REBATE, ObligationType.OPERATIONAL_CONCESSION):
        return o.effective_day is not None
    return o.type in (ObligationType.IMMEDIATE_DISCOUNT, ObligationType.TERMS_EXTENSION,
                      ObligationType.PRICE_ADJUSTMENT)


def committed_obligations(state: FinancialState, commitments: list[Commitment]) -> list[Obligation]:
    """Cash-relevant obligations of ACCEPTED/ACTIVE commitments that still bind to the state (an
    early-pay discount on a receivable already settled is history, not a projection)."""
    out: list[Obligation] = []
    for c in commitments:
        if c.status not in LIVE:
            continue
        for o in c.obligations:
            if _cash_relevant(o) and binds(state, o):
                out.append(o)
    return out


def binds(state: FinancialState, o: Obligation) -> bool:
    try:
        project(state, [o], [], Mode.CONSERVATIVE, 0)
    except EngineError:
        return False
    return True
