"""Capacity: how much room the books leave, as day series, before and after a package, and the additional need FLOW could
still support (docs/CUSTOMER_ECONOMICS_BRIEF.md section F; map #88, ticket #96).

Read-only, like the rest of the strategy MVP: every figure is a reading of a labelled copy of the books (`Books`,
`model_copy`) through the kernel (the router's committed plan, the CONSERVATIVE projection, the verifier's own verdict
for a package). Nothing is stored and nothing is booked. Money is integer fen and days are absolute (INVARIANT 9).

The five dimensions, each reconciled to a figure the product already shows (the tests prove it):
  - cash buffer above the floor: `closing - min_cash` on the unfunded trajectory (its lowest point is `Reading` and
    Home's `cash.lowest_headroom_fen`);
  - credit-line headroom per facility: `limit - balance`, the balance rebuilt from `drawn_fen`, the plan's actions counted
    from their request day and the trajectory's REPAYMENT events (NOT `covenants.line_balances`, which counts an unlanded
    lot twice); with no plan today's figure is Home's `available`;
  - invoice-finance headroom per facility: `min(limit - balance, eligible receivables x advance rate - the plan's
    advances)`, read two ways, TODAY (the invoices issued, the executor's rule) and AS_ISSUED (recurring invoices
    issued as scheduled, labelled); TODAY is `alerts.engine._candidates` less the plan's advances;
  - concession headroom: `cap - booked forward concessions`; after a package `cap - the verdict's
    forward_concession_total_fen` (the what-if's `forward.headroom_fen`); per buyer likewise;
  - covenant headroom in money per month: the extra debt service (DSCR) or month-end debt (leverage) a month could carry.

A negative figure is kept and reported as "over by", never clamped. A source that is not COMMITTED and owner-approved
counts as nothing; `allow_new_borrowing = false` makes every borrowing headroom 0 with the reason stated.

`spare_capacity` is the additional need search (section F.3), further down.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.alerts import covenant_limits
from app.api.display import displayed
from app.api.presentation import t, when_text
from app.books import Books
from app.domain.models import (
    CashFlow,
    Commitment,
    ConcessionValue,
    CounterProposal,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    FundingAction,
    FundingActionKind,
    FundingPlan,
    LedgerEventKind,
    Mandate,
    Mode,
    Obligation,
    ObligationType,
    Repayment,
    Trajectory,
    Verdict,
)
from app.domain.money import fmt_yuan
from app.financial import EngineError, project
from app.funding import plan
from app.funding.router import shared_runs
from app.mandate.predicates import _net
from app.strategy.cache import AnswerCache, cache_key
from app.strategy.envelope import Setting, _params, open_context
from app.strategy.types import (
    CandidatePackage,
    CapacityBeforeAfter,
    CapacityDimension,
    CapacityReading,
    CapacitySnapshot,
    CapacityWindow,
    CovenantRoom,
    SpareCapacity,
    SpareCriterion,
    SpareShape,
)
from app.verifier import evaluate
from app.verifier.evaluate import _evaluate, _Router, counter_offer
from app.whatif.offer import build

# reasons (codes; `reason_text` words them)
NO_NEW_BORROWING = "NEW_BORROWING_NOT_ALLOWED"
NOT_OWNER_APPROVED = "NOT_OWNER_APPROVED"
NO_ELIGIBLE_INVOICE = "NO_ELIGIBLE_INVOICE"
EBITDA_NOT_POSITIVE = "EBITDA_NOT_POSITIVE"

_DRAWABLE = (FacilityKind.CREDIT_LINE, FacilityKind.GOV_GUARANTEED_LOAN, FacilityKind.EQUIPMENT_TERM_LOAN,
             FacilityKind.EQUIPMENT_LEASE)
MONTH_DAYS = 30
INVOICE_REACH_DAYS = 150  # past the horizon: far enough for the due day of any invoice issued inside it (terms to 100 days)


# ---------------------------------------------------------------- the package behind the "after" books


@dataclass(frozen=True)
class BoundPackage:
    """A package as the verifier binds it: the obligations it puts on the books and its forward-concession reading.
    `forward_total_fen` is the verdict's `forward_concession_total_fen` (existing + the net new)."""

    buyer_id: str
    label: str
    obligations: tuple[Obligation, ...]
    concession_values: tuple[ConcessionValue, ...]
    forward_total_fen: int

    @property
    def key(self) -> str:
        return "|".join(o.model_dump_json() for o in self.obligations) + f"#{self.forward_total_fen}"


