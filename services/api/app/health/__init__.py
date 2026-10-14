"""Financial health for the buy side (ADR-0013, phase 5; docs/capex_handover.md D6).

Four readings of the current books, read-only and each reconciled to a figure the product already shows:

1. Cash: today's headroom and the lowest forecast headroom on the conservative projection of current books, the same
   projection and the same "first breach ahead" rule as Home, and whether a committed funding plan cures a shortfall.
2. The 90-day cash coverage ratio: (cash today + money coming in over the next 90 days) / money going out over them, read
   from that projection's own events. It is a liquidity reading the books can support; it is **not** a balance-sheet
   current ratio and is never called one.
3. The current and quick ratios, only from the owner's own entries (inventory, other current assets, trade payables, other
   current liabilities), labelled OWNER_ESTIMATE: the books hold none of those, and a ratio built without them would be
   wrong. The debt falling due within twelve months is computed from the books' own schedules.
4. Covenant room and borrowing capacity: the worst projected DSCR and leverage against the strictest limits (the mandate's
   and every committed facility's), the extra monthly debt service and extra debt they still allow, and for each
   owner-approved term facility the largest principal whose service and debt fit both rooms and its limit. Capacity is
   what the ratios allow, not cash in hand: an uncommitted facility still counts as zero for every hard constraint
   (INVARIANT 4) and says so.

No arithmetic on money paths of its own beyond sums and the ratio of two exact sums: payments come from `app.financial`
and `app.capex` (ADR-0008 service), ratios from `app.covenants`, and every ratio is an exact `Ratio`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from typing import Literal

from pydantic import Field

from app.books import current_books
from app.capex.evaluate import is_term_facility, term_service
from app.capex.models import OWNER_ESTIMATE
from app.covenants import ratios_for, worst_dscr, worst_leverage
from app.domain.models import (
    Commitment,
    Contract,
    CovenantKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    LedgerEventKind,
    Mandate,
    Mode,
    Trajectory,
)
from app.domain.money import DAYS_PER_YEAR, Ratio, bp, fmt_pct, fmt_yuan, post
from app.financial import EngineError, project
from app.financial.debts import debt_payments
from app.financial.lots import contractual_payments, ensure_lots
from app.funding import router as funding_router

COVERAGE_DAYS = 90
YEAR_DAYS = DAYS_PER_YEAR  # "within twelve months" for liabilities: 365 days, so an instalment on day 360 is counted
_OPERATING_IN = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT, LedgerEventKind.FLOW)
_FUNDING_IN = (LedgerEventKind.DRAW, LedgerEventKind.ADVANCE)
_SHORT_TERM_KINDS = (FacilityKind.CREDIT_LINE, FacilityKind.INVOICE_FINANCING, FacilityKind.BUYER_EARLY_PAY,
                     FacilityKind.BANK_ACCEPTANCE_BILL)


def x(r: Ratio | None) -> str:
    return f"{r.text}×" if r is not None else "n/a"


# ---------------------------------------------------------------- models


class HealthInputs(Contract):
    """The owner's balance-sheet entries the books do not hold. Each is optional; the current and quick ratios need all
    four (a missing one is named, never assumed to be zero)."""

    inventory_fen: int | None = Field(default=None, ge=0)
    other_current_assets_fen: int | None = Field(default=None, ge=0)
    trade_payables_fen: int | None = Field(default=None, ge=0)
    other_current_liabilities_fen: int | None = Field(default=None, ge=0)


class CashHealth(Contract):
    cash_fen: int
    reserve_fen: int
    headroom_fen: int  # cash today - the reserve
    lowest_fen: int
    lowest_day: int
    lowest_headroom_fen: int
    first_breach_day: int | None
    first_breach_cash_fen: int | None
    horizon_end_day: int
    status: Literal["OK", "SHORT"]
    plan_admissible: bool | None = None  # a committed funding plan cures the shortfall (None: no shortfall to cure)
    plan_cost_fen: int | None = None
    text: str


class Coverage(Contract):
    window_days: int
    cash_fen: int
    operating_in_fen: int  # receipts and scheduled inflows the conservative projection counts
    funding_in_fen: int  # funding already requested that lands in the window
    out_fen: int  # every outflow in the window (payroll, suppliers, purchases, debt service, interest, fees)
    capex_out_fen: int  # of which committed capex payments (ADR-0013)
    ratio: Ratio | None  # None when nothing goes out
    text: str
    formula: str


class LiquidityRatios(Contract):
    available: bool
    needs: list[str] = Field(default_factory=list)
    cash_fen: int
    receivables_fen: int  # outstanding face of open and financed invoices
    debt_due_12m_fen: int  # principal falling due within twelve months on the books' own schedules
    capex_due_12m_fen: int  # committed capex payments within twelve months (a commitment, shown beside, not a liability)
    current_assets_fen: int | None = None
    current_liabilities_fen: int | None = None
    current_ratio: Ratio | None = None
    quick_ratio: Ratio | None = None
    evidence: str | None = None  # OWNER_ESTIMATE when the ratios rest on the owner's entries
    formula: str
    text: str


class CovenantRoom(Contract):
    ebitda_fen: int
    worst_dscr: Ratio | None
    worst_dscr_month: int | None
    worst_debt_service_fen: int
    min_dscr: Ratio
    min_dscr_source: str
    dscr_ok: bool
    worst_leverage: Ratio | None
    worst_leverage_month: int | None
    worst_debt_fen: int
    max_leverage: Ratio
    max_leverage_source: str
    leverage_ok: bool
    dscr_room_monthly_fen: int  # extra monthly debt service the DSCR minimum still allows (0 when already failing)
    leverage_room_fen: int  # extra debt the leverage maximum still allows (0 when already failing)
    text: str
    formula: str


class FacilityCapacity(Contract):
    facility_id: str
    name: str
    status: str
    counts_now: bool  # COMMITTED and owner-approved: usable today; otherwise zero for every hard constraint
    rate_bp: int
    term_months: int
    room_fen: int  # limit - drawn
    capacity_fen: int  # the largest principal that fits the limit, the DSCR room and the leverage room
    binding: Literal["LIMIT", "DSCR", "LEVERAGE", "NONE"]
    monthly_payment_fen: int | None  # the highest monthly service at that principal
    text: str


class FinancialHealth(Contract):
    day: int
    state_version: int
    mandate_version: int
    cash: CashHealth
    coverage: Coverage
    liquidity: LiquidityRatios
    covenants: CovenantRoom | None  # None when monthly EBITDA <= 0 (the ratios are undefined)
    capacity: list[FacilityCapacity]
    summary: str
    assumptions: list[str]


# ---------------------------------------------------------------- readings


def _ahead(traj: Trajectory, today: int) -> list:
    return [d for d in traj.days if d.day >= today] or list(traj.days)


def _cash(state: FinancialState, mandate: Mandate, traj: Trajectory, obligations: list,
          plan_cost: tuple[bool, int] | None) -> CashHealth:
    today = state.as_of_day
    days = _ahead(traj, today)
    low = min(days, key=lambda d: (d.closing_fen, d.day))
    hit = next((d for d in days if d.closing_fen < mandate.min_cash_fen), None)  # Home's "first breach ahead"
    breach = (max(hit.day, today), hit.closing_fen) if hit is not None else None
    status: Literal["OK", "SHORT"] = "SHORT" if breach else "OK"
    gap = low.closing_fen - mandate.min_cash_fen
    if breach is None:
        text = (f"Cash stays above your {fmt_yuan(mandate.min_cash_fen)} minimum for the next {mandate.horizon_days} days; "
                f"the lowest point is {fmt_yuan(low.closing_fen)} on day {low.day}, {fmt_yuan(gap)} above it.")
    else:
        cure = ("" if plan_cost is None else
                f" A committed funding plan covers it for {fmt_yuan(plan_cost[1])}." if plan_cost[0] else
                " No committed funding plan covers it.")
        text = (f"Cash falls below your {fmt_yuan(mandate.min_cash_fen)} minimum on day {breach[0]} "
                f"({fmt_yuan(breach[1])}); the lowest point is {fmt_yuan(low.closing_fen)} on day {low.day}.{cure}")
    return CashHealth(
        cash_fen=state.cash_fen, reserve_fen=mandate.min_cash_fen, headroom_fen=state.cash_fen - mandate.min_cash_fen,
        lowest_fen=low.closing_fen, lowest_day=low.day, lowest_headroom_fen=gap,
        first_breach_day=breach[0] if breach else None, first_breach_cash_fen=breach[1] if breach else None,
        horizon_end_day=traj.days[-1].day if traj.days else today, status=status,
        plan_admissible=plan_cost[0] if plan_cost is not None else None,
        plan_cost_fen=plan_cost[1] if plan_cost is not None and plan_cost[0] else None, text=text)


def _coverage(state: FinancialState, traj: Trajectory) -> Coverage:
    today = state.as_of_day
    end = today + COVERAGE_DAYS
    window = [d for d in traj.days if today <= d.day < end]
    days = (window[-1].day - today + 1) if window else 0
    op_in = funding_in = out = capex_out = 0
    capex_ids = {f.id for f in state.flows if f.kind == FlowKind.CAPEX}
    for d in window:
        for e in d.events:
            if e.kind == LedgerEventKind.OPENING:
                continue
            if e.amount_fen > 0:
                if e.kind in _FUNDING_IN:
                    funding_in += e.amount_fen
                elif e.kind in _OPERATING_IN:
                    op_in += e.amount_fen
                else:
                    op_in += e.amount_fen  # any other cash in the engine counts (none expected); kept, never dropped
            elif e.amount_fen < 0:
                out += -e.amount_fen
                if e.ref in capex_ids:
                    capex_out += -e.amount_fen
    ratio = Ratio.of(Fraction(state.cash_fen + op_in + funding_in, out)) if out > 0 else None
    formula = (f"(cash today + money in over days {today}..{today + days - 1}) / money out over them = "
               f"({fmt_yuan(state.cash_fen)} + {fmt_yuan(op_in)} + {fmt_yuan(funding_in)} funding landing) / "
               f"{fmt_yuan(out)}; the conservative projection's own events (unconfirmed inflows not counted)")
    if ratio is None:
        text = f"Nothing is due to go out over the next {days} days."
    else:
        verdict = ("covers" if ratio.value >= 1 else "does not cover")
        text = (f"Over the next {days} days, cash on hand and what comes in {verdict} what goes out: "
                f"{x(ratio)} ({fmt_yuan(state.cash_fen + op_in + funding_in)} against {fmt_yuan(out)}).")
    return Coverage(window_days=days, cash_fen=state.cash_fen, operating_in_fen=op_in, funding_in_fen=funding_in,
                    out_fen=out, capex_out_fen=capex_out, ratio=ratio, text=text, formula=formula)


def debt_due_within(state: FinancialState, days: int) -> int:
    """Principal falling due in [today, today + days) on the books' own schedules: existing debts' payments, term
    lots' contractual payments; a credit-line, invoice-advance or bill balance is due within the period in full."""
    today = state.as_of_day
    end = today + days
    total = sum(p.principal for d in state.debts for p in debt_payments(d, today, end))
    state = ensure_lots(state)
    fac = {f.id: f for f in state.facilities}
    for lot in state.lots:
        f = fac.get(lot.facility_id)
        if f is None or lot.remaining_fen <= 0:
            continue
        if f.kind in _SHORT_TERM_KINDS or f.repayment.value == "ON_RECEIPT":
            total += lot.remaining_fen
        else:
            total += sum(p.principal for p in contractual_payments(lot, f) if p.day < end)
    return total


