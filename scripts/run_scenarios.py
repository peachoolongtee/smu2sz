#!/usr/bin/env python3
"""Run the scripted /nl tasks and write judge-facing evidence.

Usage (from the repo root):
  python3 scripts/run_scenarios.py --inproc [--out services/api/evals/e2e/latest] [--screenshots DIR]
  python3 scripts/run_scenarios.py --base-url http://localhost:8000 [--out ...]
  python3 scripts/run_scenarios.py --inproc --only S01_scene1_counter_accept,S17_ex12_goal_accept

Each task starts from POST /demo/reset and fresh /nl sessions, runs its turns, and checks the expected
intent, verdict outcome and codes, and operation kinds/statuses. A COUNTERPARTY response carries only the
reply (the verdict, plan and operations are withheld from the sender), so in `--inproc` mode a counterparty
turn's `store_*` expectations are checked against what the runtime's store holds for that turn: the verdict
outcome and codes, the operations logged and the security events raised. It writes:
  results.json          pass/fail and latency per task and per turn
  evidence.jsonl        per-task segments (task header + app.api.evidence.build output)
  evidence/<task>.jsonl the same segment alone; `python scripts/verify_evidence.py <file>` verifies it
  transcripts/<task>/turn-<n>.html   a readable card per turn (linked from each operation line)
  summary.md            the table judges read first
Exits 1 if any task fails. `--inproc` needs the API's dependencies; if they are missing it re-runs
itself with `uv run --project services/api`.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"
DEFAULT_SCENARIOS = API / "evals" / "e2e" / "scenarios.yaml"
DEFAULT_OUT = API / "evals" / "e2e" / "latest"
AGENT_KEY = os.environ.get("AGENT_KEY", "demo-agent-key")
OWNER_TOKEN = os.environ.get("OWNER_TOKEN", "demo-owner-token")
# A registered buyer's own channel key (the server maps key -> counterparty id). Buyer turns send it by default; a
# scenario turn with `buyer_key: false` models an unauthenticated sender (proposal only).
BUYER_KEYS = {"BUYER-1": os.environ.get("BUYER_1_KEY", "demo-buyer-1-key"),
              "BUYER-2": os.environ.get("BUYER_2_KEY", "demo-buyer-2-key")}


def _nl_headers(body: dict, owner: bool) -> dict:
    """Headers for one /nl turn. Pops the scenario-only `_buyer_key` marker so it is never sent as a body field."""
    send_key = body.pop("_buyer_key", True)
    if owner:
        return {"X-Owner-Token": OWNER_TOKEN}
    headers = {"X-Agent-Key": AGENT_KEY}
    key = BUYER_KEYS.get(body.get("counterparty_id") or "") if body.get("actor") == "COUNTERPARTY" else None
    if key and send_key:
        headers["X-Counterparty-Key"] = key
    return headers


def _bootstrap() -> None:
    """Import the API; if its dependencies are missing, re-exec under the API's uv project."""
    sys.path.insert(0, str(API))
    os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")
    try:
        import fastapi  # noqa: F401
        import yaml  # noqa: F401
    except ImportError:
        if os.environ.get("TL_RUNNER_REEXEC") or not shutil.which("uv"):
            raise
        env = {**os.environ, "TL_RUNNER_REEXEC": "1"}
        cmd = ["uv", "run", "--project", str(API), "python", str(Path(__file__).resolve()), *sys.argv[1:]]
        sys.exit(subprocess.run(cmd, env=env, check=False).returncode)


# ---------------------------------------------------------------- transports


