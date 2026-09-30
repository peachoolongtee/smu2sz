"""The funding router: cheapest admissible plan, the spec §7.4 comparison table, and the `Router`
class that satisfies `app.domain.ports.FundingRouter`.

COMMITTED basis (the only one a hard constraint may rely on, INVARIANT 4 and 11) uses COMMITTED
facilities and the CONSERVATIVE trajectory. EXPECTED basis also uses owner-approved PENDING and
NOT_APPLIED facilities on the EXPECTED trajectory; it is labelled "expected" and shown only.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import (
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingAction,
    FundingActionKind,
    FundingPlan,
    Mandate,
    Obligation,
    RejectedCandidate,
    Violation,
    ViolationCode,
)
from app.domain.money import Ratio, fmt_yuan
from app.funding.models import ComparisonResult, ComparisonRow
from app.funding.rates import NoPermanentSourceError, marginal_cost
from app.funding.search import Eval, Search, Slot, action_key, cost_display, plan_id, reserve_violation

EXPECTED_LABEL = "expected plan: shown only, never relied on (uses facilities not yet committed)"


@dataclass
class Alternative:
    key: str
    label: str
    components: list[str]
    actions: list[FundingAction]
    ev: Eval | None  # None when not computable
    reasons: list[ViolationCode]
    note: str = ""


# ---------------------------------------------------------------- canonical alternatives (spec §7.4)


def _first_line(search: Search) -> Slot | None:
    lines = [s for s in search.slots if s.facility.kind == FacilityKind.CREDIT_LINE]
    return min(lines, key=lambda s: (s.repay_day or 0, s.facility.id)) if lines else None


def _target_early_pay(search: Search) -> Slot | None:
    """The early-pay slot on the receivable that pays first after the gap opens."""
    first = search.first_breach
    eps = [s for s in search.slots if s.kind == FundingActionKind.EARLY_PAY and first is not None and s.arrival <= first]
    if not eps:
        return None
    return min(eps, key=lambda s: (search.rcvs[s.receivable_id or ""].due_day, s.sort_key))


def _alt(search: Search, key: str, label: str, actions: list[FundingAction]) -> Alternative:
    actions = search.ordered(actions)
    ev = search.evaluate(actions)
    comps = [search.action_label(a) for a in actions]
    return Alternative(key, label, comps, actions, ev if ev.traj is not None else None, ev.reasons,
                       ev.error or "")


def alternatives(search: Search) -> list[Alternative]:
    """Full discount, line + partial early pay (the 1.0 optimum), line + guaranteed loan, line only."""
    if not search.breach_days:
        return []
    need, first = search.need_fen, search.breach_days[0]
    out: list[Alternative] = []
    ep = _target_early_pay(search)
    line = _first_line(search)
    line_amt = min(line.cap_fen, need) if line else 0
    if ep is not None:
        d = f"{ep.rate_bp / 100:g}%"
        out.append(_alt(search, "full_discount", f"Discount the whole invoice at {d}", [ep.action(ep.cap_fen)]))
        if line is not None and line_amt < need:
            ev = search.fill([line.action(line_amt)], ep, prune=False)
            if ev is not None:
                out.append(_alt(search, "line_partial_early_pay",
                                f"Line + early payment on part of the invoice at {d}", list(ev.actions)))
    ggl = next((f for f in sorted(search.state.facilities, key=lambda f: f.id)
                if f.kind == FacilityKind.GOV_GUARANTEED_LOAN and f.owner_approved), None)
    if ggl is not None and line is not None and line_amt < need:
        loan = FundingAction(kind=FundingActionKind.DRAW, facility_id=ggl.id, day=0, amount_fen=need - line_amt)
        actions = [line.action(line_amt), loan]
        comps = [search.action_label(line.action(line_amt)),
                 f"{ggl.name}: draw {fmt_yuan(need - line_amt)} (arrives day {ggl.lead_time_days})"]
        reasons: list[ViolationCode] = []
        if ggl.status not in search.statuses:
            reasons.append(ViolationCode.UNCOMMITTED_FACILITY)
        if ggl.lead_time_days > first:
            reasons.append(ViolationCode.LEAD_TIME_TOO_LONG)
        note = (f"{ggl.status.value.lower().replace('_', ' ')}; cash on day {ggl.lead_time_days}, "
                f"gap opens on day {first}")
        if ggl.status in search.statuses:
            ev = search.evaluate(actions)
            reasons += [c for c in ev.reasons if c not in reasons]
            out.append(Alternative("line_guaranteed_loan", "Line + guaranteed loan", comps, actions,
                                   ev if ev.traj is not None else None, reasons, note))
        else:
            out.append(Alternative("line_guaranteed_loan", "Line + guaranteed loan", comps, actions, None, reasons, note))
    if line is not None:
        out.append(_alt(search, "line_only", "Line only", [line.action(line_amt)]))
    return out


def _note(alt: Alternative, search: Search) -> str:
    parts = []
    if alt.ev is not None and alt.ev.cost is not None:
        parts.append(f"cost {fmt_yuan(alt.ev.cost)}")
    if alt.ev is not None and alt.ev.breach_day is not None:
        parts.append(f"RESERVE_BREACH on day {alt.ev.breach_day}")
    if not alt.reasons and alt.ev is not None:
        parts.append("admissible but dearer than the selected plan")
    if alt.note:
        parts.append(alt.note)
    return "; ".join(parts)


# ---------------------------------------------------------------- plan


def _marginal(state: FinancialState, mandate: Mandate) -> tuple[Ratio | None, str | None]:
    try:
        return marginal_cost(state, mandate)
    except NoPermanentSourceError:
        return None, None


def _run(state: FinancialState, obligations: list[Obligation], mandate: Mandate, basis: str) -> Search:
    search = Search(state, obligations, mandate, basis)
    search.run()
    return search


def _build_plan(search: Search, state: FinancialState, mandate: Mandate) -> FundingPlan:
    basis = search.basis
    rate, fid = _marginal(state, mandate)
    common = {"basis": basis, "need_fen": search.need_fen, "marginal_cost_annual": rate, "marginal_facility_id": fid}
    if not search.breach_days:
        return FundingPlan(id=plan_id(basis, [], state, mandate), actions=[], costs=[], total_cost_fen=0,
                           admissible=True, label="no funding needed" + ("" if basis == "COMMITTED" else
                                                                        f" ({EXPECTED_LABEL})"), **common)
    best = search.best
    rejected = []
    for alt in alternatives(search):
        if best is not None and action_key(alt.actions) == action_key(best.actions):
            continue
        rejected.append(RejectedCandidate(label=alt.label, reasons=alt.reasons, note=_note(alt, search)))
    if best is None:
        violations = _infeasible_violations(search)
        return FundingPlan(id=plan_id(basis, [], state, mandate), actions=[], costs=[], total_cost_fen=0,
                           admissible=False, violations=violations, rejected=rejected,
                           label="no admissible plan: the menu cannot cover the gap", **common)
    best = search.evaluate(search.ordered(best.actions))
    lines = search.cost_lines(best)
    uses_expected = any(state_fac.status != FacilityStatus.COMMITTED
                        for state_fac in (search.facilities[a.facility_id] for a in best.actions))
    if basis == "COMMITTED":
        label = "committed plan: " + cost_display(lines, best.cost)
    else:
        label = (EXPECTED_LABEL if uses_expected else "expected plan (committed sources only)") + ": " + \
            cost_display(lines, best.cost)
    return FundingPlan(id=plan_id(basis, list(best.actions), state, mandate), actions=list(best.actions),
                       costs=lines, total_cost_fen=best.cost or 0, admissible=True, rejected=rejected,
                       label=label, **common)


def _infeasible_violations(search: Search) -> list[Violation]:
    """What the best effort (the candidate with the smallest shortfall) still breaks."""
    be = search.best_effort
    if be is None or be.traj is None:
        v = reserve_violation(search.baseline, search.floor, " (no usable source on the menu)")
        return [v] if v is not None else []
    note = f" even with {', '.join(search.action_label(a) for a in be.actions)}"
    out = []
    for v in be.violations:
        if v.code == ViolationCode.RESERVE_BREACH:
            v = reserve_violation(be.traj, search.floor, note) or v
        out.append(v)
    return out


def plan(
    state: FinancialState, obligations: list[Obligation], mandate: Mandate, basis: str = "COMMITTED"
) -> FundingPlan:
    """Cheapest admissible mix of facility actions for the gap in the `basis` trajectory."""
    return _build_plan(_run(state, obligations, mandate, basis), state, mandate)


# ---------------------------------------------------------------- comparison table


def _row(alt: Alternative, search: Search, result: ComparisonResult) -> ComparisonRow:
    ev = alt.ev
    cost = ev.cost if ev is not None else None
    lines = search.cost_lines(ev) if ev is not None else []
    return ComparisonRow(
        key=alt.key, label=alt.label, components=alt.components, actions=alt.actions, cost_fen=cost,
        cost_display=cost_display(lines, cost), result=result, reasons=alt.reasons,
        breach_day=ev.breach_day if ev is not None else None, note=_note(alt, search) if result != ComparisonResult.SELECTED else "",
    )


def compare(state: FinancialState, obligations: list[Obligation], mandate: Mandate) -> list[ComparisonRow]:
    """Spec §7.4 rows, in order: full discount, line + partial early pay, the router optimum,
    line + guaranteed loan, line only. An alternative identical to the optimum is marked SELECTED."""
    search = _run(state, obligations, mandate, "COMMITTED")
    best = search.best
    if not search.breach_days:
        return [ComparisonRow(key="router_optimum", label="No funding needed", components=[], cost_fen=0,
                              cost_display=fmt_yuan(0), result=ComparisonResult.SELECTED)]
    alts = alternatives(search)
    rows: list[ComparisonRow] = []
    selected_done = False

    def add_selected() -> None:
        nonlocal selected_done
        if selected_done:
            return
        selected_done = True
        if best is None:
            viol = _infeasible_violations(search)
            rows.append(ComparisonRow(
                key="router_optimum", label="Router optimum", components=[], cost_fen=None, cost_display="—",
                result=ComparisonResult.NOT_ADMISSIBLE, reasons=list(dict.fromkeys(v.code for v in viol)),
                breach_day=next((v.day for v in viol if v.code == ViolationCode.RESERVE_BREACH), None),
                note="no admissible plan: the menu cannot cover the gap"))
            return
        ordered = search.ordered(best.actions)
        alt = Alternative("router_optimum", "Router optimum", [search.action_label(a) for a in ordered],
                          ordered, search.evaluate(ordered), [])
        rows.append(_row(alt, search, ComparisonResult.SELECTED))

    for alt in alts:
        if best is not None and action_key(alt.actions) == action_key(best.actions):
            if not selected_done:
                rows.append(_row(alt, search, ComparisonResult.SELECTED))
                selected_done = True
            continue
        if alt.key in ("line_guaranteed_loan", "line_only"):
            add_selected()
        ok = not alt.reasons and alt.ev is not None
        rows.append(_row(alt, search, ComparisonResult.ADMISSIBLE if ok else ComparisonResult.NOT_ADMISSIBLE))
    add_selected()
    return rows


# ---------------------------------------------------------------- port


class Router:
    """Satisfies `app.domain.ports.FundingRouter`. Stateless."""

    def plan(
        self, state: FinancialState, obligations: list[Obligation], mandate: Mandate, basis: str = "COMMITTED"
    ) -> FundingPlan:
        return plan(state, obligations, mandate, basis)

    def marginal_cost(self, state: FinancialState, mandate: Mandate) -> tuple[Ratio, str]:
        return marginal_cost(state, mandate)

    def compare(self, state: FinancialState, obligations: list[Obligation], mandate: Mandate) -> list[ComparisonRow]:
        return compare(state, obligations, mandate)
