"""Owner-goal constraints (`OwnerConstraints`): what a package or a counter must satisfy on top of the
mandate. Pure checks over typed obligations and their forward values; they only ever tighten."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.models import ConcessionValue, FinancialState, Obligation, ObligationType
from app.domain.money import bp, fmt_pct
from app.financial.invoices import terms_in_force
from app.verifier.bind import open_receivables
from app.verifier.models import OwnerConstraints


def _current_terms(state: FinancialState, counterparty_id: str) -> int | None:
    """The buyer's terms now: those in force for the next recurring invoice (accepted adjustments applied, as the
    verifier's bind and counters read them), else the first open invoice's."""
    in_force = terms_in_force(state, counterparty_id)
    if in_force is not None:
        return in_force
    rcvs = open_receivables(state, counterparty_id)
    return rcvs[0].terms_days if rcvs else None


def terms_after(ob: Obligation, state: FinancialState) -> int | None:
    """The payment terms a TERMS_EXTENSION leaves in place."""
    if ob.target_terms_days is not None:
        return ob.target_terms_days
    current = _current_terms(state, ob.counterparty_id)
    if current is None or ob.days_delta is None:
        return None
    return current + ob.days_delta


def breaches(
    obligations: Sequence[Obligation],
    values: Sequence[ConcessionValue],
    state: FinancialState,
    constraints: OwnerConstraints,
) -> list[str]:
    """Human-readable reasons the obligations break the owner's constraints (empty: they satisfy them)."""
    out: list[str] = []
    by_id = {cv.obligation_id: cv for cv in values}
    for ob in obligations:
        if (constraints.max_early_pay_bp is not None and ob.type == ObligationType.IMMEDIATE_DISCOUNT
                and ob.rate_bp is not None and ob.rate_bp > constraints.max_early_pay_bp):
            out.append(f"early-pay discount {fmt_pct(bp(ob.rate_bp))} above the owner's "
                       f"{fmt_pct(bp(constraints.max_early_pay_bp))}")
        if constraints.zero_forward_concessions:
            cv = by_id.get(ob.id)
            if cv is not None and cv.value_fen > 0:
                out.append(f"{ob.type.value} is a forward concession; the owner wants none")
        if constraints.max_terms_days is not None and ob.type == ObligationType.TERMS_EXTENSION:
            after = terms_after(ob, state)
            if after is None or after > constraints.max_terms_days:
                out.append(f"payment terms {after if after is not None else 'unknown'} days above the owner's "
                           f"{constraints.max_terms_days} days")
    return out


def describe(constraints: OwnerConstraints) -> str:
    parts = []
    if constraints.max_early_pay_bp is not None:
        parts.append(f"early pay at most {fmt_pct(bp(constraints.max_early_pay_bp))}")
    if constraints.zero_forward_concessions:
        parts.append("zero forward concessions")
    if constraints.max_terms_days is not None:
        parts.append(f"terms at most {constraints.max_terms_days} days")
    return ", ".join(parts) or "no constraint"
