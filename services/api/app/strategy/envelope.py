"""The Safe Deal Envelope: what the supplier can live with for one named buyer, before the buyer asks
(docs/STRATEGY_MVP_BRIEF.md section 5.2).

A sweep over the real verifier, the what-if sandbox's own call (`whatif.offer.build` then `verifier.evaluate`): the
largest value of each lever alone (bisection with the two neighbours past the boundary checked, a full scan of the
lever when a neighbour disagrees), the region terms x price (on request), and a grid of packages, each re-evaluated whole.
A package counts as approved when the verifier passes it (ACCEPT, or NEEDS_OWNER_APPROVAL with every reserve breach
curable) and the counter re-check (`counters.infeasibility`) finds nothing wrong with it.

Read-only and pure in (books, mandate, day, commitments): nothing is stored, no verdict is put, every figure is an
engine output (the verifier's own plan costs and violations), never a new computation. The method is the research
spike's (`scripts/research/envelope_spike.py`, the oracle `fixtures/strategy/envelope_day0.json`).

`envelope_facts` runs the sweep (language-neutral, cacheable); `envelope_answer` words it in `en` or `zh`;
`envelope` does both.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Literal, NamedTuple

from pydantic import Field

from app.alerts.engine import past_due_invoices
from app.api.presentation import party_name, t, when_text
from app.books import Books
from app.domain.models import (
    Commitment,
    Contract,
    CounterProposal,
    FinancialState,
    Mandate,
    ObligationType,
    Outcome,
    Verdict,
    ViolationCode,
)
from app.domain.money import bp, fmt_pct, fmt_yuan
from app.domain.ports import LedgerStore
from app.financial import value_concessions
from app.funding import NoPermanentSourceError, marginal_cost
from app.strategy.types import CandidatePackage
from app.verifier import bind, evaluate
from app.verifier.counters import infeasibility, smallest_step_covering
from app.whatif.offer import Context, EarlyPayContext, build, context
from app.whatif.params import (
    DISCOUNT_MAX_BP,
    FACE_STEP_FEN,
    PRICE_MAX_BP,
    RATE_STEP_BP,
    REBATE_MAX_BP,
    TERMS_MAX,
    TERMS_MIN,
    TERMS_STEP,
    WhatIfParamError,
    WhatIfParams,
)

PASSING = (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL)
CAP_CODES = (ViolationCode.AGG_CONCESSION_EXCEEDED, ViolationCode.PER_BUYER_CAP_EXCEEDED)
MVP_TERMS_STEPS = 3  # the default package grid: the terms in force, +5 and +10 days

# the levers, by the oracle's own labels (fixtures/strategy/envelope_day0.json `maxima[].lever`)
TERMS_ALONE = "Terms (days), alone"
TERMS_BUDGET_IGNORED = "Terms (days), budget ignored"
TERMS_WITH_PRICE = "Terms (days), with the price that compensates it"
REBATE = "Rebate on the expected order"


def early_pay_lever(face_fen: int) -> str:
    return f"Early pay on {fmt_yuan(face_fen)}"


class Setting(NamedTuple):
    """One package on the what-if grid. `face` is the early-pay face in fen (None: the whole open invoice)."""

    terms: int
    price: int = 0
    discount: int = 0
    face: int | None = None
    rebate: int = 0


@dataclass(frozen=True)
class Probe:
    """What the verifier said about one setting."""

    setting: Setting
    outcome: str
    tier: str
    passes: bool  # ACCEPT or NEEDS_OWNER_APPROVAL with every reserve breach curable
    liquidity_only: bool  # passes if the forward budget is ignored (every violation is a cap or a curable reserve breach)
    codes: tuple[str, ...]
    binding: tuple[str, ...]  # the codes that make it fail (a curable reserve breach does not)
    forward_total_fen: int
    reserve_day: int | None
    reserve_curable: bool | None
    cure_cost_fen: int | None
    cure_needs_owner: bool  # the reserve cure needs the owner's approval
    cure_cannot_run_today: bool  # the reserve cure's funding cannot run today
    counters: tuple[Setting, ...]  # the verifier's own counters to this setting, read as settings
    counter_costs_fen: tuple[int, ...]  # each counter's own cost to the supplier (`supplier_cost_fen`), in the same order
    plan_cost_fen: int | None  # FundingPlan.total_cost_fen of the verdict's committed plan
    recheck: str | None  # why the package would fail the counter re-check (None: it would pass)

    @property
    def approved(self) -> bool:
        return self.passes and self.recheck is None


@dataclass(frozen=True)
class Ranges:
    terms: tuple[int, ...]  # empty when the buyer has no recurring invoice to extend
    price: tuple[int, ...]
    discount: tuple[int, ...]
    rebate: tuple[int, ...]
    face_max_fen: int


def open_context(state: FinancialState, day: int, buyer_id: str) -> Context | EarlyPayContext:
    """The what-if context of one buyer, with the early-pay face the invoice still owes: an invoice paid in part is
    asked about for its outstanding amount, not the original face the sandbox's own builder would name."""
    ctx = context(state, day, buyer_id)
    rcv = ctx.receivable
    if rcv.outstanding_fen >= rcv.face_fen:
        return ctx
    return replace(ctx, receivable=rcv.model_copy(update={"face_fen": rcv.outstanding_fen}))


def ranges_for(ctx: Context | EarlyPayContext, mandate: Mandate) -> Ranges:
    """The levers' own ranges: the what-if grid, with the discount held to the mandate's immediate-discount cap."""
    cap = DISCOUNT_MAX_BP if mandate.max_immediate_discount_bp is None else min(DISCOUNT_MAX_BP, mandate.max_immediate_discount_bp)
    terms: tuple[int, ...] = ()
    if isinstance(ctx, Context):
        terms = tuple(range(min(TERMS_MIN, ctx.recurring.terms_days), TERMS_MAX + 1, TERMS_STEP))
    return Ranges(
        terms=terms,
        price=tuple(range(0, PRICE_MAX_BP + 1, RATE_STEP_BP)) if terms else (0,),
        discount=tuple(range(0, cap + 1, RATE_STEP_BP)),
        rebate=tuple(range(0, REBATE_MAX_BP + 1, RATE_STEP_BP)) if terms else (0,),
        face_max_fen=ctx.receivable.face_fen - ctx.receivable.face_fen % FACE_STEP_FEN,
    )


# ---------------------------------------------------------------- bisection


@dataclass(frozen=True)
class Found:
    """A search result. `value` is the extreme value that passes (None: none does); `confirmed` says the two neighbours
    past the boundary agree with it; `scanned` says a neighbour disagreed and the whole lever was scanned."""

    value: int | None
    confirmed: bool
    scanned: bool = False


