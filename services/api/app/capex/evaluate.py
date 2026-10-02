"""Capex mode: capital budgeting with the financing structure attached (spec v2 §7.7).

Step 1 asks whether the investment is worth doing (NPV at the hurdle, simple payback against the
owner's limit). Step 2 tests each financing structure against the covenants month by month and against
the mandate reserve day by day, and, only when the project is worth doing, selects the structure with the
lowest total financing charges (interest + fees, not discounted) that passes both. It is a screen, not an
investment-appraisal engine: see ASSUMPTIONS for what it leaves out.

No arithmetic of its own on money paths: payments and schedules come from `app.financial`, ratios
from `app.covenants`, the menu (rates, Tier-3 and APR screens) from `app.funding`, APR and tiers
from `app.mandate`, and the liquidity test runs through `financial.project` (a DRAW on the candidate
facility plus the purchase). Only the NPV discounting lives here (appraisal.py), rounded once through
`app.domain.money.post`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import NamedTuple

from app.books import Books, current_books
from app.capex.appraisal import effective_monthly_rate_text, npv_fen, payback_month, uplift_in_month
from app.capex.models import (
    CHARGES_BASIS,
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
from app.covenants import line_can_carry_permanent_need, ratios_or_undefined
from app.covenants.ratios import leverage_value
from app.domain.models import (
    Actor,
    ApplyForFacility,
    CashFlow,
    Commitment,
    CovenantKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    FundingAction,
    FundingActionKind,
    Mandate,
    Mode,
    Repayment,
    Tier,
    Violation,
    ViolationCode,
)
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan, post
from app.financial import (
    EngineError,
    amortisation_schedule,
    extension_extra_debt,
    line_interest,
    pro_forma_scale,
    project,
    recurring_issue_days,
    upfront_fee,
    window,
)
from app.financial.debts import service_months_end
from app.financial.trajectory import MONTH_DAYS
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


class _Row(NamedTuple):
    month: int
    payment: int
    interest: int


def _is_term_facility(f: Facility) -> bool:
    """A facility repaid on a schedule over `term_months`: amortising, or a bullet term loan (ADR-0008)."""
    return bool(f.term_months) and (f.repayment == Repayment.AMORTISING
                                    or (f.repayment == Repayment.BULLET and f.kind != FacilityKind.CREDIT_LINE))


def _term_rows(f: Facility, amount: int, term: int) -> list[_Row]:
    """Contractual monthly service on `amount` over `term` months: the annuity for an amortising facility, the
    level (principal + interest) / term for a bullet term loan (ADR-0008; the remainder goes to the last month)."""
    if f.repayment == Repayment.AMORTISING:
        return [_Row(r.month, r.payment, r.interest) for r in amortisation_schedule(amount, f.rate_bp, term)]
    interest = line_interest(amount, f.rate_bp, MONTH_DAYS * term)
    level, rest = divmod(amount + interest, term)
    i_level, i_rest = divmod(interest, term)
    return [_Row(m, level + (rest if m == term else 0), i_level + (i_rest if m == term else 0))
            for m in range(1, term + 1)]


def _carried_service(f: Facility) -> tuple[list[int], int]:
    """(service in months 1..n, service after month n) for the balance already drawn on `f`: scheduled for a term
    facility, interest-only for a revolving line or a facility repaid on receipt."""
    if _is_term_facility(f):
        return [r.payment for r in _term_rows(f, f.drawn_fen, f.term_months or 1)], 0
    return [], post(bp(f.rate_bp) * f.drawn_fen / 12)


# ---------------------------------------------------------------- limits and base position


_DEBT_MONTHS = 600  # how far ahead an existing debt's schedule is read for the ratio months (50 years)


class _Base:
    """The current books every structure is tested against: the stored state plus the live commitments'
    obligations (ADR-0006), with every facility balance already drawn counted in debt and debt service."""

    def __init__(self, books: Books, mandate: Mandate) -> None:
        state = books.state
        self.obligations = list(books.obligations)
        self.live_extension_debt = _live_extension_debt(books, mandate)
        self.ebitda = state.monthly_ebitda_fen
        # Existing debt: its fixed service for the months its schedule (`app.financial.debts`, the cash the projection
        # below already pays) covers, counted from today's month; None: not cleared in the horizon of any structure.
        self._fixed: list[tuple[int, int | None]] = []
        for d in state.debts:
            end = service_months_end(d, state.as_of_day, state.as_of_day + MONTH_DAYS * _DEBT_MONTHS)
            if end is not None:
                end = 0 if d.principal_fen <= 0 else max(1, -(-(end - state.as_of_day) // MONTH_DAYS))
            self._fixed.append((d.monthly_debt_service_fen, end))
        committed = [f for f in state.facilities if f.status == FacilityStatus.COMMITTED and f.owner_approved]
        # A committed credit line counts at its full limit, as in the verifier's pro-forma test (ASSUMPTIONS).
        self.lines = [f for f in committed if f.kind == FacilityKind.CREDIT_LINE]
        counted_lines = {f.id for f in self.lines if f.counts_in_leverage}
        self.line_limits = sum(f.limit_fen for f in self.lines if f.counts_in_leverage)
        # Balances already drawn on any other facility (F-FIN-03): the debt and the contractual monthly service.
        # A drawn balance a DebtPosition already carries is not counted twice.
        covered = {d.facility_id for d in state.debts if d.facility_id}
        self.carried_debt = 0
        self._carried: list[tuple[list[int], int]] = []
        for f in state.facilities:
            if f.drawn_fen <= 0 or f.id in covered:
                continue
            if f.counts_in_leverage and f.id not in counted_lines:
                self.carried_debt += f.drawn_fen
            if f.counts_in_debt_service:
                self._carried.append(_carried_service(f))
        self.debt = sum(d.principal_fen for d in state.debts) + self.carried_debt
        # Current books without the purchase: the daily cash a structure is compared with (see _breach_day).
        self.reserve = mandate.min_cash_fen
        self.today = state.as_of_day
        try:
            traj = project(state, self.obligations, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
            self._baseline = {p.day: p.closing_fen for p in traj.days}
        except EngineError:
            self._baseline = {}
        # Debt the pro-forma ratios start from: committed line limits, plus the receivables the live terms
        # extensions tie up, funded permanently (the verifier's pro-forma rule). Zero without such commitments.
        self.base_extra_debt = self.line_limits + self.live_extension_debt
        self.extension_inputs = ({"live_terms_extension_receivables": fmt_yuan(self.live_extension_debt)}
                                 if self.live_extension_debt else {})
        self.extension_term = f" + {fmt_yuan(self.live_extension_debt)}" if self.live_extension_debt else ""
        self.drawn_inputs = {"drawn_facility_debt": fmt_yuan(self.carried_debt)} if self.carried_debt else {}
        dscr = [(bp(mandate.min_dscr_bp), f"mandate v{mandate.version}")]
        lev = [(bp(mandate.max_leverage_bp), f"mandate v{mandate.version}")]
        for f in committed:
            d, lv = _covenant_limits(f)
            dscr += d
            lev += lv
        self.dscr_limits = dscr
        self.lev_limits = lev

    def baseline_close(self, day: int) -> int | None:
        """Closing cash on `day` on current books without the purchase (the last known day's value beyond the
        baseline horizon, where the books carry no further postings); None if the books cannot be projected."""
        if not self._baseline:
            return None
        return self._baseline.get(day, self._baseline[max(self._baseline)])

    def baseline_low_below_reserve(self) -> tuple[int, int] | None:
        """(day, closing) of the lowest cash on current books without the purchase, if it is below the reserve."""
        days = [(c, d) for d, c in self._baseline.items() if d >= self.today]
        if not days:
            return None
        low, day = min(days)
        return (day, low) if low < self.reserve else None

    def breach_day(self, days: list) -> int | None:
        """First day cash is below the reserve AND lower than the same day on current books without the purchase.
        A sub-reserve day the structure does not make worse is a feature of the books, not of the structure, and
        is reported beside it; a structure that deepens a shortfall (or opens one) is not feasible."""
        for p in days:
            if p.closing_fen < self.reserve:
                before = self.baseline_close(p.day)
                if before is None or p.closing_fen < before:
                    return p.day
        return None

    def books_note(self) -> str:
        low = self.baseline_low_below_reserve()
        if low is None:
            return ""
        return (f" Current books alone already fall to {fmt_yuan(low[1])} on day {low[0]}, below the "
                f"{fmt_yuan(self.reserve)} reserve, before any purchase.")

    def debt_service(self, month: int) -> int:
        """Existing monthly debt service in `month`: the fixed service on state debts plus the contractual
        service on every drawn facility balance still being serviced that month."""
        total = sum(ds for ds, end in self._fixed if end is None or month <= end)
        for payments, tail in self._carried:
            total += payments[month - 1] if month <= len(payments) else tail
        return total

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
    buyer's recurring face × delta ÷ invoice interval, the verifier's pro-forma rule
    (`app.financial.extension_extra_debt`, so capex and the verifier read a live extension the same way).
    ADR-0009: a live extension is an invoice adjustment in the state; a finite one carries its share of the
    steady state (`pro_forma_scale`): the invoices still in its scope over the invoices of the window."""
    state = books.state
    lo, hi = window(state, mandate.forward_concession_horizon_days)
    total = Fraction(0)
    for adj in state.invoice_adjustments:
        if adj.days_delta <= 0:
            continue
        recs = [r for r in state.recurring_invoices if r.counterparty_id == adj.counterparty_id]
        if len(recs) != 1 or recs[0].every_days <= 0:
            continue
        rec = recs[0]
        in_window = len(recurring_issue_days(rec, lo, hi))
        if adj.receivable_ids is not None:
            scale = pro_forma_scale(len(adj.receivable_ids), in_window, perpetual=False)
        elif adj.until_issue_day is not None:
            first = max(lo, adj.from_issue_day or 0)
            scoped = len(recurring_issue_days(rec, first, min(hi, adj.until_issue_day + 1)))
            scale = pro_forma_scale(scoped, in_window, perpetual=False)
        else:
            scale = Fraction(1)
        total += extension_extra_debt(rec.face_fen, adj.days_delta, rec.every_days, scale)
    return post(total)


