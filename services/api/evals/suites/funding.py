"""E9 funding router: optimality against an exhaustive brute force, savings against a "draw the line
first" baseline, honesty (no plan relies on an uncommitted facility) and latency.

The brute force is written here, independently of `app.funding.search`: it enumerates every usable
committed source as a lever (a line draw for each candidate repayment day, an advance or an early payment
on each receivable, a bill discount, a committed term loan), every combination of up to three levers,
a fine grid of amounts for all but one lever, and the exact minimal amount (to the fen) for the last one.
It shares only the engine (`financial.project`), the covenant evaluator and `funding.rates`
(`action_rate`, `approval_reason`: the one rate rule of docs/FINANCIAL_SEMANTICS.md section 4) with the router.

Plans are ranked as the router ranks them: a plan the executor cannot run today ranks after one it can, a plan
with a leg above the mandate's `max_apr_bp` (it needs the owner, Tier 2) ranks after one that needs nobody, then
the cheaper plan. A rate above the ceiling no longer makes a plan inadmissible; it makes it need the owner.
"""

from __future__ import annotations

import itertools
import random
import time
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from evals.common import Failure, Metric, SuiteResult, median, pct, quiet, ratio

REPRO = "uv run --project services/api python scripts/evaluate.py --suite funding"
TOLERANCE_FEN = 100  # ¥1


# ---------------------------------------------------------------- scenarios


def scenarios(n_random: int = 16, seed: int = 20261001) -> list[dict[str, Any]]:
    """Designed cases plus seeded random variants of the golden fixture. Each item is a dict of changes."""
    designed: list[dict[str, Any]] = [
        {"id": "F00_golden", "why": "golden fixture: line + invoice financing (¥3,113.93)"},
        {"id": "F01_dear_line", "why": "line at 11.5%: invoice financing is cheaper for part of the gap",
         "fac": {"FAC-LINE": {"rate_bp": 1150}}},
        {"id": "F02_cheap_early_pay", "why": "buyer offers 0.3% for 30 days early",
         "fac": {"FAC-EARLYPAY": {"rate_bp": 30}}},
        {"id": "F03_bill_held", "why": "¥400,000 of 银票 held at 0.58%", "fac": {"FAC-BILL": {"limit_fen": 40_000_000}}},
        {"id": "F04_no_new_borrowing", "why": "mandate forbids new borrowing", "mandate": {"allow_new_borrowing": False}},
        {"id": "F05_pending_cheap_ggl", "why": "a PENDING guaranteed loan at 1% must count as zero",
         "fac": {"FAC-GGL": {"status": "PENDING", "rate_bp": 100, "lead_time_days": 1}}},
        {"id": "F06_uncovered", "why": "only the line is usable: no admissible plan",
         "drop": ["FAC-IF", "FAC-EARLYPAY"]},
        {"id": "F07_big_line_clean_down", "why": "a ¥500,000 line: clean-down still needs 30 zero days",
         "fac": {"FAC-LINE": {"limit_fen": 50_000_000}}},
        {"id": "F08_late_payroll", "why": "payroll on day 28, lead times matter less", "flows": {"F-PAYROLL": {"day": 28}}},
        {"id": "F09_committed_cheap_loan_late", "why": "a committed 1% loan that lands on day 21 (after payroll)",
         "fac": {"FAC-GGL": {"status": "COMMITTED", "rate_bp": 100, "term_months": 1}}},
    ]
    rng = random.Random(seed)
    out = list(designed)
    for i in range(n_random):
        fac: dict[str, dict[str, Any]] = {
            "FAC-LINE": {"rate_bp": rng.choice([450, 550, 640, 800, 950, 1150]),
                         "limit_fen": rng.choice([0, 10_000_000, 15_000_000, 20_000_000, 30_000_000])},
            "FAC-IF": {"rate_bp": rng.choice([600, 700, 780, 900]), "fee_bp_per_advance": rng.choice([10, 25, 40]),
                       "lead_time_days": rng.choice([1, 3, 5, 8]), "advance_rate_bp": rng.choice([7000, 8000, 9000])},
            "FAC-EARLYPAY": {"rate_bp": rng.choice([40, 80, 120, 150]), "lead_time_days": rng.choice([1, 2, 4])},
        }
        if rng.random() < 0.4:
            fac["FAC-BILL"] = {"limit_fen": rng.choice([10_000_000, 20_000_000, 40_000_000]),
                               "rate_bp": rng.choice([58, 150, 300])}
        if rng.random() < 0.25:
            fac["FAC-GGL"] = {"status": "PENDING", "rate_bp": rng.choice([100, 300]), "lead_time_days": 1}
        item: dict[str, Any] = {
            "id": f"R{i + 1:02d}", "why": "seeded random variant",
            "cash_fen": rng.choice([30_000_000, 35_000_000, 40_000_000, 45_000_000]),
            "flows": {"F-PAYROLL": {"day": rng.randint(5, 25),
                                    "amount_fen": -rng.choice([28_000_000, 34_000_000, 40_000_000])}},
            "fac": fac,
        }
        if rng.random() < 0.25:
            item["clean_down_days"] = rng.choice([0, 60])  # 0: no clean-down covenant on the line
        out.append(item)
    return out


