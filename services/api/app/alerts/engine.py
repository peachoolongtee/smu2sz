"""Cash-flow alerts from the CONSERVATIVE trajectory (INVARIANTS 4, 5, 11).

Every alert carries a formula and the typed operation it suggests. Nothing here executes anything:
a suggestion is data for the owner or the agent to submit to the executor, which computes its tier.

Committed cure. A reserve breach "has a committed cure" when a projection that adds draws on
COMMITTED, owner-approved facilities (requested today, landing after their lead times) closes every
day of the breach at or above the floor. The search is greedy (credit lines and loans first, then
invoice financing, invoice by invoice) and then drops any action the cure does not need. It proves
feasibility only; the funding router prices the cheapest admissible plan.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from fractions import Fraction

from app.alerts.models import EXECUTABLE_KINDS, Alert, AlertKind, Severity, SuggestedAction
from app.books import Books, current_books
from app.domain.models import (
    CommitmentStatus,
    CovenantKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingAction,
    FundingActionKind,
    LedgerEventKind,
    Mandate,
    Mode,
    Obligation,
    Repayment,
    Trajectory,
)
from app.domain.money import DAYS_PER_YEAR, Ratio, bp, fmt_pct, fmt_yuan, round_half_up
from app.domain.ports import LedgerStore
from app.financial import EngineError, project
from app.financial.lots import ensure_lots, first_unsettled, landed, repay
from app.funding.rates import action_rate, approval_reason

MONTH_DAYS = 30
HEADROOM_SHARE = Fraction(1, 10)  # reserve headroom below 10% of the floor
COVENANT_HEADROOM = Fraction(1, 10)  # 0.10x
CONCESSION_SHARE = Fraction(4, 5)  # 80% of the cap
EXPIRY_WINDOW_DAYS = 7

_DRAWABLE = (FacilityKind.CREDIT_LINE, FacilityKind.GOV_GUARANTEED_LOAN, FacilityKind.EQUIPMENT_TERM_LOAN,
             FacilityKind.EQUIPMENT_LEASE)
_RANK = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


def x(r: Fraction) -> str:
    """Exact ratio to a 2 dp half-up display: '1.92×'."""
    q = round_half_up(r * 100)
    sign = "−" if q < 0 else ""
    q = abs(q)
    return f"{sign}{q // 100}.{q % 100:02d}×"


def _usable(f: Facility) -> bool:
    return f.status == FacilityStatus.COMMITTED and f.owner_approved


# ---------------------------------------------------------------- reserve


def _episodes(t: Trajectory, floor: int, start: int) -> list[tuple[int, int]]:
    """Maximal runs [first, last] of days >= start that close below the floor."""
    out: list[tuple[int, int]] = []
    run: int | None = None
    for p in t.days:
        if p.day < start:
            continue
        if p.closing_fen < floor:
            run = p.day if run is None else run
        elif run is not None:
            out.append((run, p.day - 1))
            run = None
    if run is not None:
        out.append((run, t.days[-1].day))
    return out


def _cured(state: FinancialState, obs: list[Obligation], actions: list[FundingAction], horizon: int, floor: int,
           start: int, end: int) -> bool:
    try:
        t = project(state, obs, actions, Mode.CONSERVATIVE, horizon)
    except EngineError:
        return False
    return all(p.closing_fen >= floor for p in t.days if start <= p.day <= end)


def stable_id(prefix: str, kind: AlertKind, subject: str, day: int | None) -> str:
    """A deterministic alert id: a hash of the kind, the subject and the day the alert refers to."""
    digest = hashlib.sha256(f"{kind.value}|{subject}|{day}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _candidates(state: FinancialState, day: int) -> list[FundingAction]:
    """Draws and invoice advances the executor would accept on `day` (today): COMMITTED facilities, and
    invoices that exist, are OPEN, buyer-confirmed and not yet due."""
    out: list[FundingAction] = []
    for f in state.facilities:
        if _usable(f) and f.kind in _DRAWABLE and f.repayment != Repayment.ON_RECEIPT and f.limit_fen > f.drawn_fen:
            out.append(FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=day,
                                     amount_fen=f.limit_fen - f.drawn_fen))
    invoices: list[tuple[int, str, int]] = []  # (due, id, outstanding face)
    for r in state.receivables:
        if r.status == "OPEN" and r.confirmed and r.outstanding_fen > 0 and r.due_day > day:
            invoices.append((r.due_day, r.id, r.outstanding_fen))
    invoices.sort()  # a recurring invoice not yet issued is not a receivable: the executor refuses it today
    for f in state.facilities:
        if not (_usable(f) and f.kind == FacilityKind.INVOICE_FINANCING):
            continue
        room = f.limit_fen - f.drawn_fen
        for _due, rid, face in invoices:
            if room <= 0:
                break
            cap = face * (f.advance_rate_bp or 10_000) // 10_000
            amount = min(cap, room)
            if amount > 0:
                out.append(FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id=f.id, day=day,
                                         amount_fen=amount, receivable_id=rid))
                room -= amount
    return out


def committed_cure(state: FinancialState, obs: list[Obligation], horizon: int, floor: int, day: int,
                   start: int, end: int) -> list[FundingAction] | None:
    """A small set of committed funding actions that keeps days start..end at or above the floor. Every
    action is requested today: `day`, and never before the day the books are closed to."""
    day = max(day, state.as_of_day)
    chosen: list[FundingAction] = []
    for a in _candidates(state, day):
        trial = [*chosen, a]
        try:
            project(state, obs, trial, Mode.CONSERVATIVE, horizon)
        except EngineError:
            continue  # this action is not feasible (limit, timing, early-settled invoice ...)
        chosen = trial
        if _cured(state, obs, chosen, horizon, floor, start, end):
            break
    else:
        return None
    for a in list(reversed(chosen)):  # drop what the cure does not need
        rest = [b for b in chosen if b is not a]
        if rest and _cured(state, obs, rest, horizon, floor, start, end):
            chosen = rest
    if len(chosen) == 1:  # one source: size it to the peak shortfall when that is enough
        need = max(floor - p.closing_fen for p in project(state, obs, [], Mode.CONSERVATIVE, horizon).days
                   if start <= p.day <= end)
        a = chosen[0]
        if 0 < need < a.amount_fen:
            sized = a.model_copy(update={"amount_fen": need})
            if _cured(state, obs, [sized], horizon, floor, start, end):
                chosen = [sized]
    return chosen


def _suggest(a: FundingAction) -> SuggestedAction:
    if a.kind == FundingActionKind.DRAW:
        return SuggestedAction(operation_kind="DRAW_FACILITY", facility_id=a.facility_id, amount_fen=a.amount_fen,
                               note=f"draw requested day {a.day}; the router sizes and prices the final plan")
    return SuggestedAction(operation_kind="SUBMIT_INVOICE_FOR_FINANCING", facility_id=a.facility_id,
                           receivable_id=a.receivable_id, amount_fen=a.amount_fen,
                           note="submit today: the invoice is open, buyer-confirmed and not yet due")


def _charges(t: Trajectory) -> int:
    return t.interest_posted_fen + t.fees_posted_fen


def _new_events(t: Trajectory, base: Trajectory, kind: LedgerEventKind, ref: str) -> list[tuple[int, str]]:
    """(day, label) of the events of `kind` on `ref` that the cure adds to the base projection, by day."""
    seen = Counter((e.day, e.kind, e.amount_fen, e.label, e.ref) for p in base.days for e in p.events)
    out: list[tuple[int, str]] = []
    for p in t.days:
        for e in p.events:
            key = (e.day, e.kind, e.amount_fen, e.label, e.ref)
            if e.kind == kind and e.ref == ref:
                if seen[key] > 0:
                    seen[key] -= 1
                else:
                    out.append((e.day, e.label))
    return sorted(out)


def _priced(a: FundingAction, s: SuggestedAction, alone: Trajectory, base: Trajectory,
            mandate: Mandate, facility: Facility | None = None) -> tuple[SuggestedAction, int | None]:
    """`s` with its cost read from the engine: the charges the projection posts with `a` alone minus without it,
    and the days it is out (arrival to the repayment the projection shows). Also the day that cost falls due.
    `above_apr_cap` is not read off that quoted rate: it is the executor's own test, `funding.rates.action_rate`
    (an advance on the days from landing to due, a draw at its tariff) against the mandate's ceiling, so the alert
    and the router agree on whether the cure needs the owner.
    A draw the projection never repays is carried open: it posts no interest, so its cost is not stated (a
    "¥0.00" would be false) and `s` comes back unpriced."""
    cost = _charges(alone) - _charges(base)
    ref = a.facility_id
    days: int | None = None
    end: int | None = None

    def needs_owner(landing: int | None, due: int | None) -> bool:
        if facility is None:
            return False
        rated, how = action_rate(facility, a.kind, amount_fen=a.amount_fen, landing_day=landing, due_day=due)
        return approval_reason(rated, how, mandate) is not None

    if a.kind == FundingActionKind.FINANCE_INVOICE:
        rid = a.receivable_id or ""
        arrive = [d for d, label in _new_events(alone, base, LedgerEventKind.ADVANCE, ref) if rid in label]
        repay = [d for d, label in _new_events(alone, base, LedgerEventKind.REPAYMENT, ref) if rid in label]
    else:
        arrive = [d for d, _ in _new_events(alone, base, LedgerEventKind.DRAW, ref)]
        repay = [d for d, _ in _new_events(alone, base, LedgerEventKind.REPAYMENT, ref)]
        if not repay:  # unpriced, but the executor still tests the draw's tariff against the ceiling
            return s.model_copy(update={"above_apr_cap": needs_owner(None, None)}), None
    if len(arrive) == 1 and len(repay) == 1:  # one lump repayment: a schedule of instalments has no single day
        # counted from the day the cash lands: the same days the executor's rate ceiling is tested on
        days, end = repay[0] - arrive[0], repay[0]
    amount = a.amount_fen
    over_cap = needs_owner(arrive[0] if len(arrive) == 1 else None,
                           end if a.kind == FundingActionKind.FINANCE_INVOICE else None)
    rate: Fraction | None = Fraction(cost, amount) * DAYS_PER_YEAR / days if days is not None and days > 0 else None
    if rate is not None:
        formula = f"{fmt_yuan(cost)} / {fmt_yuan(amount)} × 365/{days} = {fmt_pct(rate, 1)} a year"
    else:
        formula = f"{fmt_yuan(cost)} on {fmt_yuan(amount)}; the projection shows no single repayment day"
    priced = s.model_copy(update={
        "cost_fen": cost, "cost_days": days if rate is not None else None,
        "annual_rate": Ratio.of(rate) if rate is not None else None, "cost_formula": formula,
        "above_apr_cap": over_cap})
    return priced, end


def _cure_costs(state: FinancialState, obs: list[Obligation], t: Trajectory, cure: list[FundingAction],
                mandate: Mandate) -> tuple[list[SuggestedAction], int | None, dict[int, int]]:
    """The cure's suggestions, each priced from the engine, the whole cure's cost (None if it cannot be projected)
    and the day each priced cost falls due. An action that is infeasible alone keeps empty cost fields."""
    base = project(state, obs, [], Mode.CONSERVATIVE, t.horizon_days)
    suggested = [_suggest(a) for a in cure]
    due: dict[int, int] = {}
    for i, a in enumerate(cure):
        try:
            alone = project(state, obs, [a], Mode.CONSERVATIVE, t.horizon_days)
        except EngineError:
            continue
        suggested[i], end = _priced(a, suggested[i], alone, base, mandate,
                                    next((f for f in state.facilities if f.id == a.facility_id), None))
        if end is not None:
            due[i] = end
    try:
        total = _charges(project(state, obs, cure, Mode.CONSERVATIVE, t.horizon_days)) - _charges(base)
    except EngineError:
        total = None
    if any(a.kind == FundingActionKind.DRAW and s.cost_fen is None for a, s in zip(cure, suggested, strict=True)):
        total = None  # an open-ended draw has no stated interest: a total without it would understate the price
    return suggested, total, due


def _cost_words(s: SuggestedAction) -> str:
    if s.cost_fen is None:
        return ""
    if s.annual_rate is None:
        return f", cost {fmt_yuan(s.cost_fen)}"
    return f", cost {fmt_yuan(s.cost_fen)} ({fmt_pct(s.annual_rate.value, 1)} a year for {s.cost_days} days)"


def _reserve_alerts(state: FinancialState, mandate: Mandate, t: Trajectory, obs: list[Obligation],
                    day: int) -> list[Alert]:
    floor = mandate.min_cash_fen
    out: list[Alert] = []
    for start, end in _episodes(t, floor, day):
        run = [p for p in t.days if start <= p.day <= end]
        worst = min(run, key=lambda p: (p.closing_fen, p.day))
        first_short = floor - run[0].closing_fen
        max_short = floor - worst.closing_fen
        cure = (committed_cure(state, obs, t.horizon_days, floor, day, start, end)
                if mandate.allow_new_borrowing else None)
        if cure is not None:
            suggested, cure_total, cure_due = _cure_costs(state, obs, t, cure, mandate)
            cure_text = "a committed cure exists: " + " + ".join(
                f"{s.operation_kind} {s.facility_id} {fmt_yuan(s.amount_fen or 0)}{_cost_words(s)}" for s in suggested)
            cure_inputs = {f"cure_end_day_{i}": str(d) for i, d in cure_due.items()}
            if cure_total is not None:
                cure_inputs["cure_cost"] = fmt_yuan(cure_total)
            if any(s.above_apr_cap for s in suggested):
                cure_inputs["cure_above_apr_cap"] = "true"
                cure_text += (f"; that is above the {fmt_pct(bp(mandate.max_apr_bp))} ceiling for what the agent may "
                              f"borrow alone, so it needs the owner's approval before it runs")
        elif not mandate.allow_new_borrowing:
            cure_inputs = {}
            suggested = []
            cure_text = "the mandate does not allow new borrowing, so no facility can be drawn or applied for"
        else:
            cure_inputs = {}
            usable = [f for f in state.facilities if f.owner_approved and f.status == FacilityStatus.NOT_APPLIED
                      and f.kind in _DRAWABLE and day + f.lead_time_days <= start]
            suggested = [SuggestedAction(operation_kind="APPLY_FOR_FACILITY", facility_id=f.id,
                                         amount_fen=max_short, note="Tier 2: the owner applies; zero until committed")
                         for f in sorted(usable, key=lambda f: f.lead_time_days)[:1]]
            cure_text = "no committed facility can cure it; uncommitted facilities count as zero"
        out.append(Alert(
            id=f"ALERT-RESERVE-{start}",
            kind=AlertKind.RESERVE_BREACH_AHEAD,
            severity=Severity.CRITICAL,
            title=f"Reserve breach ahead on day {start}",
            detail=(f"Projected cash closes at {fmt_yuan(run[0].closing_fen)} on day {start}, "
                    f"{fmt_yuan(first_short)} below the reserve floor; the gap peaks at {fmt_yuan(max_short)} "
                    f"on day {worst.day} and lasts to day {end}. {cure_text[0].upper()}{cure_text[1:]}."),
            formula=(f"shortfall = floor − closing_d: {fmt_yuan(floor)} − {fmt_yuan(run[0].closing_fen)} "
                     f"= {fmt_yuan(first_short)} (day {start}); max over days {start}..{end} = {fmt_yuan(max_short)}"),
            day=start,
            amount_fen=first_short,
            committed_cure=cure is not None,
            inputs={"floor": fmt_yuan(floor), "closing": fmt_yuan(run[0].closing_fen), "last_day": str(end),
                    "worst_day": str(worst.day), "max_shortfall": fmt_yuan(max_short), **cure_inputs},
            suggested=suggested,
            actionable=any(sg.operation_kind in EXECUTABLE_KINDS for sg in suggested),
        ))
    # headroom below 10% of the floor on days that do not breach
    thin = [p for p in t.days if p.day >= day and floor <= p.closing_fen and
            (p.closing_fen - floor) < HEADROOM_SHARE * floor]
    if thin:
        p = min(thin, key=lambda q: (q.closing_fen, q.day))
        head = p.closing_fen - floor
        out.append(Alert(
            id=f"ALERT-HEADROOM-{p.day}",
            kind=AlertKind.RESERVE_HEADROOM_LOW,
            severity=Severity.WARNING,
            title=f"Reserve headroom thin on day {p.day}",
            detail=(f"Cash stays above the floor but only by {fmt_yuan(head)} on day {p.day} "
                    f"({len(thin)} day(s) under 10% of the floor)."),
            formula=f"closing − floor = {fmt_yuan(p.closing_fen)} − {fmt_yuan(floor)} = {fmt_yuan(head)} "
                    f"< 10% × {fmt_yuan(floor)}",
            day=p.day,
            amount_fen=head,
            inputs={"days": ", ".join(str(q.day) for q in thin[:10])},
        ))
    return out


# ---------------------------------------------------------------- covenants


def covenant_limits(state: FinancialState, mandate: Mandate) -> tuple[list[tuple[Fraction, str]], list[tuple[Fraction, str]]]:
    dscr = [(bp(mandate.min_dscr_bp), f"mandate v{mandate.version}")]
    lev = [(bp(mandate.max_leverage_bp), f"mandate v{mandate.version}")]
    for f in state.facilities:
        if not _usable(f):
            continue
        for c in f.covenants:
            if c.threshold_bp is None:
                continue
            if c.kind == CovenantKind.DSCR_MIN:
                dscr.append((bp(c.threshold_bp), c.id))
            elif c.kind == CovenantKind.LEVERAGE_MAX:
                lev.append((bp(c.threshold_bp), c.id))
    return dscr, lev


def _covenant_alerts(state: FinancialState, mandate: Mandate, t: Trajectory, day: int) -> list[Alert]:
    dscr_limits, lev_limits = covenant_limits(state, mandate)
    dscr_limit, dscr_src = max(dscr_limits, key=lambda z: z[0])
    lev_limit, lev_src = min(lev_limits, key=lambda z: z[0])
    ahead = [m for m in t.months if MONTH_DAYS * m.month >= day]
    out: list[Alert] = []

    def emit(kind: str, rows: list[tuple[int, Fraction | None, Fraction]], limit: Fraction, src: str,
             formula: str) -> None:
        if not rows:
            return
        worst = min(rows, key=lambda r: (r[2], r[0]))
        month, value, head = worst
        breach = head < 0
        shown = x(value) if value is not None else "undefined"
        out.append(Alert(
            id=f"ALERT-COVENANT-{kind}-{month}",
            kind=AlertKind.COVENANT_HEADROOM_LOW,
            severity=Severity.CRITICAL if breach else Severity.WARNING,
            title=f"{kind} {'breach' if breach else 'headroom below 0.10×'} in month {month}",
            detail=(f"{kind} {shown} against {src} limit {x(limit)} (headroom {x(head)}); "
                    f"months affected: {', '.join(str(r[0]) for r in rows)}."),
            formula=formula.format(month=month),
            month=month,
            inputs={"limit": x(limit), "source": src, "value": shown, "headroom": x(head)},
            suggested=[SuggestedAction(operation_kind="COUNTER_OFFER",
                                       note="decline or counter terms that add debt service; the verifier prices it")]
            if kind == "DSCR" else [SuggestedAction(operation_kind="REPAY_FACILITY",
                                                    note="reduce drawn balances to restore leverage headroom")],
        ))

    d_rows: list[tuple[int, Fraction | None, Fraction]] = []
    l_rows: list[tuple[int, Fraction | None, Fraction]] = []
    for m in ahead:
        if m.debt_service_fen > 0:
            v = Fraction(m.ebitda_fen, m.debt_service_fen)
            if v - dscr_limit < COVENANT_HEADROOM:
                d_rows.append((m.month, v, v - dscr_limit))
        if m.ebitda_fen > 0:
            lv = Fraction(m.total_debt_fen, 12 * m.ebitda_fen)
            if lev_limit - lv < COVENANT_HEADROOM:
                l_rows.append((m.month, lv, lev_limit - lv))
        elif m.total_debt_fen > 0:
            l_rows.append((m.month, None, Fraction(-1)))
    emit("DSCR", d_rows, dscr_limit, dscr_src, "DSCR_m − min = EBITDA_m / DS_m − min < 0.10 (month {month})")
    emit("Leverage", l_rows, lev_limit, lev_src, "max − Debt_m / (12 × EBITDA_m) < 0.10 (month {month})")
    return out


def _zero_run(t: Trajectory, f: Facility, start: int) -> int:
    balance, best, run = f.drawn_fen, 0, 0
    for p in t.days:
        drew = False
        for ev in p.events:
            if ev.ref != f.id:
                continue
            if ev.kind == LedgerEventKind.DRAW:
                balance += abs(ev.amount_fen)
                drew = True
            elif ev.kind == LedgerEventKind.REPAYMENT:
                balance -= abs(ev.amount_fen)
        if p.day < start:
            continue
        run = run + 1 if balance <= 0 and not drew else 0
        best = max(best, run)
    return best


def _clean_down_alerts(state: FinancialState, t: Trajectory, day: int) -> list[Alert]:
    out: list[Alert] = []
    remaining = t.horizon_days - day + 1
    for f in state.facilities:
        if not (_usable(f) and f.kind == FacilityKind.CREDIT_LINE):
            continue
        for c in f.covenants:
            if c.kind != CovenantKind.CLEAN_DOWN or not c.clean_down_days or remaining < c.clean_down_days:
                continue
            best = _zero_run(t, f, day)
            if best >= c.clean_down_days:
                continue
            out.append(Alert(
                id=f"ALERT-CLEANDOWN-{f.id}",
                kind=AlertKind.CLEAN_DOWN_AT_RISK,
                severity=Severity.WARNING,
                title=f"Clean-down at risk on {f.name}",
                detail=(f"The longest projected run at zero balance is {best} day(s) from day {day}; the covenant "
                        f"needs {c.clean_down_days} consecutive days. Drawn now: {fmt_yuan(f.drawn_fen)}."),
                formula=f"max run of days with balance = 0 = {best} < {c.clean_down_days} ({c.formula})",
                amount_fen=f.drawn_fen,
                inputs={"facility_id": f.id, "covenant_id": c.id, "longest_zero_run": str(best)},
                suggested=[SuggestedAction(operation_kind="REPAY_FACILITY", facility_id=f.id,
                                           amount_fen=f.drawn_fen or None,
                                           note="repay the line (or refinance a permanent need elsewhere)")],
            ))
    return out


# ---------------------------------------------------------------- ledger-based alerts


def _expiring(store: LedgerStore, day: int) -> list[Alert]:
    out: list[Alert] = []
    for c in store.commitments():
        if c.status not in (CommitmentStatus.PROPOSED, CommitmentStatus.ACCEPTED):
            continue
        left = c.expires_day - day
        if not 0 <= left <= EXPIRY_WINDOW_DAYS:
            continue
        kind = "ACCEPT_OFFER" if c.status == CommitmentStatus.PROPOSED else "RECORD_COMMITMENT"
        out.append(Alert(
            id=f"ALERT-EXPIRY-{c.id}",
            kind=AlertKind.COMMITMENT_EXPIRING,
            severity=Severity.WARNING if left <= 2 else Severity.INFO,
            title=f"Commitment {c.id} expires in {left} day(s)",
            detail=f"{c.status.value} commitment on offer {c.offer_id} v{c.offer_version} expires on day "
                   f"{c.expires_day}; after that its nonce is refused (COMMITMENT_EXPIRED).",
            formula=f"expires_day − today = {c.expires_day} − {day} = {left} ≤ {EXPIRY_WINDOW_DAYS}",
            day=c.expires_day,
            amount_fen=c.forward_value_fen,
            inputs={"commitment_id": c.id, "terms_hash": c.terms_hash},
            suggested=[SuggestedAction(operation_kind=kind, commitment_id=c.id, offer_id=c.offer_id,
                                       note="decide before expiry, or let it lapse")],
        ))
    return out


def _books_due_days(books: Books, horizon: int) -> dict[str, int]:
    """Due day of each receivable on current books, read from the engine: the day of its RECEIPT event once
    the live obligations (terms extensions ...) are applied. The books are projected as of day 0 so a receipt
    already past due still appears; only its date is used, never its cash. A receivable without a dated
    receipt (unconfirmed, settled early) is absent and falls back to the invoice's own due day."""
    try:
        t = project(books.state.model_copy(update={"as_of_day": 0}), list(books.obligations), [], Mode.CONSERVATIVE,
                    horizon)
    except EngineError:
        return {}
    return {e.ref: p.day for p in t.days for e in p.events if e.kind == LedgerEventKind.RECEIPT and e.ref}


