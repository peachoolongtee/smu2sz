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
from app.domain.models import Mandate
from app.domain.money import bp, post, round_half_up
from app.financial import EngineError
from app.funding import NoPermanentSourceError
from app.funding.rates import break_even_cost_share
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy.collections import ReceivableWorth, WorthAnswer, early_pay_vs_plan, receivables_worth
from app.strategy.impact import marginal_impact, scenario_inflow
from app.strategy.price_curve import WINDOW_DAYS, PriceCurve, price_curve
from app.verifier.evaluate import clear_caches
from app.whatif.params import DISCOUNT_MAX_BP

SCENARIOS = API / "evals" / "e2e" / "scenarios.yaml"
ORACLE = ROOT / "fixtures" / "strategy" / "collections_both.json"
RUNNER = ROOT / "scripts" / "run_scenarios.py"
REPORT_DIR = ROOT / "docs" / "research" / "strategy"
QUICK_SCENARIO = "S01_scene1_counter_accept"  # the golden scenario: EX01 evaluated, countered, agreed
OWNER = {"X-Owner-Token": "demo-owner-token"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
FACE_KIND = {"the whole outstanding invoice": "whole", "the shortfall the plan covers": "need"}
# The one known difference from the oracle: on day 0 the module values the net saving on the plan's-need face
# (RCV-A, 0.75% on ¥405,000: ¥59.39); the spike's `net_value_at_ceiling` is on the whole face (0.70%: ¥173.93).
EXPECTED_DAY0_NET = {"RCV-A": (5_939, 17_393)}
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


def replay(quick: bool, collections: Section, curve: Section) -> None:
    import yaml

    scenarios: list[dict[str, Any]] = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
    if quick:
        scenarios = [s for s in scenarios if s["id"] == QUICK_SCENARIO]
    transport = _load_runner().InProc()
    memo: dict[str, Analysis] = {}
    actions: Counter[str] = Counter()
    slowest: list[tuple[float, str, int]] = []
    collections.counts.update({"scenarios": len(scenarios), "turns": 0, "distinct_book_states": 0, "rows_checked": 0,
                               "ceilings_checked": 0, "turns_with_two_or_more_rows": 0,
                               "net_order_differs_from_amount_order": 0, "turns_without_rows": 0, "non_200_turns": 0})
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
                _record(scn["id"], n, a, collections, curve, actions)
            print(f"[{i}/{len(scenarios)}] {scn['id']}: {len(turns)} turns, {fresh} new book states, "
                  f"{time.perf_counter() - t_scn:.1f}s", file=sys.stderr, flush=True)
    finally:
        set_runtime(None)
    collections.counts["actions"] = dict(sorted(actions.items()))
    collections.counts["slowest_turns"] = [{"scenario": s, "turn": n, "seconds": round(t, 2)}
                                           for t, s, n in sorted(slowest, reverse=True)[:5]]


def _record(scn: str, n: int, a: Analysis, collections: Section, curve: Section, actions: Counter[str]) -> None:
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
    rt0 = _runtime()
    rt34 = _runtime()
    _replay_to_day34(rt34)
    for which, rt in ((0, rt0), (34, rt34)):
        name = f"day {which}"
        book = next(b for b in oracle if b["books"] == name)
        books, mandate = books_from_store(rt.store), rt.store.get_mandate()

        def bad(figure: str, message: str, _name: str = name) -> None:
            sec.fail(_name, 0, figure, message)

        answer = receivables_worth(books, mandate, store=rt.store, day=which)
        curve = price_curve(books, mandate, store=rt.store, day=which)
        counts[f"{name} books"] += 1
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
                  "expected_differences": expected}
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
        expected.append(f"{name} {rid}: net saving {w.net_saving_fen} fen (plan's-need face) vs the oracle's net_value_at_ceiling "
                        f"{want_net} fen (whole face): the module values the discount on the plan's need, as the brief says")
    else:
        bad(f"{rid} net value at the ceiling", f"net saving {w.net_saving_fen} fen vs oracle {want_net} fen")


# ---------------------------------------------------------------- section 4: the envelope


def check_envelope() -> Section:
    """The brief's section 9 item 1 for the Safe Deal Envelope. Skipped until `app.strategy.envelope` is on this branch.

    TODO (follow-up once Wave 3 is merged): for every offer in `fixtures/offers/offers.yaml` and `fixtures/heldout*/`,
    on the golden books:
      - compile and evaluate the offer (`verifier.evaluate`), then build the envelope for its buyer;
      - every counter in the verdict appears among the packages (same terms, price, early-pay rate and face, rebate);
      - "as asked" is inside the zone if and only if the verdict passes;
      - every package passes its re-check (`evaluate`) and `counters.infeasibility` is None;
      - the bisection agrees with the exhaustive grid for every lever;
      - count the refusals (a buyer with no recurring invoice and no open invoice).
    Count the offers, the packages and the refusals, and record each failure with the offer id as the scenario.
    """
    sec = Section("envelope", status="skipped")
    if importlib.util.find_spec("app.strategy.envelope") is None:
        sec.notes.append("envelope checks: module not on this branch yet; skipped")
    else:
        sec.notes.append("envelope checks: module present, checks not written yet (see the TODO); skipped")
    print(sec.notes[0], file=sys.stderr)
    return sec


# ---------------------------------------------------------------- the report


def _money(fen: int) -> str:
    return f"¥{fen / 100:,.2f}"


def render(result: dict[str, Any]) -> str:
    secs: dict[str, dict[str, Any]] = {s["name"]: s for s in result["sections"]}
    col, cur, dif, env = secs["collections"], secs["curve"], secs["differential"], secs["envelope"]
    cc, uc, dc = col["counts"], cur["counts"], dif["counts"]
    verdict = "PASS" if result["failures_total"] == 0 else "FAIL"
    quick = " --quick" if result["quick"] else ""
    slowest = "; ".join(f"{x['scenario']} turn {x['turn']} {x['seconds']} s" for x in cc["slowest_turns"])
    actions = ", ".join(f"{k} {v}" for k, v in cc["actions"].items()) or "none"
    lines: list[str] = [
        f"# Strategy backtest, {result['date']}",
        "",
        (f"Wave 6 of map #47 (`services/api/scripts/strategy_backtest.py{quick}`). Result: **{verdict}** "
         f"({result['failures_total']} failures, {result['skipped']} section skipped), {result['seconds']:.0f} s in all."),
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
        f"- Actions (rows): {actions}.",
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
    lines += ["", "Expected differences (not failures):", ""]
    lines += [f"- {x}" for x in dc["expected_differences"]] or ["- none"]
    lines += ["", "## Envelope", "", *(f"- {n}" for n in env["notes"]), ""]
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
    collections, curve = Section("collections"), Section("curve")
    replay(args.quick, collections, curve)
    print("differential: golden day-0 and day-34 books against the oracle", file=sys.stderr, flush=True)
    diff = differential()
    envelope = check_envelope()
    sections = [collections, curve, diff, envelope]
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
