"""Forward value of obligations over the concession horizon (spec v2 §6.5, §7.5; ADR-0002).

Every value is exact until reported, then rounded once with money.post. A positive value is a
cost to the supplier; a negative value is a gain (a shorter term, a price increase). Whether a gain
may offset a cost is the mandate's decision (only FIRM gains net; INVARIANT 5), not this module's.
"""

from __future__ import annotations

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
    if ob.base.receivable_id is not None:
        for r in state.receivables:
            if r.id == ob.base.receivable_id:
                return r.face_fen
        raise ObligationError(f"{ob.id}: receivable {ob.base.receivable_id} not found")
    if rec is not None:
        return rec.face_fen
    if ob.base.amount_fen is not None:
        return ob.base.amount_fen
    raise ObligationError(f"{ob.id}: no invoice face (no recurring invoice and no base amount)")


def _invoice_count(ob: Obligation, rec: RecurringInvoice | None, horizon_days: int) -> tuple[int, bool]:
    """How many invoices the obligation touches and whether it is the open-ended recurring case.

    Recurring: n = horizon_days // every_days. Bounded: N invoices (or the issues up to end_day,
    capped at n). One-off or a named receivable: 1.
    """
    if ob.base.receivable_id is not None or ob.duration.kind == DurationKind.ONE_OFF:
        return 1, False
    if ob.duration.kind == DurationKind.RECURRING_BOUNDED:
        if ob.duration.invoices is not None:
            if ob.duration.invoices < 0:
                raise ObligationError(f"{ob.id}: negative invoice count")
            return ob.duration.invoices, False
        if ob.duration.end_day is not None:
            if rec is None:
                raise ObligationError(f"{ob.id}: end-day bound needs the buyer's recurring invoice")
            start = max(ob.effective_day or 0, rec.next_issue_day)
            first = start + (-(start - rec.next_issue_day)) % rec.every_days
            last = min(ob.duration.end_day, horizon_days)
            issues = 0 if last < first else (last - first) // rec.every_days + 1
            return min(issues, horizon_days // rec.every_days), False
        raise ObligationError(f"{ob.id}: bounded duration with neither invoices nor end_day")
    if rec is None:
        raise ObligationError(f"{ob.id}: recurring obligation but {ob.counterparty_id} has no recurring invoice")
    return horizon_days // rec.every_days, True


def _terms_extension(
    ob: Obligation, state: FinancialState, rate: Fraction, basis_label: str, horizon_days: int
) -> ConcessionValue:
    if ob.days_delta is None:
        raise ObligationError(f"{ob.id}: terms extension without days_delta")
    rec = _recurring(state, ob.counterparty_id)
    face = _invoice_face(ob, state, rec)
    n, recurring = _invoice_count(ob, rec, horizon_days)
    delta = ob.days_delta
    per_invoice_exact = Fraction(face) * delta / DAYS_PER_YEAR * rate
    per_invoice = post(per_invoice_exact)
    if recurring:
        extra = Fraction(face) * n * delta / DAYS_PER_YEAR
        value = post(extra * rate * horizon_days / DAYS_PER_YEAR)
        formula = (
            f"extra receivables {y(post(extra))} = {y(face)} × {n} × {delta}/365; "
            f"× {pct(rate)} × {horizon_days}/365 = {y(value)}"
        )
    else:
        value = post(per_invoice_exact * n)
        formula = f"{n} × {y(face)} × {delta}/365 × {pct(rate)} = {y(value)}"
    kind = "shortening (gain)" if delta < 0 else "terms extension priced as a loan"
    return ConcessionValue(
        obligation_id=ob.id,
        value_fen=value,
        basis=f"{kind}: {basis_label}",
        formula=formula,
        per_invoice_fen=per_invoice,
    )


def _price_adjustment(ob: Obligation, state: FinancialState, horizon_days: int) -> ConcessionValue:
    if ob.rate_bp is None:
        raise ObligationError(f"{ob.id}: price adjustment without rate_bp")
    rec = _recurring(state, ob.counterparty_id)
    face = _invoice_face(ob, state, rec)
    n, _ = _invoice_count(ob, rec, horizon_days)
    rate = bp(ob.rate_bp)
    value = post(-rate * face * n)
    return ConcessionValue(
        obligation_id=ob.id,
        value_fen=value,
        basis="price adjustment on future invoices (a positive rate is a gain to the supplier)",
        formula=f"−1 × {pct(rate)} × {y(face)} × {n} = {y(value)}",
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
    """One ConcessionValue per obligation, in input order."""
    if horizon_days < 0:
        raise ObligationError("horizon_days must not be negative")
    rate = funding_rate.value
    return [value_concession(ob, state, rate, basis_label, horizon_days) for ob in obligations]
