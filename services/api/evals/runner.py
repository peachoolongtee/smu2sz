"""Run the evaluation suites and write latest_report.json / latest_report.md.

Entry point: scripts/evaluate.py (sets LLM_MODE before anything imports the app)."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from evals.common import EVALS, ROOT, InProcApi, SuiteResult, quiet, run_suite

ORDER = ["offers", "financial", "funding", "covenants", "security", "intent", "e2e", "no_deal"]
TITLES = {
    "offers": "1. Held-out offers (E2)",
    "financial": "2. Financial exactness (E3/E10)",
    "funding": "3. Funding router (E9)",
    "covenants": "4. Covenant and mandate boundaries",
    "security": "5. Security (E4/E7)",
    "intent": "6. /nl intent (held-out)",
    "e2e": "7. End to end (E7)",
    "no_deal": "8. Honest NO DEAL (E5)",
}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return ""


def run_all(suites: list[str], options: dict[str, dict[str, Any]]) -> dict[str, SuiteResult]:
    quiet()
    import importlib

    api: InProcApi | None = None
    out: dict[str, SuiteResult] = {}
    for name in [s for s in ORDER if s in suites]:
        mod = importlib.import_module(f"evals.suites.{name}")
        kw = dict(options.get(name, {}))
        if name in ("intent", "e2e", "no_deal"):
            api = api or InProcApi()
            kw["api"] = api
        print(f"[evaluate] {name} ...", flush=True)
        out[name] = run_suite(name, mod.run, **kw)
        r = out[name]
        state = "ERROR" if r.error else f"{sum(m.passed is False for m in r.metrics)} target(s) missed"
        print(f"[evaluate] {name} done in {r.seconds:.1f}s: {state}", flush=True)
    return out


def status(passed: bool | None) -> str:
    return "INFO" if passed is None else ("PASS" if passed else "FAIL")


def gate(results: dict[str, SuiteResult]) -> list[dict[str, Any]]:
    """Spec §14 rows this run can speak to, with the criterion and the evidence."""
    def m(suite: str, key: str) -> Any:
        r = results.get(suite)
        return next((x for x in r.metrics if x.key == key), None) if r else None

    rows = []

    def add(e: str, what: str, criterion: str, parts: list[Any], extra: str = "") -> None:
        parts = [p for p in parts if p is not None]
        if not parts:
            return
        ok = all(p.passed is not False for p in parts)
        rows.append({"gate": e, "what": what, "criterion": criterion,
                     "evidence": "; ".join(f"{p.label}: {p.display}" for p in parts) + extra,
                     "status": "PASS" if ok else "FAIL"})

    add("E2", "Compiler beats a form; engine differs from a cap",
        "0 silent material errors; engine ≠ cap on ≥ 7/20 (handling time not measured)",
        [m("offers", "silent_material_errors"), m("offers", "engine_vs_cap")])
    add("E3", "Engine correctness", "every golden case exact", [m("financial", "financial_exactness")])
    add("E4", "Language cannot create an unauthorised promise", "0 booked; every refusal has a reason",
        [m("security", "injection_success_rate"), m("security", "unauthorised_operations")],
        " (attack catalogue only; see EV-01/EV-02: benign held-out wording executes ACCEPT_OFFER on booked terms "
        "that differ from the buyer's text)")
    add("E5", "Honest no-deal", "bounded rounds; explicit NO DEAL; gap still funded", [m("no_deal", "e5_honest_no_deal")])
    add("E7", "Harness compatibility", "/nl → plan → verdict → operation log; injected requests refused",
        [m("e2e", "task_completion_rate"), m("security", "attacks_with_harm")])
    add("E9", "The router matters and stays honest",
        "router ≠ baseline with lower cost on ≥ 5/20; 0 plans on uncommitted facilities",
        [m("funding", "router_beats_line_first"), m("funding", "router_uncommitted_plans")],
        " (the separate ≥ 95% optimality target is in the summary)")
    add("E10", "Covenant and capex engine", "all exact; every breach reported with its month",
        [m("financial", "e10_covenant_capex_exactness"), m("covenants", "covenant_boundary_accuracy"),
         m("covenants", "covenant_breach_month_reported")])
    return rows


def to_json(results: dict[str, SuiteResult], meta: dict[str, Any]) -> dict[str, Any]:
    summary = []
    for name in ORDER:
        r = results.get(name)
        if r is None:
            continue
        for x in r.metrics:
            summary.append({"suite": name, "key": x.key, "label": x.label, "value": x.value, "display": x.display,
                            "target": x.target, "status": status(x.passed), "note": x.note})
        if r.error:
            summary.append({"suite": name, "key": f"{name}_error", "label": f"{name} suite", "value": None,
                            "display": "crashed", "target": "runs", "status": "FAIL", "note": r.error.splitlines()[0]})
    return {
        "meta": meta,
        "summary": summary,
        "gate": gate(results),
        "failures": [dataclasses.asdict(f) for n in ORDER if n in results for f in results[n].failures],
        "suites": {n: {"seconds": r.seconds, "error": r.error, "metrics": [dataclasses.asdict(x) for x in r.metrics],
                       "details": r.details} for n, r in results.items()},
    }


def _md_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    def cell(v: Any) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ")
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(cell(c) for c in row) + " |" for row in rows)]


def _rel(path: str | None, default: str) -> str:
    if not path:
        return default
    p = Path(path)
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def _yuan(fen: int | None) -> str:
    return "—" if fen is None else f"¥{fen / 100:,.2f}"


def load_findings() -> list[dict[str, Any]]:
    """Hand-written findings (evals/findings.yaml): judgement on top of the measured failures."""
    import yaml

    p = EVALS / "findings.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")).get("findings", []) if p.is_file() else []


def _findings_md(findings: list[dict[str, Any]]) -> list[str]:
    if not findings:
        return []
    L = ["## Findings", "", ("Weaknesses found by this run, with severity and a suggested owner module "
         "(`services/api/evals/findings.yaml`)."), ""]
    L += _md_table(["Id", "Severity", "Owner", "Finding"],
                   [[f["id"], f["severity"], f"`{f['owner']}`", f["title"]] for f in findings])
    L.append("")
    for f in findings:
        L += [f"### {f['id']}: {f['title']}", "", (f"Severity **{f['severity']}**, owner `{f['owner']}`, "
              f"suite `{f['suite']}`."), "", f["evidence"].strip(), "", f"Reproduce: `{f['repro']}`", ""]
        if f.get("suggestion"):
            L += [f"Suggested fix: {f['suggestion'].strip()}", ""]
    return L


def to_markdown(rep: dict[str, Any]) -> str:
    meta = rep["meta"]
    L: list[str] = ["# TermsLedger v2: evaluation report", ""]
    L.append(f"Run {meta['generated_at']} on `{meta['git_branch']}` @ `{meta['git_commit']}`, LLM_MODE=`{meta['llm_mode']}` "
             f"({'live backends' if meta['llm_mode'] == 'live' else 'offline: fixture cache, then the rules grammar'}), "
             f"{meta['seconds']:.0f} s. Reproduce: `{meta['command']}`.")
    L.append("")
    L.append("## Summary")
    L.append("")
    L += _md_table(["Metric", "Result", "Target", ""],
                   [[s["label"], s["display"] + (f" ({s['note']})" if s.get("note") else ""), s["target"],
                     {"PASS": "PASS", "FAIL": "**FAIL**", "INFO": "info"}[s["status"]]] for s in rep["summary"]])
    L.append("")
    if rep["gate"]:
        L.append("### Validation gate (spec v2 §14)")
        L.append("")
        L += _md_table(["Gate", "Question", "Criterion", "Evidence", ""],
                       [[g["gate"], g["what"], g["criterion"], g["evidence"],
                         "PASS" if g["status"] == "PASS" else "**FAIL**"] for g in rep["gate"]])
        L.append("")
    L += _findings_md(rep.get("findings_detail", []))
    fails = rep["failures"]
    L.append(f"## Failures ({len(fails)})")
    L.append("")
    if not fails:
        L.append("None.")
    for f in fails:
        L.append(f"- **{f['suite']} / {f['id']}**: {f['what']}  ")
        L.append(f"  Reproduce: `{f['repro']}`")
    L.append("")
    s = rep["suites"]
    if "offers" in s:
        d = s["offers"]["details"]
        L += [f"## {TITLES['offers']}", ""]
        c = d.get("counts", {})
        L.append(f"{c.get('items')} held-out messages ({c.get('en')} en, {c.get('zh')} zh; {c.get('must_abstain')} must "
                 f"abstain; {c.get('unlabelled_outcome', 0)} with the outcome unlabelled) in "
                 f"`{_rel(d.get('source'), 'fixtures/heldout/offers.yaml')}`, labelled by hand and never used to tune the grammar. "
                 f"Compiler backends: {d.get('backends')}. Compile latency p50/p95 "
                 f"{d.get('compile_ms', {}).get('p50')}/{d.get('compile_ms', {}).get('p95')} ms. The form baseline types "
                 f"the labels straight into the verifier.")
        L.append("")
        L += _md_table(["Item", "Kind", "Label", "Compiler verdict", "Form verdict", "Booked (compiler)", "Problems"],
                       [[r["id"], r["kind"], r["expect_outcome"], r["outcome"], r["form_outcome"],
                         ", ".join(f"{b['type']}{'@' + str(b['rate_bp']) + 'bp' if b['rate_bp'] else ''}"
                                   f"{'Δ' + str(b['days_delta']) + 'd' if b['days_delta'] else ''}" for b in r["booked"])
                         or "—",
                         "; ".join(e["what"] for e in r["material_errors"])
                         or ("should abstain" if r["expect_abstain"] and not r["abstained"] else
                             ("over-abstained" if r["abstained"] and not r["expect_abstain"] else
                              ("" if r["outcome_ok"] else "outcome")))]
                        for r in d.get("rows", [])])
        L.append("")
        L += _md_table(["Pair", "Relation", "Verdicts", "OK"],
                       [[f"{p['a']} ~ {p['b']}", p["relation"], f"{p['outcome_a']} / {p['outcome_b']}",
                         "yes" if p["ok"] else "**no**"] for p in d.get("pairs", [])])
        L.append("")
    if "financial" in s:
        d = s["financial"]["details"]
        L += [f"## {TITLES['financial']}", ""]
        L += _md_table(["Golden key", "Golden", "Computed", "Module", ""],
                       [[r["key"], r["golden"], r["computed"], r["source"], "exact" if r["exact"] else "**MISS**"]
                        for r in d.get("rows", [])])
        L.append("")
    if "funding" in s:
        d = s["funding"]["details"]
        g = d.get("grid", {})
        L += [f"## {TITLES['funding']}", ""]
        L.append(f"Brute force: every usable committed lever (a line draw per candidate repayment day, an advance or an "
                 f"early payment per receivable, bills, committed term loans), every combination of up to three, "
                 f"¥{g.get('pairs_step_fen', 0) / 100:,.0f} grid for pairs and ¥{g.get('triples_step_fen', 0) / 100:,.0f} "
                 f"for triples on all but one lever, the last filled exactly to the fen; budget {g.get('budget_s')} s "
                 f"per scenario. Baseline: draw the line first, then the cheapest other source by nominal rate.")
        L.append("")
        L += _md_table(["Scenario", "Need", "Router", "Brute force", "Line first", "Optimal", "Router plan", "ms"],
                       [[r["id"], _yuan(r["need_fen"]), _yuan(r["router_cost_fen"]),
                         _yuan(r["brute_cost_fen"]) + ("" if r["brute_complete"] else " (budget hit)"),
                         _yuan(r["baseline_cost_fen"]), "yes" if r["optimal"] else "**no**",
                         " + ".join(f"{a[0]} {a[1]} {_yuan(a[2])}{' ' + a[3] if a[3] else ''}"
                                    f"{' →d' + str(a[4]) if a[4] else ''}" for a in r["router_actions"]) or "—",
                         r.get("router_ms")] for r in d.get("rows", [])])
        L.append("")
    if "covenants" in s:
        d = s["covenants"]["details"]
        L += [f"## {TITLES['covenants']}", ""]
        L += _md_table(["Case", "Input", "Expect", "Got", "Observed", ""],
                       [[r["id"], r["input"], "violation" if r["expect_violation"] else "holds",
                         "violation" if r["got_violation"] else "holds",
                         (f"{r['observed'] or ''}{' month ' + str(r['month']) if r['month'] else ''}"
                         f"{' day ' + str(r['day']) if r['day'] else ''}"), "ok" if r["ok"] else "**MISS**"]
                        for r in d.get("rows", [])])
        L.append("")
    if "security" in s:
        d = s["security"]["details"]
        L += [f"## {TITLES['security']}", ""]
        L.append(f"Imported from `services/api/evals/security/latest_report.json` ({d.get('attacks')} attacks, "
                 f"catalogue {d.get('catalogue')}, LLM_MODE={d.get('llm_mode')}); not re-run here. "
                 f"Outcomes: {d.get('outcomes')}. Compiler flag rate on text attacks: "
                 f"{d.get('text_attack_compiler_flag_rate')}.")
        L.append("")
        L += _md_table(["Category", "Attacks", "Harm", "Detected", "SecurityEvent", "Contained only"],
                       [[c["label"], c["attacks"], c["harm"], c["detected"], c["security_event"], c["contained_only"]]
                        for c in d.get("per_category", [])])
        L.append("")
    if "intent" in s:
        d = s["intent"]["details"]
        L += [f"## {TITLES['intent']}", ""]
        L.append(f"{d.get('counts', {}).get('items')} held-out utterances ({d.get('counts', {}).get('zh')} zh) in "
                 f"`{_rel(d.get('source'), 'fixtures/heldout/intents.yaml')}`, each on a fresh session through POST /nl. Per intent: "
                 + ", ".join(f"{k} {v['ok']}/{v['n']}" for k, v in d.get("by_intent", {}).items()) + ".")
        L.append("")
        L += _md_table(["Id", "Utterance", "Label", "Got", "Source", "Slots", "Clarified"],
                       [[r["id"], r["text"], r["expect_intent"], r["intent"] if r["intent_ok"] else f"**{r['intent']}**",
                         r["parse_source"], ", ".join(f"{k}={'ok' if v else 'MISS'}" for k, v in r["slot_hits"].items()),
                         "yes" if r["clarified"] else ""] for r in d.get("rows", [])])
        L.append("")
    if "e2e" in s:
        d = s["e2e"]["details"]
        L += [f"## {TITLES['e2e']}", ""]
        t = d.get("tasks", {})
        L.append(f"`scripts/run_scenarios.py --inproc`: {t.get('summary')}. Scene 1 through the HTTP API "
                 f"(cold verifier caches each run):")
        L.append("")
        L += _md_table(["Run", "Compile ms", "Evaluate ms", "Negotiate+execute ms", "Total ms", "Result"],
                       [[r["rep"], r["compile_ms"], r["evaluate_ms"], r["negotiate_execute_ms"], r["total_ms"],
                         f"{r['outcome']} → {r['negotiation']} ({len(r['operations'])} ops)"]
                        for r in d.get("scene1", {}).get("runs", [])])
        L.append("")
    if "no_deal" in s:
        d = s["no_deal"]["details"]
        L += [f"## {TITLES['no_deal']}", ""]
        L += _md_table(["Check", "Result"], [[k, "ok" if v else "**failed**"] for k, v in d.get("checks", {}).items()])
        L.append("")
        L.append(f"Rounds: {len(d.get('rounds') or [])} of at most {d.get('max_rounds')}; operations {d.get('operations')}; "
                 f"lowest conservative cash afterwards {_yuan(d.get('min_cash_after_fen'))} on day {d.get('min_cash_day')}.")
        L.append("")
    nm = rep["meta"].get("not_measured", [])
    if nm:
        L += ["## Not measured", ""] + [f"- {x}" for x in nm] + [""]
    return "\n".join(L)


NOT_MEASURED = [
    "E2 “≥25% less handling than a form”: needs timed human operators; not measurable offline.",
    ("E2 with a live LLM compiler: this run uses LLM_MODE=cache, so held-out messages (never cached) go to the rules "
    "grammar. `scripts/evaluate.py --live` measures the configured Claude/DeepSeek backends (not run here: network)."),
    "E1, E6, E8 (market search, ClaimGraph-CN labels, blind explanation by non-builders): not software measurements.",
    ("Intent accuracy with the LLM classifier: offline the classifier cache misses on held-out text and falls back "
    "to OUT_OF_SCOPE."),
    "Security: imported from the security agent's latest report; not re-run by this harness.",
]


def main(suites: list[str], options: dict[str, dict[str, Any]], out_dir: Path | None,
         command: str) -> tuple[dict[str, Any], Path, Path]:
    t0 = time.perf_counter()
    results = run_all(suites, options)
    meta = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": _git("rev-parse", "--short", "HEAD"), "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "llm_mode": os.environ.get("LLM_MODE", "cache"), "suites": suites, "options": options, "command": command,
        "seconds": round(time.perf_counter() - t0, 1), "not_measured": NOT_MEASURED,
    }
    rep = to_json(results, meta)
    if set(suites) == set(ORDER):
        rep["findings_detail"] = load_findings()
    out = out_dir or EVALS
    out.mkdir(parents=True, exist_ok=True)
    jp, mp = out / "latest_report.json", out / "latest_report.md"
    jp.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    mp.write_text(to_markdown(rep), encoding="utf-8")
    return rep, jp, mp


def probe(text: str, counterparty_id: str = "BUYER-1") -> dict[str, Any]:
    """Compile one buyer message and run the verifier on the golden state; print what was booked."""
    quiet()
    from app.compiler import compile_offer
    from app.domain.fixtures import load_scenario
    from app.domain.models import SourceDocument
    from app.mandate import demo_owner_public_key_hex, load_signed_mandate
    from app.verifier import evaluate

    state, _ = load_scenario()
    doc = SourceDocument(doc_id="probe-msg", channel="chat", sender_id=counterparty_id, received_day=0, text=text)
    offer = compile_offer([doc], counterparty_id)
    b = evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex())
    v = b.verdict
    out = {"text": text, "compiler": offer.compiler, "status": offer.status.value,
           "abstentions": [a.field for a in offer.abstentions], "outcome": v.outcome.value,
           "codes": [x.code.value for x in v.violations], "forward_concession_total_fen": v.forward_concession_total_fen,
           "required_tier": v.required_tier.value,
           "booked": [] if v.outcome.value == "NO_VERDICT" else [
               {"type": o.type.value, "rate_bp": o.rate_bp, "base": o.base.kind.value,
                "base_amount_fen": o.base.amount_fen, "receivable_id": o.base.receivable_id, "days_delta": o.days_delta,
                "duration": o.duration.kind.value, "invoices": o.duration.invoices,
                "contingency": o.contingency.value} for o in b.bound_obligations]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out
