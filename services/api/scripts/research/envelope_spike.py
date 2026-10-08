"""Spike 1, the Safe Deal Envelope: what can the supplier offer one buyer, as the verifier itself decides it.

Read-only research (wayfinder map #39, ticket #43). For a buyer on the golden books it searches, by bisection over the
real verifier (`app.whatif.offer.build` -> `app.verifier.evaluate`, the what-if sandbox's own call):

  1. the longest terms the verifier permits (alone; and with the forward budget ignored, liquidity only),
  2. the region terms days x price adjustment (5-day steps x 5 bp steps): the smallest price that makes each terms
     value pass,
  3. the largest early-payment discount on each face asked about,
  4. the largest rebate within the forward budget,

then it assembles approved packages (terms, price, early payment, rebate), each re-evaluated whole by the verifier,
with the verifier's binding violation codes when one fails and the cure cost when liquidity needs one.

    FLOW_RESEARCH_SPIKES=1 uv run --project services/api python services/api/scripts/research/envelope_spike.py [--json]

Every figure is an engine output formatted with fmt_yuan / fmt_pct. A lever outside the mandate's own ranges is refused.
"""

from __future__ import annotations

import _common

_common.require_flag()

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from functools import partial
from typing import Any, NamedTuple

_common.quiet_logs()

from app.domain.fixtures import load_scenario
from app.domain.models import FinancialState, Mandate, Outcome, ViolationCode
from app.financial import value_concessions
from app.funding import marginal_cost
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import bind, evaluate
from app.verifier.counters import infeasibility, smallest_step_covering
from app.verifier.evaluate import clear_caches
from app.whatif.offer import Context, build, context
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
CURE_FLAGS = {"cure_needs_owner_approval": "the cure needs the owner's approval",
              "cure_executable_now": "the cure cannot run today"}


class Lever(NamedTuple):
    """One package on the what-if grid. `face` is the early-pay face in fen (None: the whole open invoice)."""

    terms: int
    price: int = 0
    discount: int = 0
    face: int | None = None
    rebate: int = 0


@dataclass(frozen=True)
class Probe:
    """What the verifier said about one lever setting."""

    lever: Lever
    outcome: str
    tier: str
    passes: bool
    liquidity_only: bool  # passes if the forward budget is ignored (every violation is a cap code or a curable reserve breach)
    codes: tuple[str, ...]
    binding: tuple[str, ...]  # the codes that make it fail (a curable reserve breach does not)
    forward_total_fen: int
    reserve_day: int | None
    reserve_curable: bool | None
    cure_cost_fen: int | None
    cure_flags: tuple[str, ...]
    counter_faces_fen: tuple[int, ...]  # early-pay faces of the verifier's own counters (Option A)
    recheck: str | None  # why the package would fail the re-check every counter must pass (None: it would pass)
    seconds: float


@dataclass(frozen=True)
class Ranges:
    terms: tuple[int, ...]
    price: tuple[int, ...]
    discount: tuple[int, ...]
    rebate: tuple[int, ...]
    face_max_fen: int
    discount_cap_source: str


def ranges_for(ctx: Context, mandate: Mandate) -> Ranges:
    """The levers' own ranges: the what-if grid, with the discount held to the mandate's immediate-discount cap."""
    cap = DISCOUNT_MAX_BP if mandate.max_immediate_discount_bp is None else min(DISCOUNT_MAX_BP, mandate.max_immediate_discount_bp)
    source = "the what-if grid" if mandate.max_immediate_discount_bp is None else "the mandate's immediate-discount cap"
    current = ctx.recurring.terms_days
    return Ranges(
        terms=tuple(range(min(TERMS_MIN, current), TERMS_MAX + 1, TERMS_STEP)),
        price=tuple(range(0, PRICE_MAX_BP + 1, RATE_STEP_BP)),
        discount=tuple(range(0, cap + 1, RATE_STEP_BP)),
        rebate=tuple(range(0, REBATE_MAX_BP + 1, RATE_STEP_BP)),
        face_max_fen=ctx.receivable.face_fen - ctx.receivable.face_fen % FACE_STEP_FEN,
        discount_cap_source=source,
    )