def _past_due(books: Books, today: int, horizon: int) -> list[Alert]:
    """Receivables OPEN or FINANCED with money outstanding whose due day on current books is before today,
    and the early payments promised under a live commitment that did not arrive."""
    state = books.state
    due_on = _books_due_days(books, horizon)
    out: list[Alert] = []
    for r in state.receivables:
        if r.status not in ("OPEN", "FINANCED") or r.outstanding_fen <= 0:
            continue
        due = due_on.get(r.id, r.due_day)
        if due >= today:
            continue
        late = today - due
        moved = f" (day {r.due_day} on the invoice, moved to day {due} by a live terms extension)" if due != r.due_day else ""
        out.append(Alert(
            id=f"ALERT-PASTDUE-{r.id}",
            kind=AlertKind.RECEIVABLE_PAST_DUE,
            severity=Severity.CRITICAL if r.status == "FINANCED" else Severity.WARNING,
            title=f"Receivable {r.id} is {late} day(s) past due",
            detail=(f"{fmt_yuan(r.outstanding_fen)} outstanding from {r.counterparty_id} was due on day {due}{moved} "
                    f"and is still {r.status}. The conservative trajectory no longer counts on a dated receipt."
                    + (" The financing advance falls due with it." if r.status == "FINANCED" else "")),
            formula=f"today − due_day = {today} − {due} = {late} > 0",
            day=due,
            amount_fen=r.outstanding_fen,
            receivable_id=r.id,
            inputs={"receivable_id": r.id, "counterparty_id": r.counterparty_id, "due_day": str(due),
                    "outstanding": fmt_yuan(r.outstanding_fen)},
            suggested=[SuggestedAction(operation_kind="RECEIVE_PAYMENT", receivable_id=r.id,
                                       amount_fen=r.outstanding_fen,
                                       note="chase the buyer; record the receipt when the money lands")],
        ))
    for lp in books.lapsed:
        if lp.reason != "EARLY_PAYMENT_MISSED":
            continue
        o = lp.obligation
        rid = o.base.receivable_id
        rcv = next((x for x in state.receivables if x.id == rid), None)
        if rcv is None or o.effective_day is None:
            continue
        due = due_on.get(rcv.id, rcv.due_day)
        promised = o.effective_day
        out.append(Alert(
            id=stable_id("ALERT-EARLYPAY", AlertKind.RECEIVABLE_PAST_DUE, f"{lp.commitment_id}|{o.id}|{rcv.id}", promised),
            kind=AlertKind.RECEIVABLE_PAST_DUE,
            severity=Severity.WARNING,
            title=f"Early payment on {rcv.id} did not arrive",
            detail=(f"The early payment promised under commitment {lp.commitment_id} for day {promised} did not "
                    f"arrive. {rcv.id} ({fmt_yuan(rcv.outstanding_fen)} outstanding from {rcv.counterparty_id}) is back "
                    f"on its original due day, day {due}, and the conservative trajectory is projected that way."),
            formula=f"promised day − today = {promised} − {today} < 0 and outstanding = {fmt_yuan(rcv.outstanding_fen)} > 0",
            day=today,
            amount_fen=rcv.outstanding_fen,
            commitment_id=lp.commitment_id,
            receivable_id=rcv.id,
            inputs={"commitment_id": lp.commitment_id, "receivable_id": rcv.id, "counterparty_id": rcv.counterparty_id,
                    "promised_day": str(promised), "due_day": str(due), "obligation_id": o.id},
            suggested=[SuggestedAction(operation_kind="RECEIVE_PAYMENT", receivable_id=rcv.id,
                                       amount_fen=rcv.outstanding_fen, commitment_id=lp.commitment_id,
                                       note="chase the buyer; record the receipt when the money lands")],
        ))
    return out


