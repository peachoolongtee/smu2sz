"""Counter generation, priced from the Debt Desk's marginal cost of funds (spec v2 §6.5, §8).

- **Early-pay counter (Option A).** Keep the current terms, no rebate; accept early settlement on up
  to the face that closes the near-term gap net of the committed line, at the largest whole-5bp rate
  strictly below the break-even discount d/(1−d) < c (0.85% < 0.88%). The face is rounded up to a coarse
  step (two significant figures of the invoice's outstanding amount, `early_pay_step`) so it nets at least the gap
  and does not reveal it (R-10), at most the outstanding amount; if that face fails its re-check the whole
  outstanding amount is tried, else no Option A; the router's committed plan on books that include the counter must
  keep the floor (else no Option A). Supplier cost = discount + that plan's cost.
- **Price-adjustment counter (Option B).** Accept a perpetual terms extension with the smallest
  whole-5bp PRICE_ADJUSTMENT whose per-invoice amount covers the per-invoice funding cost, no rebate.
  The offered terms are tried first, then shorter ones in 5-day steps down to the current terms + 5
  (60, 55, 50 days for 45-day terms going to 60); the longest that the router can fund on current books
  and that passes its own re-check is offered, otherwise none.

**Every counter passes its own re-check** (the counter property, curable reading): its obligations,
evaluated as an offer on the same books by the caller's `check` (as the commit hook will evaluate them),
must give ACCEPT or NEEDS_OWNER_APPROVAL, with
  - no covenant breach (DSCR, leverage, clean-down) and no MAX_APR_EXCEEDED;
  - every RESERVE_BREACH curable by an admissible committed plan (the cure the re-check names). A cure that
    needs the owner's approval counts. A cure flagged "cannot run today" counts only if every advance it
    makes is on an invoice issued on or before the first day the counter's terms take cash below the reserve
    (the counter's effective day for funding: the day the cure must have landed), and an invoice already on
    the books is open and confirmed.
A counter that fails is not offered, and one sentence says why no counter of that kind is possible. A
counter offered with a curable shortfall says, in one sentence, which plan funds it ("funded by the plan: ...").
- **Bounded extension.** Fewer invoices (the most that fit the cap), or the same invoices with the
  buyer's contingent credit made firm.
- **Rebate over the cap.** The largest whole-5bp rebate rate that fits the remaining headroom.

Each counter carries two numbers: `supplier_cost_fen`, what it costs the supplier (Option A: discount +
funding the rest of the gap), and `forward_value_fen`, the forward concession a commitment on it books: the net value of
its own obligations floored at 0, as in the aggregate (Option A: 0, an immediate discount is not a forward
concession; Option B: the extension net of the price adjustment).

Outbound text is template-filled from an allow-list of fields: the offer's own terms and the counter's
own terms. It never contains the reserve floor, a cap, a menu limit, the marginal rate or any
reservation value (INVARIANT 7). `rationale` and `formula` are supplier-side only.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from app.domain.models import (
    BaseKind,
    CompiledOffer,
    Contingency,
    CounterProposal,
    Duration,
    DurationKind,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingActionKind,
    Mandate,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    Outcome,
    Receivable,
    SourceSpan,
    Verdict,
    ViolationCode,
)
from app.domain.money import BP_DENOM, Ratio, bp, fmt_pct, fmt_yuan, post
from app.financial import project, value_concessions
from app.financial.invoices import terms_in_force
from app.funding import NoPermanentSourceError, break_even_discount, marginal_cost
from app.funding import plan as funding_plan
from app.funding.rates import break_even_cost_share
from app.mandate.predicates import discount_rate
from app.verifier.bind import bind, early_pay_lead, is_claimed, is_gain, open_receivables, recurring_for
from app.verifier.models import OwnerConstraints
from app.verifier.owner import breaches as owner_breaches
from app.verifier.reserve import baseline

STEP_BP = 5
NO_COUNTER_CODES = frozenset({
    ViolationCode.UNKNOWN_COUNTERPARTY,
    ViolationCode.TIER3_PERSONAL_GUARANTEE,
    ViolationCode.TIER3_COLLATERAL,
    ViolationCode.TIER3_EQUITY,
    ViolationCode.TIER3_MANDATE_CHANGE,
    ViolationCode.CONFLICTING_SOURCES,
    ViolationCode.UNRESOLVED_SCOPE,
    ViolationCode.MANDATE_EXPIRED,
    ViolationCode.MANDATE_REVOKED,
    ViolationCode.MANDATE_VERSION_MISMATCH,
    ViolationCode.BAD_SIGNATURE,
})
# The counter property: a counter re-checked as an offer on the same books gives one of these outcomes and none of
# these codes; a RESERVE_BREACH it shows must be curable in time (see `infeasibility`).
FEASIBLE_OUTCOMES = frozenset({Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL})
INFEASIBLE_CODES = frozenset({
    ViolationCode.DSCR_BREACH,
    ViolationCode.LEVERAGE_BREACH,
    ViolationCode.CLEAN_DOWN_BREACH,
    ViolationCode.MAX_APR_EXCEEDED,
})
_COVENANT_NAME = {ViolationCode.DSCR_BREACH: "DSCR", ViolationCode.LEVERAGE_BREACH: "leverage",
                  ViolationCode.CLEAN_DOWN_BREACH: "clean-down"}
TERMS_STEP_DAYS = 5  # shorter extensions the price-adjustment counter tries, in steps of this many days
Recheck = Callable[[CounterProposal], Verdict]  # the counter's obligations evaluated as an offer on the same books
_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
          10: "ten", 11: "eleven", 12: "twelve"}


# ---------------------------------------------------------------- formatting for outbound text


def money_text(fen: int) -> str:
    """Whole yuan without decimals ('¥211,900'), else two decimals ('¥1,871.30')."""
    return fmt_yuan(fen)[:-3] if fen % 100 == 0 else fmt_yuan(fen)


def rate_text(rate_bp: int) -> str:
    return fmt_pct(bp(rate_bp))


def invoices_text(n: int) -> str:
    return "the next invoice" if n == 1 else f"the next {_WORDS.get(n, str(n))} invoices"


def largest_step_below(limit: Fraction) -> int:
    """Largest whole-5bp rate strictly below `limit` (a fraction, not bp)."""
    k = -(-limit * BP_DENOM // STEP_BP) - 1  # ceil(limit in 5bp steps) − 1
    return max(0, int(k) * STEP_BP)


def smallest_step_covering(per_invoice_fen: int, face_fen: int) -> int:
    """Smallest whole-5bp rate r with post(r × face) >= per_invoice_fen."""
    r = STEP_BP
    while post(bp(r) * face_fen) < per_invoice_fen:
        r += STEP_BP
    return r


# ---------------------------------------------------------------- context


@dataclass
class _Ctx:
    offer: CompiledOffer
    verdict: Verdict
    state: FinancialState
    mandate: Mandate
    bound: list[Obligation]
    rate: Fraction  # marginal all-in annual rate
    rate_label: str
    constraints: OwnerConstraints | None = None  # the owner's goal for this evaluation, if any
    live: tuple[Obligation, ...] = ()  # obligations of commitments in force: part of the books, not of any counter
    check: Recheck | None = None  # the counter property's re-check; None: counters are not re-checked
    notes: list[str] = field(default_factory=list)  # why no counter of a kind is possible (one sentence each)
    funded: dict[str, str] = field(default_factory=dict)  # counter id -> the plan that funds its curable shortfall

    def why_not(self, c: CounterProposal) -> str | None:
        """None when `c` passes its own re-check (or there is no re-check); else why it fails, as a predicate.
        A counter that passes with a curable shortfall has the plan that funds it recorded in `funded`."""
        if self.check is None:
            return None
        v = self.check(c)
        why = infeasibility(v, self.state)
        if why is None:
            rb = next((x for x in v.violations if x.code == ViolationCode.RESERVE_BREACH), None)
            if rb is not None and v.plan is not None:
                self.funded[c.id] = (f"its terms leave a shortfall of {_shortfall(rb)} on day {rb.day}, funded by the "
                                     f"plan: {v.plan.label}")
        return why

    def planner(self) -> Callable[..., Any]:
        """The router as the re-check runs it (its memo, so the re-check reuses the plan), else the router itself."""
        return getattr(self.check, "plan", None) or funding_plan

    @property
    def cp(self) -> str:
        return self.offer.counterparty_id

    def of_type(self, t: ObligationType) -> list[Obligation]:
        return [o for o in self.bound if o.type == t]

    def value(self, obs: list[Obligation]) -> list[int]:
        return [cv.value_fen for cv in value_concessions(obs, self.state, _ratio(self.rate), self.rate_label,
                                                          self.mandate.forward_concession_horizon_days)]

    def net_new(self, obs: list[Obligation]) -> int:
        """New concessions + FIRM gains (contingent gains count as zero); may be negative."""
        return sum(v for ob, v in zip(obs, self.value(obs), strict=True)
                   if v >= 0 or ob.contingency == Contingency.FIRM)

    def net_forward(self, obs: list[Obligation]) -> int:
        """Existing + new concessions + FIRM gains (contingent gains count as zero)."""
        return sum(fc.value_fen for fc in self.state.forward_concessions) + self.net_new(obs)

    def forward_value(self, obs: list[Obligation]) -> int:
        """What a commitment on `obs` books as a forward concession: the net new value, floored at 0 as in
        the aggregate (a package never creates headroom). An immediate discount is valued at 0."""
        return max(0, self.net_new(obs))

    def fits(self, obs: list[Obligation]) -> bool:
        return self.net_forward(obs) <= self.mandate.max_aggregate_forward_concession_fen

    def current_terms(self) -> int | None:
        """The terms in force for the buyer's next invoice (accepted adjustments applied), which counter texts quote."""
        terms = terms_in_force(self.state, self.cp)
        if terms is not None:
            return terms
        rcvs = open_receivables(self.state, self.cp)
        return rcvs[0].terms_days if rcvs else None


