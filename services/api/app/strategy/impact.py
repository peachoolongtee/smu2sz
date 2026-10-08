"""Marginal impact: what the router, the trajectory and the alerts say about two sets of books, and the scenarios
that produce the second set (docs/STRATEGY_MVP_BRIEF.md section 3).

Read-only: every state passed to the kernel is a `model_copy`, nothing is stored, nothing is booked. A receipt that
"arrives" is a labelled projection (`ScenarioState.hypothetical`), never a bank receipt.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.alerts import alerts
from app.api.presentation import when_text
from app.books import Books, current_books
from app.domain.models import (
    CashFlow,
    FinancialState,
    FlowKind,
    FundingLot,
    Mandate,
    Mode,
    Receivable,
)
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.financial import lots as funding_lots
from app.financial import project
from app.funding import plan
from app.funding.router import shared_runs
from app.strategy.types import MarginalImpact, ScenarioState

_OPEN = ("OPEN", "FINANCED")


# ---------------------------------------------------------------- scenarios


def _find(state: FinancialState, receivable_id: str) -> Receivable:
    r = next((x for x in state.receivables if x.id == receivable_id), None)
    if r is None:
        raise ValueError(f"receivable {receivable_id} is not on the books")
    if r.status not in _OPEN or r.outstanding_fen <= 0:
        raise ValueError(f"receivable {receivable_id} is {r.status} with {fmt_yuan(r.outstanding_fen)} outstanding: "
                         f"nothing is left to collect")
    return r


def _who(state: FinancialState, r: Receivable) -> str:
    return next((c.name for c in state.counterparties if c.id == r.counterparty_id), r.counterparty_id)


def _received_today(state: FinancialState, r: Receivable) -> FinancialState:
    """The outstanding face credited to cash and the receivable SETTLED (`settled_fen = face_fen`). A FINANCED
    receivable pays the lender first, as the executor's receipt does (ADR-0010): the advance lot is cleared with its
    charges out of the receipt, the facility's drawn balance falls with it and cash gets the rest."""
    state = funding_lots.ensure_lots(state)
    amount = r.outstanding_fen
    cash = state.cash_fen + amount
    facilities, lots = state.facilities, list(state.lots)
    if r.status == "FINANCED":
        lot = next((x for x in state.lots if x.receivable_id == r.id and x.remaining_fen > 0), None)
        if lot is None:
            raise ValueError(f"no advance on record for financed {r.id}")
        f = next(x for x in state.facilities if x.id == lot.facility_id)
        still: FundingLot | None = None
        if lot.settled:
            applied = funding_lots.apply_receipt(f, lot, amount, state.as_of_day, True)
            cash -= applied.applied  # the lender is paid first, from the receipt only
            still = applied.lot
        # an advance that has not landed is cancelled by a receipt that settles the invoice: nothing is charged
        lots = [x for x in lots if x.id != lot.id] + ([still] if still is not None else [])
        drawn = f.drawn_fen - lot.remaining_fen + (still.remaining_fen if still is not None else 0)
        facilities = [x.model_copy(update={"drawn_fen": drawn}) if x.id == f.id else x for x in state.facilities]
    paid = r.model_copy(update={"status": "SETTLED", "settled_fen": r.face_fen, "advance_fen": 0,
                                "advance_facility_id": None})
    receivables = [paid if x.id == r.id else x for x in state.receivables]
    return state.model_copy(update={"cash_fen": cash, "receivables": receivables, "facilities": facilities,
                                    "lots": lots})


def _received_on(state: FinancialState, r: Receivable, on_day: int) -> FinancialState:
    """The receipt moved to `on_day` the way the collections spike moved it: the receivable's terms on the COPY end on
    that day, so the engine posts the RECEIPT there and the invoice stays financeable until then. The books' own
    receivable, the commitments and the contract are untouched. (An `IMMEDIATE_DISCOUNT` at 0 bp dates the receipt
    too, but it marks the invoice settled early and the router then cannot finance it: it prices another source.)"""
    receivables = [x.model_copy(update={"terms_days": on_day - x.issue_day}) if x.id == r.id else x
                   for x in state.receivables]
    return state.model_copy(update={"receivables": receivables})


def scenario_received(books: Books, receivable_id: str, on_day: int, *, label: str | None = None) -> ScenarioState:
    """The receivable's outstanding face received on `on_day` (a labelled projection, not a bank receipt).

    Today: cash is credited and the receivable settled. A later day, up to its due day: the receipt is moved on the
    copy (`_received_on`). `ValueError` for an unknown or settled receivable, a day before today, an overdue
    receivable asked for any day but today, a day after the due day, and a financed receivable asked for any day but
    today (the lender is paid first, and only that case is modelled)."""
    state = books.state
    today = state.as_of_day
    r = _find(state, receivable_id)
    if on_day < today:
        raise ValueError(f"day {on_day} is before today (day {today})")
    if on_day == today:
        scenario = _received_today(state, r)
    elif r.due_day < today:
        raise ValueError(f"{receivable_id} is overdue (due day {r.due_day}): only today can be asked for")
    elif r.status == "FINANCED":
        raise ValueError(f"{receivable_id} is financed: only a receipt today is modelled (the lender is paid first)")
    elif on_day > r.due_day:
        raise ValueError(f"day {on_day} is after {receivable_id}'s due day {r.due_day}: a later receipt is not modelled")
    else:
        scenario = _received_on(state, r, on_day)
    when = when_text(on_day, today, "en")
    return ScenarioState(
        state=scenario, label=label or f"{receivable_id} received {when}",
        assumption=f"assumes the {fmt_yuan(r.outstanding_fen)} from {_who(state, r)} arrives {when}",
        source_state_version=state.state_version, day=today)