def _concession_alerts(state: FinancialState, mandate: Mandate, t: Trajectory) -> list[Alert]:
    out: list[Alert] = []
    cap = mandate.max_aggregate_forward_concession_fen
    booked = sum(fc.value_fen for fc in state.forward_concessions)
    total = max([p.forward_concession_fen for p in t.days] + [booked])
    if cap > 0 and total >= CONCESSION_SHARE * cap:
        share = Fraction(total, cap)
        out.append(Alert(
            id="ALERT-CONCESSIONS-AGG",
            kind=AlertKind.CONCESSIONS_NEAR_CAP,
            severity=Severity.CRITICAL if total > cap else Severity.WARNING,
            title=f"Forward concessions at {round_half_up(share * 100)}% of the cap",
            detail=(f"Booked {fmt_yuan(booked)} plus projected contingent concessions at maximum give "
                    f"{fmt_yuan(total)} against the aggregate cap {fmt_yuan(cap)}. Terms extensions are valued "
                    f"separately by the verifier at the marginal cost of funds."),
            formula=f"forward total / cap = {fmt_yuan(total)} / {fmt_yuan(cap)} ≥ 80%",
            amount_fen=total,
            inputs={"booked": fmt_yuan(booked), "cap": fmt_yuan(cap)},
            suggested=[SuggestedAction(operation_kind="COUNTER_OFFER",
                                       note="counter new concessions; the verifier enforces the cap")],
        ))
    per: dict[str, int] = {}
    for fc in state.forward_concessions:
        per[fc.counterparty_id] = per.get(fc.counterparty_id, 0) + fc.value_fen
    for buyer, buyer_cap in sorted(mandate.per_buyer_caps_fen.items()):
        v = per.get(buyer, 0)
        if buyer_cap > 0 and v >= CONCESSION_SHARE * buyer_cap:
            out.append(Alert(
                id=f"ALERT-CONCESSIONS-{buyer}",
                kind=AlertKind.CONCESSIONS_NEAR_CAP,
                severity=Severity.CRITICAL if v > buyer_cap else Severity.WARNING,
                title=f"Concessions to {buyer} at {round_half_up(Fraction(v, buyer_cap) * 100)}% of its cap",
                detail=f"Booked {fmt_yuan(v)} against the per-buyer cap {fmt_yuan(buyer_cap)}.",
                formula=f"{fmt_yuan(v)} / {fmt_yuan(buyer_cap)} ≥ 80%",
                amount_fen=v,
                inputs={"counterparty_id": buyer},
                suggested=[SuggestedAction(operation_kind="COUNTER_OFFER", note="counter further concessions")],
            ))
    return out


