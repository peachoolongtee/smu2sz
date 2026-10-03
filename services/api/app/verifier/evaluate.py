"""The verdict algorithm (docs/ARCHITECTURE.md "Verdict algorithm", binding).

1. Offer status: CONFLICTING_SOURCES or ABSTAINED → NO_VERDICT.
2. Security screen: unknown sender or funding claims, unevidenced claims, data requests.
3. Mandate validity with the pinned owner key: any failure → REJECT, no evaluation.
4. Bind, project the CONSERVATIVE trajectory, the router's committed (and expected) plan, the marginal
   cost of funds, and the forward value of every obligation at that rate.
5. Predicates: min cash (offer-induced breaches; curable on permanent-capable sources), concession
   caps, immediate-discount cap, implied early-pay APR, covenants monthly and pro forma for any
   terms extension funded permanently.
6. Outcome, counters, required tier, summary.

Reads typed contracts only (INVARIANT 2). Conservative mode alone decides (INVARIANT 11): the
expected plan is returned for display and never consulted.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from typing import Any, Literal

from app.alerts.engine import past_due_invoices
from app.books import current_books
from app.covenants import (
    book_basis,
    fmt_x,
    line_balances,
    longest_zero_run,
    ratios_for,
    with_extra,
    worst_dscr,
    worst_leverage,
)
from app.covenants import evaluate as evaluate_covenants
from app.covenants.ratios import fmt_exact
from app.domain.models import (
    Commitment,
    CompiledOffer,
    CompiledTermSheet,
    CompileStatus,
    ConcessionValue,
    Contingency,
    CounterProposal,
    CovenantKind,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    ForwardConcession,
    FundingPlan,
    Mandate,
    Mode,
    Obligation,
    ObligationType,
    Outcome,
    Tier,
    Trajectory,
    Verdict,
    Violation,
    ViolationCode,
)
from app.domain.money import DAYS_PER_YEAR, Ratio, bp, fmt_pct, fmt_yuan, post
from app.financial import EngineError, extension_pro_forma, project, value_concessions
from app.funding import (
    ComparisonResult,
    ComparisonRow,
    NoPermanentSourceError,
    break_even_discount,
    compare,
    marginal_cost,
)
from app.funding import plan as funding_plan
from app.funding.rates import break_even_cost_share
from app.mandate import check_apr, check_predicates, check_validity
from app.verifier.bind import bind, material_gaps
from app.verifier.counters import Recheck, flag_inputs, plan_flags
from app.verifier.counters import counters_explained as make_counters
from app.verifier.display import describe_all, only_early_pay, precise
from app.verifier.models import CALC_VERSION, OwnerConstraints, PassedCheck, VerdictBundle
from app.verifier.owner import breaches as owner_breaches
from app.verifier.owner import describe as describe_constraints
from app.verifier.reserve import baseline, cure_plan, induced_breach_days, reserve_violation
from app.verifier.screen import SECURITY_CODES, screen

PRICE_CODES = frozenset({ViolationCode.MAX_APR_EXCEEDED, ViolationCode.IMMEDIATE_DISCOUNT_EXCEEDED,
                         ViolationCode.DISCOUNT_ABOVE_BREAK_EVEN,
                         ViolationCode.EARLY_PAY_NOT_NEEDED, ViolationCode.EARLY_PAY_DEARER_THAN_PLAN})
CAP_CODES = frozenset({ViolationCode.AGG_CONCESSION_EXCEEDED, ViolationCode.PER_BUYER_CAP_EXCEEDED})
MANDATE_CODES = frozenset({ViolationCode.BAD_SIGNATURE, ViolationCode.MANDATE_EXPIRED,
                           ViolationCode.MANDATE_REVOKED, ViolationCode.MANDATE_VERSION_MISMATCH})
Plans = Literal["all", "committed"]
TIER3_BY_FIELD = {
    "guarantee": ViolationCode.TIER3_PERSONAL_GUARANTEE,
    "collateral": ViolationCode.TIER3_COLLATERAL,
    "equity": ViolationCode.TIER3_EQUITY,
}


# ---------------------------------------------------------------- helpers


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def verdict_id(offer_id: str, offer_version: int, state: FinancialState, mandate: Mandate, day: int,
               constraints: OwnerConstraints | None = None, live: Sequence[Obligation] = ()) -> str:
    """Deterministic. An owner-constrained evaluation gets its own id: its verdict can differ from the
    unconstrained one for the same offer, and both may be stored. So does one run on books that carry live
    obligations (same state, different commitments in force)."""
    parts = [offer_id, str(offer_version), state.model_dump_json(), str(mandate.version), str(day), CALC_VERSION]
    if constraints is not None:
        parts.append(constraints.model_dump_json())
    if live:
        parts.append("|".join(o.model_dump_json() for o in live))
    return "VER-" + _digest(*parts)


# ---------------------------------------------------------------- router memo


class _Router:
    """Memoises identical router calls within one evaluation (same state, obligations and basis): the
    status-quo plan is the baseline's, and a cure on an unchanged state is the committed plan."""

    def __init__(self, mandate: Mandate) -> None:
        self.mandate = mandate
        self.memo: dict[tuple[str, str, str], FundingPlan] = {}
        self.calls = 0  # router searches actually run (for tests and measurement)

    @staticmethod
    def key(state: FinancialState, obligations: Sequence[Obligation], basis: str) -> tuple[str, str, str]:
        return state.model_dump_json(), "|".join(o.model_dump_json() for o in obligations), basis

    def seed(self, state: FinancialState, obligations: Sequence[Obligation], basis: str, plan: FundingPlan) -> None:
        self.memo.setdefault(self.key(state, obligations, basis), plan)

    def plan(self, state: FinancialState, obligations: list[Obligation], mandate: Mandate,
             basis: str = "COMMITTED") -> FundingPlan:
        k = self.key(state, obligations, basis)
        hit = self.memo.get(k)
        if hit is None:
            self.calls += 1
            hit = funding_plan(state, obligations, mandate, basis)
            self.memo[k] = hit
        return hit


# The spec §7.4 comparison depends only on (state with the offered early-pay rate, mandate): cached across
# evaluations like the baseline, so slider moves that keep the discount do not re-run that search.
_COMPARE_CACHE: OrderedDict[tuple[str, str, str], list[ComparisonRow]] = OrderedDict()
_COMPARE_LOCK = threading.Lock()
_COMPARE_SIZE = 32


def _compare_cached(state: FinancialState, mandate: Mandate, live: Sequence[Obligation] = ()) -> list[ComparisonRow]:
    k = (state.model_dump_json(), mandate.model_dump_json(), "|".join(o.model_dump_json() for o in live))
    with _COMPARE_LOCK:
        hit = _COMPARE_CACHE.get(k)
        if hit is not None:
            _COMPARE_CACHE.move_to_end(k)
            return list(hit)
    rows = compare(state, list(live), mandate)
    with _COMPARE_LOCK:
        _COMPARE_CACHE[k] = list(rows)
        while len(_COMPARE_CACHE) > _COMPARE_SIZE:
            _COMPARE_CACHE.popitem(last=False)
    return rows


