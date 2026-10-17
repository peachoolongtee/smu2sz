"""The owner's reusable metrics (research/owner-questions BASELINE section 5), read-only.

Each metric is one function of the turn's context (`NlContext`, or a `Reading` already taken of it) that returns a
`Metric`: a typed value in integer fen, days or exact ratios, its display string from the existing formatters, the day
it refers to and the engine function it comes from. Nothing here writes, books, sends or executes, and nothing here is
new financial logic: every figure is read from the books or from an existing engine read (the conservative projection,
the funding router and menu, the covenant ratios, the alerts and their cure, the reconciliation, the what-if sandbox,
the capex evaluation, the mandate and the operations log). The two hypotheticals ("can we clear all our debts?",
"what if a buyer pays late?") run the same projection on a model copy of the state; the store is never touched.

A `Reading` takes the books once per answer: every metric of one answer reads the same state, projection and plan, so
the figures of one sentence always agree with each other and with what Home shows.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cached_property
from typing import Any

from app.alerts import Alert, AlertKind, alerts, covenant_limits, reconcile
from app.alerts.ledger import Entry, entries
from app.api.presentation import first_breach_ahead, party_name, whole
from app.books import Books, current_books
from app.clock import ADVANCE_CLOCK_KIND
from app.config import get_settings
from app.covenants import ratios_for, worst_dscr, worst_leverage
from app.covenants.ratios import leverage_debt_fen
from app.domain.models import (
    DayPoint,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    LedgerEventKind,
    Mandate,
    Mode,
    OperationStatus,
    Receivable,
    Trajectory,
)
from app.domain.money import BP_DENOM, Ratio, bp, fmt_pct, round_half_up
from app.domain.ports import LedgerStore
from app.financial import EngineError, project
from app.financial.debts import debt_payments
from app.funding import NoPermanentSourceError, break_even_discount, compare, marginal_cost, menu_view
from app.funding.models import ComparisonRow, MenuRow
from app.mandate.validity import check_validity

UPCOMING_DAYS = 60  # "coming up": the next two months, as the bank's question means it
RECENT_DAYS = 7  # "this week": the last week of the simulated clock, as Home's "what changed" reads it


def money(fen: int) -> str:
    """¥300,000 for a whole number of yuan, ¥3,113.93 otherwise, −¥105,000 below zero (`presentation.whole`)."""
    return whole(fen)


def ratio_x(x: Fraction) -> str:
    """2.00 for a DSCR or a leverage ratio (two decimals, half-up), as the ratios' own `text` says them."""
    return Ratio.of(x).text


@dataclass(frozen=True)
class Metric:
    id: str
    value: Any
    display: str
    day: int | None = None
    source: str = ""
    detail: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


@dataclass(frozen=True)
class Event:
    """One cash movement of the projection ahead: an outflow (amount < 0) or a receipt, with what it is."""

    day: int
    amount_fen: int
    kind: str  # PAYROLL, SUPPLIER, OPERATING, DEBT_SERVICE, CAPEX, OTHER, RECEIPT, FUNDING
    label: str  # the books' own label (a flow's, a debt's), or the buyer's name for a receipt
    counterparty_id: str | None = None


class Reading:
    """The books as one answer reads them: the stored state and mandate, the current books (ADR-0006), the conservative
    projection Home draws, today's alerts and the plan Home recommends. Every property is computed at most once."""

    def __init__(self, store: LedgerStore, day: int, owner_key_hex: str, reads: Any = None) -> None:
        self.store = store
        self.day = day
        self.owner_key_hex = owner_key_hex
        self.reads = reads

    @classmethod
    def of(cls, ctx: Any) -> Reading:
        if isinstance(ctx, Reading):
            return ctx
        return cls(ctx.store, ctx.day, ctx.owner_key_hex, getattr(ctx, "reads", None))

    # ------------------------------------------------------------ the books

    @cached_property
    def state(self) -> FinancialState:
        return self.store.get_state()

    @cached_property
    def mandate(self) -> Mandate:
        return self.store.get_mandate()

    @cached_property
    def books(self) -> Books:
        return current_books(self.state, self.store.commitments())

    @cached_property
    def today(self) -> int:
        return max(self.day, self.state.as_of_day)

    @property
    def floor(self) -> int:
        return self.mandate.min_cash_fen

    @property
    def horizon(self) -> int:
        return self.mandate.horizon_days

    @cached_property
    def traj(self) -> Trajectory:
        """The conservative projection of today's books, exactly as GET /home projects it."""
        b = self.books
        return project(b.state, b.with_([]), [], Mode.CONSERVATIVE, self.horizon, self.floor)

    @cached_property
    def ahead(self) -> list[DayPoint]:
        return [d for d in self.traj.days if d.day >= self.today] or list(self.traj.days)

    @cached_property
    def found(self) -> list[Alert]:
        try:
            return alerts(self.state, self.mandate, self.store, self.day)
        except EngineError:
            return []

    @cached_property
    def breach_alert(self) -> Alert | None:
        return next((a for a in self.found if a.kind == AlertKind.RESERVE_BREACH_AHEAD), None)

    @cached_property
    def action(self) -> dict[str, Any] | None:
        """Home's "one thing to do now" (`app.api.home.next_action`): the router's cheapest runnable plan for a reserve breach,
        else the alert's own cure, else a repayment the books can afford. The one plan source for every answer."""
        from app.api.home import next_action  # the Home module imports the presentation layer; read lazily

        b = self.books
        try:
            found = next_action(b.state, b.with_([]), self.mandate, self.found, self.store.approvals(), self.today,
                                self.state.state_version, "en", use_router=get_settings().features.debt_desk)
        except EngineError:
            return None
        if found is not None:
            found.pop("plan_series", None)
            found.pop("plan_traj", None)
        return found

    @cached_property
    def entries(self) -> list[Entry]:
        return entries(self.store)

    # ------------------------------------------------------------ the projection's events, in words

    def events(self, start: int, end: int) -> list[Event]:
        """The projection's cash movements dated in [start, end], each said by what it is (never by its id)."""
        flows = {f.id: f for f in self.books.state.flows}
        debts = {d.id: d for d in self.books.state.debts}
        out: list[Event] = []
        for d in self.traj.days:
            if not start <= d.day <= end:
                continue
            for e in d.events:
                if e.kind == LedgerEventKind.FLOW and e.amount_fen < 0:
                    flow = flows.get(e.ref or "")
                    if flow is not None:
                        label = flow.label.split(" (")[0].split(",")[0]  # "Payroll, month 2" -> "Payroll", as Home's drivers say it
                        out.append(Event(d.day, e.amount_fen, flow.kind.value, label, flow.counterparty_id))
                    elif e.ref in debts:
                        out.append(Event(d.day, e.amount_fen, FlowKind.DEBT_SERVICE.value, debt_label(debts[e.ref].label)))
                    else:
                        out.append(Event(d.day, e.amount_fen, FlowKind.OTHER.value, e.label.split(" (")[0].split(",")[0]))
                elif e.kind in (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT) and e.amount_fen > 0:
                    buyer = buyer_of(self.books.state, e.ref)
                    out.append(Event(d.day, e.amount_fen, "RECEIPT", party_name(self.state, buyer), buyer))
        return out


