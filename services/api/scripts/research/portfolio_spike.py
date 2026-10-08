"""Spike 2, the multi-deal portfolio: which of several open deals to accept, counter or reject together.

Read-only research (wayfinder map #39, ticket #43). The fixture offers named on the command line are compiled and
evaluated on the golden books. Each deal gets a candidate set (accept as asked, each counter the verifier offers,
reject). The combinations are enumerated through `current_books(...).with_()` and the router's `plan()`, the forward
value of every package is taken from `value_concessions` and held against the mandate's caps, and the feasible
portfolios are ranked lexicographically: no hard-constraint breach (a filter), then the mandate (owner decisions
the portfolio needs), then cost (interest + fees + discounts the projection posts, plus the forward value of the
concessions at the marginal rate).

Pruning, as the deep dive describes it: a package that the verifier does not permit alone is dropped before the
enumeration; a partial choice whose forward value already exceeds the aggregate or a per-buyer cap is cut with
everything below it (budget monotonicity: every package adds at least zero); the router is called once per distinct
set of cash-moving packages, because a package that leaves the projection unchanged (a rebate, an operational
concession) interacts with the others through the caps alone (buyer separability).

    FLOW_RESEARCH_SPIKES=1 uv run --project services/api python services/api/scripts/research/portfolio_spike.py \\
        [EX01_PACKAGE EX08A EX08B ...] [--json]
"""

from __future__ import annotations

import _common

_common.require_flag()

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import prod
from typing import Any

_common.quiet_logs()

from app.books import current_books
from app.compiler import compile_offer
from app.domain.fixtures import load_offers, load_scenario, offer_documents
from app.domain.models import (
    CompiledOffer,
    FundingPlan,
    Mode,
    Obligation,
    Outcome,
    Tier,
    Verdict,
    ViolationCode,
)
from app.financial import EngineError, project, value_concessions
from app.funding import marginal_cost
from app.funding import plan as funding_plan
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate, evaluate_many
from app.verifier.evaluate import _forward_total, clear_caches, counter_recheck

PERMITTED_CODES = frozenset({ViolationCode.AGG_CONCESSION_EXCEEDED, ViolationCode.PER_BUYER_CAP_EXCEEDED,
                             ViolationCode.RESERVE_BREACH})  # re-tested jointly, by the caps and by plan()
DEFAULT_DEALS = ("EX01_PACKAGE", "EX08A", "EX08B")


def resolve(name: str) -> str:
    """EX01 / EX08A / EX01_PACKAGE -> the fixture id."""
    offers = load_offers()
    if name in offers:
        return name
    hits = [oid for oid in offers if oid.split("_")[0] == name]
    if len(hits) != 1:
        raise SystemExit(f"refused: '{name}' is not one fixture offer ({', '.join(sorted(offers)[:8])} ...)")
    return hits[0]


def short(oid: str) -> str:
    return oid.split("_")[0]


@dataclass(frozen=True)
class Candidate:
    deal: str
    buyer: str
    label: str  # "reject", "as asked", "Option A" ...
    rank: int  # 0 reject, then counters, then as asked: the order of how much of the ask is granted
    obligations: tuple[Obligation, ...]
    net_fen: int  # the forward value a commitment on this package books (net new value, floored at 0)
    inert: bool  # the projection with the package is the projection without it (no cash effect inside the horizon)
    alone_outcome: str
    alone_codes: tuple[str, ...]
    needs_owner: bool
    permitted: bool

    @property
    def key(self) -> tuple[str, str]:
        return (self.deal, self.label)


@dataclass
class Portfolio:
    choice: tuple[Candidate, ...]
    feasible: bool
    reason: str = ""
    need_fen: int = 0
    funding_cost_fen: int = 0
    posted_cost_fen: int = 0
    concession_fen: int = 0
    forward_total_fen: int = 0
    approvals: int = 0
    plan_label: str = ""
    binding: str = ""

    @property
    def cost_fen(self) -> int:
        return self.posted_cost_fen + self.concession_fen

    @property
    def name(self) -> str:
        return " | ".join(f"{short(c.deal)}: {c.label}" for c in self.choice)


@dataclass
class Stats:
    raw_packages: int = 0
    candidates_dropped: int = 0
    packages_removed_by_dropped_candidates: int = 0
    pruned_by_budget: int = 0
    leaves_evaluated: int = 0
    plan_calls: int = 0
    plan_calls_saved_by_separability: int = 0
    infeasible: int = 0
    feasible: int = 0
    seconds_prepare: float = 0.0
    seconds_enumerate: float = 0.0
    reasons: dict[str, int] = field(default_factory=dict)


