"""E2 held-out offers: compiler + verifier against hand labels, and the "form" baseline.

For every item in fixtures/heldout/offers.yaml the real pipeline runs (compiler in the configured
LLM_MODE, then the verifier on the golden state). Metrics:

- MATERIAL ERROR RATE: items (not labelled abstain) where the system booked a verdict and at least one
  booked obligation has a wrong type (missing or spurious), rate, amount, days/duration or contingency.
- SILENT MATERIAL ERRORS: the above plus must-abstain items where something was booked anyway.
- ABSTENTION precision/recall: predicted NO_VERDICT against `abstain` labels.
- WORDING INVARIANCE: same pairs need the same verdict and the same booked economics; near-miss pairs
  need different verdicts.
- VERDICT AGREEMENT: outcome == label, for the compiler and for the form baseline (labels as input).
"""

from __future__ import annotations

import json
import time
from typing import Any

import yaml

from evals.common import HELDOUT, Failure, Metric, SuiteResult, median, pct, quiet, ratio

REPRO = "uv run --project services/api python scripts/evaluate.py --suite offers --only {id}"
FIELD_GROUP = {"rate_bp": "rate", "base_amount_fen": "amount", "amount_fen": "amount", "days_delta": "days",
               "invoices": "days", "duration": "days", "contingency": "contingency"}
ACCEPTISH = {"ACCEPT", "NEEDS_OWNER_APPROVAL"}