def debt_label(label: str) -> str:
    """"Existing equipment loan (rate 0%: a fixture assumption)" -> "Existing equipment loan"."""
    return label.split(" (")[0].strip()


def buyer_of(state: FinancialState, receivable_id: str | None) -> str | None:
    if not receivable_id:
        return None
    r = next((x for x in state.receivables if x.id == receivable_id), None)
    if r is not None:
        return r.counterparty_id
    if receivable_id.startswith("RI:"):  # a recurring invoice not issued yet: "RI:<buyer>:<issue day>"
        return receivable_id.split(":")[1]
    return None


def unpaid(state: FinancialState) -> list[Receivable]:
    return [r for r in state.receivables if r.status != "SETTLED" and r.face_fen > r.settled_fen]


def R(ctx: Any) -> Reading:
    return Reading.of(ctx)


# ================================================================ liquidity


def cash_today(ctx: Any) -> Metric:
    r = R(ctx)
    return Metric("cash_today", r.state.cash_fen, money(r.state.cash_fen), r.today, "FinancialState.cash_fen")


def reserve(ctx: Any) -> Metric:
    r = R(ctx)
    return Metric("reserve", r.floor, money(r.floor), None, "Mandate.min_cash_fen")


def headroom_today(ctx: Any) -> Metric:
    r = R(ctx)
    h = r.state.cash_fen - r.floor
    return Metric("headroom_today", h, money(h), r.today, "cash_fen - min_cash_fen")


def first_breach(ctx: Any) -> Metric:
    """The first day from today on whose closing cash is below the reserve (Home's `first_breach_ahead`)."""
    r = R(ctx)
    hit = first_breach_ahead(r.traj, r.today, r.floor)
    if hit is None:
        return Metric("first_breach", None, "none", None, "trajectory.first_breach_day")
    day, closing = hit
    return Metric("first_breach", day, f"day {day}", day, "trajectory.first_breach_day",
                  {"closing_fen": closing, "closing": money(closing), "short_fen": r.floor - closing,
                   "short": money(r.floor - closing), "today": day == r.today})


def lowest_point(ctx: Any) -> Metric:
    """The lowest closing cash ahead (Home's `_lowest_ahead`: the closed days before today are not ahead)."""
    r = R(ctx)
    low = min(r.ahead, key=lambda d: (d.closing_fen, d.day))
    return Metric("lowest_point", low.closing_fen, money(low.closing_fen), low.day, "trajectory.min_cash_fen")


def funding_need(ctx: Any) -> Metric:
    """How far the lowest point ahead is below the reserve (Home's `lowest_headroom_fen`, negated; the router's `need_fen`)."""
    r = R(ctx)
    low = lowest_point(r)
    need = max(0, r.floor - low.value)
    return Metric("funding_need", need, money(need), low.day, "home.cash.lowest_headroom_fen",
                  {"lowest_headroom_fen": low.value - r.floor})


def first_negative_cash_day(ctx: Any) -> Metric:
    r = R(ctx)
    d = next((x for x in r.ahead if x.closing_fen < 0), None)
    if d is None:
        return Metric("first_negative_cash_day", None, "none", None, "trajectory.days")
    return Metric("first_negative_cash_day", d.day, f"day {d.day}", d.day, "trajectory.days",
                  {"closing_fen": d.closing_fen, "closing": money(d.closing_fen)})


def runway_days(ctx: Any) -> Metric:
    r = R(ctx)
    fb, neg = first_breach(r), first_negative_cash_day(r)
    to_reserve = fb.value - r.today if fb.value is not None else None
    to_zero = neg.value - r.today if neg.value is not None else None
    return Metric("runway_days", to_reserve, "none" if to_reserve is None else f"{to_reserve} days", fb.value,
                  "trajectory.first_breach_day, trajectory.days", {"to_zero_days": to_zero, "zero_day": neg.value})


def cash_on(ctx: Any, day: int) -> Metric:
    r = R(ctx)
    d = next((x for x in r.traj.days if x.day == day), None)
    if d is None:
        return Metric("cash_on", None, "none", day, "trajectory.days")
    return Metric("cash_on", d.closing_fen, money(d.closing_fen), day, "trajectory.days[day].closing_fen")