def clear_caches() -> None:
    """Drop the cross-evaluation caches (baseline, comparison), e.g. before a cold measurement."""
    from app.verifier.reserve import _baseline

    _baseline.cache_clear()
    with _COMPARE_LOCK:
        _COMPARE_CACHE.clear()


def _unique_codes(violations: Sequence[Violation]) -> list[ViolationCode]:
    return list(dict.fromkeys(v.code for v in violations))


def _is_hard(v: Violation) -> bool:
    if v.code in PRICE_CODES:
        return False
    return not (v.code == ViolationCode.RESERVE_BREACH and v.curable)


def _describe(v: Violation) -> str:
    if v.code == ViolationCode.RESERVE_BREACH:
        cure = ""
        if v.curable:
            held = [w for k, w in (("cure_needs_owner_approval", "needs the owner's approval"),
                                   ("cure_executable_now", "cannot run today")) if k in v.inputs]
            cure = f" (curable at {fmt_yuan(v.cure_cost_fen or 0)}" + (f"; the cure {' and '.join(held)}" if held else "") + ")"
        elif v.curable is False:
            cure = " (not curable on committed sources)"
        return f"RESERVE_BREACH@{v.day}{cure}"
    if v.observed and v.limit:
        return f"{v.code.value} ({v.observed} vs {v.limit})"
    return v.code.value


class _Result:
    """Accumulates one evaluation."""

    def __init__(self, offer_id: str, offer_version: int, state: FinancialState, mandate: Mandate, day: int,
                 constraints: OwnerConstraints | None = None, live: Sequence[Obligation] = ()):
        self.offer_id = offer_id
        self.offer_version = offer_version
        self.state = state
        self.mandate = mandate
        self.id = verdict_id(offer_id, offer_version, state, mandate, day, constraints, live)
        self.violations: list[Violation] = []
        self.values: list[ConcessionValue] = []
        self.forward_total = sum(fc.value_fen for fc in state.forward_concessions)
        self.plan: FundingPlan | None = None
        self.notes_text: list[str] = []
        self.bound: list[Obligation] = []  # set once bound obligations reach the predicates

    def verdict(self, outcome: Outcome, tier: Tier, summary: str, counters: list[Any] | None = None) -> Verdict:
        return Verdict(
            id=self.id, offer_id=self.offer_id, offer_version=self.offer_version, outcome=outcome,
            violations=self.violations, bound_obligations=self.bound, concession_values=self.values,
            forward_concession_total_fen=self.forward_total, counters=counters or [], plan=self.plan,
            required_tier=tier, mandate_version=self.mandate.version, state_version=self.state.state_version,
            calc_version=CALC_VERSION, summary=summary,
        )


def _summary(outcome: Outcome, violations: Sequence[Violation], extra: Sequence[str] = ()) -> str:
    head = outcome.value.replace("_", " ")
    parts = [f"{head}: " + "; ".join(describe_all(violations, _describe)) if violations else head]
    parts += [e for e in extra if e]
    return ". ".join(parts) + "."


# ---------------------------------------------------------------- predicates


def _forward_total(bound: list[Obligation], values: list[ConcessionValue], state: FinancialState) -> int:
    """Existing + this offer's net new forward concessions (only FIRM gains net; INVARIANT 5). A package
    whose FIRM gains exceed its concessions adds nothing: it never creates headroom for other buyers."""
    by_id = {o.id: o for o in bound}
    net = 0
    for cv in values:
        ob = by_id.get(cv.obligation_id)
        if cv.value_fen >= 0 or (ob is not None and ob.contingency == Contingency.FIRM):
            net += cv.value_fen
    return sum(fc.value_fen for fc in state.forward_concessions) + max(0, net)


def _apr_checks(bound: list[Obligation], state: FinancialState, mandate: Mandate,
                comparison: list[ComparisonRow]) -> tuple[list[Violation], list[PassedCheck]]:
    out: list[Violation] = []
    passed: list[PassedCheck] = []
    for ob in bound:
        if ob.type != ObligationType.IMMEDIATE_DISCOUNT or ob.rate_bp is None or ob.base.receivable_id is None:
            continue
        r = next((r for r in state.receivables if r.id == ob.base.receivable_id), None)
        if r is None or ob.effective_day is None:
            continue
        days = r.due_day - ob.effective_day
        if days <= 0:
            continue
        d = bp(ob.rate_bp)
        rate = d / (1 - d) * DAYS_PER_YEAR / days
        formula = f"d/(1−d) × 365/days_early = {fmt_pct(d)}/(1 − {fmt_pct(d)}) × 365/{days} = {fmt_pct(rate, 4)}"
        inputs = {"discount": fmt_pct(d), "days_early": str(days), "receivable_id": r.id,
                  "implied_annual_rate": fmt_pct(rate, 4)}
        rows = {row.key: row for row in comparison}
        if "line_partial_early_pay" in rows:
            inputs["line_plus_partial_at_offered_rate"] = rows["line_partial_early_pay"].cost_display
        sel = next((row for row in comparison if row.result == ComparisonResult.SELECTED), None)
        if sel is not None:
            inputs["router_optimum"] = sel.cost_display
            inputs.update(flag_inputs(sel, "router_optimum"))
        # ADR-0007 test 1 (spec v2 §5.3 / §8 example 2): early payment is worth taking only below the SME's own
        # marginal cost of carrying the money for this tenor (0.88% for 30 days on the golden fixture).
        try:
            be, be_bp = break_even_discount(state, mandate, days)
            _, k_periods, period = break_even_cost_share(state, mandate, days)
        except NoPermanentSourceError:
            be = None
        if be is not None and d >= be.value:
            tenor = f"{days} days ({k_periods} × {period}-day periods)" if k_periods is not None else f"{days} days"
            out.append(Violation(
                code=ViolationCode.DISCOUNT_ABOVE_BREAK_EVEN,
                message=f"Early settlement at {fmt_pct(d)} costs more than financing the invoice: "
                        f"break-even {fmt_pct(be.value)}",
                observed=fmt_pct(d), limit=f"< {fmt_pct(be.value)}",
                formula=f"d < c/(1+c), c = marginal source's cost share for {tenor}",
                inputs={**inputs, "break_even": fmt_pct(be.value, 4), "break_even_bp_floor": str(be_bp),
                        "break_even_days": str(days)},
                spans=ob.spans))
        v = check_apr(Ratio.of(rate), mandate, f"Early settlement of {r.id} at {fmt_pct(d)}")
        if v is not None:
            out.append(v.model_copy(update={"formula": f"{formula} > {fmt_pct(bp(mandate.max_apr_bp))}",
                                            "inputs": {**v.inputs, **inputs}, "spans": ob.spans}))
        else:
            passed.append(PassedCheck(code="MAX_APR", label=f"Implied cost of early settlement of {r.id}",
                                      observed=fmt_pct(rate), limit=fmt_pct(bp(mandate.max_apr_bp)),
                                      formula=formula, inputs=inputs))
    return out, passed