# ---------------------------------------------------------------- repayable credit line


def _repay_alerts(state: FinancialState, mandate: Mandate, store: LedgerStore, obs: list[Obligation],
                  day: int) -> list[Alert]:
    """A drawn balance on a COMMITTED, owner-approved bullet credit line that the books can repay today: cash
    after paying the whole balance plus the interest the executor will charge stays at or above the floor on
    every day from today (CONSERVATIVE, the mandate horizon). Interest is the executor's own rule
    (`app.financial.lots.repay`): each lot whose cash has landed, at the facility's rate for the days from its
    landing day to today; a lot that has not landed cannot be repaid yet (ADR-0010 §6) and is left out. The what-if
    state is a copy and is never written back: cash less the landed balance and its interest, those lots repaid."""
    floor = mandate.min_cash_fen
    state = ensure_lots(state)
    out: list[Alert] = []
    for f in state.facilities:
        if not (_usable(f) and f.kind == FacilityKind.CREDIT_LINE and f.repayment == Repayment.BULLET
                and f.drawn_fen > 0):
            continue
        amount = landed(state.lots, f.id)
        if amount <= 0:
            continue
        repaid = repay(state.lots, f, amount, day)
        interest = repaid.interest
        total = amount + interest
        if total > state.cash_fen:
            continue
        what_if = state.model_copy(update={
            "cash_fen": state.cash_fen - total, "lots": repaid.lots,
            "facilities": [g.model_copy(update={"drawn_fen": g.drawn_fen - amount}) if g.id == f.id else g
                           for g in state.facilities]})
        try:
            t = project(what_if, obs, [], Mode.CONSERVATIVE, mandate.horizon_days, floor)
        except EngineError:
            continue
        ahead = [p for p in t.days if p.day >= day]
        if not ahead:
            continue
        low = min(ahead, key=lambda p: (p.closing_fen, p.day))
        if low.closing_fen < floor:
            continue
        clean_down = any(c.kind == CovenantKind.CLEAN_DOWN for c in f.covenants)
        pending = first_unsettled(state.lots, f.id)
        not_landed = (f" A further {fmt_yuan(f.drawn_fen - amount)} requested on day {pending.request_day} lands on "
                      f"day {pending.arrival_day} and can be repaid only after that." if pending is not None else "")
        out.append(Alert(
            id=f"ALERT-REPAY-{f.id}",
            kind=AlertKind.FACILITY_REPAYABLE,
            severity=Severity.WARNING,
            title=f"{f.name} can be repaid",
            detail=(f"{fmt_yuan(amount)} is drawn on {f.name}. Repaying it today costs {fmt_yuan(interest)} "
                    f"interest to date, {fmt_yuan(total)} in all, and cash stays above the floor: the lowest projected "
                    f"close after repaying is {fmt_yuan(low.closing_fen)} on day {low.day}."
                    + (" The line must be at zero for its clean-down." if clean_down else "") + not_landed),
            formula=(f"repay today = balance + interest = {fmt_yuan(amount)} + {fmt_yuan(interest)} = "
                     f"{fmt_yuan(total)}; lowest closing after repaying = {fmt_yuan(low.closing_fen)} (day {low.day}) "
                     f"≥ floor {fmt_yuan(floor)}"),
            day=day,
            amount_fen=amount,
            inputs={"facility_id": f.id, "interest_due": fmt_yuan(interest), "lowest_closing": fmt_yuan(low.closing_fen),
                    "lowest_day": str(low.day), "floor": fmt_yuan(floor)},
            suggested=[SuggestedAction(operation_kind="REPAY_FACILITY", facility_id=f.id, amount_fen=amount,
                                       note=("repay the whole drawn balance today" if pending is None
                                             else "repay the balance that has landed"), cost_fen=interest,
                                       cost_formula=f"{fmt_yuan(interest)} interest to date")],
            actionable=True,
        ))
    return out


