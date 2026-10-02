"""A cash-only fast path over the same postings as `project` (for the funding router's search).

`project_cash` books exactly what `project` books (the shared `trajectory._booked`) and then sums it
without building the display trajectory (no DayPoint/LedgerEvent objects, no month ratios). It
returns the closing cash of every day, the peak debt outstanding and the posted interest, fees and
discounts; each equals what `project` reports for the same arguments, and it raises exactly when
`project` raises. `tests/funding/test_cashpath.py` checks this against the full `project`.

Covenants need the full trajectory: callers that must test them still call `project`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.domain.models import FinancialState, FundingAction, Mode, Obligation
from app.financial.trajectory import _booked


@dataclass(frozen=True)
class CashPath:
    horizon_days: int
    closings: tuple[int, ...]  # closing cash of day d at index d, days 0..horizon_days
    peak_debt_fen: int  # max over days of DayPoint.debt_outstanding_fen
    interest_posted_fen: int
    fees_posted_fen: int
    discounts_posted_fen: int

    @property
    def cost_fen(self) -> int:
        return self.interest_posted_fen + self.fees_posted_fen + self.discounts_posted_fen


def project_cash(
    state: FinancialState,
    obligations: list[Obligation],
    actions: list[FundingAction],
    mode: Mode,
    horizon_days: int,
    min_cash_fen: int | None = None,
) -> CashPath:
    """Closing cash, peak debt and posted costs of `project(...)` with the same arguments."""
    book, horizon = _booked(state, obligations, actions, mode, horizon_days, min_cash_fen)
    cash_by_day: dict[int, int] = defaultdict(int)
    interest = fees = discounts = 0
    for p in book.postings:
        if 0 <= p.day <= horizon:
            cash_by_day[p.day] += p.amount
            if p.category == "interest" and p.facility_id:  # as in `project`: facility interest only
                interest -= p.amount
            elif p.category == "fee":
                fees -= p.amount
            elif p.category == "discount":
                discounts -= p.amount
    debt_by_day: dict[int, int] = defaultdict(int)
    debt = sum(d.principal_fen for d in state.debts)
    for f in {f.id: f for f in state.facilities}.values():  # one balance per id, as in `project`
        debt += f.drawn_fen
        for d, delta in book.balance_deltas.get(f.id, {}).items():
            if 0 <= d <= horizon:
                debt_by_day[d] += delta
    for d, delta in book.debt_deltas.items():  # the existing debts' scheduled principal
        if 0 <= d <= horizon:
            debt_by_day[d] += delta
    cash = state.cash_fen
    closings = []
    peak = debt + debt_by_day.get(0, 0)  # horizon >= 0, so day 0 always exists
    for d in range(horizon + 1):
        cash += cash_by_day.get(d, 0)
        debt += debt_by_day.get(d, 0)
        closings.append(cash)
        peak = max(peak, debt)
    return CashPath(horizon, tuple(closings), peak, interest, fees, discounts)