def load(path: Any = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = yaml.safe_load((path or HELDOUT / "offers.yaml").read_text(encoding="utf-8"))
    return data["offers"], data.get("pairs", [])


def documents(item: dict[str, Any]) -> list[Any]:
    from app.domain.models import SourceDocument

    cp = item.get("counterparty_id", "BUYER-1")
    raw = item.get("documents") or [{"doc_id": f"{item['id']}-msg", "channel": "chat", "sender_id": cp,
                                     "received_day": 0, "text": item["text"]}]
    return [SourceDocument.model_validate_json(json.dumps(d)) for d in raw]


def _field(ob: Any, name: str) -> Any:
    match name:
        case "base_amount_fen":
            return ob.base.amount_fen
        case "invoices":
            return ob.duration.invoices
        case "duration":
            return ob.duration.kind.value
        case "contingency":
            return ob.contingency.value
        case _:
            return getattr(ob, name)


def compare(booked: list[Any], labels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Material differences between booked obligations and labels (matched by type, in order)."""
    errs: list[dict[str, Any]] = []
    by_type: dict[str, list[Any]] = {}
    for ob in booked:
        by_type.setdefault(ob.type.value, []).append(ob)
    want: dict[str, list[dict[str, Any]]] = {}
    for lb in labels:
        want.setdefault(lb["type"], []).append(lb)
    for t in sorted(set(by_type) | set(want)):
        got_t, want_t = by_type.get(t, []), want.get(t, [])
        for lb in want_t[len(got_t):]:
            errs.append({"group": "type", "field": "type", "want": t, "got": None, "what": f"missing {t}"})
        for ob in got_t[len(want_t):]:
            errs.append({"group": "type", "field": "type", "want": None, "got": t, "what": f"spurious {t}"})
        for ob, lb in zip(got_t, want_t, strict=False):
            for f, g in FIELD_GROUP.items():
                if f in lb and _field(ob, f) != lb[f]:
                    errs.append({"group": g, "field": f"{t}.{f}", "want": lb[f], "got": _field(ob, f),
                                 "what": f"{t}.{f}: {_field(ob, f)!r} != {lb[f]!r}"})
    return errs


def signature(obs: list[Any]) -> list[tuple]:
    return sorted((o.type.value, o.rate_bp, o.base.amount_fen, o.amount_fen, o.days_delta, o.duration.kind.value,
                   o.duration.invoices, o.contingency.value) for o in obs)


def cap_decision(labels: list[dict[str, Any]], max_bp: int) -> str:
    """A static cap: accept if every stated rate is within the discount cap and terms stay at 60 days or less."""
    ok = all((lb.get("rate_bp") or 0) <= max_bp for lb in labels) and all(
        (lb.get("target_terms_days") or 0) <= 60 for lb in labels)
    return "ACCEPT" if ok else "REJECT"


def run(only: list[str] | None = None, **_: Any) -> SuiteResult:
    quiet()
    from app.compiler import compile_offer
    from app.domain.fixtures import load_scenario
    from app.domain.models import CompileStatus
    from app.mandate import demo_owner_public_key_hex, load_signed_mandate
    from app.verifier import evaluate

    from evals.forms import form_offer

    items, pairs = load()
    if only:
        items = [i for i in items if i["id"] in only]
        pairs = [p for p in pairs if p["a"] in only and p["b"] in only]
    state, _ = load_scenario()
    m = load_signed_mandate()
    key = demo_owner_public_key_hex()
    res = SuiteResult(name="offers")
    rows: list[dict[str, Any]] = []
    bundles: dict[str, Any] = {}
    compile_ms: list[float] = []
    for it in items:
        exp = it["expect"]
        cp = it.get("counterparty_id", "BUYER-1")
        docs = documents(it)
        t0 = time.perf_counter()
        offer = compile_offer(docs, cp)
        compile_ms.append((time.perf_counter() - t0) * 1000)
        b = evaluate(offer, state, m, trusted_owner_key_hex=key, owner_declared=it.get("declared_costs"))
        bundles[it["id"]] = b
        v = b.verdict
        abstained = v.outcome.value == "NO_VERDICT"
        booked = [] if abstained else list(b.bound_obligations)
        labels = exp.get("booked", [])
        errs = [] if abstained else compare(booked, labels)
        codes = list(dict.fromkeys(x.code.value for x in v.violations))
        # the form baseline: the labels themselves, typed into the verifier
        if exp.get("abstain"):
            form_outcome, form_codes = "NO_VERDICT", []
        else:
            fo = form_offer(docs, cp, [*labels, *exp.get("claims", [])], status=CompileStatus.COMPILED,
                            offer_id=f"FORM-{it['id']}")
            fb = evaluate(fo, state, m, trusted_owner_key_hex=key, owner_declared=it.get("declared_costs"))
            form_outcome = fb.verdict.outcome.value
            form_codes = list(dict.fromkeys(x.code.value for x in fb.verdict.violations))
        rows.append({
            "id": it["id"], "kind": it["kind"], "lang": "zh" if any("一" <= ch <= "鿿" for d in docs
                                                                   for ch in d.text) else "en",
            "counterparty_id": cp, "text": " | ".join(d.text for d in docs),
            "compiler": offer.compiler, "compile_status": offer.status.value,
            "expect_abstain": bool(exp.get("abstain")), "abstained": abstained,
            "expect_outcome": exp["outcome"], "outcome": v.outcome.value, "outcome_ok": v.outcome.value == exp["outcome"],
            "expect_codes": exp.get("codes", []), "codes": codes,
            "codes_ok": set(exp.get("codes", [])) <= set(codes),
            "booked": [{"type": o.type.value, "rate_bp": o.rate_bp, "base_amount_fen": o.base.amount_fen,
                        "amount_fen": o.amount_fen, "days_delta": o.days_delta, "duration": o.duration.kind.value,
                        "invoices": o.duration.invoices, "contingency": o.contingency.value} for o in booked],
            "compiled": [{"type": o.type.value, "rate_bp": o.rate_bp, "target_terms_days": o.target_terms_days,
                          "days_delta": o.days_delta, "base_amount_fen": o.base.amount_fen,
                          "contingency": o.contingency.value, "duration": o.duration.kind.value,
                          "invoices": o.duration.invoices} for o in offer.obligations],
            "abstentions": [a.field for a in offer.abstentions],
            "material_errors": errs,
            "form_outcome": form_outcome, "form_ok": form_outcome == exp["outcome"], "form_codes": form_codes,
            "compile_ms": round(compile_ms[-1], 1),
        })
    by_id = {r["id"]: r for r in rows}

    # -------- metrics
    non_abstain = [r for r in rows if not r["expect_abstain"]]
    must_abstain = [r for r in rows if r["expect_abstain"]]
    mat = [r for r in non_abstain if r["material_errors"]]
    silent_booked_on_abstain = [r for r in must_abstain if not r["abstained"] and r["booked"]]
    tp = sum(r["abstained"] for r in must_abstain)
    fp = sum(r["abstained"] for r in non_abstain)
    fn = len(must_abstain) - tp
    prec, rec = ratio(tp, tp + fp), ratio(tp, tp + fn)
    agree = sum(r["outcome_ok"] for r in rows)
    form_agree = sum(r["form_ok"] for r in rows)
    same = [p for p in pairs if p["relation"] == "same"]
    diff = [p for p in pairs if p["relation"] == "different"]
    pair_rows = []
    for p in pairs:
        a, b = by_id.get(p["a"]), by_id.get(p["b"])
        if not a or not b:
            continue
        sa = signature(list(bundles[p["a"]].bound_obligations)) if not a["abstained"] else []
        sb = signature(list(bundles[p["b"]].bound_obligations)) if not b["abstained"] else []
        if p["relation"] == "same":
            ok = a["outcome"] == b["outcome"] and sa == sb
        else:
            ok = a["outcome"] != b["outcome"]
        pair_rows.append({**p, "ok": ok, "outcome_a": a["outcome"], "outcome_b": b["outcome"],
                          "same_terms": sa == sb})
    same_ok = sum(x["ok"] for x in pair_rows if x["relation"] == "same")
    diff_ok = sum(x["ok"] for x in pair_rows if x["relation"] == "different")
    # engine vs a static cap (E2: "engine ≠ cap"), on items the form can evaluate
    capable = [r for r in rows if not r["expect_abstain"] and r["kind"] != "security"]
    item_by_id = {it["id"]: it for it in items}
    cap_diff = sum((r["form_outcome"] in ACCEPTISH) != (cap_decision(item_by_id[r["id"]]["expect"].get("booked", []),
                                                                     m.max_immediate_discount_bp or 150) == "ACCEPT")
                   for r in capable)
    field_counts: dict[str, int] = {}
    for r in mat:
        for e in r["material_errors"]:
            field_counts[e["group"]] = field_counts.get(e["group"], 0) + 1
    backends: dict[str, int] = {}
    for r in rows:
        backends[r["compiler"]] = backends.get(r["compiler"], 0) + 1
    mer = ratio(len(mat), len(non_abstain))
    res.details = {"rows": rows, "pairs": pair_rows, "material_error_fields": field_counts, "backends": backends,
                   "counts": {"items": len(rows), "must_abstain": len(must_abstain), "non_abstain": len(non_abstain),
                              "en": sum(r["lang"] == "en" for r in rows), "zh": sum(r["lang"] == "zh" for r in rows)},
                   "compile_ms": {"p50": median(compile_ms), "p95": pct(compile_ms, 95)}}
    gap = (form_agree - agree) / len(rows) if rows else 0.0
    res.metrics += [
        Metric("compiler_material_error_rate", "Compiler material error rate (held-out, booked verdicts)", mer,
               f"{len(mat)}/{len(non_abstain)} ({(mer or 0):.1%})", "≤ 5%", (mer or 0) <= 0.05, "offers",
               "fields: " + ", ".join(f"{k} {v}" for k, v in sorted(field_counts.items())) if field_counts else ""),
        Metric("silent_material_errors", "E2 silent material errors (incl. booked on must-abstain)",
               len(mat) + len(silent_booked_on_abstain), str(len(mat) + len(silent_booked_on_abstain)), "0",
               len(mat) + len(silent_booked_on_abstain) == 0, "offers"),
        Metric("abstention_precision", "Abstention precision (NO_VERDICT when it should)", prec,
               f"{tp}/{tp + fp}" + (f" ({prec:.0%})" if prec is not None else ""), "informational", None, "offers"),
        Metric("abstention_recall", "Abstention recall (must-abstain items caught)", rec,
               f"{tp}/{tp + fn}" + (f" ({rec:.0%})" if rec is not None else ""), "informational", None, "offers"),
        Metric("wording_invariance_same", "Wording invariance: same economics → same verdict and terms",
               ratio(same_ok, len(same)), f"{same_ok}/{len(same)}", "informational", None, "offers"),
        Metric("wording_invariance_near_miss", "Near-miss pairs → different verdicts", ratio(diff_ok, len(diff)),
               f"{diff_ok}/{len(diff)}", "informational", None, "offers"),
        Metric("verdict_agreement", "Verdict agreement with labels (compiler)", ratio(agree, len(rows)),
               f"{agree}/{len(rows)} ({(ratio(agree, len(rows)) or 0):.0%})", "informational", None, "offers"),
        Metric("verdict_agreement_form", "Verdict agreement with labels (form baseline: labels as input)",
               ratio(form_agree, len(rows)), f"{form_agree}/{len(rows)} ({(ratio(form_agree, len(rows)) or 0):.0%}); "
               f"gap {gap:+.0%}", "informational", None, "offers"),
        Metric("engine_vs_cap", "E2 engine ≠ static cap (form inputs)", ratio(cap_diff, len(capable)),
               f"{cap_diff}/{len(capable)}", "≥ 35% (7/20)", cap_diff * 20 >= 7 * max(1, len(capable)), "offers"),
    ]
    for r in rows:
        problems = []
        if r["material_errors"]:
            problems.append("material: " + "; ".join(e["what"] for e in r["material_errors"]))
        if r["expect_abstain"] and not r["abstained"]:
            problems.append(f"should abstain, got {r['outcome']} booking {[b['type'] for b in r['booked']]}")
        if r["abstained"] and not r["expect_abstain"]:
            problems.append(f"abstained ({r['codes']}) where the terms are clear")
        if not r["outcome_ok"]:
            problems.append(f"outcome {r['outcome']} != {r['expect_outcome']}")
        elif not r["codes_ok"]:
            problems.append(f"codes {r['codes']} lack {sorted(set(r['expect_codes']) - set(r['codes']))}")
        if not r["form_ok"]:
            problems.append(f"FORM baseline outcome {r['form_outcome']} != label {r['expect_outcome']} "
                            f"({r['form_codes']})")
        if problems:
            res.failures.append(Failure("offers", r["id"], f"{r['id']} [{r['kind']}] {r['text'][:90]!r}: "
                                        + " | ".join(problems), REPRO.format(id=r["id"]), r))
    for pr in pair_rows:
        if not pr["ok"]:
            res.failures.append(Failure(
                "offers", f"pair:{pr['a']}~{pr['b']}",
                f"{pr['relation']} pair {pr['a']} ({pr['outcome_a']}) vs {pr['b']} ({pr['outcome_b']})"
                + ("" if pr["relation"] == "different" else f", same booked terms: {pr['same_terms']}"),
                REPRO.format(id=f"{pr['a']},{pr['b']}"), pr))
    return res