def _shortfall(x: Any) -> str:
    return str(x.inputs.get("shortfall") or x.observed or "an amount")


def _ri_issue_day(receivable_id: str) -> int | None:
    """Issue day of a recurring invoice's receivable id ('RI:<buyer>:<issue day>', `app.financial.invoices`)."""
    if not receivable_id.startswith("RI:"):
        return None
    try:
        return int(receivable_id.rsplit(":", 1)[1])
    except ValueError:
        return None


def late_legs(plan: Any, state: FinancialState, day: int) -> list[str]:
    """The advances of a cure flagged "cannot run today" that cannot run by `day` (the first day the counter's
    terms take cash below the reserve): an invoice issued after `day`, or one on the books that is not open and
    confirmed. Empty for a plan that can run today."""
    if plan is None or getattr(plan, "executable_now", True):
        return []
    on_books = {r.id: r for r in state.receivables}
    out: list[str] = []
    for a in plan.actions:
        if a.kind != FundingActionKind.FINANCE_INVOICE or not a.receivable_id:
            continue
        r = on_books.get(a.receivable_id)
        if r is not None:
            if r.status != "OPEN" or not r.confirmed:
                out.append(f"{r.id} cannot be financed")
            elif r.issue_day > day:
                out.append(f"{r.id} is issued on day {r.issue_day}")
            continue
        issue = _ri_issue_day(a.receivable_id)
        if issue is None or issue > day:
            out.append(f"{a.receivable_id} is issued on day {issue}" if issue is not None
                       else f"{a.receivable_id} is not an invoice")
    return out