def _early_pay_legs(bound: Sequence[Obligation], state: FinancialState) -> list[Obligation]:
    """The offer's early-payment legs: an immediate discount on a named open invoice, settled before it is due."""
    due = {r.id: r.due_day for r in state.receivables}
    return [o for o in bound if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.rate_bp is not None
            and o.base.receivable_id in due and o.effective_day is not None
            and due[o.base.receivable_id] - o.effective_day > 0]


def _early_pay_vs_plan(bound: list[Obligation], live: Sequence[Obligation], state: FinancialState,
                       mandate: Mandate, router: _Router, base_plan: FundingPlan, plan_committed: FundingPlan,
                       horizon: int, floor: int) -> tuple[list[Violation], list[PassedCheck]]:
    """ADR-0007 tests 2 and 3, once per offer. C = interest + fees + discounts the engine posts over the
    horizon for the books under test with the router's committed plan for those same books. The early-pay legs
    are priced at the margin: C0 = books + the offer's other obligations, C1 = books + everything."""
    legs = _early_pay_legs(bound, state)
    if not legs or not plan_committed.admissible:
        return [], []
    leg_ids = {o.id for o in legs}
    others = [o for o in bound if o.id not in leg_ids]
    plan0 = base_plan if not others else router.plan(state, [*live, *others], mandate, "COMMITTED")
    spans = [sp for o in legs for sp in o.spans]
    label = ", ".join(f"{o.base.receivable_id} at {fmt_pct(bp(o.rate_bp or 0))}" for o in legs)

    def cost(obs: list[Obligation], plan: FundingPlan) -> int:
        t = project(state, obs, plan.actions, Mode.CONSERVATIVE, horizon, floor)
        return t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen

    c1 = cost([*live, *bound], plan_committed)
    flagged = [x for x in (plan_flags(plan_committed, "the plan with the offer"),
                           plan_flags(plan0, "the plan without it")) if x]
    flag_note = "; ".join(flagged)
    flag_in = {**flag_inputs(plan_committed, "plan_with_offer"), **flag_inputs(plan0, "plan_without_offer")}
    if not plan0.admissible:
        return [], [PassedCheck(
            code="EARLY_PAY_VS_PLAN", label="Early payment against the router's plan", observed=fmt_yuan(c1),
            limit="no admissible plan without the offer",
            formula="the books cannot keep the floor on committed sources without the early payment, and can with it"
                    + (f"; {flag_note}" if flag_note else ""),
            inputs={"plan_with_offer": plan_committed.label, "plan_without_offer": plan0.label,
                    "cost_with_offer": fmt_yuan(c1), "legs": label, **flag_in})]
    c0 = cost([*live, *others], plan0)
    inputs = {"plan_with_offer": plan_committed.label, "plan_without_offer": plan0.label,
              "cost_with_offer": fmt_yuan(c1), "cost_without_offer": fmt_yuan(c0), "legs": label, **flag_in}
    formula_base = (f"C1 = interest + fees + discounts with the offer = {fmt_yuan(c1)}; "
                    f"C0 = the same without the early payment = {fmt_yuan(c0)}"
                    + (f"; {flag_note}" if flag_note else ""))
    if c1 < c0:
        return [], [PassedCheck(
            code="EARLY_PAY_VS_PLAN", label="Early payment against the router's plan", observed=fmt_yuan(c1),
            limit=f"< {fmt_yuan(c0)}", formula=f"{formula_base}; C1 < C0", inputs=inputs)]
    if not plan0.actions and c1 > c0:
        code = ViolationCode.EARLY_PAY_NOT_NEEDED
        message = (f"No funding is needed without the early payment; taking it costs {fmt_yuan(c1)} "
                   f"for cash the books do not need" + (f" ({flag_note})" if flag_note else ""))
        formula = f"{formula_base}; no funding needed without the offer and C1 > C0"
    else:
        code = ViolationCode.EARLY_PAY_DEARER_THAN_PLAN
        message = (f"The early payment costs {fmt_yuan(c1)}, not less than the plan without it ({fmt_yuan(c0)})"
                   + (f" ({flag_note})" if flag_note else ""))
        formula = f"{formula_base}; C1 < C0 required"
    return [Violation(code=code, message=message, observed=fmt_yuan(c1), limit=f"< {fmt_yuan(c0)}",
                      formula=formula, inputs=inputs, spans=spans)], []


def _committed(state: FinancialState) -> list[Facility]:
    return [f for f in state.facilities if f.status == FacilityStatus.COMMITTED and f.owner_approved]


_EXTENSION_ESTIMATE = ("estimate: the steady-state receivables the extension ties up (face × Δdays / invoice "
                       "interval), funded permanently at the marginal rate; no plan funds that steady state yet")


def _leverage_reading(funded: Trajectory) -> dict[str, str]:
    """The leverage the verdict reports: the highest month-end leverage of the projection that carries the offer's
    obligations and the committed plan that funds them (`ratios_for` on its month points, the one definition)."""
    worst = worst_leverage(funded.months)
    if worst is None:
        debt = max((m.total_debt_fen for m in funded.months), default=0)
        return {"pro_forma_leverage": "undefined (EBITDA is not positive)" if debt > 0 else "n/a (no debt)"}
    _, lev = ratios_for(worst)
    assert lev is not None
    return {"pro_forma_leverage": fmt_x(lev.value), "pro_forma_leverage_month": str(worst.month),
            "pro_forma_leverage_debt": fmt_yuan(worst.total_debt_fen),
            "pro_forma_leverage_basis": "projection with the offer and its committed plan: highest month-end "
                                        "debt / (12 × EBITDA_m)"}