class InProc:
    """FastAPI TestClient over an in-memory runtime (no network, cache-mode compiler)."""

    name = "inproc"

    def __init__(self) -> None:
        import logging

        import structlog
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.nl import router as nl_router
        from app.api.runtime import Runtime, set_runtime
        from app.config import get_settings
        from app.main import app as main_app
        from app.mandate.fixture import demo_owner_public_key_hex
        from app.persistence import InMemoryLedgerStore

        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
        self.rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
        self.rt.reset()
        set_runtime(self.rt)
        app = main_app
        if not any(getattr(r, "path", None) == "/nl" for r in main_app.routes):
            app = FastAPI()
            app.include_router(main_app.router)
            app.include_router(nl_router)
        self.client = TestClient(app)

    def reset(self, setup: dict | None) -> None:
        from app.domain.models import CashFlow
        from app.nl import reset_sessions

        self.rt.reset()
        reset_sessions()
        if setup:
            st = self.rt.store.get_state()
            update: dict[str, Any] = {}
            if "cash_fen" in setup:
                update["cash_fen"] = int(setup["cash_fen"])
            if setup.get("add_flows"):
                update["flows"] = [*st.flows, *(CashFlow.model_validate_json(json.dumps(f)) for f in setup["add_flows"])]
            self.rt.store.put_state(st.model_copy(update=update))
            for op in setup.get("operations", []):  # e.g. queue a Tier-2 item before the conversation
                self.client.post("/operations", json=op, headers={"X-Owner-Token": OWNER_TOKEN})

    def post(self, path: str, body: dict, owner: bool) -> tuple[int, dict]:
        headers = _nl_headers(body, owner)
        r = self.client.post(path, json=body, headers=headers)
        return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})

    def snapshot(self) -> tuple[int, int, int]:
        """(operations, security events, verdicts) the store holds now."""
        s = self.rt.store
        return len(s.operations()), len(s.security_events()), len(s.verdicts())

    def store_view(self, session_id: str | None, before: tuple[int, int, int]) -> dict[str, Any]:
        """What the store holds for the turn that just ran: the verdict behind it, the operations it logged and
        the security events it raised. The response of a COUNTERPARTY turn withholds all three."""
        from app.nl.sessions import SESSIONS

        s = self.rt.store
        ops0, events0, verdicts0 = before
        new = s.verdicts()[verdicts0:]
        session = SESSIONS.get(session_id) if session_id else None
        verdict = next((v for v in new if session and v.id == session.last_verdict_id), new[-1] if new else None)
        return {
            "outcome": verdict.outcome.value if verdict else None,
            "codes": list(dict.fromkeys(x.code.value for x in verdict.violations)) if verdict else [],
            "ops": [f"{r.kind}:{json.loads(r.result_json)['status']}" for r in s.operations()[ops0:]],
            "security_events": len(s.security_events()) - events0,
        }

    def get(self, path: str) -> Any:
        r = self.client.get(path, headers={"X-Owner-Token": OWNER_TOKEN})
        return r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text

    def evidence(self, screenshots: dict[str, str]) -> str:
        from app.api.evidence import build

        return build(self.rt, screenshots=screenshots)


