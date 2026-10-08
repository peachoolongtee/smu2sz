#!/usr/bin/env python3
"""The strategy backtest (docs/STRATEGY_MVP_BRIEF.md section 9, Wave 6 of map #47).

Replays the e2e scenarios in process, turn by turn, and after every turn asks the strategy modules what they would say
about the books the turn left behind; it then asserts the invariants the brief names and compares the modules with the
recorded oracle (`fixtures/strategy/collections_both.json`) to the fen.

  1. collections: `receivables_worth` after every turn. Per row: "call now" rows are past due; no ceiling exceeds the
     mandate's immediate-discount cap or fails to beat the plan; the row order is the same after `clear_caches()`;
     counts of the turns where the net order differs from the overdue-amount order and the actions' distribution.
  2. curve: `price_curve` at the same turns. Every band equals the spike's pair (`marginal_impact` of the inflow moved 30
     days earlier) at both its ends, no band is above the cost of two billing periods, `flat` iff every band is 0.
  3. differential: the golden day-0 and day-34 books against `collections_both.json`.
  4. envelope: a placeholder until `app.strategy.envelope` is on the branch (see `check_envelope`).

Usage (from the repository root):

    TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \
      uv run --project services/api python services/api/scripts/strategy_backtest.py [--json] [--quick] [--out PATH]

`--quick` replays the golden scenario only and writes no report unless `--out` is given. `--json` prints the result
as JSON on stdout. Exit 1 on any failure. Read-only: nothing here writes to the evals or to a database; after a run,
`git checkout -- services/api/evals` keeps the tree clean.

The scenario runner is reused, not copied: `scripts/run_scenarios.py`'s `InProc` transport (the in-memory runtime and
the TestClient) applies every turn. The one-turn request body is built here the way its `run()` builds it, because
`run()` keeps that inline.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

# The in-process flags, set before anything of the app is imported (the settings are read on first use).
for _key, _value in (("TERMSLEDGER_NO_DOTENV", "1"), ("DATABASE_URL", "memory"), ("LLM_MODE", "cache"),
                     ("PYTHONUTF8", "1"), ("FEATURE_ENVELOPE", "1"), ("FEATURE_PRICE_CURVE", "1"),
                     ("FEATURE_COLLECTIONS_WORTH", "1")):
    os.environ[_key] = _value

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "services" / "api"
if str(API) not in sys.path:
    sys.path.insert(0, str(API))

from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import Books, books_from_store
from app.config import get_settings
from app.domain.models import (
    CompiledOffer,
    Mandate,
    Obligation,
    ObligationType,
    Outcome,
    Verdict,
    ViolationCode,
)
from app.domain.money import bp, post, round_half_up
from app.financial import EngineError
from app.funding import NoPermanentSourceError
from app.funding.rates import break_even_cost_share
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy import CandidatePackage
from app.strategy.collections import ReceivableWorth, WorthAnswer, early_pay_vs_plan, receivables_worth
from app.strategy.envelope import (
    BuyerContext,
    EnvelopeAnswer,
    EnvelopeFacts,
    EnvelopePackage,
    envelope_answer,
    envelope_facts,
    open_context,
    probe_packages,
    ranges_for,
)
from app.strategy.impact import marginal_impact, scenario_inflow
from app.strategy.price_curve import WINDOW_DAYS, PriceCurve, price_curve
from app.verifier import evaluate
from app.verifier.counters import infeasibility
from app.verifier.evaluate import clear_caches
from app.whatif.offer import build
from app.whatif.params import DISCOUNT_MAX_BP, WhatIfParams

SCENARIOS = API / "evals" / "e2e" / "scenarios.yaml"
ORACLE = ROOT / "fixtures" / "strategy" / "collections_both.json"
RUNNER = ROOT / "scripts" / "run_scenarios.py"
REPORT_DIR = ROOT / "docs" / "research" / "strategy"
QUICK_SCENARIO = "S01_scene1_counter_accept"  # the golden scenario: EX01 evaluated, countered, agreed
SWEEP_DAYS = (10, 20, 34, 47, 60)  # the clock sweep: each scenario's end state, advanced to these days in turn
QUICK_SWEEP_DAYS = (10, 34)
OWNER = {"X-Owner-Token": "demo-owner-token"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
FACE_KIND = {"the whole outstanding invoice": "whole", "the shortfall the plan covers": "need"}
# The one known difference from the oracle: on day 0 the module values the net saving on the face the verifier's own
# Option A counter uses (RCV-A, 0.85% on ¥257,200: ¥86.16; the plan's need is 0.75% on ¥405,000: ¥59.39); the spike's
# `net_value_at_ceiling` is on the whole face (0.70%: ¥173.93).
EXPECTED_DAY0_NET = {"RCV-A": (8_616, 17_393)}
MAX_ACTION_WORDS = 25  # a row's action sentence is at most this many words (English)
MAX_FAILURES_IN_REPORT = 200


# ---------------------------------------------------------------- results


@dataclass
class Failure:
    section: str
    scenario: str
    turn: int
    figure: str
    message: str


@dataclass
class Section:
    name: str
    status: str = "ok"  # ok | failed | skipped
    seconds: float = 0.0
    counts: dict[str, Any] = field(default_factory=dict)
    failures: list[Failure] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, scenario: str, turn: int, figure: str, message: str) -> None:
        self.failures.append(Failure(self.name, scenario, turn, figure, message))
        self.status = "failed"

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


# ---------------------------------------------------------------- the golden books (copied from tests/strategy/conftest.py)


def _runtime() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    return rt


def _replay_to_day34(rt: Runtime) -> None:
    """The demo path in process: EX01 evaluated, Option A agreed, the agreed receipt on day 2, the clock to day 34."""
    from app.main import app

    set_runtime(rt)
    try:
        c = TestClient(app)
        oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
        c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
        n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
        commitment = rt.store.get_commitment(n["commitment"]["id"])
        assert commitment is not None
        ob = commitment.obligations[0]
        assert ob.base.amount_fen is not None and ob.rate_bp is not None and ob.effective_day is not None
        agreed = ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
        c.post("/clock/advance", json={"to_day": ob.effective_day}, headers=OWNER)
        r = c.post("/operations", headers=BANK, json={
            "kind": "RECEIVE_PAYMENT", "op_id": "strategy-receipt-1", "idempotency_key": "strategy-receipt-1",
            "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
            "receivable_id": ob.base.receivable_id, "amount_fen": agreed}).json()
        assert r["result"]["status"] == "EXECUTED", r
        c.post("/clock/advance", json={"to_day": 30}, headers=OWNER)
        c.post("/clock/advance", json={"to_day": 34}, headers=OWNER)
    finally:
        set_runtime(None)


# ---------------------------------------------------------------- the checks on one set of books


def check_worth(books: Books, mandate: Mandate, rt: Runtime, day: int) -> tuple[WorthAnswer, list[tuple[str, str]], dict[str, Any]]:
    """`receivables_worth` and the brief's invariants on it: (answer, [(figure, message)], stats)."""
    answer = receivables_worth(books, mandate, store=rt.store, day=day)
    bad: list[tuple[str, str]] = []
    cap = mandate.max_immediate_discount_bp if mandate.max_immediate_discount_bp is not None else DISCOUNT_MAX_BP
    ceilings = 0
    for w in answer.rows:
        if w.action == "call_now" and w.days_late <= 0:
            bad.append((w.receivable_id, f"call_now on a receivable that is not past due (days_late {w.days_late})"))
        if w.days_late > 0 and w.ceilings:
            bad.append((w.receivable_id, f"an early-payment ceiling on an overdue receivable ({w.days_late} days late)"))
        if len(w.action_sentence.split()) > MAX_ACTION_WORDS:
            words = len(w.action_sentence.split())
            bad.append((w.receivable_id, f"the action sentence has {words} words (at most {MAX_ACTION_WORDS}): {w.action_sentence}"))
        if not w.worth_text:
            bad.append((w.receivable_id, "the row has no worth_text"))
        elif w.action == "wait" and w.worth_text != "Saves nothing extra now":
            bad.append((w.receivable_id, f"a wait row says {w.worth_text!r}"))
        for c in w.ceilings:
            ceilings += 1
            if c.largest_rate_bp is None:
                continue
            tag = f"{w.receivable_id} ceiling on the {c.face_kind} face"
            if c.largest_rate_bp > cap:
                bad.append((tag, f"largest rate {c.largest_rate_bp} bp is above the cap of {cap} bp"))
            if c.beats_by_fen is None or c.beats_by_fen <= 0:
                bad.append((tag, f"beats_by_fen {c.beats_by_fen} does not beat the plan"))
            elif c.cost_with_fen is None or c.cost_without_fen - c.cost_with_fen != c.beats_by_fen:
                bad.append((tag, f"beats_by_fen {c.beats_by_fen} is not C0 {c.cost_without_fen} less C1 {c.cost_with_fen}"))
    before = ([w.receivable_id for w in answer.rows], answer.gross_order)
    clear_caches()
    again = receivables_worth(books, mandate, store=rt.store, day=day)
    if before != ([w.receivable_id for w in again.rows], again.gross_order):
        after = [w.receivable_id for w in again.rows]
        message = f"order {before[0]} / gross {before[1]} differs after clear_caches(): {after} / {again.gross_order}"
        bad.append(("row order", message))
    amount_order = [w.receivable_id for w in sorted(
        answer.rows, key=lambda w: (w.days_late <= 0, -w.outstanding_fen, w.due_day, w.receivable_id))]
    net_order = [w.receivable_id for w in answer.rows]
    stats = {"rows": len(answer.rows), "ceilings": ceilings, "actions": Counter(w.action for w in answer.rows),
             "overdue": sum(w.days_late > 0 for w in answer.rows), "day": day,
             "comparable": len(answer.rows) >= 2, "order_differs": len(answer.rows) >= 2 and net_order != amount_order}
    return answer, bad, stats


