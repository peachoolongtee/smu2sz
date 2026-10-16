"""Long-term plans: the permutations of several purchases, their start months and their financing (ADR-0013, phase 7;
docs/capex_handover.md D9, D10).

A **monthly estimate**, labelled so everywhere, never a hard constraint and never a substitute for the conservative daily
test (the capex screen runs that for each contract, and the best plan's contract projects are re-run through it here):

- before any plan, each month's free cash is monthly EBITDA less the existing debt service (the capex screen's own rule,
  `existing_debt_service`), from today's cash: an estimate that ignores the timing of receipts within a month;
- each project adds its own months: the contract's payments (or a price paid at the start), shifted by the start month
  tried; the owner's uplift; for a financed option, the proceeds in the month they land (requested the facility's lead
  time before the first payment, never before today), the upfront fee, and the ADR-0008 service from the following
  month;
- every month must hold: cash at or above the reserve wherever the plan makes it lower than without it (a shortfall the
  books already have is reported, not blamed on the plan, the capex screen's rule); DSCR = (EBITDA + uplift) / (existing +
  new service) at or above the strictest minimum (the mandate's, every committed facility's and every facility the plan
  uses); leverage = (existing debt + new principal outstanding) / (12 × EBITDA) at or below the strictest maximum; and no
  facility lent more than its limit across the projects together;
- plans are ranked on NPV to the owner at the hurdle of all the plan's cash flows over every month they run (payments,
  uplift, proceeds, service, fees), then on the higher lowest headroom. NPV is linear, so each project-option's NPV is
  computed once (50-digit Decimal) and a plan's is their sum, rounded once.

The number of permutations is capped (`MAX_COMBINATIONS`); a request above it is refused with the count, never sampled.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction

from pydantic import Field

from app.books import current_books
from app.capex.appraisal import NPV_PRECISION, payment_month
from app.capex.evaluate import existing_debt_service, is_term_facility, term_service
from app.capex.models import OWNER_ESTIMATE
from app.capex.schedule import Timeline, derive_schedule
from app.domain.models import (
    Commitment,
    Contract,
    ContractRecord,
    CovenantKind,
    DocumentKind,
    Facility,
    FacilityStatus,
    FinancialState,
    FlowKind,
    Mandate,
)
from app.domain.money import BP_DENOM, Ratio, bp, fmt_yuan, post
from app.financial.debts import debt_payments
from app.financial.lots import contractual_payments, ensure_lots
from app.financial.trajectory import MONTH_DAYS
from app.funding.rates import tier3_reasons
from app.health import covenant_limits

CASH = "CASH"
MAX_COMBINATIONS = 20_000
MAX_PROJECTS = 4
TOP = 5


# ---------------------------------------------------------------- request and result


class PlanProject(Contract):
    """One purchase in the plan: a capex contract on the owner's timeline, or a price paid when the project starts."""

    id: str = Field(min_length=1, max_length=40)
    label: str = Field(default="", max_length=120)
    document_id: str | None = None  # a capex contract's record
    timeline: Timeline | None = None  # with `document_id`: the days at the plan's start (offset 0)
    price_fen: int | None = Field(default=None, gt=0)  # without a contract: one payment when the project starts
    monthly_uplift_fen: int = Field(default=0, ge=0)
    uplift_start_month: int | None = Field(default=None, ge=1)  # months from today at offset 0; None: after acceptance
    life_months: int = Field(default=60, ge=1, le=600)  # months from today at offset 0 through which the uplift runs
    start_offsets: list[int] = Field(default_factory=lambda: [0, 3, 6, 12])  # months to delay the whole project
    options: list[str] | None = None  # "CASH" and facility ids; None: cash and every usable term facility on the menu
    optional: bool = False  # the plan may leave this project out


class PlanRequest(Contract):
    projects: list[PlanProject] = Field(min_length=1, max_length=MAX_PROJECTS)
    horizon_months: int = Field(default=60, ge=12, le=120)
    hurdle_bp: int = Field(default=1000, ge=0)