class Http:
    name = "http"

    def __init__(self, base_url: str) -> None:
        import httpx

        self.base = base_url.rstrip("/")
        self.client = httpx.Client(timeout=60.0)

    def reset(self, setup: dict | None) -> None:
        self.client.post(f"{self.base}/demo/reset", headers={"X-Owner-Token": OWNER_TOKEN}).raise_for_status()
        self.client.post(f"{self.base}/nl/reset", headers={"X-Owner-Token": OWNER_TOKEN})

    def post(self, path: str, body: dict, owner: bool) -> tuple[int, dict]:
        headers = _nl_headers(body, owner)
        r = self.client.post(f"{self.base}{path}", json=body, headers=headers)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {}

    def snapshot(self) -> None:
        return None  # the store is not reachable over HTTP

    def store_view(self, session_id: str | None, before: Any) -> None:
        return None

    def get(self, path: str) -> Any:
        r = self.client.get(f"{self.base}{path}", headers={"X-Owner-Token": OWNER_TOKEN})
        try:
            return r.json()
        except ValueError:
            return r.text

    def evidence(self, screenshots: dict[str, str]) -> str:
        lines = []
        for raw in self.client.get(f"{self.base}/evidence", headers={"X-Owner-Token": OWNER_TOKEN}).text.splitlines():
            if not raw.strip():
                continue
            rec = json.loads(raw)
            if rec.get("record") == "operation" and rec.get("op_id") in screenshots:
                rec["screenshot"] = screenshots[rec["op_id"]]  # outside the hash (ADR-0004)
            lines.append(json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- checks


def _codes(resp: dict) -> list[str]:
    v = resp.get("verdict") or {}
    return list(dict.fromkeys(x.get("code") for x in v.get("violations", [])))


def check_store(store: dict, exp: dict) -> list[str]:
    """Expectations on what the store holds for a COUNTERPARTY turn (`store_*` keys; see InProc.store_view)."""
    f: list[str] = []
    if "store_outcome" in exp and store["outcome"] != exp["store_outcome"]:
        f.append(f"stored outcome {store['outcome']} != {exp['store_outcome']}")
    if "store_codes" in exp and not set(exp["store_codes"]) <= set(store["codes"]):
        f.append(f"stored codes {store['codes']} missing {sorted(set(exp['store_codes']) - set(store['codes']))}")
    if "store_codes_exact" in exp and store["codes"] != exp["store_codes_exact"]:
        f.append(f"stored codes {store['codes']} != {exp['store_codes_exact']}")
    if "store_ops" in exp and store["ops"] != exp["store_ops"]:
        f.append(f"stored ops {store['ops']} != {exp['store_ops']}")
    if "store_none_executed" in exp:
        executed = any(o.endswith(":EXECUTED") for o in store["ops"])
        if exp["store_none_executed"] and executed:
            f.append(f"expected nothing executed in the store: {store['ops']}")
        if not exp["store_none_executed"] and not executed:
            f.append("expected at least one executed operation in the store")
    if "store_security_events_min" in exp and store["security_events"] < exp["store_security_events_min"]:
        f.append(f"{store['security_events']} stored security events < {exp['store_security_events_min']}")
    return f


def check_turn(resp: dict, exp: dict, store: dict | None = None) -> list[str]:
    f: list[str] = []
    if store is not None:
        f += check_store(store, exp)
    ops = [f"{o['kind']}:{o['status']}" for o in resp.get("operations", [])]
    reply = (resp.get("reply") or "").lower()
    outcome = (resp.get("verdict") or {}).get("outcome")
    if "intent" in exp and resp.get("intent") != exp["intent"]:
        f.append(f"intent {resp.get('intent')} != {exp['intent']}")
    if "outcome" in exp and outcome != exp["outcome"]:
        f.append(f"outcome {outcome} != {exp['outcome']}")
    if "codes" in exp and not set(exp["codes"]) <= set(_codes(resp)):
        f.append(f"codes {_codes(resp)} missing {sorted(set(exp['codes']) - set(_codes(resp)))}")
    if "codes_exact" in exp and _codes(resp) != exp["codes_exact"]:
        f.append(f"codes {_codes(resp)} != {exp['codes_exact']}")
    if "ops" in exp and ops != exp["ops"]:
        f.append(f"ops {ops} != {exp['ops']}")
    if "ops_count" in exp and len(ops) != exp["ops_count"]:
        f.append(f"{len(ops)} operations, expected {exp['ops_count']}: {ops}")
    if "none_executed" in exp:
        executed = any(o.endswith(":EXECUTED") for o in ops)
        if exp["none_executed"] and executed:
            f.append(f"expected nothing executed: {ops}")
        if not exp["none_executed"] and not executed:
            f.append("expected at least one executed operation")
    for key, field in (("clarification", "clarification"), ("awaiting", "awaiting_confirmation"),
                       ("amended", "amended"), ("replayed", "replayed")):
        if key in exp and bool(resp.get(field)) != bool(exp[key]):
            f.append(f"{key} {bool(resp.get(field))} != {exp[key]}")
    if "negotiation" in exp and (resp.get("negotiation") or {}).get("outcome") != exp["negotiation"]:
        f.append(f"negotiation {(resp.get('negotiation') or {}).get('outcome')} != {exp['negotiation']}")
    if "plan_kinds" in exp:
        kinds = {s["kind"] for s in resp.get("plan", [])}
        missing = [k for k in exp["plan_kinds"] if k not in kinds]
        if missing:
            f.append(f"plan lacks {missing}")
    for s in exp.get("reply_contains", []):
        if s.lower() not in reply:
            f.append(f"reply lacks {s!r}")
    for s in exp.get("reply_excludes", []):
        if s.lower() in reply:
            f.append(f"reply contains forbidden {s!r}")
    if "security_events_min" in exp and len(resp.get("security_events", [])) < exp["security_events_min"]:
        f.append(f"{len(resp.get('security_events', []))} security events < {exp['security_events_min']}")
    return f


def check_after(t: Any, after: dict, cash_before: int) -> list[str]:
    f: list[str] = []
    state = t.get("/state")
    cash = state["state"]["cash_fen"]
    summary = t.get("/security/summary")
    ledger = t.get("/ledger")
    if after.get("cash_unchanged") and cash != cash_before:
        f.append(f"cash moved: {cash_before} -> {cash}")
    if "cash_fen" in after and cash != after["cash_fen"]:
        f.append(f"cash {cash} != {after['cash_fen']}")
    if "facilities_added" in after and summary.get("facilities_added_by_non_owner") != after["facilities_added"]:
        f.append(f"facilities added by non-owner: {summary.get('facilities_added_by_non_owner')}")
    if "unauthorised_executions" in after and summary.get("unauthorised_executions") != after["unauthorised_executions"]:
        f.append(f"unauthorised executions: {summary.get('unauthorised_executions')}")
    if after.get("chain_valid") and not ledger.get("chain_valid"):
        f.append("hash chain invalid")
    return f


# ---------------------------------------------------------------- transcripts


def card(scn: dict, n: int, turn: dict, resp: dict, ok: bool, store: dict | None = None) -> str:
    esc = html.escape
    ops = "".join(f"<tr><td>{esc(o['kind'])}</td><td>{esc(o['status'])}</td><td>{esc(o.get('tier', ''))}</td>"
                  f"<td>{esc(o.get('message', ''))}</td></tr>" for o in resp.get("operations", []))
    plan = "".join(f"<li>[{esc(s['status'])}] {esc(s['kind'])}: {esc(s['description'])}"
                   f"{' (' + esc(s['condition']) + ')' if s.get('condition') else ''}</li>" for s in resp.get("plan", []))
    v = resp.get("verdict") or {}
    stored = (f"<p><b>Stored (withheld from the sender)</b> verdict {esc(str(store['outcome']))} "
              f"{esc(', '.join(store['codes']))} · operations {esc(', '.join(store['ops']) or 'none')} · "
              f"security events {store['security_events']}</p>") if store else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(scn['id'])} turn {n}</title><style>body{{font:14px/1.5 system-ui,sans-serif;margin:24px;max-width:960px;color:#1d2330;background:#fff}}
.tag{{display:inline-block;padding:2px 8px;border-radius:10px;background:{'#e3f5e8' if ok else '#fde8e8'}}}
pre{{white-space:pre-wrap;background:#f5f6f8;padding:12px;border-radius:6px}}table{{border-collapse:collapse;width:100%}}
td{{border-top:1px solid #e3e5e8;padding:4px 6px;vertical-align:top}}</style></head><body>
<h1>{esc(scn['id'])} · turn {n} <span class="tag">{'PASS' if ok else 'FAIL'}</span></h1><p>{esc(scn.get('title', ''))}</p>
<p><b>{esc(turn.get('actor', 'OWNER'))}</b>{' (' + esc(turn['counterparty_id']) + ')' if turn.get('counterparty_id') else ''}:</p>
<pre>{esc(turn['text'])}</pre><p><b>Intent</b> {esc(str(resp.get('intent')))} · <b>Verdict</b> {esc(str(v.get('outcome', '—')))}
{esc(', '.join(_codes(resp)))}</p><p><b>Reply</b></p><pre>{esc(resp.get('reply', ''))}</pre>{stored}<p><b>Plan</b></p><ol>{plan}</ol>
<p><b>Operations</b></p><table>{ops or '<tr><td>none</td></tr>'}</table>
<p>session {esc(str(resp.get('session_id')))} · trace {esc(str(resp.get('trace_id')))} · security events {len(resp.get('security_events', []))}</p>
</body></html>"""


# ---------------------------------------------------------------- run


def run(args: argparse.Namespace) -> int:
    import yaml

    out = Path(args.out).resolve()
    shots = Path(args.screenshots).resolve() if args.screenshots else out / "transcripts"
    for d in (out, out / "evidence", shots):
        d.mkdir(parents=True, exist_ok=True)
    scenarios = yaml.safe_load(Path(args.scenarios).read_text(encoding="utf-8"))["scenarios"]
    if args.only:
        wanted = set(args.only.split(","))
        scenarios = [s for s in scenarios if s["id"] in wanted]
    transport: Any = Http(args.base_url) if args.base_url else InProc()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results, segments = [], []
    for scn in scenarios:
        if scn.get("setup") and transport.name != "inproc":
            results.append({"id": scn["id"], "title": scn.get("title"), "status": "SKIPPED",
                            "reason": "setup needs --inproc", "turns": []})
            continue
        transport.reset(scn.get("setup"))
        cash_before = transport.get("/state")["state"]["cash_fen"]
        turns_out, failures, op_links, t0 = [], [], {}, time.perf_counter()
        for n, turn in enumerate(scn["turns"], 1):
            actor = turn.get("actor", "OWNER")
            body = {"session_id": turn.get("session") or f"{scn['id']}-{actor.lower()}"[:64], "actor": actor,
                    "text": turn["text"]}
            for k in ("counterparty_id", "request_id", "lang"):
                if turn.get(k):
                    body[k] = turn[k]
            if turn.get("buyer_key") is False:
                body["_buyer_key"] = False
            if turn.get("buyer_profile") or scn.get("buyer_profile"):
                body["buyer_profile"] = turn.get("buyer_profile") or scn["buyer_profile"]
            owner = actor == "OWNER" and turn.get("owner_token", True)
            before = transport.snapshot()
            s0 = time.perf_counter()
            code, resp = transport.post("/nl", body, owner)
            latency = round((time.perf_counter() - s0) * 1000, 1)
            store = transport.store_view(resp.get("session_id"), before) if actor == "COUNTERPARTY" and code == 200 \
                and before is not None else None
            fails = [f"HTTP {code}"] if code != 200 else check_turn(resp, turn.get("expect", {}), store)
            link = f"{shots.relative_to(out) if shots.is_relative_to(out) else shots}/{scn['id']}/turn-{n}.html"
            (shots / scn["id"]).mkdir(parents=True, exist_ok=True)
            (shots / scn["id"] / f"turn-{n}.html").write_text(card(scn, n, turn, resp, not fails, store), encoding="utf-8")
            for o in resp.get("operations", []):
                op_links.setdefault(o["op_id"], link)
            failures += [f"turn {n}: {x}" for x in fails]
            turns_out.append({"n": n, "actor": actor, "text": turn["text"], "intent": resp.get("intent"),
                              "outcome": (resp.get("verdict") or {}).get("outcome") or (store or {}).get("outcome"),
                              "codes": _codes(resp) or (store or {}).get("codes", []), "store": store,
                              "operations": [f"{o['kind']}:{o['status']}" for o in resp.get("operations", [])],
                              "reply": resp.get("reply"), "latency_ms": latency, "passed": not fails,
                              "failures": fails, "transcript": link})
        failures += [f"after: {x}" for x in check_after(transport, scn.get("after", {}), cash_before)]
        status = "PASSED" if not failures else "FAILED"
        results.append({"id": scn["id"], "title": scn.get("title"), "tags": scn.get("tags", []), "status": status,
                        "failures": failures, "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                        "turns": turns_out})
        task = {"record": "task", "task": scn["id"], "title": scn.get("title"), "status": status,
                "turns": [{"n": x["n"], "actor": x["actor"], "request": x["text"], "intent": x["intent"],
                           "outcome": x["outcome"], "operations": x["operations"], "transcript": x["transcript"]}
                          for x in turns_out]}
        seg = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" + \
            transport.evidence(op_links)
        (out / "evidence" / f"{scn['id']}.jsonl").write_text(seg, encoding="utf-8")
        segments.append(seg)
        if args.verbose or failures:
            print(f"{status:7} {scn['id']}" + "".join(f"\n        - {x}" for x in failures))
    (out / "evidence.jsonl").write_text("".join(segments), encoding="utf-8")
    ran = [r for r in results if r["status"] != "SKIPPED"]
    passed = sum(r["status"] == "PASSED" for r in ran)
    summary = {"total": len(results), "ran": len(ran), "passed": passed, "failed": len(ran) - passed,
               "skipped": len(results) - len(ran), "pass_rate": round(passed / len(ran), 4) if ran else 0.0,
               "turns": sum(len(r["turns"]) for r in ran),
               "median_turn_latency_ms": _median([t["latency_ms"] for r in ran for t in r["turns"]])}
    (out / "results.json").write_text(json.dumps({"run": {"started_at": started, "transport": transport.name,
                                                          "scenarios_file": str(Path(args.scenarios)),
                                                          "llm_mode": os.environ.get("LLM_MODE", "cache")},
                                                  "summary": summary, "scenarios": results},
                                                 ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.md").write_text(_summary_md(results, summary, started, transport.name), encoding="utf-8")
    print(f"{passed}/{len(ran)} scenarios passed ({summary['skipped']} skipped), "
          f"{summary['turns']} turns, median {summary['median_turn_latency_ms']} ms/turn -> {out}")
    return 0 if passed == len(ran) else 1


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[len(s) // 2]


def _summary_md(results: list[dict], s: dict, started: str, transport: str) -> str:
    rows = []
    for r in results:
        intents = " → ".join(t["intent"] or "?" for t in r["turns"])
        ops = sum(len(t["operations"]) for t in r["turns"])
        executed = sum(o.endswith(":EXECUTED") for t in r["turns"] for o in t["operations"])
        rows.append(f"| {r['id']} | {r.get('title', '')} | {intents} | {ops} ({executed} executed) | "
                    f"{r['status']} | {r.get('latency_ms', '')} |")
    return "\n".join([
        "# /nl scripted tasks",
        "",
        (f"Run {started} ({transport}). **{s['passed']}/{s['ran']} passed** (pass rate {s['pass_rate']:.0%}), "
         f"{s['skipped']} skipped, {s['turns']} turns, median {s['median_turn_latency_ms']} ms per turn."),
        "",
        ("Each task starts from `POST /demo/reset`. Every operation below was built by code from a verifier "
         "verdict and sent to the executor; nothing a message says can skip either."),
        "",
        "| Task | What it shows | Intents | Operations | Result | ms |",
        "| --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        "## Verify the evidence",
        "",
        ("Each `evidence/<task>.jsonl` is one hash chain (a `task` line with the requests, then the `run` header, "
         "operations, security events and the chain line). Recompute every hash with the standard library:"),
        "",
        "```",
        "python scripts/verify_evidence.py services/api/evals/e2e/latest/evidence/S01_scene1_counter_accept.jsonl",
        "```",
        "",
        "Reproduce the whole run: `python3 scripts/run_scenarios.py --inproc`.",
        "",
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--base-url", help="run against a live API (e.g. http://localhost:8000)")
    g.add_argument("--inproc", action="store_true", help="in-process TestClient with an in-memory runtime (default)")
    ap.add_argument("--scenarios", default=str(DEFAULT_SCENARIOS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--screenshots", help="directory for the per-turn transcript cards (default <out>/transcripts)")
    ap.add_argument("--only", help="comma-separated task ids")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    _bootstrap()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