class Spike:
    def __init__(self, deals: Sequence[str], prune: bool = True) -> None:
        self.prune = prune
        self.show_infeasible = False
        self.state, _ = load_scenario()
        self.mandate = load_signed_mandate()
        self.key = demo_owner_public_key_hex()
        self.books = current_books(self.state, ())
        self.deals = [resolve(d) for d in deals]
        if len(set(self.deals)) != len(self.deals):
            raise SystemExit("refused: a deal is named twice")
        rate, rate_id = marginal_cost(self.state, self.mandate)
        self.rate, self.rate_label = rate, f"committed marginal source {rate_id}"
        self.existing = sum(fc.value_fen for fc in self.state.forward_concessions)
        self.base_traj = project(self.state, self.books.with_([]), [], Mode.CONSERVATIVE, self.mandate.horizon_days,
                                 self.mandate.min_cash_fen)
        self.offers: dict[str, CompiledOffer] = {}
        self.bundles: dict[str, Any] = {}
        self.lists: list[list[Candidate]] = []
        self.dropped: list[Candidate] = []
        self.plans: dict[tuple[tuple[str, str], ...], tuple[FundingPlan, int] | str] = {}
        self.reached_router = 0  # leaves of the enumeration that needed the router's answer
        self.stats = Stats()

    # ------------------------------------------------------------ candidates

    def _net(self, obs: Sequence[Obligation]) -> int:
        values = value_concessions(list(obs), self.state, self.rate, self.rate_label,
                                   self.mandate.forward_concession_horizon_days)
        return _forward_total(list(obs), values, self.state) - self.existing

    def _inert(self, obs: Sequence[Obligation]) -> bool:
        """The package leaves cash, debt, the monthly ratios and the postings as they are inside the horizon."""
        t = project(self.state, self.books.with_(obs), [], Mode.CONSERVATIVE, self.mandate.horizon_days,
                    self.mandate.min_cash_fen)
        b = self.base_traj
        same_days = all((x.opening_fen, x.closing_fen, x.debt_outstanding_fen) == (y.opening_fen, y.closing_fen, y.debt_outstanding_fen)
                        for x, y in zip(t.days, b.days, strict=True))
        return (same_days and t.months == b.months and t.interest_posted_fen == b.interest_posted_fen
                and t.fees_posted_fen == b.fees_posted_fen and t.discounts_posted_fen == b.discounts_posted_fen)

    def _candidate(self, deal: str, buyer: str, label: str, rank: int, obs: Sequence[Obligation], v: Verdict) -> Candidate:
        codes = tuple(dict.fromkeys(x.code.value for x in v.violations))
        permitted = all(x.code in PERMITTED_CODES for x in v.violations) and v.outcome not in (Outcome.NO_VERDICT,)
        try:
            net, inert = self._net(obs), self._inert(obs)
        except EngineError:
            net, inert, permitted = 0, False, False
        return Candidate(deal, buyer, label, rank, tuple(obs), net, inert, v.outcome.value, codes,
                         v.required_tier != Tier.TIER_1, permitted)

    def prepare(self) -> None:
        recheck = counter_recheck(self.state, self.mandate, trusted_owner_key_hex=self.key)
        for oid in self.deals:
            o = load_offers()[oid]
            offer = compile_offer(offer_documents(oid), o["counterparty_id"])
            self.offers[oid] = offer
            b = evaluate(offer, self.state, self.mandate, trusted_owner_key_hex=self.key,
                         owner_declared=dict(o.get("declared_costs") or {}), plans="committed")
            self.bundles[oid] = b
            buyer = offer.counterparty_id
            cands = [Candidate(oid, buyer, "reject", 0, (), 0, True, "REJECT (nothing booked)", (), False, True)]
            for i, c in enumerate(b.verdict.counters, 1):
                cands.append(self._candidate(oid, buyer, c.label, i, c.obligations, recheck(c)))
            cands.append(self._candidate(oid, buyer, "as asked", len(cands), b.bound_obligations, b.verdict))
            self.lists.append([c for c in cands if c.permitted or not self.prune])
            self.dropped += [c for c in cands if not c.permitted and self.prune]
        self.all_candidates = {c.key: c for lst in self.lists for c in lst} | {c.key: c for c in self.dropped}

    # ------------------------------------------------------------ one combination

    def caps(self, choice: Sequence[Candidate]) -> str:
        total = self.existing + sum(c.net_fen for c in choice)
        if total > self.mandate.max_aggregate_forward_concession_fen:
            return ViolationCode.AGG_CONCESSION_EXCEEDED.value
        for buyer, cap in self.mandate.per_buyer_caps_fen.items():
            held = sum(fc.value_fen for fc in self.state.forward_concessions if fc.counterparty_id == buyer)
            if held + sum(c.net_fen for c in choice if c.buyer == buyer) > cap:
                return ViolationCode.PER_BUYER_CAP_EXCEEDED.value
        return ""

    def routed(self, choice: Sequence[Candidate]) -> tuple[FundingPlan, int] | str:
        """The router and the projection for the cash-moving packages of `choice`, once per distinct set of them."""
        sig = tuple(c.key for c in choice if not c.inert)
        hit = self.plans.get(sig)
        if hit is not None:
            return hit
        obs = self.books.with_([o for c in choice if not c.inert for o in c.obligations])
        self.stats.plan_calls += 1
        try:
            p = funding_plan(self.state, obs, self.mandate)
            traj = project(self.state, obs, p.actions, Mode.CONSERVATIVE, self.mandate.horizon_days,
                           self.mandate.min_cash_fen)
        except EngineError as e:
            out: tuple[FundingPlan, int] | str = f"CONFLICT ({type(e).__name__}: two packages cannot both be booked)"
        else:
            posted = traj.interest_posted_fen + traj.fees_posted_fen + traj.discounts_posted_fen
            out = (p, posted) if p.admissible else f"RESERVE_NOT_HELD (no admissible plan: {p.label})"
        self.plans[sig] = out
        return out

    def explain(self, choice: Sequence[Candidate]) -> str:
        """Why `choice` is infeasible (empty: it is feasible). Cheap checks first; the router only when they pass."""
        bad = [c for c in choice if not c.permitted]
        note = " (and not acceptable alone)" if bad else ""
        capped = self.caps(choice)
        if capped:
            return {"AGG_CONCESSION_EXCEEDED": "forward budget", "PER_BUYER_CAP_EXCEEDED": "per-buyer cap"}[capped] + note
        if bad:
            return "not acceptable alone: " + "; ".join(
                f"{short(c.deal)} {c.label} ({', '.join(c.alone_codes) or c.alone_outcome})" for c in bad)
        r = self.routed(choice)
        return r if isinstance(r, str) else ""

    def build(self, choice: tuple[Candidate, ...]) -> Portfolio:
        why = self.explain(choice)
        if not why or why.startswith(("RESERVE_NOT_HELD", "CONFLICT")):
            self.reached_router += 1
        if why:
            out = Portfolio(choice, False, why)
            if not self.prune:  # unpruned run: show what the router said anyway
                r = self.routed(choice)
                if not isinstance(r, str):
                    out.need_fen, out.funding_cost_fen, out.posted_cost_fen = r[0].need_fen, r[0].total_cost_fen, r[1]
                    out.concession_fen = sum(c.net_fen for c in choice)
                    out.forward_total_fen = self.existing + out.concession_fen
            return out
        r = self.routed(choice)
        assert not isinstance(r, str)
        p, posted = r
        concession = sum(c.net_fen for c in choice)
        approvals = sum(1 for c in choice if c.needs_owner) + sum(1 for x in p.costs if x.needs_owner_approval)
        return Portfolio(choice, True, "", p.need_fen, p.total_cost_fen, posted, concession,
                         self.existing + concession, approvals, p.label)

    # ------------------------------------------------------------ the enumeration

    def run(self) -> list[Portfolio]:
        t0 = time.perf_counter()
        self.prepare()
        self.stats.seconds_prepare = time.perf_counter() - t0
        full = [[*lst, *[d for d in self.dropped if d.deal == lst[0].deal]] for lst in self.lists]
        self.stats.raw_packages = prod(len(f) for f in full)
        self.stats.candidates_dropped = len(self.dropped)
        self.stats.packages_removed_by_dropped_candidates = self.stats.raw_packages - prod(len(x) for x in self.lists)
        for d in self.dropped:  # how many packages each dropped candidate took out, and why
            others = prod(len(f) for f in full if f[0].deal != d.deal)
            key = f"dropped before enumeration: {short(d.deal)} {d.label} is not acceptable alone ({', '.join(d.alone_codes)})"
            self.stats.reasons[key] = others
        t1 = time.perf_counter()
        out: list[Portfolio] = []
        n = len(self.lists)

        def dfs(i: int, chosen: tuple[Candidate, ...]) -> None:
            if i == n:
                self.stats.leaves_evaluated += 1
                out.append(self.build(chosen))
                return
            for c in self.lists[i]:
                nxt = (*chosen, c)
                if self.prune and self.caps(nxt):  # budget monotonicity: each package adds >= 0, so nothing below can fit
                    cut = prod(len(x) for x in self.lists[i + 1:])
                    self.stats.pruned_by_budget += cut
                    key = "cut before evaluation: " + ("forward budget" if self.caps(nxt) == "AGG_CONCESSION_EXCEEDED" else "per-buyer cap")
                    self.stats.reasons[key] = self.stats.reasons.get(key, 0) + cut
                    continue
                dfs(i + 1, nxt)

        dfs(0, ())
        self.stats.plan_calls_saved_by_separability = self.reached_router - len(self.plans)
        for p in out:
            if p.feasible:
                self.stats.feasible += 1
            else:
                self.stats.infeasible += 1
                self.stats.reasons[p.reason] = self.stats.reasons.get(p.reason, 0) + 1
        out.sort(key=lambda p: (not p.feasible, p.approvals, p.cost_fen, p.name))
        for p in out:
            if p.feasible:
                p.binding = self.binding(p)
        self.stats.seconds_enumerate = time.perf_counter() - t1
        return out

    def binding(self, p: Portfolio) -> str:
        """What blocks the next step up: each deal moved to a package that grants more of the ask, one at a time."""
        blocked: dict[str, list[str]] = {}
        for i, cur in enumerate(p.choice):
            for up in self.all_candidates.values():
                if up.deal != cur.deal or up.rank <= cur.rank:
                    continue
                why = self.explain((*p.choice[:i], up, *p.choice[i + 1:]))
                if why:
                    blocked.setdefault(why, []).append(f"{short(up.deal)} {up.label}")
        if not blocked:
            return "none: every deal is already at its fullest feasible package"
        return "; ".join(f"{', '.join(dict.fromkeys(v))} -> {k}" for k, v in blocked.items())