def build(spec: dict[str, Any]) -> tuple[Any, Any]:
    from app.domain.fixtures import load_scenario
    from app.domain.models import CovenantKind, FacilityStatus
    from app.mandate import load_signed_mandate

    s, _ = load_scenario()
    m = load_signed_mandate()
    upd: dict[str, Any] = {}
    if "cash_fen" in spec:
        upd["cash_fen"] = spec["cash_fen"]
    if spec.get("flows"):
        upd["flows"] = [f.model_copy(update=spec["flows"].get(f.id, {})) for f in s.flows]
    facs = []
    for f in s.facilities:
        if f.id in spec.get("drop", []):
            continue
        ch = dict(spec.get("fac", {}).get(f.id, {}))
        if "status" in ch:
            ch["status"] = FacilityStatus(ch["status"])
        f = f.model_copy(update=ch)
        if f.id == "FAC-LINE" and "clean_down_days" in spec:
            cds = spec["clean_down_days"]
            covs = [c for c in f.covenants if c.kind != CovenantKind.CLEAN_DOWN] if cds == 0 else [
                c.model_copy(update={"clean_down_days": cds}) if c.kind == CovenantKind.CLEAN_DOWN else c
                for c in f.covenants]
            f = f.model_copy(update={"covenants": covs})
        facs.append(f)
    upd["facilities"] = facs
    s = s.model_copy(update=upd)
    if spec.get("mandate"):
        m = m.model_copy(update=spec["mandate"])  # signature is irrelevant to the router
    return s, m


# ---------------------------------------------------------------- independent evaluation


@dataclass
class Lever:
    facility_id: str
    kind: str  # FundingActionKind value
    cap: int
    receivable_id: str | None = None
    repay_day: int | None = None
    rate_bp: int | None = None
    label: str = ""

    def action(self, amount: int) -> Any:
        from app.domain.models import FundingAction, FundingActionKind

        return FundingAction(kind=FundingActionKind(self.kind), facility_id=self.facility_id, day=0, amount_fen=amount,
                             receivable_id=self.receivable_id, repay_day=self.repay_day, rate_bp=self.rate_bp)

    def clashes(self, o: Lever) -> bool:
        if self.receivable_id and self.receivable_id == o.receivable_id:
            return True
        return self.facility_id == o.facility_id and self.kind in ("DRAW", "DISCOUNT_BILL")


@dataclass
class Checked:
    ok: bool
    cost: int | None
    reserve_ok: bool
    reasons: list[str] = field(default_factory=list)
    shortfall: int = 0  # max over days of (floor − closing), 0 when the floor holds
    approval: bool = False  # a leg costs more a year than the mandate lets the agent borrow alone
    unrunnable: bool = False  # a leg uses an invoice the executor cannot finance today


