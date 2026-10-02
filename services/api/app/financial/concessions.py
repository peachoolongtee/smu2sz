"""Forward value of obligations over the concession horizon (spec v2 §6.5, §7.5; ADR-0002;
docs/FINANCIAL_SEMANTICS.md §6).

Every value is exact until reported, then rounded once with money.post. A positive value is a
cost to the supplier; a negative value is a gain (a shorter term, a price increase). Whether a gain
may offset a cost is the mandate's decision (only FIRM gains net; INVARIANT 5), not this module's.

Dating (rules fixed by the owner, 3 Oct 2026):

- The valuation window is W = [today, today + H), half-open; today = `state.as_of_day`, H the mandate's
  `forward_concession_horizon_days`.
- An obligation is worth the sum over the dated invoices of its scope whose ISSUE day is in W. The scope is
  the one the engine fixes at acceptance (`invoices.scope_at` -> `resolve_scope`); a recurring invoice issues
  on `next_issue_day` + k × `every_days`. The effective day is honoured for every duration kind and a
  count-bounded scope is truncated by W. The same invoices give the same value however the scope is worded.
- Terms extension of delta days: Σ face × delta × r / 365 over those invoices, rounded once at the end.
  Price adjustment p: −Σ post(p × face) (each invoice is posted on its own, because the price lands on the
  invoice).
- A cost and a gain are dated the same way: on the ISSUE day. A gain issued inside W whose cash arrives just
  after W still counts (the window-edge convention, derivation objection 1); a gain whose invoices are all
  issued outside W is worth 0 (F-FIN-01).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.domain.models import (
    ConcessionValue,
    Contingency,
    DurationKind,
    Facility,
    FinancialState,
    Obligation,
    ObligationType,
    RecurringInvoice,
)
from app.domain.money import DAYS_PER_YEAR, Ratio, bp, post
from app.financial.errors import ObligationError
from app.financial.fmt import pct, y
from app.financial.invoices import scope_at, scope_start

UNEVIDENCED_BASIS = "unevidenced, not booked"


def if_all_in_rate(facility: Facility) -> Fraction:
    """All-in simple annual rate: rate + per-period fee × 365/fee_period_days (10.8417% for FAC-IF).

    An upfront fee is term-dependent and is not folded in here.
    """
    rate = bp(facility.rate_bp)
    if facility.fee_bp_per_advance == 0:
        return rate
    if not facility.fee_period_days:
        raise ObligationError(f"facility {facility.id} has a per-advance fee but no fee_period_days")
    return rate + bp(facility.fee_bp_per_advance) * DAYS_PER_YEAR / facility.fee_period_days


def _recurring(state: FinancialState, counterparty_id: str) -> RecurringInvoice | None:
    found = [r for r in state.recurring_invoices if r.counterparty_id == counterparty_id]
    if len(found) > 1:
        raise ObligationError(f"{counterparty_id} has more than one recurring invoice; cannot choose")
    return found[0] if found else None


def _invoice_face(ob: Obligation, state: FinancialState, rec: RecurringInvoice | None) -> int:
    """The face one invoice of the obligation carries (for the per-invoice figure)."""
    rid = ob.base.receivable_id
    if rid is not None:
        for r in state.receivables:
            if r.id == rid:
                return r.face_fen
        if rid.startswith("RI:") and rec is not None:
            return rec.face_fen
        raise ObligationError(f"{ob.id}: receivable {rid} not found")
    if rec is not None:
        return rec.face_fen
    if ob.base.amount_fen is not None:
        return ob.base.amount_fen
    raise ObligationError(f"{ob.id}: no invoice face (no recurring invoice and no base amount)")


# ---------------------------------------------------------------- dated invoices


@dataclass(frozen=True, slots=True)
class DatedInvoice:
    """One invoice of an obligation's scope: the day it is issued and its face."""

    issue_day: int
    face_fen: int


def window(state: FinancialState, horizon_days: int) -> tuple[int, int]:
    """The valuation window W = [today, today + H), half-open. today = `state.as_of_day`."""
    return state.as_of_day, state.as_of_day + horizon_days