# ---------------------------------------------------------------- output


def greedy_choice(spike: Spike, outcomes: dict[str, str]) -> tuple[Candidate, ...]:
    """The portfolio the sequential joint check yields: accept each offer that passes, take no counter, reject the rest."""
    pick: list[Candidate] = []
    for lst, d in zip(spike.lists, spike.deals, strict=True):
        asked = next((c for c in spike.all_candidates.values() if c.deal == d and c.label == "as asked"), None)
        reject = next(c for c in lst if c.label == "reject")
        pick.append(asked if asked is not None and outcomes[short(d)] in ("ACCEPT", "NEEDS_OWNER_APPROVAL") else reject)
    return tuple(pick)


def greedy(spike: Spike, ranked: Sequence[Portfolio] = ()) -> dict[str, Any]:
    """What `evaluate_many` (the engine's own sequential, cap-only joint check) does with the offers as asked, in order,
    and where the portfolio it yields stands in the enumeration."""
    bundles = evaluate_many([spike.offers[d] for d in spike.deals], spike.state, spike.mandate,
                            trusted_owner_key_hex=spike.key,
                            owner_declared={k: v for d in spike.deals
                                            for k, v in (load_offers()[d].get("declared_costs") or {}).items()})
    outcomes = {short(d): b.verdict.outcome.value for d, b in zip(spike.deals, bundles, strict=True)}
    choice = greedy_choice(spike, outcomes)
    feas = [p for p in ranked if p.feasible]
    where = next((i for i, p in enumerate(feas, 1) if tuple(c.key for c in p.choice) == tuple(c.key for c in choice)), None)
    mine = feas[where - 1] if where else None
    return {"order": [short(d) for d in spike.deals],
            "portfolio": {short(c.deal): c.label for c in choice},
            "rank_in_enumeration": where, "feasible_portfolios": len(feas),
            "cost_for_ranking": _common.money(mine.cost_fen) if mine else None,
            "best_cost_for_ranking": _common.money(feas[0].cost_fen) if feas else None,
            "outcomes": outcomes,
            "codes": {short(d): list(dict.fromkeys(x.code.value for x in b.verdict.violations))
                      for d, b in zip(spike.deals, bundles, strict=True)},
            "counters": {short(d): [c.label for c in b.verdict.counters] for d, b in zip(spike.deals, bundles, strict=True)}}