def gap_windows(ctx: Any) -> Metric:
    """The runs of days below the reserve ahead (`app.nl.funding.gaps`, on current books)."""
    from app.nl.funding import gaps

    r = R(ctx)
    found = gaps(r.state, r.floor, r.horizon, r.books.obligations, from_day=r.today)
    rows = [{"start": g.start, "end": g.end, "low_fen": g.low_fen, "low_day": g.low_day, "shortfall_fen": g.shortfall_fen}
            for g in found]
    text = "; ".join(f"days {g.start}–{g.end}" for g in found) or "none"
    return Metric("gap_windows", rows, text, found[0].start if found else None, "nl.funding.gaps")


def upcoming_outflows(ctx: Any, window: int = UPCOMING_DAYS) -> Metric:
    r = R(ctx)
    out = [e for e in r.events(r.today, r.today + window - 1) if e.amount_fen < 0]  # [today, today + window), as debt_payments
    total = -sum(e.amount_fen for e in out)
    return Metric("upcoming_outflows", out, money(total), r.today, "state.flows + debt_payments (trajectory events)",
                  {"total_fen": total, "window_days": window})


def upcoming_inflows(ctx: Any, window: int | None = None) -> Metric:
    r = R(ctx)
    end = r.today + (window if window is not None else r.horizon)
    ins = [e for e in r.events(r.today, end) if e.amount_fen > 0]
    total = sum(e.amount_fen for e in ins)
    return Metric("upcoming_inflows", ins, money(total), r.today, "receivables + recurring invoices (trajectory events)",
                  {"total_fen": total})


def cash_drivers(ctx: Any) -> Metric:
    """What drives the risk, as Home's `_drivers` picks it: the two largest outflows between today and the first unsafe day
    (to the lowest point when cash is already below the reserve), and the first receipt after the first unsafe day."""
    r = R(ctx)
    fb = first_breach(r)
    if fb.value is None:
        return Metric("cash_drivers", {"outflows": [], "receipt": None}, "none", None, "home._drivers")
    low = lowest_point(r)
    last = max(fb.value, low.day or fb.value) if fb.value <= r.today else fb.value
    outs = sorted((e for e in r.events(r.today, last) if e.amount_fen < 0 and e.kind != FlowKind.DEBT_SERVICE.value),
                  key=lambda e: (e.amount_fen, e.day))[:2] or sorted(
        (e for e in r.events(r.today, last) if e.amount_fen < 0), key=lambda e: (e.amount_fen, e.day))[:2]
    receipt = next((e for e in r.events(fb.value + 1, r.today + r.horizon) if e.amount_fen > 0), None)
    return Metric("cash_drivers", {"outflows": outs, "receipt": receipt}, f"{len(outs)} outflows", fb.value, "home._drivers")


def in_transit(ctx: Any) -> Metric:
    from app.financial.lots import ensure_lots

    r = R(ctx)
    lots = [x for x in ensure_lots(r.state).lots if not x.settled]
    total = sum(x.remaining_fen for x in lots)
    rows = [{"facility_id": x.facility_id, "amount_fen": x.remaining_fen, "arrival_day": x.arrival_day,
             "kind": facility_kind(r.state, x.facility_id)} for x in lots]
    return Metric("in_transit", rows, money(total), None, "state.lots (unsettled)", {"total_fen": total})


# ================================================================ debt


def facility_kind(state: FinancialState, facility_id: str | None) -> str | None:
    f = next((x for x in state.facilities if x.id == facility_id), None)
    return f.kind.value if f is not None else None


def total_debt(ctx: Any) -> Metric:
    """DebtPosition principal plus every drawn balance that counts in leverage (`covenants.ratios.leverage_debt_fen`)."""
    r = R(ctx)
    total = leverage_debt_fen(r.state)
    return Metric("total_debt", total, money(total), r.today, "covenants.ratios.leverage_debt_fen")


def debt_positions(ctx: Any) -> Metric:
    """Each debt by loan and facility: term loans (whose lender the books may not record) and drawn facility balances."""
    r = R(ctx)
    rows: list[dict[str, Any]] = []
    for d in r.state.debts:
        lender = None
        if d.facility_id is not None:
            f = next((x for x in r.state.facilities if x.id == d.facility_id), None)
            lender = party_name(r.state, f.lender_id) if f is not None and f.lender_id else None
        nxt = debt_payments(d, r.today, r.today + r.horizon + 1)
        rows.append({"kind": "LOAN", "label": debt_label(d.label), "principal_fen": d.principal_fen,
                     "monthly_fen": d.monthly_debt_service_fen, "rate_bp": d.rate_bp, "lender": lender,
                     "next_day": nxt[0].day if nxt else None, "next_fen": (nxt[0].principal + nxt[0].interest) if nxt else None,
                     "repayable_on_demand": False})
    for f in r.state.facilities:
        if f.drawn_fen > 0 and f.counts_in_leverage:
            rows.append({"kind": "FACILITY", "facility_kind": f.kind.value, "label": f.name, "principal_fen": f.drawn_fen,
                         "lender": party_name(r.state, f.lender_id) if f.lender_id else None, "rate_bp": f.rate_bp,
                         # a credit line is repaid on demand (REPAY_FACILITY); an invoice advance is repaid by the buyer's receipt
                         "repayable_on_demand": f.kind == FacilityKind.CREDIT_LINE})
    total = sum(x["principal_fen"] for x in rows)
    return Metric("debt_positions", rows, money(total), r.today, "state.debts + facilities drawn")