def _extension_pro_forma(
    bound: list[Obligation], rate: Fraction, state: FinancialState, mandate: Mandate, funded: Trajectory,
) -> tuple[list[Violation], list[PassedCheck], dict[str, str]]:
    """DSCR if every lengthening terms extension is funded permanently at `rate`: an estimate, since no plan funds
    the steady state (extra monthly debt service = extra debt × rate / 12, extra debt = face × delta / invoice
    interval, `app.financial.extension_pro_forma`), computed by `covenants.pro_forma` on the books' debt service.
    Leverage is not estimated: the inputs carry the funded projection's reading (`_leverage_reading`), which
    `_covenant_checks` tests. Non-positive EBITDA leaves DSCR defined only by its sign; it is never an exception."""
    extra_debt_exact = Fraction(0)
    extra_ds_exact = Fraction(0)
    for ob in bound:
        pf = extension_pro_forma(ob, state, rate, mandate.forward_concession_horizon_days)
        if pf is not None:
            extra_debt_exact += pf.extra_debt
            extra_ds_exact += pf.monthly_service
    if extra_debt_exact == 0:
        return [], [], {}
    extra_debt = post(extra_debt_exact)
    extra_ds = post(extra_ds_exact)
    basis = with_extra(book_basis(state), extra_debt, extra_ds)
    dscr, _ = ratios_for(basis)
    inputs = {
        "EBITDA_m": fmt_yuan(basis.ebitda_fen), "DS_m": fmt_yuan(basis.debt_service_fen),
        "extra_receivables": fmt_yuan(extra_debt), "extra_monthly_debt_service": fmt_yuan(extra_ds),
        "extra_receivables_basis": _EXTENSION_ESTIMATE,
        "pro_forma_dscr": fmt_x(dscr.value) if dscr else "n/a",
        **_leverage_reading(funded),
    }
    dscr_limits = [(bp(mandate.min_dscr_bp), f"mandate v{mandate.version}")]
    for f in _committed(state):
        for c in f.covenants:
            if c.kind == CovenantKind.DSCR_MIN and c.threshold_bp is not None:
                dscr_limits.append((bp(c.threshold_bp), c.id))
    dscr_limit, dscr_src = max(dscr_limits)
    dscr_formula = (f"EBITDA_m / (DS_m + extra debt × rate / 12) = {fmt_yuan(basis.ebitda_fen)} / "
                    f"{fmt_yuan(basis.debt_service_fen)} (estimate)")
    violations: list[Violation] = []
    passed: list[PassedCheck] = []
    if dscr is not None:
        text = fmt_x(dscr.value)
        if dscr.value < dscr_limit:
            violations.append(Violation(
                code=ViolationCode.DSCR_BREACH, message=f"Pro-forma DSCR {text} with the extension funded (an "
                f"estimate) is below {fmt_x(dscr_limit)}", observed=text, limit=fmt_x(dscr_limit),
                formula=f"{dscr_formula} = {text} < {fmt_x(dscr_limit)}", inputs={**inputs, "source": dscr_src}))
        else:
            passed.append(PassedCheck(code="DSCR_MIN", label="DSCR with the extension funded (pro-forma estimate)",
                                      observed=text, limit=f"≥ {fmt_x(dscr_limit)}",
                                      formula=f"{dscr_formula} = {text}", inputs={**inputs, "source": dscr_src}))
    return violations, passed, inputs


def _covenant_checks(traj: Trajectory, state: FinancialState, mandate: Mandate,
                     skip_dscr: bool) -> tuple[list[Violation], list[PassedCheck]]:
    """Every month of `traj` (the offer with its committed plan) against the covenants. `skip_dscr`: the DSCR pass
    is reported by the extension's pro-forma estimate instead; leverage is always read here, from the projection."""
    facilities = _committed(state)
    violations = [precise(v) for v in evaluate_covenants(traj, facilities, mandate)]
    if not mandate.require_clean_down:
        violations = [v for v in violations if v.code != ViolationCode.CLEAN_DOWN_BREACH]
    codes = {v.code for v in violations}
    passed: list[PassedCheck] = []
    months = list(traj.months)
    if not skip_dscr and ViolationCode.DSCR_BREACH not in codes and (worst := worst_dscr(months)) is not None:
        dscr, _ = ratios_for(worst)
        assert dscr is not None
        passed.append(PassedCheck(
            code="DSCR_MIN", label=f"Lowest monthly DSCR (month {worst.month})", observed=fmt_x(dscr.value),
            limit=f"≥ {fmt_x(bp(mandate.min_dscr_bp))}",
            formula=f"EBITDA_m / DS_m = {fmt_yuan(worst.ebitda_fen)} / {fmt_yuan(worst.debt_service_fen)}"))
    if ViolationCode.LEVERAGE_BREACH not in codes and (worst := worst_leverage(months)) is not None:
        _, lev = ratios_for(worst)
        assert lev is not None
        passed.append(PassedCheck(
            code="LEVERAGE_MAX", label=f"Highest monthly leverage (month {worst.month})",
            observed=fmt_x(lev.value), limit=f"≤ {fmt_x(bp(mandate.max_leverage_bp))}",
            formula=f"Debt_m / (12 × EBITDA_m) = {fmt_yuan(worst.total_debt_fen)} / "
                    f"(12 × {fmt_yuan(worst.ebitda_fen)})",
            inputs={"month": str(worst.month), "Debt_m": fmt_yuan(worst.total_debt_fen),
                    "EBITDA_m": fmt_yuan(worst.ebitda_fen), "leverage_exact": fmt_exact(lev.value),
                    "definition": "DebtPosition principal + drawn balances counted in leverage, at month end"}))
    for f in facilities:
        for c in f.covenants:
            if c.kind != CovenantKind.CLEAN_DOWN or c.clean_down_days is None:
                continue
            if any(v.code == ViolationCode.CLEAN_DOWN_BREACH and v.inputs.get("facility_id", f.id) == f.id
                   for v in violations):
                continue
            run = longest_zero_run(line_balances(traj, f))
            passed.append(PassedCheck(
                code="CLEAN_DOWN", label=f"{f.name}: clean-down", observed=f"{run.length} days at zero",
                limit=f"≥ {c.clean_down_days} consecutive days", formula=c.formula,
                inputs={"facility_id": f.id, "run_start_day": str(run.start_day), "run_end_day": str(run.end_day),
                        "horizon_days": str(traj.horizon_days)}))
    return violations, passed


def _comparison(offer_bound: list[Obligation], state: FinancialState, mandate: Mandate,
                base_plan: FundingPlan, live: Sequence[Obligation] = ()) -> list[ComparisonRow]:
    """Spec §7.4 rows with the buyer's offered discount as the early-pay rate (a what-if copy)."""
    if not base_plan.need_fen:
        return []
    discounts = [o for o in offer_bound if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.rate_bp is not None]
    if not discounts:
        return []
    ob = discounts[0]
    facilities = [f.model_copy(update={"rate_bp": ob.rate_bp})
                  if f.kind == FacilityKind.BUYER_EARLY_PAY and f.lender_id == ob.counterparty_id else f
                  for f in state.facilities]
    return _compare_cached(state.model_copy(update={"facilities": facilities}), mandate, live)


# ---------------------------------------------------------------- entry points


