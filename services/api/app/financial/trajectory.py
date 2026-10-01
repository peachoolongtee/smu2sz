"""The daily cash recursion (docs/ARCHITECTURE.md "Engine semantics"; ADR-0002, ADR-0003).

Pure and deterministic: no I/O, no clock, no model calls. Every cash movement is an integer-fen
posting built with app.domain.money; a day's closing is its opening plus the sum of its events.

Conventions this module adds (documented in the agent report):
- A funding action's `day` is the request day. Cash lands on `day + facility.lead_time_days`.
- Receivables generated from a RecurringInvoice have the id `recurring_receivable_id(cp, issue_day)`.
- Day 0 is booked into month 1. Month m covers days 30(m-1)+1 .. 30m.

Balances already drawn (`Facility.drawn_fen` > 0, e.g. after executed operations) are repaid in the
projection, not carried for free. The state does not say when they were drawn, so each is one lot
dated day 0 (the convention `app.operations.log.open_lots` uses for a balance no logged draw
explains); that can only overstate interest.
- Invoice financing: the drawn balance is allocated to the FINANCED receivables in due order (each up
  to its advance rate); each advance is repaid on its receivable's due day with interest and fees per
  `finance_invoice_charges`. Anything left unallocated is repaid at the horizon end.
- Amortising facilities: the balance amortises from day 0 per `amortisation_schedule`.
- Other bullet facilities (the credit line): a REPAY action may repay the carried lot like any draw;
  what is left is repaid in full, with `line_interest`, on the first receipt day after which cash
  stays at or above the floor (`min_cash_fen`, or zero), or else on the horizon's last day.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction

from app.domain.models import (
    Contingency,
    DayPoint,
    DurationKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingAction,
    FundingActionKind,
    LedgerEvent,
    LedgerEventKind,
    Mode,
    MonthPoint,
    Obligation,
    ObligationType,
    Repayment,
    Trajectory,
)
from app.domain.money import Ratio, bp, post, simple_interest
from app.financial.amortisation import amortisation_schedule
from app.financial.charges import fee_period_days, finance_invoice_charges, line_interest, upfront_fee
from app.financial.errors import FundingActionError, ObligationError, UncommittedFacilityError
from app.financial.fmt import day as fday
from app.financial.fmt import pct, y

DEFAULT_EARLY_PAY_LEAD_DAYS = 2
MONTH_DAYS = 30
# Leverage when annualised EBITDA is zero or negative: larger than any limit, so it always fails.

# intra-day phases (Engine semantics §1)
INFLOW, OUTFLOW, SETTLE = 0, 1, 2


def recurring_receivable_id(counterparty_id: str, issue_day: int) -> str:
    """Id of the receivable a RecurringInvoice generates on `issue_day` (e.g. 'RI:BUYER-1:2')."""
    return f"RI:{counterparty_id}:{issue_day}"


# ---------------------------------------------------------------- internal records


@dataclass
class _Rcv:
    id: str
    counterparty_id: str
    face: int
    issue_day: int
    terms: int
    confirmed: bool
    generated: bool
    notes: list[str] = field(default_factory=list)
    early: int = 0  # face settled before the due day (discounted or early-paid)
    financed: bool = False
    advance: int = 0  # recorded advance outstanding on this invoice, and its facility
    advance_facility_id: str | None = None

    @property
    def due(self) -> int:
        return self.issue_day + self.terms


@dataclass
class _Posting:
    day: int
    phase: int
    kind: LedgerEventKind
    amount: int  # signed effect on cash
    label: str
    ref: str | None
    formula: str | None
    facility_id: str | None = None
    category: str | None = None  # interest | fee | discount | amort | principal


@dataclass
class _Lot:
    facility: Facility
    arrival: int
    amount: int
    repay_day: int | None  # None: open until a REPAY action
    remaining: int


@dataclass
class _TermLot:
    """A lot drawn on a bullet term facility. For DSCR its principal, interest and fees are spread
    evenly over the months of its term (ADR-0008): `postings` are the ones that make up that total."""

    arrival: int
    term_months: int
    postings: list[_Posting]


def _is_bullet_term(f: Facility) -> bool:
    return f.repayment == Repayment.BULLET and bool(f.term_months) and f.counts_in_debt_service


@dataclass
class _Book:
    """Everything the recursion needs, before it knows the final horizon."""

    postings: list[_Posting] = field(default_factory=list)
    balance_deltas: dict[str, dict[int, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    balance_in: dict[str, dict[int, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    repayment_days: list[int] = field(default_factory=list)
    funding_days: list[int] = field(default_factory=list)  # days funding cash lands
    # (from_day, until_day_or_None, amount): forward concessions outstanding on [from, until)
    forward: list[tuple[int, int | None, int]] = field(default_factory=list)
    # balances drawn before day 0 on bullet facilities, repaid once the cash path is known
    carried: list[_Lot] = field(default_factory=list)
    # invoice-financing balance no FINANCED receivable explains: (facility, amount), repaid at the horizon end
    unallocated: list[tuple[Facility, int]] = field(default_factory=list)
    # lots on bullet term facilities, serviced on a level basis in the monthly debt service (ADR-0008)
    term_lots: list[_TermLot] = field(default_factory=list)

    def add(self, p: _Posting) -> None:
        self.postings.append(p)

    def balance(self, facility_id: str, day: int, delta: int) -> None:
        self.balance_deltas[facility_id][day] += delta
        if delta > 0:
            self.balance_in[facility_id][day] += delta
            self.funding_days.append(day)


# ---------------------------------------------------------------- receivables and obligations


def _receivables(state: FinancialState, issue_bound: int) -> dict[str, _Rcv]:
    out: dict[str, _Rcv] = {}
    for r in state.receivables:
        if r.status in ("SETTLED", "FAILED"):
            continue
        if r.face_fen - r.settled_fen <= 0:
            continue
        out[r.id] = _Rcv(r.id, r.counterparty_id, r.face_fen - r.settled_fen, r.issue_day, r.terms_days, r.confirmed,
                         False, financed=r.status == "FINANCED",
                         advance=r.advance_fen if r.status == "FINANCED" else 0,
                         advance_facility_id=r.advance_facility_id)
    for ri in state.recurring_invoices:
        if ri.every_days <= 0:
            raise ObligationError(f"recurring invoice for {ri.counterparty_id} has every_days <= 0")
        d = ri.next_issue_day
        while d <= issue_bound:
            rid = recurring_receivable_id(ri.counterparty_id, d)
            if rid in out:
                raise ObligationError(f"duplicate recurring invoice {rid}")
            out[rid] = _Rcv(rid, ri.counterparty_id, ri.face_fen, d, ri.terms_days, True, True)
            d += ri.every_days
    return out


def _is_gain(ob: Obligation) -> bool:
    if ob.type == ObligationType.TERMS_EXTENSION:
        return (ob.days_delta or 0) < 0
    if ob.type == ObligationType.PRICE_ADJUSTMENT:
        return (ob.rate_bp or 0) > 0
    # an immediate discount is an early receipt: the cash arrives only if the buyer performs
    return ob.type == ObligationType.IMMEDIATE_DISCOUNT


def _bookable(ob: Obligation, mode: Mode) -> bool:
    """INVARIANT 5: unevidenced claims never book; in CONSERVATIVE, contingent gains count as zero."""
    if ob.type == ObligationType.CLAIMED_PRIOR_CONCESSION or ob.contingency == Contingency.CLAIMED_UNEVIDENCED:
        return False
    return not (mode == Mode.CONSERVATIVE and ob.contingency == Contingency.CONTINGENT and _is_gain(ob))


def _select_invoices(ob: Obligation, rcvs: dict[str, _Rcv]) -> list[_Rcv]:
    """Invoices a terms or price change applies to: the named one, or the buyer's invoices issued on
    or after the effective day (default 0), bounded by the duration."""
    if ob.base.receivable_id is not None:
        if ob.base.receivable_id not in rcvs:
            raise ObligationError(f"{ob.id}: receivable {ob.base.receivable_id} not found or not open")
        return [rcvs[ob.base.receivable_id]]
    start = ob.effective_day if ob.effective_day is not None else 0
    pool = sorted(
        (r for r in rcvs.values() if r.counterparty_id == ob.counterparty_id and r.issue_day >= start),
        key=lambda r: (r.issue_day, r.id),
    )
    d = ob.duration
    if d.kind == DurationKind.ONE_OFF:
        return pool[:1]
    if d.kind == DurationKind.RECURRING_BOUNDED:
        if d.end_day is not None:
            pool = [r for r in pool if r.issue_day <= d.end_day]
        if d.invoices is not None:
            pool = pool[: d.invoices]
        if d.end_day is None and d.invoices is None:
            raise ObligationError(f"{ob.id}: bounded duration with neither invoices nor end_day")
    return pool


def _apply_terms_and_prices(obs: list[Obligation], rcvs: dict[str, _Rcv]) -> None:
    for ob in obs:
        if ob.type == ObligationType.TERMS_EXTENSION:
            if ob.days_delta is None:
                raise ObligationError(f"{ob.id}: terms extension without days_delta")
            for r in _select_invoices(ob, rcvs):
                if r.terms + ob.days_delta < 0:
                    raise ObligationError(f"{ob.id}: terms of {r.id} would become negative")
                r.terms += ob.days_delta
                sign = "+" if ob.days_delta >= 0 else "−"
                r.notes.append(f"terms {sign}{abs(ob.days_delta)} days ({ob.id})")
        elif ob.type == ObligationType.PRICE_ADJUSTMENT:
            if ob.rate_bp is None:
                raise ObligationError(f"{ob.id}: price adjustment without rate_bp")
            for r in _select_invoices(ob, rcvs):
                adj = post(bp(ob.rate_bp) * r.face)
                r.notes.append(f"price {pct(bp(ob.rate_bp))} of {y(r.face)} = {y(adj)} ({ob.id})")
                r.face += adj


def _early_pay_lead(state: FinancialState, counterparty_id: str) -> int:
    eps = [f for f in state.facilities if f.kind == FacilityKind.BUYER_EARLY_PAY]
    for f in eps:
        if f.lender_id == counterparty_id:
            return f.lead_time_days
    return eps[0].lead_time_days if eps else DEFAULT_EARLY_PAY_LEAD_DAYS


def _bind_discount_receivable(ob: Obligation, state: FinancialState, rcvs: dict[str, _Rcv]) -> _Rcv:
    if ob.base.receivable_id is not None:
        r = rcvs.get(ob.base.receivable_id)
        if r is None:
            raise ObligationError(f"{ob.id}: receivable {ob.base.receivable_id} not found or not open")
        return r
    if ob.base.amount_fen is None:
        raise ObligationError(f"{ob.id}: immediate discount names no receivable and no amount to match")
    matches = [
        rcvs[r.id]
        for r in state.receivables
        if r.status == "OPEN"
        and r.counterparty_id == ob.counterparty_id
        and r.face_fen == ob.base.amount_fen
        and r.id in rcvs
    ]
    if len(matches) != 1:
        raise ObligationError(
            f"{ob.id}: expected exactly one open receivable of {ob.counterparty_id} with face "
            f"{y(ob.base.amount_fen)}, found {len(matches)}"
        )
    return matches[0]


def _immediate_discount(ob: Obligation, state: FinancialState, rcvs: dict[str, _Rcv], book: _Book) -> None:
    r = _bind_discount_receivable(ob, state, rcvs)
    settle_day = ob.effective_day
    if settle_day is None:
        settle_day = _early_pay_lead(state, ob.counterparty_id)
    if settle_day < state.as_of_day or settle_day >= r.due:
        raise ObligationError(f"{ob.id}: settlement on {fday(settle_day)} is not between today "
                              f"({fday(state.as_of_day)}) and {r.id}'s due day {r.due}")
    portion = r.face - r.early
    if ob.base.receivable_id is not None and ob.base.amount_fen is not None:
        portion = ob.base.amount_fen
    if portion <= 0 or portion > r.face - r.early:
        raise ObligationError(f"{ob.id}: settles {y(portion)} but {r.id} has {y(r.face - r.early)} open")
    if ob.rate_bp is not None:
        disc = post(bp(ob.rate_bp) * portion)
        formula = f"{y(portion)} × {pct(bp(ob.rate_bp))} = {y(disc)}"
    elif ob.amount_fen is not None:
        disc = ob.amount_fen
        formula = f"fixed discount {y(disc)}"
    else:
        raise ObligationError(f"{ob.id}: immediate discount without rate_bp or amount_fen")
    r.early += portion
    book.add(_Posting(settle_day, INFLOW, LedgerEventKind.EARLY_RECEIPT, portion,
                      f"Early settlement of {r.id} ({ob.id})", r.id,
                      f"face {y(portion)} received on {fday(settle_day)} instead of {fday(r.due)}"))
    book.add(_Posting(settle_day, INFLOW, LedgerEventKind.DISCOUNT, -disc,
                      f"Discount on early settlement of {r.id} ({ob.id})", ob.id, formula, category="discount"))


def _forward_concession(ob: Obligation, book: _Book) -> None:
    """Rebates and operational concessions: the forward ledger, or cash on an effective day."""
    if ob.type == ObligationType.CONTINGENT_REBATE:
        if ob.rate_bp is not None and ob.base.amount_fen is not None:
            amount = post(bp(ob.rate_bp) * ob.base.amount_fen)
            formula = f"{pct(bp(ob.rate_bp))} × {y(ob.base.amount_fen)} = {y(amount)} (at maximum)"
        elif ob.amount_fen is not None:
            amount = ob.amount_fen
            formula = f"fixed rebate {y(amount)}"
        else:
            raise ObligationError(f"{ob.id}: rebate needs rate_bp and a base amount, or a fixed amount")
        label = f"Rebate to {ob.counterparty_id} ({ob.id})"
    else:  # OPERATIONAL_CONCESSION: one year of events
        if ob.amount_fen is None or ob.base.events_per_year is None:
            raise ObligationError(f"{ob.id}: operational concession needs amount_fen and events_per_year")
        amount = ob.amount_fen * ob.base.events_per_year
        formula = f"{y(ob.amount_fen)} × {ob.base.events_per_year} events a year = {y(amount)}"
        label = f"Operational concession to {ob.counterparty_id} ({ob.id})"
    eff = ob.effective_day
    if eff is not None and eff >= 0:
        # outstanding until paid; paid in cash on the effective day if that is inside the horizon
        book.forward.append((0, eff, amount))
        book.add(_Posting(eff, OUTFLOW, LedgerEventKind.CONCESSION, -amount, label, ob.id, formula))
    else:
        book.forward.append((0, None, amount))


# ---------------------------------------------------------------- funding actions


def _facility(state: FinancialState, a: FundingAction, mode: Mode) -> Facility:
    f = next((x for x in state.facilities if x.id == a.facility_id), None)
    if f is None:
        raise FundingActionError(f"unknown facility {a.facility_id}")
    if not f.owner_approved:
        raise FundingActionError(f"facility {f.id} is not owner-approved")
    allowed = {FacilityStatus.COMMITTED} | ({FacilityStatus.PENDING} if mode == Mode.EXPECTED else set())
    if f.status not in allowed:
        raise UncommittedFacilityError(f.id, f.status, mode)
    return f


def _receivable_for(a: FundingAction, rcvs: dict[str, _Rcv], mode: Mode) -> _Rcv:
    if a.receivable_id is None:
        raise FundingActionError(f"{a.kind.value} on {a.facility_id} needs a receivable_id")
    r = rcvs.get(a.receivable_id)
    if r is None:
        raise FundingActionError(f"receivable {a.receivable_id} not found or not open")
    if mode == Mode.CONSERVATIVE and not r.confirmed:
        raise FundingActionError(f"receivable {r.id} is unconfirmed; CONSERVATIVE mode cannot fund against it")
    return r


def _upfront_fee(f: Facility, arrival: int, amount: int, book: _Book) -> None:
    if f.upfront_fee_bp:
        fee = upfront_fee(f, amount)
        book.add(_Posting(arrival, SETTLE, LedgerEventKind.FEE, -fee, f"Upfront fee, {f.name}", f.id,
                          f"{y(amount)} × {pct(bp(f.upfront_fee_bp))} = {y(fee)}", f.id, "fee"))


def _bullet_repayment(lot: _Lot, amount: int, day: int, book: _Book) -> None:
    f = lot.facility
    days = day - lot.arrival
    interest = line_interest(amount, f.rate_bp, days)
    book.add(_Posting(day, SETTLE, LedgerEventKind.INTEREST, -interest, f"Interest, {f.name}", f.id,
                      f"{y(amount)} × {pct(bp(f.rate_bp))} × {days}/365 = {y(interest)}", f.id, "interest"))
    book.add(_Posting(day, SETTLE, LedgerEventKind.REPAYMENT, -amount, f"Repay {f.name}", f.id,
                      f"principal drawn {fday(lot.arrival)}", f.id, "principal"))
    book.balance(f.id, day, -amount)
    book.repayment_days.append(day)


def _amortise(f: Facility, arrival: int, amount: int, book: _Book) -> None:
    if not f.term_months:
        raise FundingActionError(f"amortising facility {f.id} has no term_months")
    for row in amortisation_schedule(amount, f.rate_bp, f.term_months):
        d = arrival + MONTH_DAYS * row.month
        book.add(_Posting(d, SETTLE, LedgerEventKind.INTEREST, -row.interest,
                          f"Interest, {f.name} (month {row.month})", f.id,
                          f"balance × {pct(bp(f.rate_bp))}/12 = {y(row.interest)}", f.id, "interest"))
        book.add(_Posting(d, SETTLE, LedgerEventKind.REPAYMENT, -row.principal,
                          f"Principal, {f.name} (month {row.month})", f.id,
                          f"payment {y(row.payment)} − interest {y(row.interest)}", f.id, "amort"))
        book.balance(f.id, d, -row.principal)
        book.repayment_days.append(d)


def _draw(f: Facility, a: FundingAction, book: _Book) -> _Lot | None:
    if f.kind in (FacilityKind.INVOICE_FINANCING, FacilityKind.BUYER_EARLY_PAY,
                  FacilityKind.BANK_ACCEPTANCE_BILL, FacilityKind.EQUITY):
        raise FundingActionError(f"cannot DRAW on {f.kind.value} facility {f.id}")
    if f.repayment == Repayment.ON_RECEIPT:
        raise FundingActionError(f"facility {f.id} is repaid on receipt; DRAW is not available")
    arrival = a.day + f.lead_time_days
    first = len(book.postings)
    book.add(_Posting(arrival, INFLOW, LedgerEventKind.DRAW, a.amount_fen, f"Draw {f.name}", f.id,
                      f"requested {fday(a.day)} + {f.lead_time_days}-day lead time", f.id))
    book.balance(f.id, arrival, a.amount_fen)
    _upfront_fee(f, arrival, a.amount_fen, book)
    if f.repayment == Repayment.AMORTISING:
        if not f.term_months:
            raise FundingActionError(f"amortising facility {f.id} has no term_months")
        _amortise(f, arrival, a.amount_fen, book)
        return None
    repay = a.repay_day
    if repay is None and f.term_months:
        repay = arrival + MONTH_DAYS * f.term_months
    if repay is not None and repay < arrival:
        raise FundingActionError(f"draw on {f.id} repaid on {fday(repay)} before it lands on {fday(arrival)}")
    lot = _Lot(f, arrival, a.amount_fen, repay, a.amount_fen)
    if repay is not None:
        _bullet_repayment(lot, a.amount_fen, repay, book)
        lot.remaining = 0
    if repay is not None and _is_bullet_term(f):
        book.term_lots.append(_TermLot(arrival, f.term_months, [
            p for p in book.postings[first:] if p.category in ("interest", "fee", "principal")]))
    return lot


def _repay(f: Facility, a: FundingAction, lots: list[_Lot], book: _Book) -> None:
    if f.repayment != Repayment.BULLET:
        raise FundingActionError(f"REPAY is only supported on bullet facilities, not {f.id}")
    left = a.amount_fen
    for lot in lots:
        if left == 0:
            break
        if lot.facility.id != f.id or lot.repay_day is not None or lot.remaining == 0 or lot.arrival > a.day:
            continue
        part = min(left, lot.remaining)
        _bullet_repayment(lot, part, a.day, book)
        lot.remaining -= part
        left -= part
    if left:
        raise FundingActionError(f"REPAY of {y(a.amount_fen)} on {f.id} exceeds its open draws by {y(left)}")


def _finance_invoice(f: Facility, a: FundingAction, r: _Rcv, book: _Book) -> None:
    if f.kind != FacilityKind.INVOICE_FINANCING:
        raise FundingActionError(f"FINANCE_INVOICE needs an invoice-financing facility, not {f.id}")
    if r.financed:
        raise FundingActionError(f"receivable {r.id} is already financed")
    open_face = r.face - r.early
    if f.advance_rate_bp is not None and a.amount_fen * 10_000 > f.advance_rate_bp * open_face:
        raise FundingActionError(
            f"advance {y(a.amount_fen)} exceeds {pct(bp(f.advance_rate_bp))} of {r.id}'s open face {y(open_face)}"
        )
    request = max(a.day, r.issue_day)  # an unissued invoice is submitted on its issue day
    arrival = request + f.lead_time_days
    days = r.due - arrival
    if days <= 0:
        raise FundingActionError(f"advance on {r.id} would land on {fday(arrival)}, not before its due day {r.due}")
    period = fee_period_days(f)
    rate = bp(f.rate_bp)
    interest, fee, periods = finance_invoice_charges(f, a.amount_fen, days)
    r.financed = True
    book.add(_Posting(arrival, INFLOW, LedgerEventKind.ADVANCE, a.amount_fen, f"Advance on {r.id}, {f.name}", f.id,
                      f"requested {fday(request)} + {f.lead_time_days}-day lead time", f.id))
    book.balance(f.id, arrival, a.amount_fen)
    _upfront_fee(f, arrival, a.amount_fen, book)
    book.add(_Posting(r.due, SETTLE, LedgerEventKind.INTEREST, -interest, f"Interest, {f.name} on {r.id}", f.id,
                      f"{y(a.amount_fen)} × {pct(rate)} × {periods * period}/365 "
                      f"({days} days billed as {periods} × {period}-day period) = {y(interest)}", f.id, "interest"))
    if fee:
        book.add(_Posting(r.due, SETTLE, LedgerEventKind.FEE, -fee, f"Fee, {f.name} on {r.id}", f.id,
                          f"{y(a.amount_fen)} × {pct(bp(f.fee_bp_per_advance))} × {periods} = {y(fee)}",
                          f.id, "fee"))
    book.add(_Posting(r.due, SETTLE, LedgerEventKind.REPAYMENT, -a.amount_fen, f"Repay advance on {r.id}", f.id,
                      f"repaid from the receipt of {r.id}", f.id, "principal"))
    book.balance(f.id, r.due, -a.amount_fen)
    book.repayment_days.append(r.due)


def _early_pay(f: Facility, a: FundingAction, r: _Rcv, book: _Book) -> int:
    if f.kind != FacilityKind.BUYER_EARLY_PAY:
        raise FundingActionError(f"EARLY_PAY needs a buyer early-payment facility, not {f.id}")
    if r.counterparty_id != f.lender_id:
        raise FundingActionError(f"{f.id} is offered by {f.lender_id}, not by {r.counterparty_id}")
    if r.financed:
        raise FundingActionError(f"receivable {r.id} is financed; it cannot also be paid early")
    portion = a.amount_fen
    if portion > r.face - r.early:
        raise FundingActionError(f"early pay of {y(portion)} exceeds {r.id}'s open face {y(r.face - r.early)}")
    request = max(a.day, r.issue_day)
    arrival = request + f.lead_time_days
    if arrival >= r.due:
        raise FundingActionError(f"early pay on {r.id} would land on {fday(arrival)}, not before {fday(r.due)}")
    rate = bp(a.rate_bp if a.rate_bp is not None else f.rate_bp)
    disc = post(rate * portion)
    r.early += portion
    book.funding_days.append(arrival)
    book.add(_Posting(arrival, INFLOW, LedgerEventKind.EARLY_RECEIPT, portion, f"Early payment on {r.id}", r.id,
                      f"face {y(portion)} of {y(r.face)}; residual {y(r.face - r.early)} on {fday(r.due)}", f.id))
    book.add(_Posting(arrival, INFLOW, LedgerEventKind.DISCOUNT, -disc, f"Early-payment discount on {r.id}", f.id,
                      f"{y(portion)} × {pct(rate)} = {y(disc)}", f.id, "discount"))
    return portion


def _discount_bill(f: Facility, a: FundingAction, book: _Book) -> int:
    if f.kind != FacilityKind.BANK_ACCEPTANCE_BILL:
        raise FundingActionError(f"DISCOUNT_BILL needs a bank-acceptance-bill facility, not {f.id}")
    arrival = a.day + f.lead_time_days
    if a.repay_day is None or a.repay_day <= arrival:
        raise FundingActionError("DISCOUNT_BILL needs the bill's maturity as repay_day, after the cash lands")
    days = a.repay_day - arrival
    rate = bp(a.rate_bp if a.rate_bp is not None else f.rate_bp)
    disc = post(simple_interest(a.amount_fen, rate, days))
    book.funding_days.append(arrival)
    book.add(_Posting(arrival, INFLOW, LedgerEventKind.EARLY_RECEIPT, a.amount_fen, f"Bill discounted, {f.name}",
                      f.id, f"bill face {y(a.amount_fen)}, matures {fday(a.repay_day)}", f.id))
    book.add(_Posting(arrival, INFLOW, LedgerEventKind.DISCOUNT, -disc, f"Bill discount, {f.name}", f.id,
                      f"{y(a.amount_fen)} × {pct(rate)} × {days}/365 = {y(disc)}", f.id, "discount"))
    return a.amount_fen


def _apply_actions(
    state: FinancialState, actions: list[FundingAction], mode: Mode, rcvs: dict[str, _Rcv], book: _Book
) -> None:
    lots: list[_Lot] = list(book.carried)  # a REPAY action may repay a balance drawn before day 0
    used: dict[str, int] = defaultdict(int)  # early-pay / bill face used against the limit
    resolved = [(a, _facility(state, a, mode)) for a in actions]
    for a, f in resolved:
        if a.amount_fen <= 0:
            raise FundingActionError(f"{a.kind.value} on {f.id} must have a positive amount")
        if a.day < 0:
            raise FundingActionError(f"{a.kind.value} on {f.id} is requested before day 0")
    for a, f in resolved:
        match a.kind:
            case FundingActionKind.DRAW:
                lot = _draw(f, a, book)
                if lot is not None:
                    lots.append(lot)
            case FundingActionKind.FINANCE_INVOICE:
                _finance_invoice(f, a, _receivable_for(a, rcvs, mode), book)
            case FundingActionKind.EARLY_PAY:
                used[f.id] += _early_pay(f, a, _receivable_for(a, rcvs, mode), book)
            case FundingActionKind.DISCOUNT_BILL:
                used[f.id] += _discount_bill(f, a, book)
            case FundingActionKind.REPAY:
                pass
    lots.sort(key=lambda lot: lot.arrival)
    for a, f in sorted(((a, f) for a, f in resolved if a.kind == FundingActionKind.REPAY), key=lambda t: t[0].day):
        _repay(f, a, lots, book)
    for fid, total in used.items():
        f = next(x for x in state.facilities if x.id == fid)
        if total > f.limit_fen:
            raise FundingActionError(f"{fid} used {y(total)} against a limit of {y(f.limit_fen)}")


# ---------------------------------------------------------------- balances drawn before day 0

_NOT_CARRIED = (FacilityKind.BUYER_EARLY_PAY, FacilityKind.BANK_ACCEPTANCE_BILL, FacilityKind.EQUITY)
_BUYER_RECEIPTS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)


def _repay_carried_advance(f: Facility, r: _Rcv, advance: int, book: _Book, today: int = 0) -> None:
    """An advance made before day 0 on a FINANCED receivable, repaid from its receipt on the due day. If the
    receivable is already overdue the advance is repaid today without the receipt (recourse; ADR-0006)."""
    day = max(today, r.due)
    period = fee_period_days(f)
    interest, fee, periods = finance_invoice_charges(f, advance, day)
    book.add(_Posting(day, SETTLE, LedgerEventKind.INTEREST, -interest, f"Interest, {f.name} on {r.id}", f.id,
                      f"{y(advance)} × {pct(bp(f.rate_bp))} × {periods * period}/365 (advance drawn before day 0, "
                      f"dated day 0; {periods} × {period}-day period) = {y(interest)}", f.id, "interest"))
    if fee:
        book.add(_Posting(day, SETTLE, LedgerEventKind.FEE, -fee, f"Fee, {f.name} on {r.id}", f.id,
                          f"{y(advance)} × {pct(bp(f.fee_bp_per_advance))} × {periods} = {y(fee)}", f.id, "fee"))
    book.add(_Posting(day, SETTLE, LedgerEventKind.REPAYMENT, -advance, f"Repay advance on {r.id}", f.id,
                      f"advance drawn before day 0, repaid from the receipt of {r.id}", f.id, "principal"))
    book.balance(f.id, day, -advance)
    book.repayment_days.append(day)


def _carry_drawn_balances(state: FinancialState, rcvs: dict[str, _Rcv], book: _Book) -> None:
    """Schedule the repayment of every balance already drawn at day 0 (module docstring)."""
    financed = sorted((r for r in rcvs.values() if r.financed), key=lambda r: (r.due, r.id))
    recorded = [r for r in financed if r.advance > 0]  # the executor recorded the advance on the invoice
    financed = [r for r in financed if r.advance == 0]  # older states: allocate the balance in due order
    for f in sorted(state.facilities, key=lambda x: x.id):
        if f.drawn_fen <= 0 or f.kind in _NOT_CARRIED:
            continue
        if f.kind == FacilityKind.INVOICE_FINANCING:
            left = f.drawn_fen
            for r in [r for r in recorded if r.advance_facility_id == f.id]:
                advance = min(left, r.advance)
                if advance > 0:
                    _repay_carried_advance(f, r, advance, book, state.as_of_day)
                    left -= advance
            while financed and left > 0:
                r = financed.pop(0)
                cap = r.face if f.advance_rate_bp is None else post(bp(f.advance_rate_bp) * r.face)
                advance = min(left, cap)
                if advance > 0:
                    _repay_carried_advance(f, r, advance, book, state.as_of_day)
                    left -= advance
            if left > 0:
                book.unallocated.append((f, left))
        elif f.repayment == Repayment.AMORTISING and f.term_months:
            _amortise(f, 0, f.drawn_fen, book)
        elif f.repayment == Repayment.BULLET and f.term_months and f.kind != FacilityKind.CREDIT_LINE:
            maturity = MONTH_DAYS * f.term_months  # a term bullet is repaid at maturity, as a projected draw is
            first = len(book.postings)
            _bullet_repayment(_Lot(f, 0, f.drawn_fen, maturity, 0), f.drawn_fen, maturity, book)
            if _is_bullet_term(f):
                book.term_lots.append(_TermLot(0, f.term_months, book.postings[first:]))
        elif f.repayment == Repayment.ON_RECEIPT:
            book.unallocated.append((f, f.drawn_fen))
        else:
            book.carried.append(_Lot(f, 0, f.drawn_fen, None, f.drawn_fen))


def _closings(opening: int, postings: list[_Posting], horizon: int) -> list[int]:
    by_day: dict[int, int] = defaultdict(int)
    for p in postings:
        by_day[p.day] += p.amount
    out, cash = [], opening
    for d in range(horizon + 1):
        cash += by_day.get(d, 0)
        out.append(cash)
    return out


def _repay_carried(state: FinancialState, book: _Book, horizon: int, floor: int) -> None:
    """Once the horizon is fixed: repay what is left of the balances drawn before day 0."""
    for f, amount in book.unallocated:
        period = fee_period_days(f)
        interest, fee, periods = finance_invoice_charges(f, amount, horizon)
        book.add(_Posting(horizon, SETTLE, LedgerEventKind.INTEREST, -interest, f"Interest, {f.name}", f.id,
                          f"{y(amount)} × {pct(bp(f.rate_bp))} × {periods * period}/365 (balance drawn before day 0 "
                          f"that no financed receivable repays, dated day 0) = {y(interest)}", f.id, "interest"))
        if fee:
            book.add(_Posting(horizon, SETTLE, LedgerEventKind.FEE, -fee, f"Fee, {f.name}", f.id,
                              f"{y(amount)} × {pct(bp(f.fee_bp_per_advance))} × {periods} = {y(fee)}", f.id, "fee"))
        book.add(_Posting(horizon, SETTLE, LedgerEventKind.REPAYMENT, -amount, f"Repay {f.name}", f.id,
                          "balance drawn before day 0, repaid at the horizon end", f.id, "principal"))
        book.balance(f.id, horizon, -amount)
    for lot in book.carried:
        if lot.remaining == 0:
            continue
        closings = _closings(state.cash_fen, book.postings, horizon)
        receipt_days = sorted({p.day for p in book.postings if p.kind in _BUYER_RECEIPTS and 0 <= p.day <= horizon})
        rate, amount = lot.facility.rate_bp, lot.remaining
        day = next((d for d in receipt_days
                    if min(closings[d:]) - amount - line_interest(amount, rate, d - lot.arrival) >= floor), horizon)
        _bullet_repayment(lot, amount, day, book)
        lot.remaining = 0


def _check_limits(state: FinancialState, book: _Book) -> None:
    """Each facility's balance may never exceed its limit, even for a moment within a day
    (draws land before the day's repayments)."""
    for f in state.facilities:
        deltas = book.balance_deltas.get(f.id)
        if not deltas:
            continue
        bal = f.drawn_fen
        for d in sorted(deltas):
            peak = bal + book.balance_in.get(f.id, {}).get(d, 0)
            if peak > f.limit_fen:
                raise FundingActionError(
                    f"{f.id} balance would reach {y(peak)} on {fday(d)}, above its limit {y(f.limit_fen)}"
                )
            bal += deltas[d]


# ---------------------------------------------------------------- recursion


def _build(
    state: FinancialState, obligations: list[Obligation], actions: list[FundingAction], mode: Mode, issue_bound: int
) -> tuple[_Book, dict[str, _Rcv]]:
    rcvs = _receivables(state, issue_bound)
    book = _Book()
    obs = [ob for ob in obligations if _bookable(ob, mode)]
    _apply_terms_and_prices(obs, rcvs)
    for ob in obs:
        if ob.type == ObligationType.IMMEDIATE_DISCOUNT:
            _immediate_discount(ob, state, rcvs, book)
        elif ob.type in (ObligationType.CONTINGENT_REBATE, ObligationType.OPERATIONAL_CONCESSION):
            _forward_concession(ob, book)
    _carry_drawn_balances(state, rcvs, book)
    _apply_actions(state, actions, mode, rcvs, book)
    _check_limits(state, book)

    today = state.as_of_day  # days before it are closed: posted flows are in cash_fen, unpaid receipts did not happen
    for fl in state.flows:
        if fl.day < today:
            continue
        if mode == Mode.CONSERVATIVE and fl.amount_fen > 0 and not fl.confirmed:
            continue  # unconfirmed inflows are ignored
        phase = INFLOW if fl.amount_fen >= 0 else OUTFLOW
        note = "" if fl.confirmed else " (unconfirmed)"
        book.add(_Posting(fl.day, phase, LedgerEventKind.FLOW, fl.amount_fen, fl.label + note, fl.id,
                          f"{fl.kind.value.lower()} {y(fl.amount_fen)}"))
    for r in rcvs.values():
        residual = r.face - r.early
        if residual <= 0 or r.due < today:
            continue  # settled early, or overdue before today (no dated receipt to rely on)
        if mode == Mode.CONSERVATIVE and not r.confirmed:
            continue
        what = "residual " if r.early else ""
        notes = f"; {'; '.join(r.notes)}" if r.notes else ""
        book.add(_Posting(r.due, INFLOW, LedgerEventKind.RECEIPT, residual, f"Receipt {r.id} from {r.counterparty_id}",
                          r.id, f"{what}face {y(residual)}: issued {fday(r.issue_day)} + {r.terms}-day terms{notes}"))
    return book, rcvs


def _issue_day_of(receivable_id: str | None) -> int:
    """Issue day encoded in a generated receivable id, so a referenced future invoice is generated."""
    if receivable_id and receivable_id.startswith("RI:"):
        try:
            return int(receivable_id.rsplit(":", 1)[1])
        except ValueError:
            return 0
    return 0


def _month_of(d: int) -> int:
    return max(1, -(-d // MONTH_DAYS))


def _booked(
    state: FinancialState,
    obligations: list[Obligation],
    actions: list[FundingAction],
    mode: Mode,
    horizon_days: int,
    min_cash_fen: int | None,
) -> tuple[_Book, int]:
    """Every posting of a projection and its final horizon H (see `project`). Shared by `project`
    and `app.financial.cashpath.project_cash`, so both book exactly the same postings."""
    if horizon_days < 0:
        raise ValueError("horizon_days must not be negative")
    horizon_days += state.as_of_day  # the horizon is counted from today; days stay absolute (ADR-0006)
    bound = max([horizon_days] + [a.day for a in actions] + [a.repay_day or 0 for a in actions]
                + [ob.effective_day or 0 for ob in obligations] + [_issue_day_of(a.receivable_id) for a in actions])
    while True:
        book, _ = _build(state, obligations, actions, mode, bound)
        horizon = max([horizon_days] + [d + 1 for d in book.repayment_days] + book.funding_days)
        if horizon <= bound:
            break
        bound = horizon
    _repay_carried(state, book, horizon, min_cash_fen if min_cash_fen is not None else 0)
    return book, horizon


def project(
    state: FinancialState,
    obligations: list[Obligation],
    actions: list[FundingAction],
    mode: Mode,
    horizon_days: int,
    min_cash_fen: int | None = None,
) -> Trajectory:
    """Daily cash recursion over days 0..H. Days before `state.as_of_day` are closed and carry no postings.

    H = max(as_of_day + horizon_days, last repayment day + 1, last day funding cash lands). Raises
    UncommittedFacilityError for a facility the mode may not use, FundingActionError for a malformed
    or over-limit action, and ObligationError for an obligation that cannot be bound to state.
    """
    book, horizon = _booked(state, obligations, actions, mode, horizon_days, min_cash_fen)

    fac = {f.id: f for f in state.facilities}
    by_day: dict[int, list[_Posting]] = defaultdict(list)
    for p in book.postings:
        if 0 <= p.day <= horizon:
            by_day[p.day].append(p)

    fids = sorted(fac)
    balances = {fid: fac[fid].drawn_fen for fid in fids}
    debt_principal = sum(dbt.principal_fen for dbt in state.debts)
    existing_fc = sum(fc.value_fen for fc in state.forward_concessions)
    base_ds = sum(dbt.monthly_debt_service_fen for dbt in state.debts)

    n_months = _month_of(horizon)
    month_ds = defaultdict(int)
    # bullet term lots: level amount in each month of the term, their own postings left out below
    level_posted = {id(p) for lot in book.term_lots for p in lot.postings}
    for lot in book.term_lots:
        total = -sum(p.amount for p in lot.postings)  # principal + interest + fees, as the engine posted them
        level, rest = divmod(total, lot.term_months)
        first_month = _month_of(lot.arrival)
        for i in range(lot.term_months):
            month_ds[first_month + i] += level + (rest if i == lot.term_months - 1 else 0)
    month_end_leverage_debt: dict[int, int] = {}

    days: list[DayPoint] = []
    cash = state.cash_fen
    interest_total = fees_total = discounts_total = 0
    for d in range(horizon + 1):
        todays = sorted(by_day.get(d, []), key=lambda p: p.phase)  # stable: keeps insertion order
        opening = cash
        cash += sum(p.amount for p in todays)
        for fid in fids:
            balances[fid] += book.balance_deltas.get(fid, {}).get(d, 0)
        for p in todays:
            if p.category == "interest":
                interest_total -= p.amount
            elif p.category == "fee":
                fees_total -= p.amount
            elif p.category == "discount":
                discounts_total -= p.amount
            if (p.facility_id and p.category in ("interest", "fee", "amort") and id(p) not in level_posted
                    and fac[p.facility_id].counts_in_debt_service):
                month_ds[_month_of(d)] -= p.amount
        forward = existing_fc + sum(a for start, until, a in book.forward if start <= d and (until is None or d < until))
        days.append(DayPoint(
            day=d,
            opening_fen=opening,
            closing_fen=cash,
            debt_outstanding_fen=debt_principal + sum(balances.values()),
            forward_concession_fen=forward,
            events=[LedgerEvent(day=d, kind=p.kind, amount_fen=p.amount, label=p.label, ref=p.ref, formula=p.formula)
                    for p in todays],
        ))
        if d == horizon or (d > 0 and d % MONTH_DAYS == 0):
            month_end_leverage_debt[_month_of(d)] = debt_principal + sum(
                balances[fid] for fid in fids if fac[fid].counts_in_leverage
            )

    ebitda = state.monthly_ebitda_fen
    months: list[MonthPoint] = []
    for m in range(1, n_months + 1):
        ds = base_ds + month_ds[m]
        total_debt = month_end_leverage_debt[m]
        dscr = Ratio.of(Fraction(ebitda, ds)) if ds > 0 else None
        leverage = Ratio.of(Fraction(total_debt, 12 * ebitda)) if ebitda > 0 else None
        months.append(MonthPoint(month=m, ebitda_fen=ebitda, debt_service_fen=ds, total_debt_fen=total_debt,
                                 dscr=dscr, leverage=leverage))

    low = min(days, key=lambda p: (p.closing_fen, p.day))
    breach = None
    if min_cash_fen is not None:
        breach = next((p.day for p in days if p.closing_fen < min_cash_fen), None)
    return Trajectory(
        mode=mode,
        horizon_days=horizon,
        days=days,
        months=months,
        min_cash_fen=low.closing_fen,
        min_cash_day=low.day,
        first_breach_day=breach,
        interest_posted_fen=interest_total,
        fees_posted_fen=fees_total,
        discounts_posted_fen=discounts_total,
    )


__all__ = ["project", "recurring_receivable_id"]
