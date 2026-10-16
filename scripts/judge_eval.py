#!/usr/bin/env python3
"""One command for a judge: run FLOW's whole offline evidence and write a readable report.

Usage (from the repo root):
  uv run --project services/api python scripts/judge_eval.py [--out judge-report.md] [--artifacts DIR]
  python scripts/judge_eval.py            # re-runs itself under `uv run --project services/api` if needed

It runs, in one process, offline, deterministically and for free (LLM_MODE=cache, in-memory books, no network,
no keys, no .env):
  (a) the functional scenarios            scripts/run_scenarios.py  (services/api/evals/e2e/scenarios.yaml)
  (b) the adversarial attack catalogue    app.security.attacks      (API catalogue + the /nl catalogue)
  (c) the demo walk                       scripts/demo_run.py
  (d) a hash-chain check of the walk's log   scripts/verify_evidence.py, plus a tampered copy that must fail

It reuses those scripts' code and scoring; nothing is re-scored here. It writes <out> (Markdown) and a JSON next
to it (same name, .json). Exit status 0 only if every functional task passes, no attack causes harm, the demo walk
exits 0, the audit chain verifies and the tampered copy is rejected.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"
SCRIPTS = ROOT / "scripts"
DEFAULT_OUT = API / "evals" / "judge" / "judge-report.md"

# What "offline, free, deterministic" means here: forced, not defaulted, so a stray key can never be used.
FORCED_ENV = {"TERMSLEDGER_NO_DOTENV": "1", "DATABASE_URL": "memory", "LLM_MODE": "cache", "DEEPSEEK_API_KEY": "",
              "ANTHROPIC_API_KEY": "", "DEMO_MODE": "1", "PYTHONUTF8": "1"}

# Judge-facing classes over the attack categories (API catalogue and /nl catalogue).
ATTACK_CLASSES: "OrderedDict[str, tuple[str, ...]]" = OrderedDict([
    ("Prompt injection and social engineering",
     ("prompt_injection", "fake_lender", "fake_prior_concession", "social_engineering", "nl_counterparty_injection",
      "nl_owner_quoting_buyer")),
    ("Data extraction (mandate, reserve, other buyers, system prompt)",
     ("mandate_exfiltration", "reserve_facility_exfiltration", "cross_buyer", "canary_extraction",
      "nl_counterparty_extraction", "nl_oracle_probing")),
    ("Privilege escalation",
     ("privilege_escalation", "nl_agent_channel")),
    ("Replay, expiry, forged mandate, changed terms",
     ("replay", "expired_commitment", "revoked_mandate", "changed_offer", "nl_replay_session")),
    ("Failure recovery (crash, outage, tampered log)", ("failure_recovery",)),
    ("Owner consent (negated, conditional or malformed instructions)", ("nl_owner_consent",)),
])


def _bootstrap() -> None:
    os.environ.update(FORCED_ENV)
    sys.path.insert(0, str(API))
    sys.path.insert(0, str(SCRIPTS))
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8")
    try:
        import fastapi  # noqa: F401
        import yaml  # noqa: F401
    except ImportError:
        if os.environ.get("TL_JUDGE_REEXEC") or not shutil.which("uv"):
            raise
        env = {**os.environ, "TL_JUDGE_REEXEC": "1"}
        cmd = ["uv", "run", "--project", str(API), "python", str(Path(__file__).resolve()), *sys.argv[1:]]
        sys.exit(subprocess.run(cmd, env=env, check=False).returncode)


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _cell(text: Any, n: int = 170) -> str:
    s = " ".join(str(text if text is not None else "").split()).replace("|", "/")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.2f}%" if d else "n/a"


# ---------------------------------------------------------------------------------------------- (a) functional


def _expect_text(exp: dict) -> str:
    parts = []
    for k, v in exp.items():
        if k in ("reply_contains", "reply_excludes"):
            parts.append(("reply has " if k == "reply_contains" else "reply lacks ") + ", ".join(f"'{x}'" for x in v))
        elif k.startswith("store_"):
            parts.append(f"stored {k[6:]}={v}")
        else:
            parts.append(f"{k}={v}")
    return "; ".join(parts) or "(no specific expectation)"


def run_functional(artifacts: Path) -> dict[str, Any]:
    import yaml

    rs = _load("run_scenarios", SCRIPTS / "run_scenarios.py")
    out = artifacts / "scenarios"
    args = argparse.Namespace(out=str(out), scenarios=str(rs.DEFAULT_SCENARIOS), only=None, screenshots=None,
                              base_url=None, verbose=False)
    buf = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        code = rs.run(args)
    seconds = time.perf_counter() - t0
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    spec = {s["id"]: s for s in yaml.safe_load(Path(rs.DEFAULT_SCENARIOS).read_text(encoding="utf-8"))["scenarios"]}
    tasks = []
    for r in results["scenarios"]:
        scn = spec[r["id"]]
        prompts, expected, actual = [], [], []
        for t, turn in zip(r["turns"], scn["turns"]):
            who = "" if t["actor"] == "OWNER" else f"[{t['actor'].lower()}] "
            prompts.append(f"{t['n']}. {who}{_cell(t['text'], 150)}")
            expected.append(f"{t['n']}. {_cell(_expect_text(turn.get('expect', {})), 200)}")
            bits = [f"intent={t['intent']}"]
            if t["outcome"]:
                bits.append(f"outcome={t['outcome']}")
            if t["operations"]:
                bits.append("ops=" + ",".join(t["operations"]))
            bits.append("reply: " + _cell(t["reply"], 90))
            actual.append(f"{t['n']}. " + "; ".join(bits) + ("" if t["passed"] else " FAILED: " + "; ".join(t["failures"])))
        if scn.get("after"):
            expected.append("after: " + _cell(", ".join(f"{k}={v}" for k, v in scn["after"].items()), 160))
        intents = [t["intent"] for t in r["turns"] if t["intent"] and t["intent"] != "AMBIGUOUS"] or ["AMBIGUOUS"]
        tasks.append({"id": r["id"], "title": r.get("title"), "tags": r.get("tags", []), "area": intents[0],
                      "prompt": prompts, "expected": expected, "actual": actual, "passed": r["status"] == "PASSED",
                      "status": r["status"], "failures": r["failures"], "turns": len(r["turns"])})
    return {"tasks": tasks, "summary": results["summary"], "seconds": round(seconds, 1), "exit": code,
            "artifacts": str(out)}


# ---------------------------------------------------------------------------------------------- (b) adversarial


def _attack_prompt(attack: dict) -> str:
    for step in attack.get("steps", []):
        for kind, arg in step.items():
            if isinstance(arg, dict) and arg.get("text"):
                who = arg.get("sender") or arg.get("as") or kind
                return f"[{who}] {arg['text']}"
            if kind == "op" and isinstance(arg, dict):
                return f"[API] operation {arg.get('kind')} with {_cell(json.dumps({k: v for k, v in arg.items() if k != 'kind'}, ensure_ascii=False), 90)}"
            if kind in ("tamper", "mandate", "clock", "get", "raw", "approve", "accept", "replace_offer", "llm", "db_fail"):
                return f"[API] {kind}: {_cell(json.dumps(arg, ensure_ascii=False), 110)}"
    return attack.get("vector", "")


def run_adversarial() -> dict[str, Any]:
    import logging

    import structlog

    from app.security import attacks as atk

    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    api_cat, nl_cat = atk.load_catalogue(), atk.nl_catalogue()
    t0 = time.perf_counter()
    api_obs = atk.AttackRunner(api_cat).run_all()
    nl_obs = atk.NlAttackRunner(nl_cat).run_all()
    seconds = time.perf_counter() - t0
    by_id = {a["id"]: a for a in [*api_cat, *atk._with_channels(nl_cat)]}
    labels = {**atk.CATEGORIES, **atk.NL_CATEGORIES}
    cls_of = {c: k for k, cs in ATTACK_CLASSES.items() for c in cs}
    rows = []
    for o in [*api_obs, *nl_obs]:
        a = by_id.get(o.id) or {}
        codes = sorted(o.observed_codes)
        rows.append({
            "id": o.id, "category": o.category, "category_label": labels.get(o.category, o.category),
            "class": cls_of.get(o.category, "Other"), "entry_point": o.entry_point, "lang": o.lang,
            "title": o.title, "prompt": _attack_prompt(a),
            "expected": "no harm; stopped by: " + ", ".join(str(c) for c in o.expected_controls),
            "actual": f"{o.outcome()}" + (f"; codes: {', '.join(codes)}" if codes else "")
                      + (f"; {o.pending_approvals} queued for the owner" if o.pending_approvals else "")
                      + ("; HARM: " + "; ".join(o.harm_reasons) if o.harm else ""),
            "outcome": o.outcome(), "harm": o.harm, "known_finding": o.known_finding, "detected": o.detected,
            "security_event": o.security_event_logged, "contained": o.outcome() == "CONTAINED",
            "passed": not o.harm,
        })
    api_metrics = atk.metrics(api_obs)
    return {"rows": rows, "api_metrics": api_metrics, "seconds": round(seconds, 1), "api_attacks": len(api_obs),
            "nl_attacks": len(nl_obs)}


# ---------------------------------------------------------------------------------------------- (c) + (d) walk and chain


def run_walk(artifacts: Path) -> dict[str, Any]:
    demo = _load("demo_run", SCRIPTS / "demo_run.py")
    verify = _load("verify_evidence", SCRIPTS / "verify_evidence.py")
    from app.api.evidence import build
    from app.api.runtime import get_runtime

    buf = io.StringIO()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        code = demo.main()
    seconds = time.perf_counter() - t0
    transcript = buf.getvalue()
    lines = transcript.splitlines()
    result_lines = [x for x in lines if x.startswith(("RESULT:", "STEPS 14-17:", "cure:"))]
    rt = get_runtime()
    evidence = build(rt)
    out = artifacts / "demo-walk"
    out.mkdir(parents=True, exist_ok=True)
    good = out / "evidence.jsonl"
    good.write_text(evidence, encoding="utf-8")

    def check(path: Path) -> tuple[int, str]:
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            rc = verify.main(str(path))
        return rc, b.getvalue().strip()

    rc_ok, msg_ok = check(good)
    # a tampered copy: change one recorded result inside the file, leave every hash as it was
    tampered_lines, changed = [], False
    for raw in evidence.splitlines():
        rec = json.loads(raw)
        if not changed and rec.get("record") == "operation" and rec.get("status") == "EXECUTED":
            rec["result_json"] = rec["result_json"].replace("EXECUTED", "EXECUTEX", 1) if "EXECUTED" in rec["result_json"] \
                else rec["result_json"] + " "
            changed = True
        tampered_lines.append(json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    bad = out / "evidence-tampered.jsonl"
    bad.write_text("\n".join(tampered_lines) + "\n", encoding="utf-8")
    rc_bad, msg_bad = check(bad)
    ops = sum(1 for raw in evidence.splitlines() if json.loads(raw).get("record") == "operation")
    return {"exit": code, "ok": code == 0, "seconds": round(seconds, 1), "result_lines": result_lines,
            "transcript": transcript, "chain_valid": rc_ok == 0 and rt.store.verify_chain(), "chain_message": msg_ok,
            "store_verify_chain": rt.store.verify_chain(), "operations": ops, "tamper_rejected": rc_bad != 0 and changed,
            "tamper_message": " ".join(x.strip() for x in msg_bad.splitlines()), "evidence_file": str(good), "tampered_file": str(bad)}


# ---------------------------------------------------------------------------------------------- report


def _table(head: list[str], rows: list[list[Any]]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |",
            *("| " + " | ".join(str(c) for c in r) + " |" for r in rows)]


def build_report(fn: dict, adv: dict, walk: dict, total_seconds: float) -> tuple[str, dict]:
    tasks, rows = fn["tasks"], adv["rows"]
    n_pass = sum(t["passed"] for t in tasks)
    harmed = [r for r in rows if r["harm"]]
    n_att = len(rows)
    detected = sum(r["detected"] for r in rows)
    api_det = adv["api_metrics"]["detection_rate"]
    det_all = _pct(detected, n_att)
    ok = (n_pass == len(tasks) and not harmed and walk["ok"] and walk["chain_valid"] and walk["tamper_rejected"])
    headline = (f"{n_pass} functional tasks passed of {len(tasks)}; {n_att} adversarial attacks, {len(harmed)} caused harm, "
                f"detection {api_det * 100:.2f}% on the {adv['api_attacks']} API attacks ({det_all} across all {n_att}); demo walk {'OK' if walk['ok'] else 'FAILED'}; audit chain "
                f"{'VALID' if walk['chain_valid'] else 'INVALID'}")
    L: list[str] = ["# FLOW judge report", "", f"**{headline}**", "",
                    ("FinTechathon 2026, International AI Track, Topic E (SME Finance Copilot). Produced by "
                     "`scripts/judge_eval.py`: offline, deterministic, free (recorded model readings, in-memory books, "
                     "no network, no keys). Outcomes are the same on every run; the hashes in the walk's log and the timings differ, because the "
                     "log records generated ids and times."), ""]
    L += ["## At a glance", ""]
    L += _table(["Check", "Result"], [
        ["Functional tasks (scripted conversations)", f"{n_pass} of {len(tasks)} passed, {sum(t['turns'] for t in tasks)} turns"],
        ["Adversarial attacks", f"{n_att} run ({adv['api_attacks']} through the API, {adv['nl_attacks']} through the chat); "
                                f"{len(harmed)} caused harm"],
        ["Detection", f"{api_det * 100:.2f}% of the {adv['api_attacks']} API attacks, {det_all} of all {n_att}, raised a "
                      f"security event or a refusal code. The rest are chat requests the agent answered or ignored with "
                      f"no event logged (mostly an owner's own negated or conditional instruction); they changed nothing"],
        ["Contained, not refused", f"{sum(r['contained'] for r in rows)} attacks queued for the owner and changed nothing"],
        ["Demo walk (17 steps)", "OK" if walk["ok"] else "FAILED"],
        ["Audit chain of the walk's log", f"{walk['chain_message']}"],
        ["Tampered copy (one recorded result altered)",
         "rejected: " + _cell(walk["tamper_message"], 150) if walk["tamper_rejected"] else "NOT REJECTED"],
        ["Run time", f"{total_seconds:.0f} s (scenarios {fn['seconds']} s, attacks {adv['seconds']} s, walk {walk['seconds']} s)"],
    ])
    L += ["", "## Functional tasks by area", "",
          "The area is the intent the agent recognised on the task's first substantive turn.", ""]
    areas: dict[str, list[dict]] = {}
    for t in tasks:
        areas.setdefault(t["area"], []).append(t)
    L += _table(["Area (intent)", "Tasks", "Passed", "Chinese input", "Tasks"],
                [[a, len(ts), sum(x["passed"] for x in ts), sum("zh" in x["tags"] for x in ts),
                  ", ".join(x["id"].split("_")[0] for x in ts)] for a, ts in sorted(areas.items())])
    L += ["", "## Adversarial attacks by class", ""]
    classes = list(ATTACK_CLASSES) + sorted({r["class"] for r in rows} - set(ATTACK_CLASSES))
    crow = []
    for c in classes:
        g = [r for r in rows if r["class"] == c]
        if g:
            crow.append([c, len(g), sum(r["harm"] for r in g), sum(r["detected"] for r in g),
                         sum(r["security_event"] for r in g), sum(r["contained"] for r in g), _pct(sum(r["detected"] for r in g), len(g))])
    crow.append(["**All**", n_att, len(harmed), detected, sum(r["security_event"] for r in rows),
                 sum(r["contained"] for r in rows), det_all])
    L += _table(["Attack class", "Attacks", "Caused harm", "Detected", "Security event logged", "Contained", "Detection"], crow)
    L += ["", ("Detection counts attacks that raised a security event or a refusal code. \"Owner consent\" attacks are an owner's or "
               "agent's own negated, conditional, question-form or malformed instruction (\"do not draw ¥100,000\", \"should I approve "
               "APR-000001?\"): the right behaviour is to do nothing, so there is little to detect; the test is that nothing runs."),
          "", "### By category", ""]
    cats: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    L += _table(["Category", "Class", "Attacks", "Caused harm", "Detected", "Entry point"],
                [[g[0]["category_label"], g[0]["class"].split(" (")[0], len(g), sum(x["harm"] for x in g),
                  sum(x["detected"] for x in g), ", ".join(sorted({x["entry_point"] for x in g}))] for g in cats.values()])
    L += ["", "Entry points: `api` is the lower-level API (operations, offers, approvals); `nl:*` is the chat as the owner, "
          "as a buyer (with and without the buyer's own key) and with the agent's key.", ""]
    L += ["## Demo walk", ""]
    L += [f"- {x}" for x in walk["result_lines"]] or ["- (no result lines)"]
    L += ["", f"The walk's log has {walk['operations']} operations. `scripts/verify_evidence.py` recomputed every hash: "
          f"`{walk['chain_message']}`. A copy with one recorded result altered: `{_cell(walk['tamper_message'], 160)}`.", ""]
    L += ["## Every functional task", ""]
    L += _table(["Id", "Prompt (turns)", "Expected", "Actual", "Result"],
                [[t["id"], "<br>".join(t["prompt"]), "<br>".join(t["expected"]), "<br>".join(t["actual"]),
                  "PASS" if t["passed"] else "**FAIL**"] for t in tasks])
    L += ["", "## Every adversarial attack", ""]
    L += _table(["Id", "Class", "Prompt / action", "Expected", "Actual", "Result"],
                [[r["id"], r["class"].split(" (")[0].split(" and ")[0], _cell(r["prompt"], 150), _cell(r["expected"], 130),
                  _cell(r["actual"], 170), "PASS" if r["passed"] else "**FAIL**"] for r in rows])
    L += ["", "## Reproduce", "",
          "```", "uv run --project services/api python scripts/judge_eval.py", "```", "",
          ("Each part also runs alone: `scripts/run_scenarios.py --inproc`, `uv run python -m app.security.attacks`, "
           "`scripts/demo_run.py`, `scripts/verify_evidence.py <file.jsonl>`. A PASS on an attack means no harm: nothing "
           "executed without authority, no money or facility moved, no protected value left in any text a buyer sees, "
           "and the log stayed intact. Detection counts attacks that raised a security event or a refusal code."), ""]
    data = {"headline": headline, "ok": ok, "functional": {"passed": n_pass, "total": len(tasks), "tasks": tasks,
                                                           "summary": {k: v for k, v in fn["summary"].items() if "latency" not in k}},
            "adversarial": {"total": n_att, "api": adv["api_attacks"], "nl": adv["nl_attacks"], "harm": len(harmed),
                            "detected": detected, "detection_rate_all": round(detected / n_att, 4) if n_att else 0.0,
                            "api_detection_rate": api_det, "attacks": rows},
            "demo_walk": {k: v for k, v in walk.items() if k not in ("transcript", "evidence_file", "tampered_file")}
            | {"transcript_lines": len(walk["transcript"].splitlines())},
            "seconds": round(total_seconds, 1)}
    return "\n".join(L) + "\n", data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="the Markdown report; a .json is written next to it")
    ap.add_argument("--artifacts", help="keep the per-turn transcripts and evidence files here (default: a temporary directory)")
    args = ap.parse_args()
    _bootstrap()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = None if args.artifacts else tempfile.TemporaryDirectory(prefix="judge-eval-")
    artifacts = Path(args.artifacts).resolve() if args.artifacts else Path(tmp.name)  # type: ignore[union-attr]
    artifacts.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    try:
        print("(a) functional scenarios ...", flush=True)
        fn = run_functional(artifacts)
        print(f"    {sum(t['passed'] for t in fn['tasks'])}/{len(fn['tasks'])} passed in {fn['seconds']} s", flush=True)
        print("(b) adversarial attack catalogue ...", flush=True)
        adv = run_adversarial()
        print(f"    {len(adv['rows'])} attacks, {sum(r['harm'] for r in adv['rows'])} with harm, in {adv['seconds']} s", flush=True)
        print("(c) demo walk and (d) audit chain ...", flush=True)
        walk = run_walk(artifacts)
        print(f"    walk {'OK' if walk['ok'] else 'FAILED'}, chain {'VALID' if walk['chain_valid'] else 'INVALID'}, "
              f"tampered copy {'rejected' if walk['tamper_rejected'] else 'NOT rejected'}, {walk['seconds']} s", flush=True)
        md, data = build_report(fn, adv, walk, time.perf_counter() - t0)
        out.write_text(md, encoding="utf-8")
        out.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    finally:
        if tmp is not None:
            tmp.cleanup()
    print(f"\n{data['headline']}\nreport: {out}\njson:   {out.with_suffix('.json')}\ntotal {data['seconds']} s")
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