def recurring_issue_days(rec: RecurringInvoice, lo: int, hi: int) -> list[int]:
    """The days in [lo, hi) on which `rec` issues: next_issue_day + k × every_days, k >= 0."""
    if rec.every_days <= 0 or hi <= lo:
        return []
    first = rec.next_issue_day
    if first < lo:
        first += -(-(lo - first) // rec.every_days) * rec.every_days
    return list(range(first, hi, rec.every_days))


def _check_scope(ob: Obligation, rec: RecurringInvoice | None) -> None:
    d = ob.duration
    if d.kind == DurationKind.RECURRING_BOUNDED:
        if d.invoices is None and d.end_day is None:
            raise ObligationError(f"{ob.id}: bounded duration with neither invoices nor end_day")
        if d.invoices is not None and d.invoices < 0:
            raise ObligationError(f"{ob.id}: negative invoice count")
    if ob.base.receivable_id is not None or rec is not None:
        return
    if _undated(ob):
        return
    if d.kind == DurationKind.RECURRING_BOUNDED and d.end_day is not None:
        raise ObligationError(f"{ob.id}: end-day bound needs the buyer's recurring invoice")
    raise ObligationError(f"{ob.id}: no invoice face (no recurring invoice and no base amount)"
                          if ob.base.amount_fen is None and d.kind != DurationKind.RECURRING_PERPETUAL
                          else f"{ob.id}: recurring obligation but {ob.counterparty_id} has no recurring invoice")


def _undated(ob: Obligation) -> bool:
    """A ONE_OFF or count-bounded obligation with a stated amount and no recurring invoice to date it."""
    d = ob.duration
    return ob.base.amount_fen is not None and (
        d.kind == DurationKind.ONE_OFF or (d.kind == DurationKind.RECURRING_BOUNDED and d.invoices is not None))


def scoped_invoices(ob: Obligation, state: FinancialState, horizon_days: int) -> list[DatedInvoice]:
    """The dated invoices of `ob`'s scope whose ISSUE day is in W = [today, today + H).

    The scope is the one the engine fixes at acceptance (`invoices.scope_at`, which calls `resolve_scope`),
    so valuation and projection never select different invoices. Invoices issued before today are history:
    a perpetual or date-bounded scope is an issue-day range over the recurring schedule, a count-bounded or
    ONE_OFF scope takes the next invoices from max(effective day, today), and a scope cut by W is truncated,
    never an error. The effective day is honoured for every duration kind. A named invoice that is already
    issued is valued from today (its cash is still ahead); a named future invoice counts only if it is
    issued inside W.

    With no recurring invoice and no named receivable, a ONE_OFF or count-bounded obligation with a stated
    base amount is that many undated invoices of that amount, issued on max(effective day, today).
    """
    today, hi = window(state, horizon_days)
    rec = _recurring(state, ob.counterparty_id)
    _check_scope(ob, rec)
    named = ob.base.receivable_id is not None
    if not named and rec is None:
        assert ob.base.amount_fen is not None
        n = 1 if ob.duration.kind == DurationKind.ONE_OFF else (ob.duration.invoices or 0)
        day = scope_start(ob, today)
        return [] if day >= hi else [DatedInvoice(day, ob.base.amount_fen)] * n
    scope = scope_at(state, ob)  # the scope acceptance writes: an unnamed one starts at scope_start(ob, today)
    if scope.receivable_ids is not None:
        issued = {r.id: r for r in state.receivables}
        out: list[DatedInvoice] = []
        for rid in scope.receivable_ids:
            if rid in issued:
                r = issued[rid]
                issue, face = max(r.issue_day, today), r.face_fen
            elif rec is not None and rid.startswith("RI:"):
                issue, face = int(rid.rsplit(":", 1)[1]), rec.face_fen
            else:
                raise ObligationError(f"{ob.id}: receivable {rid} not found")
            if today <= issue < hi:
                out.append(DatedInvoice(issue, face))
        return out
    assert rec is not None
    lo = scope.from_issue_day if scope.from_issue_day is not None else today
    top = hi if scope.until_issue_day is None else min(hi, scope.until_issue_day + 1)
    return [DatedInvoice(day, rec.face_fen)
            for day in recurring_issue_days(rec, lo, top)]


def _span(invoices: list[DatedInvoice], state: FinancialState, horizon_days: int) -> str:
    lo, hi = window(state, horizon_days)
    days = f"issued days {invoices[0].issue_day} to {invoices[-1].issue_day}" if invoices else "none in the window"
    return f"{days}; window days {lo} to {hi - 1}"


def _terms_extension(
    ob: Obligation, state: FinancialState, rate: Fraction, basis_label: str, horizon_days: int
) -> ConcessionValue:
    if ob.days_delta is None:
        raise ObligationError(f"{ob.id}: terms extension without days_delta")
    delta = ob.days_delta
    rec = _recurring(state, ob.counterparty_id)
    face = _invoice_face(ob, state, rec)
    counted = scoped_invoices(ob, state, horizon_days)
    value = post(sum((Fraction(i.face_fen) * delta * rate / DAYS_PER_YEAR for i in counted), Fraction(0)))
    kind = "shortening (gain)" if delta < 0 else "terms extension priced as a loan"
    return ConcessionValue(
        obligation_id=ob.id,
        value_fen=value,
        basis=f"{kind}: {basis_label}",
        formula=(f"Σ over {len(counted)} invoices ({_span(counted, state, horizon_days)}) of "
                 f"face × {delta}/365 × {pct(rate)} = {y(value)}"),
        per_invoice_fen=post(Fraction(face) * delta * rate / DAYS_PER_YEAR),
    )


def _price_adjustment(ob: Obligation, state: FinancialState, horizon_days: int) -> ConcessionValue:
    if ob.rate_bp is None:
        raise ObligationError(f"{ob.id}: price adjustment without rate_bp")
    rec = _recurring(state, ob.counterparty_id)
    face = _invoice_face(ob, state, rec)
    rate = bp(ob.rate_bp)
    counted = scoped_invoices(ob, state, horizon_days)
    # Each invoice is posted on its own (the price lands on the invoice): value = −Σ post(p × face).
    value = -sum((post(rate * i.face_fen) for i in counted), 0)
    return ConcessionValue(
        obligation_id=ob.id,
        value_fen=value,
        basis="price adjustment on future invoices (a positive rate is a gain to the supplier)",
        formula=(f"−Σ over {len(counted)} invoices ({_span(counted, state, horizon_days)}) of "
                 f"{pct(rate)} × face = {y(value)}"),
        per_invoice_fen=post(-rate * face),
    )


def _rebate(ob: Obligation) -> ConcessionValue:
    if ob.rate_bp is not None and ob.base.amount_fen is not None:
        value = post(bp(ob.rate_bp) * ob.base.amount_fen)
        formula = f"{pct(bp(ob.rate_bp))} × {y(ob.base.amount_fen)} = {y(value)}"
    elif ob.amount_fen is not None:
        value = ob.amount_fen
        formula = f"fixed rebate {y(value)}"
    else:
        raise ObligationError(f"{ob.id}: rebate needs rate_bp and a base amount, or a fixed amount")
    at_max = ob.contingency == Contingency.CONTINGENT
    basis = "contingent rebate counted at maximum" if at_max else "firm rebate"
    return ConcessionValue(obligation_id=ob.id, value_fen=value, basis=basis, formula=formula)


def _operational(ob: Obligation, horizon_days: int) -> ConcessionValue:
    if ob.amount_fen is None or ob.base.events_per_year is None:
        raise ObligationError(f"{ob.id}: operational concession needs amount_fen and events_per_year")
    value = post(Fraction(ob.amount_fen) * ob.base.events_per_year * horizon_days / DAYS_PER_YEAR)
    return ConcessionValue(
        obligation_id=ob.id,
        value_fen=value,
        basis="operational concession: cost per event × events a year",
        formula=f"{y(ob.amount_fen)} × {ob.base.events_per_year} × {horizon_days}/365 = {y(value)}",
    )


def _zero(ob: Obligation, basis: str, formula: str) -> ConcessionValue:
    return ConcessionValue(obligation_id=ob.id, value_fen=0, basis=basis, formula=formula)


def value_concession(
    ob: Obligation, state: FinancialState, rate: Fraction, basis_label: str, horizon_days: int
) -> ConcessionValue:
    if ob.type == ObligationType.CLAIMED_PRIOR_CONCESSION or ob.contingency == Contingency.CLAIMED_UNEVIDENCED:
        return _zero(ob, UNEVIDENCED_BASIS, "0 (never booked)")
    match ob.type:
        case ObligationType.TERMS_EXTENSION:
            return _terms_extension(ob, state, rate, basis_label, horizon_days)
        case ObligationType.PRICE_ADJUSTMENT:
            return _price_adjustment(ob, state, horizon_days)
        case ObligationType.CONTINGENT_REBATE:
            return _rebate(ob)
        case ObligationType.OPERATIONAL_CONCESSION:
            return _operational(ob, horizon_days)
        case ObligationType.IMMEDIATE_DISCOUNT:
            return _zero(
                ob,
                "immediate discount: settled in cash now and capped separately, not a forward concession",
                "0 (see the immediate-discount cap)",
            )
        case ObligationType.VOLUME_COMMITMENT:
            return _zero(ob, "volume commitment: no forward cost to the supplier", "0")
    raise ObligationError(f"{ob.id}: unsupported obligation type {ob.type}")  # pragma: no cover


def value_concessions(
    obligations: list[Obligation],
    state: FinancialState,
    funding_rate: Ratio,
    basis_label: str,
    horizon_days: int,
) -> list[ConcessionValue]:
    """One ConcessionValue per obligation, in input order. The window starts at `state.as_of_day`."""
    if horizon_days < 0:
        raise ObligationError("horizon_days must not be negative")
    rate = funding_rate.value
    return [value_concession(ob, state, rate, basis_label, horizon_days) for ob in obligations]


# ---------------------------------------------------------------- pro forma of an extension (F-FIN-07)


@dataclass(frozen=True, slots=True)
class ExtensionProForma:
    """Steady-state pro forma of a lengthening terms extension funded permanently, exact (not posted).

    Callers add the exact values of every extension and post each total once."""

    extra_debt: Fraction
    monthly_service: Fraction


def pro_forma_scale(in_scope: int, in_window: int, *, perpetual: bool) -> Fraction:
    """How much of the steady state a scope carries.

    A perpetual scope that issues at least one invoice in the window is the steady state: 1. A finite scope
    (ONE_OFF, count- or date-bounded) carries min(1, invoices in scope ÷ invoices in W) of it: 3 of the 13
    monthly invoices of a year is 3/13 of the steady state, a ONE_OFF is 1/13. A scope with no invoice in
    the window, or a window with no invoice, carries none."""
    if in_scope <= 0 or in_window <= 0:
        return Fraction(0)
    return Fraction(1) if perpetual else min(Fraction(1), Fraction(in_scope, in_window))


def extension_extra_debt(face_fen: int, delta_days: int, every_days: int, scale: Fraction = Fraction(1)) -> Fraction:
    """Extra receivables a lengthening extension ties up in steady state: face × delta / every_days (an
    average stock: delta days of sales at one invoice per `every_days`), × `scale` for a finite scope."""
    if delta_days <= 0 or every_days <= 0:
        return Fraction(0)
    return Fraction(face_fen) * delta_days / every_days * scale


def extension_monthly_service(extra_debt: Fraction, rate: Fraction) -> Fraction:
    """Monthly funding cost of that debt: extra debt × r / 12."""
    return extra_debt * rate / 12


def extension_pro_forma(
    ob: Obligation, state: FinancialState, rate: Fraction, horizon_days: int
) -> ExtensionProForma | None:
    """Pro forma of one lengthening terms extension of a recurring buyer. None when it is not one (a shortening,
    or the buyer has no recurring invoice); zero when no invoice of its scope is issued in W.

    extra debt = face × delta / every_days; monthly service = extra debt × r / 12; scaled by
    `pro_forma_scale` for a finite scope. The one function the verifier and capex share."""
    if ob.type != ObligationType.TERMS_EXTENSION or (ob.days_delta or 0) <= 0:
        return None
    rec = _recurring(state, ob.counterparty_id)
    if rec is None or rec.every_days <= 0:
        return None
    lo, hi = window(state, horizon_days)
    n_scope = len(scoped_invoices(ob, state, horizon_days))
    perpetual = ob.duration.kind == DurationKind.RECURRING_PERPETUAL
    scale = pro_forma_scale(n_scope, len(recurring_issue_days(rec, lo, hi)), perpetual=perpetual)
    debt = extension_extra_debt(rec.face_fen, ob.days_delta or 0, rec.every_days, scale)
    return ExtensionProForma(debt, extension_monthly_service(debt, rate))