class Oracle:
    """Projects and checks candidate plans (with a cache); counts evaluations."""

    def __init__(self, state: Any, mandate: Any) -> None:
        from app.domain.models import Mode
        from app.financial import project

        self.s, self.m = state, mandate
        self.facs = {f.id: f for f in state.facilities}
        self.base = project(state, [], [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
        self.base_cost = self._cost(self.base)
        self.need = max(0, max(mandate.min_cash_fen - p.closing_fen for p in self.base.days))
        self.cache: dict[tuple, Checked] = {}
        self.evals = 0
        # what the executor lets a facility finance today: an issued, open, buyer-confirmed invoice of a known buyer
        buyers = {c.id for c in state.counterparties if c.role == "BUYER" and c.known}
        self.financeable = {r.id for r in state.receivables if r.status == "OPEN" and r.confirmed
                            and r.issue_day <= state.as_of_day and r.counterparty_id in buyers}

    @staticmethod
    def _cost(t: Any) -> int:
        return t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen

    def check(self, actions: list[Any], full: bool = True) -> Checked:
        from app.covenants import evaluate as evaluate_covenants
        from app.domain.models import FacilityKind, FacilityStatus, FundingActionKind, Mode
        from app.financial import EngineError, project
        from app.funding.rates import action_rate, approval_reason, invoice_landing_day

        key = (tuple(sorted((a.kind.value, a.facility_id, a.amount_fen, a.receivable_id or "", a.repay_day or -1)
                            for a in actions)), full)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        self.evals += 1
        try:
            t = project(self.s, [], actions, Mode.CONSERVATIVE, self.m.horizon_days, self.m.min_cash_fen)
        except EngineError as e:
            out = Checked(False, None, False, [f"engine: {type(e).__name__}"], shortfall=1 << 60)
            self.cache[key] = out
            return out
        cost = self._cost(t) - self.base_cost
        shortfall = max(0, max(self.m.min_cash_fen - p.closing_fen for p in t.days))
        reserve_ok = shortfall == 0
        reasons = [] if reserve_ok else ["RESERVE_BREACH"]
        approval = unrunnable = False
        for a in actions:
            f = self.facs[a.facility_id]
            due = self._due(a.receivable_id) if a.receivable_id else None
            landing = invoice_landing_day(f, a.day, self._issue(a.receivable_id)) if a.receivable_id else None
            rate, how = action_rate(f, a.kind, amount_fen=a.amount_fen, landing_day=landing, due_day=due,
                                    rate_bp=a.rate_bp)
            approval = approval or approval_reason(rate, how, self.m) is not None
            unrunnable = unrunnable or (a.kind == FundingActionKind.FINANCE_INVOICE
                                        and a.receivable_id not in self.financeable)
        if full and reserve_ok:
            used = {a.facility_id for a in actions}
            binding = [f for f in self.s.facilities if f.status == FacilityStatus.COMMITTED or f.id in used]
            reasons += [v.code.value for v in evaluate_covenants(t, binding, self.m)]
            for a in actions:
                f = self.facs[a.facility_id]
                if f.status != FacilityStatus.COMMITTED:
                    reasons.append("UNCOMMITTED_FACILITY")
                debt = f.kind not in (FacilityKind.BUYER_EARLY_PAY, FacilityKind.BANK_ACCEPTANCE_BILL)
                if debt and not self.m.allow_new_borrowing:
                    reasons.append("NEW_BORROWING_NOT_ALLOWED")
        out = Checked(reserve_ok and not reasons, cost, reserve_ok, sorted(set(reasons)), shortfall, approval,
                      unrunnable)
        self.cache[key] = out
        return out

    # receivables as the baseline sees them
    def receipts(self) -> dict[str, tuple[int, int]]:
        from app.domain.models import LedgerEventKind

        out = {}
        for p in self.base.days:
            for e in p.events:
                if e.kind == LedgerEventKind.RECEIPT and e.amount_fen > 0 and e.ref:
                    out[e.ref] = (p.day, e.amount_fen)
        return out

    def _issue(self, rid: str | None) -> int:
        for r in self.s.receivables:
            if r.id == rid:
                return max(0, r.issue_day)
        if rid and rid.startswith("RI:"):
            return max(0, int(rid.rsplit(":", 1)[1]))
        return 0

    def _due(self, rid: str | None) -> int | None:
        r = self.receipts().get(rid or "")
        return r[0] if r else None

    def counterparty(self, rid: str) -> str | None:
        for r in self.s.receivables:
            if r.id == rid:
                return r.counterparty_id
        if rid.startswith("RI:"):
            return rid.split(":")[1]
        return None

    @property
    def breach_days(self) -> list[int]:
        return [p.day for p in self.base.days if p.closing_fen < self.m.min_cash_fen]


def levers(o: Oracle) -> list[Lever]:
    from app.domain.models import FacilityKind, FacilityStatus, Repayment

    breaches = o.breach_days
    if not breaches:
        return []
    first = breaches[0]
    rec = o.receipts()
    inflow_days = sorted({p.day for p in o.base.days if p.day > first
                          and any(e.amount_fen > 0 and e.kind.value in ("RECEIPT", "FLOW") for e in p.events)})
    out: list[Lever] = []
    for f in sorted(o.s.facilities, key=lambda x: x.id):
        avail = f.limit_fen - f.drawn_fen
        if (f.status != FacilityStatus.COMMITTED or not f.owner_approved or avail <= 0 or f.personal_guarantee
                or f.collateral or f.kind == FacilityKind.EQUITY):
            continue
        if f.kind == FacilityKind.CREDIT_LINE and f.repayment == Repayment.BULLET:
            for d in inflow_days:
                if d > f.lead_time_days:
                    out.append(Lever(f.id, "DRAW", avail, repay_day=d, label=f"{f.id} repaid day {d}"))
        elif f.kind == FacilityKind.INVOICE_FINANCING:
            for rid, (due, amt) in rec.items():
                arrival = o._issue(rid) + f.lead_time_days
                if arrival < due and due > first:
                    cap = min(avail, (f.advance_rate_bp or 10_000) * amt // 10_000)
                    out.append(Lever(f.id, "FINANCE_INVOICE", cap, receivable_id=rid, label=f"{f.id} on {rid}"))
        elif f.kind == FacilityKind.BUYER_EARLY_PAY:
            for rid, (due, amt) in rec.items():
                arrival = o._issue(rid) + f.lead_time_days
                if o.counterparty(rid) == f.lender_id and arrival < due and due > first:
                    out.append(Lever(f.id, "EARLY_PAY", min(avail, amt), receivable_id=rid, rate_bp=f.rate_bp,
                                     label=f"{f.id} on {rid}"))
        elif f.kind == FacilityKind.BANK_ACCEPTANCE_BILL:
            out.append(Lever(f.id, "DISCOUNT_BILL", avail, repay_day=30 * (f.term_months or 6), rate_bp=f.rate_bp,
                             label=f"{f.id} bills"))
        elif f.term_months and f.repayment in (Repayment.BULLET, Repayment.AMORTISING):
            out.append(Lever(f.id, "DRAW", avail, label=f"{f.id} term draw"))
    return out


def _gross(lv: Lever, net: int, arrival_days: int) -> int:
    """Amount of `lv` whose cash on arrival is at least `net` (face for early pay and bills)."""
    if lv.kind == "EARLY_PAY":
        d = Fraction(lv.rate_bp or 0, 10_000)
        return -(-net * d.denominator // (d.denominator - d.numerator))
    if lv.kind == "DISCOUNT_BILL":
        d = Fraction(lv.rate_bp or 0, 10_000) * max(0, (lv.repay_day or 0) - arrival_days) / 365
        return int(-(-Fraction(net) // (1 - d)))
    return net


def min_fill(o: Oracle, prefix: list[Any], lv: Lever) -> tuple[int, Checked] | None:
    """Smallest amount (to the fen) of `lv` that, with `prefix`, keeps cash above the floor every day.

    Feasibility is monotone in the amount, so the answer is the `hi` of a bisection; the search is
    bracketed from a shortfall-based estimate (a few projections) and then closed exactly to 1 fen."""
    if not o.check([*prefix, lv.action(lv.cap)], full=False).reserve_ok:
        return None
    base = o.check(prefix, full=False) if prefix else None
    if base is not None and base.reserve_ok:
        return None  # the prefix alone suffices; a smaller subset covers it
    short = base.shortfall if base is not None else o.need
    hi = lv.cap
    est = min(lv.cap, max(1, _gross(lv, short, 0)))
    for _ in range(6):  # walk the estimate up until feasible
        chk = o.check([*prefix, lv.action(est)], full=False)
        if chk.reserve_ok:
            hi = est
            break
        if est == lv.cap:
            break
        est = min(lv.cap, est + max(1, _gross(lv, chk.shortfall, 0)))
    lo = 0
    probe = hi - 1
    step = 1
    while probe > 0:  # find an infeasible amount below hi (usually hi − 1)
        if not o.check([*prefix, lv.action(probe)], full=False).reserve_ok:
            lo = probe
            break
        hi = probe
        step *= 4
        probe = hi - step
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if o.check([*prefix, lv.action(mid)], full=False).reserve_ok:
            hi = mid
        else:
            lo = mid
    return hi, o.check([*prefix, lv.action(hi)], full=True)


def grid(cap: int, step: int) -> list[int]:
    return sorted({*range(step, cap, step), cap})


def brute_force(o: Oracle, step2: int, step3: int, budget_s: float) -> dict[str, Any]:
    lv = levers(o)
    best: tuple[int, list[str], list[Any], tuple[bool, bool]] | None = None
    t0 = time.perf_counter()
    complete = True

    def consider(actions: list[Any], chk: Checked, labels: list[str]) -> None:
        nonlocal best
        if not (chk.ok and chk.cost is not None):
            return
        # the router's order: runnable before unrunnable, no approval before approval, then cheaper
        if best is None or ((chk.unrunnable, chk.approval), chk.cost) < (best[3], best[0]):
            best = (chk.cost, labels, actions, (chk.unrunnable, chk.approval))

    for a in lv:  # single levers
        got = min_fill(o, [], a)
        if got:
            consider([a.action(got[0])], got[1], [a.label])
    def walk(fixed: list[Lever], filler: Lever, chosen: list[Any], step: int, labels: list[str]) -> None:
        """Every grid amount of each fixed lever, ascending, then the exact fill of `filler`. Costs rise
        with every amount, so a prefix that already costs as much as the best plan ends that branch."""
        nonlocal complete
        if len(chosen) == len(fixed):
            got = min_fill(o, chosen, filler)
            if got:
                consider([*chosen, filler.action(got[0])], got[1], labels)
            return
        lever = fixed[len(chosen)]
        for v in grid(lever.cap, step):
            if time.perf_counter() - t0 > budget_s:
                complete = False
                return
            prefix = [*chosen, lever.action(v)]
            part = o.check(prefix, full=False)
            if part.cost is None:
                continue
            if best is not None:
                # more levers only cost more and only raise the class: a prefix already ranked below the best
                # (a worse class, or the same class and as dear) ends the branch
                if (part.unrunnable, part.approval) > best[3] or (
                        (part.unrunnable, part.approval) == best[3] and part.cost >= best[0]):
                    break
            if part.reserve_ok:  # the prefix alone suffices: a smaller combination; more only costs more
                consider(prefix, o.check(prefix, full=True), labels[:len(prefix)])
                break
            walk(fixed, filler, prefix, step, labels)

    for size, step in ((2, step2), (3, step3)):
        for combo in itertools.combinations(lv, size):
            if any(x.clashes(y) for x, y in itertools.combinations(combo, 2)):
                continue
            for filler in combo:
                fixed = [x for x in combo if x is not filler]
                walk(fixed, filler, [], step, [x.label for x in (*fixed, filler)])
    return {"cost": best[0] if best else None, "levers": best[1] if best else [],
            "needs_approval": best[3][1] if best else None, "unrunnable": best[3][0] if best else None,
            "actions": [(a.kind.value, a.facility_id, a.amount_fen, a.receivable_id, a.repay_day)
                        for a in (best[2] if best else [])],
            "complete": complete, "n_levers": len(lv), "evals": o.evals}


def line_first_baseline(o: Oracle) -> dict[str, Any]:
    """Draw the committed line first (repaid when cash recovers), then the cheapest other committed source
    by nominal all-in rate, then the next, each filled to the fen."""
    from app.funding import all_in_rate

    breaches = o.breach_days
    if not breaches:
        return {"cost": 0, "admissible": True, "actions": []}
    lv = levers(o)
    lines = [x for x in lv if x.kind == "DRAW" and o.facs[x.facility_id].kind.value == "CREDIT_LINE"]
    recovery = [p.day for p in o.base.days if p.day > breaches[0] and p.closing_fen >= o.m.min_cash_fen]
    prefix: list[Any] = []
    if lines:
        rd = recovery[0] if recovery else lines[-1].repay_day
        line = min(lines, key=lambda x: abs((x.repay_day or 0) - (rd or 0)))
        got = min_fill(o, [], line)
        prefix = [line.action(got[0] if got else line.cap)]
    others = sorted((x for x in lv if o.facs[x.facility_id].kind.value != "CREDIT_LINE"),
                    key=lambda x: (all_in_rate(o.facs[x.facility_id])[0], o._due(x.receivable_id) or 0, x.label))
    used: list[Lever] = []
    for x in others:
        if o.check(prefix, full=False).reserve_ok:
            break
        if any(x.clashes(u) for u in used):
            continue
        got = min_fill(o, prefix, x)
        prefix = [*prefix, x.action(got[0] if got else x.cap)]
        used.append(x)
    chk = o.check(prefix, full=True)
    return {"cost": chk.cost if chk.ok else None, "admissible": chk.ok, "reasons": chk.reasons,
            "actions": [(a.kind.value, a.facility_id, a.amount_fen, a.receivable_id, a.repay_day) for a in prefix]}


# ---------------------------------------------------------------- run


def evaluate_scenario(spec: dict[str, Any], step2_fen: int, step3_fen: int, budget_s: float) -> dict[str, Any]:
    """Router plan, independent re-check, brute force and baseline for one scenario (runs in a worker)."""
    quiet()
    from app.domain.models import FacilityStatus
    from app.funding import plan

    s, m = build(spec)
    p = plan(s, [], m)
    o = Oracle(s, m)
    tb = time.perf_counter()
    router_acts = list(p.actions)
    status = {f.id: f.status for f in s.facilities}
    uncommitted = [a.facility_id for a in router_acts if status[a.facility_id] != FacilityStatus.COMMITTED]
    indep = o.check(router_acts, full=True)
    bf = brute_force(o, step2_fen, step3_fen, budget_s)
    r_class = (not p.executable_now, p.needs_owner_approval)
    flags_agree = (not p.admissible) or r_class == (indep.unrunnable, indep.approval)
    bl = line_first_baseline(o)
    need = p.need_fen
    r_cost = p.total_cost_fen if p.admissible else None
    if need == 0:
        optimal = p.admissible and not router_acts
    elif bf["cost"] is None:
        optimal = not p.admissible  # honest: no admissible plan exists on the grid, and it says so
    else:
        b_class = (bool(bf["unrunnable"]), bool(bf["needs_approval"]))
        optimal = p.admissible and r_cost is not None and (
            r_class < b_class or (r_class == b_class and r_cost <= bf["cost"] + TOLERANCE_FEN))
    return {
        "id": spec["id"], "why": spec["why"], "spec": spec, "need_fen": need, "router_admissible": p.admissible,
        "router_cost_fen": r_cost, "router_label": p.label,
        "router_actions": [(a.kind.value, a.facility_id, a.amount_fen, a.receivable_id, a.repay_day)
                           for a in router_acts],
        "router_independently_admissible": indep.ok if p.admissible else None,
        "router_needs_approval": p.needs_owner_approval, "router_executable_now": p.executable_now,
        "router_flags_agree": flags_agree, "brute_needs_approval": bf["needs_approval"],
        "router_independent_reasons": indep.reasons, "router_uses_uncommitted": uncommitted,
        "brute_cost_fen": bf["cost"], "brute_actions": bf["actions"], "brute_complete": bf["complete"],
        "brute_levers": bf["n_levers"], "brute_evals": bf["evals"],
        "baseline_cost_fen": bl["cost"], "baseline_admissible": bl["admissible"], "baseline_actions": bl["actions"],
        "optimal": optimal,
        "gap_to_brute_fen": (r_cost - bf["cost"]) if (r_cost is not None and bf["cost"] is not None) else None,
        "saving_vs_baseline_fen": (bl["cost"] - r_cost) if (r_cost is not None and bl["cost"] is not None) else None,
        "eval_s": round(time.perf_counter() - tb, 1),
    }


def run(n_random: int = 16, step2_fen: int = 500_000, step3_fen: int = 1_000_000, budget_s: float = 120.0,
        only: list[str] | None = None, workers: int | None = None, **_: Any) -> SuiteResult:
    import os
    from concurrent.futures import ProcessPoolExecutor

    quiet()
    from app.funding import plan

    res = SuiteResult(name="funding")
    specs = [sp for sp in scenarios(n_random) if not only or sp["id"] in only]
    latencies: list[float] = []  # measured here, sequentially, so worker contention does not inflate them
    for spec in specs:
        s, m = build(spec)
        t0 = time.perf_counter()
        plan(s, [], m)
        latencies.append((time.perf_counter() - t0) * 1000)
    n_workers = workers or min(len(specs), max(1, (os.cpu_count() or 2) - 1), 8)
    if n_workers > 1:
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            rows = list(ex.map(evaluate_scenario, specs, [step2_fen] * len(specs), [step3_fen] * len(specs),
                               [budget_s] * len(specs)))
    else:
        rows = [evaluate_scenario(sp, step2_fen, step3_fen, budget_s) for sp in specs]
    for row, ms in zip(rows, latencies, strict=True):
        row["router_ms"] = round(ms, 1)
        sid = row["id"]
        if not row["optimal"]:
            res.failures.append(Failure("funding", sid,
                                        f"{sid}: router {row['router_cost_fen']} (admissible={row['router_admissible']}) "
                                        f"vs brute force {row['brute_cost_fen']} fen ({row['why']})",
                                        f"{REPRO} --only {sid}", row))
        if row["router_admissible"] and not row["router_independently_admissible"]:
            res.failures.append(Failure("funding", sid + ":independent",
                                        f"{sid}: the router's plan fails an independent check: "
                                        f"{row['router_independent_reasons']}", f"{REPRO} --only {sid}", row))
        if not row["router_flags_agree"]:
            res.failures.append(Failure("funding", sid + ":flags",
                                        f"{sid}: the plan's needs-the-owner / runs-today flags differ from the "
                                        f"independent classification of its actions", f"{REPRO} --only {sid}", row))
        if row["router_uses_uncommitted"]:
            res.failures.append(Failure("funding", sid + ":uncommitted",
                                        f"{sid}: the committed plan uses {row['router_uses_uncommitted']}",
                                        f"{REPRO} --only {sid}", row))
    n = len(rows)
    with_need = [r for r in rows if r["need_fen"] > 0]
    opt = sum(r["optimal"] for r in rows)
    differs_lower = [r for r in with_need if r["router_cost_fen"] is not None and (
        r["baseline_cost_fen"] is None or r["router_cost_fen"] < r["baseline_cost_fen"])]
    savings = [r["saving_vs_baseline_fen"] for r in with_need if r["saving_vs_baseline_fen"] is not None]
    uncommitted_plans = sum(bool(r["router_uses_uncommitted"]) for r in rows)
    incomplete = sum(not r["brute_complete"] for r in rows)
    res.details = {"rows": rows, "latency_ms": latencies, "grid": {"pairs_step_fen": step2_fen,
                                                                   "triples_step_fen": step3_fen,
                                                                   "budget_s": budget_s}}
    res.metrics += [
        Metric("router_optimality", "Router optimality (within ¥1 of brute force)", ratio(opt, n),
               f"{opt}/{n} ({(ratio(opt, n) or 0):.0%})", "≥ 95%", (ratio(opt, n) or 0) >= 0.95, "funding",
               f"brute force incomplete on {incomplete}" if incomplete else ""),
        Metric("router_beats_line_first", "E9 router cheaper than 'line first' baseline (or baseline infeasible)",
               len(differs_lower), f"{len(differs_lower)}/{len(with_need)} scenarios with a gap", "≥ 5/20",
               len(differs_lower) * 20 >= 5 * max(1, len(with_need)), "funding"),
        Metric("router_saving_total", "Total saving vs 'line first' (where both admissible)", sum(savings),
               f"¥{sum(savings) / 100:,.2f} over {len(savings)} scenarios (median ¥{median(savings) / 100:,.2f})",
               "informational", None, "funding"),
        Metric("router_uncommitted_plans", "E9 committed plans relying on an uncommitted facility", uncommitted_plans,
               str(uncommitted_plans), "0", uncommitted_plans == 0, "funding"),
        Metric("router_latency", "Router latency p50 / p95", {"p50": median(latencies), "p95": pct(latencies, 95)},
               f"{median(latencies):.0f} / {pct(latencies, 95):.0f} ms", "informational", None, "funding"),
    ]
    return res