def _evaluate(
    offer: CompiledOffer,
    state: FinancialState,
    mandate: Mandate,
    *,
    trusted_owner_key_hex: str,
    day: int = 0,
    owner_declared: Mapping[str, Any] | None = None,
    commitments: Sequence[Commitment] = (),
    owner_constraints: OwnerConstraints | None = None,
    plans: Plans = "all",
    router: _Router | None = None,
    with_counters: bool = True,
) -> VerdictBundle:
    # Current books (ADR-0006): every projection runs on `live + <what is tested>`. `live` is never part of
    # the verdict's bound obligations, the concession values, the forward total or a counter's obligations.
    live = list(current_books(state, commitments).obligations)
    res = _Result(offer.offer_id, offer.version, state, mandate, day, owner_constraints, live)
    router = router or _Router(mandate)

    # 2 (computed first so its events are logged whatever the outcome)
    sec_violations, events = screen(offer, state, day=day, commitments=commitments)

    # 1. offer status
    if offer.status in (CompileStatus.CONFLICTING_SOURCES, CompileStatus.ABSTAINED):
        conflict = offer.status == CompileStatus.CONFLICTING_SOURCES
        gaps = [a for a in offer.abstentions if a.field != "unresolved_reference" and not a.field.startswith("note:")]
        fields = [a.field for a in gaps]
        spans = [sp for a in gaps for sp in a.spans]
        code = ViolationCode.CONFLICTING_SOURCES if conflict else ViolationCode.UNRESOLVED_SCOPE
        what = "the documents disagree on a material value" if conflict else "a material field has no evidence"
        res.violations = [Violation(
            code=code, message=f"No verdict: {what}; clarification requested from {offer.counterparty_id}",
            observed=", ".join(fields) or "material field", limit="one grounded value per material field",
            formula="every material field has exactly one grounded value",
            inputs={"fields": ", ".join(fields), "clarification": "requested", "booked": "0"}, spans=spans,
        ), *sec_violations]
        summary = _summary(Outcome.NO_VERDICT, res.violations,
                           [f"Clarification requested from {offer.counterparty_id}; nothing booked"])
        return VerdictBundle(verdict=res.verdict(Outcome.NO_VERDICT, Tier.TIER_1, summary), security_events=events)

    # 2. unknown counterparty or funding claims: refused without evaluation
    if any(v.code == ViolationCode.UNKNOWN_COUNTERPARTY for v in sec_violations):
        res.violations = sec_violations
        summary = _summary(Outcome.REJECT, res.violations,
                           ["Nothing booked, no facility added, nothing disclosed"])
        return VerdictBundle(verdict=res.verdict(Outcome.REJECT, Tier.TIER_1, summary), security_events=events)

    # 3. mandate validity
    validity = check_validity(mandate, day, None, trusted_owner_key_hex)
    if validity:
        res.violations = [*validity, *sec_violations]
        summary = _summary(Outcome.REJECT, res.violations, ["The mandate cannot be relied on; nothing evaluated"])
        return VerdictBundle(verdict=res.verdict(Outcome.REJECT, Tier.TIER_1, summary), security_events=events)

    # 4. bind and project
    bound, notes = bind(offer, state, owner_declared)
    gaps = material_gaps(notes)
    if gaps:
        res.violations = [Violation(
            code=ViolationCode.UNRESOLVED_SCOPE,
            message="A material term cannot be established from evidence or the ledger; nothing booked",
            observed=", ".join(f"{g.obligation_id or 'offer'}:{g.field}" for g in gaps),
            limit="every material field resolved", formula="bind(obligation, state, owner_declared) is complete",
            inputs={f"{g.obligation_id or 'offer'}:{g.field}": g.message for g in gaps},
            spans=[sp for ob in offer.obligations if ob.id in {g.obligation_id for g in gaps} for sp in ob.spans],
        ), *sec_violations]
        outcome = Outcome.REJECT if sec_violations else Outcome.NO_VERDICT
        summary = _summary(outcome, res.violations, ["Owner or buyer clarification needed; nothing booked"])
        return VerdictBundle(verdict=res.verdict(outcome, Tier.TIER_1, summary), security_events=events,
                             bound_obligations=bound, notes=notes)

    # An inbound message with nothing bookable (only instructions or questions) has nothing to accept.
    # Internal status-quo evaluations (the owner's own "no new terms" baseline) still get a verdict and plan.
    if not bound and not sec_violations and offer.counterparty_id != "OWNER" and not offer.compiler.startswith(("nl-", "whatif")):
        res.violations = [Violation(
            code=ViolationCode.UNRESOLVED_SCOPE, message="The message contains no bookable commercial term; nothing to accept",
            observed="0 bookable obligations", limit="at least one grounded obligation",
            formula="len(bind(offer)) > 0", inputs={"booked": "0"},
        )]
        outcome = Outcome.NO_VERDICT
        summary = _summary(outcome, res.violations, ["Nothing booked"])
        return VerdictBundle(verdict=res.verdict(outcome, Tier.TIER_1, summary), security_events=events, notes=notes)

    res.bound = list(bound)  # what the predicates below verify: a commitment on this verdict books exactly these
    floor = mandate.min_cash_fen
    horizon = mandate.horizon_days
    offer_traj = project(state, [*live, *bound], [], Mode.CONSERVATIVE, horizon, floor)
    base_traj, base_plan = baseline(state, mandate, live)
    router.seed(state, live, "COMMITTED", base_plan)
    plan_committed = router.plan(state, [*live, *bound], mandate, "COMMITTED")
    # The expected plan is display-only (INVARIANT 11): callers that need only the committed plan skip it.
    plan_expected = router.plan(state, [*live, *bound], mandate, "EXPECTED") if plans == "all" else None
    res.plan = plan_committed

    extra_notes: list[str] = []
    try:
        m_ratio, m_id = marginal_cost(state, mandate)
        m_fac = next(f for f in state.facilities if f.id == m_id)
        rate, label = m_ratio, f"committed marginal source: {m_fac.name} {fmt_pct(m_ratio.value, 4)}"
    except NoPermanentSourceError:
        rate = Ratio.of(bp(mandate.max_apr_bp))
        label = "no committed source can carry a permanent need: valued at the mandate's maximum APR"
        extra_notes.append("No committed source can carry a permanent need; concessions valued at the maximum APR")
    values = value_concessions(bound, state, rate, label, mandate.forward_concession_horizon_days)
    res.values = values
    res.forward_total = _forward_total(bound, values, state)

    # 5. predicates
    violations: list[Violation] = []
    passed: list[PassedCheck] = []
    for v in check_predicates(offer_traj, bound, values, state, mandate, offer.counterparty_id):
        if v.code == ViolationCode.RESERVE_BREACH:
            continue  # replaced by the offer-induced check below
        if v.code in CAP_CODES:
            spans = [sp for ob in bound for cv in values if cv.obligation_id == ob.id and cv.value_fen > 0
                     for sp in ob.spans]
            v = v.model_copy(update={"spans": spans})
        violations.append(v)

    funded = offer_traj
    if plan_committed.admissible and plan_committed.actions:
        funded = project(state, [*live, *bound], plan_committed.actions, Mode.CONSERVATIVE, horizon, floor)

    cure: FundingPlan | None = None
    induced = induced_breach_days(offer_traj, base_traj, floor)
    ext_violations, ext_passed, pf_inputs = _extension_pro_forma(bound, rate.value, state, mandate, funded)
    if induced:
        rv = reserve_violation(offer_traj, base_traj, floor, induced[0])
        cure = cure_plan(state, bound, mandate, offer_traj, base_traj, base_plan, planner=router.plan, live=live)
        per_invoice = [cv.per_invoice_fen for cv in values for ob in bound
                       if cv.obligation_id == ob.id and ob.type == ObligationType.TERMS_EXTENSION
                       and (ob.days_delta or 0) > 0 and cv.per_invoice_fen]
        inputs = dict(rv.inputs)
        if per_invoice:
            inputs["structural_cost_per_invoice"] = fmt_yuan(sum(p for p in per_invoice if p))
        inputs.update({f"covenant_{k}": val for k, val in pf_inputs.items() if k.startswith("pro_forma")})
        if cure.admissible:
            names = sorted({f.name for f in state.facilities for a in cure.actions if a.facility_id == f.id})
            src = ", ".join(names) or "no new funding"
            note = f"cured on {src} (sources able to carry a permanent need): {cure.label}"
            if per_invoice:
                note += f"; the extension itself costs {fmt_yuan(sum(p for p in per_invoice if p))} per invoice"
            inputs["cure_plan"] = cure.label
            if cure_flags := plan_flags(cure, "the cure"):  # the plan the verdict relies on is not one the agent runs alone
                note += f"; {cure_flags}"
                inputs.update(flag_inputs(cure, "cure"))
            rv = rv.model_copy(update={"curable": True, "cure_cost_fen": cure.total_cost_fen, "cure_note": note,
                                       "inputs": inputs})
            res.plan = cure  # the plan the verdict relies on for the breach it reports
        else:
            rv = rv.model_copy(update={
                "curable": False, "inputs": inputs,
                "cure_note": "no admissible plan on sources able to carry a permanent need"})
        violations.append(rv)
    else:
        low = min(funded.days, key=lambda p: (p.closing_fen, p.day))
        with_plan = funded is not offer_traj
        min_formula = "closing_cash(day) >= min_cash on every day; the offer induces no breach"
        min_inputs = {"plan": plan_committed.label if with_plan else "no funding needed",
                      "offer_lowest_without_funding": fmt_yuan(offer_traj.min_cash_fen),
                      "offer_lowest_day": str(offer_traj.min_cash_day)}
        if with_plan and (plan_note := plan_flags(plan_committed, "the committed plan")):
            min_formula += f"; {plan_note}"
            min_inputs.update(flag_inputs(plan_committed, "plan"))
        passed.append(PassedCheck(
            code="MIN_CASH", label="Minimum cash" + (" with the committed plan" if with_plan else ""),
            observed=f"{fmt_yuan(low.closing_fen)} on day {low.day}", limit=f"≥ {fmt_yuan(floor)}",
            formula=min_formula, inputs=min_inputs))

    comparison = _comparison(bound, state, mandate, base_plan, live)  # its rows feed the MAX_APR check's inputs
    apr_v, apr_passed = _apr_checks(bound, state, mandate, comparison)
    violations += apr_v
    passed += apr_passed
    ep_v, ep_passed = _early_pay_vs_plan(bound, live, state, mandate, router, base_plan, plan_committed,
                                         horizon, floor)
    violations += ep_v
    passed += ep_passed

    cov_v, cov_passed = _covenant_checks(funded, state, mandate, skip_dscr=bool(ext_passed or ext_violations))
    violations += cov_v + ext_violations
    passed += ext_passed + cov_passed
    violations += sec_violations
    res.violations = violations

    # 6. outcome
    codes = set(_unique_codes(violations))
    hard = [v for v in violations if _is_hard(v)]
    draft = res.verdict(Outcome.REJECT, Tier.TIER_1, "")
    # The owner's goal (if any) only tightens: a package that breaks it cannot be accepted as offered.
    goal_breaches = owner_breaches(bound, values, state, owner_constraints) if owner_constraints else []
    counter_list: list[CounterProposal] = []
    if with_counters and (hard or (codes & PRICE_CODES) or goal_breaches):
        # The counter property: each counter, re-checked as an offer on these same books (as the commit hook will),
        # must pass; one that fails is not offered and a note says why no counter of that kind is possible.
        recheck = counter_recheck(state, mandate, trusted_owner_key_hex=trusted_owner_key_hex, day=day,
                                  commitments=commitments)
        counter_list, no_counter = make_counters(offer, draft, state, mandate, bound=bound,
                                                 owner_declared=owner_declared, owner_constraints=owner_constraints,
                                                 live=live, check=recheck)
        extra_notes += no_counter
    if owner_constraints is not None:
        extra_notes.append(f"owner goal ({describe_constraints(owner_constraints)}): "
                           + ("; ".join(goal_breaches) if goal_breaches else "the package satisfies it"))
    past_due = _buyer_past_due(offer.counterparty_id, state, commitments, mandate, day)
    past_due_note = _past_due_note(offer.counterparty_id, past_due)
    if hard or codes & SECURITY_CODES:
        outcome, tier = Outcome.REJECT, Tier.TIER_1
    elif codes & PRICE_CODES or goal_breaches:
        outcome, tier = (Outcome.COUNTER if counter_list else Outcome.REJECT), Tier.TIER_1
    else:
        existing = sum(fc.value_fen for fc in state.forward_concessions)
        lengthening = any(o.type == ObligationType.TERMS_EXTENSION and (o.days_delta or 0) > 0 for o in bound)
        new_value = res.forward_total - existing
        # Autonomous (Tier 1) acceptance covers only an early-payment discount on a named invoice; any other
        # bound promise (rebate, terms, price, volume, operational) waits for the owner (the executor's rule).
        beyond = bool(bound) and not only_early_pay(bound)
        if lengthening or new_value > mandate.tier2_single_commitment_fen or beyond:
            outcome, tier = Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2
            if lengthening:
                why = "the package lengthens payment terms"
            elif new_value > mandate.tier2_single_commitment_fen:
                why = f"forward value {fmt_yuan(new_value)} is above the Tier-2 threshold"
            else:
                kinds = ", ".join(dict.fromkeys(o.type.value for o in bound
                                                if o.type != ObligationType.IMMEDIATE_DISCOUNT or not o.base.receivable_id))
                why = (f"only an early-payment discount on a named invoice is accepted without the owner; "
                       f"this package also binds {kinds}")
            extra_notes.append("owner approval needed: " + why)
        else:
            unproven = _autonomy_gaps(offer, bound, state)
            if unproven:
                outcome, tier = Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2
                extra_notes.append("owner approval needed: autonomy not proven (" + "; ".join(unproven) + ")")
            elif past_due:
                outcome, tier = Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2
                extra_notes.append("owner approval needed: " + past_due_note)
            else:
                outcome, tier = Outcome.ACCEPT, Tier.TIER_1

    if past_due and outcome != Outcome.NEEDS_OWNER_APPROVAL:  # the deciding note above already names it otherwise
        extra_notes.append(past_due_note)
    extra = [f"Forward concessions {fmt_yuan(res.forward_total)} against "
             + fmt_yuan(mandate.max_aggregate_forward_concession_fen)]
    held = [f"{p.code} {p.observed}" for p in passed if p.code in ("DSCR_MIN", "LEVERAGE_MAX")]
    if held:
        extra.append("Covenants hold: " + ", ".join(held))
    if any(n.field == "unresolved_reference" for n in notes):
        extra.append("Unresolved reference flagged; nothing booked for it")
    extra += extra_notes
    if counter_list:
        extra.append("Counters: " + ", ".join(c.label for c in counter_list))
    verdict = res.verdict(outcome, tier, _summary(outcome, violations, extra), counter_list)
    return VerdictBundle(
        verdict=verdict, trajectory=offer_traj, plan_committed=plan_committed, plan_expected=plan_expected,
        security_events=events, passed_checks=passed, bound_obligations=bound, notes=notes, cure_plan=cure,
        comparison=comparison,
    )


