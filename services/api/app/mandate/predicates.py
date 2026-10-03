"""Mandate predicates on a conservative trajectory and an offer's valued obligations.

Netting (INVARIANT 5): a negative concession value is a gain to the supplier. Only obligations
whose contingency is FIRM may contribute a negative value; a negative value from any other
obligation (CONTINGENT, CLAIMED_UNEVIDENCED, or a value with no matching obligation) counts as zero.
Positive values always count in full.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.domain.models import (
    ConcessionValue,
    Contingency,
    FinancialState,
    Mandate,
    Obligation,
    ObligationType,
    Trajectory,
    Violation,
    ViolationCode,
)
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan


def check_reserve(trajectory: Trajectory, mandate: Mandate) -> Violation | None:
    """RESERVE_BREACH on the first day closing < min_cash_fen. `curable` is left None: the
    verifier decides whether the committed plan cures it."""
    floor = mandate.min_cash_fen
    days = sorted(trajectory.days, key=lambda p: p.day)
    first = next((i for i, p in enumerate(days) if p.closing_fen < floor), None)
    if first is None:
        return None
    breach = days[first]
    episode = []
    recovery_day = None
    for p in days[first:]:
        if p.closing_fen >= floor:
            recovery_day = p.day
            break
        episode.append(p)
    shortfall = floor - breach.closing_fen
    worst = min(episode, key=lambda p: (p.closing_fen, p.day))
    total_breach_days = sum(1 for p in days if p.closing_fen < floor)
    return Violation(
        code=ViolationCode.RESERVE_BREACH,
        message=f"Projected cash falls below the reserve on day {breach.day}",
        day=breach.day,
        observed=fmt_yuan(breach.closing_fen),
        limit=fmt_yuan(floor),
        curable=None,
        formula=(
            f"closing_cash(day {breach.day}) >= min_cash: {fmt_yuan(breach.closing_fen)} < {fmt_yuan(floor)}, "
            f"shortfall {fmt_yuan(shortfall)}"
        ),
        inputs={
            "day": str(breach.day),
            "closing_cash": fmt_yuan(breach.closing_fen),
            "min_cash": fmt_yuan(floor),
            "shortfall": fmt_yuan(shortfall),
            "shortfall_fen": str(shortfall),
            "max_shortfall": fmt_yuan(floor - worst.closing_fen),
            "max_shortfall_day": str(worst.day),
            "recovery_day": "none within horizon" if recovery_day is None else str(recovery_day),
            "days_below_floor_in_first_episode": str(len(episode)),
            "days_below_floor_total": str(total_breach_days),
            "mode": str(trajectory.mode),
        },
    )


@dataclass(frozen=True)
class _Netted:
    gross_fen: int  # positive values (concessions)
    firm_gains_fen: int  # negative values from FIRM obligations (<= 0)
    ignored_gains_fen: int  # negative values from non-FIRM obligations, counted as zero (<= 0)

    @property
    def net_fen(self) -> int:
        return self.gross_fen + self.firm_gains_fen


def _net(values: list[ConcessionValue], by_id: dict[str, Obligation]) -> _Netted:
    gross = firm = ignored = 0
    for cv in values:
        if cv.value_fen >= 0:
            gross += cv.value_fen
            continue
        ob = by_id.get(cv.obligation_id)
        if ob is not None and ob.contingency == Contingency.FIRM:
            firm += cv.value_fen
        else:
            ignored += cv.value_fen
    return _Netted(gross, firm, ignored)


def _cap_violation(
    code: ViolationCode, scope: str, existing: int, netted: _Netted, cap: int, extra: dict[str, str]
) -> Violation | None:
    total = existing + netted.net_fen
    if total <= cap:
        return None
    return Violation(
        code=code,
        message=f"Forward concessions ({scope}) would reach {fmt_yuan(total)}, above the cap",
        observed=fmt_yuan(total),
        limit=fmt_yuan(cap),
        formula=(
            f"existing + new concessions + FIRM gains <= cap: {fmt_yuan(existing)} + "
            f"{fmt_yuan(netted.gross_fen)} + ({fmt_yuan(netted.firm_gains_fen)}) = {fmt_yuan(total)} "
            f"> {fmt_yuan(cap)}"
        ),
        inputs={
            **extra,
            "existing": fmt_yuan(existing),
            "new_concessions": fmt_yuan(netted.gross_fen),
            "firm_gains_netted": fmt_yuan(netted.firm_gains_fen),
            "contingent_gains_ignored": fmt_yuan(netted.ignored_gains_fen),
            "total": fmt_yuan(total),
            "total_fen": str(total),
            "cap": fmt_yuan(cap),
            "netting_rule": "only FIRM gains offset concessions; contingent gains count as zero",
        },
    )


def check_concession_caps(
    obligations: list[Obligation],
    concession_values: list[ConcessionValue],
    state: FinancialState,
    mandate: Mandate,
    counterparty_id: str | None,
) -> list[Violation]:
    by_id = {o.id: o for o in obligations}
    out: list[Violation] = []

    existing_all = sum(c.value_fen for c in state.forward_concessions)
    v = _cap_violation(
        ViolationCode.AGG_CONCESSION_EXCEEDED,
        "all buyers",
        existing_all,
        _net(concession_values, by_id),
        mandate.max_aggregate_forward_concession_fen,
        {"scope": "aggregate"},
    )
    if v is not None:
        out.append(v)

    # Per-buyer: attribute each value to its obligation's counterparty (else the offer's).
    grouped: dict[str, list[ConcessionValue]] = {}
    for cv in concession_values:
        ob = by_id.get(cv.obligation_id)
        buyer = ob.counterparty_id if ob is not None else counterparty_id
        if buyer is not None:
            grouped.setdefault(buyer, []).append(cv)
    buyers = sorted(set(grouped) | ({counterparty_id} if counterparty_id else set()))
    for buyer in buyers:
        cap = mandate.per_buyer_caps_fen.get(buyer)
        if cap is None:
            continue
        existing = sum(c.value_fen for c in state.forward_concessions if c.counterparty_id == buyer)
        v = _cap_violation(
            ViolationCode.PER_BUYER_CAP_EXCEEDED,
            f"buyer {buyer}",
            existing,
            _net(grouped.get(buyer, []), by_id),
            cap,
            {"scope": "per_buyer", "counterparty_id": buyer},
        )
        if v is not None:
            out.append(v)
    return out


def discount_rate(ob: Obligation) -> Fraction | None:
    """The exact discount rate of an IMMEDIATE_DISCOUNT: its stated rate, or, for a discount stated as a fixed sum,
    the sum over the portion it applies to (`amount_fen / base.amount_fen`, an exact Fraction; binding sets the
    portion to the named invoice's face or the stated base). None when neither is known: the obligation is then
    unbound and the verdict is UNRESOLVED_SCOPE. Every early-pay check (the mandate's discount cap, ADR-0007's
    three tests, the rate ceiling) runs on this rate, so "take ¥8,000 off ¥420,000" is tested as 8,000/420,000."""
    if ob.type != ObligationType.IMMEDIATE_DISCOUNT:
        return None
    if ob.rate_bp is not None:
        return bp(ob.rate_bp)
    if ob.amount_fen is not None and ob.base.amount_fen:
        return Fraction(ob.amount_fen, ob.base.amount_fen)
    return None


def _rate_text(ob: Obligation, rate: Fraction) -> str:
    if ob.rate_bp is not None:
        return f"{ob.rate_bp} bp"
    return f"{fmt_yuan(ob.amount_fen or 0)} / {fmt_yuan(ob.base.amount_fen or 0)} = {fmt_pct(rate, 4)}"


def check_immediate_discounts(obligations: list[Obligation], mandate: Mandate) -> list[Violation]:
    if mandate.max_immediate_discount_bp is None:
        return []
    cap = mandate.max_immediate_discount_bp
    out = []
    for ob in obligations:
        rate = discount_rate(ob)
        if rate is None or rate <= bp(cap):  # exact: a fixed sum is compared as its exact Fraction
            continue
        shown = fmt_pct(rate) if ob.rate_bp is not None else fmt_pct(rate, 4)
        out.append(
            Violation(
                code=ViolationCode.IMMEDIATE_DISCOUNT_EXCEEDED,
                message=f"Immediate discount {shown} exceeds the mandate cap",
                day=ob.effective_day,
                observed=shown,
                limit=fmt_pct(bp(cap)),
                formula=f"discount_rate <= max_immediate_discount: {_rate_text(ob, rate)} > {cap} bp",
                inputs={
                    "obligation_id": ob.id,
                    "counterparty_id": ob.counterparty_id,
                    **({"rate_bp": str(ob.rate_bp)} if ob.rate_bp is not None else
                       {"amount_fen": str(ob.amount_fen), "portion_fen": str(ob.base.amount_fen),
                        "exact_rate": f"{rate.numerator}/{rate.denominator}"}),
                    "cap_bp": str(cap),
                },
                spans=ob.spans,
            )
        )
    return out


def check_predicates(
    trajectory: Trajectory,
    obligations: list[Obligation],
    concession_values: list[ConcessionValue],
    state: FinancialState,
    mandate: Mandate,
    counterparty_id: str | None,
) -> list[Violation]:
    """RESERVE_BREACH, AGG_CONCESSION_EXCEEDED, PER_BUYER_CAP_EXCEEDED, IMMEDIATE_DISCOUNT_EXCEEDED."""
    out: list[Violation] = []
    reserve = check_reserve(trajectory, mandate)
    if reserve is not None:
        out.append(reserve)
    out.extend(check_concession_caps(obligations, concession_values, state, mandate, counterparty_id))
    out.extend(check_immediate_discounts(obligations, mandate))
    return out


def check_apr(annual_rate: Ratio, mandate: Mandate, label: str) -> Violation | None:
    """MAX_APR_EXCEEDED when the exact all-in annual rate is above the mandate's max APR."""
    cap = bp(mandate.max_apr_bp)
    if annual_rate.value <= cap:
        return None
    return Violation(
        code=ViolationCode.MAX_APR_EXCEEDED,
        message=f"{label}: all-in annual rate {fmt_pct(annual_rate.value)} exceeds the mandate maximum",
        observed=fmt_pct(annual_rate.value, 4),
        limit=fmt_pct(cap),
        formula=f"all_in_annual_rate <= max_apr: {fmt_pct(annual_rate.value, 4)} > {fmt_pct(cap)}",
        inputs={
            "label": label,
            "rate_exact": f"{annual_rate.num}/{annual_rate.den}",
            "max_apr_bp": str(mandate.max_apr_bp),
        },
    )