def refusals(lever: Lever, r: Ranges, ctx: Context) -> list[str]:
    """Why a lever setting lies outside the mandate's own ranges (empty: inside)."""
    out: list[str] = []
    if lever.terms not in r.terms:
        out.append(f"terms {lever.terms} days is outside {r.terms[0]}-{r.terms[-1]} by {TERMS_STEP}")
    if lever.price not in r.price:
        out.append(f"price adjustment {lever.price} bp is outside 0-{r.price[-1]} bp by {RATE_STEP_BP}")
    if lever.discount not in r.discount:
        out.append(f"early-pay discount {lever.discount} bp is outside 0-{r.discount[-1]} bp by {RATE_STEP_BP} "
                   f"({r.discount_cap_source})")
    if lever.rebate not in r.rebate:
        out.append(f"rebate {lever.rebate} bp is outside 0-{r.rebate[-1]} bp by {RATE_STEP_BP}")
    if lever.face is not None and (lever.face <= 0 or lever.face % FACE_STEP_FEN or lever.face > ctx.receivable.face_fen):
        out.append(f"face {_common.yuan_text(lever.face)} is not a whole multiple of ¥100 within the open "
                   f"{ctx.receivable.id} ({_common.yuan_text(ctx.receivable.face_fen)})")
    return out


class Envelope:
    """The verifier behind a memo, counting the evaluations it actually runs."""

    def __init__(self, state: FinancialState, mandate: Mandate, key: str, ctx: Context, ranges: Ranges) -> None:
        self.state, self.mandate, self.key, self.ctx, self.ranges = state, mandate, key, ctx, ranges
        self.memo: dict[Lever, Probe] = {}
        self.lookups = 0

    @property
    def evaluations(self) -> int:
        return len(self.memo)

    def norm(self, lever: Lever) -> Lever:
        if lever.discount == 0 or lever.face == self.ctx.receivable.face_fen:
            return lever._replace(face=None, discount=lever.discount)
        return lever

    def probe(self, lever: Lever) -> Probe:
        lever = self.norm(lever)
        self.lookups += 1
        hit = self.memo.get(lever)
        if hit is not None:
            return hit
        problems = refusals(lever, self.ranges, self.ctx)
        if problems:
            raise ValueError("refused: " + "; ".join(problems))
        params = WhatIfParams(terms_days=lever.terms, discount_bp=lever.discount, rebate_bp=lever.rebate,
                              price_adjustment_bp=lever.price, settle_face_fen=lever.face)
        offer, _ = build(params, self.ctx)
        started = time.perf_counter()
        v = evaluate(offer, self.state, self.mandate, trusted_owner_key_hex=self.key, plans="committed").verdict
        seconds = time.perf_counter() - started
        reserve = next((x for x in v.violations if x.code == ViolationCode.RESERVE_BREACH), None)
        curable_reserve = reserve is not None and bool(reserve.curable)
        binding = tuple(dict.fromkeys(x.code.value for x in v.violations
                                      if not (x.code == ViolationCode.RESERVE_BREACH and x.curable)))
        liquidity_only = all(x.code in CAP_CODES or (x.code == ViolationCode.RESERVE_BREACH and x.curable)
                             for x in v.violations) and v.outcome != Outcome.NO_VERDICT
        faces = tuple(o.base.amount_fen for c in v.counters for o in c.obligations
                      if o.base.amount_fen is not None and o.rate_bp is not None and o.days_delta is None
                      and o.type.value == "IMMEDIATE_DISCOUNT")
        p = Probe(
            lever=lever, outcome=v.outcome.value, tier=v.required_tier.value, passes=v.outcome in PASSING,
            liquidity_only=liquidity_only, codes=tuple(dict.fromkeys(x.code.value for x in v.violations)),
            binding=binding, forward_total_fen=v.forward_concession_total_fen,
            reserve_day=reserve.day if reserve else None, reserve_curable=reserve.curable if reserve else None,
            cure_cost_fen=reserve.cure_cost_fen if reserve and curable_reserve else None,
            cure_flags=tuple(w for k, w in CURE_FLAGS.items() if reserve is not None and k in reserve.inputs),
            counter_faces_fen=faces, recheck=infeasibility(v, self.state) if v.outcome in PASSING else None,
            seconds=seconds)
        self.memo[lever] = p
        return p

    def ok(self, lever: Lever) -> bool:
        return self.probe(lever).passes

    def ok_at(self, base: Lever, field_name: str, value: int) -> bool:
        """Does `base` with one lever (`price`, `rebate`, `discount`, `terms`) set to `value` pass?"""
        return self.ok(base._replace(**{field_name: value}))

    def compensating_price(self, terms: int) -> tuple[int | None, int | None]:
        """(per-invoice funding cost of the extension, the smallest 5 bp price step that covers it): the Option B rule
        of `app.verifier.counters`, read from `value_concessions` and `smallest_step_covering`. None below the terms in force."""
        if terms <= self.ctx.recurring.terms_days:
            return None, None
        offer, _ = build(WhatIfParams(terms_days=terms, discount_bp=0, rebate_bp=0), self.ctx)
        bound, _notes = bind(offer, self.state, None)
        ratio, _fid = marginal_cost(self.state, self.mandate)
        values = value_concessions(bound, self.state, ratio, "committed marginal source",
                                   self.mandate.forward_concession_horizon_days)
        per_invoice = next((v.per_invoice_fen for v in values if v.per_invoice_fen), None)
        if per_invoice is None:
            return None, None
        return per_invoice, smallest_step_covering(per_invoice, self.ctx.recurring.face_fen)