def _scan_max(values: Sequence[int], ok: Callable[[int], bool]) -> Found:
    return Found(max(v for v in values if ok(v)), False, True)


def last_true(values: Sequence[int], ok: Callable[[int], bool], *, hint: int | None = None, gallop: bool = False,
              hint_steps: int = 2) -> Found:
    """Largest value with ok(value), assuming ok holds up to a boundary and fails after it (binary search, then the two
    values past the boundary checked; if one passes the lever is scanned whole and its largest passing value returned).
    A `hint` (a value expected to be the boundary) is tried first: it stands when it passes and the two values past it
    fail, which is the same evidence the search ends with; otherwise the search runs as if there were no hint. With
    `gallop` the search first doubles its steps up from the first value (cheap when the boundary is near it, as for
    the terms, where a long extension is also the costliest evaluation). `hint_steps` is how many values past the
    hint must fail for it to stand (a sibling search's boundary, which had both neighbours checked, stands on one)."""
    if not values or not ok(values[0]):
        return Found(None, True)
    if hint is not None and hint in values:
        i = values.index(hint)
        if ok(hint) and not any(ok(v) for v in values[i + 1: i + 1 + hint_steps]):
            return Found(hint, True)
    lo, hi = 0, len(values)  # values[hi] is past the end: the top of the range is only probed when the search gets there
    step = 1
    while gallop and lo + step < hi:
        if ok(values[lo + step]):
            lo += step
            step *= 2
        else:
            hi = lo + step
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(values[mid]):
            lo = mid
        else:
            hi = mid
    if any(ok(v) for v in values[lo + 1: lo + 3]):
        return _scan_max(values, ok)
    return Found(values[lo], True)


def first_true(values: Sequence[int], ok: Callable[[int], bool], *, hint: int | None = None, hint_steps: int = 2) -> Found:
    """Smallest value with ok(value), assuming ok fails up to a boundary and holds after it (see `last_true`)."""
    if not values:
        return Found(None, True)
    if hint is not None and hint in values:
        i = values.index(hint)
        if ok(hint) and not any(ok(v) for v in values[max(0, i - hint_steps): i]):
            return Found(hint, True)
    if hint != values[0] and ok(values[0]):
        return Found(values[0], True)
    if not ok(values[-1]):
        return Found(None, True)
    lo, hi = 0, len(values) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(values[mid]):
            hi = mid
        else:
            lo = mid
    if any(ok(v) for v in values[max(0, hi - 2): hi]):
        return _scan_min(values, ok)
    return Found(values[hi], True)


def _scan_min(values: Sequence[int], ok: Callable[[int], bool]) -> Found:
    return Found(min(v for v in values if ok(v)), False, True)


def descend(values: Sequence[int], ok: Callable[[int], bool], start: int) -> Found:
    """Largest value with ok(value), looked for downward from `start` (a value known to be the lever's standalone
    maximum): the first value that passes is taken when the two above it fail. At most four steps down, then `last_true`."""
    if start not in values:
        return last_true(values, ok)
    i = values.index(start)
    for _ in range(4):
        if i < 0 or ok(values[i]):
            break
        i -= 1
    else:
        return last_true(values[: i + 1], ok)
    if i < 0:
        return Found(None, True)
    if any(ok(v) for v in values[i + 1: i + 3]):
        return _scan_max(values, ok)
    return Found(values[i], True)


# ---------------------------------------------------------------- the verifier behind a memo


def _setting_of(c: CounterProposal, current_terms: int, receivable_face_fen: int) -> Setting:
    """A verifier counter read as a setting of the what-if grid."""
    terms, price, discount, face, rebate = current_terms, 0, 0, None, 0
    for o in c.obligations:
        if o.type == ObligationType.TERMS_EXTENSION and o.target_terms_days is not None:
            terms = o.target_terms_days
        elif o.type == ObligationType.PRICE_ADJUSTMENT and o.rate_bp is not None:
            price = o.rate_bp
        elif o.type == ObligationType.IMMEDIATE_DISCOUNT and o.rate_bp is not None and o.days_delta is None:
            discount = o.rate_bp
            face = o.base.amount_fen if o.base.amount_fen not in (None, receivable_face_fen) else None
        elif o.type == ObligationType.CONTINGENT_REBATE and o.rate_bp is not None:
            rebate = o.rate_bp
    return Setting(terms, price, discount, face, rebate)