def check_curve(books: Books, mandate: Mandate, rt: Runtime, day: int) -> tuple[PriceCurve, list[tuple[str, str]], dict[str, Any]]:
    """`price_curve` and the brief's invariants on it: (curve, [(figure, message)], stats)."""
    curve = price_curve(books, mandate, store=rt.store, day=day)
    amount = curve.amount_fen
    bad: list[tuple[str, str]] = []
    pairs: dict[int, int] = {}

    def spike(d: int) -> int:
        if d not in pairs:
            mi = marginal_impact(scenario_inflow(books, amount, d + WINDOW_DAYS), scenario_inflow(books, amount, d),
                                 mandate, store=rt.store, day=day)
            pairs[d] = -mi.posted_cost_delta_fen
        return pairs[d]

    try:
        share, _, _ = break_even_cost_share(books.state, mandate, 2 * WINDOW_DAYS)
        limit: int | None = round_half_up(share * amount)
    except NoPermanentSourceError:
        limit = None
    checks = 0
    for b in curve.bands:
        tag = f"band {b.from_day}..{b.to_day}"
        ends = [spike(b.from_day), spike(b.to_day)]
        checks += 2
        if b.varies:
            if b.value_fen != min(ends):
                bad.append((tag, f"a varies band carries {b.value_fen} fen, its ends are {ends}"))
        else:
            for d, got in ((b.from_day, ends[0]), (b.to_day, ends[1])):
                if got != b.value_fen:
                    bad.append((tag, f"band value {b.value_fen} fen but the marginal-impact pair at day {d} gives {got}"))
        if limit is not None and b.value_fen > limit:
            bad.append((tag, f"value {b.value_fen} fen is above the cost of funds for two periods ({limit} fen)"))
    if curve.flat != all(b.value_fen == 0 for b in curve.bands):
        bad.append(("flat", f"flat={curve.flat} but the band values are {[b.value_fen for b in curve.bands]}"))
    if curve.bands and (curve.bands[0].from_day != day
                        or any(y.from_day != x.to_day + 1 for x, y in zip(curve.bands, curve.bands[1:], strict=False))):
        spans = [(b.from_day, b.to_day) for b in curve.bands]
        bad.append(("tiling", f"the bands do not tile from day {day} without a gap: {spans}"))
    stats = {"bands": len(curve.bands), "varies": sum(b.varies for b in curve.bands), "flat": curve.flat, "checks": checks}
    return curve, bad, stats