def to_json(spike: Spike, ranked: list[Portfolio], seconds: float, top: int | None) -> dict[str, Any]:
    cap = spike.mandate.max_aggregate_forward_concession_fen

    def row(rank: int | None, p: Portfolio) -> dict[str, Any]:
        d: dict[str, Any] = {"rank": rank, "packages": {short(c.deal): c.label for c in p.choice}, "feasible": p.feasible}
        if p.feasible:
            d.update({"need": _common.money(p.need_fen), "funding_cost": _common.money(p.funding_cost_fen),
                      "posted_cost": _common.money(p.posted_cost_fen), "concession_value": _common.money(p.concession_fen),
                      "cost_for_ranking": _common.money(p.cost_fen),
                      "budget_used": _common.money(p.forward_total_fen), "budget_cap": _common.money(cap),
                      "owner_decisions": p.approvals, "binding": p.binding, "plan": p.plan_label})
        else:
            d["reason"] = p.reason
        return d

    feas = [p for p in ranked if p.feasible]
    s = spike.stats
    return {
        "spike": "portfolio", "deals": [short(d) for d in spike.deals],
        "candidates": {short(d): [{"label": c.label, "alone": c.alone_outcome, "alone_codes": list(c.alone_codes),
                                   "forward_value": _common.money(c.net_fen), "moves_cash": not c.inert,
                                   "enumerated": c.permitted}
                                  for c in sorted(spike.all_candidates.values(), key=lambda c: c.rank) if c.deal == d]
                       for d in spike.deals},
        "ranked": [row(i, p) for i, p in enumerate(feas[:top] if top else feas, 1)],
        "infeasible": [{"packages": {short(c.deal): c.label for c in p.choice}, "reason": p.reason,
                        "need": _common.money(p.need_fen) if p.need_fen else None,
                        "funding_cost": _common.money(p.funding_cost_fen) if p.need_fen else None,
                        "concession_value": _common.money(p.concession_fen) if p.concession_fen else None}
                       for p in ranked if not p.feasible],
        "infeasible_reasons": s.reasons,
        "counts": {"all_packages": s.raw_packages, "candidates_dropped_alone": s.candidates_dropped,
                   "packages_removed_by_dropped_candidates": s.packages_removed_by_dropped_candidates,
                   "pruned_by_budget": s.pruned_by_budget, "evaluated": s.leaves_evaluated, "feasible": s.feasible,
                   "infeasible": s.infeasible, "router_calls": s.plan_calls,
                   "router_calls_saved_by_separability": s.plan_calls_saved_by_separability,
                   "removed_by_pruning_in_total": s.raw_packages - s.leaves_evaluated},
        "greedy_evaluate_many": greedy(spike, ranked),
        "seconds": {"prepare_candidates": round(s.seconds_prepare, 3), "enumerate_and_rank": round(s.seconds_enumerate, 3),
                    "total": round(seconds, 3)},
    }