def _buyer_past_due(buyer_id: str, state: FinancialState, commitments: Sequence[Commitment], mandate: Mandate,
                    day: int) -> list[tuple[str, int, int]]:
    """(invoice id, days past due, outstanding fen) of this buyer's open invoices past due on current books today
    (the alerts' own reading of the books). Nothing is past due on day 0, so no day-0 verdict can change."""
    today = max(day, state.as_of_day)
    books = current_books(state, commitments)
    found = past_due_invoices(books, today, today + mandate.horizon_days)
    return sorted((a.receivable_id or "", today - int(a.inputs["due_day"]), a.amount_fen or 0)
                  for a in found if a.inputs.get("counterparty_id") == buyer_id)


def _past_due_note(buyer_id: str, past_due: list[tuple[str, int, int]]) -> str:
    return "; ".join(f"{buyer_id} has a past-due invoice {rid}: {fmt_yuan(owed)} outstanding, {late} day(s) past due"
                     for rid, late, owed in past_due)


def _autonomy_gaps(offer: CompiledOffer, bound: list[Obligation], state: FinancialState) -> list[str]:
    """Why this offer may not be accepted without the owner (ADR-0005). Empty means proven.

    Owner-built typed offers (/nl plans, what-if) carry no free text and are exempt. A counterparty's
    message must carry the compiler's positive coverage proof, and every early-pay discount must name
    a whole open invoice by its stated face: never bound by default to "the only open receivable"."""
    if offer.compiler.startswith(("nl-", "whatif")):
        return []
    gaps: list[str] = []
    if not offer.autonomy_eligible:
        gaps.append("the compiler could not account for every figure and request in the message"
                    + (f": {'; '.join(offer.autonomy_notes)}" if offer.autonomy_notes else ""))
    faces = {r.id: r.face_fen for r in state.receivables}
    stated = {o.id: o.base.amount_fen for o in offer.obligations}
    for ob in bound:
        if ob.type != ObligationType.IMMEDIATE_DISCOUNT:
            continue
        face = faces.get(ob.base.receivable_id or "")
        if stated.get(ob.id) is None:
            gaps.append(f"{ob.id}: the message does not state the invoice amount")
        elif face is None or stated[ob.id] != face or ob.base.amount_fen != face:
            gaps.append(f"{ob.id}: the stated amount is not the whole face of an open invoice")
    return gaps