# ---------------------------------------------------------------- output records


@dataclass
class Maximum:
    name: str
    wall: str
    value_text: str
    value: int | None
    confirmed: bool
    at_max: Probe | None
    beyond: Probe | None


def _lever_text(p: Probe) -> str:
    lv = p.lever
    parts = [f"{lv.terms}d"]
    if lv.price:
        parts.append(f"+{_common.pct_text(lv.price)}")
    if lv.discount:
        parts.append(f"{_common.pct_text(lv.discount)} early" + (f" on {_common.yuan_text(lv.face)}" if lv.face else ""))
    if lv.rebate:
        parts.append(f"{_common.pct_text(lv.rebate)} rebate")
    return " ".join(parts)


def _probe_json(p: Probe | None) -> dict[str, Any] | None:
    if p is None:
        return None
    lv = p.lever
    return {
        "terms_days": lv.terms, "price_adjustment": _common.rate(lv.price),
        "early_pay": ({"rate": _common.rate(lv.discount), "face": _common.money(lv.face) if lv.face else "whole invoice"}
                      if lv.discount else None),
        "rebate": _common.rate(lv.rebate), "outcome": p.outcome, "tier": p.tier, "passes": p.passes,
        "codes": list(p.codes), "binding_codes": list(p.binding),
        "counter_grade": p.passes and p.recheck is None, "recheck_failure": p.recheck if p.passes else None,
        "forward_budget_used": _common.money(p.forward_total_fen),
        "reserve_breach": ({"day": p.reserve_day, "curable": p.reserve_curable,
                            "cure_cost": _common.money(p.cure_cost_fen) if p.cure_cost_fen is not None else None,
                            "cure_flags": list(p.cure_flags)} if p.reserve_day is not None else None),
    }


def _why(p: Probe | None) -> str:
    if p is None:
        return "none"
    if p.passes:
        return p.outcome
    parts = list(p.binding)
    if p.reserve_day is not None and p.reserve_curable is False:
        parts = [f"{c} (day {p.reserve_day}, not curable)" if c == ViolationCode.RESERVE_BREACH.value else c for c in parts]
    return ", ".join(parts) or p.outcome


def _cure_text(p: Probe) -> str:
    if p.reserve_day is None:
        return "no breach"
    if p.cure_cost_fen is None:
        return f"day {p.reserve_day}, no cure"
    flags = f" ({'; '.join(p.cure_flags)})" if p.cure_flags else ""
    return f"day {p.reserve_day}: cure {_common.yuan_text(p.cure_cost_fen)}{flags}"


# ---------------------------------------------------------------- the spike


@dataclass
class Report:
    buyer: str
    receivable: str
    current_terms: int
    ranges: dict[str, Any]
    maxima: list[Maximum] = field(default_factory=list)
    zone: list[dict[str, Any]] = field(default_factory=list)
    packages: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    requested: list[dict[str, Any]] = field(default_factory=list)
    exhaustive: dict[str, Any] | None = None
    phases: list[dict[str, Any]] = field(default_factory=list)
    grid: list[str] = field(default_factory=list)
    evaluations: int = 0
    lookups: int = 0
    seconds: float = 0.0