def infeasibility(v: Verdict, state: FinancialState) -> str | None:
    """Why a counter's re-check verdict `v` breaks the counter property (curable reading, see the module
    docstring), as a predicate ("cannot be funded from committed sources: ..."), or None when it holds."""
    for x in v.violations:
        if x.code == ViolationCode.RESERVE_BREACH and not x.curable:
            return f"cannot be funded from committed sources: the shortfall of {_shortfall(x)} on day {x.day} has no cure"
    for x in v.violations:
        if x.code == ViolationCode.RESERVE_BREACH and x.day is not None and (late := late_legs(v.plan, state, x.day)):
            return (f"cannot be funded in time: the shortfall of {_shortfall(x)} on day {x.day} is cured only by "
                    f"an advance that cannot run by then ({'; '.join(late)})")
    for x in v.violations:
        if x.code in _COVENANT_NAME:
            return f"would breach a covenant: {_COVENANT_NAME[x.code]} {x.observed} against {x.limit}"
        if x.code == ViolationCode.MAX_APR_EXCEEDED:
            return f"is above the mandate's rate ceiling: {x.observed} against {x.limit}"
    if v.outcome not in FEASIBLE_OUTCOMES:
        codes = ", ".join(dict.fromkeys(x.code.value for x in v.violations)) or "no code"
        return f"fails its own re-check ({v.outcome.value}: {codes})"
    return None


def plan_flags(plan: Any, subject: str) -> str:
    """What the router flagged on a plan or a comparison row, as "<subject> needs the owner's approval: ..." and
    "<subject> cannot run today: ...", or '' when it is neither. A text only: no verdict, counter or number reads it."""
    out: list[str] = []
    if getattr(plan, "needs_owner_approval", False):
        out.append(f"{subject} needs the owner's approval: {getattr(plan, 'approval_reason', '')}")
    if not getattr(plan, "executable_now", True):
        reason = getattr(plan, "not_executable_reason", "") or "it relies on an invoice that is not issued yet"
        out.append(f"{subject} cannot run today: {reason}")
    return "; ".join(out)


def flag_inputs(plan: Any, prefix: str) -> dict[str, str]:
    """The same flags as `inputs` entries (`<prefix>_needs_owner_approval`, ...); empty when the plan is not flagged."""
    out: dict[str, str] = {}
    if getattr(plan, "needs_owner_approval", False):
        out[f"{prefix}_needs_owner_approval"] = "true"
        if getattr(plan, "approval_reason", ""):
            out[f"{prefix}_approval_reason"] = plan.approval_reason
    if not getattr(plan, "executable_now", True):
        out[f"{prefix}_executable_now"] = "false"
        if getattr(plan, "not_executable_reason", ""):
            out[f"{prefix}_not_executable_reason"] = plan.not_executable_reason
    return out


def _ratio(x: Fraction) -> Ratio:
    return Ratio.of(x)


def _counter_id(verdict: Verdict, label: str) -> str:
    return "CTR-" + hashlib.sha256(f"{verdict.id}|{label}".encode()).hexdigest()[:12]