def debt_service_month(ctx: Any, month: int = 1) -> Metric:
    r = R(ctx)
    m = next((x for x in r.traj.months if x.month == month), None)
    if m is None:
        return Metric("debt_service_month", None, "none", None, "trajectory.months")
    return Metric("debt_service_month", m.debt_service_fen, money(m.debt_service_fen), None,
                  "trajectory.months[m].debt_service_fen", {"month": month})


def next_debt_payment(ctx: Any) -> Metric:
    r = R(ctx)
    pays = [(p, d) for d in r.state.debts for p in debt_payments(d, r.today, r.today + r.horizon + 1)[:1]]
    if not pays:
        return Metric("next_debt_payment", None, "none", None, "financial.debts.debt_payments")
    p, d = min(pays, key=lambda x: (x[0].day, x[1].id))
    amount = p.principal + p.interest
    return Metric("next_debt_payment", amount, money(amount), p.day, "financial.debts.debt_payments",
                  {"label": debt_label(d.label), "interest_fen": p.interest, "principal_fen": p.principal})


def drawn_by_facility(ctx: Any) -> Metric:
    r = R(ctx)
    rows: list[dict[str, Any]] = [{"facility_kind": f.kind.value, "name": f.name, "drawn_fen": f.drawn_fen} for f in r.state.facilities
            if f.status == FacilityStatus.COMMITTED and f.limit_fen > 0]
    total = sum(x["drawn_fen"] for x in rows)
    return Metric("drawn_by_facility", rows, money(total), r.today, "facility.drawn_fen")


def _menu(r: Reading) -> list[MenuRow]:
    return menu_view(r.state, r.mandate)


def undrawn_committed(ctx: Any) -> Metric:
    """What can still be borrowed now: the committed, owner-approved debt facilities with room (`funding.menu_view`), and what is
    on the menu but not applied for (it counts as zero until committed). A buyer's early payment is a discount, not borrowing."""
    r = R(ctx)
    rows = _menu(r)
    usable = [x for x in rows if x.committed and x.owner_approved and x.is_debt and x.available_fen > 0]
    expected = [x for x in rows if x.expected_only and x.is_debt]
    out: list[dict[str, Any]] = [{"facility_id": x.facility_id, "facility_kind": x.kind.value, "name": x.name, "available_fen": x.available_fen,
            "all_in": x.all_in_display, "days": x.time_to_cash_days} for x in usable]
    full: list[dict[str, Any]] = [{"facility_kind": x.kind.value, "name": x.name} for x in rows
            if x.committed and x.owner_approved and x.is_debt and x.limit_fen > 0 and x.available_fen == 0]
    later: list[dict[str, Any]] = [{"facility_kind": x.kind.value, "name": x.name, "limit_fen": x.limit_fen, "days": x.time_to_cash_days,
              "status": x.status.value} for x in expected]
    total = sum(x["available_fen"] for x in out)
    return Metric("undrawn_committed", out, money(total), r.today, "funding.menu_view", {"total_fen": total, "not_applied": later, "fully_drawn": full})


def projected_interest_fees(ctx: Any) -> Metric:
    r = R(ctx)
    t = r.traj
    return Metric("projected_interest_fees", t.interest_posted_fen + t.fees_posted_fen,
                  money(t.interest_posted_fen + t.fees_posted_fen), None, "trajectory.interest_posted_fen + fees_posted_fen",
                  {"interest_fen": t.interest_posted_fen, "fees_fen": t.fees_posted_fen})


def marginal_cost_of_funds(ctx: Any) -> Metric:
    r = R(ctx)
    try:
        rate, fid = marginal_cost(r.state, r.mandate)
    except NoPermanentSourceError:
        return Metric("marginal_cost_of_funds", None, "none", None, "funding.rates.marginal_cost")
    return Metric("marginal_cost_of_funds", rate.value, fmt_pct(rate.value), None, "funding.rates.marginal_cost",
                  {"facility_kind": facility_kind(r.state, fid)})


def fastest_and_cheapest_source(ctx: Any) -> Metric:
    r = R(ctx)
    usable = [x for x in _menu(r) if x.committed and x.owner_approved and x.available_fen > 0 and x.is_debt]
    if not usable:
        return Metric("fastest_and_cheapest_source", None, "none", None, "funding.menu_view")
    best = min(usable, key=lambda x: (x.all_in_rate.value, x.time_to_cash_days))
    fastest = min(usable, key=lambda x: (x.time_to_cash_days, x.all_in_rate.value))
    return Metric("fastest_and_cheapest_source", best.kind.value, best.all_in_display, None, "funding.menu_view",
                  {"cheapest": best.name, "cheapest_days": best.time_to_cash_days, "fastest": fastest.name,
                   "fastest_days": fastest.time_to_cash_days, "fastest_kind": fastest.kind.value})


# ================================================================ funding


def standing_plan(ctx: Any) -> Metric:
    """The plan Home recommends for the reserve breach (`app.api.home.next_action`): its legs, total cost, whether it needs the
    owner, and whether committed funding restores the reserve at all. None when nothing needs funding."""
    r = R(ctx)
    a = r.action
    if a is None or a.get("kind") != AlertKind.RESERVE_BREACH_AHEAD.value:
        return Metric("standing_plan", None, "none", None, "home.next_action")
    legs = [{"operation_kind": leg["operation_kind"], "facility_kind": facility_kind(r.state, leg["facility_id"]),
             "facility": leg["facility_name"], "receivable_id": leg["receivable_id"],
             "buyer_id": buyer_of(r.state, leg["receivable_id"]), "amount_fen": leg["amount_fen"] or 0,
             "cost": leg["cost_display"], "lands_day": leg["lands_day"]} for leg in a["legs"]]
    restores = not (r.breach_alert is not None and r.breach_alert.inputs.get("cure_restores_reserve") == "false")
    cost = a.get("cost_total_display")
    return Metric("standing_plan", legs, cost or "unstated", r.today, "home.next_action / funding.router.plan",
                  {"cost": cost, "needs_owner": bool(a.get("needs_owner")), "source": a.get("plan_source"),
                   "receive_fen": a.get("receive_fen") or 0, "restores_reserve": restores,
                   "cost_unstated": bool(a.get("cost_unstated")), "lands_day": a.get("lands_day")})


