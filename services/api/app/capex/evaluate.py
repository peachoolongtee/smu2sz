"""Capex mode: capital budgeting with the financing structure attached (spec v2 §7.7).

Step 1 asks whether the investment is worth doing (NPV at the hurdle, simple payback against the
owner's limit). Step 2 tests each financing structure month by month against the covenants and
selects the cheapest by total interest that holds in every month.

No arithmetic of its own on money paths: payments and schedules come from `app.financial`, ratios
from `app.covenants`, the menu (rates, Tier-3 and APR screens) from `app.funding`, APR and tiers
from `app.mandate`, and the cash + line test runs through `financial.project`. Only the NPV
discounting lives here (appraisal.py), rounded once through `app.domain.money.post`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from app.books import Books, current_books
from app.capex.appraisal import effective_monthly_rate_text, npv_fen, payback_month, uplift_in_month
from app.capex.models import (
    OWNER_ESTIMATE,
    CapexCandidate,
    CapexRequest,
    CapexResult,
    CapexStructure,
    DscrMonth,
    StructureKind,
    Working,
)
from app.config import Settings, get_settings
from app.covenants import line_can_carry_permanent_need, pro_forma, ratios
from app.domain.models import (
    Actor,
    ApplyForFacility,
    CashFlow,
    Commitment,
    CovenantKind,
    DurationKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    FundingAction,
    FundingActionKind,
    Mandate,
    Mode,
    ObligationType,
    Tier,
    Violation,
    ViolationCode,
)
from app.domain.money import DAYS_PER_YEAR, Ratio, bp, fmt_pct, fmt_yuan, post
from app.financial import EngineError, amortisation_schedule, annuity_payment, project
from app.funding import MenuRow, menu_view
from app.mandate import check_apr, tier_for

CASH_LINE_ID = "cash_line"
_USABLE_STATUSES = (FacilityStatus.NOT_APPLIED, FacilityStatus.PENDING, FacilityStatus.COMMITTED)
_TIER3_CODES = (ViolationCode.TIER3_EQUITY, ViolationCode.TIER3_PERSONAL_GUARANTEE, ViolationCode.TIER3_COLLATERAL)


class CapexDisabled(Exception):
    """FEATURE_CAPEX is off. The API maps this to FEATURE_DISABLED; the core is unaffected."""

    code = ViolationCode.FEATURE_DISABLED

    def __init__(self) -> None:
        super().__init__("FEATURE_DISABLED: capex mode is switched off (FEATURE_CAPEX)")


def capex_enabled(settings: Settings | None = None) -> bool:
    return (settings or get_settings()).features.capex


def x(r: Ratio | Fraction | None) -> str:
    """Ratio display, 2 dp half-up: '1.13×'."""
    if r is None:
        return "n/a"
    return (r if isinstance(r, Ratio) else Ratio.of(r)).text + "×"


# ---------------------------------------------------------------- limits and base position


class _Base:
    """The current books every structure is tested against: the stored state plus the live commitments'
    obligations (ADR-0006)."""

    def __init__(self, books: Books, mandate: Mandate) -> None:
        state = books.state
        self.obligations = list(books.obligations)
        self.live_extension_debt = _live_extension_debt(books, mandate)
        self.ebitda = state.monthly_ebitda_fen
        self.debt_service = sum(d.monthly_debt_service_fen for d in state.debts)
        self.debt = sum(d.principal_fen for d in state.debts)
        committed = [f for f in state.facilities if f.status == FacilityStatus.COMMITTED and f.owner_approved]
        # A committed credit line counts at its full limit, as in the verifier's pro-forma test.
        self.lines = [f for f in committed if f.kind == FacilityKind.CREDIT_LINE]
        self.line_limits = sum(f.limit_fen for f in self.lines if f.counts_in_leverage)
        # Debt the pro-forma ratios start from: committed line limits, plus the receivables the live terms
        # extensions tie up, funded permanently (the verifier's pro-forma rule). Zero without such commitments.
        self.base_extra_debt = self.line_limits + self.live_extension_debt
        self.extension_inputs = ({"live_terms_extension_receivables": fmt_yuan(self.live_extension_debt)}
                                 if self.live_extension_debt else {})
        self.extension_term = f" + {fmt_yuan(self.live_extension_debt)}" if self.live_extension_debt else ""
        dscr = [(bp(mandate.min_dscr_bp), f"mandate v{mandate.version}")]
        lev = [(bp(mandate.max_leverage_bp), f"mandate v{mandate.version}")]
        for f in committed:
            d, lv = _covenant_limits(f)
            dscr += d
            lev += lv
        self.dscr_limits = dscr
        self.lev_limits = lev

    def limits_with(self, f: Facility | None) -> tuple[Fraction, str, Fraction, str]:
        """(min DSCR, source, max leverage, source): the strictest of the mandate, every committed
        facility's covenants and the candidate facility's own covenants."""
        dscr, lev = list(self.dscr_limits), list(self.lev_limits)
        if f is not None:
            d, lv = _covenant_limits(f)
            dscr += d
            lev += lv
        d_lim, d_src = max(dscr)
        l_lim, l_src = min(lev)
        return d_lim, d_src, l_lim, l_src


def _covenant_limits(f: Facility) -> tuple[list[tuple[Fraction, str]], list[tuple[Fraction, str]]]:
    dscr, lev = [], []
    for c in f.covenants:
        if c.threshold_bp is None:
            continue
        if c.kind == CovenantKind.DSCR_MIN:
            dscr.append((bp(c.threshold_bp), c.id))
        elif c.kind == CovenantKind.LEVERAGE_MAX:
            lev.append((bp(c.threshold_bp), c.id))
    return dscr, lev


def _live_extension_debt(books: Books, mandate: Mandate) -> int:
    """Receivables tied up by the live lengthening terms extensions, funded permanently: for each, the
    buyer's recurring face × invoices in the horizon × Δdays / 365, rounded once (the verifier's pro-forma
    rule, so capex and the verifier read a live extension the same way)."""
    total = Fraction(0)
    for ob in books.obligations:
        if ob.type != ObligationType.TERMS_EXTENSION or (ob.days_delta or 0) <= 0:
            continue
        recs = [r for r in books.state.recurring_invoices if r.counterparty_id == ob.counterparty_id]
        if len(recs) != 1 or recs[0].every_days <= 0:
            continue
        rec = recs[0]
        n = mandate.forward_concession_horizon_days // rec.every_days
        if ob.duration.kind == DurationKind.RECURRING_BOUNDED and ob.duration.invoices is not None:
            n = min(n, ob.duration.invoices)
        elif ob.duration.kind == DurationKind.ONE_OFF:
            n = 1
        total += Fraction(rec.face_fen * n * (ob.days_delta or 0), DAYS_PER_YEAR)
    return post(total)


def _extension_extra_receivables(request: CapexRequest, state: FinancialState, mandate: Mandate) -> int | None:
    """Extra receivables if the recurring buyer's terms moved to `extension_target_terms_days` and
    were funded permanently: face × (horizon // every_days) × Δdays / 365, rounded once (the
    verifier's pro-forma rule)."""
    if request.extension_target_terms_days is None:
        return None
    recs = [r for r in state.recurring_invoices
            if request.extension_counterparty_id is None or r.counterparty_id == request.extension_counterparty_id]
    if len(recs) != 1 or recs[0].every_days <= 0:
        return None
    rec = recs[0]
    delta = request.extension_target_terms_days - rec.terms_days
    if delta <= 0:
        return None
    n = mandate.forward_concession_horizon_days // rec.every_days
    return post(Fraction(rec.face_fen * n * delta, DAYS_PER_YEAR))


# ---------------------------------------------------------------- financed structures


def _kind(f: Facility) -> StructureKind:
    return "LEASE" if f.kind == FacilityKind.EQUIPMENT_LEASE else "LOAN"


def _structure_id(kind: StructureKind, facility_id: str, term: int, seen: set[str]) -> str:
    sid = f"{kind.lower()}_{term}m"
    if sid in seen:
        sid = f"{facility_id.lower()}_{term}m"
    seen.add(sid)
    return sid


def _menu_violations(f: Facility, row: MenuRow | None, mandate: Mandate) -> list[Violation]:
    """Screens that make a structure inadmissible regardless of the covenants."""
    out: list[Violation] = []
    if not f.owner_approved or f.status not in _USABLE_STATUSES:
        out.append(Violation(
            code=ViolationCode.UNCOMMITTED_FACILITY,
            message=f"{f.name} is {f.status.value}{'' if f.owner_approved else ', not owner-approved'}; "
                    f"it cannot be applied for from capex mode",
            inputs={"facility_id": f.id, "status": f.status.value, "owner_approved": str(f.owner_approved)}))
    if row is not None:
        apr = check_apr(row.all_in_rate, mandate, f.name)
        if apr is not None:
            out.append(apr)
        for code in row.reasons:
            if code in _TIER3_CODES:
                out.append(Violation(code=code, message=f"{f.name} needs a Tier-3 action ({code.value}); never executed",
                                     inputs={"facility_id": f.id}))
    if not mandate.allow_new_borrowing:
        out.append(Violation(code=ViolationCode.NEW_BORROWING_NOT_ALLOWED,
                             message=f"The mandate (v{mandate.version}) does not allow new borrowing",
                             inputs={"mandate_version": str(mandate.version)}))
    return out


def _financed(
    c: CapexCandidate, sid: str, request: CapexRequest, state: FinancialState, mandate: Mandate,
    base: _Base, rows: dict[str, MenuRow],
) -> CapexStructure:
    price = request.price_fen
    f = next((fac for fac in state.facilities if fac.id == c.facility_id), None)
    if f is None:
        return CapexStructure(
            id=sid, label=f"{c.term_months}-month {c.facility_id}", kind="LOAN", facility_id=c.facility_id,
            term_months=c.term_months, rate_bp=None, monthly_payment_fen=None, total_interest_fen=None,
            feasible=False, result="REJECTED",
            violations=[Violation(code=ViolationCode.PRECONDITION_FAILED,
                                  message=f"{c.facility_id} is not on the owner's funding menu",
                                  inputs={"facility_id": c.facility_id})],
            note=f"Rejected: {c.facility_id} is not on the owner's funding menu.")

    kind = _kind(f)
    r_text = fmt_pct(bp(f.rate_bp))
    label = f"{c.term_months}-month {'lease' if kind == 'LEASE' else 'term loan'}, {r_text}"
    violations = _menu_violations(f, rows.get(f.id), mandate)
    if price > f.limit_fen - f.drawn_fen:
        violations.append(Violation(
            code=ViolationCode.PRECONDITION_FAILED,
            message=f"{fmt_yuan(price)} is above the {fmt_yuan(f.limit_fen - f.drawn_fen)} left on {f.name}",
            observed=fmt_yuan(price), limit=fmt_yuan(f.limit_fen - f.drawn_fen),
            formula="principal ≤ limit − drawn",
            inputs={"principal": fmt_yuan(price), "limit": fmt_yuan(f.limit_fen), "drawn": fmt_yuan(f.drawn_fen)}))

    payment = annuity_payment(price, f.rate_bp, c.term_months)
    schedule = amortisation_schedule(price, f.rate_bp, c.term_months)
    total_interest = sum(row.interest for row in schedule)
    d_lim, d_src, l_lim, l_src = base.limits_with(f)
    debt = base.debt + base.base_extra_debt + price

    months: list[DscrMonth] = []
    failing: list[DscrMonth] = []
    for row in schedule:
        ebitda_m = base.ebitda + uplift_in_month(row.month, request.monthly_uplift_fen,
                                                 request.uplift_start_month, request.life_months)
        ds_m = base.debt_service + row.payment
        dscr, _ = ratios(ebitda_m, ds_m, debt)
        passes = dscr is None or dscr.value >= d_lim
        point = DscrMonth(month=row.month, dscr=dscr, passes=passes, ebitda_fen=ebitda_m, debt_service_fen=ds_m)
        months.append(point)
        if not passes:
            failing.append(point)
    _, leverage = pro_forma(state, extra_debt_fen=price, base_extra_debt_fen=base.base_extra_debt)

    if failing:
        first = failing[0]
        uplift = first.ebitda_fen - base.ebitda
        ebitda_expr = fmt_yuan(base.ebitda) + (f" + {fmt_yuan(uplift)}" if uplift else "")
        span = _month_ranges([p.month for p in failing])
        violations.append(Violation(
            code=ViolationCode.DSCR_BREACH,
            message=(f"DSCR is {x(first.dscr)} in month {first.month}, below the {x(d_lim)} minimum "
                     f"(fails in month{'s' if len(failing) > 1 else ''} {span} of {c.term_months})."),
            month=first.month, observed=x(first.dscr), limit=f"≥ {x(d_lim)}",
            formula=(f"(EBITDA_m + uplift_m) / (existing DS_m + payment) = {ebitda_expr} / "
                     f"({fmt_yuan(base.debt_service)} + {fmt_yuan(first.debt_service_fen - base.debt_service)}) "
                     f"= {x(first.dscr)} < {x(d_lim)}"),
            inputs={"EBITDA_m": fmt_yuan(base.ebitda), "uplift_m": fmt_yuan(uplift),
                    "existing_debt_service": fmt_yuan(base.debt_service),
                    "new_payment": fmt_yuan(first.debt_service_fen - base.debt_service),
                    "DS_m": fmt_yuan(first.debt_service_fen), "failing_months": span, "limit_source": d_src}))
    if leverage.value > l_lim:
        violations.append(Violation(
            code=ViolationCode.LEVERAGE_BREACH,
            message=f"Leverage is {x(leverage)} with the {fmt_yuan(price)} principal, above the {x(l_lim)} maximum",
            month=1, observed=x(leverage), limit=f"≤ {x(l_lim)}",
            formula=f"(debt + committed line limits + principal) / (12 × EBITDA_m) = {fmt_yuan(debt)} / "
                    f"(12 × {fmt_yuan(base.ebitda)}) = {x(leverage)} > {x(l_lim)}",
            inputs={"debt": fmt_yuan(base.debt), "committed_line_limits": fmt_yuan(base.line_limits),
                    **base.extension_inputs,
                    "principal": fmt_yuan(price), "EBITDA_m": fmt_yuan(base.ebitda), "limit_source": l_src}))

    dscrs = [p.dscr.value for p in months if p.dscr is not None]
    workings = [
        Working(label="Monthly payment", value=fmt_yuan(payment),
                formula=f"P·r / (1 − (1 + r)^−n), r = {r_text}/12, n = {c.term_months}; rounded half-up once",
                inputs={"P": fmt_yuan(price), "annual_rate": r_text, "n": str(c.term_months)}),
        Working(label="Total interest", value=fmt_yuan(total_interest),
                formula=(f"Σ post(balance × {r_text}/12) over {c.term_months} months; "
                         f"the final payment ({fmt_yuan(schedule[-1].payment)}) clears the balance"),
                inputs={"P": fmt_yuan(price), "payment": fmt_yuan(payment),
                        "final_payment": fmt_yuan(schedule[-1].payment)}),
        Working(label="DSCR by month", value=" / ".join(dict.fromkeys(x(p.dscr) for p in months)),
                formula="(EBITDA_m + uplift_m) / (existing DS_m + payment_m), tested in every month of the term",
                inputs={"EBITDA_m": fmt_yuan(base.ebitda), "existing_debt_service": fmt_yuan(base.debt_service),
                        "uplift_m": f"{fmt_yuan(request.monthly_uplift_fen)} from month {request.uplift_start_month}",
                        "min_dscr": x(d_lim), "limit_source": d_src},
                evidence=OWNER_ESTIMATE),
        Working(label="Leverage", value=x(leverage),
                formula=f"(debt + committed line limits + principal) / (12 × EBITDA_m) = {fmt_yuan(debt)} / "
                        f"(12 × {fmt_yuan(base.ebitda)})",
                inputs={"debt": fmt_yuan(base.debt), "committed_line_limits": fmt_yuan(base.line_limits),
                    **base.extension_inputs,
                        "principal": fmt_yuan(price), "max_leverage": x(l_lim), "limit_source": l_src}),
    ]
    return CapexStructure(
        id=sid, label=label, kind=kind, facility_id=f.id, term_months=c.term_months, rate_bp=f.rate_bp,
        monthly_payment_fen=payment, total_interest_fen=total_interest, feasible=not violations,
        result="ADMISSIBLE" if not violations else "REJECTED", violations=violations, dscr_by_month=months,
        min_dscr=Ratio.of(min(dscrs)) if dscrs else None, leverage=leverage, workings=workings)


def _month_ranges(ms: list[int]) -> str:
    """[1, 2, 3, 7] -> '1–3, 7'."""
    out: list[str] = []
    start = prev = ms[0]
    for m in ms[1:] + [None]:  # type: ignore[list-item]
        if m is not None and m == prev + 1:
            prev = m
            continue
        out.append(str(start) if start == prev else f"{start}–{prev}")
        if m is not None:
            start = prev = m
    return ", ".join(out)


# ---------------------------------------------------------------- cash + credit line


def _cash_line(request: CapexRequest, state: FinancialState, mandate: Mandate, base: _Base) -> CapexStructure:
    """Pay from cash above the reserve plus the committed line, tested on the conservative daily
    trajectory of current books with the purchase posted today (day 0 on a fresh ledger)."""
    price = request.price_fen
    today = state.as_of_day
    lines = [f for f in base.lines if f.limit_fen > f.drawn_fen]
    line_available = sum(f.limit_fen - f.drawn_fen for f in lines)
    cash_above = state.cash_fen - mandate.min_cash_fen
    available = cash_above + line_available
    need_from_line = min(line_available, max(0, price - max(0, cash_above)))

    actions: list[FundingAction] = []
    remaining = need_from_line
    for f in lines:
        amt = min(remaining, f.limit_fen - f.drawn_fen)
        if amt > 0:
            actions.append(FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=today, amount_fen=amt))
            remaining -= amt
    purchase = CashFlow(id="CAPEX-PURCHASE", day=today, amount_fen=-price, kind=FlowKind.OTHER,
                        label=f"Capex purchase: {request.label}")
    inputs = {"cash": fmt_yuan(state.cash_fen), "min_cash": fmt_yuan(mandate.min_cash_fen),
              "line_available": fmt_yuan(line_available), "available_above_reserve": fmt_yuan(available),
              "price": fmt_yuan(price)}
    violations: list[Violation] = []
    try:
        traj = project(state.model_copy(update={"flows": [*state.flows, purchase]}), base.obligations, actions,
                       Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    except EngineError as exc:
        traj = None
        violations.append(Violation(code=ViolationCode.PRECONDITION_FAILED, message=str(exc), inputs=inputs))
    breach_day = None if traj is None else next(
        (p.day for p in traj.days if p.day >= today and p.closing_fen < mandate.min_cash_fen), None)
    if traj is not None and breach_day is not None:
        day = breach_day
        closing = next(p.closing_fen for p in traj.days if p.day == day)
        when = "on purchase day" if day == today else f"on day {day}"
        violations.append(Violation(
            code=ViolationCode.RESERVE_BREACH,
            message=(f"Only {fmt_yuan(available)} is available above the {fmt_yuan(mandate.min_cash_fen)} reserve "
                     f"(cash plus the {fmt_yuan(line_available)} line) for a {fmt_yuan(price)} price; "
                     f"cash falls to {fmt_yuan(closing)} {when}."),
            day=day, observed=fmt_yuan(closing), limit=f"≥ {fmt_yuan(mandate.min_cash_fen)}", curable=False,
            formula=(f"(cash − min_cash) + line_available ≥ price: ({fmt_yuan(state.cash_fen)} − "
                     f"{fmt_yuan(mandate.min_cash_fen)}) + {fmt_yuan(line_available)} = {fmt_yuan(available)} "
                     f"{'<' if available < price else '≥'} {fmt_yuan(price)}; conservative closing cash on day {day} "
                     f"= {fmt_yuan(closing)}"),
            inputs={**inputs, "shortfall": fmt_yuan(max(0, price - available)), "closing_cash": fmt_yuan(closing)}))
    for f in lines:
        if need_from_line > 0 and not line_can_carry_permanent_need(f):
            violations.append(Violation(
                code=ViolationCode.CLEAN_DOWN_BREACH,
                message=f"{f.name} must return to zero for its clean-down period, so it cannot carry a "
                        f"permanent purchase",
                formula="a clean-down line cannot fund a permanent need", inputs={"facility_id": f.id}))
    lowest: list[Working] = []
    if traj is not None:
        low = min((p for p in traj.days if p.day >= today), key=lambda p: (p.closing_fen, p.day))
        lowest.append(Working(
            label="Lowest projected cash", value=fmt_yuan(low.closing_fen),
            formula=f"min over days {today}..{traj.days[-1].day} of the conservative closing cash on current books, "
                    f"with the purchase on day {today}",
            inputs={"day": str(low.day), "min_cash": fmt_yuan(mandate.min_cash_fen),
                    "live_obligations": str(len(base.obligations))}))
    feasible = not violations
    if feasible:
        note = "Feasible: paid from cash above the reserve" + (" and the line." if need_from_line else ".")
    elif any(v.code == ViolationCode.RESERVE_BREACH for v in violations):
        breach = next(v for v in violations if v.code == ViolationCode.RESERVE_BREACH)
        note = (f"Infeasible: only {fmt_yuan(available)} available above the reserve; RESERVE_BREACH "
                f"{'on purchase day' if breach.day == today else f'on day {breach.day}'}.")
    else:
        note = f"Infeasible: {violations[0].message}"
    return CapexStructure(
        id=CASH_LINE_ID, label="Cash + credit line", kind="CASH_LINE", facility_id=None, term_months=None,
        rate_bp=None, monthly_payment_fen=None,
        total_interest_fen=0 if feasible and need_from_line == 0 else None,
        feasible=feasible, result="ADMISSIBLE" if feasible else "INFEASIBLE", violations=violations, note=note,
        workings=[Working(label="Available above the reserve", value=fmt_yuan(available),
                          formula="(cash − min_cash) + committed line available", inputs=inputs),
                  *lowest])


# ---------------------------------------------------------------- entry point


def evaluate_capex(
    request: CapexRequest, state: FinancialState, mandate: Mandate, *, settings: Settings | None = None,
    commitments: Sequence[Commitment] = (),
) -> CapexResult:
    """Step 1: NPV and payback on the owner's estimate. Step 2: each structure month by month;
    select the cheapest by total interest that holds DSCR and leverage in every month. Everything is
    projected on current books: `state` plus the live obligations of `commitments` (ADR-0006).
    Raises CapexDisabled when FEATURE_CAPEX is off."""
    if not capex_enabled(settings):
        raise CapexDisabled()
    base = _Base(current_books(state, commitments), mandate)
    price = request.price_fen

    npv = npv_fen(price, request.monthly_uplift_fen, request.uplift_start_month, request.life_months,
                  request.hurdle_bp)
    payback = payback_month(price, request.monthly_uplift_fen, request.uplift_start_month, request.life_months)
    payback_ok = payback is not None and payback <= request.payback_limit_months
    estimate = (f"Owner's estimate, not observed by the system: +{fmt_yuan(request.monthly_uplift_fen)} a month of "
                f"operating cash flow from month {request.uplift_start_month} through month {request.life_months}.")

    rows = {r.facility_id: r for r in menu_view(state, mandate)}
    structures: list[CapexStructure] = []
    if request.include_cash_line:
        structures.append(_cash_line(request, state, mandate, base))
    seen: set[str] = {CASH_LINE_ID}
    for c in request.candidates:
        f = next((fac for fac in state.facilities if fac.id == c.facility_id), None)
        sid = _structure_id(_kind(f) if f else "LOAN", c.facility_id, c.term_months, seen)
        structures.append(_financed(c, sid, request, state, mandate, base, rows))

    admissible = [s for s in structures if s.feasible and s.total_interest_fen is not None]
    selected = min(admissible, key=lambda s: (s.total_interest_fen, s.term_months or 0, s.id), default=None)
    admissible_ids = {s.id for s in admissible}
    final: list[CapexStructure] = []
    for s in structures:
        if selected is not None and s.id == selected.id:
            s = s.model_copy(update={"result": "SELECTED", "extra_cost_vs_selected_fen": None,
                                     "note": "Selected: the cheapest structure by total interest that holds "
                                             "DSCR and leverage in every month."})
        elif s.id in admissible_ids and selected is not None:
            extra = (s.total_interest_fen or 0) - (selected.total_interest_fen or 0)
            s = s.model_copy(update={
                "extra_cost_vs_selected_fen": extra,
                "note": f"Admissible, but {fmt_yuan(extra)} dearer in total interest than the {selected.label}.",
                "workings": [*s.workings, Working(
                    label="Extra cost vs the selected structure", value=fmt_yuan(extra),
                    formula=f"total interest − selected total interest = {fmt_yuan(s.total_interest_fen or 0)} − "
                            f"{fmt_yuan(selected.total_interest_fen or 0)}",
                    inputs={"selected": selected.id})]})
        elif s.result == "REJECTED" and not s.note:
            v = s.violations[0]
            where = f"@month {v.month}" if v.month is not None else (f"@day {v.day}" if v.day is not None else "")
            detail = f" ({v.observed} < {v.limit.lstrip('≥ ')})" if v.code == ViolationCode.DSCR_BREACH else ""
            s = s.model_copy(update={"note": f"Rejected: {v.code.value}{where}{detail}."})
        final.append(s)

    _, lev_fin = pro_forma(state, extra_debt_fen=price, base_extra_debt_fen=base.base_extra_debt)
    ext = _extension_extra_receivables(request, state, mandate)
    lev_ext = (pro_forma(state, extra_debt_fen=price + ext, base_extra_debt_fen=base.base_extra_debt)[1]
               if ext is not None else None)
    d_lim, _, l_lim, _ = base.limits_with(None)

    sel_fac = selected.facility_id if selected else None
    if sel_fac is not None:
        preview = ApplyForFacility(op_id="capex-tier-preview", idempotency_key="capex-tier-preview",
                                   mandate_version=mandate.version, requested_by=Actor.AGENT, day=state.as_of_day,
                                   facility_id=sel_fac, amount_fen=price)
        tier = tier_for(preview, mandate, state)
    else:
        tier = Tier.TIER_2  # capex spend is the owner's decision even without a new facility

    worth = npv >= 0 and payback_ok
    recommendation = _recommendation(worth, npv, payback, request, final, selected, tier)
    debt_all = base.debt + base.base_extra_debt
    workings = [
        Working(label="NPV at the hurdle", value=fmt_yuan(npv),
                formula=(f"−price + Σ_(m={request.uplift_start_month}..{request.life_months}) uplift / (1 + r_m)^m, "
                         f"r_m = (1 + {fmt_pct(bp(request.hurdle_bp))})^(1/12) − 1 = "
                         f"{effective_monthly_rate_text(request.hurdle_bp)}; 50-digit Decimal, rounded once"),
                inputs={"price": fmt_yuan(price), "uplift": fmt_yuan(request.monthly_uplift_fen),
                        "start_month": str(request.uplift_start_month), "life_months": str(request.life_months),
                        "hurdle": fmt_pct(bp(request.hurdle_bp))},
                evidence=OWNER_ESTIMATE),
        Working(label="Simple payback", value=f"month {payback}" if payback else "not within the life",
                formula=(f"first month m with −price + Σ_(k≤m) uplift_k ≥ 0; limit {request.payback_limit_months} "
                         f"months → {'within' if payback_ok else 'outside'} the limit"),
                inputs={"price": fmt_yuan(price), "uplift": fmt_yuan(request.monthly_uplift_fen),
                        "start_month": str(request.uplift_start_month),
                        "payback_limit_months": str(request.payback_limit_months)},
                evidence=OWNER_ESTIMATE),
        Working(label="Leverage, financed", value=x(lev_fin),
                formula=(f"(debt + committed line limits + principal) / (12 × EBITDA_m) = "
                         f"({fmt_yuan(base.debt)} + {fmt_yuan(base.line_limits)}{base.extension_term} + {fmt_yuan(price)}) / "
                         f"(12 × {fmt_yuan(base.ebitda)})"),
                inputs={"debt": fmt_yuan(base.debt), "committed_line_limits": fmt_yuan(base.line_limits),
                    **base.extension_inputs,
                        "principal": fmt_yuan(price), "EBITDA_m": fmt_yuan(base.ebitda), "max_leverage": x(l_lim)}),
    ]
    if lev_ext is not None and ext is not None:
        workings.append(Working(
            label="Leverage, financed and the terms extension funded", value=x(lev_ext),
            formula=(f"(debt + committed line limits + principal + extra receivables) / (12 × EBITDA_m) = "
                     f"({fmt_yuan(debt_all)} + {fmt_yuan(price)} + {fmt_yuan(ext)}) / (12 × {fmt_yuan(base.ebitda)})"),
            inputs={"extra_receivables": fmt_yuan(ext),
                    "extra_receivables_formula": (f"face × (horizon // every_days) × Δdays / 365, terms → "
                                                  f"{request.extension_target_terms_days} days"),
                    "max_leverage": x(l_lim)}))

    return CapexResult(
        request=request, npv_fen=npv, payback_month=payback, npv_positive=npv >= 0, payback_within_limit=payback_ok,
        worth_doing=worth, estimate_note=estimate, structures=final, selected_id=selected.id if selected else None,
        selected_facility_id=sel_fac, leverage_financed=lev_fin, leverage_with_extension=lev_ext,
        extension_extra_receivables_fen=ext, dscr_limit_bp=_to_bp(d_lim), leverage_limit_bp=_to_bp(l_lim),
        required_tier=tier, recommendation=recommendation, workings=workings,
        mandate_version=mandate.version, state_version=state.state_version)


def _to_bp(r: Fraction) -> int:
    return post(r * 10_000)


def _recommendation(worth: bool, npv: int, payback: int | None, request: CapexRequest,
                    structures: list[CapexStructure], selected: CapexStructure | None, tier: Tier) -> str:
    head = (f"Worth doing on the owner's estimate: NPV {fmt_yuan(npv)} at {fmt_pct(bp(request.hurdle_bp))}, "
            f"payback in month {payback}." if worth else
            f"Not worth doing on the owner's estimate: NPV {fmt_yuan(npv)}, payback "
            f"{f'in month {payback}' if payback else 'not within the life'} against a "
            f"{request.payback_limit_months}-month limit.")
    if selected is None:
        return f"{head} No structure holds every covenant in every month."
    cheaper_rejected = [s for s in structures if s.result == "REJECTED" and s.total_interest_fen is not None
                        and s.total_interest_fen < (selected.total_interest_fen or 0)]
    tail = (f" Finance with the {selected.label}"
            + (f" ({fmt_yuan(selected.monthly_payment_fen)} a month)" if selected.monthly_payment_fen else "") + ".")
    if cheaper_rejected:
        tail += f" The cheaper {cheaper_rejected[0].label} fails a covenant."
    if tier == Tier.TIER_2:
        tail += " A new facility is Tier 2: the agent recommends and the owner applies."
    return head + tail