def _proposal(ctx: _Ctx, label: str, clauses: list[tuple[str, Obligation | None]], supplier_cost: int,
              rationale: str, formula: str) -> CounterProposal:
    """Assemble the outbound text from clauses; each obligation's span is its own clause.

    `supplier_cost` is the immediate cost to the supplier; `forward_value_fen` is derived here from the
    counter's own obligations, so a commitment on the counter books exactly what they are worth forward."""
    cid = _counter_id(ctx.verdict, label)
    text, obligations = "", []
    for n, (clause, ob) in enumerate(clauses, start=1):
        start = len(text) + (1 if text else 0)
        text = f"{text} {clause}" if text else clause
        if ob is not None:
            span = SourceSpan(doc_id=cid, start=start, end=start + len(clause), text=clause)
            obligations.append(ob.model_copy(update={"id": f"{cid}-O{n}", "spans": [span], "confidence": 1.0,
                                                     "unresolved": []}))
    return CounterProposal(id=cid, label=label, text=text, obligations=obligations, supplier_cost_fen=supplier_cost,
                           forward_value_fen=ctx.forward_value(obligations), rationale=rationale, formula=formula)


def _span_stub(cp: str) -> list[SourceSpan]:
    return [SourceSpan(doc_id=f"counter:{cp}", start=0, end=0, text="")]


def _obligation(cp: str, t: ObligationType, **kw: Any) -> Obligation:
    kw.setdefault("contingency", Contingency.FIRM)
    kw.setdefault("duration", Duration(kind=DurationKind.ONE_OFF))
    return Obligation(id="pending", type=t, counterparty_id=cp, spans=_span_stub(cp), confidence=1.0, **kw)


# ---------------------------------------------------------------- Option A: early-pay counter


def _target_receivable(ctx: _Ctx) -> Receivable | None:
    for ob in ctx.of_type(ObligationType.IMMEDIATE_DISCOUNT):
        if ob.base.receivable_id is not None:
            r = next((r for r in open_receivables(ctx.state, ctx.cp) if r.id == ob.base.receivable_id), None)
            if r is not None:
                return r
    rcvs = sorted(open_receivables(ctx.state, ctx.cp), key=lambda r: (r.due_day, r.id))
    return rcvs[0] if rcvs else None


def early_pay_step(outstanding_fen: int) -> int:
    """The early-pay face's rounding step in fen: the power of ten one digit below the outstanding amount's leading
    digit (¥10,000 for an invoice of ¥100,000 to ¥999,999.99), so the face keeps two significant figures."""
    return 10 ** max(0, len(str(max(outstanding_fen, 1))) - 2)