class PlanChoice(Contract):
    project_id: str
    label: str
    included: bool
    start_offset_months: int
    option: str  # "CASH", a facility id, or "SKIP"
    option_label: str
    first_payment_day: int | None
    principal_fen: int | None
    monthly_payment_fen: int | None


class PlanMonth(Contract):
    month: int
    cash_fen: int
    baseline_cash_fen: int
    dscr: Ratio | None
    leverage: Ratio | None


class RankedPlan(Contract):
    rank: int | None
    choices: list[PlanChoice]
    npv_fen: int
    financing_charges_fen: int  # interest + upfront fees over the loans' lives, not discounted
    lowest_headroom_fen: int
    lowest_month: int
    admissible: bool
    first_failure: str | None
    months: list[PlanMonth] = Field(default_factory=list)
    text: str


class DailyCheck(Contract):
    project_id: str
    document_id: str
    selected_id: str | None  # the capex screen's own choice on that timeline
    plan_option_passes: bool | None  # the plan's option passes the daily test (None: cash, read as the cash+line row)
    text: str


class PlanResult(Contract):
    horizon_months: int
    combinations: int
    admissible_count: int
    best: list[RankedPlan]
    best_unconstrained: RankedPlan | None  # the highest NPV of all, when it is not admissible: what the limits cost
    never_admissible: list[str]  # "project / option" pairs no admissible plan uses
    baseline_lowest_headroom_fen: int
    daily_checks: list[DailyCheck] = Field(default_factory=list)
    evidence: str = OWNER_ESTIMATE
    assumptions: list[str]