def _extension_extra_receivables(request: CapexRequest, state: FinancialState, mandate: Mandate) -> int | None:
    """Extra receivables if the recurring buyer's terms moved to `extension_target_terms_days` and
    were funded permanently: face × delta ÷ invoice interval, rounded once (the verifier's pro-forma rule,
    `app.financial.extension_extra_debt`)."""
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
    return post(extension_extra_debt(rec.face_fen, delta, rec.every_days))


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


def _no_ratio_violation(base: _Base) -> Violation:
    """Monthly EBITDA <= 0: DSCR and leverage have no basis, so a debt-financed structure cannot pass."""
    return Violation(
        code=ViolationCode.PRECONDITION_FAILED,
        message=(f"Monthly EBITDA is {fmt_yuan(base.ebitda)}, so DSCR and leverage are undefined and debt "
                 f"financing cannot be tested against the covenants; it is treated as infeasible."),
        observed=fmt_yuan(base.ebitda), limit="> ¥0.00", curable=False,
        formula="DSCR = EBITDA_m / debt service and leverage = debt / (12 × EBITDA_m) need EBITDA_m > 0",
        inputs={"EBITDA_m": fmt_yuan(base.ebitda), "debt": fmt_yuan(base.debt + base.base_extra_debt)})


def _liquidity(
    f: Facility, term: int, fee: int, request: CapexRequest, state: FinancialState, mandate: Mandate, base: _Base,
) -> tuple[list[Violation], list[Working]]:
    """The daily cash test of a financed structure, on current books (the engine, not a second model): the
    purchase goes out on the day the proceeds land (request day + the facility's lead time), the proceeds and
    the upfront fee post, and every scheduled payment follows. Cash must stay at or above the mandate reserve.
    The facility is projected as if granted (COMMITTED): capex asks what happens if the owner gets it. The
    owner's uplift is deliberately not counted as cash here."""
    price = request.price_fen
    today = state.as_of_day
    land = today + f.lead_time_days
    granted = f.model_copy(update={"status": FacilityStatus.COMMITTED, "owner_approved": True, "term_months": term})
    purchase = CashFlow(id="CAPEX-PURCHASE", day=land, amount_fen=-price, kind=FlowKind.OTHER,
                        label=f"Capex purchase: {request.label}")
    draw = FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=today, amount_fen=price)
    scenario = state.model_copy(update={"flows": [*state.flows, purchase],
                                        "facilities": [granted if x.id == f.id else x for x in state.facilities]})
    try:
        traj = project(scenario, base.obligations, [draw], Mode.CONSERVATIVE, mandate.horizon_days,
                       mandate.min_cash_fen)
    except EngineError as exc:
        return [Violation(code=ViolationCode.PRECONDITION_FAILED,
                          message=f"Cash cannot be projected with {f.name}: {exc}",
                          inputs={"facility_id": f.id})], []
    days = [p for p in traj.days if p.day >= today]
    low = min(days, key=lambda p: (p.closing_fen, p.day))
    inputs = {"price": fmt_yuan(price), "proceeds": fmt_yuan(price), "upfront_fee": fmt_yuan(fee),
              "purchase_day": str(land), "min_cash": fmt_yuan(mandate.min_cash_fen),
              "live_obligations": str(len(base.obligations))}
    working = Working(
        label="Lowest projected cash", value=fmt_yuan(low.closing_fen),
        formula=(f"min over days {today}..{days[-1].day} of the conservative closing cash on current books with the "
                 f"{fmt_yuan(price)} purchase on day {land}, the {fmt_yuan(price)} proceeds and {fmt_yuan(fee)} "
                 f"upfront fee, and the scheduled payments (the owner's uplift is not counted as cash)"),
        inputs={**inputs, "day": str(low.day)})
    breach_day = base.breach_day(days)
    if breach_day is None:
        return [], [working]
    closing = next(p.closing_fen for p in days if p.day == breach_day)
    before = base.baseline_close(breach_day)
    return [Violation(
        code=ViolationCode.RESERVE_BREACH,
        message=(f"Cash falls to {fmt_yuan(closing)} on day {breach_day}, below the "
                 f"{fmt_yuan(mandate.min_cash_fen)} reserve, once the {fmt_yuan(price)} purchase, the loan "
                 f"proceeds, the {fmt_yuan(fee)} upfront fee and the scheduled payments are counted."
                 f"{base.books_note()}"),
        day=breach_day, observed=fmt_yuan(closing), limit=f"≥ {fmt_yuan(mandate.min_cash_fen)}",
        curable=False,
        formula=(f"conservative closing cash on day {breach_day} on current books with the purchase, proceeds, "
                 f"fee and payments = {fmt_yuan(closing)} < {fmt_yuan(mandate.min_cash_fen)}"
                 + (f" and < {fmt_yuan(before)} without them" if before is not None else "")),
        inputs={**inputs, "closing_cash": fmt_yuan(closing),
                **({"closing_cash_without_purchase": fmt_yuan(before)} if before is not None else {})})], [working]