def alternatives_priced(ctx: Any) -> Metric:
    r = R(ctx)
    try:
        rows: list[ComparisonRow] = compare(r.books.state, r.books.with_([]), r.mandate)
    except EngineError:
        rows = []
    out = [{"key": x.key, "label": x.label, "cost_fen": x.cost_fen, "cost": x.cost_display, "result": x.result.value,
            "reasons": [str(c) for c in x.reasons]} for x in rows]
    return Metric("alternatives_priced", out, f"{len(out)} rows", None, "funding.router.compare")


def break_even(ctx: Any) -> Metric:
    r = R(ctx)
    try:
        d, floor_bp = break_even_discount(r.state, r.mandate)
    except NoPermanentSourceError:
        return Metric("break_even_discount", None, "none", None, "funding.rates.break_even_discount")
    return Metric("break_even_discount", d.value, fmt_pct(d.value), None, "funding.rates.break_even_discount",
                  {"bp_floor": floor_bp})


def invoice_financing_capacity(ctx: Any, receivable_id: str | None = None) -> Metric:
    """The advance an open invoice can raise: the committed invoice-financing facility's advance rate on what is still
    outstanding and not yet advanced, capped by the facility's room."""
    r = R(ctx)
    fac = next((f for f in r.state.facilities if f.kind == FacilityKind.INVOICE_FINANCING
                and f.status == FacilityStatus.COMMITTED and f.owner_approved), None)
    rcv = [x for x in unpaid(r.state) if x.status == "OPEN" and (receivable_id is None or x.id == receivable_id)]
    if fac is None or not rcv or fac.advance_rate_bp is None:
        return Metric("invoice_financing_capacity", 0, money(0), None, "facility.advance_rate_bp × outstanding")
    inv = min(rcv, key=lambda x: (x.due_day, x.id))
    room = max(0, fac.limit_fen - fac.drawn_fen)
    cap = min(room, round_half_up(Fraction(inv.outstanding_fen - inv.advance_fen) * bp(fac.advance_rate_bp)))
    return Metric("invoice_financing_capacity", cap, money(cap), None, "facility.advance_rate_bp × outstanding, capped by the limit",
                  {"advance_rate": fmt_pct(bp(fac.advance_rate_bp), 0), "invoice_fen": inv.outstanding_fen,
                   "buyer_id": inv.counterparty_id})


# ================================================================ customers


def receivables_total(ctx: Any) -> Metric:
    r = R(ctx)
    rows = unpaid(r.state)
    total = sum(x.outstanding_fen for x in rows)
    late = [x for x in rows if x.due_day < r.today]
    return Metric("receivables_total", total, money(total), r.today, "GET /receivables summary",
                  {"count": len(rows), "overdue_count": len(late), "overdue_fen": sum(x.outstanding_fen for x in late)})


def receivables_by_customer(ctx: Any) -> Metric:
    r = R(ctx)
    rows = unpaid(r.state)
    total = sum(x.outstanding_fen for x in rows)
    out: list[dict[str, Any]] = []
    for c in r.state.counterparties:
        if c.role != "BUYER":
            continue
        mine = [x for x in rows if x.counterparty_id == c.id]
        owed = sum(x.outstanding_fen for x in mine)
        nxt = min(mine, key=lambda x: (x.due_day, x.id)) if mine else None
        out.append({"buyer_id": c.id, "name": c.name, "owed_fen": owed, "invoices": len(mine),
                    "share": Fraction(owed, total) if total else Fraction(0),
                    "overdue_fen": sum(x.outstanding_fen for x in mine if x.due_day < r.today),
                    "next_due_day": nxt.due_day if nxt else None})
    out.sort(key=lambda x: (-x["owed_fen"], x["name"]))
    return Metric("receivables_by_customer", out, money(total), r.today, "worklist customers (state.receivables)")


def overdue(ctx: Any) -> Metric:
    """The unpaid invoices past their due day (`alerts.reconcile`'s outstanding rows, marked past due by the clock)."""
    r = R(ctx)
    rep = reconcile(r.store, r.day)
    rows: list[dict[str, Any]] = [{"buyer_id": o.counterparty_id, "face_fen": o.face_fen, "due_day": o.due_day,
                                   "days_late": r.today - o.due_day}
            for o in rep.outstanding if o.past_due]
    rows.sort(key=lambda x: (-x["face_fen"], -x["days_late"]))
    total = sum(x["face_fen"] for x in rows)
    return Metric("overdue", rows, money(total), r.today, "alerts.reconcile outstanding.past_due",
                  {"chain_valid": rep.chain_valid})


def next_receipt(ctx: Any) -> Metric:
    r = R(ctx)
    ahead = [x for x in unpaid(r.state) if x.due_day >= r.today]
    if not ahead:
        return Metric("next_receipt", None, "none", None, "receivables.summary.next_expected")
    x = min(ahead, key=lambda v: (v.due_day, v.id))
    return Metric("next_receipt", x.outstanding_fen, money(x.outstanding_fen), x.due_day, "receivables.summary.next_expected",
                  {"buyer_id": x.counterparty_id})