class _Verifier:
    """`build` then `evaluate`, memoised per setting within one call, counting the evaluations it actually runs."""

    def __init__(self, books: Books, mandate: Mandate, key: str, day: int, commitments: Sequence[Commitment],
                 ctx: Context | EarlyPayContext, ranges: Ranges) -> None:
        self.books, self.mandate, self.key, self.day, self.commitments = books, mandate, key, day, commitments
        self.ctx, self.ranges = ctx, ranges
        self.state: FinancialState = books.state
        self.memo: dict[Setting, Probe] = {}
        self.cur = ctx.recurring.terms_days if isinstance(ctx, Context) else TERMS_MIN

    @property
    def evaluations(self) -> int:
        return len(self.memo)

    def norm(self, s: Setting) -> Setting:
        if s.discount == 0 or s.face == self.ctx.receivable.face_fen:
            return s._replace(face=None)
        return s

    def probe(self, setting: Setting) -> Probe:
        s = self.norm(setting)
        hit = self.memo.get(s)
        if hit is not None:
            return hit
        r = self.ranges
        if (s.terms not in r.terms and (r.terms or s.terms != self.cur)) or s.price not in r.price \
                or s.discount not in r.discount or s.rebate not in r.rebate:
            raise ValueError(f"{s} is outside the levers' ranges")
        offer, _ = build(WhatIfParams(terms_days=s.terms, discount_bp=s.discount, rebate_bp=s.rebate,
                                      price_adjustment_bp=s.price, settle_face_fen=s.face), self.ctx, self.day)
        v = evaluate(offer, self.state, self.mandate, trusted_owner_key_hex=self.key, day=self.day,
                     commitments=self.commitments, plans="committed").verdict
        p = self._read(s, v)
        self.memo[s] = p
        return p

    def _read(self, s: Setting, v: Verdict) -> Probe:
        reserve = next((x for x in v.violations if x.code == ViolationCode.RESERVE_BREACH), None)
        curable_reserve = reserve is not None and bool(reserve.curable)
        binding = tuple(dict.fromkeys(x.code.value for x in v.violations
                                      if not (x.code == ViolationCode.RESERVE_BREACH and x.curable)))
        liquidity_only = v.outcome != Outcome.NO_VERDICT and all(
            x.code in CAP_CODES or (x.code == ViolationCode.RESERVE_BREACH and x.curable) for x in v.violations)
        passes = v.outcome in PASSING and not any(
            x.code == ViolationCode.RESERVE_BREACH and not x.curable for x in v.violations)
        flags = reserve.inputs if reserve is not None else {}
        cur = self.cur
        return Probe(
            setting=s, outcome=v.outcome.value, tier=v.required_tier.value, passes=passes, liquidity_only=liquidity_only,
            codes=tuple(dict.fromkeys(x.code.value for x in v.violations)), binding=binding,
            forward_total_fen=v.forward_concession_total_fen,
            reserve_day=reserve.day if reserve else None, reserve_curable=reserve.curable if reserve else None,
            cure_cost_fen=reserve.cure_cost_fen if reserve is not None and curable_reserve else None,
            cure_needs_owner="cure_needs_owner_approval" in flags, cure_cannot_run_today="cure_executable_now" in flags,
            counters=tuple(self.norm(_setting_of(c, cur, self.ctx.receivable.face_fen)) for c in v.counters),
            counter_costs_fen=tuple(c.supplier_cost_fen for c in v.counters),
            plan_cost_fen=v.plan.total_cost_fen if v.plan is not None else None,
            recheck=infeasibility(v, self.state) if v.outcome in PASSING else None)

    def ok(self, s: Setting) -> bool:
        return self.probe(s).passes

    def rebate_hint(self, at_zero: Probe) -> int | None:
        """Where the largest rebate probably lies, read from the verifier's own forward-concession totals: the room the
        cap leaves above `at_zero` (the package at no rebate) over the cost of one 5 bp step of rebate (the difference
        of two standalone probes, the status quo and the top of the range). Only a hint: the search keeps it when the
        verifier agrees at it and at the two steps past it, and runs without it otherwise."""
        top = self.ranges.rebate[-1]
        if top == 0:
            return None
        base, full = self.probe(Setting(self.cur)), self.probe(Setting(self.cur, rebate=top))
        steps = len(self.ranges.rebate) - 1
        per_step, rest = divmod(full.forward_total_fen - base.forward_total_fen, steps)
        room = self.mandate.max_aggregate_forward_concession_fen - at_zero.forward_total_fen
        if per_step <= 0 or rest or room < 0:
            return None
        return self.ranges.rebate[min(room // per_step, steps)]

    def approved(self, s: Setting) -> bool:
        return self.probe(s).approved

    def compensating_price(self, terms: int) -> tuple[int | None, int | None]:
        """(per-invoice funding cost of the extension, the smallest 5 bp price step that covers it): the Option B rule of
        `app.verifier.counters`, read from `value_concessions` and `smallest_step_covering`. None at or below the terms
        in force and when the buyer has no recurring invoice."""
        ctx = self.ctx
        if not isinstance(ctx, Context) or terms <= ctx.recurring.terms_days:
            return None, None
        offer, _ = build(WhatIfParams(terms_days=terms, discount_bp=0, rebate_bp=0), ctx, self.day)
        bound, _notes = bind(offer, self.state, None)
        try:
            ratio, _fid = marginal_cost(self.state, self.mandate)
        except NoPermanentSourceError:
            return None, None
        values = value_concessions(bound, self.state, ratio, "committed marginal source",
                                   self.mandate.forward_concession_horizon_days)
        per_invoice = next((x.per_invoice_fen for x in values if x.per_invoice_fen), None)
        if per_invoice is None:
            return None, None
        return per_invoice, smallest_step_covering(per_invoice, ctx.recurring.face_fen)


# ---------------------------------------------------------------- the facts (language-neutral)


@dataclass(frozen=True)
class Maximum:
    """The largest value of one lever that passes, and the verifier's answer at it and at the next step."""

    lever: str  # the oracle's label
    key: str
    unit: Literal["days", "bp"]
    value: int | None
    confirmed: bool
    scanned: bool
    at_max: Probe | None
    beyond: Probe | None
    wall: str | None  # wall key (see `wall_of`); None when the lever has no wall inside its range
    face_fen: int | None = None  # early pay: the face
    rule_price_bp: int | None = None  # terms with price: the Option B rule price at `value`
    unavailable: bool = False  # the buyer has no recurring invoice to extend


@dataclass(frozen=True)
class ZoneRow:
    terms_days: int
    min_price_bp: int | None
    confirmed: bool
    rule_price_bp: int | None
    cost_per_invoice_fen: int | None
    at_price: Probe


@dataclass(frozen=True)
class Cell:
    probe: Probe
    counter_match: bool


@dataclass(frozen=True)
class EnvelopeFacts:
    buyer_id: str
    buyer_name: str
    day: int
    source_state_version: int
    refused: bool
    mandate: Mandate | None
    current_terms: int
    receivable_face_fen: int
    has_terms_lever: bool
    maxima: tuple[Maximum, ...]
    zone: tuple[ZoneRow, ...]
    cells: tuple[Cell, ...]
    counter_costs_fen: dict[Setting, int]  # the verifier's own counters to the asks, and what each costs the supplier
    status_quo: Probe | None
    next_terms: int | None  # the first terms step above the longest approved one
    next_terms_passes_with_early_pay: bool
    evaluations: int
    seconds: float
    past_due: tuple[tuple[int, int], ...] = ()  # (outstanding fen, days late) of this buyer's invoices past due today


def wall_of(p: Probe | None, *, ignore_caps: bool = False) -> str | None:
    """The wall a failing step runs into, from its binding codes (map decision 2)."""
    if p is None:
        return None
    b = set(p.binding)
    if not ignore_caps:
        if ViolationCode.PER_BUYER_CAP_EXCEEDED.value in b:
            return "buyer cap"
        if ViolationCode.AGG_CONCESSION_EXCEEDED.value in b:
            return "forward budget"
    if ViolationCode.RESERVE_BREACH.value in b:
        return "liquidity"
    if ViolationCode.DISCOUNT_ABOVE_BREAK_EVEN.value in b:
        return "break-even"
    if ViolationCode.EARLY_PAY_DEARER_THAN_PLAN.value in b:
        return "plan comparison"
    if b & {ViolationCode.IMMEDIATE_DISCOUNT_EXCEEDED.value, ViolationCode.MAX_APR_EXCEEDED.value}:
        return "the mandate's price ceiling"
    if ignore_caps and b:
        return "forward budget" if ViolationCode.AGG_CONCESSION_EXCEEDED.value in b else "buyer cap"
    return None


def _maximum(v: _Verifier, lever: str, key: str, unit: Literal["days", "bp"], found: Found, make: Callable[[int], Setting],
             values: Sequence[int], *, ignore_caps: bool = False, face_fen: int | None = None) -> Maximum:
    val = found.value
    nxt = next((x for x in values if val is not None and x > val), None)
    at = v.probe(make(val)) if val is not None else None
    beyond = v.probe(make(nxt)) if nxt is not None else None
    return Maximum(lever, key, unit, val, found.confirmed, found.scanned, at, beyond, wall_of(beyond, ignore_caps=ignore_caps),
                   face_fen=face_fen)


def _unavailable(lever: str, key: str, unit: Literal["days", "bp"]) -> Maximum:
    return Maximum(lever, key, unit, None, True, False, None, None, None, unavailable=True)


def _passes(v: _Verifier, make: Callable[[int], Setting]) -> Callable[[int], bool]:
    return lambda x: v.ok(make(x))


def _levers(v: _Verifier) -> tuple[list[Maximum], list[tuple[Setting, int | None]]]:
    """The six maxima, in the oracle's order, and the early-pay variants found (Option A's face and rate, ...)."""
    r, cur, ctx = v.ranges, v.cur, v.ctx
    has_terms = bool(r.terms)
    top_discount = r.discount[-1]
    out: list[Maximum] = []
    up = [x for x in r.terms if x >= cur]
    pmax = r.price[-1]

    if has_terms:
        f = last_true(up, lambda x: v.ok(Setting(x)), gallop=True)
        out.append(_maximum(v, TERMS_ALONE, "terms_alone", "days", f, lambda x: Setting(x), up))
        g = last_true(up, lambda x: v.probe(Setting(x)).liquidity_only, gallop=True)
        out.append(_maximum(v, TERMS_BUDGET_IGNORED, "terms_budget_ignored", "days", g, lambda x: Setting(x), up,
                            ignore_caps=True))
        # the longest terms that any price in range makes pass (the price is monotone: the top of the range is the best
        # chance), then the smallest price that does it
        h = last_true(up, lambda x: v.approved(Setting(x, price=pmax)), gallop=True)
        t_best = h.value
        hp = Found(None, True)
        if t_best is not None:
            hp = first_true(r.price, lambda p: v.approved(Setting(t_best, price=p)))
        rule = v.compensating_price(t_best)[1] if t_best is not None else None
        nxt = next((x for x in up if t_best is not None and x > t_best), None)
        out.append(Maximum(
            TERMS_WITH_PRICE, "terms_with_price", "days", t_best, h.confirmed and hp.confirmed, h.scanned or hp.scanned,
            v.probe(Setting(t_best, price=hp.value if hp.value is not None else pmax)) if t_best is not None else None,
            v.probe(Setting(nxt, price=pmax)) if nxt is not None else None,
            wall_of(v.probe(Setting(nxt, price=pmax))) if nxt is not None else None, rule_price_bp=rule))
    else:
        out += [_unavailable(TERMS_ALONE, "terms_alone", "days"),
                _unavailable(TERMS_BUDGET_IGNORED, "terms_budget_ignored", "days"),
                _unavailable(TERMS_WITH_PRICE, "terms_with_price", "days")]

    # early pay: the whole invoice, and the face of the verifier's own early-pay counter (asked for the top of the range,
    # so that the counter's rate is the break-even step and not the buyer's own)
    faces: list[int] = []
    whole = last_true(r.discount, lambda d: v.ok(Setting(cur, discount=d)))
    if (whole.value or 0) < top_discount:
        for s in v.probe(Setting(cur, discount=top_discount)).counters:
            if s.discount and s.face is not None and s.face not in faces:
                faces.append(s.face)

    def early_at(face: int | None) -> Callable[[int], Setting]:
        return lambda d: Setting(cur, discount=d, face=face)

    early: list[tuple[int | None, Found]] = [(None, whole)]
    for fc in faces:
        rate = next((c.discount for c in v.probe(Setting(cur, discount=top_discount)).counters if c.face == fc), None)
        early.append((fc, last_true(r.discount, _passes(v, early_at(fc)), hint=rate)))
    for face, found in early:
        shown = face if face is not None else ctx.receivable.face_fen
        out.append(_maximum(v, early_pay_lever(shown), "early_pay_whole" if face is None else "early_pay_counter", "bp",
                            found, early_at(face), r.discount, face_fen=shown))

    if has_terms:
        rb = last_true(r.rebate, lambda x: v.ok(Setting(cur, rebate=x)), hint=v.rebate_hint(v.probe(Setting(cur))))
        out.append(_maximum(v, REBATE, "rebate", "bp", rb, lambda x: Setting(cur, rebate=x), r.rebate))
    else:
        out.append(_unavailable(REBATE, "rebate", "bp"))
    return out, [(Setting(cur, discount=f.value or 0, face=fc), fc) for fc, f in early if f.value and fc is not None]


def _price_at(v: _Verifier, terms: int) -> Callable[[int], bool]:
    return lambda p: v.ok(Setting(terms, price=p))


def _zone(v: _Verifier) -> list[ZoneRow]:
    out: list[ZoneRow] = []
    for terms in v.ranges.terms:
        fp = first_true(v.ranges.price, _price_at(v, terms))
        at = v.probe(Setting(terms, price=fp.value if fp.value is not None else v.ranges.price[-1]))
        per_invoice, rule = v.compensating_price(terms)
        out.append(ZoneRow(terms, fp.value, fp.confirmed, rule, per_invoice, at))
    return out


def _whole_at(v: _Verifier, terms: int, price: int) -> Callable[[int], bool]:
    return lambda d: v.ok(Setting(terms, price=price, discount=d))


def _cell(v: _Verifier, base: Setting, keep_failures: bool, price_hint: int | None = None) -> Probe | None:
    """The package of one terms value and early-pay variant: the smallest price that passes, then the largest rebate
    that still passes at that price (one whole verifier evaluation). A failing cell shows the verifier's answer at the
    largest price, and only when `keep_failures`."""
    r = v.ranges
    fp = first_true(r.price, lambda p: v.ok(base._replace(price=p)), hint=price_hint, hint_steps=1)
    if fp.value is None:
        return v.probe(base._replace(price=r.price[-1], rebate=0)) if keep_failures else None
    priced = base._replace(price=fp.value)
    fr = last_true(r.rebate, lambda x: v.ok(priced._replace(rebate=x)), hint=v.rebate_hint(v.probe(priced)),
                   hint_steps=1 if price_hint is not None else 2)
    return v.probe(priced._replace(rebate=fr.value or 0))


def _grid(v: _Verifier, early_counter: list[tuple[Setting, int | None]], whole_standalone: int | None,
          full_grid: bool) -> list[Probe]:
    """The package grid: per terms value (the terms in force upward) x early-pay variant {none; Option A's face at its
    rate; the whole face at the largest rate that passes inside the package}. With `full_grid` every terms value up to
    the top of the range, the whole face at its standalone maximum as well (the oracle's variant) and the cells where no
    price passes are kept as failing rows; without it the terms in force, +5 and +10 and approved packages only."""
    r, cur = v.ranges, v.cur
    up = [x for x in r.terms if x >= cur] or [cur]
    terms = up if full_grid else up[:MVP_TERMS_STEPS]
    out: list[Probe] = []
    seen: set[Setting] = set()
    pmax = r.price[-1]
    for tm in terms:
        bases = [Setting(tm)]
        bases += [Setting(tm, discount=s.discount, face=s.face) for s, _ in early_counter]
        if whole_standalone:
            d = descend(r.discount, _whole_at(v, tm, pmax), whole_standalone)
            if d.value:
                bases.append(Setting(tm, discount=d.value))
            if full_grid:
                bases.append(Setting(tm, discount=whole_standalone))
        hint: int | None = None
        for base in dict.fromkeys(v.norm(b) for b in bases):
            p = _cell(v, base, full_grid, hint)
            if p is None:
                continue
            if hint is None and p.passes:
                hint = p.setting.price
            if p.setting not in seen:
                seen.add(p.setting)
                out.append(p)
    return out


def envelope_facts(books: Books, mandate: Mandate, *, store: LedgerStore | None = None, day: int, buyer_id: str,
                   trusted_owner_key_hex: str, commitments: Sequence[Commitment] = (), zone: bool = False,
                   full_grid: bool = False) -> EnvelopeFacts:
    """Run the sweep. `store` is accepted for the kernel's calling convention (the alerts engine reads it) and not read."""
    started = time.perf_counter()
    state = books.state
    name = party_name(state, buyer_id)
    version = state.state_version
    try:
        ctx = open_context(state, day, buyer_id)
    except WhatIfParamError:
        return EnvelopeFacts(buyer_id, name, day, version, True, None, 0, 0, False, (), (), (), {}, None, None, False, 0,
                             time.perf_counter() - started)
    today = max(day, state.as_of_day)
    late = past_due_invoices(books, today, today + mandate.horizon_days)
    past_due = tuple(sorted((a.amount_fen or 0, today - int(a.inputs["due_day"])) for a in late
                            if a.inputs.get("counterparty_id") == buyer_id))
    ranges = ranges_for(ctx, mandate)
    v = _Verifier(books, mandate, trusted_owner_key_hex, day, commitments, ctx, ranges)
    cur = v.cur
    maxima, early_counter = _levers(v)
    status_quo = v.probe(Setting(cur))
    zone_rows = _zone(v) if zone else []
    whole = next((m.value for m in maxima if m.key == "early_pay_whole"), None)
    cells = _grid(v, early_counter, whole, full_grid)

    # the verifier's own counters to the asks one step past the liquidity wall (terms), the top of the early-pay range
    # and one step past the rebate maximum: the nearest asks the sweep has already put to the verifier
    asks: list[Setting] = [Setting(cur, discount=ranges.discount[-1])]
    for m in maxima:
        if m.key in ("terms_budget_ignored", "rebate") and m.beyond is not None:
            asks.append(m.beyond.setting)
    counter_costs: dict[Setting, int] = {}
    for a in asks:
        p = v.probe(a)
        for c, cost in zip(p.counters, p.counter_costs_fen, strict=True):
            counter_costs.setdefault(c, cost)
    counters = set(counter_costs)
    seen = {c.setting for c in cells}
    for s in sorted(counters):
        if s not in seen and v.probe(s).approved:
            cells.append(v.probe(s))
    cell_tuple = tuple(Cell(p, p.setting in counters) for p in cells)

    # the first terms step above the longest approved one, and whether an early payment lets it through
    best = next((m for m in maxima if m.key == "terms_with_price"), None)
    next_terms: int | None = None
    with_early = False
    if best is not None and best.value is not None:
        next_terms = next((x for x in ranges.terms if x > best.value), None)
    if next_terms is not None and early_counter:
        s0 = early_counter[0][0]
        with_early = v.approved(Setting(next_terms, price=ranges.price[-1], discount=s0.discount, face=s0.face))
    return EnvelopeFacts(
        buyer_id, name, day, version, False, mandate, cur, ctx.receivable.face_fen, bool(ranges.terms), tuple(maxima),
        tuple(zone_rows), cell_tuple, counter_costs, status_quo, next_terms, with_early, v.evaluations, time.perf_counter() - started,
        past_due)


# ---------------------------------------------------------------- the answer (words)


class ReserveBreachView(Contract):
    day: int
    when: str  # a distance from today
    curable: bool
    cure_cost_fen: int | None


class EnvelopePackage(Contract):
    """One package and the verifier's answer to it. `approved` is passes and the counter re-check finds nothing."""

    package: CandidatePackage
    outcome: str
    tier: str
    passes: bool
    approved: bool
    codes: list[str]
    binding_codes: list[str]
    forward_budget_used_fen: int
    reserve_breach: ReserveBreachView | None
    flags: list[str]  # in words: "needs your approval", "its funding cannot run today"
    counter_match: bool  # the verifier's own counters to the largest asks include this package
    plan_cost_fen: int | None
    summary: str  # the package on one line, its terms joined by " · ": "55-day terms · price up 0.25% · rebate 0.60%"


class EnvelopeLever(Contract):
    lever: str  # the oracle's label, stable
    key: str
    label: str
    unit: Literal["days", "bp"]
    maximum: int | None
    confirmed: bool
    scanned: bool
    wall: str | None
    wall_text: str | None
    face_fen: int | None
    rule_price_bp: int | None  # terms with price: the counter FLOW would send (Option B's rule), beside the smallest
    unavailable: str | None  # "no recurring invoice to extend"
    maximum_display: str  # the maximum in words: "45 days", "55 days, price up 0.30%", "0.70% on ¥420,000.00", "1.25%"
    wall_words: str | None  # what stops the next step, in the owner's words; None when nothing inside the range does
    next_step_sentence: str  # "50 days: over your limits; its funding cannot run today"
    at_maximum: EnvelopePackage | None
    next_step: EnvelopePackage | None


class ZoneEntry(Contract):
    terms_days: int
    terms_words: str  # "45 days"
    min_price_bp: int | None  # the smallest price that passes alone
    rule_price_bp: int | None  # Option B's rule price beside it
    cost_per_invoice_fen: int | None
    passes_within_range: bool
    neighbours_confirmed: bool
    at_that_price: EnvelopePackage
    lowest_price_words: str  # "no price rise needed", the percentage, or "none works"


class EnvelopeAnswer(Contract):
    buyer_id: str
    buyer_name: str
    primary: str
    reason: str
    money: str
    packages: list[EnvelopePackage]
    levers: list[EnvelopeLever]
    zone: list[ZoneEntry] = Field(default_factory=list)
    refused: str | None = None
    source_state_version: int
    hypothetical: Literal[True] = True
    evaluations: int
    computed_in_seconds: float


_WALL_TEXT = {
    "forward budget": ("your budget for what you give buyers", "您给买家让步的预算"),
    "buyer cap": ("your limit for this buyer", "您对该买家的上限"),
    "liquidity": ("your cash floor", "您的现金底线"),
    "break-even": ("the break-even for paying early", "提前付款的盈亏平衡点"),
    "plan comparison": ("the cheaper funding you already have", "您已有的更便宜的资金安排"),
    "the mandate's price ceiling": ("your price ceiling", "您的价格上限"),
}
_WALL_WORDS = {
    "forward budget": ("your budget for what you give buyers", "您给买家让利的预算"),
    "buyer cap": ("the cap for this buyer", "该买家的上限"),
    "liquidity": ("your cash floor", "您的现金底线"),
    "break-even": ("the break-even for paying early", "提前付款的盈亏平衡点"),
    "plan comparison": ("the cheaper funding you already have", "您已有的更便宜的资金安排"),
    "the mandate's price ceiling": ("the price ceiling in your mandate", "您授权中的价格上限"),
}
_LEVER_LABEL = {
    "terms_alone": ("Longest payment terms on their own", "仅延长账期时的最长账期"),
    "terms_budget_ignored": ("Longest payment terms if the budget is ignored", "不计预算时的最长账期"),
    "terms_with_price": ("Longest payment terms with a price rise", "加价后的最长账期"),
    "rebate": ("Rebate on the expected order", "预期订单的返利"),
}


def _lever_label(m: Maximum, lang: str) -> str:
    if m.key in _LEVER_LABEL:
        return t(lang, *_LEVER_LABEL[m.key])
    face = fmt_yuan(m.face_fen or 0)
    return t(lang, f"Early payment on {face}", f"{face} 的提前付款")


def _flags(p: Probe, lang: str) -> list[str]:
    out: list[str] = []
    if p.outcome == Outcome.NEEDS_OWNER_APPROVAL.value or p.cure_needs_owner:
        out.append(t(lang, "needs your approval", "需要您批准"))
    if p.cure_cannot_run_today:
        out.append(t(lang, "its funding cannot run today", "其资金安排今天无法执行"))
    return out


def _pct(value_bp: int) -> str:
    return fmt_pct(bp(value_bp))


def _days(n: int, lang: str) -> str:
    return t(lang, f"{n} {'day' if n == 1 else 'days'}", f"{n} 天")


def _summary(s: Setting, lang: str) -> str:
    """One package on a line, from the server's own displays: terms first, then what is added to them."""
    parts = [t(lang, f"{s.terms}-day terms", f"{s.terms} 天账期")]
    if s.price > 0:
        parts.append(t(lang, f"price up {_pct(s.price)}", f"加价 {_pct(s.price)}"))
    if s.discount > 0:
        rate = _pct(s.discount)
        if s.face is not None:
            parts.append(t(lang, f"early payment {rate} on {fmt_yuan(s.face)}", f"提前付款 {rate}，金额 {fmt_yuan(s.face)}"))
        else:
            parts.append(t(lang, f"early payment {rate}", f"提前付款 {rate}"))
    if s.rebate > 0:
        parts.append(t(lang, f"rebate {_pct(s.rebate)}", f"返利 {_pct(s.rebate)}"))
    return " · ".join(parts)


def _lever_value(m: Maximum, p: Probe | None, lang: str, *, rule_price: bool = False) -> str | None:
    """A lever's value at one probe, in words ("55 days, price up 0.30%", "0.70% on ¥420,000.00", "1.25%")."""
    if p is None:
        return None
    s = p.setting
    if m.unit == "days":
        days = _days(s.terms, lang)
        if m.key != "terms_with_price":
            return days
        price = _pct(m.rule_price_bp if rule_price and m.rule_price_bp is not None else s.price)
        return t(lang, f"{days}, price up {price}", f"{days}，加价 {price}")
    if m.key.startswith("early_pay"):
        rate, face = _pct(s.discount), fmt_yuan(m.face_fen or 0)
        return t(lang, f"{rate} on {face}", f"{rate}，金额 {face}")
    return _pct(s.rebate) if m.key == "rebate" else None


def _maximum_words(m: Maximum, lang: str) -> str:
    if m.unavailable:
        return t(lang, "no recurring invoice to extend", "没有可延长的定期发票")
    return _lever_value(m, m.at_max, lang, rule_price=True) or t(lang, "none passes", "没有可通过的值")


def _next_step_words(m: Maximum, lang: str) -> str:
    value = _lever_value(m, m.beyond, lang)
    if m.beyond is None or value is None:
        return t(lang, "no further step", "没有更进一步的方案")
    flags = _flags(m.beyond, lang)
    verdict = t(lang, "within your limits", "在您的底线内") if m.beyond.approved else t(lang, "over your limits", "超出您的底线")
    text = f"{value}{t(lang, ': ', '：')}{verdict}"
    if flags:
        text += t(lang, "; ", "；") + t(lang, ", ", "，").join(flags)
    return text


def _wall_words(m: Maximum, lang: str) -> str | None:
    if m.unavailable:
        return t(lang, "no recurring invoice to extend", "没有可延长的定期发票")
    return t(lang, *_WALL_WORDS[m.wall]) if m.wall in _WALL_WORDS else None


def _lowest_price_words(z: ZoneRow, lang: str) -> str:
    if z.min_price_bp is None:
        return t(lang, "none works", "没有可行的价格")
    if z.min_price_bp == 0:
        return t(lang, "no price rise needed", "无需加价")
    return _pct(z.min_price_bp)


def _package(facts: EnvelopeFacts, p: Probe, lang: str, match: bool = False) -> EnvelopePackage:
    s = p.setting
    breach = None
    if p.reserve_day is not None:
        breach = ReserveBreachView(day=p.reserve_day, when=when_text(p.reserve_day, facts.day, lang),
                                   curable=bool(p.reserve_curable), cure_cost_fen=p.cure_cost_fen)
    return EnvelopePackage(
        package=CandidatePackage(buyer_id=facts.buyer_id, terms_days=s.terms, price_bp=s.price, early_pay_bp=s.discount,
                                 early_pay_face_fen=s.face, rebate_bp=s.rebate),
        outcome=p.outcome, tier=p.tier, passes=p.passes, approved=p.approved, codes=list(p.codes),
        binding_codes=list(p.binding), forward_budget_used_fen=p.forward_total_fen, reserve_breach=breach,
        flags=_flags(p, lang), counter_match=match, plan_cost_fen=p.plan_cost_fen, summary=_summary(s, lang))


def _lever(facts: EnvelopeFacts, m: Maximum, lang: str) -> EnvelopeLever:
    wall_text = t(lang, *_WALL_TEXT[m.wall]) if m.wall in _WALL_TEXT else None
    return EnvelopeLever(
        lever=m.lever, key=m.key, label=_lever_label(m, lang), unit=m.unit, maximum=m.value, confirmed=m.confirmed,
        scanned=m.scanned, wall=m.wall, wall_text=wall_text, face_fen=m.face_fen, rule_price_bp=m.rule_price_bp,
        unavailable=t(lang, "no recurring invoice to extend", "没有可延长的定期发票") if m.unavailable else None,
        maximum_display=_maximum_words(m, lang), wall_words=_wall_words(m, lang), next_step_sentence=_next_step_words(m, lang),
        at_maximum=_package(facts, m.at_max, lang) if m.at_max is not None else None,
        next_step=_package(facts, m.beyond, lang) if m.beyond is not None else None)


def _lever_of(facts: EnvelopeFacts, key: str) -> Maximum | None:
    return next((m for m in facts.maxima if m.key == key), None)


def _primary(facts: EnvelopeFacts, lang: str) -> str:
    cur = facts.current_terms
    pieces: list[str] = []
    terms = _lever_of(facts, "terms_with_price")
    longest = terms.value if terms is not None and terms.value is not None else cur
    if terms is not None and terms.value is not None and longest > cur:
        # the counter FLOW would send: Option B's rule price when it passes, else the smallest price that does
        price = terms.at_max.setting.price if terms.at_max is not None else 0
        if terms.rule_price_bp is not None and any(
                c.probe.setting == Setting(longest, price=terms.rule_price_bp) for c in facts.cells):
            price = terms.rule_price_bp
        pieces.append(t(lang, f"up to {longest}-day terms if the price rises {fmt_pct(bp(price))}",
                        f"账期最长 {longest} 天（价格上调 {fmt_pct(bp(price))}）"))
    early = next((m for m in facts.maxima if m.key == "early_pay_counter" and m.value), None) or \
        next((m for m in facts.maxima if m.key == "early_pay_whole" and m.value), None)
    if early is not None and early.value:
        pieces.append(t(lang, f"early payment at up to {fmt_pct(bp(early.value))} on {fmt_yuan(early.face_fen or 0)}",
                        f"提前付款最高 {fmt_pct(bp(early.value))}（金额 {fmt_yuan(early.face_fen or 0)}）"))
    first = t(lang, ", or ", "，或") .join(pieces)
    parts = [first] if first else []
    rebate = _lever_of(facts, "rebate")
    if rebate is not None and rebate.value:
        parts.append(t(lang, f"a rebate up to {fmt_pct(bp(rebate.value))}", f"返利最高 {fmt_pct(bp(rebate.value))}"))
    if facts.has_terms_lever:
        if facts.next_terms is not None:
            n = facts.next_terms
            parts.append(t(lang, f"not {n} days without an early payment", f"不提前付款则不能做到 {n} 天")
                         if facts.next_terms_passes_with_early_pay else t(lang, f"not {n} days", f"不能做到 {n} 天"))
        elif longest == cur:
            parts.append(t(lang, "no longer payment terms", "不能延长账期"))
    if not parts:
        return t(lang, "Nothing beyond today's terms passes FLOW's checks.", "今天的条件之外，没有任何方案能通过 FLOW 的检查。")
    text = t(lang, "You can live with: ", "您能接受的范围：") + t(lang, "; ", "；").join(parts)
    return text + t(lang, ".", "。")


def _past_due_clause(facts: EnvelopeFacts, lang: str) -> str | None:
    """Said only when the standing position itself needs the owner and a past-due invoice from this buyer is why."""
    sq = facts.status_quo
    if not facts.past_due or sq is None or sq.outcome != Outcome.NEEDS_OWNER_APPROVAL.value or sq.codes:
        return None
    who, owed = facts.buyer_name, fmt_yuan(sum(o for o, _ in facts.past_due))
    n = len(facts.past_due)
    if n > 1:
        return t(lang, f"{n} invoices from {who} are past due, so any deal with {who} needs your approval",
                 f"{who} 有 {n} 张发票已逾期，因此与其做任何交易都需要您批准")
    late = facts.past_due[0][1]
    return t(lang, f"the {owed} still owed by {who} is {late} {'day' if late == 1 else 'days'} past due, so any deal with "
                   f"{who} needs your approval",
             f"{who} 欠款 {owed} 已逾期 {late} 天，因此与其做任何交易都需要您批准")


def _reason(facts: EnvelopeFacts, lang: str) -> str:
    clauses: list[str] = []
    overdue = _past_due_clause(facts, lang)
    if overdue is not None:
        clauses.append(overdue)
    if not facts.has_terms_lever:
        clauses.append(t(lang, "there is no recurring invoice to extend, so only an early payment can be priced",
                         "没有可延长的定期发票，所以只能为提前付款估值"))
        return _sentence(clauses, lang)
    liquid = _lever_of(facts, "terms_budget_ignored")
    if liquid is not None and liquid.beyond is not None:
        b, n = liquid.beyond, liquid.beyond.setting.terms
        if liquid.wall == "liquidity" and b.reserve_day is not None:
            when = when_text(b.reserve_day, facts.day, lang)
            clauses.append(t(lang, f"{n} days leaves a shortfall {when} that no fix covers",
                             f"账期 {n} 天在 {when}会出现缺口，且无法补上"))
        elif liquid.wall is not None:
            wall = t(lang, *_WALL_TEXT[liquid.wall]) if liquid.wall in _WALL_TEXT else ""
            clauses.append(t(lang, f"{n} days runs into {wall}", f"账期 {n} 天会碰到{wall}"))
    alone = _lever_of(facts, "terms_alone")
    mandate = facts.mandate
    if alone is not None and alone.value is not None and mandate is not None and alone.wall in ("forward budget", "buyer cap"):
        if alone.wall == "buyer cap":
            cap = mandate.per_buyer_caps_fen.get(facts.buyer_id, mandate.max_aggregate_forward_concession_fen)
            what = t(lang, f"the {fmt_yuan(cap)} limit for {facts.buyer_name}", f"对{facts.buyer_name}的 {fmt_yuan(cap)} 上限")
        else:
            cap = mandate.max_aggregate_forward_concession_fen
            what = t(lang, f"the {fmt_yuan(cap)} budget", f"{fmt_yuan(cap)} 的预算")
        if alone.value == facts.current_terms:
            clauses.append(t(lang, f"{what} buys no terms without a price rise", f"{what}无法在不加价的情况下延长账期"))
        else:
            clauses.append(t(lang, f"{what} buys terms only up to {alone.value} days without a price rise",
                             f"{what}在不加价时最多只能延长到 {alone.value} 天"))
    if not clauses:
        return t(lang, "No payment-terms step fails inside the range FLOW checks.", "FLOW 检查的范围内，没有哪一档账期被拒绝。")
    return _sentence(clauses, lang)


def _sentence(clauses: list[str], lang: str) -> str:
    text = t(lang, "; ", "；").join(clauses)
    if lang != "zh":
        text = text[0].upper() + text[1:]
    return text + t(lang, ".", "。")


def _money(facts: EnvelopeFacts, lang: str) -> str:
    standing = facts.status_quo.plan_cost_fen if facts.status_quo is not None else None
    if standing is None:
        return ""
    cur = facts.current_terms
    approved = {c.probe.setting for c in facts.cells if c.counter_match and c.probe.approved}
    given = [(c, fen) for c, fen in facts.counter_costs_fen.items() if c in approved]
    option_a = next((fen for c, fen in given if c.discount and c.terms == cur and not c.price), None)
    option_b = next((fen for c, fen in given if c.terms > cur and c.price and not c.discount), None)
    costs: list[str] = []
    if option_b is not None:
        costs.append(t(lang, f"{fmt_yuan(option_b)} with the price rise", f"加价方案 {fmt_yuan(option_b)}"))
    if option_a is not None:
        costs.append(t(lang, f"{fmt_yuan(option_a)} with the early payment", f"提前付款方案 {fmt_yuan(option_a)}"))
    now = t(lang, f"without a deal your current funding plan costs {fmt_yuan(standing)}", f"不做交易时，现行资金安排的成本为 {fmt_yuan(standing)}")
    if not costs:
        return (now[0].upper() + now[1:] if lang != "zh" else now) + t(lang, ".", "。")
    lead = t(lang, "Cost to you ", "您的成本：") + t(lang, ", or ", "，或").join(costs)
    return lead + t(lang, "; ", "；") + now + t(lang, ".", "。")


def _refusal(name: str, lang: str) -> str:
    return t(lang, f"FLOW has no terms or payment lever to value for {name} yet: no recurring invoice and no open invoice.",
             f"FLOW 目前没有可为{name}估值的账期或付款杠杆：没有定期发票，也没有未结发票。")


def envelope_answer(facts: EnvelopeFacts, lang: str = "en") -> EnvelopeAnswer:
    """The sweep's facts in words (`en` or `zh`)."""
    meta: dict[str, object] = {"buyer_id": facts.buyer_id, "buyer_name": facts.buyer_name,
                               "source_state_version": facts.source_state_version, "evaluations": facts.evaluations,
                               "computed_in_seconds": round(facts.seconds, 3)}
    if facts.refused:
        return EnvelopeAnswer.model_validate({**meta, "primary": "", "reason": "", "money": "", "packages": [],
                                              "levers": [], "zone": [], "refused": _refusal(facts.buyer_name, lang)})
    zone = [ZoneEntry(terms_days=z.terms_days, terms_words=_days(z.terms_days, lang), min_price_bp=z.min_price_bp, rule_price_bp=z.rule_price_bp,
                      cost_per_invoice_fen=z.cost_per_invoice_fen, passes_within_range=z.min_price_bp is not None,
                      neighbours_confirmed=z.confirmed, at_that_price=_package(facts, z.at_price, lang),
                      lowest_price_words=_lowest_price_words(z, lang))
            for z in facts.zone]
    return EnvelopeAnswer(
        buyer_id=facts.buyer_id, buyer_name=facts.buyer_name, primary=_primary(facts, lang), reason=_reason(facts, lang),
        money=_money(facts, lang), packages=[_package(facts, c.probe, lang, c.counter_match) for c in facts.cells],
        levers=[_lever(facts, m, lang) for m in facts.maxima], zone=zone, refused=None,
        source_state_version=facts.source_state_version, evaluations=facts.evaluations,
        computed_in_seconds=round(facts.seconds, 3))


def probe_packages(books: Books, mandate: Mandate, packages: Sequence[CandidatePackage], *, day: int,
                   trusted_owner_key_hex: str, commitments: Sequence[Commitment] = (), lang: str = "en") -> list[EnvelopePackage]:
    """Put these packages to the verifier whole, as the sweep does (one buyer's, memoised within the call). A package
    outside the levers' ranges, or for a buyer with no lever, raises `ValueError` (`WhatIfParamError`)."""
    out: list[EnvelopePackage] = []
    verifiers: dict[str, _Verifier] = {}
    for pkg in packages:
        v = verifiers.get(pkg.buyer_id)
        if v is None:
            ctx = open_context(books.state, day, pkg.buyer_id)
            v = verifiers[pkg.buyer_id] = _Verifier(books, mandate, trusted_owner_key_hex, day, commitments, ctx,
                                                    ranges_for(ctx, mandate))
        facts = EnvelopeFacts(pkg.buyer_id, party_name(books.state, pkg.buyer_id), day, books.state.state_version, False,
                              mandate, v.cur, v.ctx.receivable.face_fen, bool(v.ranges.terms), (), (), (), {}, None, None,
                              False, 0, 0.0)
        out.append(_package(facts, v.probe(Setting(pkg.terms_days, pkg.price_bp, pkg.early_pay_bp, pkg.early_pay_face_fen,
                                                   pkg.rebate_bp)), lang))
    return out


def envelope(books: Books, mandate: Mandate, *, store: LedgerStore | None = None, day: int, buyer_id: str,
             trusted_owner_key_hex: str, commitments: Sequence[Commitment] = (), zone: bool = False,
             full_grid: bool = False, lang: str = "en") -> EnvelopeAnswer:
    """The Safe Deal Envelope for one buyer: the sweep (`envelope_facts`) worded in `lang`. A buyer with no lever is
    answered with `refused` set and empty lists, not an error."""
    return envelope_answer(
        envelope_facts(books, mandate, store=store, day=day, buyer_id=buyer_id, trusted_owner_key_hex=trusted_owner_key_hex,
                       commitments=commitments, zone=zone, full_grid=full_grid), lang)


__all__ = ["EnvelopeAnswer", "EnvelopeFacts", "EnvelopeLever", "EnvelopePackage", "ZoneEntry", "envelope", "envelope_answer",
           "envelope_facts", "probe_packages"]
