"""A cash-only fast path over the same postings as `project` (for the funding router's search).

`project_cash` books exactly what `project` books (the shared `trajectory._booked`) and then sums it
without building the display trajectory (no DayPoint/LedgerEvent objects, no month ratios). It
returns the closing cash of every day, the peak debt outstanding and the posted interest, fees and
discounts; each equals what `project` reports for the same arguments, and it raises exactly when
`project` raises. `tests/funding/test_cashpath.py` checks this against the full `project`.

Covenants need the full trajectory: callers that must test them still call `project`.

`CashProjector` is `project_cash` for one fixed set of books and many action lists (the router's search probes
thousands of them): what the actions do not touch (the invoices with the obligations' terms and prices, the
obligations' own postings, the state's lots, the flows, the debt service, the receipts) is booked once and reused;
only the actions are booked per call. Each call returns what `project_cash` returns for the same arguments and
raises the same error (`tests/funding/test_cashpath.py` checks both against the full `project`).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import accumulate

from app.domain.models import (
    FinancialState,
    FundingAction,
    FundingActionKind,
    Mode,
    Obligation,
    ObligationType,
)
from app.financial.lots import ensure_lots
from app.financial.trajectory import (
    _apply_actions,
    _apply_terms_and_prices,
    _Book,
    _bookable,
    _booked,
    _carry_drawn_balances,
    _check_limits,
    _debt_service,
    _forward_concession,
    _immediate_discount,
    _issue_day_of,
    _Rcv,
    _receivables,
    _repay_carried,
)


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


# ---------------------------------------------------------------- many action lists on the same books


@dataclass
class _Base:
    """What `trajectory._build` books for one issue bound before and after the actions and the actions do not
    change: the invoices with the obligations applied, the obligations' and the state's lots' postings, and (summed
    by day) the flows, the debt service and the receipts."""

    rcvs: dict[str, _Rcv]  # never mutated: a call copies the invoices its actions touch
    book: _Book  # the obligations' and the state's lots' postings and balances
    cash: dict[int, int]  # signed cash by day of everything above, receipts included
    receipts: dict[str, tuple[int, int]]  # invoice id -> (due day, residual) of the receipt booked for it
    costs: list[tuple[int, int, int]]  # (day, 0 interest | 1 fee | 2 discount, signed amount) of the same postings
    debt_deltas: dict[int, int]  # the existing debts' scheduled principal by day
    arr: list[int] = field(default_factory=list)  # `cash` as a list over days 0.., grown as longer horizons need it


def _cost_slot(category: str | None, facility_id: str | None) -> int | None:
    if category == "interest" and facility_id:  # as in `project`: facility interest only
        return 0
    if category == "fee":
        return 1
    if category == "discount":
        return 2
    return None


def _copy_rcv(r: _Rcv) -> _Rcv:
    return _Rcv(r.id, r.counterparty_id, r.face, r.issue_day, r.terms, r.confirmed, r.generated, r.contract,
                list(r.applied), list(r.notes), r.early, r.financed, r.advance, r.advance_facility_id)


class CashProjector:
    """`project_cash(state, obligations, actions, mode, horizon_days, min_cash_fen)` for many `actions` on the same
    books. The obligations are read once, when the first call needs them."""

    def __init__(self, state: FinancialState, obligations: Sequence[Obligation], mode: Mode, horizon_days: int,
                 min_cash_fen: int | None = None) -> None:
        self.state, self.mode, self.horizon_days, self.min_cash_fen = state, mode, horizon_days, min_cash_fen
        self.obligations = list(obligations)
        self._bases: dict[int, _Base | None] = {}  # per issue bound; None: not reusable (use `project_cash`)
        self._lots_state: FinancialState | None = None
        self._fixed_bound = 0
        # as `project_cash` reads them: the state as given
        facilities = list({f.id: f for f in state.facilities}.values())
        self._facility_ids = [f.id for f in facilities]
        self._debt0 = sum(d.principal_fen for d in state.debts) + sum(f.drawn_fen for f in facilities)

    def _prepare(self) -> FinancialState:
        if self._lots_state is None:
            if self.horizon_days < 0:
                raise ValueError("horizon_days must not be negative")
            lots_state = ensure_lots(self.state)  # a balance no lot explains is dated today, in memory only
            self._fixed_bound = max([self.horizon_days + lots_state.as_of_day]
                                    + [ob.effective_day or 0 for ob in self.obligations])
            self._lots_state = lots_state
        return self._lots_state

    def _receipt(self, r: _Rcv, today: int) -> tuple[int, int] | None:
        residual = r.face - r.early
        if residual <= 0 or r.due < today:
            return None  # settled early, or overdue before today (no dated receipt to rely on)
        if self.mode == Mode.CONSERVATIVE and not r.confirmed:
            return None
        return r.due, residual

    def _base(self, state: FinancialState, bound: int) -> _Base | None:
        if bound in self._bases:
            return self._bases[bound]
        mode = self.mode
        rcvs = _receivables(state, bound, mode)
        book = _Book()
        obs = [ob for ob in self.obligations if _bookable(ob, mode)]
        _apply_terms_and_prices(obs, rcvs, state.as_of_day)
        for ob in obs:
            if ob.type == ObligationType.IMMEDIATE_DISCOUNT:
                _immediate_discount(ob, state, rcvs, book)
            elif ob.type in (ObligationType.CONTINGENT_REBATE, ObligationType.OPERATIONAL_CONCESSION):
                _forward_concession(ob, book)
        _carry_drawn_balances(state, rcvs, book, {})
        if book.carried:  # `_repay_carried` reads the whole cash path to place these: take the long way round
            self._bases[bound] = None
            return None
        cash: dict[int, int] = defaultdict(int)
        costs: list[tuple[int, int, int]] = []

        def add(day: int, amount: int, category: str | None = None, facility_id: str | None = None) -> None:
            cash[day] += amount
            slot = _cost_slot(category, facility_id)
            if slot is not None:
                costs.append((day, slot, amount))

        for p in book.postings:
            add(p.day, p.amount, p.category, p.facility_id)
        today = state.as_of_day
        for fl in state.flows:
            if fl.day < today:
                continue
            if mode == Mode.CONSERVATIVE and fl.amount_fen > 0 and not fl.confirmed:
                continue  # unconfirmed inflows are ignored
            add(fl.day, fl.amount_fen)
        tail = _Book()
        _debt_service(state, bound, tail)
        for p in tail.postings:
            add(p.day, p.amount, p.category, p.facility_id)
        receipts: dict[str, tuple[int, int]] = {}
        for r in rcvs.values():
            hit = self._receipt(r, today)
            if hit is not None:
                receipts[r.id] = hit
                add(hit[0], hit[1])
        base = _Base(rcvs, book, cash, receipts, costs, tail.debt_deltas)
        self._bases[bound] = base
        return base

    def run(self, actions: list[FundingAction]) -> CashPath:
        state = self._prepare()
        if any(a.kind == FundingActionKind.REPAY for a in actions):
            return project_cash(self.state, self.obligations, actions, self.mode, self.horizon_days, self.min_cash_fen)
        horizon_days = self.horizon_days + state.as_of_day
        bound = max([self._fixed_bound] + [a.day for a in actions] + [a.repay_day or 0 for a in actions]
                    + [_issue_day_of(a.receivable_id) for a in actions])
        while True:
            base = self._base(state, bound)
            if base is None:
                return project_cash(self.state, self.obligations, actions, self.mode, self.horizon_days,
                                    self.min_cash_fen)
            touched = {a.receivable_id for a in actions if a.receivable_id in base.rcvs}
            rcvs = dict(base.rcvs)
            for rid in touched:
                rcvs[rid] = _copy_rcv(base.rcvs[rid])
            ab = _Book()
            _apply_actions(state, actions, self.mode, rcvs, ab)
            book = _Book()
            for src in (base.book, ab):
                for fid, days in src.balance_deltas.items():
                    delta_to = book.balance_deltas[fid]
                    for d, v in days.items():
                        delta_to[d] += v
                for fid, days in src.balance_in.items():
                    in_to = book.balance_in[fid]
                    for d, v in days.items():
                        in_to[d] += v
            _check_limits(state, book)
            book.repayment_days = base.book.repayment_days + ab.repayment_days
            book.funding_days = base.book.funding_days + ab.funding_days
            horizon = max([horizon_days] + [d + 1 for d in book.repayment_days] + book.funding_days)
            if horizon <= bound:
                break
            bound = horizon
        book.postings = ab.postings
        book.unallocated = base.book.unallocated
        _repay_carried(state, book, horizon, self.min_cash_fen if self.min_cash_fen is not None else 0)

        need = horizon + 1
        if len(base.arr) < need:
            base.arr = [base.cash.get(d, 0) for d in range(need + 64)]
        arr = base.arr[:need]  # signed cash of days 0..horizon: the books above, then what this call books
        for rid in touched:  # the receipt of an invoice the actions touch is booked again from the touched copy
            old = base.receipts.get(rid)
            if old is not None and 0 <= old[0] < need:
                arr[old[0]] -= old[1]
            new = self._receipt(rcvs[rid], state.as_of_day)
            if new is not None and 0 <= new[0] < need:
                arr[new[0]] += new[1]
        costs = list(base.costs)
        for p in book.postings:
            if 0 <= p.day < need:
                arr[p.day] += p.amount
            slot = _cost_slot(p.category, p.facility_id)
            if slot is not None:
                costs.append((p.day, slot, p.amount))
        totals = [0, 0, 0]
        for day, slot, amount in costs:
            if 0 <= day < need:
                totals[slot] -= amount
        debt_by_day = [0] * need
        for fid in self._facility_ids:  # one balance per id, as in `project`
            for d, delta in book.balance_deltas.get(fid, {}).items():
                if 0 <= d < need:
                    debt_by_day[d] += delta
        for d, delta in base.debt_deltas.items():  # the existing debts' scheduled principal
            if 0 <= d < need:
                debt_by_day[d] += delta
        arr[0] += self.state.cash_fen
        debt_by_day[0] += self._debt0  # horizon >= 0, so day 0 always exists
        return CashPath(horizon, tuple(accumulate(arr)), max(accumulate(debt_by_day)), totals[0], totals[1],
                        totals[2])