def _liquidity(state: FinancialState, inputs: HealthInputs) -> LiquidityRatios:
    today = state.as_of_day
    receivables = sum(r.outstanding_fen for r in state.receivables if r.status in ("OPEN", "FINANCED"))
    debt_12m = debt_due_within(state, YEAR_DAYS)
    capex_12m = sum(-f.amount_fen for f in state.flows
                    if f.kind == FlowKind.CAPEX and today <= f.day < today + YEAR_DAYS)
    needs = [n for n in ("inventory_fen", "other_current_assets_fen", "trade_payables_fen",
                         "other_current_liabilities_fen") if getattr(inputs, n) is None]
    formula = ("current ratio = (cash + receivables + inventory + other current assets) / (trade payables + other "
               "current liabilities + debt due within 12 months); quick ratio = (cash + receivables) / the same "
               "liabilities; committed capex payments are shown beside, not counted as a liability")
    base = LiquidityRatios(
        available=False, needs=needs, cash_fen=state.cash_fen, receivables_fen=receivables, debt_due_12m_fen=debt_12m,
        capex_due_12m_fen=capex_12m, formula=formula, text=(
            "The current and quick ratios need your inventory, other current assets, trade payables and other current "
            "liabilities, which the books do not hold; until you enter them, the 90-day cash coverage above is the "
            "liquidity reading."))
    if needs:
        return base
    assert inputs.inventory_fen is not None and inputs.other_current_assets_fen is not None
    assert inputs.trade_payables_fen is not None and inputs.other_current_liabilities_fen is not None
    ca = state.cash_fen + receivables + inputs.inventory_fen + inputs.other_current_assets_fen
    cl = inputs.trade_payables_fen + inputs.other_current_liabilities_fen + debt_12m
    current = Ratio.of(Fraction(ca, cl)) if cl > 0 else None
    quick = Ratio.of(Fraction(state.cash_fen + receivables, cl)) if cl > 0 else None
    text = (f"Current ratio {x(current)}, quick ratio {x(quick)}: {fmt_yuan(ca)} of current assets against "
            f"{fmt_yuan(cl)} of current liabilities, on your own entries for inventory and payables."
            if cl > 0 else "No current liabilities: the ratios are not defined.")
    return base.model_copy(update={"available": True, "current_assets_fen": ca, "current_liabilities_fen": cl,
                                   "current_ratio": current, "quick_ratio": quick, "evidence": OWNER_ESTIMATE,
                                   "text": text})