class PlanRefused(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- per project-option vectors


@dataclass(frozen=True)
class _Vec:
    """One project at one start offset with one option: its monthly effects (index 0 = month 1) and its NPV."""

    project: PlanProject
    offset: int
    option: str
    label: str
    cash: tuple[int, ...]  # net cash effect in the month (payments out, proceeds in, service and fee out, uplift in)
    uplift: tuple[int, ...]
    service: tuple[int, ...]  # new debt service in the month
    principal: tuple[int, ...]  # new principal outstanding at the month's end
    npv: Decimal  # exact enough: summed with others, rounded once
    charges: int
    facility_id: str | None
    principal_fen: int | None
    monthly_payment_fen: int | None
    first_payment_day: int | None
    skip: bool = False


def _discount(months: int, hurdle_bp: int) -> list[Decimal]:
    with localcontext() as ctx:
        ctx.prec = NPV_PRECISION
        h = Decimal(hurdle_bp) / Decimal(BP_DENOM)
        rm = (1 + h) ** (Decimal(1) / Decimal(12)) - 1
        return [1 / (1 + rm) ** m for m in range(months + 1)]


def _payments(project: PlanProject, records: dict[str, ContractRecord], state: FinancialState) -> list[tuple[int, int]]:
    """(day, fen) of the project's payments at offset 0; PlanRefused when they cannot be established."""
    if project.document_id is not None:
        rec = records.get(project.document_id)
        if rec is None or rec.kind != DocumentKind.CAPEX_CONTRACT or rec.contract is None:
            raise PlanRefused("NOT_A_CAPEX_CONTRACT", f"{project.id}: {project.document_id} is not a capex contract")
        res = derive_schedule(rec.contract, project.timeline or Timeline(), anchor_iso=state.as_of,
                              today=state.as_of_day)
        if not res.derivable or res.schedule is None:
            raise PlanRefused("NO_SCHEDULE", f"{project.id}: " + " ".join(res.reasons))
        return [(p.day, p.amount_fen) for p in res.schedule.payments]
    if project.price_fen is None:
        raise PlanRefused("NO_PRICE", f"{project.id}: give a capex contract or a price")
    return [(state.as_of_day, project.price_fen)]


def _uplift_start(project: PlanProject, today: int) -> int:
    if project.uplift_start_month is not None:
        return project.uplift_start_month
    t = project.timeline
    for day in ((t.acceptance_day, t.delivery_day) if t is not None else ()):
        if day is not None:
            return payment_month(day, today) + 1
    return 4  # the capex screen's default


def _vector(project: PlanProject, offset: int, option: str, base: list[tuple[int, int]], f: Facility | None,
            today: int, months: int, disc: list[Decimal]) -> _Vec:
    """The effects of one project-option over `months` months (enough for every flow it has)."""
    shift = offset * MONTH_DAYS
    pays = [(d + shift, a) for d, a in base]
    cash = [0] * (months + 1)  # index = month (0 = today)
    uplift = [0] * (months + 1)
    service = [0] * (months + 1)
    principal = [0] * (months + 1)
    for d, a in pays:
        cash[payment_month(d, today)] -= a
    start = _uplift_start(project, today) + offset
    last = project.life_months + offset
    for m in range(start, min(last, months) + 1):
        uplift[m] += project.monthly_uplift_fen
        cash[m] += project.monthly_uplift_fen
    price = sum(a for _, a in pays)
    charges = 0
    pay: int | None = None
    if f is not None:
        first_day = min(d for d, _ in pays)
        # requested its lead time before the first payment (never before today), so the proceeds land when needed
        request = max(today, first_day - f.lead_time_days)
        land = payment_month(request + f.lead_time_days, today)
        fee = post(bp(f.upfront_fee_bp) * price)
        cash[land] += price - fee
        rows = term_service(f, price, f.term_months or 1)
        interest = sum(rows) - price
        charges = interest + fee
        pay = max(rows)
        # the level or annuity service from the month after the proceeds land; principal falls by what each payment repays
        sched = _principal_path(f, price)
        for k, amount in enumerate(rows, start=1):
            m = land + k
            if m > months:
                break
            service[m] += amount
            cash[m] -= amount
        for m in range(land, months + 1):
            k = m - land
            principal[m] += sched[k] if k < len(sched) else 0
    npv = sum((Decimal(c) * disc[m] for m, c in enumerate(cash) if c), Decimal(0))
    # the monthly tests run from month 1: what falls today (month 0) is in month 1's cash, never dropped
    tested = cash[1:]
    tested[0] += cash[0]
    return _Vec(project=project, offset=offset, option=option, label=f.name if f is not None else "Cash",
                cash=tuple(tested), uplift=tuple(uplift[1:]), service=tuple(service[1:]),
                principal=tuple(principal[1:]), npv=npv, charges=charges, facility_id=f.id if f is not None else None,
                principal_fen=price if f is not None else None, monthly_payment_fen=pay,
                first_payment_day=min(d for d, _ in pays))


def _principal_path(f: Facility, principal: int) -> list[int]:
    """Principal outstanding after k payments (k = 0, 1, ...): the annuity's balances, or for a level bullet loan the
    principal until its last month (ADR-0008 counts it at level service; the balance is owed until maturity)."""
    from app.domain.models import Repayment
    from app.financial.amortisation import amortisation_schedule

    n = f.term_months or 1
    if f.repayment == Repayment.AMORTISING:
        return [principal, *(r.balance for r in amortisation_schedule(principal, f.rate_bp, n))]
    return [principal] * n + [0]


def _skip(project: PlanProject, months: int) -> _Vec:
    z = (0,) * months
    return _Vec(project=project, offset=0, option="SKIP", label="Left out", cash=z, uplift=z, service=z, principal=z,
                npv=Decimal(0), charges=0, facility_id=None, principal_fen=None, monthly_payment_fen=None,
                first_payment_day=None, skip=True)


# ---------------------------------------------------------------- the search


def _existing_debt(state: FinancialState, months: int) -> list[int]:
    """Debt that counts in leverage at each month's end from today, on the books' own schedules."""
    today = state.as_of_day
    state = ensure_lots(state)
    fac = {f.id: f for f in state.facilities}
    out = []
    for m in range(1, months + 1):
        end = today + m * MONTH_DAYS
        debt = sum(d.principal_fen - sum(p.principal for p in debt_payments(d, today, end + 1)) for d in state.debts)
        for lot in state.lots:
            f = fac.get(lot.facility_id)
            if f is None or not f.counts_in_leverage or lot.remaining_fen <= 0:
                continue
            paid = sum(p.principal for p in contractual_payments(lot, f) if p.day <= end)
            debt += lot.remaining_fen - paid
        out.append(debt)
    return out


def _options(project: PlanProject, state: FinancialState, mandate: Mandate) -> list[tuple[str, Facility | None]]:
    usable = (FacilityStatus.NOT_APPLIED, FacilityStatus.PENDING, FacilityStatus.COMMITTED)
    menu = {f.id: f for f in state.facilities
            if f.owner_approved and f.status in usable and is_term_facility(f) and not tier3_reasons(f)}
    wanted = project.options if project.options is not None else [CASH, *menu]
    out: list[tuple[str, Facility | None]] = []
    for o in wanted:
        if o == CASH:
            out.append((CASH, None))
        elif o in menu and mandate.allow_new_borrowing:
            out.append((o, menu[o]))
        else:
            raise PlanRefused("UNKNOWN_OPTION", f"{project.id}: {o} is not cash or a usable, owner-approved term facility "
                                                f"on the funding menu" + ("" if mandate.allow_new_borrowing else
                                                                          " (the mandate allows no new borrowing)"))
    return out


@dataclass
class _Eval:
    admissible: bool
    failure: str | None
    lowest_headroom: int
    lowest_month: int
    months: list[PlanMonth]


def _evaluate(combo: Sequence[_Vec], baseline: list[int], ebitda: int, ds0: list[int], debt0: list[int],
              state: FinancialState, mandate: Mandate, keep_months: bool) -> _Eval:
    reserve = mandate.min_cash_fen
    d_lim, _, l_lim, _ = covenant_limits(state, mandate)
    used = {v.facility_id for v in combo if v.facility_id}
    fac = {f.id: f for f in state.facilities}
    for fid in used:
        for c in fac[fid].covenants:
            if c.threshold_bp is None:
                continue
            if c.kind == CovenantKind.DSCR_MIN:
                d_lim = max(d_lim, bp(c.threshold_bp))
            elif c.kind == CovenantKind.LEVERAGE_MAX:
                l_lim = min(l_lim, bp(c.threshold_bp))
    d_num, d_den = d_lim.numerator, d_lim.denominator
    l_num, l_den = l_lim.numerator, l_lim.denominator
    failure: str | None = None
    for fid in sorted(used):
        lent = sum(v.principal_fen or 0 for v in combo if v.facility_id == fid)
        room = fac[fid].limit_fen - fac[fid].drawn_fen
        if lent > room:
            failure = f"{fac[fid].name} would lend {fmt_yuan(lent)}, above the {fmt_yuan(room)} left on it"
            break
    cum = 0
    low_head: int | None = None
    low_month = 0
    months: list[PlanMonth] = []
    for i, base in enumerate(baseline):
        m = i + 1
        cum += sum(v.cash[i] for v in combo)
        cash = base + cum
        head = cash - reserve
        if low_head is None or head < low_head:
            low_head, low_month = head, m
        new_service = sum(v.service[i] for v in combo)
        uplift = sum(v.uplift[i] for v in combo)
        new_principal = sum(v.principal[i] for v in combo)
        ds = ds0[i] + new_service
        debt = debt0[i] + new_principal
        if failure is None:
            # exact integer comparisons: (E + U) / DS >= d_num / d_den, debt / (12 E) <= l_num / l_den
            if cash < reserve and cum < 0:
                failure = (f"month {m}: cash {fmt_yuan(cash)} is below the {fmt_yuan(reserve)} reserve, "
                           f"{fmt_yuan(-cum)} lower than without the plan")
            elif (new_service > 0 or new_principal > 0) and ebitda <= 0:
                failure = f"month {m}: EBITDA is not positive, so new debt cannot be tested"
            elif new_service > 0 and (ebitda + uplift) * d_den < d_num * ds:
                failure = (f"month {m}: DSCR {Ratio.of(Fraction(ebitda + uplift, ds)).text}× is below the "
                           f"{Ratio.of(d_lim).text}× minimum")
            elif new_principal > 0 and debt * l_den > l_num * 12 * ebitda:
                failure = (f"month {m}: leverage {Ratio.of(Fraction(debt, 12 * ebitda)).text}× is above the "
                           f"{Ratio.of(l_lim).text}× maximum")
        if keep_months:
            dscr = Ratio.of(Fraction(ebitda + uplift, ds)) if ds > 0 and ebitda + uplift > 0 else None
            lev = Ratio.of(Fraction(debt, 12 * ebitda)) if ebitda > 0 else None
            months.append(PlanMonth(month=m, cash_fen=cash, baseline_cash_fen=base, dscr=dscr, leverage=lev))
    return _Eval(admissible=failure is None, failure=failure, lowest_headroom=low_head or 0, lowest_month=low_month,
                 months=months)


def _choices(combo: Sequence[_Vec]) -> list[PlanChoice]:
    return [PlanChoice(project_id=v.project.id, label=v.project.label or v.project.id, included=not v.skip,
                       start_offset_months=v.offset, option=v.option, option_label=v.label,
                       first_payment_day=v.first_payment_day, principal_fen=v.principal_fen,
                       monthly_payment_fen=v.monthly_payment_fen) for v in combo]


def _text(choices: list[PlanChoice], npv: int, ev: _Eval) -> str:
    parts = []
    for c in choices:
        if not c.included:
            parts.append(f"leave {c.label} out")
            continue
        when = "now" if c.start_offset_months == 0 else f"{c.start_offset_months} months later"
        how = "from cash" if c.option == CASH else (f"with the {c.option_label}"
                                                     + (f" ({fmt_yuan(c.monthly_payment_fen)} a month)"
                                                        if c.monthly_payment_fen else ""))
        parts.append(f"{c.label} {when}, {how}")
    head = "; ".join(parts)
    tail = (f"NPV {fmt_yuan(npv)}; lowest headroom {fmt_yuan(ev.lowest_headroom)} in month {ev.lowest_month}"
            + ("" if ev.admissible else f"; fails: {ev.failure}"))
    return f"{head}. {tail}."


ASSUMPTIONS = (
    ("A monthly estimate, not the conservative daily test: before the plan, each month's free cash is monthly EBITDA "
     "less the existing debt service and less the payments of purchases already committed, from today's cash; the "
     "timing of receipts within a month is ignored. The first "
     "120 days of each contract are tested day by day by the capex screen (the best plan's contracts are re-run "
     "through it below)."),
    ("A financed option borrows the project's whole price, requested its lead time before the first payment falls due "
     "(never before today), so the proceeds land when they are needed; its service starts the month after they land. "
     "Uncommitted facilities are used as if granted, exactly as the capex screen does: applying for them is still the "
     "owner's step."),
    ("A month fails on cash only where the plan makes it lower than without it; DSCR counts the owner's uplift (an "
     "estimate) and leverage does not; the strictest limits apply, including every used facility's own covenants."),
    ("Plans are ranked on NPV to the owner at the hurdle of all their cash flows (payments, uplift, proceeds, service "
     "and fees) over every month they run, then on the higher lowest headroom."),
)


def plan(request: PlanRequest, state: FinancialState, mandate: Mandate, records: Sequence[ContractRecord], *,
         commitments: Sequence[Commitment] = ()) -> PlanResult:
    """The ranked permutations. PlanRefused for a request that cannot be read or is above `MAX_COMBINATIONS`."""
    ids = [p.id for p in request.projects]
    if len(set(ids)) != len(ids):
        raise PlanRefused("DUPLICATE_PROJECT", "each project needs its own id")
    books = current_books(state, commitments)
    st = books.state
    today = st.as_of_day
    by_id = {r.id: r for r in records}
    per_project: list[list[_Vec]] = []
    count = 1
    sized: list[tuple[PlanProject, list[tuple[int, int]], list[tuple[str, Facility | None]]]] = []
    for p in request.projects:
        if not p.start_offsets or any(o < 0 or o > request.horizon_months for o in p.start_offsets):
            raise PlanRefused("BAD_OFFSET", f"{p.id}: start offsets are months from 0 to the horizon")
        base = _payments(p, by_id, st)
        opts = _options(p, st, mandate)
        sized.append((p, base, opts))
        count *= len(set(p.start_offsets)) * len(opts) + (1 if p.optional else 0)
    if count > MAX_COMBINATIONS:
        raise PlanRefused("TOO_MANY_COMBINATIONS", f"{count:,} combinations is above the {MAX_COMBINATIONS:,} this reads; "
                                                   f"try fewer start months or options")
    # every vector runs long enough for all its flows (the longest term, life and offset), so NPV sees them all
    longest = max(request.horizon_months,
                  *(p.life_months + max(p.start_offsets) for p, _, _ in sized),
                  *(max(payment_month(d, today) for d, _ in base) + max(p.start_offsets)
                    + max(((f.term_months or 1) + f.lead_time_days // MONTH_DAYS + 2 for _, f in opts if f), default=0)
                    for p, base, opts in sized))
    disc = _discount(longest, request.hurdle_bp)
    for p, base, opts in sized:
        vecs = [_vector(p, o, oid, base, f, today, longest, disc) for o in sorted(set(p.start_offsets)) for oid, f in opts]
        if p.optional:
            vecs.append(_skip(p, longest))
        per_project.append(vecs)

    h = request.horizon_months
    ebitda = st.monthly_ebitda_fen
    ds0 = existing_debt_service(books, mandate, h)
    debt0 = _existing_debt(st, h)
    # purchases already committed (ADR-0013 CAPEX flows) are capital payments EBITDA does not hold: each comes off the
    # baseline in the month it falls (one due today in month 1), so a plan is never read against cash already promised
    committed = [0] * (h + 1)
    for f in st.flows:
        if f.kind == FlowKind.CAPEX and f.day >= today:
            m = payment_month(f.day, today)
            if m <= h:
                committed[max(1, m)] += f.amount_fen  # negative: an outflow
    baseline: list[int] = []
    cash = st.cash_fen
    for i in range(h):
        cash += ebitda - ds0[i] + committed[i + 1]
        baseline.append(cash)

    scored: list[tuple[Decimal, int, tuple[_Vec, ...], _Eval]] = []
    for combo in itertools.product(*per_project):
        ev = _evaluate(combo, baseline, ebitda, ds0, debt0, st, mandate, keep_months=False)
        scored.append((sum((v.npv for v in combo), Decimal(0)), ev.lowest_headroom, combo, ev))
    key = lambda t: (-t[0], -t[1], sum(v.charges for v in t[2]), [(v.project.id, v.offset, v.option) for v in t[2]])
    admissible = sorted((t for t in scored if t[3].admissible), key=key)
    everything = sorted(scored, key=key)

    def ranked(t: tuple[Decimal, int, tuple[_Vec, ...], _Eval], rank: int | None) -> RankedPlan:
        npv, _, combo, _ = t
        full = _evaluate(combo, baseline, ebitda, ds0, debt0, st, mandate, keep_months=True)
        choices = _choices(combo)
        with localcontext() as ctx:
            ctx.prec = NPV_PRECISION
            npv_fen = post(Fraction(npv))
        return RankedPlan(rank=rank, choices=choices, npv_fen=npv_fen, financing_charges_fen=sum(v.charges for v in combo),
                          lowest_headroom_fen=full.lowest_headroom, lowest_month=full.lowest_month,
                          admissible=full.admissible, first_failure=full.failure, months=full.months,
                          text=_text(choices, npv_fen, full))

    best = [ranked(t, i + 1) for i, t in enumerate(admissible[:TOP])]
    top = everything[0] if everything else None
    unconstrained = ranked(top, None) if top is not None and not top[3].admissible else None
    used = {(v.project.id, v.option) for t in admissible for v in t[2]}
    never = sorted({f"{v.project.id} / {v.option}" for vecs in per_project for v in vecs
                    if (v.project.id, v.option) not in used})
    checks = _daily_checks(admissible[0][2] if admissible else (), by_id, st, mandate, commitments)
    base_low = min(b - mandate.min_cash_fen for b in baseline)
    return PlanResult(horizon_months=h, combinations=len(scored), admissible_count=len(admissible), best=best,
                      best_unconstrained=unconstrained, never_admissible=never, baseline_lowest_headroom_fen=base_low,
                      daily_checks=checks, assumptions=list(ASSUMPTIONS))


def _signing_day(record: ContractRecord, state: FinancialState) -> int:
    """The signing day the schedule used without an owner's signing day: the contract's stated date, else today."""
    from app.contracts.derive import day_of

    signed = next((x for x in record.contract.terms if x.field.value == "SIGNED_DATE" and x.date), None) \
        if record.contract else None
    return day_of(signed.date, state.as_of) if signed is not None and signed.date else state.as_of_day


def _daily_checks(combo: Sequence[_Vec], records: dict[str, ContractRecord], state: FinancialState, mandate: Mandate,
                  commitments: Sequence[Commitment]) -> list[DailyCheck]:
    """The best plan's contract projects through the conservative daily screen, at the plan's start month."""
    from app.capex.buyside import CapexEstimate, evaluate_contract

    out = []
    for v in combo:
        p = v.project
        if v.skip or p.document_id is None or p.timeline is None:
            continue
        shift = v.offset * MONTH_DAYS
        t = p.timeline
        moved = Timeline(**{k: (getattr(t, k) + shift if getattr(t, k) is not None else None)
                            for k in ("signing_day", "delivery_day", "acceptance_day", "invoice_day",
                                      "retention_release_day")})
        if moved.signing_day is None:  # the plan shifted the signing payment from the day the schedule used
            moved = moved.model_copy(update={"signing_day": _signing_day(records[p.document_id], state) + shift})
        estimate = CapexEstimate(monthly_uplift_fen=p.monthly_uplift_fen, life_months=p.life_months + v.offset,
                                 uplift_start_month=_uplift_start(p, state.as_of_day) + v.offset)
        ev = evaluate_contract(records[p.document_id], moved, estimate, state, mandate, commitments=commitments)
        r = ev.evaluation
        if r is None:
            out.append(DailyCheck(project_id=p.id, document_id=p.document_id, selected_id=None, plan_option_passes=False,
                                  text=f"{p.label or p.id}: the daily screen has no schedule ({ev.summary})"))
            continue
        row = next((s for s in r.structures if s.facility_id == v.facility_id), None) if v.facility_id else None
        passes = None if row is None else row.feasible
        if v.facility_id is None:
            text = (f"{p.label or p.id}: from cash, the daily screen's cash + line row is "
                    f"{'feasible' if any(s.kind == 'CASH_LINE' and s.feasible for s in r.structures) else 'not feasible'}"
                    f"; its own choice is {r.selected_id or 'none'}.")
        else:
            text = (f"{p.label or p.id}: the plan's {v.label} {'passes' if passes else 'does not pass'} the daily test"
                    + (f" ({row.note})" if row is not None and not passes else "") + ".")
        out.append(DailyCheck(project_id=p.id, document_id=p.document_id, selected_id=r.selected_id,
                              plan_option_passes=passes, text=text))
    return out


__all__ = ["CASH", "MAX_COMBINATIONS", "PlanChoice", "PlanProject", "PlanRefused", "PlanRequest", "PlanResult",
           "RankedPlan", "plan"]