def early_pay_counter(ctx: _Ctx, label: str = "Option A") -> CounterProposal | None:
    r = _target_receivable(ctx)
    if r is None:
        return None
    settle = early_pay_lead(ctx.state, ctx.cp)
    n = r.due_day - settle  # days early: the tenor the break-even is computed for (ADR-0007)
    if n <= 0:
        return None
    try:
        d_ratio, _ = break_even_discount(ctx.state, ctx.mandate, n)
        c, k_periods, period = break_even_cost_share(ctx.state, ctx.mandate, n)
    except NoPermanentSourceError:
        return None
    rate_bp = largest_step_below(d_ratio.value)
    # never above the buyer's offered rate; a fixed sum offers its exact rate on its portion, floored to whole bp
    offered = [x for x in map(discount_rate, ctx.of_type(ObligationType.IMMEDIATE_DISCOUNT)) if x is not None]
    if offered:
        rate_bp = min(rate_bp, math.floor(min(offered) * BP_DENOM))
    if ctx.mandate.max_immediate_discount_bp is not None:
        rate_bp = min(rate_bp, ctx.mandate.max_immediate_discount_bp)
    if ctx.constraints is not None and ctx.constraints.max_early_pay_bp is not None:
        rate_bp = min(rate_bp, ctx.constraints.max_early_pay_bp)
    if rate_bp <= 0:
        return None

    _, base_plan = baseline(ctx.state, ctx.mandate, ctx.live)
    lines = [f for f in ctx.state.facilities if f.kind == FacilityKind.CREDIT_LINE and f.owner_approved
             and f.status == FacilityStatus.COMMITTED]
    line_avail = sum(max(0, f.limit_fen - f.drawn_fen) for f in lines)
    need = base_plan.need_fen
    net = need - line_avail
    if net <= 0:
        return None
    rate = bp(rate_bp)
    face_exact = Fraction(net) / (1 - rate)
    # R-10 (owner, 16 Oct): the face is a coarse step above the gap, never the gap to the ¥100, so the figure a buyer
    # reads does not give the owner's funding gap back; at most the invoice's outstanding amount.
    step = early_pay_step(r.outstanding_fen)
    stepped = min(int(-(-face_exact // step)) * step, r.outstanding_fen)

    def at(face: int, face_note: str) -> CounterProposal | None:
        disc_ob = _obligation(
            ctx.cp, ObligationType.IMMEDIATE_DISCOUNT, rate_bp=rate_bp, effective_day=settle,
            base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=face, receivable_id=r.id),
        )
        # the committed plan on books that include the counter: a counter that cannot keep the floor is not offered
        counter_plan = funding_plan(ctx.state, [*ctx.live, disc_ob], ctx.mandate, "COMMITTED")
        if not counter_plan.admissible:
            return None
        t = project(ctx.state, [*ctx.live, disc_ob], counter_plan.actions, Mode.CONSERVATIVE, ctx.mandate.horizon_days)
        live_discounts = 0
        if ctx.live:  # what the commitments in force already cost is not the counter's cost
            live_discounts = project(ctx.state, list(ctx.live), [], Mode.CONSERVATIVE,
                                     ctx.mandate.horizon_days).discounts_posted_fen
        # Read from the projection (ADR-0007): interest + fees + discounts the engine posts with the counter in the
        # books and the router's plan for the rest. The counter's own discount is its face at its rate; everything
        # else is the cost of funding the rest of the gap.
        total = t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen - live_discounts
        discount = post(rate * face)
        funding_cost = total - discount
        # ADR-0007 test 3 for the counter: it is offered only if it beats the standing plan, like with like
        # (both exclude the discounts the live commitments already post).
        if base_plan.admissible:
            t0 = project(ctx.state, list(ctx.live), base_plan.actions, Mode.CONSERVATIVE, ctx.mandate.horizon_days)
            standing = t0.interest_posted_fen + t0.fees_posted_fen + t0.discounts_posted_fen - live_discounts
            if total >= standing:
                return None

        clauses: list[tuple[str, Obligation | None]] = []
        touched_terms = bool(ctx.of_type(ObligationType.TERMS_EXTENSION))
        mentioned_rebate = bool(ctx.of_type(ObligationType.CONTINGENT_REBATE)) or any(
            is_claimed(o) for o in ctx.offer.obligations)
        current = ctx.current_terms()
        lead = []
        if touched_terms and current is not None:
            lead.append(f"Terms stay at {current} days")
        if mentioned_rebate:
            lead.append("no rebate" if lead else "No rebate is on record, so none applies")
        if lead:
            clauses.append((", ".join(lead) + ".", None))
        # red team e, F4: the promise names its day; any portion up to the face paid by then earns the rate
        settle_text = (f"We will accept early settlement on up to {money_text(face)} of this invoice at "
                       f"{rate_text(rate_bp)}, paid on or before day {settle}.")
        clauses.append((settle_text, disc_ob))
        if not lead:
            clauses.append(("Nothing else changes.", None))
        if k_periods is not None:
            times = f" × {k_periods}" if k_periods > 1 else ""
            c_text = f"{fmt_pct(ctx.rate, 4)} × {period}/365{times} = {fmt_pct(c, 4)}"
        else:
            c_text = f"{fmt_pct(ctx.rate, 4)} × {n}/365 = {fmt_pct(c, 4)}"
        formula = (
            f"break-even: d/(1−d) < c, c = {c_text} "
            f"→ d < {fmt_pct(d_ratio.value, 4)}; largest whole-5bp rate below it = {rate_text(rate_bp)}. "
            f"Face: (near-term need {fmt_yuan(need)} − committed line {fmt_yuan(line_avail)}) / (1 − {rate_text(rate_bp)}) "
            f"= {fmt_yuan(post(face_exact))} → up to {fmt_yuan(face)} ({face_note}). "
            f"Cost: discount {fmt_yuan(discount)} + funding the rest of the gap {fmt_yuan(funding_cost)} "
            f"({counter_plan.label}) = {fmt_yuan(total)}"
        )
        rationale = (f"Early settlement at {rate_text(rate_bp)} is cheaper than financing the invoice on the "
                     f"marginal committed source; the line covers the rest of the near-term gap.")
        # What the router flagged on the plans this counter stands on (supplier-side texts only: the outbound text, the
        # figures and whether the counter is offered are unchanged).
        for plan, subject in ((counter_plan, "the committed plan that funds the rest of the gap"),
                              (base_plan, "the standing plan it is compared with")):
            flags = plan_flags(plan, subject)
            if flags:
                formula += f". Flagged: {flags}"
                rationale += f" Note: {flags}."
        return _proposal(ctx, label, clauses, total, rationale, formula)

    # The rounded face first, then the whole outstanding amount; each must pass its own re-check. Never the ¥100
    # rounding: if neither passes, no early-pay counter is offered.
    candidates = [(stepped, f"rounded up to a whole {money_text(step)}, at most the outstanding amount")]
    if stepped != r.outstanding_fen:
        candidates.append((r.outstanding_fen, "the whole outstanding amount: the rounded face did not pass"))
    failed: tuple[CounterProposal, str] | None = None
    for face, note in candidates:
        if face <= 0:
            continue
        cand = at(face, note)
        if cand is None:
            continue
        why = ctx.why_not(cand)
        if why is None:
            return cand
        failed = failed or (cand, why)
    if failed is not None:
        ctx.notes.append(f"No {_KIND['early_pay']} counter ({_terms_text(failed[0])}): it {failed[1]}")
    return None


# ---------------------------------------------------------------- Option B: price adjustment


def price_adjustment_counter(ctx: _Ctx, ext: Obligation, label: str = "Option B") -> CounterProposal | None:
    """The offered terms with a compensating price, else the longest shorter terms (5-day steps, down to the
    current terms + 5) whose counter the router can fund on current books and that passes its own re-check.
    None, with one sentence in `ctx.notes`, when no terms in that range can be."""
    rec = recurring_for(ctx.state, ctx.cp)
    current = ctx.current_terms()
    if rec is None or current is None or ext.days_delta is None or ext.days_delta <= 0:
        return None
    offered = current + ext.days_delta  # days_delta was bound against the terms in force (bind.terms)
    refused: list[tuple[list[int], str]] = []  # runs of consecutive targets refused for the same reason
    for target in range(offered, current, -TERMS_STEP_DAYS):
        c, why = _price_adjustment_at(ctx, ext, current, target, rec.face_fen, label)
        if c is not None:
            if refused:
                ctx.notes.append(f"Price-adjustment counter at {target} days, not {offered}: " + "; ".join(
                    f"{_days_text(targets)} terms {why}" for targets, why in refused))
            return c
        if refused and refused[-1][1] == why:
            refused[-1][0].append(target)
        else:
            refused.append(([target], why))
    if refused:
        ctx.notes.append("No price-adjustment counter: " + "; ".join(
            f"{_days_text(targets)} terms {why}" for targets, why in refused))
    return None


def _days_text(targets: list[int]) -> str:
    """'60-day', '55- or 50-day', '55-, 50- or 45-day'."""
    if len(targets) == 1:
        return f"{targets[0]}-day"
    return ", ".join(f"{t}-" for t in targets[:-1]) + f" or {targets[-1]}-day"


def _price_adjustment_at(ctx: _Ctx, ext: Obligation, current: int, target: int, face: int,
                         label: str) -> tuple[CounterProposal | None, str]:
    """The price-adjustment counter at `target`-day terms, or (None, why not)."""
    delta = target - current
    update: dict[str, Any] = {"contingency": Contingency.FIRM, "days_delta": delta}
    if ext.target_terms_days is not None:
        update["target_terms_days"] = target
    terms = ext.model_copy(update=update)
    cv = value_concessions([terms], ctx.state, _ratio(ctx.rate), ctx.rate_label,
                           ctx.mandate.forward_concession_horizon_days)[0]
    per_invoice = cv.per_invoice_fen or 0
    rate_bp = smallest_step_covering(per_invoice, face)
    price = _obligation(
        ctx.cp, ObligationType.PRICE_ADJUSTMENT, rate_bp=rate_bp,
        base=ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=face),
        duration=Duration(kind=DurationKind.RECURRING_PERPETUAL),
    )
    if not ctx.fits([terms, price]):
        return None, f"with a {rate_text(rate_bp)} price adjustment exceed the forward-concession budget"
    clauses: list[tuple[str, Obligation | None]] = [
        (f"{target}-day terms accepted", terms),
        (f"with a {rate_text(rate_bp)} price adjustment on future invoices, no rebate.", price),
    ]
    # Liquidity: the router's committed plan on current books with the counter's obligations, the same call the
    # early-pay counter makes (on the counter's own obligations, so the re-check below reuses it). A counter that
    # cannot keep the floor is not offered.
    obs = _proposal(ctx, label, clauses, 0, "", "").obligations
    plan = ctx.planner()(ctx.state, [*ctx.live, *obs], ctx.mandate, "COMMITTED")
    if not plan.admissible:
        return None, "cannot be funded from committed sources: no committed plan keeps cash at the reserve"
    ext_v, price_v = ctx.value([terms, price])
    net = ext_v + price_v
    per_price = post(bp(rate_bp) * face)
    formula = (
        f"smallest whole-5bp rate r with r × {fmt_yuan(face)} >= per-invoice funding cost "
        f"{fmt_yuan(per_invoice)}: {rate_text(rate_bp)} → {fmt_yuan(per_price)} per invoice. "
        f"12-month: extension {fmt_yuan(ext_v)} + price adjustment {fmt_yuan(price_v)} = {fmt_yuan(net)} "
        f"(cost to the supplier {fmt_yuan(max(0, net))}). "
        f"Funded on current books with these terms by the router's committed plan ({plan.label}), "
        f"cost {fmt_yuan(plan.total_cost_fen)}"
    )
    rationale = ("The price adjustment covers the per-invoice cost of funding the longer terms on the marginal "
                 "committed source, so the net forward concession is about zero; on current books with these terms "
                 f"the router's committed plan ({plan.label}) keeps the reserve.")
    if target != current + (ext.days_delta or 0):
        rationale += (f" The offered {current + (ext.days_delta or 0)}-day terms fail their own re-check; {target} days "
                      "is the longest that passes.")
    if flags := plan_flags(plan, "the committed plan that funds these terms"):
        formula += f". Flagged: {flags}"
        rationale += f" Note: {flags}."
    c = _proposal(ctx, label, clauses, max(0, net), rationale, formula)
    if why := ctx.why_not(c):
        return None, why
    if funded := ctx.funded.get(c.id):  # the shortfall its terms cause and the plan the re-check cures it with
        c = c.model_copy(update={"formula": f"{c.formula}. Re-check: {funded}",
                                 "rationale": f"{c.rationale} Re-checked as an offer, {funded}."})
    return c, ""


# ---------------------------------------------------------------- bounded extension


def bounded_extension_counters(ctx: _Ctx, ext: Obligation) -> list[CounterProposal]:
    n = ext.duration.invoices or 0
    delta = ext.days_delta or 0
    others = [o for o in ctx.bound if o is not ext and not (o.contingency != Contingency.FIRM and is_gain(o))]
    out: list[CounterProposal] = []
    for k in range(n - 1, 0, -1):
        fewer = ext.model_copy(update={"duration": Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=k)})
        if ctx.fits([fewer, *others]):
            v = ctx.value([fewer])[0]
            formula = (f"largest invoice count k < {n} with existing + {k} × per-invoice funding cost within the "
                       f"concession budget: k = {k}, value {fmt_yuan(v)}")
            out.append(_proposal(ctx, "Option A", [
                (f"We can extend terms by {delta} days on {invoices_text(k)}.", fewer)], max(0, v),
                "Fewer extended invoices keep the forward concession inside the mandate.", formula))
            break
    credits = [o for o in ctx.bound if o.type == ObligationType.PRICE_ADJUSTMENT and o.contingency != Contingency.FIRM
               and is_gain(o) and o.rate_bp is not None]
    rec = recurring_for(ctx.state, ctx.cp)
    if credits and rec is not None:
        firm = [c.model_copy(update={
            "contingency": Contingency.FIRM,
            "base": ObligationBase(kind=BaseKind.FUTURE_INVOICES, amount_fen=rec.face_fen),
            "duration": Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=n),
        }) for c in credits]
        if ctx.fits([ext, *firm, *others]):
            values = ctx.value([ext, *firm])
            net = sum(values)
            formula = (f"extension {fmt_yuan(values[0])} + firm credit "
                       f"{' + '.join(fmt_yuan(v) for v in values[1:])} = {fmt_yuan(net)}")
            clauses: list[tuple[str, Obligation | None]] = [
                (f"We can extend terms by {delta} days on {invoices_text(n)}", ext),
            ]
            for c in firm:
                clauses.append((f"if the {rate_text(c.rate_bp or 0)} credit is firm on each of them.", c))
            out.append(_proposal(ctx, "Option B", clauses, max(0, net),
                                 "A firm credit is a FIRM gain and may offset the extension; a contingent one "
                                 "counts as zero.", formula))
    return out