def covenant_limits(state: FinancialState, mandate: Mandate) -> tuple[Fraction, str, Fraction, str]:
    """(min DSCR, its source, max leverage, its source): the strictest of the mandate and every committed, owner-approved
    facility's covenants (the capex screen's rule, `_Base.limits_with(None)`)."""
    dscr = [(bp(mandate.min_dscr_bp), f"mandate v{mandate.version}")]
    lev = [(bp(mandate.max_leverage_bp), f"mandate v{mandate.version}")]
    for f in state.facilities:
        if f.status != FacilityStatus.COMMITTED or not f.owner_approved:
            continue
        for c in f.covenants:
            if c.threshold_bp is None:
                continue
            if c.kind == CovenantKind.DSCR_MIN:
                dscr.append((bp(c.threshold_bp), c.id))
            elif c.kind == CovenantKind.LEVERAGE_MAX:
                lev.append((bp(c.threshold_bp), c.id))
    d_lim, d_src = max(dscr)
    l_lim, l_src = min(lev)
    return d_lim, d_src, l_lim, l_src


def _covenants(state: FinancialState, mandate: Mandate, traj: Trajectory) -> CovenantRoom | None:
    ebitda = state.monthly_ebitda_fen
    if ebitda <= 0:
        return None
    d_lim, d_src, l_lim, l_src = covenant_limits(state, mandate)
    dp = worst_dscr(traj.months)
    lp = worst_leverage(traj.months)
    ds = dp.debt_service_fen if dp is not None else 0
    debt = lp.total_debt_fen if lp is not None else 0
    dscr, _ = ratios_for(dp) if dp is not None else (None, None)
    _, lev = ratios_for(lp) if lp is not None else (None, None)
    dscr_ok = dscr is None or dscr.value >= d_lim
    lev_ok = lev is None or lev.value <= l_lim
    ds_room = max(0, post(Fraction(ebitda) / d_lim) - ds)  # EBITDA / min DSCR - the worst month's debt service
    debt_room = max(0, post(12 * ebitda * l_lim) - debt)  # 12 x EBITDA x max leverage - the worst month's debt
    text = (f"Worst projected DSCR {x(dscr)} (minimum {x(Ratio.of(d_lim))}) and leverage {x(lev)} (maximum "
            f"{x(Ratio.of(l_lim))}): room for {fmt_yuan(ds_room)} more debt service a month and {fmt_yuan(debt_room)} "
            f"more debt.")
    formula = (f"DSCR room = EBITDA_m / min DSCR − worst DS_m = {fmt_yuan(ebitda)} / {x(Ratio.of(d_lim))} − "
               f"{fmt_yuan(ds)}; leverage room = 12 × EBITDA_m × max leverage − worst month-end debt = 12 × "
               f"{fmt_yuan(ebitda)} × {x(Ratio.of(l_lim))} − {fmt_yuan(debt)}; each rounded once, never below zero")
    return CovenantRoom(
        ebitda_fen=ebitda, worst_dscr=dscr, worst_dscr_month=dp.month if dp is not None else None,
        worst_debt_service_fen=ds, min_dscr=Ratio.of(d_lim), min_dscr_source=d_src, dscr_ok=dscr_ok,
        worst_leverage=lev, worst_leverage_month=lp.month if lp is not None else None, worst_debt_fen=debt,
        max_leverage=Ratio.of(l_lim), max_leverage_source=l_src, leverage_ok=lev_ok, dscr_room_monthly_fen=ds_room,
        leverage_room_fen=debt_room, text=text, formula=formula)