def scenario_inflow(books: Books, amount_fen: int, on_day: int, *, outflow_day: int | None = None) -> ScenarioState:
    """One confirmed `CashFlow` of `amount_fen` on `on_day` appended to the state's flows. With `outflow_day` the same
    amount also leaves on that day (the pair that moves money earlier, brief section 5.1)."""
    state = books.state
    today = state.as_of_day
    if amount_fen <= 0:
        raise ValueError("an inflow must be positive")
    if on_day < today or (outflow_day is not None and outflow_day < today):
        raise ValueError(f"a flow cannot be dated before today (day {today})")
    flows = [CashFlow(id=f"SCENARIO-INFLOW-{on_day}", day=on_day, amount_fen=amount_fen, kind=FlowKind.OTHER,
                      label="hypothetical inflow", confirmed=True)]
    label = f"{fmt_yuan(amount_fen)} arrives on day {on_day}"
    assumption = f"assumes {fmt_yuan(amount_fen)} arrives {when_text(on_day, today, 'en')}"
    if outflow_day is not None:
        flows.append(CashFlow(id=f"SCENARIO-OUTFLOW-{outflow_day}", day=outflow_day, amount_fen=-amount_fen,
                              kind=FlowKind.OTHER, label="hypothetical outflow", confirmed=True))
        label += f" and leaves on day {outflow_day}"
        assumption += f" and leaves {when_text(outflow_day, today, 'en')}"
    return ScenarioState(
        state=state.model_copy(update={"flows": [*state.flows, *flows]}), label=label, assumption=assumption,
        source_state_version=state.state_version, day=today)


# ---------------------------------------------------------------- marginal impact


@dataclass(frozen=True)
class _Reading:
    cost_fen: int
    need_fen: int
    needs_owner: bool
    executable_now: bool
    first_breach_day: int | None
    breach_days: int
    lowest_headroom_fen: int
    budget_used_fen: int
    alert_codes: tuple[str, ...]


def _read(side: Books | ScenarioState, mandate: Mandate, store: LedgerStore, day: int) -> _Reading:
    if isinstance(side, Books):
        state, obs = side.state, side.with_([])
    else:  # a scenario's live obligations are those of the stored commitments that still bind to its state
        state = side.state
        obs = current_books(state, store.commitments()).with_([])
    p = plan(state, obs, mandate)
    t = project(state, obs, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    found = alerts(state, mandate, store, day)
    floor = mandate.min_cash_fen
    live = [d for d in t.days if d.day >= state.as_of_day]
    booked = sum(fc.value_fen for fc in state.forward_concessions)
    return _Reading(
        cost_fen=p.total_cost_fen, need_fen=p.need_fen, needs_owner=p.needs_owner_approval,
        executable_now=p.executable_now, first_breach_day=t.first_breach_day,
        breach_days=sum(1 for d in live if d.closing_fen < floor),
        lowest_headroom_fen=min((d.closing_fen - floor for d in live), default=0),
        budget_used_fen=max([d.forward_concession_fen for d in t.days] + [booked]),
        alert_codes=tuple(dict.fromkeys(a.kind.value for a in found)))


def marginal_impact(before: Books | ScenarioState, after: Books | ScenarioState, mandate: Mandate, *,
                    store: LedgerStore, day: int, label: str = "") -> MarginalImpact:
    """What changes between two books: the COMMITTED plan, the CONSERVATIVE trajectory and the alerts of each,
    subtracted (after minus before). `posted_cost_delta_fen` is `FundingPlan.total_cost_fen` after less before: a
    negative figure is a saving, a positive one a cost, kept as it is. The alerts read the state they are given and
    the `store` only for the commitments, expiries and repayments (a scenario's state need not be the store's)."""
    with shared_runs():
        b = _read(before, mandate, store, day)
        a = _read(after, mandate, store, day)
    return MarginalImpact(
        label=label,
        need_delta_fen=a.need_fen - b.need_fen,
        posted_cost_delta_fen=a.cost_fen - b.cost_fen,
        first_breach_before=b.first_breach_day, first_breach_after=a.first_breach_day,
        lowest_headroom_delta_fen=a.lowest_headroom_fen - b.lowest_headroom_fen,
        budget_used_delta_fen=a.budget_used_fen - b.budget_used_fen,
        breach_days_removed=b.breach_days - a.breach_days,
        alerts_removed=[c for c in b.alert_codes if c not in a.alert_codes],
        alerts_added=[c for c in a.alert_codes if c not in b.alert_codes],
        before_needs_owner=b.needs_owner, after_needs_owner=a.needs_owner,
        before_executable_now=b.executable_now, after_executable_now=a.executable_now,
        before_cost_fen=b.cost_fen, after_cost_fen=a.cost_fen,
        before_need_fen=b.need_fen, after_need_fen=a.need_fen)


__all__ = ["marginal_impact", "scenario_inflow", "scenario_received"]
