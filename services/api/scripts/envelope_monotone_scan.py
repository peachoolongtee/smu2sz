#!/usr/bin/env python3
"""The envelope's weekly monotonicity scan (ticket #98, P5; brief E.2): never in the online path.

The online envelope reads its levers by bisection with neighbour checks, which proves a local boundary, not that a lever is
monotone. Once a week this script puts every terms x price cell of each buyer's ranges to the same verifier the envelope uses
(`app.strategy.envelope._Verifier`, a fresh memo), plus the early-payment face column of an asked term at the smallest rate,
and compares the scan with what the online envelope answered:

  - the zone: the smallest approved price at each term;
  - the three terms levers: the longest term that passes at today's price, that is financially safe with the caps ignored,
    and that is approved at the top price;
  - each column (a term, every price) and each row (a price, every term): approved must not fail again once it passes as the
    price rises, nor pass again once it fails as the term lengthens;
  - with `--ask T`: the ask's answer (`compensate`): its smallest price, or, when no price works, its smallest face, which
    must pass with the face ¥100 below it failing, every scanned face below it failing and every one above passing.

Any disagreement is printed to stderr as a line starting "DISAGREEMENT" and the exit code is 1; agreement exits 0. About 273
evaluations per buyer with terms (55 to 110 s on the public-record SME), more with the face column.

Usage (from the repository root):

    TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \\
      uv run --project services/api python services/api/scripts/envelope_monotone_scan.py \\
        [--state STATE.json --mandate MANDATE.json] [--day N] [--buyer ID ...] [--ask T] [--face-step-fen F] [--json]

Without `--state` the golden Demo books are scanned. Read-only: nothing is written.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.books import Books, books_from_store
from app.domain.models import Mandate
from app.strategy.envelope import (
    FACE_STEP_FEN,
    RATE_STEP_BP,
    AskFacts,
    EnvelopeFacts,
    Setting,
    _sweep_ranges,
    _Verifier,
    envelope_ask,
    envelope_facts,
    open_context,
)
from app.whatif.params import WhatIfParamError


@dataclass(frozen=True)
class Cell:
    passes: bool
    approved: bool
    liquidity_only: bool


@dataclass
class Scan:
    """One buyer's exhaustive scan: every (terms, price) cell, and the face column of the ask at the smallest rate and the
    top price (face -> approved)."""

    buyer_id: str
    current_terms: int
    terms: tuple[int, ...]
    prices: tuple[int, ...]
    grid: dict[tuple[int, int], Cell] = field(default_factory=dict)
    faces: dict[int, bool] = field(default_factory=dict)
    face_checks: dict[int, bool] = field(default_factory=dict)  # the ask's face and the face ¥100 below it
    evaluations: int = 0
    seconds: float = 0.0


def scan_buyer(books: Books, mandate: Mandate, key: str, day: int, buyer_id: str, ask: AskFacts | None,
               face_step_fen: int) -> Scan | None:
    """Every terms x price cell on the envelope's own verifier; None for a buyer with no terms lever."""
    started = time.perf_counter()
    try:
        ctx = open_context(books.state, day, buyer_id)
    except WhatIfParamError:
        return None
    ranges, _, no_plan = _sweep_ranges(books, mandate, ctx)
    if not ranges.terms or no_plan:
        return None
    v = _Verifier(books, mandate, key, day, (), ctx, ranges)
    out = Scan(buyer_id, v.cur, ranges.terms, ranges.price)
    for t in ranges.terms:
        for p in ranges.price:
            q = v.quick(Setting(t, price=p))
            out.grid[(t, p)] = Cell(q.passes, q.approved, q.liquidity_only)
    if ask is not None and ask.price_only is None and ask.terms_days in ranges.terms and RATE_STEP_BP in ranges.discount:
        pmax = ranges.price[-1]
        step = max(FACE_STEP_FEN, face_step_fen - face_step_fen % FACE_STEP_FEN)
        for f in range(step, ranges.face_max_fen + 1, step):
            out.faces[f] = v.quick(Setting(ask.terms_days, price=pmax, discount=RATE_STEP_BP, face=f)).approved
        if ask.with_early is not None and ask.with_early.setting.face is not None:
            f = ask.with_early.setting.face
            for g in (f, f - FACE_STEP_FEN):
                if g > 0:
                    out.face_checks[g] = v.quick(Setting(ask.terms_days, price=pmax, discount=RATE_STEP_BP, face=g)).approved
    out.evaluations, out.seconds = v.evaluations, time.perf_counter() - started
    return out