def largest_principal(fits: object, upper: int) -> int:
    """The largest principal in [0, upper] for which `fits(p)` holds, `fits` being monotone (true up to some p, false
    after): integer bisection."""
    assert callable(fits)
    if upper <= 0 or not fits(1):
        return 0
    lo, hi = 1, upper  # fits(lo) holds
    if fits(hi):
        return hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if fits(mid):
            lo = mid
        else:
            hi = mid
    return lo


def facility_capacity(f: Facility, room: CovenantRoom | None, term: int | None = None) -> FacilityCapacity:
    """The largest principal on `f` whose highest monthly service fits the DSCR room and which fits the leverage room and
    the facility's limit (each binding constraint named)."""
    n = term or f.term_months or 1
    limit_room = max(0, f.limit_fen - f.drawn_fen)
    counts = f.status == FacilityStatus.COMMITTED and f.owner_approved
    status_note = ("" if counts else f" It is {f.status.value.replace('_', ' ').lower()}: it counts as zero until it is "
                   f"committed.")
    if room is None:
        return FacilityCapacity(
            facility_id=f.id, name=f.name, status=f.status.value, counts_now=counts, rate_bp=f.rate_bp, term_months=n,
            room_fen=limit_room, capacity_fen=0, binding="NONE", monthly_payment_fen=None,
            text=f"{f.name}: no capacity can be read while EBITDA is not positive.{status_note}")

    def fits(p: int) -> bool:
        return max(term_service(f, p, n)) <= room.dscr_room_monthly_fen and p <= room.leverage_room_fen

    cap = largest_principal(fits, limit_room)
    if cap == limit_room and limit_room > 0:
        binding: Literal["LIMIT", "DSCR", "LEVERAGE", "NONE"] = "LIMIT"
    elif cap >= room.leverage_room_fen and room.leverage_room_fen < limit_room:
        binding = "LEVERAGE"
    elif limit_room > 0:
        binding = "DSCR"
    else:
        binding = "NONE"
    pay = max(term_service(f, cap, n)) if cap > 0 else None
    why = {"LIMIT": "the facility's limit", "DSCR": "the DSCR minimum", "LEVERAGE": "the leverage maximum",
           "NONE": "nothing left on the facility"}[binding]
    text = (f"{f.name} ({fmt_pct(bp(f.rate_bp))}, {n} months): up to {fmt_yuan(cap)}"
            + (f" at {fmt_yuan(pay)} a month" if pay else "") + f", set by {why}.{status_note}")
    return FacilityCapacity(
        facility_id=f.id, name=f.name, status=f.status.value, counts_now=counts, rate_bp=f.rate_bp, term_months=n,
        room_fen=limit_room, capacity_fen=cap, binding=binding, monthly_payment_fen=pay, text=text)