def _financed(
    c: CapexCandidate, sid: str, request: CapexRequest, state: FinancialState, mandate: Mandate,
    base: _Base, rows: dict[str, MenuRow],
) -> CapexStructure:
    price = request.price_fen
    f = next((fac for fac in state.facilities if fac.id == c.facility_id), None)
    if f is None or not _is_term_facility(f):
        why = (f"{c.facility_id} is not on the owner's funding menu" if f is None
               else f"{f.name} is not a term facility (it has no scheduled term repayment)")
        return CapexStructure(
            id=sid, label=f"{c.term_months}-month {c.facility_id}", kind="LOAN" if f is None else _kind(f),
            facility_id=c.facility_id, term_months=c.term_months, rate_bp=None if f is None else f.rate_bp,
            monthly_payment_fen=None, total_interest_fen=None, feasible=False, result="REJECTED",
            violations=[Violation(code=ViolationCode.PRECONDITION_FAILED, message=why,
                                  inputs={"facility_id": c.facility_id})],
            note=f"Rejected: {why}.")

    kind = _kind(f)
    hypothetical = c.term_months != f.term_months
    r_text = fmt_pct(bp(f.rate_bp))
    label = f"{c.term_months}-month {'lease' if kind == 'LEASE' else 'term loan'}, {r_text}"
    violations = _menu_violations(f, rows.get(f.id), mandate)
    room = f.limit_fen - f.drawn_fen
    over_limit = price > room
    if over_limit:
        violations.append(Violation(
            code=ViolationCode.PRECONDITION_FAILED,
            message=f"{fmt_yuan(price)} is above the {fmt_yuan(room)} left on {f.name}",
            observed=fmt_yuan(price), limit=fmt_yuan(room),
            formula="principal ≤ limit − drawn",
            inputs={"principal": fmt_yuan(price), "limit": fmt_yuan(f.limit_fen), "drawn": fmt_yuan(f.drawn_fen)}))

    schedule = _term_rows(f, price, c.term_months)
    payment = schedule[0].payment
    total_interest = sum(row.interest for row in schedule)
    fee = upfront_fee(f, price)
    charges = total_interest + fee
    d_lim, d_src, l_lim, l_src = base.limits_with(f)
    debt = base.debt + base.base_extra_debt + price

    months: list[DscrMonth] = []
    failing: list[DscrMonth] = []
    leverage_exact = leverage_value(debt, base.ebitda)
    leverage = Ratio.of(leverage_exact) if leverage_exact is not None else None
    if base.ebitda <= 0:
        violations.append(_no_ratio_violation(base))
    else:
        for row in schedule:
            ebitda_m = base.ebitda + uplift_in_month(row.month, request.monthly_uplift_fen,
                                                     request.uplift_start_month, request.life_months)
            ds_m = base.debt_service(row.month) + row.payment
            dscr, _ = ratios_or_undefined(ebitda_m, ds_m, debt)
            passes = dscr is None or dscr.value >= d_lim
            point = DscrMonth(month=row.month, dscr=dscr, passes=passes, ebitda_fen=ebitda_m, debt_service_fen=ds_m)
            months.append(point)
            if not passes:
                failing.append(point)

    if failing:
        first = failing[0]
        uplift = first.ebitda_fen - base.ebitda
        existing = base.debt_service(first.month)
        ebitda_expr = fmt_yuan(base.ebitda) + (f" + {fmt_yuan(uplift)}" if uplift else "")
        span = _month_ranges([p.month for p in failing])
        violations.append(Violation(
            code=ViolationCode.DSCR_BREACH,
            message=(f"DSCR is {x(first.dscr)} in month {first.month}, below the {x(d_lim)} minimum "
                     f"(fails in month{'s' if len(failing) > 1 else ''} {span} of {c.term_months})."),
            month=first.month, observed=x(first.dscr), limit=f"≥ {x(d_lim)}",
            formula=(f"(EBITDA_m + uplift_m) / (existing DS_m + payment) = {ebitda_expr} / "
                     f"({fmt_yuan(existing)} + {fmt_yuan(first.debt_service_fen - existing)}) "
                     f"= {x(first.dscr)} < {x(d_lim)}"),
            inputs={"EBITDA_m": fmt_yuan(base.ebitda), "uplift_m": fmt_yuan(uplift),
                    "existing_debt_service": fmt_yuan(existing),
                    "new_payment": fmt_yuan(first.debt_service_fen - existing),
                    "DS_m": fmt_yuan(first.debt_service_fen), "failing_months": span, "limit_source": d_src}))
    if leverage is not None and leverage.value > l_lim:
        violations.append(Violation(
            code=ViolationCode.LEVERAGE_BREACH,
            message=f"Leverage is {x(leverage)} with the {fmt_yuan(price)} principal, above the {x(l_lim)} maximum",
            month=1, observed=x(leverage), limit=f"≤ {x(l_lim)}",
            formula=f"(debt incl. drawn facilities + committed line limits + principal) / (12 × EBITDA_m) = "
                    f"{fmt_yuan(debt)} / (12 × {fmt_yuan(base.ebitda)}) = {x(leverage)} > {x(l_lim)}",
            inputs={"debt": fmt_yuan(base.debt), "committed_line_limits": fmt_yuan(base.line_limits),
                    **base.drawn_inputs, **base.extension_inputs,
                    "principal": fmt_yuan(price), "EBITDA_m": fmt_yuan(base.ebitda), "limit_source": l_src}))

    low_cash: list[Working] = []
    if not over_limit:
        liq, low_cash = _liquidity(f, c.term_months, fee, request, state, mandate, base)
        violations.extend(liq)

    dscrs = [p.dscr.value for p in months if p.dscr is not None]
    pay_formula = (f"P·r / (1 − (1 + r)^−n), r = {r_text}/12 (nominal annual rate ÷ 12), n = {c.term_months}; "
                   f"rounded half-up once" if f.repayment == Repayment.AMORTISING else
                   f"(P + simple interest {r_text} × {MONTH_DAYS * c.term_months} days / 365) / n, n = {c.term_months} "
                   f"(ADR-0008 level service)")
    workings = [
        Working(label="Monthly payment", value=fmt_yuan(payment), formula=pay_formula,
                inputs={"P": fmt_yuan(price), "nominal_annual_rate": r_text, "n": str(c.term_months)}),
        Working(label="Total interest", value=fmt_yuan(total_interest),
                formula=(f"Σ interest over {c.term_months} months at {r_text} nominal annual; "
                         f"the final payment ({fmt_yuan(schedule[-1].payment)}) clears the balance"),
                inputs={"P": fmt_yuan(price), "payment": fmt_yuan(payment),
                        "final_payment": fmt_yuan(schedule[-1].payment)}),
        Working(label="Upfront fee", value=fmt_yuan(fee),
                formula=f"principal × upfront fee = {fmt_yuan(price)} × {fmt_pct(bp(f.upfront_fee_bp))}, rounded once",
                inputs={"P": fmt_yuan(price), "upfront_fee": fmt_pct(bp(f.upfront_fee_bp))}),
        Working(label="Total financing charges", value=fmt_yuan(charges),
                formula=f"total interest + upfront fee = {fmt_yuan(total_interest)} + {fmt_yuan(fee)}; "
                        f"not discounted, the quantity structures are ranked on",
                inputs={"interest": fmt_yuan(total_interest), "upfront_fee": fmt_yuan(fee)}),
    ]
    if base.ebitda > 0:
        workings.append(Working(
            label="DSCR by month", value=" / ".join(dict.fromkeys(x(p.dscr) for p in months)),
            formula=("(EBITDA_m + uplift_m) / (existing DS_m + payment_m), tested in every month of the term; "
                     "existing DS_m includes the contractual service on every balance already drawn"),
            inputs={"EBITDA_m": fmt_yuan(base.ebitda), "existing_debt_service_month_1": fmt_yuan(base.debt_service(1)),
                    "uplift_m": f"{fmt_yuan(request.monthly_uplift_fen)} from month {request.uplift_start_month}",
                    "min_dscr": x(d_lim), "limit_source": d_src},
            evidence=OWNER_ESTIMATE))
    workings.append(Working(
        label="Leverage", value=x(leverage),
        formula=f"(debt incl. drawn facilities + committed line limits + principal) / (12 × EBITDA_m) = "
                f"{fmt_yuan(debt)} / (12 × {fmt_yuan(base.ebitda)})",
        inputs={"debt": fmt_yuan(base.debt), "committed_line_limits": fmt_yuan(base.line_limits),
                **base.drawn_inputs, **base.extension_inputs,
                "principal": fmt_yuan(price), "max_leverage": x(l_lim), "limit_source": l_src}))
    workings.extend(low_cash)
    return CapexStructure(
        id=sid, label=label, kind=kind, facility_id=f.id, term_months=c.term_months, rate_bp=f.rate_bp,
        monthly_payment_fen=payment, total_interest_fen=total_interest, upfront_fee_fen=fee,
        charges_total_fen=charges, hypothetical=hypothetical, feasible=not violations,
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


def _line_authority_violations(
    used: list[tuple[Facility, int]], request: CapexRequest, mandate: Mandate, base: _Base, rows: dict[str, MenuRow],
) -> list[Violation]:
    """The checks any plan that draws on a line must pass (F-FIN-05): new borrowing allowed, the line's all-in
    rate within the APR cap, and DSCR and leverage inside the covenants with the draw's interest in the service."""
    out: list[Violation] = []
    if not mandate.allow_new_borrowing:
        out.append(Violation(code=ViolationCode.NEW_BORROWING_NOT_ALLOWED,
                             message=f"The mandate (v{mandate.version}) does not allow new borrowing, so the "
                                     f"purchase cannot be paid from a credit line",
                             inputs={"mandate_version": str(mandate.version)}))
    for f, _ in used:
        row = rows.get(f.id)
        apr = check_apr(row.all_in_rate, mandate, f.name) if row is not None else None
        if apr is not None:
            out.append(apr)
    if base.ebitda <= 0:
        out.append(_no_ratio_violation(base))
        return out
    d_lim, d_src, l_lim, l_src = base.limits_with(None)
    new_interest = sum(post(bp(f.rate_bp) * amt / 12) for f, amt in used)
    ebitda_1 = base.ebitda + uplift_in_month(1, request.monthly_uplift_fen, request.uplift_start_month,
                                             request.life_months)
    ds_1 = base.debt_service(1) + new_interest
    debt = base.debt + base.base_extra_debt
    dscr, lev = ratios_or_undefined(ebitda_1, ds_1, debt)
    if dscr is not None and dscr.value < d_lim:
        out.append(Violation(
            code=ViolationCode.DSCR_BREACH,
            message=f"DSCR is {x(dscr)} with the line drawn (interest only), below the {x(d_lim)} minimum",
            month=1, observed=x(dscr), limit=f"≥ {x(d_lim)}",
            formula=(f"EBITDA_m / (existing DS_m + line interest) = {fmt_yuan(ebitda_1)} / "
                     f"({fmt_yuan(base.debt_service(1))} + {fmt_yuan(new_interest)}) = {x(dscr)} < {x(d_lim)}"),
            inputs={"EBITDA_m": fmt_yuan(ebitda_1), "existing_debt_service": fmt_yuan(base.debt_service(1)),
                    "line_interest": fmt_yuan(new_interest), "limit_source": d_src}))
    if lev is not None and lev.value > l_lim:
        out.append(Violation(
            code=ViolationCode.LEVERAGE_BREACH,
            message=f"Leverage is {x(lev)} with the committed lines counted at their limits, above the "
                    f"{x(l_lim)} maximum",
            month=1, observed=x(lev), limit=f"≤ {x(l_lim)}",
            formula=(f"(debt incl. drawn facilities + committed line limits) / (12 × EBITDA_m) = {fmt_yuan(debt)} / "
                     f"(12 × {fmt_yuan(base.ebitda)}) = {x(lev)} > {x(l_lim)}"),
            inputs={"debt": fmt_yuan(base.debt), "committed_line_limits": fmt_yuan(base.line_limits),
                    **base.drawn_inputs, **base.extension_inputs, "EBITDA_m": fmt_yuan(base.ebitda),
                    "limit_source": l_src}))
    return out


def _cash_line(
    request: CapexRequest, state: FinancialState, mandate: Mandate, base: _Base, rows: dict[str, MenuRow],
) -> CapexStructure:
    """Pay from cash above the reserve plus the committed line, tested on the conservative daily
    trajectory of current books with the purchase posted today (day 0 on a fresh ledger). When the line is
    drawn it must also pass the authority checks every plan passes (borrowing allowed, APR cap, covenants)."""
    price = request.price_fen
    today = state.as_of_day
    lines = [f for f in base.lines if f.limit_fen > f.drawn_fen]
    line_available = sum(f.limit_fen - f.drawn_fen for f in lines)
    cash_above = state.cash_fen - mandate.min_cash_fen
    available = cash_above + line_available
    need_from_line = min(line_available, max(0, price - max(0, cash_above)))

    actions: list[FundingAction] = []
    used: list[tuple[Facility, int]] = []
    remaining = need_from_line
    for f in lines:
        amt = min(remaining, f.limit_fen - f.drawn_fen)
        if amt > 0:
            actions.append(FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=today, amount_fen=amt))
            used.append((f, amt))
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
    breach_day = None if traj is None else base.breach_day([p for p in traj.days if p.day >= today])
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
    if used:
        violations.extend(_line_authority_violations(used, request, mandate, base, rows))
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
    cash_only = 0 if feasible and need_from_line == 0 else None
    return CapexStructure(
        id=CASH_LINE_ID, label="Cash + credit line", kind="CASH_LINE", facility_id=None, term_months=None,
        rate_bp=None, monthly_payment_fen=None, total_interest_fen=cash_only, charges_total_fen=cash_only,
        feasible=feasible, result="ADMISSIBLE" if feasible else "INFEASIBLE", violations=violations, note=note,
        workings=[Working(label="Available above the reserve", value=fmt_yuan(available),
                          formula="(cash − min_cash) + committed line available", inputs=inputs),
                  *lowest])


