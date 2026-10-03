"""Candidate generation and evaluation for the funding router.

The router never computes cash itself: every candidate is a list of FundingActions run through
`financial.project`, and its cost is what that trajectory posts (interest + fees + discounts, net of
what the offer alone already posts). Admissibility is decided from the same trajectory:

- closing cash >= mandate.min_cash_fen on every day;
- no `covenants.evaluate` violation (the committed facilities plus any facility the plan uses);
- `mandate.allow_new_borrowing` when any debt source is used.

The rate ceiling (`mandate.max_apr_bp`) is not an admissibility rule: it decides who may run the plan. An action
whose effective annual cost (`funding.rates.action_rate`, the number the executor's admission tests) is above the
ceiling makes its plan `needs_approval`: still admissible, but the owner must approve that leg. A plan that needs
no approval always ranks before one that does, whatever the cost difference (the agent must be able to act alone
when it can); among plans of the same class the cheapest comes first.

Timing follows ADR-0003: every source is requested on day 0 and lands after its lead time; the router
searches amounts, not dates. A bullet credit line is repaid on an inflow day after the gap opens (the
day the baseline recovers, or an earlier receipt when another source carries the rest; EV-06).
No action is smaller than MIN_ACTION_FEN (EV-11).

Speed: the search steers on `financial.project_cash`, which books exactly the postings `project`
books and returns the same closing cash, peak debt and posted costs without building the display
trajectory (a `Probe`). A probe that breaches the floor or borrows against the
mandate is inadmissible whatever the covenants say; any other probe that could become the best plan
is re-run through the full `project` and `covenants.evaluate` (`Search.evaluate`) before it is
accepted. So the chosen plan is the one the full evaluation of every candidate would choose.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from fractions import Fraction
from itertools import permutations

from app.covenants import evaluate as evaluate_covenants
from app.domain.models import (
    CostLine,
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
    Violation,
    ViolationCode,
)
from app.domain.money import DAYS_PER_YEAR, bp, fmt_yuan, gross_up_face
from app.financial import (
    EngineError,
    UncommittedFacilityError,
    project,
    project_cash,
    recurring_receivable_id,
)
from app.financial.fmt import y
from app.funding.legs import as_executed, carries, leg_violations
from app.funding.rates import (
    MONTH_DAYS,
    action_rate,
    approval_reason,
    invoice_landing_day,
    is_debt,
    pct,
    receipt_covered_advance,
    tier3_reasons,
)

GRID_STEP_FEN = 1_000_000  # ¥10,000
MIN_ACTION_FEN = 100_000  # ¥1,000: the smallest draw, advance, early payment or bill discount the router proposes
EXPECTED_PROBE_BUDGET = 2_000  # candidates the display-only EXPECTED search may try (EV-07)
DEFAULT_BILL_MONTHS = 6  # a held bill's maturity when the facility gives no term (6-month 国股 bill)
COST_KINDS = (LedgerEventKind.INTEREST, LedgerEventKind.FEE, LedgerEventKind.DISCOUNT)
INFLOW_KINDS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT, LedgerEventKind.FLOW)


def usable_statuses(basis: str) -> frozenset[FacilityStatus]:
    if basis == "COMMITTED":
        return frozenset({FacilityStatus.COMMITTED})
    if basis == "EXPECTED":
        return frozenset({FacilityStatus.COMMITTED, FacilityStatus.PENDING, FacilityStatus.NOT_APPLIED})
    raise ValueError(f"unknown basis {basis!r}; use 'COMMITTED' or 'EXPECTED'")


def expected_state(state: FinancialState) -> FinancialState:
    """What-if copy for the EXPECTED basis: owner-approved NOT_APPLIED facilities are treated as
    applied (PENDING), so the engine's EXPECTED mode may draw them. Never used for a hard constraint
    (INVARIANT 11); the input state is not modified."""
    facilities = [
        f.model_copy(update={"status": FacilityStatus.PENDING})
        if f.owner_approved and f.status == FacilityStatus.NOT_APPLIED
        else f
        for f in state.facilities
    ]
    return state.model_copy(update={"facilities": facilities})


# ---------------------------------------------------------------- receivables seen by the engine


@dataclass(frozen=True)
class RcvInfo:
    id: str
    counterparty_id: str
    issue_day: int
    due_day: int
    open_fen: int  # what the engine expects to receive on the due day


def receivables(state: FinancialState, baseline: Trajectory) -> dict[str, RcvInfo]:
    """Receivables with a dated receipt in the baseline trajectory (so terms changes, early
    settlements and conservative-mode exclusions are the engine's, not re-derived here)."""
    issue: dict[str, tuple[str, int]] = {r.id: (r.counterparty_id, r.issue_day) for r in state.receivables}
    for ri in state.recurring_invoices:
        if ri.every_days <= 0:
            continue
        d = ri.next_issue_day
        while d <= baseline.horizon_days:
            issue[recurring_receivable_id(ri.counterparty_id, d)] = (ri.counterparty_id, d)
            d += ri.every_days
    out: dict[str, RcvInfo] = {}
    for point in baseline.days:
        for ev in point.events:
            if ev.kind == LedgerEventKind.RECEIPT and ev.ref in issue and ev.amount_fen > 0:
                cp, issued = issue[ev.ref]
                out[ev.ref] = RcvInfo(ev.ref, cp, issued, point.day, ev.amount_fen)
    return out


# ---------------------------------------------------------------- slots: one way to use one facility


@dataclass(frozen=True, eq=False)
class Slot:
    """One way to use one facility (a line repaid on a given day, an advance on a given receivable...)."""

    facility: Facility
    kind: FundingActionKind
    arrival: int
    cap_fen: int
    receivable_id: str | None = None
    repay_day: int | None = None
    rate_bp: int | None = None
    days_early: int | None = None  # EARLY_PAY: due day − arrival
    expected: bool = False
    request_day: int = 0  # today (state.as_of_day): funding is requested today, never in the past

    def action(self, amount_fen: int) -> FundingAction:
        return FundingAction(
            kind=self.kind,
            facility_id=self.facility.id,
            day=self.request_day,
            amount_fen=amount_fen,
            receivable_id=self.receivable_id,
            repay_day=self.repay_day,
            rate_bp=self.rate_bp,
        )

    def amount_for_net(self, net_fen: int) -> int:
        """Amount (face for early pay and bills) whose cash on arrival nets `net_fen`."""
        if self.kind == FundingActionKind.EARLY_PAY:
            return gross_up_face(net_fen, bp(self.rate_bp or 0))
        if self.kind == FundingActionKind.DISCOUNT_BILL:
            days = (self.repay_day or 0) - self.arrival
            return gross_up_face(net_fen, bp(self.rate_bp or 0) * days / DAYS_PER_YEAR)
        if self.facility.upfront_fee_bp:
            return gross_up_face(net_fen, bp(self.facility.upfront_fee_bp))
        return net_fen

    def conflicts(self, other: Slot) -> bool:
        if self.receivable_id is not None and self.receivable_id == other.receivable_id:
            return True
        same_fac = self.facility.id == other.facility.id
        return same_fac and self.kind in (FundingActionKind.DRAW, FundingActionKind.DISCOUNT_BILL)

    @property
    def sort_key(self) -> tuple:
        return (self.facility.id, self.kind.value, self.receivable_id or "", self.repay_day or 0)


# ---------------------------------------------------------------- evaluation


@dataclass
class Eval:
    actions: tuple[FundingAction, ...]
    traj: Trajectory | None = None
    error: str | None = None
    cost: int | None = None
    violations: list[Violation] = field(default_factory=list)
    breach_day: int | None = None
    shortfall: int = 0
    peak_debt: int = 0
    # per action (`_akey`): why it needs the owner (effective annual cost above the max APR); empty = autonomous
    approvals: dict[tuple, str] = field(default_factory=dict)
    # per action (`_akey`): why the executor cannot run it today (an advance on an invoice that is not issued yet)
    unrunnable: dict[tuple, str] = field(default_factory=dict)

    @property
    def admissible(self) -> bool:
        return self.traj is not None and not self.violations

    @property
    def needs_approval(self) -> bool:
        return bool(self.approvals)

    @property
    def cls(self) -> tuple[bool, bool]:
        """What a plan can do before cost: (cannot run today, needs the owner). False sorts first."""
        return (bool(self.unrunnable), bool(self.approvals))

    @property
    def reasons(self) -> list[ViolationCode]:
        seen: list[ViolationCode] = []
        for v in self.violations:
            if v.code not in seen:
                seen.append(v.code)
        return seen

    def rank(self) -> tuple:
        return (*self.cls, self.cost, len(self.actions), self.peak_debt, action_key(self.actions))


class _BudgetSpent(Exception):
    """The EXPECTED search has tried its budget of candidates."""


@dataclass
class Probe:
    """A candidate on the cash-only fast path: what steers the search, and whether the plan is
    already inadmissible without looking at covenants (`blocked`)."""

    actions: tuple[FundingAction, ...]
    ok: bool  # the engine accepted the actions (Eval.traj is not None)
    cost: int | None = None
    breach_day: int | None = None
    shortfall: int = 0
    peak_debt: int = 0
    blocked: bool = False  # known inadmissible (reserve breach, no new borrowing, or evaluated)
    needs_approval: bool = False  # some action is above the max APR: the owner must approve the plan
    unrunnable: bool = False  # some action cannot run today

    @property
    def cls(self) -> tuple[bool, bool]:
        return (self.unrunnable, self.needs_approval)

    def rank(self) -> tuple:
        return (*self.cls, self.cost, len(self.actions), self.peak_debt, action_key(self.actions))


def _akey(a: FundingAction) -> tuple:
    return (a.kind.value, a.facility_id, a.day, a.amount_fen, a.receivable_id or "", a.repay_day or -1, a.rate_bp or -1)


def action_key(actions: tuple[FundingAction, ...] | list[FundingAction]) -> tuple:
    return tuple(sorted(_akey(a) for a in actions))


def plan_id(basis: str, actions: list[FundingAction], state: FinancialState, mandate: Mandate) -> str:
    payload = json.dumps(
        {"basis": basis, "actions": [list(k) for k in action_key(actions)],
         "state": [state.org_id, state.state_version], "mandate": mandate.version},
        sort_keys=True,
    )
    return f"PLAN-{basis[:3]}-{hashlib.sha256(payload.encode()).hexdigest()[:12]}"


def _cost_total(t: Trajectory) -> int:
    return t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen


def reserve_violation(t: Trajectory, floor: int, note: str = "") -> Violation | None:
    below = [p for p in t.days if p.closing_fen < floor]
    if not below:
        return None
    first = below[0]
    worst = min(below, key=lambda p: (p.closing_fen, p.day))
    shortfall = floor - first.closing_fen
    return Violation(
        code=ViolationCode.RESERVE_BREACH,
        message=f"Projected cash falls below the reserve on day {first.day}{note}",
        day=first.day,
        observed=fmt_yuan(first.closing_fen),
        limit=fmt_yuan(floor),
        formula=(
            f"closing_cash(day {first.day}) >= min_cash: {fmt_yuan(first.closing_fen)} < {fmt_yuan(floor)}, "
            f"shortfall {fmt_yuan(shortfall)}"
        ),
        inputs={
            "day": str(first.day),
            "closing_cash": fmt_yuan(first.closing_fen),
            "min_cash": fmt_yuan(floor),
            "shortfall": fmt_yuan(shortfall),
            "max_shortfall": fmt_yuan(floor - worst.closing_fen),
            "max_shortfall_day": str(worst.day),
            "mode": t.mode.value,
        },
    )


class Search:
    """One router run: baseline, slots, a projection cache and the grid search.

    Rules (class attributes, so a test can pin the earlier behaviour and compare it with the frozen
    reference search):
    - LINE_REPAY_ON_ANY_INFLOW (EV-06): a bullet line may be repaid on any day after the gap opens on
      which cash comes in (a receipt, an early receipt or a positive flow), not only on the days the
      unfunded baseline recovers; another source can carry the rest of the gap after an earlier repayment.
    - MIN_ACTION_FEN (EV-11): no action is smaller than ¥1,000. A smaller residual is rounded up to
      it (never above the source's capacity), and a source with less than ¥1,000 available is not used.
    - EXPECTED_PROBE_BUDGET (EV-07): the EXPECTED basis is display-only (INVARIANT 11), so its grid
      search stops after this many candidates and keeps the best found (`capped`). The COMMITTED
      search, which hard constraints rely on, is never capped.
    """

    LINE_REPAY_ON_ANY_INFLOW = True
    MIN_ACTION_FEN = MIN_ACTION_FEN
    EXPECTED_PROBE_BUDGET: int | None = EXPECTED_PROBE_BUDGET

    def __init__(self, state: FinancialState, obligations: list[Obligation], mandate: Mandate, basis: str) -> None:
        self.basis = basis
        self.statuses = usable_statuses(basis)
        self.mode = Mode.CONSERVATIVE if basis == "COMMITTED" else Mode.EXPECTED
        self.state = state
        self.pstate = state if basis == "COMMITTED" else expected_state(state)
        self.obligations = obligations
        self.mandate = mandate
        self.floor = mandate.min_cash_fen
        self.facilities = {f.id: f for f in state.facilities}
        self._cache: dict[tuple, Eval] = {}
        self._probes: dict[tuple, Probe] = {}
        self._rule_cache: dict[tuple, bool] = {}  # per action: no new borrowing
        self._approval_cache: dict[tuple, str | None] = {}  # per action: why it needs the owner
        self._executed: dict[tuple, Trajectory | None] = {}  # per set of legs: the books right after they execute
        self._orders: dict[tuple, tuple[list[FundingAction] | None, tuple[FundingAction, str] | None]] = {}
        self.baseline = project(self.pstate, obligations, [], self.mode, mandate.horizon_days, self.floor)
        self.base_cost = _cost_total(self.baseline)
        below = [p for p in self.baseline.days if p.closing_fen < self.floor and p.day >= state.as_of_day]
        self.breach_days = [p.day for p in below]
        self.need_fen = max((self.floor - p.closing_fen for p in below), default=0)
        self.rcvs = receivables(state, self.baseline)
        self._over_cache: dict[tuple, bool] = {}
        # what the executor lets a facility finance, and lands today: an invoice that exists and is issued (a recurring
        # invoice not yet issued does not exist; the executor lands an advance on a future-dated one today, the
        # engine on its issue day), is OPEN, buyer-confirmed and owed by a registered buyer
        buyers = {c.id for c in state.counterparties if c.role == "BUYER" and c.known}
        self.financeable = {r.id for r in state.receivables if r.status == "OPEN" and r.confirmed
                            and r.issue_day <= state.as_of_day and r.counterparty_id in buyers}
        self.slots = self._slots() if below else []
        self.best: Eval | None = None
        self._best_effort: Eval | Probe | None = None
        self.unit: dict[Slot, Fraction] = {}  # probed cost per fen of net cash raised
        self.unit_amt: dict[Slot, Fraction] = {}  # probed cost per fen of action amount (face)
        self.capped = False  # the EXPECTED search stopped at its budget
        self._budget = self.EXPECTED_PROBE_BUDGET if basis != "COMMITTED" else None

    # ------------------------------------------------------------ slots

    @property
    def first_breach(self) -> int | None:
        return self.breach_days[0] if self.breach_days else None

    def recovery_days(self) -> list[int]:
        days = self.baseline.days
        return [
            days[i].day for i in range(1, len(days))
            if days[i].closing_fen >= self.floor and days[i - 1].closing_fen < self.floor
        ]

    def line_repay_days(self) -> list[int]:
        """Candidate repayment days for a bullet line: the baseline's recovery days and (EV-06) every
        later day on which cash comes in."""
        days = set(self.recovery_days())
        if self.LINE_REPAY_ON_ANY_INFLOW:
            first = self.breach_days[0]
            days |= {p.day for p in self.baseline.days
                     if p.day > first and any(e.amount_fen > 0 and e.kind in INFLOW_KINDS for e in p.events)}
        return sorted(days)

    def ticket(self, slot: Slot, amount: int) -> int:
        """`amount` raised to the minimum ticket and capped at the slot's capacity."""
        return min(slot.cap_fen, max(self.MIN_ACTION_FEN, amount))

    def early_pay_bp(self, f: Facility) -> int:
        """The buyer's standing early-payment rate. A discount an offer puts on one invoice is not a standing
        rate for other money: an offer's own early-pay leg is already in the books as an obligation, and the
        router never extends it to other faces or invoices (ADR-0007, implementation notes)."""
        return f.rate_bp

    def usable(self, f: Facility) -> bool:
        return (f.owner_approved and f.status in self.statuses and not tier3_reasons(f)
                and f.kind != FacilityKind.EQUITY and f.limit_fen - f.drawn_fen > 0)

    def _slots(self) -> list[Slot]:
        first, last = self.breach_days[0], self.breach_days[-1]
        out: list[Slot] = []
        for f in sorted(self.state.facilities, key=lambda x: x.id):
            if not self.usable(f):
                continue
            avail = f.limit_fen - f.drawn_fen
            exp = f.status != FacilityStatus.COMMITTED
            today = self.state.as_of_day
            lead = today + f.lead_time_days  # the day cash lands when requested today
            match f.kind:
                case FacilityKind.CREDIT_LINE if f.repayment == Repayment.BULLET:
                    for r in self.line_repay_days():
                        if r > lead:
                            out.append(Slot(f, FundingActionKind.DRAW, lead, avail, repay_day=r, expected=exp,
                                            request_day=today))
                case FacilityKind.INVOICE_FINANCING:
                    for r in self.rcvs.values():
                        arrival = max(today, r.issue_day) + f.lead_time_days
                        if arrival < r.due_day and arrival <= last and r.due_day > first:
                            cap = r.open_fen if f.advance_rate_bp is None else f.advance_rate_bp * r.open_fen // 10_000
                            cap = receipt_covered_advance(f, cap, r.open_fen, r.due_day - arrival)
                            if min(cap, avail) > 0:
                                out.append(Slot(f, FundingActionKind.FINANCE_INVOICE, arrival, min(cap, avail),
                                                receivable_id=r.id, expected=exp, request_day=today))
                case FacilityKind.BUYER_EARLY_PAY:
                    rate = self.early_pay_bp(f)
                    for r in self.rcvs.values():
                        arrival = max(today, r.issue_day) + f.lead_time_days
                        if (r.counterparty_id == f.lender_id and arrival < r.due_day and arrival <= last
                                and r.due_day > first):
                            out.append(Slot(f, FundingActionKind.EARLY_PAY, arrival, min(r.open_fen, avail),
                                            receivable_id=r.id, rate_bp=rate, days_early=r.due_day - arrival,
                                            expected=exp, request_day=today))
                case FacilityKind.BANK_ACCEPTANCE_BILL:
                    maturity = today + MONTH_DAYS * (f.term_months or DEFAULT_BILL_MONTHS)
                    if maturity > lead and lead <= last:
                        out.append(Slot(f, FundingActionKind.DISCOUNT_BILL, lead, avail, repay_day=maturity,
                                        rate_bp=f.rate_bp, expected=exp, request_day=today))
                case FacilityKind.CREDIT_LINE:
                    pass
                case _:
                    # term loans and leases: drawn on day 0, repaid on their own schedule
                    if f.term_months and f.repayment in (Repayment.BULLET, Repayment.AMORTISING) and lead <= last:
                        out.append(Slot(f, FundingActionKind.DRAW, lead, avail, expected=exp, request_day=today))
        return sorted((s for s in out if s.cap_fen >= self.MIN_ACTION_FEN), key=lambda s: s.sort_key)

    # ------------------------------------------------------------ evaluation

    def action_pricing(self, a: FundingAction) -> tuple[Fraction, str]:
        """(annual cost, how) of one action, from `funding.rates.action_rate`: the number the executor's
        admission compares with the mandate's ceiling (an advance on the days from landing to due)."""
        f = self.facilities[a.facility_id]
        r = self.rcvs.get(a.receivable_id or "")
        landing = invoice_landing_day(f, a.day, r.issue_day) if r is not None else None
        return action_rate(f, a.kind, amount_fen=a.amount_fen, landing_day=landing,
                           due_day=r.due_day if r is not None else None, rate_bp=a.rate_bp)

    def action_rate(self, a: FundingAction) -> Fraction:
        return self.action_pricing(a)[0]

    def unrunnable(self, a: FundingAction) -> str | None:
        """Why the executor cannot run this action today: an advance needs an invoice that exists and is issued
        (the engine lands an advance on a recurring invoice not yet issued on its issue day; the executor
        refuses it, and lands one on a future-dated invoice today). No operation asks a buyer to pay early or
        discounts a bill, so a plan with such a leg cannot run today either: it is a price, not an execution."""
        if a.kind == FundingActionKind.EARLY_PAY:
            return "needs the buyer's agreement to pay early"
        if a.kind == FundingActionKind.DISCOUNT_BILL:
            return "needs a bill in hand"
        if a.kind != FundingActionKind.FINANCE_INVOICE or a.receivable_id in self.financeable:
            return None
        r = self.rcvs.get(a.receivable_id or "")
        when = f"; it is issued on day {r.issue_day}" if r is not None and r.issue_day > self.state.as_of_day else ""
        return f"{a.receivable_id} is not an invoice the executor can finance today{when}"

    def approval(self, a: FundingAction) -> str | None:
        """Why this action needs the owner's approval: its effective annual cost is above the mandate's ceiling."""
        k = _akey(a)
        if k not in self._approval_cache:
            rate, how = self.action_pricing(a)
            self._approval_cache[k] = approval_reason(rate, how, self.mandate)
        return self._approval_cache[k]

    def binding_facilities(self, actions: tuple[FundingAction, ...]) -> list[Facility]:
        used = {a.facility_id for a in actions}
        return [f for f in self.pstate.facilities if f.status == FacilityStatus.COMMITTED or f.id in used]

    def evaluate(self, actions: list[FundingAction] | tuple[FundingAction, ...]) -> Eval:
        acts = tuple(actions)
        key = action_key(acts)
        hit = self._cache.get(key)
        if hit is not None:
            return hit if hit.actions == acts else replace(hit, actions=acts)
        ev = Eval(actions=acts)
        try:
            t = project(self.pstate, self.obligations, list(acts), self.mode, self.mandate.horizon_days, self.floor)
        except UncommittedFacilityError as e:
            ev.error = str(e)
            ev.violations = [Violation(code=ViolationCode.UNCOMMITTED_FACILITY, message=str(e))]
            self._cache[key] = ev
            return ev
        except EngineError as e:
            ev.error = str(e)
            self._cache[key] = ev
            return ev
        ev.traj = t
        ev.cost = _cost_total(t) - self.base_cost
        ev.peak_debt = max(p.debt_outstanding_fen for p in t.days)
        below = [p for p in t.days if p.closing_fen < self.floor]
        if below:
            ev.breach_day = below[0].day
            ev.shortfall = max(self.floor - p.closing_fen for p in below)
            rv = reserve_violation(t, self.floor)
            if rv is not None:
                ev.violations.append(rv)
        ev.violations.extend(evaluate_covenants(t, self.binding_facilities(acts), self.mandate))
        if not ev.violations:
            ev.violations.extend(self._carried_line_ratios(acts))
        for a in acts:
            no = self.unrunnable(a)
            if no is not None:
                ev.unrunnable[_akey(a)] = no
            why = self.approval(a)
            if why is not None:
                ev.approvals[_akey(a)] = why
        if self.basis == "COMMITTED" and not ev.violations and acts:
            order, refused = self.executable_order(acts)
            if order is None and refused is not None:
                a, why = refused
                k = _akey(a)
                # the owner cannot approve past a hard rule, so this is "cannot run today", not "needs approval"
                note = (f"only admissible as a whole: no order of its legs lets each run alone on the books the legs "
                        f"before it leave (admission refuses this one: {why})")
                ev.unrunnable[k] = f"{ev.unrunnable[k]}; {note}" if k in ev.unrunnable else note
        if not self.mandate.allow_new_borrowing and any(is_debt(self.facilities[a.facility_id]) for a in acts):
            ev.violations.append(Violation(
                code=ViolationCode.NEW_BORROWING_NOT_ALLOWED,
                message="The mandate does not allow new borrowing",
                formula="allow_new_borrowing = false",
            ))
        self._cache[key] = ev
        return ev

    def _carried_line_ratios(self, acts: tuple[FundingAction, ...]) -> list[Violation]:
        """DSCR and leverage as admission will judge the plan's later legs. A line draw names a repayment day here,
        but once executed it is a lot with none: admission (and every later projection) carries it and assumes it
        repaid on the first affordable receipt day (`carry_draw`, ADR-0010 §5), which can move its interest into
        another month. A plan whose ratios hold only with the line held to the day it names would have a later leg
        refused, so it is judged on that reading too (`legs.as_executed`). COMMITTED plans only: they are the ones
        the executor runs."""
        if self.basis != "COMMITTED" or not any(carries(a, self.pstate) for a in acts):
            return []
        t = self.executed(acts)
        if t is None:
            return []
        return [v for v in evaluate_covenants(t, self.binding_facilities(acts), self.mandate)
                if v.code in (ViolationCode.DSCR_BREACH, ViolationCode.LEVERAGE_BREACH)]

    def executed(self, acts: tuple[FundingAction, ...] | list[FundingAction]) -> Trajectory | None:
        """The projection of the books right after `acts` execute today, as admission reads them
        (`legs.as_executed`: a line draw is a carried lot); None when the engine cannot project them."""
        key = action_key(acts)
        if key not in self._executed:
            if not acts:
                self._executed[key] = self.baseline
            else:
                state, rest = as_executed(self.pstate, acts, "plan-line")
                try:
                    self._executed[key] = project(state, self.obligations, rest, self.mode,
                                                  self.mandate.horizon_days, self.floor)
                except EngineError:
                    self._executed[key] = None
        return self._executed[key]

    def refused(self, earlier: tuple[FundingAction, ...], a: FundingAction) -> str | None:
        """Why admission refuses leg `a` run on the books the `earlier` legs leave (`legs.leg_violations`, the rule
        admission applies); None when it admits it."""
        after = self.executed((*earlier, a))
        if after is None:
            return "the engine cannot project the books after it"
        found = leg_violations(self.pstate, self.executed(earlier), after, a.kind, self.mandate)
        return found[0].message if found else None

    def executable_order(self, acts: tuple[FundingAction, ...] | list[FundingAction]
                         ) -> tuple[list[FundingAction] | None, tuple[FundingAction, str] | None]:
        """(an order in which every leg is admitted on the books the legs before it leave, None when there is none;
        the first leg refused in presentation order and why, when there is none). The executor admits a plan leg by
        leg, so a plan is presented in such an order: by landing day where that works, else the first permutation
        of it that does."""
        key = action_key(acts)
        if key not in self._orders:
            first: tuple[FundingAction, str] | None = None
            found: list[FundingAction] | None = None
            for perm in permutations(self._by_landing(acts)):
                for i, a in enumerate(perm):
                    why = self.refused(perm[:i], a)
                    if why is not None:
                        first = first or (a, why)
                        break
                else:
                    found = list(perm)
                    break
            self._orders[key] = (found, None if found is not None else first)
        found, first = self._orders[key]
        if found is None:
            return None, first
        by_key = {_akey(a): a for a in acts}
        return [by_key[_akey(a)] for a in found], None

    def _breaks_rules(self, a: FundingAction) -> bool:
        """The action alone makes any plan inadmissible: new debt the mandate forbids (the same check
        `evaluate` makes, without the trajectory)."""
        k = _akey(a)
        hit = self._rule_cache.get(k)
        if hit is None:
            hit = not self.mandate.allow_new_borrowing and is_debt(self.facilities[a.facility_id])
            self._rule_cache[k] = hit
        return hit

    def probe(self, actions: list[FundingAction] | tuple[FundingAction, ...]) -> Probe:
        """`evaluate` on the cash-only fast path (no covenants): the same cost, breach day,
        shortfall and peak debt, and whether the engine accepts the actions at all."""
        acts = tuple(actions)
        key = action_key(acts)
        hit = self._probes.get(key)
        if hit is not None:
            return hit if hit.actions == acts else replace(hit, actions=acts)
        if self._budget is not None and len(self._probes) >= self._budget:
            raise _BudgetSpent
        full = self._cache.get(key)
        if full is not None:
            pr = Probe(acts, ok=full.traj is not None, cost=full.cost, breach_day=full.breach_day,
                       shortfall=full.shortfall, peak_debt=full.peak_debt,
                       blocked=full.traj is not None and not full.admissible, needs_approval=full.needs_approval,
                       unrunnable=bool(full.unrunnable))
            self._probes[key] = pr
            return pr
        try:
            path = project_cash(self.pstate, self.obligations, list(acts), self.mode, self.mandate.horizon_days,
                                self.floor)
        except EngineError:  # includes UncommittedFacilityError; `evaluate` gives no trajectory either
            pr = Probe(acts, ok=False)
            self._probes[key] = pr
            return pr
        floor = self.floor
        breach_day = next((d for d, c in enumerate(path.closings) if c < floor), None)
        shortfall = 0
        if breach_day is not None:
            shortfall = floor - min(path.closings)
        blocked = breach_day is not None or any(self._breaks_rules(a) for a in acts)
        pr = Probe(acts, ok=True, cost=path.cost_fen - self.base_cost, breach_day=breach_day, shortfall=shortfall,
                   peak_debt=path.peak_debt_fen, blocked=blocked,
                   needs_approval=any(self.approval(a) is not None for a in acts),
                   unrunnable=any(self.unrunnable(a) is not None for a in acts))
        self._probes[key] = pr
        return pr

    @property
    def best_effort(self) -> Eval | None:
        """The inadmissible candidate with the smallest shortfall (then rank), fully evaluated. It
        is tracked only while no admissible plan is known: it is read only when there is none."""
        be = self._best_effort
        if be is None or isinstance(be, Eval):
            return be
        return self.evaluate(be.actions)

    def consider(self, ev: Eval | Probe) -> None:
        """Keep the best admissible candidate by rank and, while there is none, the best effort."""
        if isinstance(ev, Probe):
            if not ev.ok:
                return
            if ev.blocked:
                self._keep_best_effort(ev)
                return
            if self.best is not None and ev.rank() >= self.best.rank():
                return  # it cannot become the best, and the best effort no longer matters
            ev = self.evaluate(ev.actions)  # it could become the best: the full evaluation decides
        if ev.traj is None:
            return
        if ev.admissible:
            if self.best is None or ev.rank() < self.best.rank():
                self.best = ev
        else:
            self._keep_best_effort(ev)

    def _keep_best_effort(self, ev: Eval | Probe) -> None:
        if self.best is not None:
            return
        be = self._best_effort
        if be is None or (ev.shortfall, ev.rank()) < (be.shortfall, be.rank()):
            self._best_effort = ev

    # ------------------------------------------------------------ grid search

    def fill(self, prefix: list[FundingAction], slot: Slot, prune: bool = True) -> Probe | None:
        """Add `slot` for exactly the residual the prefix leaves (iterating on any shortfall the
        added source's own postings cause), capped at the slot's capacity."""
        pe = self.probe(prefix) if prefix else None
        if pe is not None:
            if not pe.ok:
                return None
            self.consider(pe)
            if pe.breach_day is None:
                return None  # the prefix alone covers the gap
            base_cost, short, first = pe.cost or 0, pe.shortfall, pe.breach_day
        else:
            base_cost, short, first = 0, self.need_fen, self.breach_days[0]
        if first < slot.arrival:
            return None  # the cash would land after the breach
        if prune and slot in self.unit and self._beaten(
                base_cost + self._lb(slot, short, net=True), [*prefix, slot.action(slot.cap_fen)]):
            return None
        net = short
        ev: Probe | None = None
        for _ in range(4):
            amount = self.ticket(slot, slot.amount_for_net(net))
            ev = self.probe([*prefix, slot.action(amount)])
            self.consider(ev)
            if not ev.ok or ev.breach_day is None or amount == slot.cap_fen or ev.breach_day < slot.arrival:
                break
            net += ev.shortfall
        return ev

    def _grid(self, cap: int) -> list[int]:
        return [*range(GRID_STEP_FEN, cap, GRID_STEP_FEN), cap]

    def _probe_units(self) -> None:
        for s in self.slots:
            amount = self.ticket(s, s.amount_for_net(self.need_fen))
            ev = self.probe([s.action(amount)])
            self.consider(ev)
            if not ev.ok or ev.cost is None:
                continue
            net = amount - ev.cost if s.kind in (FundingActionKind.EARLY_PAY, FundingActionKind.DISCOUNT_BILL) else amount
            if net > 0:
                self.unit[s] = Fraction(ev.cost, net)
                self.unit_amt[s] = Fraction(ev.cost, amount)

    def run(self) -> None:
        if not self.breach_days:
            return
        try:
            self._search()
        except _BudgetSpent:
            self.capped = True
        finally:
            self._budget = None  # the presentation that follows (alternatives, cost lines) is not capped

    def _search(self) -> None:
        self._probe_units()
        slots = [s for s in self.slots if s in self.unit
                 and (self.mandate.allow_new_borrowing or not is_debt(s.facility))]
        for s in slots:
            self.fill([], s)
        for a in slots:
            for b in slots:
                if a is b or a.conflicts(b):
                    continue
                for amt in self._grid(a.cap_fen):
                    if not self._beaten(self._lb(a, amt), [a.action(amt)]):
                        self.fill([a.action(amt)], b)
        for a in slots:
            for b in slots:
                if a is b or a.conflicts(b):
                    continue
                for c in slots:
                    if c is a or c is b or c.conflicts(a) or c.conflicts(b):
                        continue
                    for amt in self._grid(b.cap_fen):
                        if not self._beaten(self._lb(a, a.cap_fen) + self._lb(b, amt),
                                            [a.action(a.cap_fen), b.action(amt)]):
                            self.fill([a.action(a.cap_fen), b.action(amt)], c)

    def _lb(self, slot: Slot, amount: int, net: bool = False) -> Fraction:
        """A lower bound on what `slot` posts for an action `amount` (or, with `net`, for raising
        that much cash): its probed unit cost, less a 2% margin and 2 fen for rounding."""
        unit = self.unit[slot] if net else self.unit_amt[slot]
        return unit * amount * Fraction(98, 100) - 2

    def _over(self, a: FundingAction) -> bool:
        """The action is certainly above the max APR, whatever fen rounding does to its amount (1% clear of the
        ceiling): a plan that holds it is certainly one that needs approval."""
        k = _akey(a)
        hit = self._over_cache.get(k)
        if hit is None:
            hit = self.action_rate(a) > bp(self.mandate.max_apr_bp) * Fraction(101, 100)
            self._over_cache[k] = hit
        return hit

    def _cls(self, actions: list[FundingAction]) -> tuple[bool, bool]:
        """The class a plan holding `actions` is certain to be in (it can only get worse as actions are added)."""
        return (any(self.unrunnable(a) is not None for a in actions), any(self._over(a) for a in actions))

    def _beaten(self, bound: Fraction, actions: list[FundingAction] = ()) -> bool:  # type: ignore[assignment]
        """A candidate holding `actions` that posts at least `bound` cannot beat the best plan: plans rank by (cannot
        run today, needs approval, cost). It is beaten when its certain class is worse than the best's, or the same
        and it is dearer; a candidate not known to be in a worse class is never beaten by a better-class best."""
        best = self.best
        if best is None or best.cost is None:
            return False
        mine = self._cls(list(actions))
        if mine != best.cls:
            return mine > best.cls
        return bound > best.cost

    # ------------------------------------------------------------ presentation helpers

    def landing_day(self, a: FundingAction) -> int:
        f = self.facilities[a.facility_id]
        r = self.rcvs.get(a.receivable_id or "")
        return max(a.day, r.issue_day if r is not None else a.day) + f.lead_time_days

    def _by_landing(self, actions: tuple[FundingAction, ...] | list[FundingAction]) -> list[FundingAction]:
        return sorted(actions, key=lambda a: (self.landing_day(a), _akey(a)))

    def ordered(self, actions: tuple[FundingAction, ...] | list[FundingAction]) -> list[FundingAction]:
        """Presentation order: by the day the cash lands, then facility id; for an admissible COMMITTED plan, the
        first such order in which every leg is admitted on the books the legs before it leave
        (`executable_order`), since the executor runs the legs in the order shown."""
        if self.basis == "COMMITTED" and actions and self.evaluate(self._by_landing(actions)).admissible:
            order, _ = self.executable_order(actions)
            if order is not None:
                return order
        return self._by_landing(actions)

    def cost_lines(self, ev: Eval) -> list[CostLine]:
        """One CostLine per action: its posted interest, fees and discounts, with the engine's formulas."""
        if ev.traj is None:
            return []
        groups: dict[int, list[tuple[int, str]]] = {i: [] for i in range(len(ev.actions))}
        for point in ev.traj.days:
            for e in point.events:
                if e.kind not in COST_KINDS:
                    continue
                idx = self._attribute(ev.actions, e.ref, point.day, e.formula)
                if idx is not None:
                    groups[idx].append((-e.amount_fen, e.formula or e.label))
        out = []
        for i, a in enumerate(ev.actions):
            f = self.facilities[a.facility_id]
            items = groups[i]
            fen = sum(x for x, _ in items)
            if len(items) == 1:
                formula = items[0][1]
            elif items:
                formula = "; ".join(t for _, t in items) + f"; total {fmt_yuan(fen)}"
            else:
                formula = "no cost posted"
            why = ev.approvals.get(_akey(a), "")
            no = ev.unrunnable.get(_akey(a), "")
            out.append(CostLine(label=self.action_label(a), fen=fen, facility_id=f.id, formula=formula,
                                needs_owner_approval=bool(why), approval_reason=why,
                                executable_now=not no, not_executable_reason=no))
        return out

    def _attribute(self, actions: tuple[FundingAction, ...], ref: str | None, day: int,
                   formula: str | None = None) -> int | None:
        idx = [i for i, a in enumerate(actions) if a.facility_id == ref]
        if not idx:
            return None
        if len(idx) == 1:
            return idx[0]
        # the engine's posting formula names the principal it is charged on first ("<amount> × <rate> ..."): that
        # tells two advances on one facility apart where the day cannot (an upfront fee posts on the landing day)
        named = [i for i in idx if formula and formula.startswith(f"{y(actions[i].amount_fen)} ×")]
        if named:
            idx = named
        for i in idx:
            a = actions[i]
            f = self.facilities[a.facility_id]
            r = self.rcvs.get(a.receivable_id or "")
            if a.kind == FundingActionKind.FINANCE_INVOICE and r is not None and r.due_day == day:
                return i
            if a.kind == FundingActionKind.EARLY_PAY and r is not None and max(0, r.issue_day) + f.lead_time_days == day:
                return i
        return idx[0]

    def action_label(self, a: FundingAction) -> str:
        f = self.facilities[a.facility_id]
        tag = " (expected)" if f.status != FacilityStatus.COMMITTED else ""
        match a.kind:
            case FundingActionKind.DRAW:
                repay = f", repaid day {a.repay_day}" if a.repay_day is not None else ""
                return f"{f.name}: draw {fmt_yuan(a.amount_fen)}{repay}{tag}"
            case FundingActionKind.FINANCE_INVOICE:
                return f"{f.name}: advance {fmt_yuan(a.amount_fen)} on {a.receivable_id}{tag}"
            case FundingActionKind.EARLY_PAY:
                return (f"{f.name}: early payment on {fmt_yuan(a.amount_fen)} face of {a.receivable_id} "
                        f"at {pct(bp(a.rate_bp or f.rate_bp))}{tag}")
            case FundingActionKind.DISCOUNT_BILL:
                return f"{f.name}: discount {fmt_yuan(a.amount_fen)} of bills{tag}"
        return f"{f.name}: {a.kind.value} {fmt_yuan(a.amount_fen)}{tag}"  # pragma: no cover


def cost_display(lines: list[CostLine], total: int | None) -> str:
    if total is None:
        return "—"
    if len(lines) <= 1:
        return fmt_yuan(total)
    return " + ".join(fmt_yuan(c.fen) for c in lines) + f" = {fmt_yuan(total)}"
