"""A terms extension priced as a loan on three funding bases (spec §7.5).

1. Notional credit-line rate: shown only; the clean-down rule means the line cannot carry it.
2. Committed marginal source: what hard constraints and the concession cap use.
3. Expected plan: a bridge on the committed marginal source for the cheaper pending source's lead
   time, then that source for the rest of the horizon. Shown to the owner, relied on only once
   approved (INVARIANT 11).

Every value comes from `financial.value_concessions`; this module only chooses the rate.
"""

from __future__ import annotations

from fractions import Fraction

from app.domain.models import (
    ConcessionValue,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    Mandate,
    Obligation,
    ObligationType,
)
from app.domain.money import Ratio, fmt_yuan
from app.financial import value_concessions
from app.funding.rates import all_in_rate, marginal_cost, pct, permanent_sources

EXPECTED_STATUSES = frozenset({FacilityStatus.PENDING, FacilityStatus.NOT_APPLIED})


def _value(ob: Obligation, state: FinancialState, rate: Fraction, label: str, horizon: int) -> ConcessionValue:
    return value_concessions([ob], state, Ratio.of(rate), label, horizon)[0]


def extension_cost_bases(state: FinancialState, obligation: Obligation, mandate: Mandate) -> list[ConcessionValue]:
    """[notional line, committed marginal source, expected plan] for a TERMS_EXTENSION. A basis is
    left out when the menu has no such source (no line; no cheaper pending source)."""
    if obligation.type != ObligationType.TERMS_EXTENSION:
        raise ValueError(f"{obligation.id}: extension_cost_bases needs a TERMS_EXTENSION, not {obligation.type}")
    horizon = mandate.forward_concession_horizon_days
    out: list[ConcessionValue] = []

    lines = sorted(
        (all_in_rate(f)[0], f.id, f) for f in state.facilities
        if f.kind == FacilityKind.CREDIT_LINE and f.owner_approved and f.status == FacilityStatus.COMMITTED
    )
    if lines:
        rate, _, f = lines[0]
        out.append(_value(obligation, state, rate,
                          f"notional {f.name} rate {pct(rate)} (not usable: clean-down rules out a permanent need)",
                          horizon))

    m_ratio, m_id = marginal_cost(state, mandate)
    m_rate = m_ratio.value
    m_fac = next(f for f in state.facilities if f.id == m_id)
    committed = _value(obligation, state, m_rate, f"committed marginal source: {m_fac.name} {pct(m_rate)}", horizon)
    out.append(committed)

    pending = [(r, f) for r, f in permanent_sources(state, mandate, EXPECTED_STATUSES) if r < m_rate]
    if pending:
        g_rate, g = pending[0]
        bridge = g.lead_time_days
        if 0 <= bridge < horizon:
            blended = (m_rate * bridge + g_rate * (horizon - bridge)) / horizon
            label = (f"expected plan: {bridge}-day {m_fac.name} bridge at {pct(m_rate)}, then {g.name} at "
                     f"{pct(g_rate)} (shown only; relied on once approved)")
            v = _value(obligation, state, blended, label, horizon)
            formula = (f"extra receivables × ({pct(m_rate)} × {bridge}/365 + {pct(g_rate)} × "
                       f"{horizon - bridge}/365) × 365/365 = {fmt_yuan(v.value_fen)}; {v.formula}")
            out.append(v.model_copy(update={"formula": formula, "per_invoice_fen": None}))
    return out