# ---------------------------------------------------------------- entry point


ASSUMPTIONS: tuple[str, ...] = (
    (f"Structures are ranked on {CHARGES_BASIS}. Residual value, tax, discounting of financing flows and "
     f"per-period fees are not modelled; this is a screen, not an investment appraisal."),
    ("A structure is evaluated only at its facility's actual term. Any other term is a hypothetical illustration: "
     "it is never selected and never applied for."),
    ("Liquidity is tested day by day on current books: the purchase is paid on the day the loan proceeds land "
     "(request day + the facility's lead time), and the proceeds, the upfront fee and every scheduled payment post. "
     "A day below the reserve fails a structure when the structure makes that day's cash lower than the same day "
     "on current books without the purchase; a shortfall the books already have is reported beside it, not "
     "blamed on the structure. The owner's uplift is not counted as cash in that test."),
    ("Debt and monthly debt service include every balance already drawn on a facility that counts in leverage / "
     "debt service: an amortising facility at its annuity payment over its term, a bullet term loan at (principal + "
     "interest) / term (ADR-0008), a revolving line interest-only. A committed credit line counts at its full "
     "limit in leverage, as the verifier's pro-forma test does. The upfront fee is a cash cost, not debt service."),
    ("Rates are nominal annual rates divided by 12 for monthly schedules, leases included; they are not "
     "effective annual rates."),
    ("The uplift is the owner's estimate and is treated as EBITDA in the DSCR test and as cash in NPV and payback; "
     "the system has not observed it."),
)