Package = CandidatePackage | Verdict | CounterProposal | BoundPackage


def _bound_of_verdict(buyer_id: str, label: str, v: Verdict) -> BoundPackage:
    return BoundPackage(buyer_id, label, tuple(v.bound_obligations), tuple(v.concession_values),
                        v.forward_concession_total_fen)


def resolve_package(books: Books, mandate: Mandate, package: Package, *, day: int, commitments: Sequence[Commitment],
                    trusted_owner_key_hex: str | None) -> BoundPackage:
    """The bound obligations of a package. A `Verdict` or a `BoundPackage` is read as it is. A `CandidatePackage` goes
    through the same path the envelope uses (`whatif.offer.build`, then the verifier on these books); a
    `CounterProposal` is evaluated as the offer it would become (the counter re-check). `ValueError` when the owner's key
    is needed and not given, or when the verifier binds nothing (an unresolved package has no "after")."""
    if isinstance(package, BoundPackage):
        return package
    if isinstance(package, Verdict):
        return _bound_of_verdict("", "", package)
    if trusted_owner_key_hex is None:
        raise ValueError("a candidate package or a counter is evaluated by the verifier: the owner's key is needed")
    state = books.state
    if isinstance(package, CounterProposal):
        offer = counter_offer(package, day)
        label = package.label
    else:
        ctx = open_context(state, day, package.buyer_id)
        offer, _ = build(_params(Setting(package.terms_days, package.price_bp, package.early_pay_bp,
                                         package.early_pay_face_fen, package.rebate_bp)), ctx, day)
        label = ""
    try:
        with shared_runs():
            bundle = _evaluate(offer, state, mandate, trusted_owner_key_hex=trusted_owner_key_hex, day=day,
                               commitments=commitments, plans="committed", router=_Router(mandate), with_counters=False)
    except EngineError:
        bundle = evaluate(offer, state, mandate, trusted_owner_key_hex=trusted_owner_key_hex, day=day,
                          commitments=commitments, plans="committed")
    if not bundle.verdict.bound_obligations:
        raise ValueError(f"the package binds no obligation on these books ({bundle.verdict.summary})")
    return _bound_of_verdict(offer.counterparty_id, label, bundle.verdict)


def books_with(books: Books, package: BoundPackage) -> Books:
    """The labelled copy: the books plus the package's bound obligations (the `MarginalImpact` semantics)."""
    return Books(state=books.state, obligations=(*books.obligations, *package.obligations), lapsed=books.lapsed,
                 owners=books.owners)


# ---------------------------------------------------------------- balances rebuilt from the engine's own events


def request_day(a: FundingAction) -> int:
    """The day an action takes its facility's room: its request day, or the invoice's issue day for an advance on an
    invoice not issued yet (the router stamps `available_from_day`). The executor counts a lot from this day, not from
    the day its cash lands (ADR-0010 section 2)."""
    return a.available_from_day if a.available_from_day is not None else a.day


def facility_balances(state: FinancialState, trajectory: Trajectory,
                      actions: Sequence[FundingAction]) -> dict[str, list[int]]:
    """Each facility's balance on every day of the trajectory (index = day): `drawn_fen` (an unlanded lot is already in
    it) + the plan's draws and advances from their request day - the |REPAYMENT| events of the trajectory with
    `ref == facility.id`. The trajectory's DRAW and ADVANCE events are not added: a lot's cash landing is not new debt.
    Against `DayPoint.debt_outstanding_fen` (which books a plan's draw on the day its cash lands) the sum differs only
    by what is requested and not yet landed."""
    last = trajectory.days[-1].day
    out: dict[str, list[int]] = {}
    for f in state.facilities:
        delta: dict[int, int] = defaultdict(int)
        for a in actions:
            if a.facility_id == f.id and a.kind in (FundingActionKind.DRAW, FundingActionKind.FINANCE_INVOICE):
                delta[request_day(a)] += a.amount_fen
        for p in trajectory.days:
            for e in p.events:
                if e.kind == LedgerEventKind.REPAYMENT and e.ref == f.id:
                    delta[p.day] -= abs(e.amount_fen)
        bal, series = f.drawn_fen, []
        for d in range(last + 1):
            bal += delta.get(d, 0)
            series.append(bal)
        out[f.id] = series
    return out