def render(spike: Spike, ranked: list[Portfolio], seconds: float, top: int | None) -> str:
    s = spike.stats
    cap = spike.mandate.max_aggregate_forward_concession_fen
    budget = (f"Forward budget {_common.yuan_text(cap)}; already booked {_common.yuan_text(spike.existing)}; "
              f"concessions valued at the {spike.rate_label} rate.")
    out = [f"PORTFOLIO of {', '.join(short(d) for d in spike.deals)} on the golden books (day 0). READ-ONLY, hypothetical.",
           budget, "", "Candidates per deal (alone = the verifier on that package by itself):"]
    rows = []
    for d in spike.deals:
        for c in sorted((x for x in spike.all_candidates.values() if x.deal == d), key=lambda x: x.rank):
            rows.append([short(d), c.label, c.alone_outcome, ", ".join(c.alone_codes) or "-", _common.yuan_text(c.net_fen),
                         "no" if c.inert else "yes", "yes" if c.permitted else "DROPPED"])
    out.append(_common.table(["Deal", "Package", "Alone", "Codes alone", "Forward value", "Moves cash", "Enumerated"], rows))
    feas = [p for p in ranked if p.feasible]
    shown = feas[:top] if top else feas
    ranked_title = (f"Ranked feasible portfolios ({len(shown)} of {len(feas)}): no hard breach, then owner decisions needed, "
                    "then posted cost + concession value")
    out += ["", ranked_title, ""]
    prow = []
    for i, p in enumerate(shown, 1):
        prow.append([i, p.name, _common.yuan_text(p.need_fen), _common.yuan_text(p.funding_cost_fen),
                     _common.yuan_text(p.posted_cost_fen), _common.yuan_text(p.concession_fen),
                     _common.yuan_text(p.cost_fen), f"{_common.yuan_text(p.forward_total_fen)} of {_common.yuan_text(cap)}",
                     p.approvals, p.binding])
    out.append(_common.table(["#", "Portfolio", "Need", "Funding cost", "Posted cost", "Concessions", "Cost + concessions",
                              "Budget use", "Owner decisions", "Binding: what blocks the next step up"], prow))
    out += ["", "Packages that are not in the ranked table, by reason:"]
    out.append(_common.table(["Reason", "Packages"], [[k, v] for k, v in sorted(s.reasons.items(), key=lambda kv: -kv[1])] or [["-", 0]]))
    if spike.show_infeasible:
        bad = [p for p in ranked if not p.feasible]
        out += ["", "Evaluated and infeasible:"]
        out.append(_common.table(["Portfolio", "Need", "Funding cost", "Budget use", "Why not"], [
            [p.name, _common.yuan_text(p.need_fen) if p.need_fen else "-", _common.yuan_text(p.funding_cost_fen) if p.need_fen else "-",
             _common.yuan_text(p.forward_total_fen) if p.need_fen else "-", p.reason] for p in bad]))
    g = greedy(spike, ranked)
    seq = "; ".join(f"{k} {v}" for k, v in g["outcomes"].items())
    where = (f"it is #{g['rank_in_enumeration']} of {g['feasible_portfolios']} at {g['cost_for_ranking']['display']} "
             f"against {g['best_cost_for_ranking']['display']} for #1" if g["rank_in_enumeration"] else "it is not feasible")
    mine = ", ".join(f"{k}: {v}" for k, v in g["portfolio"].items())
    out += ["", f"For comparison, the engine's own sequential joint check (evaluate_many, offers as asked, in this order): {seq}.",
            f"The portfolio it yields (accept what passes, take no counter) is {mine}; {where}."]
    pruning = (f"Pruning removed {s.raw_packages - s.leaves_evaluated}: {s.packages_removed_by_dropped_candidates} by dropping "
               f"{s.candidates_dropped} package(s) the verifier will not accept alone, {s.pruned_by_budget} by the budget cut."
               if spike.prune else "No pruning (--no-prune): every package was evaluated.")
    shape = " x ".join(str(len(spike.lists[i]) + len([d for d in spike.dropped if d.deal == spike.deals[i]]))
                       for i in range(len(spike.deals)))
    counts = (f"Packages: {s.raw_packages} in all ({shape}). {pruning} Evaluated {s.leaves_evaluated} ({s.feasible} feasible, "
              f"{s.infeasible} not); the router ran {s.plan_calls} times "
              f"({s.plan_calls_saved_by_separability} calls saved because the other packages do not move cash).")
    timing = (f"Wall time {_common.seconds_text(seconds)}: candidates {_common.seconds_text(s.seconds_prepare)}, "
              f"enumeration and ranking {_common.seconds_text(s.seconds_enumerate)}.")
    out += ["", counts, timing]
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deals", nargs="*", help="fixture offers (EX01, EX08A, EX08B, EX05, EX06 ...); default EX01_PACKAGE EX08A EX08B")
    ap.add_argument("--top", type=int, default=10, help="rows of the ranked table (0: all)")
    ap.add_argument("--no-prune", action="store_true",
                    help="enumerate every package (no dropped candidates, no budget cut): the soundness and speed check")
    ap.add_argument("--show-infeasible", action="store_true", help="also list the packages that failed after evaluation")
    ap.add_argument("--json", action="store_true", help="print one JSON document (fen and display strings)")
    args = ap.parse_args(argv)
    clear_caches()
    watch = _common.Stopwatch()
    spike = Spike(args.deals or DEFAULT_DEALS, prune=not args.no_prune)
    ranked = spike.run()
    seconds = watch.seconds()
    top = args.top or None
    spike.show_infeasible = args.show_infeasible
    print(_common.dump(to_json(spike, ranked, seconds, top)) if args.json else render(spike, ranked, seconds, top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