def autonomy_gaps(offer: CompiledOffer, bound: list[Obligation], state: FinancialState) -> list[str]:
    """Public read of `_autonomy_gaps` (display only): why the offer may not be accepted without the owner."""
    return _autonomy_gaps(offer, bound, state)


def evaluate_verdict(
    offer: CompiledOffer,
    state: FinancialState,
    mandate: Mandate,
    *,
    trusted_owner_key_hex: str,
    day: int = 0,
    owner_declared: Mapping[str, Any] | None = None,
    commitments: Sequence[Commitment] = (),
    owner_constraints: OwnerConstraints | None = None,
) -> Verdict:
    return evaluate(offer, state, mandate, trusted_owner_key_hex=trusted_owner_key_hex, day=day,
                    owner_declared=owner_declared, commitments=commitments, owner_constraints=owner_constraints,
                    plans="committed").verdict


def evaluate_many(
    offers: Sequence[CompiledOffer],
    state: FinancialState,
    mandate: Mandate,
    *,
    trusted_owner_key_hex: str,
    day: int = 0,
    owner_declared: Mapping[str, Any] | None = None,
    commitments: Sequence[Commitment] = (),
) -> list[VerdictBundle]:
    """Concurrent offers (spec §8 example 8). Each accepted package is reserved against the
    aggregate and per-buyer caps in order; a later offer that fits alone but no longer fits jointly
    gets COUNTER with AGG_CONCESSION_EXCEEDED (or PER_BUYER_CAP_EXCEEDED) and a counter that fits."""
    out: list[VerdictBundle] = []
    reserved = state
    kw = {"trusted_owner_key_hex": trusted_owner_key_hex, "day": day, "owner_declared": owner_declared,
          "commitments": commitments}
    for offer in offers:
        b = evaluate(offer, reserved, mandate, **kw)
        v = b.verdict
        joint = reserved is not state and any(x.code in CAP_CODES for x in v.violations)
        if joint and not [x for x in v.violations if _is_hard(x) and x.code not in CAP_CODES]:
            alone = evaluate(offer, state, mandate, **kw).verdict
            if alone.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
                summary = v.summary.replace("REJECT", "COUNTER", 1) + (
                    " Fits alone; over the cap jointly with the packages already reserved.")
                v = v.model_copy(update={"outcome": Outcome.COUNTER if v.counters else Outcome.REJECT,
                                         "summary": summary})
                b = b.model_copy(update={"verdict": v})
        if v.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
            existing = sum(fc.value_fen for fc in reserved.forward_concessions)
            new_value = v.forward_concession_total_fen - existing
            if new_value > 0:
                fc = ForwardConcession(id=f"RSV-{offer.offer_id}", counterparty_id=offer.counterparty_id,
                                       value_fen=new_value, commitment_id=None,
                                       label=f"reserved for concurrent offer {offer.offer_id}")
                reserved = reserved.model_copy(update={"forward_concessions": [*reserved.forward_concessions, fc]})
        out.append(b)
    return out