def run(buyer: str, faces: list[int] | None, packages: list[Lever], exhaustive: bool) -> tuple[Report, Envelope]:
    state, _ = load_scenario()
    mandate = load_signed_mandate()
    key = demo_owner_public_key_hex()
    only_buyer = state.model_copy(update={
        "recurring_invoices": [r for r in state.recurring_invoices if r.counterparty_id == buyer],
        "receivables": [r for r in state.receivables if r.counterparty_id == buyer or r.status != "OPEN"]})
    try:
        ctx = context(only_buyer)
    except WhatIfParamError as e:
        raise SystemExit(f"refused: {buyer} has no terms lever on these books ({e})") from e
    ranges = ranges_for(ctx, mandate)
    cur = ctx.recurring.terms_days
    env = Envelope(state, mandate, key, ctx, ranges)
    clear_caches()
    watch = _common.Stopwatch()
    report = Report(buyer=buyer, receivable=ctx.receivable.id, current_terms=cur, ranges={
        "terms_days": [ranges.terms[0], ranges.terms[-1], TERMS_STEP], "price_adjustment_bp": [0, ranges.price[-1], RATE_STEP_BP],
        "discount_bp": [0, ranges.discount[-1], RATE_STEP_BP], "discount_range_from": ranges.discount_cap_source,
        "rebate_bp": [0, ranges.rebate[-1], RATE_STEP_BP], "face_step": _common.money(FACE_STEP_FEN),
        "open_invoice": _common.money(ctx.receivable.face_fen)})

    up = [t for t in ranges.terms if t >= cur]

    # 1. terms alone, with the verifier as it is, and with the forward budget ignored
    f = _common.last_true(up, lambda t: env.ok(Lever(t)))
    report.maxima.append(_maximum("Terms (days), alone", "forward budget", f, up, lambda t: Lever(t), env, "d"))
    g = _common.last_true(up, lambda t: env.probe(Lever(t)).liquidity_only)
    report.maxima.append(_maximum("Terms (days), budget ignored", "liquidity (reserve)", g, up, lambda t: Lever(t), env, "d"))

    # 2. the region terms x price: the smallest price that passes each terms value
    zone_rows: list[tuple[int, int | None, bool]] = []
    for t in ranges.terms:
        fp = _common.first_true(ranges.price, partial(env.ok_at, Lever(t), "price"))
        zone_rows.append((t, fp.value, fp.confirmed))
        at = env.probe(Lever(t, price=fp.value if fp.value is not None else ranges.price[-1]))
        per_invoice, comp = env.compensating_price(t)
        report.zone.append({
            "terms_days": t, "min_price_adjustment": _common.rate(fp.value) if fp.value is not None else None,
            "cost_per_invoice": _common.money(per_invoice) if per_invoice is not None else None,
            "price_that_nets_it_to_zero": _common.rate(comp) if comp is not None else None,
            "passes_within_range": fp.value is not None, "neighbours_confirmed": fp.confirmed,
            "at_that_price": _probe_json(at)})
    feasible = [(t, p) for t, p, _ in zone_rows if p is not None]
    if feasible:
        t_best, p_best = feasible[-1]
        report.maxima.append(Maximum(
            "Terms (days), with the price that compensates it", "liquidity (reserve)", f"{t_best} days at +{_common.pct_text(p_best)}",
            t_best, all(c for _, p, c in zone_rows if p is not None), env.probe(Lever(t_best, price=p_best)),
            env.probe(Lever(t_best + TERMS_STEP, price=ranges.price[-1])) if t_best + TERMS_STEP in ranges.terms else None))

    # 3. the early-pay discount on each face asked about
    d_whole = _common.last_true(ranges.discount, lambda d: env.ok(Lever(cur, discount=d)))
    first_fail = next((d for d in ranges.discount if d > (d_whole.value or 0)), None)
    if faces is None:
        faces = []
        if first_fail is not None:  # the verifier's own Option A names the face that makes an early payment worth it;
            # asked for the top of the range, so that the counter's rate is the break-even step and not the buyer's own
            faces = list(dict.fromkeys(env.probe(Lever(cur, discount=ranges.discount[-1])).counter_faces_fen))
    face_list: list[int | None] = [None, *[x for x in faces if x != ctx.receivable.face_fen]]
    early: list[tuple[int | None, _common.Found]] = []
    for face in face_list:
        fd = _common.last_true(ranges.discount, partial(env.ok_at, Lever(cur, face=face), "discount"))
        early.append((face, fd))
        label = f"Early pay on {_common.yuan_text(face if face else ctx.receivable.face_fen)}"
        nxt = next((d for d in ranges.discount if d > (fd.value or 0)), None)
        report.maxima.append(Maximum(
            label, "plan comparison / break-even", "none" if not fd.value else _common.pct_text(fd.value), fd.value,
            fd.confirmed, env.probe(Lever(cur, discount=fd.value or 0, face=face)),
            env.probe(Lever(cur, discount=nxt, face=face)) if nxt is not None else None))

    # 4. the rebate within the forward budget
    rb = _common.last_true(ranges.rebate, lambda r: env.ok(Lever(cur, rebate=r)))
    nxt_r = next((r for r in ranges.rebate if r > (rb.value or 0)), None)
    report.maxima.append(Maximum(
        "Rebate on the expected order", "forward budget", "none" if not rb.value else _common.pct_text(rb.value), rb.value,
        rb.confirmed, env.probe(Lever(cur, rebate=rb.value or 0)),
        env.probe(Lever(cur, rebate=nxt_r)) if nxt_r is not None else None))

    report.phases.append({"phase": "lever searches and the terms x price zone (steps 1 to 4)",
                          "evaluations": env.evaluations, "seconds": round(watch.seconds(), 2)})
    mark = (env.evaluations, watch.seconds())

    # approved packages: for each terms value and early-pay variant, the smallest price that passes, then the
    # largest rebate that still passes at that price; the whole package is one verifier evaluation
    variants: list[tuple[int, int | None]] = [(0, None)] + [(fd.value, face) for face, fd in early if fd.value]
    for t in up:
        for d, face in variants:
            base = Lever(t, discount=d, face=face)
            fp = _common.first_true(ranges.price, partial(env.ok_at, base, "price"))
            if fp.value is None:
                failing = env.probe(base._replace(price=ranges.price[-1], rebate=0))
                report.packages.append(_package(failing, None, fp.confirmed))
                continue
            priced = base._replace(price=fp.value)
            fr = _common.last_true(ranges.rebate, partial(env.ok_at, priced, "rebate"))
            top = priced._replace(rebate=fr.value or 0)
            nxt_rb = next((r for r in ranges.rebate if r > (fr.value or 0)), None)
            report.packages.append(_package(env.probe(top), env.probe(priced._replace(rebate=nxt_rb)) if nxt_rb is not None else None,
                                            fp.confirmed and fr.confirmed))

    report.phases.append({"phase": "approved packages (smallest price, then largest rebate, per terms value and early-pay variant)",
                          "evaluations": env.evaluations - mark[0], "seconds": round(watch.seconds() - mark[1], 2)})

    # packages asked for on the command line
    for lever in packages:
        report.requested.append(_probe_json(env.probe(lever)) or {})

    report.evaluations, report.lookups, report.seconds = env.evaluations, env.lookups, watch.seconds()

    if exhaustive:  # the check the recon asked for: is bisection sound here? scan the whole grid and compare
        before = env.evaluations
        w2 = _common.Stopwatch()
        disagree: list[str] = []
        for t, minp, _ in zone_rows:
            passing = [p for p in ranges.price if env.ok(Lever(t, price=p))]
            scan = passing[0] if passing else None
            if scan != minp:
                disagree.append(f"terms {t}: bisection {minp}, scan {scan}")
            elif scan is not None and passing != [p for p in ranges.price if p >= scan]:
                disagree.append(f"terms {t}: the passing prices are not one run from {scan} up")
        scan_terms = [t for t in up if env.ok(Lever(t))]
        if scan_terms != [t for t in up if t <= (f.value or 0)]:
            disagree.append("terms alone: the passing terms are not one run from the terms in force")
        for t in ranges.terms:
            report.grid.append(f"{t:>3}d  " + "".join("#" if env.ok(Lever(t, price=p)) else "." for p in ranges.price))
        report.exhaustive = {"extra_evaluations": env.evaluations - before, "seconds": round(w2.seconds(), 2),
                             "disagreements": disagree, "bisection_sound_here": not disagree}
    return report, env