# ---------------------------------------------------------------- rebate reduction


def rebate_counter(ctx: _Ctx) -> CounterProposal | None:
    rebates = [o for o in ctx.of_type(ObligationType.CONTINGENT_REBATE)
               if o.rate_bp is not None and o.base.amount_fen is not None]
    if len(rebates) != 1:
        return None
    rb = rebates[0]
    others = [o for o in ctx.bound if o is not rb]
    base = rb.base.amount_fen or 0
    headroom = ctx.mandate.max_aggregate_forward_concession_fen - ctx.net_forward(others)
    cap = ctx.mandate.per_buyer_caps_fen.get(ctx.cp)
    if cap is not None:
        existing = sum(fc.value_fen for fc in ctx.state.forward_concessions if fc.counterparty_id == ctx.cp)
        headroom = min(headroom, cap - existing - sum(max(0, v) for v in ctx.value(others)))
    r = (rb.rate_bp or 0) - STEP_BP
    while r > 0 and post(bp(r) * base) > headroom:
        r -= STEP_BP
    if r <= 0:
        return None
    new = rb.model_copy(update={"rate_bp": r})
    value = post(bp(r) * base)
    formula = (f"largest whole-5bp rate r below {rate_text(rb.rate_bp or 0)} with r × {fmt_yuan(base)} inside the "
               f"remaining concession budget: {rate_text(r)} → {fmt_yuan(value)}")
    return _proposal(ctx, "Option A", [
        (f"We can offer {rate_text(r)} off next quarter's purchases of up to {money_text(base)}.", new)],
        value, "A smaller rebate keeps every committed package inside the mandate.", formula)


