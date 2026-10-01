"""Server-formatted view models for the UI. The UI never computes money: every amount ships as
integer fen (for chart axes) plus a display string."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.domain.models import (
    CompiledOffer,
    FinancialState,
    Mandate,
    Obligation,
    ObligationType,
    Outcome,
    Tier,
    Trajectory,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.funding import menu_view
from app.funding.rates import early_pay_rate
from app.verifier import VerdictBundle, autonomy_gaps


class Money(BaseModel):
    fen: int
    text: str

    @classmethod
    def of(cls, fen: int) -> Money:
        return cls(fen=fen, text=fmt_yuan(fen))


class DayView(BaseModel):
    day: int
    closing: Money
    debt: Money
    forward_concession: Money
    below_floor: bool
    events: list[dict]


class MonthView(BaseModel):
    month: int
    dscr: str | None
    leverage: str | None
    debt_service: Money
    total_debt: Money


class TrajectoryView(BaseModel):
    mode: str
    floor: Money
    min_cash: Money
    min_cash_day: int
    first_breach_day: int | None
    days: list[DayView]
    months: list[MonthView]
    interest: Money
    fees: Money
    discounts: Money


def trajectory_view(t: Trajectory, floor_fen: int) -> TrajectoryView:
    return TrajectoryView(
        mode=t.mode.value,
        floor=Money.of(floor_fen),
        min_cash=Money.of(t.min_cash_fen),
        min_cash_day=t.min_cash_day,
        first_breach_day=t.first_breach_day,
        days=[
            DayView(
                day=d.day,
                closing=Money.of(d.closing_fen),
                debt=Money.of(d.debt_outstanding_fen),
                forward_concession=Money.of(d.forward_concession_fen),
                below_floor=d.closing_fen < floor_fen,
                events=[
                    {"kind": e.kind.value, "amount": Money.of(e.amount_fen).model_dump(), "label": e.label,
                     "ref": e.ref, "formula": e.formula}
                    for e in d.events
                ],
            )
            for d in t.days
        ],
        months=[
            MonthView(
                month=m.month,
                dscr=m.dscr.text + "x" if m.dscr else None,
                leverage=m.leverage.text + "x" if m.leverage else None,
                debt_service=Money.of(m.debt_service_fen),
                total_debt=Money.of(m.total_debt_fen),
            )
            for m in t.months
        ],
        interest=Money.of(t.interest_posted_fen),
        fees=Money.of(t.fees_posted_fen),
        discounts=Money.of(t.discounts_posted_fen),
    )


# ---------------------------------------------------------------- owner verdict views (supplier side only)
# Read views assembled from typed fields and existing public functions: they decide nothing, and they are
# never part of a counter's outbound text or of any counterparty response (INVARIANT 7).


def _covered(ob: Obligation) -> str:
    """One plain sentence for a bound obligation, from its own typed fields."""
    base = fmt_yuan(ob.base.amount_fen) if ob.base.amount_fen is not None else None
    what = ob.base.receivable_id or ob.base.kind.value.lower().replace("_", " ")
    day = f" on day {ob.effective_day}" if ob.effective_day is not None else ""
    rate = fmt_pct(bp(ob.rate_bp)) if ob.rate_bp is not None else None
    if ob.type == ObligationType.IMMEDIATE_DISCOUNT and rate is not None:
        return f"early payment of {base + ' of ' if base else ''}{what} at {rate}{day}"
    parts = [f"{ob.type.value.lower().replace('_', ' ')} on {what}"]
    if base:
        parts.append(f"base {base}")
    if rate:
        parts.append(f"at {rate}")
    if ob.amount_fen is not None:
        parts.append(f"of {fmt_yuan(ob.amount_fen)}")
    if ob.days_delta is not None:
        parts.append(f"{ob.days_delta:+d} days")
    elif ob.target_terms_days is not None:
        parts.append(f"to {ob.target_terms_days}-day terms")
    return " ".join(parts) + day


def autonomy_view(offer: CompiledOffer, bundle: VerdictBundle, state: FinancialState) -> dict[str, Any]:
    """Why the offer could (or could not) be accepted without the owner, positively stated."""
    v, bound = bundle.verdict, list(bundle.bound_obligations)
    gaps = autonomy_gaps(offer, bound, state)
    legs = [o for o in bound if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    return {
        "eligible": offer.autonomy_eligible,
        "accepted_alone": v.outcome == Outcome.ACCEPT and v.required_tier == Tier.TIER_1,
        "whole_invoice": (not any(g.startswith(f"{o.id}:") for o in legs for g in gaps)) if legs else None,
        "covered": [_covered(o) for o in bound],
        "gaps": gaps,
        "notes": list(offer.autonomy_notes),
    }


def annualised_view(obligations: Sequence[Obligation], state: FinancialState, mandate: Mandate) -> list[dict[str, Any]]:
    """The annual rate of every early-pay discount, d/(1-d) x 365/days_early (as the verifier's MAX_APR check
    computes it), beside the committed funding sources' all-in rates from the funding menu."""
    due = {r.id: r.due_day for r in state.receivables}
    compare_to = [{"label": r.name, "annual_rate_display": r.all_in_display}
                  for r in menu_view(state, mandate) if r.committed and r.owner_approved and r.is_debt]
    out = []
    for ob in obligations:
        if ob.type != ObligationType.IMMEDIATE_DISCOUNT or ob.rate_bp is None or ob.effective_day is None:
            continue
        rid = ob.base.receivable_id
        if rid is None or rid not in due:
            continue
        days = due[rid] - ob.effective_day
        if days <= 0:
            continue
        d = bp(ob.rate_bp)
        rate = early_pay_rate(d, days)
        out.append({
            "obligation_id": ob.id, "receivable_id": rid, "discount_display": fmt_pct(d), "days_early": days,
            "annual_rate_display": fmt_pct(rate),
            "formula": f"d/(1−d) × 365/days_early = {fmt_pct(d)}/(1 − {fmt_pct(d)}) × 365/{days} = {fmt_pct(rate, 4)}",
            "compare_to": [dict(c) for c in compare_to],
        })
    return out


def owner_verdict_extras(bundle: VerdictBundle, offer: CompiledOffer, state: FinancialState,
                         mandate: Mandate) -> dict[str, Any]:
    """What the owner's screens add to a verdict: the passed checks, the autonomy proof and the annualised cost
    of every early-pay discount (the bound legs and each counter's)."""
    legs = [*bundle.bound_obligations, *(o for c in bundle.verdict.counters for o in c.obligations)]
    return {
        "passed_checks": [json.loads(p.model_dump_json()) for p in bundle.passed_checks],
        "autonomy": autonomy_view(offer, bundle, state),
        "annualised": annualised_view(legs, state, mandate),
    }
