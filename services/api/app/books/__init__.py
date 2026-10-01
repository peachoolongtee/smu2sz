"""Current books (ADR-0006): the one financial position every module projects from.

`current_books(state, commitments)` = the stored state (the actual position today, as written by the
executor and the clock) + the cash-relevant obligations of live commitments, in acceptance order.
Pure: no I/O, no clock. Modules pass `books.state` and `books.obligations + <what they are testing>`
to the engine; none projects from the raw state alone.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models import (
    Commitment,
    CommitmentStatus,
    Contingency,
    FinancialState,
    Mode,
    Obligation,
    ObligationType,
)
from app.domain.ports import LedgerStore
from app.financial import EngineError, project

LIVE = (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE)


@dataclass(frozen=True, slots=True)
class Lapsed:
    """A live commitment's obligation that no longer binds to the state, and why."""

    commitment_id: str
    obligation: Obligation
    reason: str  # "EARLY_PAYMENT_MISSED" | "RECEIVABLE_SETTLED" | "UNBOUND"


@dataclass(frozen=True, slots=True)
class Books:
    state: FinancialState
    obligations: tuple[Obligation, ...]
    lapsed: tuple[Lapsed, ...] = ()

    @property
    def day(self) -> int:
        return self.state.as_of_day

    def with_(self, extra: Sequence[Obligation]) -> list[Obligation]:
        """The live obligations followed by `extra` (an offer under test, a what-if)."""
        return [*self.obligations, *extra]


def cash_relevant(o: Obligation) -> bool:
    """Obligations of a live commitment that still move cash. Rebates and operational concessions
    without an effective day live in `state.forward_concessions` already (booked at acceptance)."""
    if o.contingency == Contingency.CLAIMED_UNEVIDENCED or o.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
        return False
    if o.type in (ObligationType.CONTINGENT_REBATE, ObligationType.OPERATIONAL_CONCESSION):
        return o.effective_day is not None
    return o.type in (ObligationType.IMMEDIATE_DISCOUNT, ObligationType.TERMS_EXTENSION,
                      ObligationType.PRICE_ADJUSTMENT)


def binds(state: FinancialState, o: Obligation) -> bool:
    try:
        project(state, [o], [], Mode.CONSERVATIVE, 0)
    except EngineError:
        return False
    return True


def _why_unbound(state: FinancialState, o: Obligation) -> str:
    if o.type == ObligationType.IMMEDIATE_DISCOUNT:
        r = next((r for r in state.receivables if r.id == o.base.receivable_id), None)
        if r is not None and (r.status == "SETTLED" or r.outstanding_fen <= 0):
            return "RECEIVABLE_SETTLED"
        if o.effective_day is not None and o.effective_day < state.as_of_day:
            return "EARLY_PAYMENT_MISSED"
    return "UNBOUND"


def current_books(state: FinancialState, commitments: Sequence[Commitment]) -> Books:
    """State + the live obligations that still bind to it. An early-pay obligation whose day has passed
    unpaid, or whose receivable is settled, is reported in `lapsed` and left out of the projection (the
    receivable then falls back to its original due day)."""
    live: list[Obligation] = []
    lapsed: list[Lapsed] = []
    for c in commitments:
        if c.status not in LIVE:
            continue
        for o in c.obligations:
            if not cash_relevant(o):
                continue
            if binds(state, o):
                live.append(o)
            else:
                lapsed.append(Lapsed(c.id, o, _why_unbound(state, o)))
    return Books(state=state, obligations=tuple(live), lapsed=tuple(lapsed))


def books_from_store(store: LedgerStore) -> Books:
    return current_books(store.get_state(), store.commitments())


__all__ = ["LIVE", "Books", "Lapsed", "binds", "books_from_store", "cash_relevant", "current_books"]
