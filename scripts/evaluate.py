#!/usr/bin/env python3
"""Measure the integrated TermsLedger v2 system and write the evaluation report.

Usage (from the repo root):
  uv run --project services/api python scripts/evaluate.py                 # every suite, offline
  uv run --project services/api python scripts/evaluate.py --suite offers --only H10b_today_1_6pct
  uv run --project services/api python scripts/evaluate.py --suite funding --only R01 --workers 1
  uv run --project services/api python scripts/evaluate.py --live          # the configured LLM backends
  uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout2

Suites: offers (E2), financial (E3/E10), funding (E9), covenants, security, intent, e2e (E7), no_deal (E5).
Offline (default) sets LLM_MODE=cache: recorded compiler outputs where they exist, else the rules grammar.
A full run writes services/api/evals/latest_report.{json,md}; a run limited by --suite or --only writes to
--out (default: a temporary directory) so the committed report is only replaced by a complete run.
Exit status: 0, or 1 with --strict when a target is missed, or 2 when a suite crashes.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"
SUITES = ["offers", "financial", "funding", "covenants", "security", "intent", "e2e", "no_deal"]


def _bootstrap(live: bool) -> None:
    os.environ["LLM_MODE"] = "live" if live else "cache"
    if not live:
        os.environ["TERMSLEDGER_NO_DOTENV"] = "1"  # offline: never read developer keys
    sys.path.insert(0, str(API))
    try:
        import fastapi  # noqa: F401
        import yaml  # noqa: F401
    except ImportError:
        if os.environ.get("TL_EVAL_REEXEC") or not shutil.which("uv"):
            raise
        env = {**os.environ, "TL_EVAL_REEXEC": "1"}
        cmd = ["uv", "run", "--project", str(API), "python", str(Path(__file__).resolve()), *sys.argv[1:]]
        sys.exit(subprocess.run(cmd, env=env, check=False).returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="use the configured LLM backends (network, keys from .env)")
    ap.add_argument("--suite", action="append", help=f"run only these suites (repeatable or comma-separated): {SUITES}")
    ap.add_argument("--only", help="comma-separated item ids inside the chosen suites (offers, intent, funding, e2e)")
    ap.add_argument("--fast", action="store_true", help="a coarser, smaller funding brute force (smoke runs)")
    ap.add_argument("--funding-random", type=int, default=16, help="seeded random funding scenarios (default 16)")
    ap.add_argument("--funding-budget", type=float, default=180.0, help="brute-force seconds per funding scenario")
    ap.add_argument("--workers", type=int, help="processes for the funding brute force (default: cores − 1, max 8)")
    ap.add_argument("--heldout", help="directory holding an alternate offers.yaml / intents.yaml for the offers and "
                    "intent suites (default fixtures/heldout), e.g. fixtures/heldout2")
    ap.add_argument("--out", help="directory for latest_report.{json,md}")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any target is missed")
    ap.add_argument("--probe", help="compile and verify one buyer message on the golden state, print, and exit")
    ap.add_argument("--counterparty", default="BUYER-1", help="sender of --probe (default BUYER-1)")
    args = ap.parse_args()
    _bootstrap(args.live)

    if args.probe:
        from evals.runner import probe

        probe(args.probe, args.counterparty)
        return 0

    from evals.runner import main as run_eval

    suites = [s for part in (args.suite or [",".join(SUITES)]) for s in part.split(",") if s]
    unknown = sorted(set(suites) - set(SUITES))
    if unknown:
        ap.error(f"unknown suite(s) {unknown}; choose from {SUITES}")
    only = [x for x in (args.only or "").split(",") if x] or None
    funding = {"n_random": args.funding_random, "budget_s": args.funding_budget, "workers": args.workers}
    if args.fast:
        funding.update({"n_random": 2, "step2_fen": 2_000_000, "step3_fen": 5_000_000, "budget_s": 20.0})
    heldout = {"heldout": args.heldout} if args.heldout else {}
    options = {"funding": {**funding, "only": only}, "offers": {"only": only, **heldout},
               "intent": {"only": only, **heldout}, "e2e": {"only": only}}
    partial = bool(args.suite or only or args.fast or args.heldout)
    out = Path(args.out) if args.out else (Path(tempfile.mkdtemp(prefix="tl-eval-")) if partial else None)
    command = "uv run --project services/api python scripts/evaluate.py " + " ".join(shlex.quote(a) for a in sys.argv[1:])
    rep, jp, mp = run_eval(suites, options, out, command.strip())

    width = max((len(s["label"]) for s in rep["summary"]), default=10)
    print()
    for s in rep["summary"]:
        print(f"{s['status']:5} {s['label']:<{width}}  {s['display']}  (target {s['target']})")
    print(f"\n{len(rep['failures'])} failure(s). Report: {mp}\n                  {jp}")
    if any(r["error"] for r in rep["suites"].values()):
        return 2
    if args.strict and any(s["status"] == "FAIL" for s in rep["summary"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