def _maximum(name: str, wall: str, found: _common.Found, values: Sequence[int], make: Callable[[int], Lever], env: Envelope,
             unit: str) -> Maximum:
    v = found.value
    nxt = next((x for x in values if v is not None and x > v), None)
    return Maximum(name, wall, "none" if v is None else f"{v} {'days' if unit == 'd' else ''}".strip(), v, found.confirmed,
                   env.probe(make(v)) if v is not None else None, env.probe(make(nxt)) if nxt is not None else None)


def _package(p: Probe, beyond: Probe | None, confirmed: bool) -> dict[str, Any]:
    out = _probe_json(p) or {}
    out["neighbours_confirmed"] = confirmed
    out["next_rebate_step"] = _probe_json(beyond) if beyond is not None else None
    return out


# ---------------------------------------------------------------- printing


PACKAGE_HEADERS = ["#", "Terms", "Price adj.", "Early pay", "Rebate", "Result", "Outcome", "Budget used", "Cure",
                   "Binding codes"]


def _package_row(i: int, p: dict[str, Any]) -> list[object]:
    early = p["early_pay"]
    early_text = "-" if early is None else (
        f"{early['rate']['display']} on "
        f"{early['face']['display'] if isinstance(early['face'], dict) else early['face']}")
    res = p["reserve_breach"]
    if res is None:
        cure = "-"
    elif res["cure_cost"] is None:
        cure = f"day {res['day']}: no cure"
    else:
        flags = f" ({'; '.join(res['cure_flags'])})" if res["cure_flags"] else ""
        cure = f"day {res['day']}: {res['cure_cost']['display']}{flags}"
    result = ("PASS" if p["counter_grade"] else "PASS, cure too late") if p["passes"] else "FAIL"
    return [i, p["terms_days"], p["price_adjustment"]["display"], early_text, p["rebate"]["display"], result, p["outcome"],
            p["forward_budget_used"]["display"], cure, ", ".join(p["binding_codes"]) or "-"]


