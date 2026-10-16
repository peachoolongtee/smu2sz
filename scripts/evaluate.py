#!/usr/bin/env python3
"""Measure the integrated TermsLedger v2 system and write the evaluation report.

Usage (from the repo root):
  DEMO_MODE=1 uv run --project services/api python scripts/evaluate.py                 # every suite, offline
  DEMO_MODE=1 uv run --project services/api python scripts/evaluate.py --suite offers --only H10b_today_1_6pct
  DEMO_MODE=1 uv run --project services/api python scripts/evaluate.py --suite funding --only R01 --workers 1
  DEMO_MODE=1 uv run --project services/api python scripts/evaluate.py --live          # the configured LLM backends
  DEMO_MODE=1 uv run --project services/api python scripts/evaluate.py --suite offers --heldout fixtures/heldout2

Suites: offers (E2), financial (E3/E10), funding (E9), covenants, security, intent, e2e (E7), no_deal (E5).
Offline (default) sets LLM_MODE=cache: recorded compiler outputs where they exist, else the rules grammar.
A full run writes services/api/evals/latest_report.{json,md}; a run limited by --suite or --only writes to
--out (default: a temporary directory) so the committed report is only replaced by a complete run.
Exit status: 0, or 1 with --strict when a target is missed, or 2 when a suite crashes.
"""

from __future__ import annotations

import argparse
import json
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
    if live:  # read the developer's keys (DEEPSEEK_API / ANTHROPIC_API_KEY) from the repo-root .env
        from app.config import load_dotenv

        load_dotenv()
        if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
            raise SystemExit("--live needs DEEPSEEK_API_KEY or ANTHROPIC_API_KEY (repo-root .env)")
    try:
        import fastapi  # noqa: F401
        import yaml  # noqa: F401
    except ImportError:
        if os.environ.get("TL_EVAL_REEXEC") or not shutil.which("uv"):
            raise
        env = {**os.environ, "TL_EVAL_REEXEC": "1"}
        cmd = ["uv", "run", "--project", str(API), "python", str(Path(__file__).resolve()), *sys.argv[1:]]
        sys.exit(subprocess.run(cmd, env=env, check=False).returncode)


def nl_attack_rows() -> tuple[list[dict], list[dict]]:
    """Summary rows (and failures) computed from a fresh run of the /nl attack group: nothing here is a literal.

    The group runs in-process through the real POST /nl route as a counterparty, as the owner and with the agent
    key (`app.security.attacks.nl_catalogue`); harm is read from the store after each attack."""
    from app.security.attacks import NlAttackRunner

    repro = "cd services/api && uv run python -m app.security.attacks --report"
    obs = NlAttackRunner().run_all()
    harmed = [o for o in obs if o.harm]
    unauthorised = sum(o.unauthorised_ops for o in obs)
    disclosed = sorted({lbl for o in obs for lbl in o.leaks})
    scanned = sum(o.outbound_texts + o.measurements.get("scoreboard", {}).get("outbound_texts_scanned", 0) for o in obs)
    report = json.loads((API / "evals" / "security" / "latest_report.json").read_text(encoding="utf-8"))
    api_disclosed = report["metrics"]["all_attacks_metrics"]["protected_values_disclosed_outbound"]
    disclosed_total = len(disclosed) + api_disclosed

    def row(key: str, label: str, value: int, display: str, note: str = "") -> dict:
        return {"suite": "security", "key": key, "label": label, "value": value, "display": display, "target": "0",
                "status": "PASS" if value == 0 else "FAIL", "note": note}

    rows = [
        row("nl_attacks_with_harm", "Attacks through /nl with harm", len(harmed), f"{len(harmed)}/{len(obs)}",
            ", ".join(o.id for o in harmed)),
        row("protected_fields_disclosed",
            "Protected fields disclosed (computed scan of all outbound texts and counterparty responses)",
            disclosed_total, f"{disclosed_total} ({scanned} /nl texts and responses scanned)",
            ", ".join(disclosed)),
        row("nl_unauthorised_operations", "Unauthorised operations via /nl", unauthorised, str(unauthorised),
            ", ".join(f"{o.id}: {o.executed_ops}" for o in obs if o.unauthorised_ops)),
    ]
    failures = [{"suite": "security", "id": o.id, "what": f"{o.id} {o.title.splitlines()[0]}: " + "; ".join(o.harm_reasons),
                 "repro": repro, "detail": {"entry_point": o.entry_point, "known_finding": o.known_finding}}
                for o in harmed]
    return rows, failures


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
    command = "DEMO_MODE=1 uv run --project services/api python scripts/evaluate.py " + " ".join(shlex.quote(a) for a in sys.argv[1:])
    rep, jp, mp = run_eval(suites, options, out, command.strip())
    if "security" in suites:  # the /nl attack group is run here, so its rows are computed, not imported
        from evals.runner import to_markdown

        rows, failures = nl_attack_rows()
        rep["summary"].extend(rows)
        rep["failures"].extend(failures)
        jp.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
        mp.write_text(to_markdown(rep), encoding="utf-8")

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