def in_flight(actions: Sequence[FundingAction], state: FinancialState, day: int) -> int:
    """What the plan has requested by `day` and whose cash has not landed (the gap between `facility_balances` and
    `DayPoint.debt_outstanding_fen`)."""
    lead = {f.id: f.lead_time_days for f in state.facilities}
    return sum(a.amount_fen for a in actions
               if a.kind in (FundingActionKind.DRAW, FundingActionKind.FINANCE_INVOICE)
               and request_day(a) <= day < request_day(a) + lead.get(a.facility_id, 0))


# ---------------------------------------------------------------- windows from a series


def _window(series: Sequence[int], start: int, dimension: CapacityDimension, *, facility_id: str | None = None,
            floor_run: bool = False, reason: str | None = None, buyer_id: str | None = None,
            reading: CapacityReading | None = None, assumed_recovery: bool = False) -> CapacityWindow:
    """The window of a day series (`series[i]` is the figure on day `start + i`): today's figure, the lowest point (the
    first day it is reached), the last day of the run that stays at that low and the day it recovers.

    With `floor_run` the run is the stretch below zero around the lowest point (a cash buffer: "below your minimum from
    ... through ..."). Otherwise it is the stretch that stays exactly at the lowest figure (a line "at ¥13.80 through
    1 Nov"). A figure that never rises again has no recovery day."""
    n = len(series)
    low = min(series)
    i = list(series).index(low)
    j = i
    if floor_run:
        if low < 0:
            while j + 1 < n and series[j + 1] < 0:
                j += 1
    else:
        while j + 1 < n and series[j + 1] == low:
            j += 1
    rec = j + 1 if j + 1 < n else None
    return CapacityWindow(
        dimension=dimension, facility_id=facility_id, today_fen=series[0],
        after_fen=series[rec] if rec is not None else None, lowest_fen=low, lowest_day=start + i,
        recovers_day=start + rec if rec is not None else None, through_day=start + j, over_by=low < 0, reason=reason,
        buyer_id=buyer_id, reading=reading, recovery_assumed=assumed_recovery and rec is not None)


def _point(value: int, day: int, through: int, dimension: CapacityDimension, **extra: Any) -> CapacityWindow:
    return CapacityWindow(dimension=dimension, facility_id=extra.pop("facility_id", None), today_fen=value,
                          after_fen=None, lowest_fen=value, lowest_day=day, recovers_day=None, through_day=through,
                          over_by=value < 0, **extra)


# ---------------------------------------------------------------- the invoices behind the finance headroom


@dataclass(frozen=True)
class _Invoice:
    id: str
    issue_day: int
    due_day: int
    outstanding_fen: int
    issued: bool  # on the books today (the executor can finance it today); False: a recurring invoice issued as scheduled