def render(r: Report) -> str:
    out: list[str] = []
    out.append(f"SAFE DEAL ENVELOPE for {r.buyer} on the golden books (day 0), invoice {r.receivable}, terms in force "
               f"{r.current_terms} days. READ-ONLY, hypothetical: nothing is booked or sent.")
    out.append(f"Levers and their ranges: terms {r.ranges['terms_days'][0]}-{r.ranges['terms_days'][1]} days by {TERMS_STEP}; "
               f"price 0-{_common.pct_text(r.ranges['price_adjustment_bp'][1])} by {_common.pct_text(RATE_STEP_BP)}; "
               f"early pay 0-{_common.pct_text(r.ranges['discount_bp'][1])} ({r.ranges['discount_range_from']}); "
               f"rebate 0-{_common.pct_text(r.ranges['rebate_bp'][1])}. A lever outside them is refused.")
    out.append("")
    out.append("1. Largest value of each lever alone (bisection over the verifier; \"passes\" = ACCEPT or NEEDS_OWNER_APPROVAL)")
    rows = []
    for m in r.maxima:
        beyond = "-" if m.beyond is None else f"{_lever_text(m.beyond)}: {_why(m.beyond)}"
        used = "-" if m.at_max is None else _common.yuan_text(m.at_max.forward_total_fen)
        rows.append([m.name, m.value_text, m.wall, used, "yes" if m.confirmed else "NO", beyond])
    out.append(_common.table(["Lever", "Largest that passes", "Wall", "Budget used", "Neighbours checked", "Next step fails with"], rows))
    out.append("")
    out.append("2. Approved packages (terms, price, early payment, rebate; each is one whole verifier evaluation)")
    out.append(_common.table(PACKAGE_HEADERS, [_package_row(i, p) for i, p in enumerate(r.packages, 1)]))
    out.append("   (price = the smallest that passes at that terms value; rebate = the largest that still passes at that price;")
    out.append("    a FAIL row is the verifier's answer at the largest price in range.)")
    if r.requested:
        out.append("")
        out.append("   Packages asked for (--package):")
        out.append(_common.table(PACKAGE_HEADERS, [_package_row(i, q) for i, q in enumerate(r.requested, 1)]))
    out.append("")
    out.append("3. Safe zone, terms days x price adjustment (no early payment, no rebate): the smallest price that passes")
    zrow = []
    for z in r.zone:
        at = z["at_that_price"]
        res = at["reserve_breach"]
        zrow.append([z["terms_days"], z["min_price_adjustment"]["display"] if z["min_price_adjustment"] else "none in range",
                     z["price_that_nets_it_to_zero"]["display"] if z["price_that_nets_it_to_zero"] else "-",
                     z["cost_per_invoice"]["display"] if z["cost_per_invoice"] else "-", at["outcome"], at["forward_budget_used"]["display"],
                     "-" if res is None else (f"day {res['day']}: " + (res["cure_cost"]["display"] if res["cure_cost"] else "no cure")),
                     ", ".join(at["binding_codes"]) or "-"])
    out.append(_common.table(["Terms", "Smallest price that passes", "Price that nets the cost to zero", "Cost per invoice", "Outcome there", "Budget used", "Reserve breach / cure", "Binding at the largest price"], zrow))
    out.append("")
    if r.exhaustive is not None:
        e = r.exhaustive
        out.append(f"Exhaustive check: {e['extra_evaluations']} further evaluations in {e['seconds']} s; "
                   f"bisection {'agrees with the full scan' if e['bisection_sound_here'] else 'DISAGREES: ' + '; '.join(e['disagreements'])}.")
    if r.grid:
        out.append("Region, terms x price (# passes, . fails; price 0.00% on the left to "
                   f"{_common.pct_text(r.ranges['price_adjustment_bp'][1])} on the right, 0.05% a column):")
        out += ["  " + row for row in r.grid]
    for ph in r.phases:
        out.append(f"  {ph['phase']}: {ph['evaluations']} evaluations, {ph['seconds']} s")
    out.append(f"Evaluations: {r.evaluations} verifier runs ({r.lookups} lookups, the rest from the memo); wall time {_common.seconds_text(r.seconds)} "
               f"(cold start, caches cleared).")
    return "\n".join(out)