# ---------------------------------------------------------------- entry point


def alerts(state: FinancialState, mandate: Mandate, store: LedgerStore, day: int, *,
           obligations: Sequence[Obligation] = ()) -> list[Alert]:
    """All alerts for today, from the conservative trajectory of current books (ADR-0006: the stored state plus
    the live commitments' obligations) and any `obligations` being considered (e.g. a verdict's bound ones).
    Today is `day`, or the day the books are closed to if that is later; no alert refers to an earlier day
    (a past-due alert names the day the receivable was due, which is the point of it)."""
    today = max(day, state.as_of_day)
    books = current_books(state, store.commitments())
    obs = books.with_(obligations)
    t = project(books.state, obs, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    reserve = _reserve_alerts(books.state, mandate, t, obs, today)
    out = [
        *reserve,
        *_covenant_alerts(books.state, mandate, t, today),
        *_clean_down_alerts(books.state, t, today),
        *_expiring(store, today),
        *_past_due(books, today, today + mandate.horizon_days),
        *_concession_alerts(books.state, mandate, t),
        *([] if any(a.kind == AlertKind.RESERVE_BREACH_AHEAD for a in reserve)  # never propose repaying in a breach
          else _repay_alerts(books.state, mandate, store, obs, today)),
    ]
    return sorted(out, key=lambda a: (_RANK[a.severity], a.day if a.day is not None else 10**6, a.id))