def recurring_billing(ctx: Any) -> Metric:
    r = R(ctx)
    rows = [{"buyer_id": x.counterparty_id, "face_fen": x.face_fen, "every_days": x.every_days,
             "next_issue_day": x.next_issue_day, "terms_days": x.terms_days} for x in r.state.recurring_invoices]
    return Metric("recurring_billing", rows, f"{len(rows)} recurring invoices", None, "state.recurring_invoices")


def terms_by_customer(ctx: Any) -> Metric:
    r = R(ctx)
    confirmed = {c.counterparty_id for c in r.store.contract_records()
                 if str(getattr(c.status, "value", c.status)) == "CONFIRMED" and getattr(c, "counterparty_id", None)}
    rows: dict[str, dict[str, Any]] = {}
    for ri in r.state.recurring_invoices:
        rows[ri.counterparty_id] = {"buyer_id": ri.counterparty_id, "terms_days": ri.terms_days}
    for rc in unpaid(r.state):
        rows.setdefault(rc.counterparty_id, {"buyer_id": rc.counterparty_id, "terms_days": rc.terms_days})
    for v in rows.values():
        v["contract_confirmed"] = v["buyer_id"] in confirmed
    return Metric("terms_by_customer", list(rows.values()), f"{len(rows)} buyers", None,
                  "state.recurring_invoices + receivables; contract records")


def late_payment_impact(ctx: Any, buyer_id: str, days_late: int) -> Metric:
    """One projection of today's books with the buyer's next unpaid invoice due `days_late` days later, on a model copy of the
    state (never stored), with the router's plan for that copy. Compared with today's lowest point and funding need."""
    from app.funding import plan as router_plan

    r = R(ctx)
    mine = [x for x in unpaid(r.state) if x.counterparty_id == buyer_id]
    # an invoice already past due is no longer counted by the conservative forecast: "late" is about the next one still to come
    coming = [x for x in mine if x.due_day >= r.today]
    already = [x for x in mine if x.due_day < r.today]
    if not coming:
        return Metric("late_payment_impact", None, "none", None, "financial.project on a model copy",
                      {"already_late_fen": sum(x.outstanding_fen for x in already)})
    inv = min(coming, key=lambda x: (x.due_day, x.id))
    moved = [x.model_copy(update={"terms_days": x.terms_days + days_late}) if x.id == inv.id else x for x in r.state.receivables]
    copy = r.state.model_copy(update={"receivables": moved})
    b = current_books(copy, r.store.commitments())
    t = project(b.state, b.with_([]), [], Mode.CONSERVATIVE, r.horizon, r.floor)
    ahead = [d for d in t.days if d.day >= r.today] or list(t.days)
    low = min(ahead, key=lambda d: (d.closing_fen, d.day))
    below = [d.day for d in ahead if d.closing_fen < r.floor]
    need = max(0, r.floor - low.closing_fen)
    cost: str | None = None
    plan_ok = False
    if need:
        try:
            p = router_plan(b.state, b.with_([]), r.mandate)
            plan_ok = bool(p.actions) and p.admissible
            cost = money(p.total_cost_fen) if plan_ok else None
        except (EngineError, NoPermanentSourceError, ValueError):
            plan_ok = False
    base_low = lowest_point(r)
    base_below = [d.day for d in r.ahead if d.closing_fen < r.floor]
    return Metric("late_payment_impact", low.closing_fen, money(low.closing_fen), low.day, "financial.project on a model copy",
                  {"invoice_fen": inv.outstanding_fen, "due_day": inv.due_day, "new_due_day": inv.due_day + days_late,
                   "need_fen": need, "last_below_day": below[-1] if below else None, "first_below_day": below[0] if below else None,
                   "plan_cost": cost, "plan_ok": plan_ok, "base_low_fen": base_low.value, "base_low_day": base_low.day,
                   "base_need_fen": funding_need(r).value, "base_last_below_day": base_below[-1] if base_below else None,
                   "already_late_fen": sum(x.outstanding_fen for x in already)})


# ================================================================ covenants


def covenant_ratios(ctx: Any) -> Metric:
    """The worst projected DSCR and leverage against the strictest limit (mandate or a facility covenant), as SHOW_RATIOS reads them."""
    r = R(ctx)
    dscr_limits, lev_limits = covenant_limits(r.books.state, r.mandate)
    dscr_limit = max(x[0] for x in dscr_limits)
    lev_limit = min(x[0] for x in lev_limits)
    out: dict[str, Any] = {"dscr_limit": dscr_limit, "lev_limit": lev_limit, "dscr": None, "lev": None}
    if (wd := worst_dscr(r.traj.months)) is not None and (d := ratios_for(wd)[0]) is not None:
        out.update(dscr=d.value, dscr_month=wd.month, dscr_head=d.value - dscr_limit)
    if (wl := worst_leverage(r.traj.months)) is not None and (lv := ratios_for(wl)[1]) is not None:
        out.update(lev=lv.value, lev_month=wl.month, lev_head=lev_limit - lv.value)
    inside = (out["dscr"] is None or out["dscr_head"] >= 0) and (out["lev"] is None or out["lev_head"] >= 0)
    cd = [a for a in r.found if a.kind == AlertKind.CLEAN_DOWN_AT_RISK]
    out.update(inside=inside, clean_down_alert=bool(cd))
    disp = f"DSCR {ratio_x(out['dscr'])}×" if out["dscr"] is not None else "no ratio"
    return Metric("covenant_ratios", inside, disp, None, "covenants.ratios worst_dscr / worst_leverage", out)