# ---------------------------------------------------------------- entry point


def counters(
    offer: CompiledOffer,
    verdict: Verdict,
    state: FinancialState,
    mandate: Mandate,
    *,
    bound: Sequence[Obligation] | None = None,
    owner_declared: Mapping[str, Any] | None = None,
    owner_constraints: OwnerConstraints | None = None,
    live: Sequence[Obligation] = (),
    check: Recheck | None = None,
) -> list[CounterProposal]:
    """Counters for a verdict that needs one. Empty when no counter is possible or appropriate.
    `live` are the obligations of commitments in force (current books); the counters' own obligations,
    texts and forward values never include them.

    With `owner_constraints`, the early-pay rate is capped at the owner's maximum and every counter that
    still breaks a constraint is dropped. With `check` (the verifier's re-check of a counter as an offer on the
    same books), a counter that fails it is not offered (the counter property)."""
    return counters_explained(offer, verdict, state, mandate, bound=bound, owner_declared=owner_declared,
                              owner_constraints=owner_constraints, live=live, check=check)[0]


def counters_explained(
    offer: CompiledOffer,
    verdict: Verdict,
    state: FinancialState,
    mandate: Mandate,
    *,
    bound: Sequence[Obligation] | None = None,
    owner_declared: Mapping[str, Any] | None = None,
    owner_constraints: OwnerConstraints | None = None,
    live: Sequence[Obligation] = (),
    check: Recheck | None = None,
) -> tuple[list[CounterProposal], list[str]]:
    """`counters()` and, for each kind of counter that cannot be offered because it fails its own re-check,
    one sentence saying why."""
    codes = {v.code for v in verdict.violations}
    if codes & NO_COUNTER_CODES:
        return [], []
    if bound is None:
        bound, _ = bind(offer, state, owner_declared)
    try:
        rate_ratio, fid = marginal_cost(state, mandate)
    except NoPermanentSourceError:
        return [], []
    fac = next(f for f in state.facilities if f.id == fid)
    ctx = _Ctx(offer, verdict, state, mandate, list(bound), rate_ratio.value,
               f"committed marginal source: {fac.name} {fmt_pct(rate_ratio.value, 4)}", owner_constraints,
               tuple(live), check)
    out = _counters(ctx, offer)
    if owner_constraints is not None:
        out = [c for c in out if not owner_breaches(
            c.obligations, value_concessions(c.obligations, state, _ratio(ctx.rate), ctx.rate_label,
                                             mandate.forward_concession_horizon_days), state, owner_constraints)]
    funded = [f"{c.label} passes its own re-check: {ctx.funded[c.id]}" for c in out if c.id in ctx.funded]
    return out, [*ctx.notes, *funded]