def evaluate_capex(
    request: CapexRequest, state: FinancialState, mandate: Mandate, *, settings: Settings | None = None,
    commitments: Sequence[Commitment] = (),
) -> CapexResult:
    """Step 1: NPV and payback on the owner's estimate. Step 2: each structure tested month by month
    (DSCR, leverage) and day by day (cash against the reserve). Only when the project is worth doing, select
    the structure with the lowest total financing charges (interest + fees, not discounted) that passes both
    and is offered at its facility's real term. Everything is projected on current books: `state` plus the live
    obligations of `commitments` (ADR-0006). Raises CapexDisabled when FEATURE_CAPEX is off."""
    if not capex_enabled(settings):
        raise CapexDisabled()
    base = _Base(current_books(state, commitments), mandate)
    price = request.price_fen

    npv = npv_fen(price, request.monthly_uplift_fen, request.uplift_start_month, request.life_months,
                  request.hurdle_bp)
    payback = payback_month(price, request.monthly_uplift_fen, request.uplift_start_month, request.life_months)
    payback_ok = payback is not None and payback <= request.payback_limit_months
    worth = npv >= 0 and payback_ok
    estimate = (f"Owner's estimate, not observed by the system: +{fmt_yuan(request.monthly_uplift_fen)} a month of "
                f"operating cash flow from month {request.uplift_start_month} through month {request.life_months}.")

    rows = {r.facility_id: r for r in menu_view(state, mandate)}
    structures: list[CapexStructure] = []
    if request.include_cash_line:
        structures.append(_cash_line(request, state, mandate, base, rows))
    seen: set[str] = {CASH_LINE_ID}
    for c in request.candidates:
        f = next((fac for fac in state.facilities if fac.id == c.facility_id), None)
        sid = _structure_id(_kind(f) if f else "LOAN", c.facility_id, c.term_months, seen)
        structures.append(_financed(c, sid, request, state, mandate, base, rows))

    # No winner unless the project is worth doing; an illustration at another term is never a winner.
    admissible = [s for s in structures if s.feasible and s.charges_total_fen is not None]
    eligible = [s for s in admissible if not s.hypothetical]
    selected = (min(eligible, key=lambda s: (s.charges_total_fen or 0, s.term_months or 0, s.id), default=None)
                if worth else None)
    admissible_ids = {s.id for s in admissible}
    final: list[CapexStructure] = []
    for s in structures:
        illus = (f"Illustration at {s.term_months} months, not the facility's actual term; never selected or "
                 f"applied for. ") if s.hypothetical else ""
        if selected is not None and s.id == selected.id:
            s = s.model_copy(update={"result": "SELECTED", "extra_cost_vs_selected_fen": None,
                                     "note": f"Selected: {CHARGES_BASIS} among the structures that hold DSCR and "
                                             f"leverage in every month and do not push daily cash below the reserve."})
        elif s.id in admissible_ids and selected is not None:
            extra = (s.charges_total_fen or 0) - (selected.charges_total_fen or 0)
            s = s.model_copy(update={
                "extra_cost_vs_selected_fen": extra,
                "note": f"{illus}Admissible, but {fmt_yuan(extra)} more in total financing charges (interest + "
                        f"fees) than the {selected.label}.",
                "workings": [*s.workings, Working(
                    label="Extra cost vs the selected structure", value=fmt_yuan(extra),
                    formula=f"total financing charges − selected total financing charges = "
                            f"{fmt_yuan(s.charges_total_fen or 0)} − {fmt_yuan(selected.charges_total_fen or 0)}",
                    inputs={"selected": selected.id})]})
        elif s.id in admissible_ids:
            s = s.model_copy(update={"note": f"{illus}Passes the covenant and cash tests; no structure is selected "
                                             f"because the project is not worth doing on the owner's estimate."
                                     if not worth else f"{illus}Passes the covenant and cash tests."})
        elif s.result == "REJECTED" and not s.note:
            v = s.violations[0]
            where = f"@month {v.month}" if v.month is not None else (f"@day {v.day}" if v.day is not None else "")
            detail = f" ({v.observed} < {v.limit.lstrip('≥ ')})" if v.code == ViolationCode.DSCR_BREACH else ""
            s = s.model_copy(update={"note": f"{illus}Rejected: {v.code.value}{where}{detail}."})
        final.append(s)

    d_lim, _, l_lim, _ = base.limits_with(None)
    debt_fin = base.debt + base.base_extra_debt + price
    lev_fin_v = leverage_value(debt_fin, base.ebitda)
    lev_fin = Ratio.of(lev_fin_v) if lev_fin_v is not None else None
    ext = _extension_extra_receivables(request, state, mandate)
    lev_ext_v = leverage_value(debt_fin + ext, base.ebitda) if ext is not None else None
    lev_ext = Ratio.of(lev_ext_v) if lev_ext_v is not None else None

    sel_fac = selected.facility_id if selected else None
    if sel_fac is not None:
        preview = ApplyForFacility(op_id="capex-tier-preview", idempotency_key="capex-tier-preview",
                                   mandate_version=mandate.version, requested_by=Actor.AGENT, day=state.as_of_day,
                                   facility_id=sel_fac, amount_fen=price)
        tier = tier_for(preview, mandate, state)
    else:
        tier = Tier.TIER_2  # capex spend is the owner's decision even without a new facility

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
                formula=(f"(debt incl. drawn facilities + committed line limits + principal) / (12 × EBITDA_m) = "
                         f"({fmt_yuan(base.debt)} + {fmt_yuan(base.line_limits)}{base.extension_term} + "
                         f"{fmt_yuan(price)}) / (12 × {fmt_yuan(base.ebitda)})"),
                inputs={"debt": fmt_yuan(base.debt), "committed_line_limits": fmt_yuan(base.line_limits),
                        **base.drawn_inputs, **base.extension_inputs,
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
        required_tier=tier, recommendation=recommendation, workings=workings, assumptions=list(ASSUMPTIONS),
        as_of_day=state.as_of_day, mandate_version=mandate.version, state_version=state.state_version)