def evaluate_term_sheet(
    ts: CompiledTermSheet,
    state: FinancialState,
    mandate: Mandate,
    *,
    trusted_owner_key_hex: str | None = None,
    day: int = 0,
) -> Verdict:
    """A lender term sheet: Tier-3 clauses → REJECT; otherwise the owner decides (Tier 2). The
    all-in rate (fees folded in, 12-month basis) is shown, not the headline rate."""
    res = _Result(ts.doc_id, 1, state, mandate, day)
    fac = ts.proposed_facility
    all_in = fmt_pct(bp(ts.all_in_rate_bp)) if ts.all_in_rate_bp is not None else "unknown"
    headline = fmt_pct(bp(fac.rate_bp)) if fac is not None else "unknown"
    inputs = {"all_in_rate": all_in, "headline_rate": headline,
              "lender_id": fac.lender_id if fac is not None else "unknown",
              "basis": "rate + upfront fee over 12 months"}
    if trusted_owner_key_hex is not None:
        res.violations += check_validity(mandate, day, None, trusted_owner_key_hex)
    if fac is not None and not any(c.id == fac.lender_id and c.known for c in state.counterparties):
        res.violations.append(Violation(
            code=ViolationCode.UNKNOWN_COUNTERPARTY, message=f"Lender {fac.lender_id} is not on the owner's registry",
            observed=fac.lender_id, limit="owner-registered lenders", formula="lender ∈ registry", inputs=inputs))
    codes: list[ViolationCode] = []
    for clause in ts.tier3_clauses:
        code = TIER3_BY_FIELD.get(clause.field)
        if code is not None and code not in codes:
            codes.append(code)
    if fac is not None and fac.personal_guarantee and ViolationCode.TIER3_PERSONAL_GUARANTEE not in codes:
        codes.append(ViolationCode.TIER3_PERSONAL_GUARANTEE)
    if fac is not None and fac.collateral and ViolationCode.TIER3_COLLATERAL not in codes:
        codes.append(ViolationCode.TIER3_COLLATERAL)
    for code in codes:
        spans = [c.span for c in ts.tier3_clauses if TIER3_BY_FIELD.get(c.field) == code]
        res.violations.append(Violation(
            code=code, message=f"The term sheet requires a Tier-3 commitment "
            f"({code.value.removeprefix('TIER3_').lower().replace('_', ' ')}); the agent can never give it. "
            f"Shown to the owner at {all_in} all-in, not {headline}",
            observed=all_in, limit="no Tier-3 clauses", formula="tier3_clauses = ∅; all-in = rate + fee × 12/term",
            inputs=inputs, spans=spans))
    if ts.all_in_rate_bp is not None:
        v = check_apr(Ratio.of(bp(ts.all_in_rate_bp)), mandate, f"Term sheet from {inputs['lender_id']}")
        if v is not None:
            res.violations.append(v)
    if any(v.code.value.startswith("TIER3_") for v in res.violations):
        outcome, tier = Outcome.REJECT, Tier.TIER_3
    elif res.violations:
        outcome, tier = Outcome.REJECT, Tier.TIER_1
    else:
        outcome, tier = Outcome.NEEDS_OWNER_APPROVAL, Tier.TIER_2
    summary = _summary(outcome, res.violations, [f"All-in {all_in} over 12 months (headline {headline})",
                                                 "Only the owner can add a facility"])
    return res.verdict(outcome, tier, summary)


def counter_offer(c: CounterProposal, day: int = 0) -> CompiledOffer:
    """A counter's obligations as an offer, built as the commit hook builds a commitment's
    (`app.api.runtime.Runtime.reverify`)."""
    return CompiledOffer(offer_id=f"RECHECK-{c.id}",
                         counterparty_id=c.obligations[0].counterparty_id if c.obligations else "",
                         doc_ids=sorted({sp.doc_id for o in c.obligations for sp in o.spans}), received_day=day,
                         status=CompileStatus.COMPILED, obligations=list(c.obligations), compiler="whatif-reverify",
                         prompt_version="reverify-v1")


def counter_recheck(
    state: FinancialState,
    mandate: Mandate,
    *,
    trusted_owner_key_hex: str,
    day: int = 0,
    commitments: Sequence[Commitment] = (),
    router: _Router | None = None,
) -> Recheck:
    """The counter property's re-check: a counter's obligations evaluated as an offer on these same books (the
    commitments in force stay live), as the commit hook will evaluate them. The re-check generates no counters of
    its own. A counter whose terms the ledger cannot carry gets NO_VERDICT. Its `plan` is the router behind its
    memo, so a counter builder that prices liquidity on the counter's obligations shares the re-check's search."""
    return _CounterRecheck(state, mandate, trusted_owner_key_hex, day, commitments, router or _Router(mandate))


class _CounterRecheck:
    def __init__(self, state: FinancialState, mandate: Mandate, key: str, day: int,
                 commitments: Sequence[Commitment], router: _Router) -> None:
        self.state, self.mandate, self.key, self.day = state, mandate, key, day
        self.commitments, self.router = commitments, router

    def plan(self, state: FinancialState, obligations: Sequence[Obligation], mandate: Mandate,
             basis: str = "COMMITTED") -> FundingPlan:
        return self.router.plan(state, list(obligations), mandate, basis)

    def __call__(self, c: CounterProposal) -> Verdict:
        offer = counter_offer(c, self.day)
        try:
            return _evaluate(offer, self.state, self.mandate, trusted_owner_key_hex=self.key, day=self.day,
                             commitments=self.commitments, plans="committed", router=self.router,
                             with_counters=False).verdict
        except EngineError as e:
            res = _Result(offer.offer_id, offer.version, self.state, self.mandate, self.day)
            res.violations = [Violation(
                code=ViolationCode.UNRESOLVED_SCOPE, message="The counter's terms are inconsistent with the ledger",
                observed=type(e).__name__, limit="terms the ledger can carry",
                formula="project(state, obligations) succeeds", inputs={"reason": str(e)[:200]})]
            return res.verdict(Outcome.NO_VERDICT, Tier.TIER_1, _summary(Outcome.NO_VERDICT, res.violations))


def evaluate(
    offer: CompiledOffer,
    state: FinancialState,
    mandate: Mandate,
    *,
    trusted_owner_key_hex: str,
    day: int = 0,
    owner_declared: Mapping[str, Any] | None = None,
    commitments: Sequence[Commitment] = (),
    owner_constraints: OwnerConstraints | None = None,
    plans: Plans = "all",
    _router_probe: Callable[[_Router], None] | None = None,
) -> VerdictBundle:
    """The verifier never crashes on an offer: obligations the ledger cannot carry (e.g. the same invoice
    settled twice) are a NO_VERDICT with UNRESOLVED_SCOPE, and nothing is booked.

    `owner_constraints`: the owner's goal for this evaluation (stricter than the mandate); a package that
    breaks it gets COUNTER with counters that satisfy it, or REJECT when none does. It never loosens.
    `plans="committed"` skips the expected plan (display-only, INVARIANT 11) for callers that need only
    the committed plan; the Verdict is identical either way (conservative mode alone decides)."""
    router = _Router(mandate)
    try:
        return _evaluate(offer, state, mandate, trusted_owner_key_hex=trusted_owner_key_hex, day=day,
                         owner_declared=owner_declared, commitments=commitments,
                         owner_constraints=owner_constraints, plans=plans, router=router)
    except EngineError as e:
        res = _Result(offer.offer_id, offer.version, state, mandate, day, owner_constraints)
        res.violations = [Violation(
            code=ViolationCode.UNRESOLVED_SCOPE,
            message="The offer's terms are inconsistent with the ledger; clarification needed, nothing booked",
            observed=type(e).__name__, limit="terms the ledger can carry", formula="project(state, obligations) succeeds",
            inputs={"reason": str(e)[:200], "booked": "0"},
        )]
        summary = _summary(Outcome.NO_VERDICT, res.violations, ["Nothing booked"])
        return VerdictBundle(verdict=res.verdict(Outcome.NO_VERDICT, Tier.TIER_1, summary))
    finally:
        if _router_probe is not None:
            _router_probe(router)