_KIND = {"early_pay": "early-pay", "bounded": "bounded-extension", "rebate": "rebate"}


def _passes(ctx: _Ctx, kind: str, c: CounterProposal | None) -> CounterProposal | None:
    """`c` when it passes its own re-check; else None, and one sentence in `ctx.notes`."""
    if c is None:
        return None
    why = ctx.why_not(c)
    if why is None:
        return c
    ctx.notes.append(f"No {_KIND[kind]} counter ({_terms_text(c)}): it {why}")
    return None


def _terms_text(c: CounterProposal) -> str:
    """The counter's own terms, from its typed obligations (never its text)."""
    out: list[str] = []
    for o in c.obligations:
        if o.type == ObligationType.IMMEDIATE_DISCOUNT:
            out.append(f"early settlement of {money_text(o.base.amount_fen or 0)} at {rate_text(o.rate_bp or 0)}")
        elif o.type == ObligationType.TERMS_EXTENSION:
            n = o.duration.invoices
            out.append(f"+{o.days_delta or 0} days on " + (invoices_text(n) if n else "future invoices"))
        elif o.type == ObligationType.PRICE_ADJUSTMENT:
            out.append(f"a {rate_text(o.rate_bp or 0)} {'credit' if is_gain(o) else 'price adjustment'}")
        elif o.type == ObligationType.CONTINGENT_REBATE:
            out.append(f"a {rate_text(o.rate_bp or 0)} rebate")
        else:
            out.append(o.type.value.lower().replace("_", " "))
    return ", ".join(out)


def _relabel(ctx: _Ctx, c: CounterProposal, label: str) -> CounterProposal:
    """`c` under `label` (its id, its obligations' ids and spans follow the label, as `_proposal` builds them)."""
    if c.label == label:
        return c
    cid = _counter_id(ctx.verdict, label)
    obs = [o.model_copy(update={"id": cid + o.id.removeprefix(c.id),
                                "spans": [s.model_copy(update={"doc_id": cid}) for s in o.spans]})
           for o in c.obligations]
    if c.id in ctx.funded:
        ctx.funded[cid] = ctx.funded.pop(c.id)
    return c.model_copy(update={"id": cid, "label": label, "obligations": obs})


def _counters(ctx: _Ctx, offer: CompiledOffer) -> list[CounterProposal]:

    lengthening = [o for o in ctx.of_type(ObligationType.TERMS_EXTENSION) if (o.days_delta or 0) > 0]
    perpetual = [o for o in lengthening if o.duration.kind == DurationKind.RECURRING_PERPETUAL]
    bounded = [o for o in lengthening if o.duration.kind == DurationKind.RECURRING_BOUNDED]
    has_discount = bool(ctx.of_type(ObligationType.IMMEDIATE_DISCOUNT))
    claimed = any(is_claimed(o) for o in offer.obligations)

    out: list[CounterProposal] = []
    if has_discount or perpetual or (claimed and not ctx.bound):
        a = early_pay_counter(ctx)  # re-checked inside, so that the whole outstanding amount can be tried
        if a is not None:
            out.append(a)
        if len(perpetual) == 1:  # re-checked inside, so that shorter terms can be tried
            b = price_adjustment_counter(ctx, perpetual[0], "Option B" if out else "Option A")
            if b is not None:
                out.append(b)
    elif len(bounded) == 1:
        kept = [c for c in (_passes(ctx, "bounded", c) for c in bounded_extension_counters(ctx, bounded[0]))
                if c is not None]
        out.extend(_relabel(ctx, c, f"Option {'AB'[i]}") for i, c in enumerate(kept))
    elif ctx.of_type(ObligationType.CONTINGENT_REBATE):
        r = _passes(ctx, "rebate", rebate_counter(ctx))
        if r is not None:
            out.append(r)
    return out
