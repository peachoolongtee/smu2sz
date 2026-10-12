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
from fractions import Fraction
from typing import Any, Literal, NamedTuple

from pydantic import Field

from app.alerts.engine import past_due_invoices
from app.api.presentation import party_name, t, when_text
from app.books import Books
from app.domain.models import (
    Commitment,
    CompiledOffer,
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
from app.financial import EngineError, value_concessions
from app.funding import NoPermanentSourceError, marginal_cost, plan
from app.funding.router import shared_runs
from app.strategy.no_plan import plan_is_missing
from app.strategy.types import CandidatePackage
from app.strategy.words import DEMO_MARGIN_NOTE, whole_yuan, year_share_sentence
from app.verifier import bind, evaluate
from app.verifier.counters import infeasibility, smallest_step_covering
from app.verifier.evaluate import _evaluate, _Router
from app.whatif.offer import Context, EarlyPayContext, RebateOnlyContext, build, context
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
CARD_SIZE = 3  # the packages on the card (owner's decision 15, #89): the verifier's counters and the ask's answer first

# the levers, by the oracle's own labels (fixtures/strategy/envelope_day0.json `maxima[].lever`)
TERMS_ALONE = "Terms (days), alone"
TERMS_BUDGET_IGNORED = "Terms (days), budget ignored"
TERMS_WITH_PRICE = "Terms (days), with the price that compensates it"
REBATE = "Rebate on the expected order"
EARLY_PAY = "Early pay"  # the lever's label for a buyer with no open invoice (otherwise `early_pay_lever(face)`)


def early_pay_lever(face_fen: int) -> str:
    return f"Early pay on {fmt_yuan(face_fen)}"


BuyerContext = Context | EarlyPayContext | RebateOnlyContext

NO_RECURRING = "no_recurring"  # the buyer has no recurring invoice to extend
NO_INVOICE = "no_invoice"  # the buyer has no open invoice to pay early
NO_PLAN = "no_plan"  # no committed plan covers the shortfall: the terms and rebate levers are withheld (map #58, ticket #79)


def face_of(ctx: BuyerContext) -> int:
    """The face of the invoice the buyer owes, 0 for a buyer with an expected order and no invoice."""
    return 0 if isinstance(ctx, RebateOnlyContext) else ctx.receivable.face_fen


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
    unlisted: tuple[Setting, ...] = ()  # the verifier's counters outside the levers' ranges: not read as settings, not probed
    # the signed caps the package breaks, from the verifier's own violations: (code, the total it counts, the cap), in fen
    caps: tuple[tuple[str, int, int], ...] = ()

    @property
    def approved(self) -> bool:
        return self.passes and self.recheck is None


Authority = Literal["flow_may", "needs_owner", "over_your_limits"]


def authority_of(p: Probe) -> Authority | None:
    """Who may act on a package, in the three classes of the customer-economics brief (E.1), read from the verifier's
    own fields and never computed: `flow_may` (Tier 1, ACCEPT, approved, nothing flagged), `needs_owner` (approved, and
    Tier 2 or a flagged fix: an approved package FLOW cannot run alone today is the owner's too), `over_your_limits`
    (financially safe, but over a cap the owner signed: `liquidity_only`, not passing, and a cap among its violations;
    only a new signed mandate moves it). None: the package fails for some other reason and has no class."""
    if p.approved:
        alone = p.tier == "TIER_1" and p.outcome == Outcome.ACCEPT.value
        return "flow_may" if alone and not p.cure_needs_owner and not p.cure_cannot_run_today else "needs_owner"
    if p.liquidity_only and not p.passes and p.caps:
        return "over_your_limits"
    return None


@dataclass(frozen=True)
class Ranges:
    terms: tuple[int, ...]  # empty when the buyer has no recurring invoice to extend
    price: tuple[int, ...]
    discount: tuple[int, ...]
    rebate: tuple[int, ...]
    face_max_fen: int


def open_context(state: FinancialState, day: int, buyer_id: str) -> BuyerContext:
    """The what-if context of one buyer, with the early-pay face the invoice still owes: an invoice paid in part is
    asked about for its outstanding amount, not the original face the sandbox's own builder would name. A buyer with an
    expected order and no invoice (`RebateOnlyContext`) has no face to correct."""
    ctx = context(state, day, buyer_id)
    if isinstance(ctx, RebateOnlyContext):
        return ctx
    rcv = ctx.receivable
    if rcv.outstanding_fen >= rcv.face_fen:
        return ctx
    return replace(ctx, receivable=rcv.model_copy(update={"face_fen": rcv.outstanding_fen}))


def ranges_for(ctx: BuyerContext, mandate: Mandate) -> Ranges:
    """The levers' own ranges: the what-if grid (the terms run two steps past the terms in force when those reach the
    grid's top), with the discount held to the mandate's immediate-discount cap. A
    rebate-only buyer has the rebate range alone (no terms, price or early payment, and no face)."""
    cap = DISCOUNT_MAX_BP if mandate.max_immediate_discount_bp is None else min(DISCOUNT_MAX_BP, mandate.max_immediate_discount_bp)
    rebates = tuple(range(0, REBATE_MAX_BP + 1, RATE_STEP_BP))
    if isinstance(ctx, RebateOnlyContext):
        return Ranges(terms=(), price=(0,), discount=(0,), rebate=rebates, face_max_fen=0)
    terms: tuple[int, ...] = ()
    if isinstance(ctx, Context):
        # the range is the envelope's own, not the sandbox's: it runs two steps past the terms in force (a buyer already
        # at 90 days is scanned to 100), and the terms in force are a point of their own when they sit off the 5-day grid
        cur = ctx.recurring.terms_days
        top = max(TERMS_MAX, cur + 2 * TERMS_STEP)
        terms = tuple(sorted({*range(min(TERMS_MIN, cur), top + 1, TERMS_STEP), cur}))
    return Ranges(
        terms=terms,
        price=tuple(range(0, PRICE_MAX_BP + 1, RATE_STEP_BP)) if terms else (0,),
        discount=tuple(range(0, cap + 1, RATE_STEP_BP)),
        rebate=rebates if terms else (0,),
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
              hint_steps: int = 2, top_first: bool = False) -> Found:
    """Largest value with ok(value), assuming ok holds up to a boundary and fails after it (binary search, then the two
    values past the boundary checked; if one passes the lever is scanned whole and its largest passing value returned).
    A `hint` (a value expected to be the boundary) is tried first: it stands when it passes and the two values past it
    fail, which is the same evidence the search ends with; otherwise the search runs as if there were no hint. With
    `gallop` the search first doubles its steps up from the first value (cheap when the boundary is near it, as for
    the terms, where a long extension is also the costliest evaluation). `hint_steps` is how many values past the
    hint must fail for it to stand (a sibling search's boundary, which had both neighbours checked, stands on one).
    With `top_first` the top of the range is asked once the first value has passed: when it passes too, one probe in the
    middle and the neighbour below the top are asked as well (the neighbour rule, read downward from a top that has no
    value past it); when both pass, the top is the largest value, and when either fails the lever is not monotone between
    its ends and is scanned whole (a lever with no wall inside its range is read in four evaluations instead of a search;
    the weekly exhaustive scan, `scripts/envelope_monotone_scan.py`, guards what the probes do not cover)."""
    if not values or not ok(values[0]):
        return Found(None, True)
    if top_first and len(values) > 1 and ok(values[-1]):
        if ok(values[len(values) // 2]) and ok(values[-2]):
            return Found(values[-1], True)
        return _scan_max(values, ok)
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


def _params(s: Setting) -> WhatIfParams:
    """The what-if parameters of a setting. The terms in force may sit off the sandbox's grid (32 days): the sliders'
    validators would refuse them, as they would the steps past the sandbox's top (95, 100): those settings are built
    unvalidated (every other value is on the grid)."""
    make = WhatIfParams if TERMS_MIN <= s.terms <= TERMS_MAX and s.terms % TERMS_STEP == 0 else WhatIfParams.model_construct
    return make(terms_days=s.terms, discount_bp=s.discount, rebate_bp=s.rebate, price_adjustment_bp=s.price,
                settle_face_fen=s.face)


class _Verifier:
    """`build` then `evaluate`, memoised per setting within one call, counting the evaluations it actually runs.

    A search asks only whether a setting passes (`quick`), and the verifier builds its counters (a second set of router
    searches) only for an offer it refuses. So a search reads the verdict without them: a setting that passes has no
    counters either way, and its probe goes to the memo as it stands; a setting that fails is kept apart in `failed` and
    is evaluated whole by `probe` only if the answer needs to show it (the counters, the verifier's own outcome word)."""

    def __init__(self, books: Books, mandate: Mandate, key: str, day: int, commitments: Sequence[Commitment],
                 ctx: BuyerContext, ranges: Ranges, withheld: str = "") -> None:
        self.books, self.mandate, self.key, self.day, self.commitments = books, mandate, key, day, commitments
        self.ctx, self.ranges = ctx, ranges
        self.withheld = withheld  # why the ranges leave out the terms and rebate levers (`NO_PLAN`); empty: they are all there
        self.state: FinancialState = books.state
        self.memo: dict[Setting, Probe] = {}
        self.failed: dict[Setting, Probe] = {}  # refused settings read without their counters (see `quick`)
        self.routers: dict[Setting, _Router] = {}  # the router of each refused setting's quick reading, for `probe` to reuse
        self.cur = ctx.recurring.terms_days if isinstance(ctx, Context) else TERMS_MIN

    @property
    def evaluations(self) -> int:
        return len(self.memo) + len(self.failed)

    def norm(self, s: Setting) -> Setting:
        if s.discount == 0 or s.face == face_of(self.ctx):
            return s._replace(face=None)
        return s

    def in_range(self, s: Setting) -> bool:
        """Whether the setting is on the levers' own grids: terms, price, early-pay rate and rebate in their ranges, the
        early-pay face a whole ¥100 inside the open invoice."""
        r = self.ranges
        if (s.terms not in r.terms and (r.terms or s.terms != self.cur)) or s.price not in r.price \
                or s.discount not in r.discount or s.rebate not in r.rebate:
            return False
        return s.face is None or (0 < s.face <= r.face_max_fen and s.face % FACE_STEP_FEN == 0)

    def probe(self, setting: Setting) -> Probe:
        """The verifier's whole answer to a setting, counters included."""
        s = self.norm(setting)
        hit = self.memo.get(s)
        if hit is not None:
            return hit
        if not self.in_range(s):
            raise ValueError(f"{s} is outside the levers' ranges")
        offer, _ = build(_params(s), self.ctx, self.day)
        # a refused setting read before keeps its router, whose memo holds the plans that reading searched for
        router = self.routers.pop(s, None)
        v = self._verdict(offer, router if router is not None else _Router(self.mandate), with_counters=True)
        p = self._read(s, v)
        self.memo[s] = p
        self.failed.pop(s, None)
        return p

    def _verdict(self, offer: CompiledOffer, router: _Router, *, with_counters: bool) -> Verdict:
        """`evaluate` on this buyer's books, on the given router and with or without the counters. An engine error is
        worded by `evaluate` itself (a NO_VERDICT); it never raises one."""
        try:
            with shared_runs():
                return _evaluate(offer, self.state, self.mandate, trusted_owner_key_hex=self.key, day=self.day,
                                 commitments=self.commitments, plans="committed", router=router,
                                 with_counters=with_counters).verdict
        except EngineError:
            return evaluate(offer, self.state, self.mandate, trusted_owner_key_hex=self.key, day=self.day,
                            commitments=self.commitments, plans="committed").verdict

    def quick(self, setting: Setting) -> Probe:
        """The answer to a setting for a search: the verdict without the counters. Its `passes`, `approved`,
        `liquidity_only`, forward total and violations are the whole answer's; `counters`, `unlisted` and, for a refused
        offer, `outcome` (the verifier words COUNTER or REJECT by whether a counter exists) are not, so a refused setting
        is never handed to anything that shows it (`probe` evaluates it whole)."""
        s = self.norm(setting)
        hit = self.memo.get(s) or self.failed.get(s)
        if hit is not None:
            return hit
        if not self.in_range(s):
            raise ValueError(f"{s} is outside the levers' ranges")
        offer, _ = build(_params(s), self.ctx, self.day)
        router = _Router(self.mandate)
        v = self._verdict(offer, router, with_counters=False)
        p = self._read(s, v)
        if v.outcome in PASSING:  # no counters are built for an offer that is not refused: the whole answer, as it is
            self.memo[s] = p
        else:
            self.failed[s] = p
            self.routers[s] = router
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
        caps = tuple((x.code.value, int(x.inputs["total_fen"]), self._cap_of(x.code, x.inputs.get("counterparty_id")))
                     for x in v.violations if x.code in CAP_CODES and "total_fen" in x.inputs)
        cur = self.cur
        read = [(self.norm(_setting_of(c, cur, face_of(self.ctx))), c.supplier_cost_fen) for c in v.counters]
        listed = [(c, cost) for c, cost in read if self.in_range(c)]
        return Probe(
            setting=s, outcome=v.outcome.value, tier=v.required_tier.value, passes=passes, liquidity_only=liquidity_only,
            codes=tuple(dict.fromkeys(x.code.value for x in v.violations)), binding=binding,
            forward_total_fen=v.forward_concession_total_fen,
            reserve_day=reserve.day if reserve else None, reserve_curable=reserve.curable if reserve else None,
            cure_cost_fen=reserve.cure_cost_fen if reserve is not None and curable_reserve else None,
            cure_needs_owner="cure_needs_owner_approval" in flags, cure_cannot_run_today="cure_executable_now" in flags,
            counters=tuple(c for c, _ in listed), counter_costs_fen=tuple(cost for _, cost in listed),
            plan_cost_fen=v.plan.total_cost_fen if v.plan is not None else None,
            recheck=infeasibility(v, self.state) if v.outcome in PASSING else None,
            unlisted=tuple(c for c, _ in read if not self.in_range(c)), caps=caps)

    def _cap_of(self, code: ViolationCode, buyer: str | None) -> int:
        """The signed cap a cap violation counts against: the mandate's per-buyer cap, else its aggregate budget."""
        m = self.mandate
        if code == ViolationCode.PER_BUYER_CAP_EXCEEDED and buyer is not None and buyer in m.per_buyer_caps_fen:
            return m.per_buyer_caps_fen[buyer]
        return m.max_aggregate_forward_concession_fen

    def ok(self, s: Setting) -> bool:
        return self.quick(s).passes

    def rebate_hint(self, at_zero: Probe) -> int | None:
        """Where the largest rebate probably lies, read from the verifier's own forward-concession totals: the room the
        cap leaves above `at_zero` (the package at no rebate) over the cost of one 5 bp step of rebate (the difference
        of two standalone probes, the status quo and the top of the range). Only a hint: the search keeps it when the
        verifier agrees at it and at the two steps past it, and runs without it otherwise."""
        top = self.ranges.rebate[-1]
        if top == 0:
            return None
        base, full = self.quick(Setting(self.cur)), self.quick(Setting(self.cur, rebate=top))
        steps = len(self.ranges.rebate) - 1
        per_step = Fraction(full.forward_total_fen - base.forward_total_fen, steps)  # the verifier rounds each total to the fen
        room = self.mandate.max_aggregate_forward_concession_fen - at_zero.forward_total_fen
        if per_step <= 0 or room < 0:
            return None
        return self.ranges.rebate[min(int(room // per_step), steps)]

    def approved(self, s: Setting) -> bool:
        return self.quick(s).approved

    def liquidity_only(self, s: Setting) -> bool:
        return self.quick(s).liquidity_only

    def compensating_price(self, terms: int) -> tuple[int | None, int | None]:
        """(per-invoice funding cost of the extension, the smallest 5 bp price step that covers it): the Option B rule of
        `app.verifier.counters`, read from `value_concessions` and `smallest_step_covering`. None at or below the terms
        in force and when the buyer has no recurring invoice."""
        ctx = self.ctx
        if not isinstance(ctx, Context) or terms <= ctx.recurring.terms_days:
            return None, None
        offer, _ = build(_params(Setting(terms)), ctx, self.day)
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
    unavailable: str = ""  # why the buyer has no such lever: `NO_RECURRING` or `NO_INVOICE` (empty: the lever exists)


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
    unlisted_counters: tuple[Setting, ...] = ()  # the verifier's counters to the asks that fall outside the levers' ranges
    refusal: Literal["no_lever", "out_of_range"] = "no_lever"  # why `refused` is set
    rebate_only: bool = False  # the buyer has an expected order and no invoice: the rebate is the only lever
    no_plan: bool = False  # no committed plan covers the shortfall: terms and rebate withheld, no plan cost is priced


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
    if b & COVENANT_CODES:
        return "covenant"
    if b & FUNDING_CODES:
        return "funding"
    # any other code is not named: with the caps ignored a cap is never the wall, and an unknown code is never called one
    return None


COVENANT_CODES = frozenset(c.value for c in (ViolationCode.DSCR_BREACH, ViolationCode.LEVERAGE_BREACH,
                                             ViolationCode.CLEAN_DOWN_BREACH))
FUNDING_CODES = frozenset(c.value for c in (ViolationCode.UNCOMMITTED_FACILITY, ViolationCode.LEAD_TIME_TOO_LONG))


def _maximum(v: _Verifier, lever: str, key: str, unit: Literal["days", "bp"], found: Found, make: Callable[[int], Setting],
             values: Sequence[int], *, ignore_caps: bool = False, face_fen: int | None = None) -> Maximum:
    val = found.value
    nxt = next((x for x in values if val is not None and x > val), None)
    at = v.probe(make(val)) if val is not None else None
    beyond = v.probe(make(nxt)) if nxt is not None else None
    return Maximum(lever, key, unit, val, found.confirmed, found.scanned, at, beyond, wall_of(beyond, ignore_caps=ignore_caps),
                   face_fen=face_fen)


def _unavailable(lever: str, key: str, unit: Literal["days", "bp"], why: str = NO_RECURRING) -> Maximum:
    return Maximum(lever, key, unit, None, True, False, None, None, None, unavailable=why)


def _passes(v: _Verifier, make: Callable[[int], Setting]) -> Callable[[int], bool]:
    return lambda x: v.ok(make(x))


def _levers(v: _Verifier) -> tuple[list[Maximum], list[tuple[Setting, int | None]]]:
    """The six maxima, in the oracle's order, and the early-pay variants found (Option A's face and rate, ...)."""
    r, cur, ctx = v.ranges, v.cur, v.ctx
    has_terms = bool(r.terms)
    rebate_only = isinstance(ctx, RebateOnlyContext)
    top_discount = r.discount[-1]
    out: list[Maximum] = []
    up = [x for x in r.terms if x >= cur]
    pmax = r.price[-1]

    if has_terms:
        f = last_true(up, lambda x: v.ok(Setting(x)), gallop=True, top_first=True)
        out.append(_maximum(v, TERMS_ALONE, "terms_alone", "days", f, lambda x: Setting(x), up))
        g = last_true(up, lambda x: v.liquidity_only(Setting(x)), gallop=True, top_first=True)
        out.append(_maximum(v, TERMS_BUDGET_IGNORED, "terms_budget_ignored", "days", g, lambda x: Setting(x), up,
                            ignore_caps=True))
        # the longest terms that any price in range makes pass (the price is monotone: the top of the range is the best
        # chance), then the smallest price that does it
        h = last_true(up, lambda x: v.approved(Setting(x, price=pmax)), gallop=True, top_first=True)
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
        why = (v.withheld or NO_RECURRING) if isinstance(ctx, Context) else NO_RECURRING  # withheld only where a lever exists
        out += [_unavailable(TERMS_ALONE, "terms_alone", "days", why),
                _unavailable(TERMS_BUDGET_IGNORED, "terms_budget_ignored", "days", why),
                _unavailable(TERMS_WITH_PRICE, "terms_with_price", "days", why)]

    # early pay: the whole invoice, and the face of the verifier's own early-pay counter (asked for the top of the range,
    # so that the counter's rate is the break-even step and not the buyer's own)
    faces: list[int] = []
    whole = last_true(r.discount, lambda d: v.ok(Setting(cur, discount=d)), gallop=True)
    if rebate_only:  # no open invoice to pay early
        whole = Found(None, True)
    elif (whole.value or 0) < top_discount:
        for s in v.probe(Setting(cur, discount=top_discount)).counters:  # only the counters on the levers' grids
            if s.discount and s.face is not None and s.face not in faces:
                faces.append(s.face)

    def early_at(face: int | None) -> Callable[[int], Setting]:
        return lambda d: Setting(cur, discount=d, face=face)

    early: list[tuple[int | None, Found]] = [] if rebate_only else [(None, whole)]
    if rebate_only:
        out.append(_unavailable(EARLY_PAY, "early_pay_whole", "bp", NO_INVOICE))
    for fc in faces:
        rate = next((c.discount for c in v.probe(Setting(cur, discount=top_discount)).counters if c.face == fc), None)
        early.append((fc, last_true(r.discount, _passes(v, early_at(fc)), hint=rate)))
    for face, found in early:
        shown = face if face is not None else face_of(ctx)
        out.append(_maximum(v, early_pay_lever(shown), "early_pay_whole" if face is None else "early_pay_counter", "bp",
                            found, early_at(face), r.discount, face_fen=shown))

    if len(r.rebate) > 1:
        rb = last_true(r.rebate, lambda x: v.ok(Setting(cur, rebate=x)), hint=v.rebate_hint(v.quick(Setting(cur))))
        out.append(_maximum(v, REBATE, "rebate", "bp", rb, lambda x: Setting(cur, rebate=x), r.rebate))
    else:
        withheld = (v.withheld or NO_RECURRING) if isinstance(ctx, Context) or rebate_only else NO_RECURRING
        out.append(_unavailable(REBATE, "rebate", "bp", withheld))
    return out, [(Setting(cur, discount=f.value or 0, face=fc), fc) for fc, f in early if f.value and fc is not None]


def _price_at(v: _Verifier, terms: int) -> Callable[[int], bool]:
    """The zone's test: a price counts only when the package passes its own re-check too (`approved`, not `passes`)."""
    return lambda p: v.approved(Setting(terms, price=p))


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
    """The package of one terms value and early-pay variant: the smallest price that is approved (passes and passes its
    own re-check), then the largest rebate still approved at that price (one whole verifier evaluation). A failing cell
    shows the verifier's answer at the largest price, and only when `keep_failures` (the full grid)."""
    r = v.ranges
    fp = first_true(r.price, lambda p: v.approved(base._replace(price=p)), hint=price_hint, hint_steps=1)
    if fp.value is None:
        return v.probe(base._replace(price=r.price[-1], rebate=0)) if keep_failures else None
    priced = base._replace(price=fp.value)
    fr = last_true(r.rebate, lambda x: v.approved(priced._replace(rebate=x)), hint=v.rebate_hint(v.quick(priced)),
                   hint_steps=1 if price_hint is not None else 2)
    p = v.probe(priced._replace(rebate=fr.value or 0))
    return p if p.approved or keep_failures else None


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
            if hint is None and p.approved:
                hint = p.setting.price
            if p.setting not in seen:
                seen.add(p.setting)
                out.append(p)
    return out


def out_of_range_facts(books: Books, *, day: int, buyer_id: str) -> EnvelopeFacts:
    """The facts of a buyer whose books fall outside the levers' ranges (a `ValueError` out of the sweep): refused with
    its own sentence, never an error."""
    state = books.state
    return EnvelopeFacts(buyer_id, party_name(state, buyer_id), day, state.state_version, True, None, 0, 0, False, (), (), (),
                         {}, None, None, False, 0, 0.0, refusal="out_of_range")


def _sweep_ranges(books: Books, mandate: Mandate, ctx: BuyerContext) -> tuple[Ranges, bool, bool]:
    """(the ranges the sweep covers, whether the buyer has a terms lever, whether no committed plan exists). With no plan
    to price a longer payment term or a rebate against, only early payment is checked."""
    ranges = ranges_for(ctx, mandate)
    has_terms_lever = bool(ranges.terms)
    with shared_runs():
        no_plan = plan_is_missing(plan(books.state, books.with_([]), mandate))
    if no_plan:
        ranges = replace(ranges, terms=(), price=(0,), rebate=(0,))
    return ranges, has_terms_lever, no_plan


@dataclass(frozen=True)
class ZoneFacts:
    """The zone table alone, cached apart from the sweep so that a read of the table after a read without it adds only
    the table's cost."""

    rows: tuple[ZoneRow, ...]
    evaluations: int
    seconds: float


def envelope_zone(books: Books, mandate: Mandate, *, day: int, buyer_id: str, trusted_owner_key_hex: str,
                  commitments: Sequence[Commitment] = ()) -> ZoneFacts:
    """The rows `envelope_facts(..., zone=True)` puts in `zone`, without the sweep (the same verifier, a fresh memo: the
    rows are pure in the books, so they are the same). Empty for a buyer with no terms lever or no plan."""
    started = time.perf_counter()
    try:
        ctx = open_context(books.state, day, buyer_id)
    except WhatIfParamError:
        return ZoneFacts((), 0, time.perf_counter() - started)
    ranges, _, no_plan = _sweep_ranges(books, mandate, ctx)
    v = _Verifier(books, mandate, trusted_owner_key_hex, day, commitments, ctx, ranges, NO_PLAN if no_plan else "")
    rows = tuple(_zone(v))
    return ZoneFacts(rows, v.evaluations, time.perf_counter() - started)


@dataclass(frozen=True)
class AskFacts:
    """The answer to the buyer's asked terms T (`compensate`, brief E.2 P4), cached apart from the sweep like the zone.

    `price_only` is the smallest approved price at T, probed whole and re-checked (None: no price in range works), with
    `at_rule` (Option B's rule price at T) beside it. When no price works, `at_top` is T at the top price (the wall and the
    shortfall day it runs into) and `with_early` is the fallback: the smallest early payment of the open invoice that lets T
    through, searched at the smallest rate (where the face is monotone: more early cash only helps, and 0.05% is too small to
    lose the comparison with the plan; at a high rate the face is not monotone, so it is never bisected there), then the
    smallest price with it, then the largest rate at that face by `descend`; probed whole and re-checked. `refusal` names
    why there is nothing to search (`NO_RECURRING`, `NO_PLAN`, "out_of_range")."""

    terms_days: int
    current_terms: int
    receivable_face_fen: int
    price_only: Probe | None
    rule_price_bp: int | None
    at_rule: Probe | None
    at_top: Probe | None
    with_early: Probe | None
    confirmed: bool
    evaluations: int
    seconds: float
    refusal: str = ""


def compensate(v: _Verifier, terms: int) -> AskFacts:
    """The smallest approved price at `terms`, else the smallest early payment that makes them pass (see `AskFacts`)."""
    started = time.perf_counter()
    r, face_now = v.ranges, face_of(v.ctx)

    blank = AskFacts(terms, v.cur, face_now, None, None, None, None, None, True, 0, 0.0)

    def done(**kw: Any) -> AskFacts:
        return replace(blank, **kw, evaluations=v.evaluations, seconds=time.perf_counter() - started)

    if not r.terms:
        return done(refusal=v.withheld or NO_RECURRING)
    if terms not in r.terms:
        return done(refusal="out_of_range")
    pmax = r.price[-1]
    rule = v.compensating_price(terms)[1]
    rule = rule if rule is not None and rule in r.price else None
    fp = first_true(r.price, lambda p: v.approved(Setting(terms, price=p)))
    if fp.value is not None:
        found = v.probe(Setting(terms, price=fp.value))  # the whole answer, counters included, re-checked
        if found.approved:
            at_rule = None
            if rule is not None and rule != fp.value:
                q = v.probe(Setting(terms, price=rule))
                at_rule = q if q.approved else None
            return done(price_only=found, rule_price_bp=rule, at_rule=at_rule, confirmed=fp.confirmed)
    top = v.probe(Setting(terms, price=pmax))
    least = RATE_STEP_BP
    if least not in r.discount or r.face_max_fen < FACE_STEP_FEN:  # no early payment to fall back on
        return done(rule_price_bp=rule, at_top=top, confirmed=fp.confirmed)
    faces = tuple(range(FACE_STEP_FEN, r.face_max_fen + 1, FACE_STEP_FEN))
    ff = first_true(faces, lambda f: v.approved(Setting(terms, price=pmax, discount=least, face=f)))
    if ff.value is None:
        return done(rule_price_bp=rule, at_top=top, confirmed=fp.confirmed and ff.confirmed)
    face = ff.value
    fq = first_true(r.price, lambda p: v.approved(Setting(terms, price=p, discount=least, face=face)))
    price = fq.value if fq.value is not None else pmax
    fr = descend(r.discount, lambda d: v.approved(Setting(terms, price=price, discount=d, face=face)), r.discount[-1])
    early = v.probe(Setting(terms, price=price, discount=fr.value or least, face=face))
    if not early.approved:  # the largest rate fails its whole re-check: the smallest one, which the searches passed
        early = v.probe(Setting(terms, price=price, discount=least, face=face))
    confirmed = fp.confirmed and ff.confirmed and fq.confirmed and fr.confirmed
    return done(rule_price_bp=rule, at_top=top, with_early=early if early.approved else None, confirmed=confirmed)


def envelope_ask(books: Books, mandate: Mandate, *, day: int, buyer_id: str, trusted_owner_key_hex: str, terms: int,
                 commitments: Sequence[Commitment] = ()) -> AskFacts:
    """`compensate(terms)` for one buyer on a fresh verifier (the answers are pure in the books, as the zone's are)."""
    ctx = open_context(books.state, day, buyer_id)
    ranges, _, no_plan = _sweep_ranges(books, mandate, ctx)
    v = _Verifier(books, mandate, trusted_owner_key_hex, day, commitments, ctx, ranges, NO_PLAN if no_plan else "")
    return compensate(v, terms)


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
    ranges, has_terms_lever, no_plan = _sweep_ranges(books, mandate, ctx)
    v = _Verifier(books, mandate, trusted_owner_key_hex, day, commitments, ctx, ranges, NO_PLAN if no_plan else "")
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
    unlisted: dict[Setting, None] = {}
    for a in asks:
        p = v.probe(a)
        for c, cost in zip(p.counters, p.counter_costs_fen, strict=True):
            counter_costs.setdefault(c, cost)
        unlisted.update(dict.fromkeys(p.unlisted))
    counters = set(counter_costs)
    seen = {c.setting for c in cells}
    for s in sorted(counters):
        if s not in seen and v.approved(s):
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
        buyer_id, name, day, version, False, mandate, cur, face_of(ctx), has_terms_lever, tuple(maxima),
        tuple(zone_rows), cell_tuple, counter_costs, status_quo, next_terms, with_early, v.evaluations, time.perf_counter() - started,
        past_due, tuple(unlisted), rebate_only=isinstance(ctx, RebateOnlyContext), no_plan=no_plan)


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
    # who may act on it (`authority_of`): None for a package that fails for any other reason
    authority: Authority | None = None
    authority_words: str | None = None  # the class in words: "FLOW may do this on its own", ...
    authority_sentence: str | None = None  # classes 2 and 3: what holds, and who decides (brief E.3)
    cap_fen: int | None = None  # class 3: the signed cap the package breaks
    cap_used_fen: int | None = None  # class 3: what the verifier counts against that cap
    over_cap_by_fen: int | None = None  # class 3: by how much
    # class 3, and only with FEATURE_CUSTOMER_ECONOMICS on and a contribution held: what the package costs as a share of a year's
    # gross profit from the buyer. Context, a sentence of its own: it never changes the class, the verdict or the cap
    economics_sentence: str | None = None
    economics_note: str | None = None  # "the margin is assumed for the Demo, not confirmed by you" while it is


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
    unavailable: str | None  # "no recurring invoice to extend" / "no open invoice to pay early"
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


class AskAnswer(Contract):
    """What makes the buyer's asked terms work (P4): the smallest price, or the early payment that does when no price
    can; every package probed whole and re-checked. The rule price is beside the smallest; no package is ranked."""

    terms_days: int
    terms_words: str  # "60 days"
    sentence: str
    price_works: bool
    smallest_price: EnvelopePackage | None = None  # the smallest approved price at the asked terms
    rule_price: EnvelopePackage | None = None  # Option B's rule price at the asked terms, when it is a different package
    with_early_payment: EnvelopePackage | None = None  # no price works: the early payment that does
    early_face_fen: int | None = None  # the part of the open invoice paid now in that package
    refused: str | None = None
    neighbours_confirmed: bool
    evaluations: int
    computed_in_seconds: float


class EnvelopeAnswer(Contract):
    buyer_id: str
    buyer_name: str
    primary: str
    reason: str
    money: str
    # the card, at most `CARD_SIZE`: the verifier's own counters, then the answer to the buyer's ask; never ranked
    packages: list[EnvelopePackage]
    more: list[EnvelopePackage] = Field(default_factory=list)  # every other package, behind a disclosure
    # class 3, in a group of its own: the longest terms that keep your cash floor if the budget is ignored, over a cap you
    # signed (never an approval: only a new signed mandate moves the cap)
    over_your_limits: list[EnvelopePackage] = Field(default_factory=list)
    levers: list[EnvelopeLever]
    zone: list[ZoneEntry] = Field(default_factory=list)
    ask: AskAnswer | None = None  # `?ask=T`: what makes the buyer's asked terms work
    refused: str | None = None
    unlisted_counters: list[str] = Field(default_factory=list)  # one sentence per verifier counter left out as off the grid
    source_state_version: int
    hypothetical: Literal[True] = True
    evaluations: int
    computed_in_seconds: float


_WALL_TEXT = {
    "forward budget": ("your budget for what you give buyers", "您给买家让利的预算"),
    "buyer cap": ("your limit for this buyer", "您对该买家的上限"),
    "liquidity": ("your cash floor", "您的现金底线"),
    "break-even": ("the break-even for paying early", "提前付款的盈亏平衡点"),
    "plan comparison": ("the cheaper funding you already have", "您已有的更便宜的资金安排"),
    "the mandate's price ceiling": ("your price ceiling", "您的价格上限"),
    "covenant": ("your loan covenants", "您的贷款契约"),
    "funding": ("funding that can arrive in time", "能及时到位的资金"),
}
_WALL_WORDS = {
    "forward budget": ("your budget for what you give buyers", "您给买家让利的预算"),
    "buyer cap": ("the cap for this buyer", "该买家的上限"),
    "liquidity": ("your cash floor", "您的现金底线"),
    "break-even": ("the break-even for paying early", "提前付款的盈亏平衡点"),
    "plan comparison": ("the cheaper funding you already have", "您已有的更便宜的资金安排"),
    "the mandate's price ceiling": ("the price ceiling in your mandate", "您授权中的价格上限"),
    "covenant": ("your loan covenants", "您的贷款契约"),
    "funding": ("funding that can arrive in time", "能及时到位的资金"),
}
_LEVER_LABEL = {
    "terms_alone": ("Longest payment terms on their own", "仅延长账期时的最长账期"),
    "terms_budget_ignored": ("Longest payment terms if the budget is ignored", "不计预算时的最长账期"),
    "terms_with_price": ("Longest payment terms with a price rise", "加价后的最长账期"),
    "rebate": ("Rebate on the expected order", "预期订单的返利"),
}


_UNAVAILABLE = {
    NO_RECURRING: ("no recurring invoice to extend", "没有可延长的定期发票"),
    NO_INVOICE: ("no open invoice to pay early", "没有可提前付款的未结发票"),
    NO_PLAN: ("withheld while no funding plan covers the shortfall", "没有融资方案能补上缺口时不提供"),
}
# said by the answer when no committed plan covers the shortfall (the terms and rebate levers are withheld)
WITHHELD = ("FLOW cannot offer longer terms or a rebate while no funding plan covers the shortfall; early payment only.",
            "在没有融资方案能补上缺口时，FLOW 无法提供更长账期或返利；只能提前付款。")
WITHHELD_REBATE_ONLY = ("FLOW cannot offer a rebate while no funding plan covers the shortfall.",
                        "在没有融资方案能补上缺口时，FLOW 无法提供返利。")
WITHHELD_NO_EARLY = (("FLOW cannot offer longer terms or a rebate while no funding plan covers the shortfall, and no early "
                      "payment passes FLOW's checks."),
                     "在没有融资方案能补上缺口时，FLOW 无法提供更长账期或返利，也没有提前付款方案能通过 FLOW 的检查。")


def _lever_label(m: Maximum, lang: str) -> str:
    if m.key in _LEVER_LABEL:
        return t(lang, *_LEVER_LABEL[m.key])
    if m.unavailable:
        return t(lang, "Early payment", "提前付款")
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
        return t(lang, *_UNAVAILABLE[m.unavailable])
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
        return t(lang, *_UNAVAILABLE[m.unavailable])
    return t(lang, *_WALL_WORDS[m.wall]) if m.wall in _WALL_WORDS else None


def _lowest_price_words(z: ZoneRow, lang: str) -> str:
    if z.min_price_bp is None:
        return t(lang, "none works", "没有可行的价格")
    if z.min_price_bp == 0:
        return t(lang, "no price rise needed", "无需加价")
    return _pct(z.min_price_bp)


_AUTHORITY_WORDS: dict[str, tuple[str, str]] = {
    "flow_may": ("FLOW may do this on its own", "FLOW 可以自行处理"),
    "needs_owner": ("within your limits; needs your approval", "在您的底线内；需要您批准"),
    "over_your_limits": ("over a limit you signed", "超出您签署的上限"),
}


def _phrase(facts: EnvelopeFacts, s: Setting, lang: str) -> str:
    """A package as the owner says it: "55-day terms with a 0.30% price rise", "55-day terms at today's price" (terms
    alone, no price rise), "45-day terms with early payment of 0.85% on ¥257,200.00"."""
    extras_en: list[str] = []
    extras_zh: list[str] = []
    if s.price > 0:
        extras_en.append(f"a {_pct(s.price)} price rise")
        extras_zh.append(f"加价 {_pct(s.price)}")
    if s.discount > 0:
        face = fmt_yuan(s.face if s.face is not None else facts.receivable_face_fen)
        extras_en.append(f"early payment of {_pct(s.discount)} on {face}")
        extras_zh.append(f"提前付款 {_pct(s.discount)}（金额 {face}）")
    if s.rebate > 0:
        extras_en.append(f"a {_pct(s.rebate)} rebate")
        extras_zh.append(f"返利 {_pct(s.rebate)}")
    if not extras_en:
        return t(lang, f"{s.terms}-day terms at today's price", f"按现价给 {s.terms} 天账期")
    joined = extras_en[0] if len(extras_en) == 1 else f"{', '.join(extras_en[:-1])} and {extras_en[-1]}"
    return t(lang, f"{s.terms}-day terms with {joined}", f"{s.terms} 天账期并{'、'.join(extras_zh)}")


def _what_needs_you(facts: EnvelopeFacts, p: Probe, lang: str) -> str:
    """What FLOW cannot agree alone in a class-2 package: the longer terms first, as the verifier's tier rule reads it."""
    s = p.setting
    if s.terms > facts.current_terms:
        return t(lang, "longer terms", "延长账期")
    if s.rebate > 0:
        return t(lang, "a rebate", "返利")
    if s.price > 0:
        return t(lang, "a price change", "调整价格")
    return t(lang, "this early payment", "这笔提前付款")


def _authority_sentence(facts: EnvelopeFacts, p: Probe, authority: Authority | None, lang: str) -> str | None:
    phrase = _phrase(facts, p.setting, lang)
    if authority == "needs_owner":
        if p.tier == "TIER_1" and p.outcome == Outcome.ACCEPT.value:  # FLOW could agree it, but its fix cannot run alone
            return t(lang, f"{phrase}: within your limits and your cash floor holds, but its funding cannot run today. "
                           "It needs your approval.",
                     f"{phrase}：在您的底线内，现金底线也守得住，但其资金安排今天无法执行，需要您批准。")
        what = _what_needs_you(facts, p, lang)
        return t(lang, f"{phrase}: within your limits and your cash floor holds, but FLOW cannot agree {what} on its own. "
                       "It needs your approval.",
                 f"{phrase}：在您的底线内，现金底线也守得住，但 FLOW 不能自行同意{what}，需要您批准。")
    if authority == "over_your_limits":
        code, used, cap = p.caps[0]
        tail = t(lang, " FLOW will not send it under the limits you signed; only you can decide, and raising the limit means "
                       "signing a new mandate.",
                 "在您签署的授权范围内，FLOW 不会发送此方案；只有您能决定，提高上限需要签署新的授权。")
        if code == ViolationCode.PER_BUYER_CAP_EXCEEDED.value:
            who = facts.buyer_name
            return t(lang, f"{phrase}: your cash floor holds, but it uses {fmt_yuan(used)} of your {fmt_yuan(cap)} limit for "
                           f"{who}.{tail}",
                     f"{phrase}：现金底线守得住，但会占用您对{who}的上限中的 {fmt_yuan(used)}（上限为 {fmt_yuan(cap)}）。{tail}")
        return t(lang, f"{phrase}: your cash floor holds, but it uses {fmt_yuan(used)} of your {fmt_yuan(cap)} budget for "
                       f"what you give buyers.{tail}",
                 f"{phrase}：现金底线守得住，但会占用您给买家让利预算中的 {fmt_yuan(used)}（预算为 {fmt_yuan(cap)}）。{tail}")
    return None


def _package(facts: EnvelopeFacts, p: Probe, lang: str, match: bool = False) -> EnvelopePackage:
    s = p.setting
    authority = authority_of(p)
    over = p.caps[0] if authority == "over_your_limits" else None
    breach = None
    if p.reserve_day is not None:
        breach = ReserveBreachView(day=p.reserve_day, when=when_text(p.reserve_day, facts.day, lang),
                                   curable=bool(p.reserve_curable), cure_cost_fen=p.cure_cost_fen)
    # the terms in force may sit off the sandbox's 5-day grid (32 days): that one package is carried unvalidated
    on_grid = TERMS_MIN <= s.terms <= TERMS_MAX and s.terms % TERMS_STEP == 0
    make = CandidatePackage if on_grid else CandidatePackage.model_construct
    return EnvelopePackage(
        package=make(buyer_id=facts.buyer_id, terms_days=s.terms, price_bp=s.price, early_pay_bp=s.discount,
                     early_pay_face_fen=s.face, rebate_bp=s.rebate),
        outcome=p.outcome, tier=p.tier, passes=p.passes, approved=p.approved, codes=list(p.codes),
        binding_codes=list(p.binding), forward_budget_used_fen=p.forward_total_fen, reserve_breach=breach,
        flags=_flags(p, lang), counter_match=match, plan_cost_fen=None if facts.no_plan else p.plan_cost_fen,
        summary=_summary(s, lang), authority=authority,
        authority_words=t(lang, *_AUTHORITY_WORDS[authority]) if authority is not None else None,
        authority_sentence=_authority_sentence(facts, p, authority, lang),
        cap_fen=over[2] if over else None, cap_used_fen=over[1] if over else None,
        over_cap_by_fen=over[1] - over[2] if over else None)


@dataclass(frozen=True)
class Economics:
    """A year of the buyer's gross profit, as the Customer overview reads it (`customer_overview.year_held`, the one margin and
    contribution function), and its 12-month scaling of a forward concession (`customer_overview.twelve_months_of`): composed by
    the route, never computed here. Given only while FEATURE_CUSTOMER_ECONOMICS is on and a contribution exists."""

    contribution_fen: int
    assumed: bool  # the margin is the Demo's default
    gross: bool  # the basis word: gross profit (default) or contribution
    year_of: Callable[[int], int]  # a forward concession over the mandate's horizon, on a 12-month basis


def _economics_words(facts: EnvelopeFacts, p: Probe, eco: Economics, lang: str) -> tuple[str | None, str | None]:
    """(the sentence, the note): the verdict's own forward concession on a 12-month basis over a year's gross profit
    (`words.year_share_sentence`, the one sentence every surface says it with). None without a cost or a positive year."""
    sentence = year_share_sentence(facts.buyer_name, eco.year_of(p.forward_total_fen), eco.contribution_fen, eco.gross,
                                   "zh" if lang == "zh" else "en")
    if sentence is None:
        return None, None
    return sentence, t(lang, *DEMO_MARGIN_NOTE) if eco.assumed else None


def _over_your_limits(facts: EnvelopeFacts, lang: str, economics: Economics | None = None) -> list[EnvelopePackage]:
    """The class-3 group: the `terms_budget_ignored` maximum as one package, when it is over a cap you signed (when the
    budget does not bind, the maximum is approved and there is nothing to list here). With `economics` the package carries
    its share of a year's gross profit, as a sentence of its own after the mandate's."""
    m = _lever_of(facts, "terms_budget_ignored")
    if m is None or m.at_max is None or authority_of(m.at_max) != "over_your_limits":
        return []
    pkg = _package(facts, m.at_max, lang)
    if economics is not None:
        sentence, note = _economics_words(facts, m.at_max, economics, lang)
        pkg = pkg.model_copy(update={"economics_sentence": sentence, "economics_note": note})
    return [pkg]


def _lever(facts: EnvelopeFacts, m: Maximum, lang: str) -> EnvelopeLever:
    wall_text = t(lang, *_WALL_TEXT[m.wall]) if m.wall in _WALL_TEXT else None
    return EnvelopeLever(
        lever=m.lever, key=m.key, label=_lever_label(m, lang), unit=m.unit, maximum=m.value, confirmed=m.confirmed,
        scanned=m.scanned, wall=m.wall, wall_text=wall_text, face_fen=m.face_fen, rule_price_bp=m.rule_price_bp,
        unavailable=t(lang, *_UNAVAILABLE[m.unavailable]) if m.unavailable else None,
        maximum_display=_maximum_words(m, lang), wall_words=_wall_words(m, lang), next_step_sentence=_next_step_words(m, lang),
        at_maximum=_package(facts, m.at_max, lang) if m.at_max is not None else None,
        next_step=_package(facts, m.beyond, lang) if m.beyond is not None else None)


def _lever_of(facts: EnvelopeFacts, key: str) -> Maximum | None:
    return next((m for m in facts.maxima if m.key == key), None)


_TOP = (" (the most FLOW checks)", "（FLOW 检查的上限）")


def _todays_price(facts: EnvelopeFacts, lang: str) -> str:
    """The terms that pass at today's price, within the limits: "At today's price: up to 45 days within your limits."
    Empty when the buyer has no terms lever, or no plan prices one."""
    alone = _lever_of(facts, "terms_alone")
    if alone is None or alone.value is None or alone.unavailable:
        return ""
    top = t(lang, *_TOP) if alone.wall is None and alone.beyond is None else ""
    return t(lang, f"At today's price: up to {alone.value} days{top} within your limits.",
             f"按现价：在您的底线内，账期最长 {alone.value} 天{top}。")


def _primary(facts: EnvelopeFacts, lang: str) -> str:
    """The headline: the terms at today's price, then the packages you can live with, each named whole (the terms
    with the price rise that makes them pass, the early payment with its face), never maxima joined from separate
    levers. A rebate is named only when its package is the one quoted (a buyer with nothing else to value)."""
    cur = facts.current_terms
    pieces: list[str] = []
    terms = _lever_of(facts, "terms_with_price")
    alone = _lever_of(facts, "terms_alone")
    longest = terms.value if terms is not None and terms.value is not None else cur
    if terms is not None and terms.value is not None and longest > cur:
        # the counter FLOW would send: Option B's rule price when it passes, else the smallest price that does
        price = terms.at_max.setting.price if terms.at_max is not None else 0
        if terms.rule_price_bp is not None and any(
                c.probe.setting == Setting(longest, price=terms.rule_price_bp) for c in facts.cells):
            price = terms.rule_price_bp
        # a maximum at the top of the range with no wall is not a ceiling the books set: say so
        top = t(lang, *_TOP) if terms.wall is None and facts.next_terms is None else ""
        said_at_todays_price = alone is not None and alone.value == longest
        if price or not said_at_todays_price:
            pieces.append(_phrase(facts, Setting(longest, price=price), lang) + top)
    early = next((m for m in facts.maxima if m.key == "early_pay_counter" and m.value), None) or \
        next((m for m in facts.maxima if m.key == "early_pay_whole" and m.value), None)
    if early is not None and early.value:
        rate, face = fmt_pct(bp(early.value)), fmt_yuan(early.face_fen or 0)
        pieces.append(t(lang, f"early payment of {rate} on {face}", f"提前付款 {rate}（金额 {face}）"))
    first = t(lang, ", or ", "，或") .join(pieces)
    parts = [first] if first else []
    rebate = _lever_of(facts, "rebate")
    if facts.rebate_only and rebate is not None and rebate.value:
        parts = [t(lang, f"a rebate up to {fmt_pct(bp(rebate.value))} on the expected order; no terms or early payment to value yet",
                   f"对预期订单的返利最高 {fmt_pct(bp(rebate.value))}；暂无可估值的账期或提前付款")]
    elif not parts and rebate is not None and rebate.value and rebate.at_max is not None and rebate.at_max.approved:
        # the rebate's own package is the one quoted: nothing else is named beside it
        parts.append(t(lang, f"a {fmt_pct(bp(rebate.value))} rebate", f"返利 {fmt_pct(bp(rebate.value))}"))
    if facts.has_terms_lever and not facts.no_plan:
        if facts.next_terms is not None:
            n = facts.next_terms
            parts.append(t(lang, f"not {n} days without an early payment", f"不提前付款则不能做到 {n} 天")
                         if facts.next_terms_passes_with_early_pay else t(lang, f"not {n} days", f"不能做到 {n} 天"))
        elif longest == cur:
            parts.append(t(lang, "no longer payment terms", "不能延长账期"))
    if not parts and facts.no_plan:
        return t(lang, *(WITHHELD_REBATE_ONLY if facts.rebate_only else WITHHELD_NO_EARLY))
    lead = _todays_price(facts, lang)
    gap = t(lang, " ", "") if lead else ""
    if not parts:
        return lead + gap + t(lang, "Nothing beyond today's terms passes FLOW's checks.", "今天的条件之外，没有任何方案能通过 FLOW 的检查。")
    text = t(lang, "You can live with: ", "您能接受的范围：") + t(lang, "; ", "；").join(parts)
    return lead + gap + text + t(lang, ".", "。")


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
    if facts.no_plan and (facts.has_terms_lever or facts.rebate_only):  # the levers that need a plan to price are withheld
        said = t(lang, *(WITHHELD_REBATE_ONLY if facts.rebate_only else WITHHELD))
        return f"{_sentence(clauses, lang)}{' ' if lang != 'zh' else ''}{said}" if clauses else said
    if facts.rebate_only:
        clauses.append(t(lang, "there is no recurring invoice to extend and no open invoice to pay early, so only the "
                               "rebate on the expected order can be valued",
                         "没有可延长的定期发票，也没有可提前付款的未结发票，所以只能为预期订单的返利估值"))
        rebate = _lever_of(facts, "rebate")
        if rebate is not None and rebate.value is not None and rebate.wall in _WALL_TEXT:
            wall = t(lang, *_WALL_TEXT[rebate.wall])
            clauses.append(t(lang, f"a bigger rebate runs into {wall}", f"更高的返利会碰到{wall}"))
        return _sentence(clauses, lang)
    if not facts.has_terms_lever:
        clauses.append(t(lang, "there is no recurring invoice to extend, so only an early payment can be priced",
                         "没有可延长的定期发票，所以只能为提前付款估值"))
        return _sentence(clauses, lang)
    liquid = _lever_of(facts, "terms_budget_ignored")
    if liquid is not None and liquid.beyond is not None:
        b, n = liquid.beyond, liquid.beyond.setting.terms
        if liquid.wall == "liquidity" and b.reserve_day is not None:
            when = when_text(b.reserve_day, facts.day, lang)
            # the failing package carries no early payment; say so when an early payment is what would let the step pass
            bare = b.setting.discount == 0 and facts.next_terms_passes_with_early_pay
            clauses.append(t(lang, f"{n} days{' without an early payment' if bare else ''} leaves a shortfall {when} that no fix covers",
                             f"不提前付款的 {n} 天账期会在 {when}出现无法补上的缺口" if bare
                             else f"账期 {n} 天在 {when}会出现缺口，且无法补上"))
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


def _now(facts: EnvelopeFacts, standing: int, lang: str) -> str:
    """The standing plan's clause of the cost line: its cost, or that it is not priced when no committed plan exists."""
    if facts.no_plan:
        return t(lang, "your current funding plan is not priced because no committed plan covers the shortfall",
                 "现行资金安排无法估值，因为没有已承诺的融资方案能补上缺口")
    return t(lang, f"without a deal your current funding plan costs {fmt_yuan(standing)}",
             f"不做交易时，现行资金安排的成本为 {fmt_yuan(standing)}")


def _money(facts: EnvelopeFacts, lang: str) -> str:
    standing = facts.status_quo.plan_cost_fen if facts.status_quo is not None else None
    if standing is None:
        return ""
    if facts.rebate_only:
        now = _now(facts, standing, lang)
        rebate = _lever_of(facts, "rebate")
        used = rebate.at_max.forward_total_fen - facts.status_quo.forward_total_fen \
            if rebate is not None and rebate.at_max is not None and facts.status_quo is not None else 0
        if used <= 0:
            return (now[0].upper() + now[1:] if lang != "zh" else now) + t(lang, ".", "。")
        return (t(lang, f"The rebate at that most counts {fmt_yuan(used)} against your budget for what you give buyers; ",
                  f"按上述上限，返利会占用您给买家让利的预算 {fmt_yuan(used)}；") + now + t(lang, ".", "。"))
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
    now = _now(facts, standing, lang)
    if not costs:
        return (now[0].upper() + now[1:] if lang != "zh" else now) + t(lang, ".", "。")
    lead = t(lang, "Cost to you ", "您的成本：") + t(lang, ", or ", "，或").join(costs)
    return lead + t(lang, "; ", "；") + now + t(lang, ".", "。")


def _unlisted_sentence(s: Setting, lang: str) -> str:
    what = _summary(s, lang)
    return t(lang, f"FLOW's own counter ({what}) is outside the ranges this page checks, so it is not listed.",
             f"FLOW 自己给出的对案（{what}）超出本页检查的范围，因此未列出。")


def _refusal(name: str, lang: str, reason: str = "no_lever") -> str:
    if reason == "out_of_range":
        return t(lang, f"FLOW cannot value a deal with {name} on the books as they stand: its terms or amounts fall "
                       f"outside the ranges FLOW checks.",
                 f"FLOW 目前无法为{name}估值：账上的账期或金额超出了 FLOW 检查的范围。")
    return t(lang, f"FLOW has no terms, payment or rebate lever to value for {name} yet.",
             f"FLOW 目前没有可为{name}估值的账期、付款或返利杠杆。")


def _ask_tail(authority: Authority | None, lang: str) -> tuple[str, str]:
    """Who decides, as the sentence's last clause: (the clause, the same clause as its own sentence)."""
    if authority == "flow_may":
        return t(lang, "FLOW may send it on its own", "FLOW 可以自行发送"), t(lang, " FLOW may send it on its own.", "FLOW 可以自行发送。")
    return t(lang, "that needs your approval", "这需要您批准"), t(lang, " It needs your approval.", "这需要您批准。")


def _ask_sentence(facts: EnvelopeFacts, ask: AskFacts, lang: str) -> str:
    n = ask.terms_days
    if ask.refusal == "out_of_range":
        return t(lang, f"{n} days is outside the payment terms FLOW checks.", f"{n} 天不在 FLOW 检查的账期范围内。")
    if ask.refusal == NO_PLAN:
        return t(lang, "FLOW cannot offer longer terms while no funding plan covers the shortfall.",
                 "在没有融资方案能补上缺口时，FLOW 无法提供更长账期。")
    if ask.refusal:
        return t(lang, f"FLOW cannot value {n}-day terms for {facts.buyer_name}: there is no recurring invoice to extend.",
                 f"FLOW 无法为{facts.buyer_name}估值 {n} 天账期：没有可延长的定期发票。")
    found = ask.price_only
    if found is not None:
        lowest = found.setting.price
        tail = _ask_tail(authority_of(found), lang)[1]
        if lowest == 0:
            return t(lang, f"{n} days works at today's price.", f"按现价即可接受 {n} 天账期。") + tail
        p = _pct(lowest)
        if ask.at_rule is not None:
            rule = _pct(ask.at_rule.setting.price)
            both = authority_of(found) == authority_of(ask.at_rule) == "needs_owner"
            return (t(lang, f"{n} days works if the price rises at least {p}; at {rule} the price rise pays for the longer terms "
                            "in full.",
                      f"价格至少上调 {p}，即可接受 {n} 天账期；上调 {rule} 时，加价可完全抵消延长账期的成本。")
                    + (t(lang, " Either needs your approval.", "两者都需要您批准。") if both else tail))
        if ask.rule_price_bp == lowest:
            return t(lang, f"{n} days works if the price rises {p}; at that price the price rise pays for the longer terms in full.",
                     f"价格上调 {p}，即可接受 {n} 天账期；该加价可完全抵消延长账期的成本。") + tail
        return t(lang, f"{n} days works if the price rises at least {p}.", f"价格至少上调 {p}，即可接受 {n} 天账期。") + tail
    top = ask.at_top
    wall = wall_of(top)
    if top is not None and wall == "liquidity" and top.reserve_day is not None:
        when = when_text(top.reserve_day, facts.day, lang)
        lead = t(lang, f"No price rise makes {n} days work: the longer terms leave your cash short {when}.",
                 f"任何加价都无法让 {n} 天账期可行：账期延长会让您的现金在 {when}不足。")
    elif wall in _WALL_TEXT:
        what = t(lang, *_WALL_TEXT[wall])
        lead = t(lang, f"No price rise makes {n} days work: the longer terms run into {what}.",
                 f"任何加价都无法让 {n} 天账期可行：账期延长会碰到{what}。")
    else:
        lead = t(lang, f"No price rise makes {n} days work.", f"任何加价都无法让 {n} 天账期可行。")
    gap = t(lang, " ", "")
    early = ask.with_early
    if early is None:
        return lead + gap + t(lang, f"Nothing within the ranges FLOW checks makes {n} days work on today's books.",
                              f"按今天的账面，在 FLOW 检查的范围内，没有方案能让 {n} 天账期可行。")
    s = early.setting
    face, whole = whole_yuan(s.face if s.face is not None else ask.receivable_face_fen), fmt_yuan(ask.receivable_face_fen)
    clause = _ask_tail(authority_of(early), lang)[0]
    if s.price:
        p = _pct(s.price)
        rest = t(lang, f"{n} days works only if {face} of the open {whole} invoice is paid now and the price rises {p}; {clause}.",
                 f"只有在 {whole} 的未结发票中先支付 {face}，并加价 {p} 时，{n} 天才可行；{clause}。")
    else:
        rest = t(lang, f"{n} days works only if {face} of the open {whole} invoice is paid now; {clause}.",
                 f"只有在 {whole} 的未结发票中先支付 {face} 时，{n} 天才可行；{clause}。")
    return lead + gap + rest


def ask_answer(facts: EnvelopeFacts, ask: AskFacts, lang: str = "en") -> AskAnswer:
    """The ask's facts in words, its packages worded as the sweep's are."""
    def pkg(p: Probe | None) -> EnvelopePackage | None:
        return _package(facts, p, lang) if p is not None else None

    early = ask.with_early
    return AskAnswer(
        terms_days=ask.terms_days, terms_words=_days(ask.terms_days, lang), sentence=_ask_sentence(facts, ask, lang),
        price_works=ask.price_only is not None, smallest_price=pkg(ask.price_only), rule_price=pkg(ask.at_rule),
        with_early_payment=pkg(early),
        early_face_fen=(early.setting.face if early.setting.face is not None else ask.receivable_face_fen) if early else None,
        refused=_ask_sentence(facts, ask, lang) if ask.refusal else None, neighbours_confirmed=ask.confirmed,
        evaluations=ask.evaluations, computed_in_seconds=round(ask.seconds, 3))


def _card(facts: EnvelopeFacts, ask: AskFacts | None, lang: str) -> tuple[list[EnvelopePackage], list[EnvelopePackage]]:
    """(the card, the rest). The card holds the verifier's own counters among the approved packages, then the answer to the
    buyer's ask (its smallest price, or the early payment that makes the terms work), at most `CARD_SIZE`; with neither,
    the first packages of the grid. Order is the verifier's and the ask's, never a ranking; nothing is called recommended."""
    cells = [(c.probe, c.counter_match) for c in facts.cells]
    asked = list(facts.counter_costs_fen)  # the counters in the order the sweep put the asks: early payment, terms, rebate
    counters = sorted(((p, m) for p, m in cells if m and p.approved), key=lambda c: asked.index(c[0].setting)
                      if c[0].setting in asked else len(asked))
    answer: list[tuple[Probe, bool]] = []
    if ask is not None:
        for p in (ask.price_only, ask.with_early):
            if p is not None and p.approved and all(p.setting != q.setting for q, _ in [*counters, *answer]):
                answer.append((p, any(m for q, m in cells if q.setting == p.setting)))
    # the ask's answer keeps its place: the counters fill what is left of the card
    on_card = [*counters[:CARD_SIZE - len(answer[:1])], *answer[:1]] or cells[:CARD_SIZE]
    shown = {p.setting for p, _ in on_card}
    rest = [(p, m) for p, m in cells if p.setting not in shown]
    return [_package(facts, p, lang, m) for p, m in on_card], [_package(facts, p, lang, m) for p, m in rest]


def envelope_answer(facts: EnvelopeFacts, lang: str = "en", ask: AskFacts | None = None,
                    economics: Economics | None = None) -> EnvelopeAnswer:
    """The sweep's facts in words (`en` or `zh`)."""
    meta: dict[str, object] = {"buyer_id": facts.buyer_id, "buyer_name": facts.buyer_name,
                               "source_state_version": facts.source_state_version, "evaluations": facts.evaluations,
                               "computed_in_seconds": round(facts.seconds, 3)}
    if facts.refused:
        return EnvelopeAnswer.model_validate({**meta, "primary": "", "reason": "", "money": "", "packages": [],
                                              "levers": [], "zone": [],
                                              "refused": _refusal(facts.buyer_name, lang, facts.refusal)})
    card, more = _card(facts, ask, lang)
    zone = [ZoneEntry(terms_days=z.terms_days, terms_words=_days(z.terms_days, lang), min_price_bp=z.min_price_bp, rule_price_bp=z.rule_price_bp,
                      cost_per_invoice_fen=z.cost_per_invoice_fen, passes_within_range=z.min_price_bp is not None,
                      neighbours_confirmed=z.confirmed, at_that_price=_package(facts, z.at_price, lang),
                      lowest_price_words=_lowest_price_words(z, lang))
            for z in facts.zone]
    return EnvelopeAnswer(
        buyer_id=facts.buyer_id, buyer_name=facts.buyer_name, primary=_primary(facts, lang), reason=_reason(facts, lang),
        money=_money(facts, lang), packages=card, more=more,
        over_your_limits=_over_your_limits(facts, lang, economics), ask=ask_answer(facts, ask, lang) if ask is not None else None,
        levers=[_lever(facts, m, lang) for m in facts.maxima], zone=zone, refused=None,
        unlisted_counters=[_unlisted_sentence(c, lang) for c in facts.unlisted_counters],
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
                              mandate, v.cur, face_of(v.ctx), bool(v.ranges.terms), (), (), (), {}, None, None,
                              False, 0, 0.0)
        out.append(_package(facts, v.probe(Setting(pkg.terms_days, pkg.price_bp, pkg.early_pay_bp, pkg.early_pay_face_fen,
                                                   pkg.rebate_bp)), lang))
    return out


def envelope(books: Books, mandate: Mandate, *, store: LedgerStore | None = None, day: int, buyer_id: str,
             trusted_owner_key_hex: str, commitments: Sequence[Commitment] = (), zone: bool = False,
             full_grid: bool = False, lang: str = "en", ask: int | None = None) -> EnvelopeAnswer:
    """The Safe Deal Envelope for one buyer: the sweep (`envelope_facts`) worded in `lang`. A buyer with no lever is
    answered with `refused` set and empty lists, not an error."""
    facts = envelope_facts(books, mandate, store=store, day=day, buyer_id=buyer_id, trusted_owner_key_hex=trusted_owner_key_hex,
                           commitments=commitments, zone=zone, full_grid=full_grid)
    asked = None
    if ask is not None and not facts.refused:
        asked = envelope_ask(books, mandate, day=day, buyer_id=buyer_id, trusted_owner_key_hex=trusted_owner_key_hex,
                             terms=ask, commitments=commitments)
    return envelope_answer(facts, lang, asked)


__all__ = [
    "AskAnswer",
    "AskFacts",
    "Economics",
    "EnvelopeAnswer",
    "EnvelopeFacts",
    "EnvelopeLever",
    "EnvelopePackage",
    "ZoneEntry",
    "ZoneFacts",
    "ask_answer",
    "authority_of",
    "compensate",
    "envelope",
    "envelope_answer",
    "envelope_ask",
    "envelope_facts",
    "envelope_zone",
    "out_of_range_facts",
    "probe_packages",
]