def _issue_day_of(rid: str) -> int:
    try:
        return int(rid.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return 0


def _eligible_invoices(state: FinancialState, funded: Trajectory, early_ids: set[str]) -> list[_Invoice]:
    """The invoices the finance headroom may count: the receipts the conservative trajectory dates (so terms, price
    changes and unconfirmed invoices are the engine's), confirmed, OPEN (not FINANCED already), not under an
    early-payment agreement. Not yet due is the day's test, made where the series is built."""
    issued = {r.id: r for r in state.receivables}
    out: list[_Invoice] = []
    for p in funded.days:
        for e in p.events:
            if e.kind != LedgerEventKind.RECEIPT or e.ref is None or e.amount_fen <= 0 or e.ref in early_ids:
                continue
            r = issued.get(e.ref)
            if r is not None:
                if r.status != "OPEN" or not r.confirmed:
                    continue
                out.append(_Invoice(r.id, r.issue_day, p.day, e.amount_fen, True))
            elif e.ref.startswith("RI:"):
                out.append(_Invoice(e.ref, _issue_day_of(e.ref), p.day, e.amount_fen, False))
    return out


def _early_ids(obligations: Sequence[Obligation], funded: Trajectory) -> set[str]:
    """Invoices under a live early-payment agreement: named by an IMMEDIATE_DISCOUNT on the books, or settled early in
    the trajectory (the engine refuses to finance an invoice with an early settlement booked)."""
    ids = {o.base.receivable_id for o in obligations
           if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.base.receivable_id is not None}
    ids |= {e.ref for p in funded.days for e in p.events if e.kind == LedgerEventKind.EARLY_RECEIPT and e.ref}
    return ids


def _usable(f: Facility) -> bool:
    return f.status == FacilityStatus.COMMITTED


# ---------------------------------------------------------------- the snapshot


def _start_of(state: FinancialState, day: int, last: int) -> int:
    return min(max(day, state.as_of_day), last)


def _covenant_rooms(state: FinancialState, mandate: Mandate, funded: Trajectory, start: int) -> list[CovenantRoom]:
    dscr_limits, lev_limits = covenant_limits(state, mandate)
    dscr_limit = max(dscr_limits, key=lambda z: z[0])[0]
    lev_limit = min(lev_limits, key=lambda z: z[0])[0]
    out: list[CovenantRoom] = []
    for m in funded.months:
        if MONTH_DAYS * m.month < start:
            continue
        ds = m.debt_service_fen
        dscr = math.floor(m.ebitda_fen / dscr_limit) - ds if ds > 0 else None
        lev = (math.floor(lev_limit * 12 * m.ebitda_fen) - m.total_debt_fen if m.ebitda_fen > 0
               else -m.total_debt_fen)  # EBITDA <= 0: leverage is undefined, a breach exactly when there is debt
        out.append(CovenantRoom(month=m.month, dscr_room_fen=dscr, leverage_room_fen=lev))
    return out


def _covenant_windows(rooms: list[CovenantRoom], state: FinancialState) -> list[CapacityWindow]:
    out: list[CapacityWindow] = []
    dscr = [(r.month, r.dscr_room_fen) for r in rooms if r.dscr_room_fen is not None]
    if dscr:
        month, low = min(dscr, key=lambda z: (z[1], z[0]))
        out.append(_point(dscr[0][1], MONTH_DAYS * month, MONTH_DAYS * month, "dscr_room", month=month)
                   .model_copy(update={"lowest_fen": low, "over_by": low < 0}))
    if rooms:
        month, low = min(((r.month, r.leverage_room_fen) for r in rooms), key=lambda z: (z[1], z[0]))
        reason = EBITDA_NOT_POSITIVE if state.monthly_ebitda_fen <= 0 else None
        out.append(_point(rooms[0].leverage_room_fen, MONTH_DAYS * month, MONTH_DAYS * month, "leverage_room",
                          month=month, reason=reason).model_copy(update={"lowest_fen": low, "over_by": low < 0}))
    return out


def _concession_windows(state: FinancialState, mandate: Mandate, start: int, forward_total: int | None,
                        package: BoundPackage | None) -> list[CapacityWindow]:
    """Aggregate and per-buyer concession headroom: a point value over the valuation window [today, today + H)."""
    through = start + mandate.forward_concession_horizon_days - 1
    cap = mandate.max_aggregate_forward_concession_fen
    used = sum(fc.value_fen for fc in state.forward_concessions) if forward_total is None else forward_total
    out = [_point(cap - used, start, through, "concession")]
    by_id = {o.id: o for o in package.obligations} if package is not None else {}
    for buyer, buyer_cap in sorted(mandate.per_buyer_caps_fen.items()):
        existing = sum(fc.value_fen for fc in state.forward_concessions if fc.counterparty_id == buyer)
        new = 0
        if package is not None:
            mine = [cv for cv in package.concession_values
                    if (by_id[cv.obligation_id].counterparty_id if cv.obligation_id in by_id else package.buyer_id) == buyer]
            new = _net(mine, by_id).net_fen
        out.append(_point(buyer_cap - existing - new, start, through, "concession_buyer", buyer_id=buyer))
    return out


def snapshot(books: Books, mandate: Mandate, day: int, *, package: BoundPackage | None = None) -> CapacitySnapshot:
    """The capacity of one set of books. With `package` its bound obligations must already be in `books` (see
    `books_with`); the package is passed only for the concession reading, which is the verdict's own total."""
    state, floor = books.state, mandate.min_cash_fen
    obs = books.with_([])
    with shared_runs():
        committed = plan(state, obs, mandate)
    unfunded = project(state, obs, [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
    actions = list(committed.actions) if committed.admissible else []
    funded = project(state, obs, actions, Mode.CONSERVATIVE, mandate.horizon_days, floor) if actions else unfunded
    start = _start_of(state, day, funded.days[-1].day)
    last = funded.days[-1].day
    borrowing_closed = not mandate.allow_new_borrowing
    windows: list[CapacityWindow] = []

    # cash buffer: the unfunded trajectory (on the funded one it is 0 whenever a plan is needed)
    buffer = [p.closing_fen - floor for p in unfunded.days if p.day >= start]
    below = [p.day for p in unfunded.days if p.day >= start and p.closing_fen < floor]
    windows.append(_window(buffer, start, "cash_buffer", floor_run=True))

    # credit lines and loans
    balances = facility_balances(state, funded, actions)
    for f in sorted(state.facilities, key=lambda x: x.id):
        if not (_usable(f) and f.kind in _DRAWABLE and f.repayment != Repayment.ON_RECEIPT and f.limit_fen > 0):
            continue
        reason = NOT_OWNER_APPROVED if not f.owner_approved else NO_NEW_BORROWING if borrowing_closed else None
        series = ([0] * (last - start + 1) if reason else [f.limit_fen - balances[f.id][d] for d in range(start, last + 1)])
        windows.append(_window(series, start, "credit_line", facility_id=f.id, reason=reason,
                               assumed_recovery=f.kind == FacilityKind.CREDIT_LINE))

    # invoice finance: TODAY and AS_ISSUED
    # the receipts dated beyond the horizon are in the invoices' own reach: read them on a trajectory that runs on
    reach = project(state, obs, actions, Mode.CONSERVATIVE, mandate.horizon_days + INVOICE_REACH_DAYS, floor)
    invoices = _eligible_invoices(state, reach, _early_ids(obs, reach))
    for f in sorted(state.facilities, key=lambda x: x.id):
        if not (_usable(f) and f.kind == FacilityKind.INVOICE_FINANCING and f.limit_fen > 0):
            continue
        reason = NOT_OWNER_APPROVED if not f.owner_approved else NO_NEW_BORROWING if borrowing_closed else None
        rate = f.advance_rate_bp or 10_000
        advances = [a for a in actions if a.kind == FundingActionKind.FINANCE_INVOICE and a.facility_id == f.id]

        def room(d: int, pool: list[_Invoice], f: Facility = f, rate: int = rate,
                 advances: list[FundingAction] = advances) -> int:
            live = {i.id for i in pool if i.issue_day <= d < i.due_day}
            cap = sum(i.outstanding_fen * rate // 10_000 for i in pool if i.id in live)
            taken = sum(a.amount_fen for a in advances if a.receivable_id in live and request_day(a) <= d)
            return min(f.limit_fen - balances[f.id][d], cap - taken)

        today_pool = [i for i in invoices if i.issued]
        today_due = [i.due_day for i in today_pool if i.due_day > start]
        today_end = min(today_due) - 1 if today_due else start
        for reading, pool, end in (("TODAY", today_pool, min(today_end, last)), ("AS_ISSUED", invoices, last)):
            if reason:
                series = [0] * (end - start + 1)
            else:
                series = [room(d, pool) for d in range(start, end + 1)]
            note = reason or (NO_ELIGIBLE_INVOICE if not any(i.due_day > start for i in pool) else None)
            windows.append(_window(series, start, "invoice_finance", facility_id=f.id, reason=note,
                                   reading=reading))  # type: ignore[arg-type]

    # concessions
    windows += _concession_windows(state, mandate, start, package.forward_total_fen if package is not None else None, package)

    # covenants
    rooms = _covenant_rooms(state, mandate, funded, start)
    windows += _covenant_windows(rooms, state)

    return CapacitySnapshot(
        day=start, through_day=last, windows=windows, covenant_months=rooms,
        no_borrowing_reason=NO_NEW_BORROWING if borrowing_closed else None, plan_admissible=committed.admissible,
        need_first_day=below[0] if below else None, need_last_day=below[-1] if below else None)


_SNAPSHOTS: AnswerCache[CapacityBeforeAfter] = AnswerCache()


def capacity_before_after(books: Books, mandate: Mandate, package: Package | None, day: int,
                          commitments: Sequence[Commitment] = (), *,
                          trusted_owner_key_hex: str | None = None) -> CapacityBeforeAfter:
    """The snapshot for the books as they stand and, when a package is given, for the labelled copy with that package in
    force: a `CandidatePackage` (bound through `whatif.offer.build` and the verifier, which needs the owner's key), a
    verdict's bound obligations (`Verdict`), a `CounterProposal` or a `BoundPackage`. Pure in (books, mandate, day,
    commitments, package); cached by `strategy.cache` with single-flight."""
    bound = (resolve_package(books, mandate, package, day=day, commitments=commitments,
                             trusted_owner_key_hex=trusted_owner_key_hex) if package is not None else None)
    key = cache_key(books.state, mandate, day, commitments, "capacity", _books_key(books), bound.key if bound else "")

    def compute() -> CapacityBeforeAfter:
        before = snapshot(books, mandate, day)
        if bound is None:
            return CapacityBeforeAfter(before=before)
        return CapacityBeforeAfter(before=before, after=snapshot(books_with(books, bound), mandate, day, package=bound),
                                   label=bound.label)

    return _SNAPSHOTS.get_or_compute(key, compute)


def _books_key(books: Books) -> str:
    return "|".join(o.model_dump_json() for o in books.obligations)


def clear_cache() -> None:
    _SNAPSHOTS.clear()
    _SPARE.clear()


# ---------------------------------------------------------------- display (the server writes every string)

_DIMENSION = {
    "cash_buffer": ("Cash above your minimum", "高于最低现金的部分"),
    "credit_line": ("Credit line room", "授信额度余量"),
    "invoice_finance": ("Invoice-finance room", "发票融资余量"),
    "concession": ("Concession budget left", "让步额度余量"),
    "concession_buyer": ("Concession budget left for this buyer", "该客户的让步额度余量"),
    "dscr_room": ("Debt service room (DSCR)", "还本付息余量（偿债覆盖率）"),
    "leverage_room": ("Debt room (leverage)", "债务余量（杠杆率）"),
}
_REASONS = {
    NO_NEW_BORROWING: ("your mandate does not allow new borrowing", "您的授权不允许新增借款"),
    NOT_OWNER_APPROVED: ("this facility is not approved by you", "该融资额度尚未获您批准"),
    NO_ELIGIBLE_INVOICE: ("no invoice can be financed (confirmed, not financed, not under an early-payment agreement, not yet due)",
                          "没有可融资的发票（需已确认、未融资、未约定提前付款、尚未到期）"),
    EBITDA_NOT_POSITIVE: ("monthly EBITDA is not positive, so leverage is undefined", "月度 EBITDA 不为正，杠杆率无从计算"),
}


def reason_text(code: str | None, lang: str = "en") -> str | None:
    if code is None:
        return None
    en, zh = _REASONS.get(code, (code, code))
    return t(lang, en, zh)


def dimension_label(dimension: str, lang: str = "en") -> str:
    en, zh = _DIMENSION[dimension]
    return t(lang, en, zh)


def headroom_text(fen: int, lang: str = "en") -> str:
    """A headroom in words: a negative one is "over by", never a clamped zero or a bare minus."""
    if fen < 0:
        return t(lang, f"over by {fmt_yuan(-fen)}", f"超出 {fmt_yuan(-fen)}")
    return fmt_yuan(fen)


def window_view(w: CapacityWindow, today: int, lang: str = "en") -> dict[str, Any]:
    """A window for the API: the contract's fields with a `*_display` for every money field (`displayed`), the relative-day
    words for every day (`*_when`), the headline texts ("over by" when negative) and the reason in words."""
    out: dict[str, Any] = displayed(w.model_dump())
    for name in ("lowest_day", "through_day", "recovers_day"):
        out[name.replace("_day", "_when")] = when_text(getattr(w, name), today, lang)
    out["today_text"] = headroom_text(w.today_fen, lang)
    out["lowest_text"] = headroom_text(w.lowest_fen, lang)
    out["after_text"] = headroom_text(w.after_fen, lang) if w.after_fen is not None else None
    out["label"] = dimension_label(w.dimension, lang)
    out["reason_text"] = reason_text(w.reason, lang)
    return out


# ---------------------------------------------------------------- the additional need FLOW could still support (F.3)

YUAN_STEP_FEN = 100_000  # the ¥1,000 grid
SCAN_BUDGET = 64  # the most points a disagreement scan evaluates before it narrows to the best coarse point's cell

SHAPE_S1 = ("a one-off payment of X today that does not come back within the horizon",
            "一笔今天支付、且在预测期内不会收回的一次性付款 X")
CRITERIA = {
    "R-TODAY": ("without another facility or your approval, with every step one FLOW can run today",
                "无需新增融资额度或您的批准，且每一步 FLOW 今天都能执行"),
    "R-AS-ISSUED": (("without another facility or your approval, assuming the invoices not yet issued are issued as "
                     "scheduled and can be financed on their issue day (an assumption)"),
                    "无需新增融资额度或您的批准，并假设尚未开具的发票按计划开具、开具当天即可融资（这是假设）"),
}
REFUSED = ("none: today's books already need the owner or a new facility",
           "无：按今天的账面，已经需要您出面或新增融资额度")


def shape_text(shape: str = "S1", criterion: str = "R-TODAY", lang: str = "en") -> str:
    """The shape and criterion sentence, printed with every figure."""
    c_en, c_zh = CRITERIA[criterion]
    return t(lang, f"Counted as {SHAPE_S1[0]}, {c_en}.", f"按{SHAPE_S1[1]}计算，{c_zh}。")


def refused_sentence(lang: str = "en") -> str:
    return t(lang, REFUSED[0], REFUSED[1])


@dataclass(frozen=True)
class _Found:
    value: int | None
    confirmed: bool
    scanned: bool = False


def _scan_best(values: Sequence[int], ok: Callable[[int], bool], budget: int) -> int:
    """The largest passing value of a grid, by a coarse scan: at most `budget` points evaluated, then the cell above the
    best coarse point scanned the same way (so a grid of any size ends at the grid's own resolution)."""
    n = len(values)
    if n <= budget:
        return max(v for v in values if ok(v))
    stride = -(-n // budget)
    coarse = sorted({*range(0, n, stride), n - 1})
    top = max(i for i in coarse if ok(values[i]))
    return _scan_best(values[top: min(n, top + stride)], ok, budget)


def last_true(values: Sequence[int], ok: Callable[[int], bool], *, budget: int = SCAN_BUDGET) -> _Found:
    """Largest value with ok(value), assuming ok holds up to a boundary and fails after it (binary search, then the two
    values past the boundary re-checked; if one of them passes the grid is scanned coarsely and its best passing value
    returned): the envelope's rule (`strategy.envelope.last_true`), with a bounded scan because one probe here is a
    router run. `values[0]` is asked first: if it fails nothing passes."""
    if not values or not ok(values[0]):
        return _Found(None, True)
    lo, hi = 0, len(values)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(values[mid]):
            lo = mid
        else:
            hi = mid
    if any(ok(v) for v in values[lo + 1: lo + 3]):
        return _Found(_scan_best(values, ok, budget), False, True)
    return _Found(values[lo], True)


def _without_buyer_early_pay(state: FinancialState) -> FinancialState:
    """The copy's facilities without any `BUYER_EARLY_PAY` source: it needs the buyer's agreement, and left in it makes the
    cheapest plan an early payment that the agent cannot run alone (brief F.3)."""
    return state.model_copy(update={"facilities": [f for f in state.facilities if f.kind != FacilityKind.BUYER_EARLY_PAY]})


def _with_need(state: FinancialState, x_fen: int) -> FinancialState:
    """Shape S1: the copy with a one-off payment of `x_fen` today that does not return within the horizon."""
    if x_fen == 0:
        return state
    flow = CashFlow(id=f"SPARE-NEED-{x_fen}", day=state.as_of_day, amount_fen=-x_fen, kind=FlowKind.OTHER,
                    label="hypothetical one-off payment", confirmed=True)
    return state.model_copy(update={"flows": [*state.flows, flow]})


def _future_only_cannot_run(p: FundingPlan, state: FinancialState) -> bool:
    """R-AS-ISSUED: whether every leg that cannot run today is an advance on a recurring invoice not yet issued (which
    the agent may run alone on its issue day). A buyer's early payment, a bill, or a plan admissible only as a whole is not."""
    if "only admissible as a whole" in p.not_executable_reason:
        return False
    issued = {r.id for r in state.receivables if r.status == "OPEN"}
    return all(not (a.kind in (FundingActionKind.EARLY_PAY, FundingActionKind.DISCOUNT_BILL))
               and not (a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id in issued
                        and (a.available_from_day or a.day) > a.day)
               for a in p.actions)


def _passes(p: FundingPlan, state: FinancialState, criterion: str) -> bool:
    if not p.admissible or p.needs_owner_approval:
        return False
    if p.executable_now:
        return True
    return criterion == "R-AS-ISSUED" and _future_only_cannot_run(p, state)


def _binding(p: FundingPlan) -> str:
    """Why this plan fails the criterion, in the router's own words."""
    if not p.admissible:
        return "; ".join(dict.fromkeys(v.message for v in p.violations)) or p.label
    if p.needs_owner_approval:
        return p.approval_reason or p.label
    if not p.executable_now:
        return p.not_executable_reason or p.label
    return ""


def _ceiling(state: FinancialState, floor: int) -> int:
    """The largest X that could possibly be funded: the cash above the floor plus every committed source's limit (a
    funding leg never exceeds its limit and cash only falls by X on day 0). Rounded down to the grid."""
    room = sum(f.limit_fen for f in state.facilities
               if f.status == FacilityStatus.COMMITTED and f.owner_approved
               and f.kind not in (FacilityKind.BUYER_EARLY_PAY, FacilityKind.EQUITY))
    top = max(0, state.cash_fen - floor) + room
    return top - top % YUAN_STEP_FEN


_SPARE: AnswerCache[SpareCapacity] = AnswerCache()


def spare_capacity(books: Books, mandate: Mandate, day: int, commitments: Sequence[Commitment] = (),
                   package: Package | None = None, shape: SpareShape = "S1", criterion: SpareCriterion = "R-TODAY", *,
                   trusted_owner_key_hex: str | None = None) -> SpareCapacity:
    """X*: the largest X on a ¥1,000 grid for which the router, on a labelled copy of the books (plus the package's
    obligations, plus a one-off payment of X today, without the buyer's early-payment source), returns a plan that is
    admissible, needs no owner approval and can run (today; `R-AS-ISSUED` also what runs once the invoices are issued).

    Bisection with both neighbours of the boundary re-checked and a coarse scan on disagreement: monotonicity is not
    assumed (whole-period billing steps the effective rate). `x_star_fen` is None, with `refused_text`, when X = 0 already
    fails: today's books need the owner or a new facility. Cached by `strategy.cache` (single-flight): it runs on request,
    never on page load. Raises `ValueError` for a shape or criterion that is not defined."""
    if shape != "S1":
        raise ValueError(f"shape {shape!r} is not defined (only S1)")
    if criterion not in CRITERIA:
        raise ValueError(f"criterion {criterion!r} is not defined")
    bound = (resolve_package(books, mandate, package, day=day, commitments=commitments,
                             trusted_owner_key_hex=trusted_owner_key_hex) if package is not None else None)
    key = cache_key(books.state, mandate, day, commitments, "spare", shape, criterion, _books_key(books),
                    bound.key if bound else "")
    return _SPARE.get_or_compute(key, lambda: _search(books, mandate, bound, shape, criterion))


def _search(books: Books, mandate: Mandate, bound: BoundPackage | None, shape: SpareShape,
            criterion: SpareCriterion) -> SpareCapacity:
    started = time.perf_counter()
    after = books_with(books, bound) if bound is not None else books
    base = _without_buyer_early_pay(after.state)
    obs = after.with_([])
    runs: dict[int, FundingPlan] = {}

    def plan_at(x: int) -> FundingPlan:
        if x not in runs:
            runs[x] = plan(_with_need(base, x), obs, mandate)
        return runs[x]

    def ok(x: int) -> bool:
        return _passes(plan_at(x), base, criterion)

    top = _ceiling(base, mandate.min_cash_fen)
    grid = range(0, top + YUAN_STEP_FEN, YUAN_STEP_FEN)
    found = last_true(grid, ok)
    words = shape_text(shape, criterion)
    seconds = round(time.perf_counter() - started, 3)
    if found.value is None:
        return SpareCapacity(shape=shape, criterion=criterion, step_fen=YUAN_STEP_FEN, x_star_fen=None, plan_at_x=None,
                             plan_next=None, binding_reason="", shape_text=words, refused_text=REFUSED[0],
                             ceiling_fen=top, evaluations=len(runs), scanned=found.scanned, seconds=seconds)
    x = found.value
    nxt = plan_at(x + YUAN_STEP_FEN)
    return SpareCapacity(
        shape=shape, criterion=criterion, step_fen=YUAN_STEP_FEN, x_star_fen=x, plan_at_x=plan_at(x), plan_next=nxt,
        binding_reason=_binding(nxt), shape_text=words, refused_text=None, ceiling_fen=top, evaluations=len(runs),
        scanned=found.scanned, seconds=round(time.perf_counter() - started, 3))


__all__ = [
    "CRITERIA",
    "NO_NEW_BORROWING",
    "REFUSED",
    "SCAN_BUDGET",
    "YUAN_STEP_FEN",
    "BoundPackage",
    "Package",
    "capacity_before_after",
    "clear_cache",
    "dimension_label",
    "facility_balances",
    "headroom_text",
    "in_flight",
    "last_true",
    "reason_text",
    "refused_sentence",
    "request_day",
    "resolve_package",
    "shape_text",
    "snapshot",
    "spare_capacity",
    "window_view",
]