ASSUMPTIONS = (
    ("Cash is read on the conservative projection of current books (the stored books plus live agreements), the same as "
     "Home: unconfirmed inflows are not counted and uncommitted facilities count as zero."),
    ("The 90-day cash coverage ratio is a reading of the projection's own cash in and out; it is not a balance-sheet "
     "current ratio. The current and quick ratios use your own entries for what the books do not hold."),
    ("Covenant room is read on the worst projected month of the mandate's horizon; a facility's capacity is what DSCR, "
     "leverage and its limit allow, not cash available, and it ignores the timing of when cash is needed (the capex "
     "screen tests that day by day)."),
    ("Each facility's capacity is read on its own: the facilities share one DSCR and leverage room, so borrowing on one "
     "leaves less for the others."),
    "Debt due within twelve months counts every payment in the next 365 days.",
)


def financial_health(state: FinancialState, mandate: Mandate, *, commitments: Sequence[Commitment] = (),
                     inputs: HealthInputs | None = None) -> FinancialHealth:
    """The four readings of current books. Raises EngineError when the books cannot be projected."""
    books = current_books(state, commitments)
    obligations = list(books.obligations)
    traj = project(books.state, obligations, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    today = books.state.as_of_day
    plan_cost: tuple[bool, int] | None = None
    if any(d.closing_fen < mandate.min_cash_fen for d in _ahead(traj, today)):
        try:
            plan = funding_router.plan(books.state, obligations, mandate, "COMMITTED")
            plan_cost = (plan.admissible, plan.total_cost_fen)
        except EngineError:
            plan_cost = (False, 0)
    cash = _cash(books.state, mandate, traj, obligations, plan_cost)
    coverage = _coverage(books.state, traj)
    liquidity = _liquidity(books.state, inputs or HealthInputs())
    room = _covenants(books.state, mandate, traj)
    capacity = [facility_capacity(f, room) for f in books.state.facilities
                if f.owner_approved and is_term_facility(f) and f.status != FacilityStatus.REFERENCE_ONLY]
    ratios = (room.text if room is not None else "Monthly EBITDA is not positive, so DSCR and leverage are undefined.")
    summary = f"{cash.text} {coverage.text} {ratios}"
    return FinancialHealth(day=today, state_version=books.state.state_version, mandate_version=mandate.version,
                           cash=cash, coverage=coverage, liquidity=liquidity, covenants=room, capacity=capacity,
                           summary=summary, assumptions=list(ASSUMPTIONS))


__all__ = [
    "ASSUMPTIONS",
    "COVERAGE_DAYS",
    "CashHealth",
    "CovenantRoom",
    "Coverage",
    "FacilityCapacity",
    "FinancialHealth",
    "HealthInputs",
    "LiquidityRatios",
    "covenant_limits",
    "debt_due_within",
    "facility_capacity",
    "financial_health",
    "largest_principal",
]