def covenant_breakpoints(ctx: Any) -> Metric:
    """Where the covenants break: monthly debt service above EBITDA / the DSCR minimum, total debt above the leverage maximum
    × 12 × EBITDA, against the highest of each in the projection."""
    r = R(ctx)
    c = covenant_ratios(r).detail
    ebitda = r.state.monthly_ebitda_fen
    ds_max = round_half_up(Fraction(ebitda) / c["dscr_limit"]) if c["dscr_limit"] else None
    debt_max = round_half_up(c["lev_limit"] * 12 * ebitda)
    months = r.traj.months
    ds_now = max((m.debt_service_fen for m in months), default=0)
    debt_now = max((m.total_debt_fen for m in months), default=0)
    return Metric("covenant_breakpoints", {"debt_service_max_fen": ds_max, "debt_max_fen": debt_max}, money(ds_max or 0), None,
                  "EBITDA / min DSCR, max leverage × 12 × EBITDA",
                  {"debt_service_now_fen": ds_now, "debt_now_fen": debt_now, "dscr_limit": c["dscr_limit"],
                   "lev_limit": c["lev_limit"]})


def ebitda_month(ctx: Any) -> Metric:
    r = R(ctx)
    return Metric("ebitda_month", r.state.monthly_ebitda_fen, money(r.state.monthly_ebitda_fen), None,
                  "FinancialState.monthly_ebitda_fen")


# ================================================================ mandate, activity, what waits


def mandate_limits_and_validity(ctx: Any) -> Metric:
    r = R(ctx)
    m = r.mandate
    problems = check_validity(m, r.today, None, r.owner_key_hex)
    out = {"reserve_fen": m.min_cash_fen, "max_apr": fmt_pct(Fraction(m.max_apr_bp, BP_DENOM)),
           "tier2_fen": m.tier2_single_commitment_fen, "max_discount": fmt_pct(Fraction(m.max_immediate_discount_bp or 0, BP_DENOM)),
           "concession_cap_fen": m.max_aggregate_forward_concession_fen, "min_dscr": ratio_x(bp(m.min_dscr_bp)),
           "max_leverage": ratio_x(bp(m.max_leverage_bp)), "expires_day": m.expires_day, "revoked": m.revoked,
           "allow_new_borrowing": m.allow_new_borrowing, "valid": not problems,
           "problems": [str(p.code) for p in problems]}
    return Metric("mandate_limits_and_validity", not problems, "valid" if not problems else "not valid", m.expires_day,
                  "GET /mandate, mandate.validity.check_validity", out)


_MONEY_FIELDS = ("amount_fen", "advance_fen", "face_fen", "net_fen")


def _op_amount(e: Entry) -> int:
    op = e.op
    for name in _MONEY_FIELDS:
        v = getattr(op, name, None)
        if isinstance(v, int):
            return v
    return 0


def activity_since(ctx: Any, since_day: int | None = None) -> Metric:
    """What the log holds since `since_day` (default: the last week): operations that ran, were refused or wait for the owner,
    the money they moved, the security events, and whether the hash chain verifies."""
    r = R(ctx)
    start = r.today - RECENT_DAYS if since_day is None else since_day
    rows = [e for e in r.entries if (e.day if e.day is not None else r.today) >= start]
    ran = [e for e in rows if e.result.status == OperationStatus.EXECUTED]
    refused = [e for e in rows if e.result.status == OperationStatus.REFUSED]
    queued = [e for e in rows if e.result.status == OperationStatus.PENDING_APPROVAL]
    sec = [s for s in r.store.security_events() if s.day >= start]
    moved = sum(abs(_op_amount(e)) for e in ran if e.kind != ADVANCE_CLOCK_KIND)
    return Metric("activity_since", len(ran), f"{len(ran)} operations", start, "store.operations, security_events, verify_chain",
                  {"ran": [(e.kind, _op_amount(e), e.op) for e in ran], "refused": len(refused), "queued": len(queued),
                   "security_events": len(sec), "moved_fen": moved, "chain_valid": r.store.verify_chain()})


