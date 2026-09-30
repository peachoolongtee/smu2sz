"""E7 end to end: the scripted /nl tasks (scripts/run_scenarios.py --inproc) for the task completion rate
and turn latency, plus the latency of golden Scene 1 through the HTTP API (FastAPI TestClient):
POST /offers (compile) → POST /offers/{id}/evaluate → POST /negotiate/{id} (the buyer accepts Option A; the
executor records the commitment and draws the line)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from evals.common import ROOT, Failure, InProcApi, Metric, SuiteResult, median, pct, quiet, ratio

REPRO_TASKS = "python3 scripts/run_scenarios.py --inproc --only {id} -v"
REPRO_SCENE = "uv run --project services/api python scripts/evaluate.py --suite e2e"


def scenario_tasks(out: Path | None = None, only: list[str] | None = None) -> dict[str, Any]:
    out = out or Path(tempfile.mkdtemp(prefix="tl-e2e-"))
    cmd = [sys.executable, str(ROOT / "scripts" / "run_scenarios.py"), "--inproc", "--out", str(out)]
    if only:
        cmd += ["--only", ",".join(only)]
    env = {**os.environ, "TERMSLEDGER_NO_DOTENV": "1", "TL_RUNNER_REEXEC": "1"}
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    wall = time.perf_counter() - t0
    path = out / "results.json"
    if not path.is_file():
        raise RuntimeError(f"run_scenarios.py wrote no results (exit {p.returncode}): {p.stderr[-1500:]}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"data": data, "exit": p.returncode, "stdout": p.stdout[-3000:], "out": str(out), "wall_s": round(wall, 1)}


def scene1(api: InProcApi, reps: int = 5) -> dict[str, Any]:
    from app.verifier import clear_caches

    runs = []
    for i in range(reps):
        api.reset()
        clear_caches()  # every repetition pays the full verifier cost (no warm router cache)
        steps: dict[str, float] = {}
        t0 = time.perf_counter()
        c1, off = api.post("/offers", {"fixture_id": "EX01_PACKAGE"})
        steps["compile_ms"] = (time.perf_counter() - t0) * 1000
        oid = (off.get("offer") or {}).get("offer_id")
        t1 = time.perf_counter()
        c2, ver = api.post(f"/offers/{oid}/evaluate", {"fixture_id": "EX01_PACKAGE"})
        steps["evaluate_ms"] = (time.perf_counter() - t1) * 1000
        t2 = time.perf_counter()
        c3, neg = api.post(f"/negotiate/{oid}", {"buyer_profile": "cooperative"})
        steps["negotiate_execute_ms"] = (time.perf_counter() - t2) * 1000
        steps["total_ms"] = (time.perf_counter() - t0) * 1000
        ops = [(o.get("kind"), o.get("status")) for o in neg.get("operations", [])]
        ok = (c1, c2, c3) == (200, 200, 200) and ver.get("outcome") == "REJECT" and neg.get("outcome") == "DEAL" \
            and bool(ops) and all(s == "EXECUTED" for _, s in ops)
        runs.append({"rep": i + 1, "ok": ok, "http": [c1, c2, c3], "outcome": ver.get("outcome"),
                     "negotiation": neg.get("outcome"), "accepted": neg.get("accepted_counter_id"), "operations": ops,
                     **{k: round(v, 1) for k, v in steps.items()}})
    return {"runs": runs}


def run(only: list[str] | None = None, api: InProcApi | None = None, reps: int = 5, **_: Any) -> SuiteResult:
    quiet()
    res = SuiteResult(name="e2e")
    tasks = scenario_tasks(only=only)
    data = tasks["data"]
    ran = [s for s in data["scenarios"] if s["status"] != "SKIPPED"]
    passed = [s for s in ran if s["status"] == "PASSED"]
    turn_ms = [t["latency_ms"] for s in ran for t in s["turns"]]
    rate = ratio(len(passed), len(ran))
    for s in ran:
        if s["status"] != "PASSED":
            res.failures.append(Failure("e2e", s["id"], f"{s['id']}: " + "; ".join(s.get("failures", []))[:400],
                                        REPRO_TASKS.format(id=s["id"])))
    api = api or InProcApi()
    sc = scene1(api, reps=reps)
    totals = [r["total_ms"] for r in sc["runs"]]
    sc_ok = all(r["ok"] for r in sc["runs"])
    if not sc_ok:
        res.failures.append(Failure("e2e", "scene1", f"Scene 1 did not complete: {sc['runs']}", REPRO_SCENE))
    res.details = {"tasks": {"summary": data["summary"], "exit": tasks["exit"], "out": tasks["out"],
                             "wall_s": tasks["wall_s"],
                             "rows": [{"id": s["id"], "status": s["status"], "latency_ms": s.get("latency_ms"),
                                       "turns": len(s["turns"]), "failures": s.get("failures", [])} for s in ran]},
                   "scene1": sc}
    res.metrics += [
        Metric("task_completion_rate", "Task completion rate (scripted /nl tasks)", rate,
               f"{len(passed)}/{len(ran)} ({(rate or 0):.0%})", "≥ 95%", (rate or 0) >= 0.95, "e2e"),
        Metric("turn_latency", "/nl turn latency p50 / p95", {"p50": median(turn_ms), "p95": pct(turn_ms, 95)},
               f"{median(turn_ms):.0f} / {pct(turn_ms, 95):.0f} ms ({len(turn_ms)} turns)", "informational", None, "e2e"),
        Metric("scene1_latency", "E2E latency, golden Scene 1 (compile → evaluate → negotiate → execute)",
               {"p50": median(totals), "p95": pct(totals, 95)},
               f"p50 {median(totals):.0f} ms, p95 {pct(totals, 95):.0f} ms over {len(totals)} cold runs"
               + ("" if sc_ok else " (FAILED)"), "completes", sc_ok, "e2e"),
    ]
    return res