def to_json(r: Report) -> dict[str, Any]:
    d = asdict(r)
    d["maxima"] = [{"lever": m.name, "wall": m.wall, "largest_that_passes": m.value_text, "value": m.value,
                    "neighbours_confirmed": m.confirmed, "at_largest": _probe_json(m.at_max),
                    "next_step": _probe_json(m.beyond)} for m in r.maxima]
    d["spike"] = "envelope"
    d["seconds"] = round(r.seconds, 3)
    return d


def parse_package(text: str) -> Lever:
    keys = {"terms": "terms", "price": "price", "discount": "discount", "rebate": "rebate", "face": "face"}
    vals: dict[str, int] = {}
    for part in text.split(","):
        k, _, v = part.partition("=")
        if k.strip() not in keys or not v.strip().lstrip("-").isdigit():
            raise SystemExit(f"refused: package '{text}' must look like terms=60,price=45,discount=85,face=25720000,rebate=0 "
                             f"(bp for rates, fen for the face)")
        vals[keys[k.strip()]] = int(v)
    if "terms" not in vals:
        raise SystemExit("refused: a package needs terms=<days>")
    return Lever(vals["terms"], vals.get("price", 0), vals.get("discount", 0), vals.get("face"), vals.get("rebate", 0))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--buyer", default="BUYER-1", help="buyer id (needs a recurring invoice and an open invoice)")
    ap.add_argument("--face", type=int, action="append", metavar="YUAN",
                    help="early-pay face in yuan (whole ¥100); repeatable. Default: the whole invoice and the face of "
                         "the verifier's own Option A")
    ap.add_argument("--package", action="append", default=[], metavar="K=V,...",
                    help="also evaluate this package, e.g. terms=60,price=45,discount=85,face=25720000,rebate=0")
    ap.add_argument("--exhaustive", action="store_true", help="also scan the whole grid and compare with the bisection")
    ap.add_argument("--json", action="store_true", help="print one JSON document (fen and display strings)")
    args = ap.parse_args(argv)
    faces = None if args.face is None else [y * 100 for y in args.face]
    try:
        report, _env = run(args.buyer, faces, [parse_package(p) for p in args.package], args.exhaustive)
    except ValueError as e:
        sys.stderr.write(f"{e}\n")
        return 2
    print(_common.dump(to_json(report)) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