# ---------------------------------------------------------------- sections 1 and 2: the replay


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("run_scenarios", RUNNER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_scenarios"] = mod
    spec.loader.exec_module(mod)
    return mod


def _turn_body(scn: dict[str, Any], turn: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """One scenario turn as the runner posts it to /nl (the construction of `run_scenarios.run`)."""
    actor = turn.get("actor", "OWNER")
    body: dict[str, Any] = {"session_id": turn.get("session") or f"{scn['id']}-{actor.lower()}"[:64], "actor": actor,
                            "text": turn["text"]}
    for k in ("counterparty_id", "request_id", "lang"):
        if turn.get(k):
            body[k] = turn[k]
    if turn.get("buyer_key") is False:
        body["_buyer_key"] = False
    if turn.get("buyer_profile") or scn.get("buyer_profile"):
        body["buyer_profile"] = turn.get("buyer_profile") or scn["buyer_profile"]
    return body, actor == "OWNER" and bool(turn.get("owner_token", True))


@dataclass
class Analysis:
    """What the two checks said about one set of books (shared by every turn that leaves the same books)."""

    worth_error: str | None = None
    worth_bad: list[tuple[str, str]] = field(default_factory=list)
    worth_stats: dict[str, Any] = field(default_factory=dict)
    worth_seconds: float = 0.0
    curve_error: str | None = None
    curve_bad: list[tuple[str, str]] = field(default_factory=list)
    curve_stats: dict[str, Any] = field(default_factory=dict)
    curve_seconds: float = 0.0


def _analyse(rt: Runtime) -> Analysis:
    books = books_from_store(rt.store)
    mandate = rt.store.get_mandate()
    day = rt.day
    out = Analysis()
    t0 = time.perf_counter()
    try:
        _, out.worth_bad, out.worth_stats = check_worth(books, mandate, rt, day)
    except (EngineError, ValueError) as e:
        out.worth_error = f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001 - a crash is a finding as well, not a reason to stop the backtest
        out.worth_error = f"unexpected {type(e).__name__}: {e}"
    out.worth_seconds = time.perf_counter() - t0
    t0 = time.perf_counter()
    try:
        _, out.curve_bad, out.curve_stats = check_curve(books, mandate, rt, day)
    except (EngineError, ValueError) as e:
        out.curve_error = f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001
        out.curve_error = f"unexpected {type(e).__name__}: {e}"
    out.curve_seconds = time.perf_counter() - t0
    return out


def _books_key(rt: Runtime) -> str:
    """The inputs of both answers: the state, the mandate, the day, the commitments and the operation log (the promises
    are read from it)."""
    parts = [rt.store.get_state().model_dump_json(), rt.store.get_mandate().model_dump_json(), str(rt.day),
             *(c.model_dump_json() for c in rt.store.commitments()), str(len(rt.store.operations()))]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def replay(quick: bool, collections: Section, curve: Section, clock: Section) -> None:
    import yaml

    scenarios: list[dict[str, Any]] = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
    if quick:
        scenarios = [s for s in scenarios if s["id"] == QUICK_SCENARIO]
    transport = _load_runner().InProc()
    memo: dict[str, Analysis] = {}
    actions: Counter[str] = Counter()
    days: set[int] = set()
    slowest: list[tuple[float, str, int]] = []
    sweep_days = QUICK_SWEEP_DAYS if quick else SWEEP_DAYS
    per_day = {d: _DayStats() for d in sweep_days}
    clock.counts.update({"scenarios": len(scenarios), "days": list(sweep_days), "states": 0, "distinct_book_states": 0,
                         "advance_errors": 0, "days_already_passed": 0})
    collections.counts.update({"scenarios": len(scenarios), "turns": 0, "distinct_book_states": 0, "rows_checked": 0,
                               "ceilings_checked": 0, "turns_with_two_or_more_rows": 0,
                               "net_order_differs_from_amount_order": 0, "turns_without_rows": 0, "non_200_turns": 0,
                               "overdue_rows": 0, "max_rows_in_a_turn": 0})
    curve.counts.update({"scenarios": len(scenarios), "turns": 0, "distinct_book_states": 0, "bands_checked": 0,
                         "band_end_checks": 0, "flat_turns": 0, "varies_bands": 0})
    try:
        for i, scn in enumerate(scenarios, 1):
            t_scn = time.perf_counter()
            fresh = 0
            try:
                transport.reset(scn.get("setup"))
            except Exception as e:  # noqa: BLE001
                collections.fail(scn["id"], 0, "setup", f"{type(e).__name__}: {e}")
                continue
            turns = scn["turns"]
            for n, turn in enumerate(turns, 1):
                body, owner = _turn_body(scn, turn)
                try:
                    code, _ = transport.post("/nl", body, owner)
                except Exception as e:  # noqa: BLE001
                    collections.fail(scn["id"], n, "turn", f"the turn itself raised {type(e).__name__}: {e}")
                    break
                if code != 200:
                    collections.bump("non_200_turns")
                key = _books_key(transport.rt)
                a = memo.get(key)
                if a is None:
                    a = memo[key] = _analyse(transport.rt)
                    fresh += 1
                    collections.counts["distinct_book_states"] += 1
                    curve.counts["distinct_book_states"] += 1
                    collections.seconds += a.worth_seconds
                    curve.seconds += a.curve_seconds
                    slowest.append((a.worth_seconds + a.curve_seconds, scn["id"], n))
                _record(scn["id"], n, a, collections, curve, actions, days)
            swept = _sweep(transport.rt, scn["id"], sweep_days, memo, clock, per_day)
            print(f"[{i}/{len(scenarios)}] {scn['id']}: {len(turns)} turns, {fresh} new book states, "
                  f"{swept} swept, {time.perf_counter() - t_scn:.1f}s", file=sys.stderr, flush=True)
    finally:
        set_runtime(None)
    collections.counts["actions"] = dict(sorted(actions.items()))
    collections.counts["days_covered"] = sorted(days)
    collections.counts["slowest_turns"] = [{"scenario": s, "turn": n, "seconds": round(t, 2)}
                                           for t, s, n in sorted(slowest, reverse=True)[:5]]
    clock.counts["by_day"] = {str(d): st.summary() for d, st in per_day.items()}
    clock.counts["states"] = sum(st.states for st in per_day.values())
    clock.seconds = sum(st.seconds for st in per_day.values())
    clock.counts["actions"] = dict(sorted(sum((st.actions for st in per_day.values()), Counter[str]()).items()))
    clock.counts["slowest_states"] = [
        {"scenario": s, "day": d, "worth_s": round(w, 2), "curve_s": round(c, 2)}
        for w, c, s, d in sorted(((st.worst[0], st.worst[1], st.worst[2], d) for d, st in per_day.items() if st.worst[2]),
                                 key=lambda x: -(x[0] + x[1]))[:5]]


def _record(scn: str, n: int, a: Analysis, collections: Section, curve: Section, actions: Counter[str],
            days: set[int]) -> None:
    collections.bump("turns")
    curve.bump("turns")
    if a.worth_error is not None:
        collections.fail(scn, n, "receivables_worth", a.worth_error)
    else:
        for figure, message in a.worth_bad:
            collections.fail(scn, n, figure, message)
        s = a.worth_stats
        collections.bump("rows_checked", s["rows"])
        collections.bump("ceilings_checked", s["ceilings"])
        collections.bump("turns_without_rows", int(s["rows"] == 0))
        collections.bump("turns_with_two_or_more_rows", int(s["comparable"]))
        collections.bump("net_order_differs_from_amount_order", int(s["order_differs"]))
        actions.update(s["actions"])
        days.add(s["day"])
        collections.bump("overdue_rows", s["overdue"])
        collections.counts["max_rows_in_a_turn"] = max(collections.counts["max_rows_in_a_turn"], s["rows"])
    if a.curve_error is not None:
        curve.fail(scn, n, "price_curve", a.curve_error)
    else:
        for figure, message in a.curve_bad:
            curve.fail(scn, n, figure, message)
        s = a.curve_stats
        curve.bump("bands_checked", s["bands"])
        curve.bump("band_end_checks", s["checks"])
        curve.bump("flat_turns", int(s["flat"]))
        curve.bump("varies_bands", s["varies"])


@dataclass
class _DayStats:
    """What the sweep found at one day, over every scenario's end state advanced to it."""

    states: int = 0
    distinct: int = 0
    rows: int = 0
    ceilings: int = 0
    overdue_rows: int = 0
    comparable: int = 0
    order_differs: int = 0
    states_without_rows: int = 0
    bands: int = 0
    varies: int = 0
    band_checks: int = 0
    flat: int = 0
    seconds: float = 0.0
    actions: Counter[str] = field(default_factory=Counter)
    worst: tuple[float, float, str] = (0.0, 0.0, "")  # worth seconds, curve seconds, scenario of the slowest state

    def summary(self) -> dict[str, Any]:
        return {"states": self.states, "distinct_book_states": self.distinct, "rows": self.rows, "ceilings": self.ceilings,
                "overdue_rows": self.overdue_rows, "states_without_rows": self.states_without_rows,
                "states_with_two_or_more_rows": self.comparable, "net_order_differs": self.order_differs,
                "bands": self.bands, "varies_bands": self.varies, "band_end_checks": self.band_checks,
                "flat_curves": self.flat, "actions": dict(sorted(self.actions.items())), "seconds": round(self.seconds, 1),
                "slowest_state": {"scenario": self.worst[2], "worth_s": round(self.worst[0], 2),
                                  "curve_s": round(self.worst[1], 2)} if self.worst[2] else None}


def _sweep(rt: Runtime, scn: str, days: Sequence[int], memo: dict[str, Analysis], clock: Section,
           per_day: dict[int, _DayStats]) -> int:
    """Advance this scenario's end state through `days` (`Runtime.advance_to`, which `POST /clock/advance` calls) and put
    `receivables_worth` and `price_curve` to the replay's invariant checks at each. Returns the states swept."""
    swept = 0
    for day in days:
        if day <= rt.day:
            clock.bump("days_already_passed")
            continue
        try:
            rt.advance_to(day)
        except Exception as e:  # noqa: BLE001 - an advance that fails is a finding, and ends this scenario's sweep
            clock.bump("advance_errors")
            clock.fail(scn, day, "clock advance", f"day {day}: {type(e).__name__}: {e}")
            break
        st = per_day[day]
        key = _books_key(rt)
        a = memo.get(key)
        if a is None:
            a = memo[key] = _analyse(rt)
            st.distinct += 1
            clock.counts["distinct_book_states"] += 1
            st.seconds += a.worth_seconds + a.curve_seconds
            if a.worth_seconds + a.curve_seconds > st.worst[0] + st.worst[1]:
                st.worst = (a.worth_seconds, a.curve_seconds, scn)
        st.states += 1
        swept += 1
        if a.worth_error is not None:
            clock.fail(scn, day, "receivables_worth", f"day {day}: {a.worth_error}")
        else:
            for figure, message in a.worth_bad:
                clock.fail(scn, day, figure, f"day {day}: {message}")
            w = a.worth_stats
            st.rows += w["rows"]
            st.ceilings += w["ceilings"]
            st.overdue_rows += w["overdue"]
            st.comparable += int(w["comparable"])
            st.order_differs += int(w["order_differs"])
            st.states_without_rows += int(w["rows"] == 0)
            st.actions.update(w["actions"])
        if a.curve_error is not None:
            clock.fail(scn, day, "price_curve", f"day {day}: {a.curve_error}")
        else:
            for figure, message in a.curve_bad:
                clock.fail(scn, day, figure, f"day {day}: {message}")
            c = a.curve_stats
            st.bands += c["bands"]
            st.varies += c["varies"]
            st.band_checks += c["checks"]
            st.flat += int(c["flat"])
    return swept


# ---------------------------------------------------------------- section 3: the differential


def _fen(m: dict[str, Any] | None) -> int | None:
    return None if m is None else int(m["fen"])


def differential() -> Section:
    """The three modules on the golden day-0 and day-34 books against `collections_both.json`, to the fen."""
    sec = Section("differential")
    t0 = time.perf_counter()
    oracle = json.loads(ORACLE.read_text(encoding="utf-8"))["books"]
    counts: Counter[str] = Counter()
    expected: list[str] = []
    invariants: list[str] = []
    rt0 = _runtime()
    rt34 = _runtime()
    _replay_to_day34(rt34)
    for which, rt in ((0, rt0), (34, rt34)):
        name = f"day {which}"
        book = next(b for b in oracle if b["books"] == name)
        books, mandate = books_from_store(rt.store), rt.store.get_mandate()

        def bad(figure: str, message: str, _name: str = name) -> None:
            sec.fail(_name, 0, figure, message)

        answer, worth_bad, worth_stats = check_worth(books, mandate, rt, which)  # the replay's invariants, on these books
        curve, curve_bad, curve_stats = check_curve(books, mandate, rt, which)
        counts[f"{name} books"] += 1
        counts[f"{name}: invariant checks (rows, ceilings, band ends)"] += (
            worth_stats["rows"] + worth_stats["ceilings"] + curve_stats["checks"])
        for figure, message in worth_bad + curve_bad:
            bad(f"invariant: {figure}", message)
        invariants.append(f"{name}: {worth_stats['rows']} rows ({', '.join(f'{k} {v}' for k, v in sorted(worth_stats['actions'].items()))}); "
                          f"net order differs from the amount order: {worth_stats['order_differs']}; "
                          f"{curve_stats['bands']} bands, flat {curve_stats['flat']}")
        if {w.receivable_id for w in answer.rows} != {r["receivable"] for r in book["ranking"]}:
            bad("receivables", f"module {[w.receivable_id for w in answer.rows]} vs oracle "
                               f"{[r['receivable'] for r in book['ranking']]}")
        counts[f"{name}: first breach day"] += 1
        if answer.first_breach_day != book["baseline"]["first_breach_day"]:
            bad("first breach day", f"module {answer.first_breach_day} vs oracle {book['baseline']['first_breach_day']}")
        for o in book["ranking"]:
            rid = o["receivable"]
            w = next((x for x in answer.rows if x.receivable_id == rid), None)
            if w is None:
                continue
            _compare_row(counts, expected, name, books, mandate, which, w, o, bad)
        for p in book["cash_price_curve"]["points"]:
            counts[f"{name}: curve points"] += 1
            band = next((b for b in curve.bands if b.from_day <= p["arrival_day"] <= b.to_day), None)
            if band is None:
                bad(f"curve day {p['arrival_day']}", "no band contains the arrival day")
            elif band.value_fen != _fen(p["worth"]):
                bad(f"curve day {p['arrival_day']}",
                    f"band {band.from_day}..{band.to_day} is {band.value_fen} fen, oracle {_fen(p['worth'])}")
    sec.counts = {"checks": sum(counts.values()), "by_kind": dict(sorted(counts.items())),
                  "expected_differences": expected, "invariants": invariants}
    sec.seconds = time.perf_counter() - t0
    return sec


def _compare_row(counts: Counter[str], expected: list[str], name: str, books: Books, mandate: Mandate, which: int,
                 w: ReceivableWorth, o: dict[str, Any], bad: Callable[[str, str], None]) -> None:
    rid = o["receivable"]
    by_day = {e.receipt_day: e for e in w.effects}
    for e in o["effects"]:
        counts[f"{name}: effects (saving)"] += 1
        got = by_day.get(e["receipt_day"])
        if got is None:
            bad(f"{rid} effect on day {e['receipt_day']}", "the module has no effect on that receipt day")
        elif got.saving_fen != _fen(e["saving"]):
            bad(f"{rid} effect on day {e['receipt_day']}", f"saving {got.saving_fen} fen vs oracle {_fen(e['saving'])}")
    for p in o["early_pay"]:
        if not p["sweep"] and p["largest_rate"] is None:  # overdue: the spike offers nothing, nor may the module
            counts[f"{name}: faces with no offer"] += 1
            if w.ceilings:
                bad(f"{rid} early pay", f"the module has ceilings {[c.face_kind for c in w.ceilings]} on an overdue invoice")
            continue
        kind = FACE_KIND[p["face_label"]]
        c = next((x for x in w.ceilings if x.face_kind == kind), None)
        face = _fen(p["face"])
        counts[f"{name}: ceilings (largest rate)"] += 1
        if c is None:
            bad(f"{rid} {kind} face", "the module has no ceiling on this face")
        else:
            want = (p["largest_rate"] or {}).get("bp")
            if c.largest_rate_bp != want or c.face_fen != face:
                bad(f"{rid} {kind} face", f"ceiling {c.largest_rate_bp} bp on {c.face_fen} fen vs oracle {want} bp on {face} fen")
        for s in p["sweep"]:
            counts[f"{name}: sweep points (C1 less C0)"] += 1
            assert face is not None
            gap = early_pay_vs_plan(books, mandate, rid, face, s["rate"]["bp"])
            if gap != _fen(s["c1_less_c0"]):
                bad(f"{rid} {kind} face at {s['rate']['bp']} bp", f"C1 less C0 {gap} fen vs oracle {_fen(s['c1_less_c0'])}")
    counts[f"{name}: net value at the ceiling"] += 1
    want_net = _fen(o["net_value_at_ceiling"])
    if w.net_saving_fen == want_net:
        return
    if which == 0 and EXPECTED_DAY0_NET.get(rid) == (w.net_saving_fen, want_net):
        expected.append(f"{name} {rid}: net saving {w.net_saving_fen} fen (the face the verifier's Option A counter uses) vs the "
                        f"oracle's net_value_at_ceiling {want_net} fen (whole face): the module quotes the one face FLOW would send")
    else:
        bad(f"{rid} net value at the ceiling", f"net saving {w.net_saving_fen} fen vs oracle {want_net} fen")


# ---------------------------------------------------------------- section 4: the envelope

Point = tuple[int, int, int, int | None, int]  # terms, price bp, early-pay bp, early-pay face fen (None: whole), rebate bp
PASSING = (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL)
CAP_CODES = (ViolationCode.AGG_CONCESSION_EXCEEDED, ViolationCode.PER_BUYER_CAP_EXCEEDED)
LEVER_TYPES = (ObligationType.TERMS_EXTENSION, ObligationType.PRICE_ADJUSTMENT, ObligationType.IMMEDIATE_DISCOUNT,
               ObligationType.CONTINGENT_REBATE)
OFFER_FILES = (ROOT / "fixtures" / "offers" / "offers.yaml",
               *(d / "offers.yaml" for d in sorted((ROOT / "fixtures").glob("heldout*")) if (d / "offers.yaml").is_file()))
QUICK_OFFERS = ("EX01_PACKAGE",)  # `--quick` puts this one offer and its counters to the envelope
MAX_UNMATCHED_NOTES = 12


def _passes(v: Verdict) -> bool:
    """The sweep's own definition of a package that passes: ACCEPT, or NEEDS_OWNER_APPROVAL with every reserve breach curable."""
    return v.outcome in PASSING and not any(x.code == ViolationCode.RESERVE_BREACH and not x.curable for x in v.violations)


def _liquidity_only(v: Verdict) -> bool:
    return v.outcome != Outcome.NO_VERDICT and all(
        x.code in CAP_CODES or (x.code == ViolationCode.RESERVE_BREACH and x.curable) for x in v.violations)


def _reading(obligations: Sequence[Obligation], cur: int, whole_face: int) -> Point | None:
    """Obligations read as one package of the envelope's levers (the levers they do not set at zero, the terms in force
    when they set none). None when an obligation has no lever or a lever is set twice. This is a second reading,
    written here, of what `envelope._setting_of` does for the sweep's own counters."""
    terms, price, discount, face, rebate = cur, 0, 0, None, 0
    seen: set[ObligationType] = set()
    for o in obligations:
        if o.type not in LEVER_TYPES or o.type in seen:
            return None
        seen.add(o.type)
        if o.type == ObligationType.TERMS_EXTENSION:
            if o.target_terms_days is not None:
                terms = o.target_terms_days
            elif o.days_delta is not None:
                terms = cur + o.days_delta
        elif o.type == ObligationType.PRICE_ADJUSTMENT:
            price = o.rate_bp or 0
        elif o.type == ObligationType.IMMEDIATE_DISCOUNT:
            discount = o.rate_bp or 0
            face = o.base.amount_fen if o.base.amount_fen not in (None, whole_face) else None
        else:
            rebate = o.rate_bp or 0
    return terms, price, discount, face, rebate


def _describe(obligations: Sequence[Obligation]) -> str:
    out: list[str] = []
    for o in obligations:
        bits = [o.type.value]
        if o.target_terms_days is not None:
            bits.append(f"to {o.target_terms_days} d")
        if o.days_delta is not None:
            bits.append(f"{o.days_delta:+d} d")
        if o.rate_bp is not None:
            bits.append(f"{o.rate_bp} bp")
        if o.base.amount_fen is not None:
            bits.append(f"on {_money(o.base.amount_fen)}")
        out.append(" ".join(bits))
    return "; ".join(out) or "no obligations"


def _point_text(p: Point) -> str:
    terms, price, discount, face, rebate = p
    return (f"terms {terms} d, price {price} bp, early pay {discount} bp on "
            f"{'the whole invoice' if face is None else _money(face)}, rebate {rebate} bp")


def _candidate(buyer_id: str, p: Point) -> CandidatePackage:
    return CandidatePackage(buyer_id=buyer_id, terms_days=p[0], price_bp=p[1], early_pay_bp=p[2], early_pay_face_fen=p[3],
                            rebate_bp=p[4])


def _note(sec: Section, text: str) -> None:
    if text not in sec.notes and len(sec.notes) < MAX_UNMATCHED_NOTES:
        sec.notes.append(text)


def _point_of(pkg: EnvelopePackage) -> Point:
    q = pkg.package
    return q.terms_days, q.price_bp, q.early_pay_bp, q.early_pay_face_fen, q.rebate_bp


@dataclass(frozen=True)
class GridCell:
    passes: bool
    approved: bool
    liquidity_only: bool


@dataclass
class Reference:
    """One buyer's envelope on the golden day-0 books and the exhaustive terms x price scan beside it."""

    buyer_id: str
    facts: EnvelopeFacts
    answer: EnvelopeAnswer
    grid: dict[tuple[int, int], GridCell] = field(default_factory=dict)
    envelope_seconds: float = 0.0
    scan_seconds: float = 0.0


class EnvelopeRun:
    """The golden day-0 books and the per-buyer references (there are two buyers on the books, so the sweep runs at
    most twice)."""

    def __init__(self, full_grid: bool, zone: bool) -> None:
        self.rt = _runtime()
        self.books = books_from_store(self.rt.store)
        self.mandate = self.rt.store.get_mandate()
        self.key = demo_owner_public_key_hex()
        self.full_grid, self.zone = full_grid, zone
        self.refs: dict[str, Reference] = {}

    def verdict(self, offer: CompiledOffer, declared: dict[str, Any] | None = None) -> Verdict:
        return evaluate(offer, self.books.state, self.mandate, trusted_owner_key_hex=self.key, day=0,
                        owner_declared=declared, plans="committed").verdict

    def package_verdict(self, ctx: BuyerContext, point: Point) -> Verdict:
        terms, price, discount, face, rebate = point
        offer, _ = build(WhatIfParams(terms_days=terms, discount_bp=discount, rebate_bp=rebate, price_adjustment_bp=price,
                                      settle_face_fen=face), ctx, 0)
        return self.verdict(offer)

    def reference(self, buyer_id: str, scan: bool) -> Reference:
        ref = self.refs.get(buyer_id)
        if ref is not None:
            return ref
        t0 = time.perf_counter()
        facts = envelope_facts(self.books, self.mandate, store=self.rt.store, day=0, buyer_id=buyer_id,
                               trusted_owner_key_hex=self.key, zone=self.zone, full_grid=self.full_grid)
        ref = self.refs[buyer_id] = Reference(buyer_id, facts, envelope_answer(facts), envelope_seconds=time.perf_counter() - t0)
        if scan and not facts.refused:
            t1 = time.perf_counter()
            ctx = open_context(self.books.state, 0, buyer_id)
            ranges = ranges_for(ctx, self.mandate)
            for terms in ranges.terms:
                for price in ranges.price:
                    v = self.package_verdict(ctx, (terms, price, 0, None, 0))
                    passes = _passes(v)
                    ref.grid[(terms, price)] = GridCell(
                        passes, passes and infeasibility(v, self.books.state) is None, _liquidity_only(v))
            ref.scan_seconds = time.perf_counter() - t1
        return ref


def _check_buyer(run: EnvelopeRun, ref: Reference, sec: Section) -> None:
    """Items iii and iv, once per buyer: every approved package passes its re-check; every lever maximum is confirmed;
    the bisection's zone and maxima equal the exhaustive terms x price scan."""
    who = f"envelope {ref.buyer_id}"
    answer, facts = ref.answer, ref.facts
    if facts.refused:
        return
    ctx = open_context(run.books.state, 0, ref.buyer_id)
    for pkg in answer.packages:  # iii
        point = _point_of(pkg)
        sec.bump("packages_rechecked")
        v = run.package_verdict(ctx, point)
        passes = _passes(v)
        why = infeasibility(v, run.books.state) if v.outcome in PASSING else None
        sec.bump("packages_approved", int(pkg.approved))
        if pkg.approved and (not passes or why is not None):
            sec.fail(who, 0, _point_text(point), f"the answer calls it approved but the verifier says {v.outcome.value} "
                                                  f"(passes {passes}); the re-check says: {why}")
        elif pkg.approved != (passes and why is None):
            sec.fail(who, 0, _point_text(point), f"the answer says approved={pkg.approved}, a fresh evaluation says {passes and why is None}")
    for lv in answer.levers:  # iv: confirmed
        if lv.unavailable is not None:
            continue
        sec.bump("lever_maxima_checked")
        if lv.confirmed:
            sec.bump("lever_maxima_confirmed")
        else:
            sec.fail(who, 0, lv.lever, f"neighbour check not confirmed (maximum {lv.maximum}, scanned {lv.scanned})")
    if not ref.grid:
        return
    cur, pmax = facts.current_terms, max(p for _, p in ref.grid)
    up = [t for t in sorted({t for t, _ in ref.grid}) if t >= cur]
    prices = sorted({p for _, p in ref.grid})
    by_key = {lv.key: lv for lv in answer.levers}

    def agree(figure: str, got: object, want: object) -> None:
        sec.bump("exhaustive_comparisons")
        if got == want:
            sec.bump("exhaustive_agreements")
        else:
            sec.fail(who, 0, figure, f"bisection {got}, exhaustive scan {want}")

    for z in answer.zone:
        want = next((p for p in prices if ref.grid[(z.terms_days, p)].passes), None)
        agree(f"zone: smallest passing price at {z.terms_days} d", z.min_price_bp, want)
    sec.counts["zone_rows_scanned"] = len(answer.zone)
    alone = by_key.get("terms_alone")
    if alone is not None and alone.unavailable is None:
        agree("terms alone: longest passing", alone.maximum, max((t for t in up if ref.grid[(t, 0)].passes), default=None))
    liquid = by_key.get("terms_budget_ignored")
    if liquid is not None and liquid.unavailable is None:
        agree("terms, budget ignored: longest", liquid.maximum,
              max((t for t in up if ref.grid[(t, 0)].liquidity_only), default=None))
    best = by_key.get("terms_with_price")
    if best is not None and best.unavailable is None:
        t_best = max((t for t in up if ref.grid[(t, pmax)].approved), default=None)
        agree("terms with price: longest approved", best.maximum, t_best)
        if t_best is not None:
            p_best = next((p for p in prices if ref.grid[(t_best, p)].approved), None)
            got = best.at_maximum.package.price_bp if best.at_maximum is not None else None
            agree(f"terms with price: smallest approved price at {t_best} d", got, p_best)


UNBOOKED_ORDER = "the order is stated in the offer, not on the books"


def _only_rebate_counters(v: Verdict) -> bool:
    """Whether the verdict has counters and every obligation of every one is a rebate (H37's counter: a rebate on an
    order the offer states and the books do not carry)."""
    return bool(v.counters) and all(c.obligations and all(o.type == ObligationType.CONTINGENT_REBATE for o in c.obligations)
                                    for c in v.counters)


def _check_offer(run: EnvelopeRun, item: dict[str, Any], offer: CompiledOffer, sec: Section, scan: bool) -> str | None:
    """Checks one offer; the reason it was skipped, if it was (counted by the caller, not as checked)."""
    oid = item["id"]
    declared = item.get("declared_costs")
    v = run.verdict(offer, declared)
    sec.bump(f"verdicts: {v.outcome.value}")
    if v.outcome == Outcome.NO_VERDICT:
        sec.bump("skipped: the verifier abstains (no verdict to compare)")
        return None
    ref = run.reference(offer.counterparty_id, scan)
    facts = ref.facts
    if facts.refused and facts.refusal == "no_lever" and _only_rebate_counters(v):
        # a buyer with no lever on the books (no recurring invoice, open invoice or expected order) whose only counter is a
        # rebate on an order the offer itself states: there is no base on the books to put the rebate to
        return UNBOOKED_ORDER
    sec.bump("offers_checked")
    if facts.refused:
        sec.bump("refusals")
        sec.bump("offers_whose_buyer_is_refused")
    whole = facts.receivable_face_fen
    cur = facts.current_terms
    approved = {_point_of(p): p for p in ref.answer.packages if p.approved}
    for c in v.counters:  # i: a counter passes when it is inside the envelope (approved when probed); listed is counted beside
        sec.bump("counters_checked")
        point = _reading(c.obligations, cur, whole)
        listed = point is not None and point in approved
        if listed:
            sec.bump("counters_listed")
        text = _describe(c.obligations)
        if facts.refused:
            sec.fail(oid, 0, c.label, f"{text}: the envelope for {facts.buyer_name} is refused, so there is no package to match")
            continue
        if point is None:
            sec.fail(oid, 0, c.label, f"{text}: the counter has an obligation or a lever twice that no package can express")
            continue
        if listed:
            sec.bump("counters_inside")
            continue
        try:
            probed = probe_packages(run.books, run.mandate, [_candidate(ref.buyer_id, point)], day=0,
                                    trusted_owner_key_hex=run.key)[0]
        except ValueError as e:
            sec.fail(oid, 0, c.label, f"{text} reads as ({_point_text(point)}) and is outside the envelope's levers "
                                      f"({str(e).splitlines()[0][:80]})")
            continue
        if probed.approved:
            sec.bump("counters_inside")
            sec.bump("counters_inside_not_listed")
            continue
        extra = f"; put to the verifier it is not approved ({probed.outcome})"
        same = [_point_of(p)[1] for p in ref.answer.packages
                if _point_of(p)[0::2] == point[0::2] and _point_of(p)[3:] == point[3:] and p.approved]
        if same:
            extra += f"; approved packages with the same other levers have price {sorted(same)} bp"
        sec.fail(oid, 0, c.label, f"{text} reads as ({_point_text(point)}) and is not inside the envelope{extra}")
    # ii: the offer's own point
    if not _passes(v):
        return None
    if facts.refused:
        sec.bump("passing offers not tested (the buyer is refused)")
        return None
    if declared:
        sec.bump("passing offers not tested (owner-declared costs the envelope cannot know)")
        return None
    types = {o.type for o in v.bound_obligations}
    point = _reading(v.bound_obligations, cur, whole)
    if point is None:
        sec.bump("passing offers not tested (an obligation with no lever, or a lever twice)")
        return None
    terms, price = point[0], point[1]
    if types <= {ObligationType.TERMS_EXTENSION, ObligationType.PRICE_ADJUSTMENT} and types:
        row = next((z for z in ref.answer.zone if z.terms_days == terms), None)
        if row is None:
            sec.bump("passing offers not tested (terms off the zone's grid or no zone computed)")
            return None
        sec.bump("zone_tests")
        if row.min_price_bp is not None and price >= row.min_price_bp:
            sec.bump("zone_tests_inside")
        else:
            sec.fail(oid, 0, f"terms {terms} d, price {price} bp",
                     f"the verdict passes ({v.outcome.value}) but the zone's smallest passing price at {terms} d is "
                     f"{row.min_price_bp} bp")
        return None
    try:
        probed = probe_packages(run.books, run.mandate, [_candidate(ref.buyer_id, point)], day=0,
                                trusted_owner_key_hex=run.key)[0]
    except ValueError as e:
        sec.bump("passing offers not tested (off the levers' grid, so not probeable)")
        _note(sec, f"not probeable: {oid} ({_point_text(point)}): {str(e).splitlines()[0][:100]}")
        return None
    sec.bump("probes")
    if probed.passes:
        sec.bump("probes_agree")
    else:
        sec.fail(oid, 0, _point_text(point), f"the verdict passes ({v.outcome.value}) but the same package put to "
                                              f"probe_packages is {probed.outcome} (passes {probed.passes})")
    return None


def check_envelope(quick: bool = False) -> Section:
    """The brief's section 9 item 1 for the Safe Deal Envelope, on the golden day-0 books, for every offer of
    `fixtures/offers/offers.yaml` and the held-out sets (`--quick`: EX01 only, with the default grid and the zone, and no exhaustive scan: that alone costs about 50 s).

    Per offer: compile it (the cache, then the rules grammar, as `LLM_MODE=cache` does), evaluate it
    (`plans="committed"`) and take the envelope of its buyer (once per buyer, with `full_grid` and the zone):
      i.   every counter of the verdict is inside the envelope: it reads as a package (terms, price, early-pay rate and
           face, rebate; levers a counter does not set at zero, the terms in force when it sets none) that
           `probe_packages` approves; the counters that are also listed among the grid's packages are counted beside;
           a buyer the envelope refuses has no envelope, so a counter to it is a failure;
      ii.  a passing offer with terms and price levers only is on or above the zone's smallest passing price at its
           terms; a passing offer with an early-pay or rebate lever too is put to `probe_packages`, which must pass it;
    Per buyer: iii. every approved package passes a fresh evaluation and `infeasibility`; iv. every lever maximum is
    confirmed by its neighbour check, and the zone and the maxima equal an exhaustive scan of terms x price built with
    `whatif.offer.build` and `evaluate` directly; v. the refusals (a buyer with no recurring invoice, open invoice or expected order) are counted, and an offer to such a buyer whose only counters are rebates on an order the offer states and the books do not carry is skipped with that reason.
    A failure carries the offer id (or `envelope <buyer>`) as its scenario and the figure.
    """
    import yaml

    from app.compiler import compile_offer
    from app.domain.models import SourceDocument

    sec = Section("envelope")
    t0 = time.perf_counter()
    run = EnvelopeRun(full_grid=not quick, zone=True)
    roles = {c.id: c.role for c in run.books.state.counterparties}
    sec.counts.update({"offers_listed": 0, "offers_checked": 0, "files": [], "compiled_from": {}, "counters_checked": 0,
                       "counters_inside": 0, "counters_listed": 0, "counters_inside_not_listed": 0, "zone_tests": 0, "zone_tests_inside": 0, "probes": 0, "probes_agree": 0,
                       "refusals": 0, "packages_rechecked": 0, "packages_approved": 0, "lever_maxima_checked": 0,
                       "lever_maxima_confirmed": 0, "exhaustive_comparisons": 0, "exhaustive_agreements": 0,
                       "buyers_swept": 0, "mode": "quick: EX01 only, default grid, no exhaustive scan" if quick else "full: full grid, zone"})
    skipped: Counter[str] = Counter()
    for path in OFFER_FILES:
        items: list[dict[str, Any]] = yaml.safe_load(path.read_text(encoding="utf-8"))["offers"]
        if quick:
            items = [i for i in items if i["id"] in QUICK_OFFERS]
        sec.counts["files"].append(f"{path.parent.name}/{path.name}: {len(items)}")
        for item in items:
            sec.counts["offers_listed"] += 1
            cp = item.get("counterparty_id", "BUYER-1")
            if roles.get(cp) != "BUYER":
                skipped[f"counterparty {cp} is not a buyer on the golden books ({roles.get(cp, 'not on the books')})"] += 1
                continue
            raw = item.get("documents") or [{"doc_id": f"{item['id']}-msg", "channel": "chat", "sender_id": cp,
                                             "received_day": 0, "text": item["text"]}]
            try:
                offer = compile_offer([SourceDocument.model_validate_json(json.dumps(d)) for d in raw], cp)
            except Exception as e:  # noqa: BLE001 - an offer that does not compile is skipped and counted, not a failure here
                skipped[f"the compile failed ({type(e).__name__})"] += 1
                continue
            sec.counts["compiled_from"][offer.compiler] = sec.counts["compiled_from"].get(offer.compiler, 0) + 1
            try:
                why = _check_offer(run, item, offer, sec, scan=not quick)
                if why is not None:
                    skipped[why] += 1
            except (EngineError, ValueError) as e:
                sec.fail(item["id"], 0, "envelope check", f"{type(e).__name__}: {e}")
    for ref in run.refs.values():
        _check_buyer(run, ref, sec)
    sec.counts["buyers_swept"] = len(run.refs)
    sec.counts["buyers"] = {r.buyer_id: {"refused": r.facts.refused, "packages": len(r.answer.packages),
                                         "approved": sum(p.approved for p in r.answer.packages),
                                         "zone_rows": len(r.answer.zone), "evaluations": r.facts.evaluations,
                                         "envelope_seconds": round(r.envelope_seconds, 1),
                                         "scan_cells": len(r.grid), "scan_seconds": round(r.scan_seconds, 1)}
                            for r in run.refs.values()}
    sec.counts["skipped"] = dict(sorted(skipped.items()))
    sec.counts["skipped_total"] = sum(skipped.values())
    sec.seconds = time.perf_counter() - t0
    if not quick:
        sec.counts["all_offers_accounted"] = sec.counts["offers_listed"] == (
            sec.counts["offers_checked"] + sec.counts["skipped_total"] + sec.counts.get(
                "skipped: the verifier abstains (no verdict to compare)", 0))
    return sec


# ---------------------------------------------------------------- the report


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.2f}"


def _envelope_lines(env: dict[str, Any], ec: dict[str, Any]) -> list[str]:
    buyers = "; ".join(
        f"{b}: {'refused (no recurring invoice, open invoice or expected order)' if v['refused'] else str(v['packages']) + ' packages (' + str(v['approved']) + ' approved), ' + str(v['zone_rows']) + ' zone rows, ' + str(v['evaluations']) + ' evaluations, ' + str(v['envelope_seconds']) + ' s'}"
        for b, v in ec["buyers"].items())
    verdicts = ", ".join(f"{k.split(': ')[1]} {v}" for k, v in sorted(ec.items()) if k.startswith("verdicts: ")) or "none"
    not_tested = [f"{k[len('passing offers not tested '):]} {v}" for k, v in ec.items() if k.startswith("passing offers not tested")]
    skipped = "; ".join(f"{k}: {v}" for k, v in ec["skipped"].items()) or "none"
    abstain = ec.get("skipped: the verifier abstains (no verdict to compare)", 0)
    out = [
        f"- Mode: {ec['mode']}. Offer files: {'; '.join(ec['files'])}.",
        (f"- Offers listed: {ec['offers_listed']}; checked: {ec['offers_checked']} (verdicts {verdicts}); not buyers on the golden "
         f"books, skipped: {ec['skipped_total']} ({skipped}); the verifier abstains (NO_VERDICT), nothing to compare: {abstain}."),
        (f"- Compiled from (`LLM_MODE=cache`: the fixture cache, then the rules grammar for a document set that is not cached): "
         f"{', '.join(f'{k} {v}' for k, v in ec['compiled_from'].items())}."),
        f"- Buyers swept (once each): {buyers}. Refusals: {ec['refusals']} offers whose buyer has no lever.",
        (f"- Counters of the verdicts: {ec['counters_inside']} of {ec['counters_checked']} are inside the envelope (approved "
         f"when probed); {ec['counters_listed']} of them are listed among the grid's packages and {ec['counters_inside_not_listed']} "
         f"are approved when probed without being listed."),
        (f"- Zone tests (passing offer with terms and price only): {ec['zone_tests_inside']} of {ec['zone_tests']} inside. "
         f"Probes (passing offer with an early-pay or rebate lever): {ec['probes_agree']} of {ec['probes']} agree with the verdict."),
        (f"- Re-check: {ec['packages_rechecked']} packages re-evaluated from scratch and put to `infeasibility`, "
         f"{ec['packages_approved']} approved. Lever maxima confirmed by the neighbour check: {ec['lever_maxima_confirmed']} of "
         f"{ec['lever_maxima_checked']}."),
        (f"- Bisection against the exhaustive terms x price scan ({sum(v['scan_cells'] for v in ec['buyers'].values())} cells): "
         f"{ec['exhaustive_agreements']} of {ec['exhaustive_comparisons']} comparisons agree (the zone's smallest passing price at "
         f"each terms value, and the longest terms alone, with the budget ignored, and with a price)."),
        f"- Passing offers the sweep cannot test: {'; '.join(not_tested) or 'none'}.",
        f"- Runtime: {env['seconds']:.1f} s.",
    ]
    out += [f"- Note: {n}" for n in env["notes"]]
    return out


def _clock_lines(clk: dict[str, Any], kc: dict[str, Any], swept_actions: str) -> list[str]:
    out = [
        (f"- Each scenario's end state is advanced in process with `Runtime.advance_to` (what `POST /clock/advance` calls) to "
         f"days {kc['days']}, and the replay's checks run at each: {kc['states']} states, {kc['distinct_book_states']} "
         f"distinct. Clock-advance errors: {kc['advance_errors']}; days already passed: {kc['days_already_passed']}."),
        f"- Actions over all days: {swept_actions}.",
        "",
        "| Day | States | Rows | Ceilings | Overdue rows | Actions | Net order differs (of 2+ rows) | Flat curves | Bands | Slowest state |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for day, d in kc["by_day"].items():
        slow = d["slowest_state"]
        slowest = f"{slow['scenario']} (worth {slow['worth_s']} s, curve {slow['curve_s']} s)" if slow else "-"
        acts = ", ".join(f"{k} {v}" for k, v in d["actions"].items()) or "none"
        out.append(f"| {day} | {d['states']} | {d['rows']} | {d['ceilings']} | {d['overdue_rows']} | {acts} | "
                   f"{d['net_order_differs']} of {d['states_with_two_or_more_rows']} | {d['flat_curves']} | {d['bands']} | {slowest} |")
    slowest5 = "; ".join(f"{x['scenario']} day {x['day']}: worth {x['worth_s']} s, curve {x['curve_s']} s" for x in kc["slowest_states"])
    out += ["", f"- Slowest states overall: {slowest5 or 'none'}.", f"- Analysis time: {clk['seconds']:.1f} s."]
    return out


def render(result: dict[str, Any]) -> str:
    secs: dict[str, dict[str, Any]] = {s["name"]: s for s in result["sections"]}
    col, cur, dif, env, clk = secs["collections"], secs["curve"], secs["differential"], secs["envelope"], secs["clock"]
    cc, uc, dc, ec, kc = col["counts"], cur["counts"], dif["counts"], env["counts"], clk["counts"]
    verdict = "PASS" if result["failures_total"] == 0 else "FAIL"
    quick = " --quick" if result["quick"] else ""
    slowest = "; ".join(f"{x['scenario']} turn {x['turn']} {x['seconds']} s" for x in cc["slowest_turns"])
    every = ("call_now", "escalate", "reminder", "offer_early_pay", "finance", "wait")
    unseen = ", ".join(a for a in every if a not in cc["actions"]) or "none"
    unseen_both = ", ".join(a for a in every if a not in cc["actions"] and a not in kc["actions"]) or "none"
    actions = ", ".join(f"{k} {v}" for k, v in cc["actions"].items()) or "none"
    swept_actions = ", ".join(f"{k} {v}" for k, v in kc["actions"].items()) or "none"
    sweep_days = kc["days"]
    lines: list[str] = [
        f"# Strategy backtest, {result['date']}",
        "",
        (f"Wave 6 of map #47 (`services/api/scripts/strategy_backtest.py{quick}`). Result: **{verdict}** "
         f"({result['failures_total']} failures, {result['skipped']} sections skipped), {result['seconds']:.0f} s in all."),
        "",
        "| Section | Status | Failures | Seconds |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {s['name']} | {s['status']} | {len(s['failures'])} | {s['seconds']:.1f} |" for s in result["sections"]]
    lines += [
        "",
        "## Collections: `receivables_worth` after every turn",
        "",
        (f"- Scenarios replayed: {cc['scenarios']}; turns replayed: {cc['turns']}; distinct book states analysed: "
         f"{cc['distinct_book_states']} (a turn that leaves the books as they were reuses the answer, and its failures "
         f"are still counted against it)."),
        (f"- Rows checked: {cc['rows_checked']}; ceilings checked: {cc['ceilings_checked']}; turns with no open "
         f"receivable: {cc['turns_without_rows']}."),
        (f"- Turns where the net order differs from the overdue-amount order: {cc['net_order_differs_from_amount_order']} "
         f"of {cc['turns_with_two_or_more_rows']} turns with two or more rows."),
        f"- Actions (rows): {actions}; never produced by the replay: {unseen}.",
        (f"- Coverage: the replay stays on simulated days {cc['days_covered']} (overdue rows {cc['overdue_rows']}, most rows "
         f"in one turn {cc['max_rows_in_a_turn']}); the clock sweep below adds days {sweep_days} (overdue rows "
         f"{sum(d['overdue_rows'] for d in kc['by_day'].values())}). Actions never produced by replay and sweep together: "
         f"{unseen_both}."),
        f"- Scenario turns the /nl route did not answer with 200: {cc['non_200_turns']} (not a failure of this backtest).",
        f"- Analysis time: {col['seconds']:.1f} s; slowest book states: {slowest}.",
        "",
        "## Curve: `price_curve` at the same turns",
        "",
        f"- Turns: {uc['turns']}; bands checked: {uc['bands_checked']}; band-end pair checks: {uc['band_end_checks']}.",
        f"- Flat-curve turns: {uc['flat_turns']}; `varies` bands: {uc['varies_bands']}.",
        f"- Analysis time: {cur['seconds']:.1f} s.",
        "",
        "## Differential: the golden books against `collections_both.json`",
        "",
        f"- Checks: {dc['checks']}, to the fen.",
    ]
    lines += [f"  - {k}: {v}" for k, v in dc["by_kind"].items()]
    lines += ["", "The replay's invariants on the same two books (they have the multi-row, overdue and call-now cases the scenarios lack):", ""]
    lines += [f"- {x}" for x in dc["invariants"]]
    lines += ["", "Expected differences (not failures):", ""]
    lines += [f"- {x}" for x in dc["expected_differences"]] or ["- none"]
    lines += ["", "## Envelope", ""]
    lines += _envelope_lines(env, ec)
    lines += ["", "## Clock sweep: `receivables_worth` and `price_curve` after the clock moves", ""]
    lines += _clock_lines(clk, kc, swept_actions)
    lines.append("")
    fails = [f for s in result["sections"] for f in s["failures"]]
    lines += ["## Failures", ""]
    if not fails:
        lines.append("None.")
    else:
        lines += ["| Section | Scenario | Turn | Figure | Message |", "| --- | --- | --- | --- | --- |"]
        lines += [f"| {f['section']} | {f['scenario']} | {f['turn']} | {f['figure']} | {f['message'].replace('|', '/')} |"
                  for f in fails[:MAX_FAILURES_IN_REPORT]]
        if len(fails) > MAX_FAILURES_IN_REPORT:
            lines.append(f"\n{len(fails) - MAX_FAILURES_IN_REPORT} more in the JSON output.")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the result as JSON on stdout")
    ap.add_argument("--quick", action="store_true", help="the golden scenario only; no report unless --out is given")
    ap.add_argument("--out", help="the Markdown report (default docs/research/strategy/06-backtest-<date>.md)")
    args = ap.parse_args(argv)
    started = time.perf_counter()
    today = date.today().isoformat()  # noqa: DTZ011 - the local date names the report
    collections, curve, clock = Section("collections"), Section("curve"), Section("clock")
    replay(args.quick, collections, curve, clock)
    print("differential: golden day-0 and day-34 books against the oracle", file=sys.stderr, flush=True)
    diff = differential()
    envelope = check_envelope(args.quick)
    sections = [collections, curve, clock, diff, envelope]
    result: dict[str, Any] = {
        "date": today, "quick": args.quick, "seconds": round(time.perf_counter() - started, 1),
        "failures_total": sum(len(s.failures) for s in sections),
        "skipped": sum(s.status == "skipped" for s in sections),
        "sections": [{"name": s.name, "status": s.status, "seconds": round(s.seconds, 1), "counts": s.counts,
                      "notes": s.notes, "failures": [asdict(f) for f in s.failures]} for s in sections]}
    out = Path(args.out) if args.out else (None if args.quick else REPORT_DIR / f"06-backtest-{today}.md")
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(result), encoding="utf-8")
        print(f"report: {out}", file=sys.stderr)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{'PASS' if result['failures_total'] == 0 else 'FAIL'}: {result['failures_total']} failures, "
              f"{collections.counts.get('turns', 0)} turns, {result['seconds']} s")
    return 1 if result["failures_total"] else 0


if __name__ == "__main__":
    sys.exit(main())