def disagreements(facts: EnvelopeFacts, scan: Scan, ask: AskFacts | None = None) -> list[str]:
    """Where the online envelope and the exhaustive scan disagree, and where the scan finds a lever that is not monotone.
    Empty: they agree."""
    out: list[str] = []
    who = scan.buyer_id
    grid, prices = scan.grid, scan.prices
    pmax = prices[-1]
    up = [t for t in scan.terms if t >= scan.current_terms]

    def say(what: str, online: object, scanned: object) -> None:
        if online != scanned:
            out.append(f"{who}: {what}: online {online}, exhaustive scan {scanned}")

    for z in facts.zone:
        say(f"zone, smallest approved price at {z.terms_days} days", z.min_price_bp,
            next((p for p in prices if grid[(z.terms_days, p)].approved), None))
    by = {m.key: m for m in facts.maxima}
    if "terms_alone" in by and not by["terms_alone"].unavailable:
        say("terms alone, longest passing", by["terms_alone"].value, max((t for t in up if grid[(t, 0)].passes), default=None))
    if "terms_budget_ignored" in by and not by["terms_budget_ignored"].unavailable:
        say("terms with the caps ignored, longest", by["terms_budget_ignored"].value,
            max((t for t in up if grid[(t, 0)].liquidity_only), default=None))
    if "terms_with_price" in by and not by["terms_with_price"].unavailable:
        say("terms with a price rise, longest approved", by["terms_with_price"].value,
            max((t for t in up if grid[(t, pmax)].approved), default=None))
    for t in scan.terms:  # a column: once a price passes, every higher price passes
        column = [grid[(t, p)].approved for p in prices]
        if any(column) and not all(column[column.index(True):]):
            out.append(f"{who}: not monotone in the price at {t} days: {''.join('P' if c else '.' for c in column)}")
    for p in prices:  # a row: once a term fails, every longer term fails
        row = [grid[(t, p)].approved for t in up]
        if not all(row) and any(row[row.index(False):]):
            out.append(f"{who}: not monotone in the terms at a {p} bp price rise: {''.join('P' if c else '.' for c in row)}")
    if ask is not None and not ask.refusal and ask.terms_days in scan.terms:
        if ask.price_only is not None:
            say(f"the ask at {ask.terms_days} days, smallest approved price", ask.price_only.setting.price,
                next((p for p in prices if grid[(ask.terms_days, p)].approved), None))
        else:
            say(f"the ask at {ask.terms_days} days, a price that works", None,
                next((p for p in prices if grid[(ask.terms_days, p)].approved), None))
            face = ask.with_early.setting.face if ask.with_early is not None else None
            if face is not None:
                if not scan.face_checks.get(face, False) or scan.face_checks.get(face - FACE_STEP_FEN, False):
                    out.append(f"{who}: the ask's smallest face {face} is not a boundary: {scan.face_checks}")
                wrong = [f for f, ok in scan.faces.items() if ok != (f >= face)]
                if wrong:
                    out.append(f"{who}: the face column disagrees with the ask's smallest face {face} at {wrong}")
            elif any(scan.faces.values()):
                out.append(f"{who}: the ask found no face, the scan passes at {[f for f, ok in scan.faces.items() if ok]}")
    return out


def _books(args: argparse.Namespace) -> tuple[Books, Mandate, str]:
    if args.state is not None:
        sys.path.insert(0, str(HERE))
        from pilot_runtime import (
            build_runtime,  # the pilot's own loader: the same store calls the runtime uses
        )

        rt = build_runtime(Path(args.state), Path(args.mandate), None)
    else:
        from app.api.runtime import Runtime
        from app.config import get_settings
        from app.mandate.fixture import demo_owner_public_key_hex
        from app.persistence import InMemoryLedgerStore

        rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
        rt.reset()
    return books_from_store(rt.store), rt.store.get_mandate(), rt.owner_key_hex


def run(books: Books, mandate: Mandate, key: str, *, day: int, buyers: Sequence[str], ask_terms: int | None,
        face_step_fen: int) -> dict[str, Any]:
    report: dict[str, Any] = {"day": day, "buyers": {}, "disagreements": []}
    for buyer in buyers:
        facts = envelope_facts(books, mandate, day=day, buyer_id=buyer, trusted_owner_key_hex=key, zone=True)
        if facts.refused:
            report["buyers"][buyer] = {"skipped": "no lever"}
            continue
        ask = envelope_ask(books, mandate, day=day, buyer_id=buyer, trusted_owner_key_hex=key, terms=ask_terms) \
            if ask_terms is not None else None
        scan = scan_buyer(books, mandate, key, day, buyer, ask, face_step_fen)
        if scan is None:
            report["buyers"][buyer] = {"skipped": "no terms lever"}
            continue
        found = disagreements(facts, scan, ask)
        report["buyers"][buyer] = {"cells": len(scan.grid), "faces": len(scan.faces), "evaluations": scan.evaluations,
                                   "seconds": round(scan.seconds, 1), "disagreements": len(found)}
        report["disagreements"] += found
    return report


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", help="the SME's books as JSON (default: the golden Demo books)")
    ap.add_argument("--mandate", help="the SME's mandate as JSON (with --state)")
    ap.add_argument("--day", type=int, default=0)
    ap.add_argument("--buyer", action="append", help="a buyer id (repeatable; default: every buyer on the books)")
    ap.add_argument("--ask", type=int, help="an asked term: compare its answer and scan its face column")
    ap.add_argument("--face-step-fen", type=int, default=1_000_000, help="the face column's step (default ¥10,000)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if (args.state is None) != (args.mandate is None):
        ap.error("--state and --mandate go together")
    books, mandate, key = _books(args)
    buyers = args.buyer or [c.id for c in books.state.counterparties]
    report = run(books, mandate, key, day=args.day, buyers=buyers, ask_terms=args.ask, face_step_fen=args.face_step_fen)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for buyer, row in report["buyers"].items():
            print(f"{buyer}: {row}")
    for line in report["disagreements"]:
        print(f"DISAGREEMENT {line}", file=sys.stderr)
    if report["disagreements"]:
        print(f"envelope monotonicity scan FAILED: {len(report['disagreements'])} disagreement(s)", file=sys.stderr)
        return 1
    print("envelope monotonicity scan: the online envelope and the exhaustive scan agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