def approvals_pending(ctx: Any) -> Metric:
    r = R(ctx)
    rows = [a for a in r.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"]
    out: list[dict[str, Any]] = []
    for a in rows:
        try:
            op = json.loads(a.op_json)
        except ValueError:
            op = {}
        out.append({"kind": a.kind or op.get("kind"), "amount_fen": op.get("amount_fen", op.get("advance_fen")),
                    "facility_kind": facility_kind(r.state, op.get("facility_id"))})
    return Metric("approvals_pending", out, str(len(out)), None, "store.approvals(PENDING)")


def what_waits(ctx: Any) -> Metric:
    """What waits for the owner: the funding plan for a reserve breach, the approvals queue and the Deals queue's Needs-you rows
    (the Business pages' own read, when the turn carries it)."""
    r = R(ctx)
    plan_ = standing_plan(r)
    queue: dict[str, Any] | None = None
    if r.reads is not None:
        try:
            queue = r.reads.queue("en")
        except Exception:  # noqa: BLE001  the queue is a supporting read; the answer says what it knows without it
            queue = None
    # the customer rows only: approvals, overdue invoices and the reserve alert are said from their own reads
    needs = [x for x in (queue or {}).get("needs_you") or [] if x.get("kind") in ("DECISION", "SETUP")] if queue else []
    return Metric("what_waits", {"plan": plan_.value is not None, "approvals": len(approvals_pending(r).value),
                                 "deal_rows": len(needs)}, "", r.today,
                  "worklist.needs_you, store.approvals(PENDING), home.next_action", {"queue_read": queue is not None})


# ================================================================ the two hypotheticals and the rest


def payoff_all(ctx: Any) -> Metric:
    """"Can we clear all our debts?": the whole debt repaid today, on a model copy of the state (cash less the debt, no loans, no
    drawn balances, no advances), projected the same conservative way. Read-only: nothing is sent to the executor."""
    r = R(ctx)
    total = total_debt(r).value
    s = r.state
    fac = [f.model_copy(update={"drawn_fen": 0}) if f.counts_in_leverage else f for f in s.facilities]
    rcv = [x.model_copy(update={"advance_fen": 0, "advance_facility_id": None, "status": "OPEN"}) if x.status == "FINANCED" else x
           for x in s.receivables]
    lots = [x for x in s.lots if not any(f.id == x.facility_id and f.counts_in_leverage for f in s.facilities)]
    copy = s.model_copy(update={"cash_fen": s.cash_fen - total, "debts": [], "facilities": fac, "receivables": rcv, "lots": lots})
    low_fen: int | None = None
    low_day: int | None = None
    try:
        b = current_books(copy, r.store.commitments())
        t = project(b.state, b.with_([]), [], Mode.CONSERVATIVE, r.horizon, r.floor)
        ahead = [d for d in t.days if d.day >= r.today] or list(t.days)
        low = min(ahead, key=lambda d: (d.closing_fen, d.day))
        low_fen, low_day = low.closing_fen, low.day
    except (EngineError, ValueError):
        pass
    ok = low_fen is not None and low_fen >= r.floor
    return Metric("payoff_all", ok, "yes" if ok else "no", low_day, "financial.project on a model copy with the debt repaid",
                  {"total_fen": total, "cash_after_fen": s.cash_fen - total, "low_fen": low_fen, "low_day": low_day,
                   "headroom_fen": s.cash_fen - r.floor})


def payroll_cover(ctx: Any) -> Metric:
    r = R(ctx)
    pay = next((e for e in r.events(r.today, r.today + r.horizon) if e.kind == FlowKind.PAYROLL.value), None)
    if pay is None:
        return Metric("payroll_cover", None, "none", None, "state.flows PAYROLL")
    closing = cash_on(r, pay.day).value
    before = closing - pay.amount_fen if closing is not None else None
    return Metric("payroll_cover", closing is not None and closing >= 0, money(-pay.amount_fen), pay.day,
                  "next PAYROLL flow; trajectory.days[day].closing",
                  {"amount_fen": -pay.amount_fen, "closing_fen": closing, "before_fen": before})


def capex_case(ctx: Any) -> Metric:
    """The capex case FLOW holds (`capex.evaluate_capex` on the default request: POST /capex/evaluate with no body)."""
    from app.capex import CapexDisabled, CapexRequest, evaluate_capex

    r = R(ctx)
    req = CapexRequest()
    try:
        res = evaluate_capex(req, r.state, r.mandate, commitments=r.store.commitments())
    except CapexDisabled:
        return Metric("capex_case", None, "off", None, "capex.evaluate_capex", {"disabled": True})
    except EngineError:
        return Metric("capex_case", None, "none", None, "capex.evaluate_capex", {"disabled": False})
    sel = next((s for s in res.structures if s.id == res.selected_id), None)
    cash = next((s for s in res.structures if s.kind == "CASH_LINE" or s.id == "cash_line"), None)
    return Metric("capex_case", res.selected_id, money(req.price_fen), None, "capex.evaluate_capex",
                  {"price_fen": req.price_fen, "npv_fen": res.npv_fen, "payback_month": res.payback_month,
                   "selected": sel, "cash_feasible": bool(cash is not None and cash.feasible),
                   "hurdle": fmt_pct(Fraction(req.hurdle_bp, BP_DENOM)), "disabled": False})


def terms_extension_cost(ctx: Any, buyer_id: str | None, terms_days: int) -> Metric:
    """What longer terms for a buyer cost (`whatif.simulate`: the verifier on a hypothetical package; it writes nothing)."""
    from app.whatif import WhatIfParamError, WhatIfParams, simulate

    r = R(ctx)
    try:
        params = WhatIfParams(terms_days=terms_days, discount_bp=0, rebate_bp=0)
        w = simulate(r.state, r.mandate, params, trusted_owner_key_hex=r.owner_key_hex, day=r.day,
                     commitments=r.store.commitments(), buyer_id=buyer_id)
    except (WhatIfParamError, ValueError) as exc:
        return Metric("terms_extension_cost", None, "none", None, "whatif.simulate", {"error": str(exc)})
    fwd = w.forward
    breach = next((v.get("day") for v in w.violations if v.get("code") == "RESERVE_BREACH"), None)
    return Metric("terms_extension_cost", fwd.get("total_fen"), money(int(fwd.get("total_fen") or 0)), None, "whatif.simulate",
                  {"cap_fen": fwd.get("cap_fen"), "over_cap": bool(fwd.get("over_cap")), "outcome": w.outcome,
                   "breach_day": breach, "counters": len(w.counters), "codes": list(w.codes)})


METRICS: dict[str, Callable[[Any], Metric]] = {
    f.__name__: f for f in (
        cash_today, reserve, headroom_today, first_breach, lowest_point, funding_need, first_negative_cash_day, runway_days,
        gap_windows, upcoming_outflows, upcoming_inflows, cash_drivers, in_transit, total_debt, debt_positions,
        debt_service_month, next_debt_payment, drawn_by_facility, undrawn_committed, projected_interest_fees,
        marginal_cost_of_funds, fastest_and_cheapest_source, standing_plan, alternatives_priced, break_even,
        invoice_financing_capacity, receivables_total, receivables_by_customer, overdue, next_receipt, recurring_billing,
        terms_by_customer, covenant_ratios, covenant_breakpoints, ebitda_month, mandate_limits_and_validity, activity_since,
        what_waits, approvals_pending, payoff_all, payroll_cover, capex_case)
}
"""The metrics that take the context alone (the parametrised ones, `cash_on`, `late_payment_impact` and `terms_extension_cost`,
take their subject as well)."""