def _to_bp(r: Fraction) -> int:
    return post(r * 10_000)


def _recommendation(worth: bool, npv: int, payback: int | None, request: CapexRequest,
                    structures: list[CapexStructure], selected: CapexStructure | None, tier: Tier) -> str:
    head = (f"Worth doing on the owner's estimate: NPV {fmt_yuan(npv)} at {fmt_pct(bp(request.hurdle_bp))}, "
            f"payback in month {payback}." if worth else
            f"Not worth doing on the owner's estimate: NPV {fmt_yuan(npv)}, payback "
            f"{f'in month {payback}' if payback else 'not within the life'} against a "
            f"{request.payback_limit_months}-month limit.")
    if not worth:
        return f"{head} No financing structure is recommended."
    if selected is None:
        return f"{head} No structure holds every covenant in every month without pushing daily cash below the reserve."
    if selected.kind == "CASH_LINE":
        return (f"{head} Pay from cash above the reserve (and the committed line if needed): no new facility "
                f"is needed.")
    tail = (f" Finance with the {selected.label}"
            + (f" ({fmt_yuan(selected.monthly_payment_fen)} a month)" if selected.monthly_payment_fen else "")
            + f": it has the {CHARGES_BASIS} of the structures that pass, {fmt_yuan(selected.charges_total_fen or 0)}.")
    lower = [s for s in structures if s.result == "REJECTED" and not s.hypothetical
             and s.charges_total_fen is not None and s.charges_total_fen < (selected.charges_total_fen or 0)]
    if lower:
        tail += f" The lower-charge {lower[0].label} is rejected ({lower[0].violations[0].code.value})."
    if tier == Tier.TIER_2:
        tail += " A new facility is Tier 2: the agent recommends and the owner applies."
    return head + tail
