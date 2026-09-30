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

from collections.abc import Sequence
from fractions import Fraction

from app.alerts.ledger import committed_obligations
from app.alerts.models import Alert, AlertKind, Severity, SuggestedAction
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
from app.domain.money import bp, fmt_yuan, round_half_up
from app.domain.ports import LedgerStore
from app.financial import EngineError, project, recurring_receivable_id

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


def _candidates(state: FinancialState, day: int, end: int) -> list[FundingAction]:
    out: list[FundingAction] = []
    for f in state.facilities:
        if _usable(f) and f.kind in _DRAWABLE and f.repayment != Repayment.ON_RECEIPT and f.limit_fen > f.drawn_fen:
            out.append(FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=day,
                                     amount_fen=f.limit_fen - f.drawn_fen))
    invoices: list[tuple[int, str, int]] = []  # (due, id, face)
    for r in state.receivables:
        if r.status == "OPEN" and r.confirmed and r.due_day > day:
            invoices.append((r.due_day, r.id, r.face_fen))
    for ri in state.recurring_invoices:
        d = ri.next_issue_day
        while ri.every_days > 0 and d <= end:
            invoices.append((d + ri.terms_days, recurring_receivable_id(ri.counterparty_id, d), ri.face_fen))
            d += ri.every_days
    invoices.sort()
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
    """A small set of committed funding actions that keeps days start..end at or above the floor."""
    chosen: list[FundingAction] = []
    for a in _candidates(state, day, end):
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
                           note="submit once the invoice is issued and buyer-confirmed")


def _reserve_alerts(state: FinancialState, mandate: Mandate, t: Trajectory, obs: list[Obligation],
                    day: int) -> list[Alert]:
    floor = mandate.min_cash_fen
    out: list[Alert] = []
    for start, end in _episodes(t, floor, day):
        run = [p for p in t.days if start <= p.day <= end]
        worst = min(run, key=lambda p: (p.closing_fen, p.day))
        first_short = floor - run[0].closing_fen
        max_short = floor - worst.closing_fen
        cure = committed_cure(state, obs, t.horizon_days, floor, day, start, end)
        if cure is not None:
            suggested = [_suggest(a) for a in cure]
            cure_text = "a committed cure exists: " + " + ".join(
                f"{s.operation_kind} {s.facility_id} {fmt_yuan(s.amount_fen or 0)}" for s in suggested)
        else:
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
                    "worst_day": str(worst.day), "max_shortfall": fmt_yuan(max_short)},
            suggested=suggested,
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


def _limits(state: FinancialState, mandate: Mandate) -> tuple[list[tuple[Fraction, str]], list[tuple[Fraction, str]]]:
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
    dscr_limits, lev_limits = _limits(state, mandate)
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


def _past_due(state: FinancialState, day: int) -> list[Alert]:
    out: list[Alert] = []
    for r in state.receivables:
        if r.status not in ("OPEN", "FINANCED") or r.due_day >= day:
            continue
        late = day - r.due_day
        out.append(Alert(
            id=f"ALERT-PASTDUE-{r.id}",
            kind=AlertKind.RECEIVABLE_PAST_DUE,
            severity=Severity.CRITICAL if r.status == "FINANCED" else Severity.WARNING,
            title=f"Receivable {r.id} is {late} day(s) past due",
            detail=(f"{fmt_yuan(r.face_fen)} from {r.counterparty_id} was due on day {r.due_day} and is still "
                    f"{r.status}. The conservative trajectory no longer counts on a dated receipt."
                    + (" The financing advance falls due with it." if r.status == "FINANCED" else "")),
            formula=f"today − due_day = {day} − {r.due_day} = {late} > 0",
            day=r.due_day,
            amount_fen=r.face_fen,
            inputs={"receivable_id": r.id, "counterparty_id": r.counterparty_id},
            suggested=[SuggestedAction(operation_kind="RECEIVE_PAYMENT", receivable_id=r.id, amount_fen=r.face_fen,
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


# ---------------------------------------------------------------- entry point


def alerts(state: FinancialState, mandate: Mandate, store: LedgerStore, day: int, *,
           obligations: Sequence[Obligation] = ()) -> list[Alert]:
    """All alerts for `day`, from the conservative trajectory of the verified state plus the live
    commitments' obligations and any `obligations` being considered (e.g. a verdict's bound ones)."""
    obs = committed_obligations(state, store.commitments()) + list(obligations)
    t = project(state, obs, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    out = [
        *_reserve_alerts(state, mandate, t, obs, day),
        *_covenant_alerts(state, mandate, t, day),
        *_clean_down_alerts(state, t, day),
        *_expiring(store, day),
        *_past_due(state, day),
        *_concession_alerts(state, mandate, t),
    ]
    return sorted(out, key=lambda a: (_RANK[a.severity], a.day if a.day is not None else 10**6, a.id))
