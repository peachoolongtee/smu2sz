"""/nl intent parsing on held-out owner utterances (fixtures/heldout/intents.yaml, or --heldout DIR).

Each utterance runs through POST /nl on a freshly reset in-memory runtime (a new session, the golden
fixture at day 0), exactly as the UI would send it. The intent and the clarification come from the
response; the slots come from the rules parser's typed slot extraction (`app.nl.rules.slots_from`),
which is what the dispatcher receives (the response does not echo slots).
"""

from __future__ import annotations

import time
from typing import Any

import yaml

from evals.common import Failure, InProcApi, Metric, SuiteResult, heldout_path, median, pct, quiet, ratio

REPRO = "uv run --project services/api python scripts/evaluate.py --suite intent --only {id}"


def load(path: Any = None) -> list[dict[str, Any]]:
    """Utterances from `path`: an intents.yaml file or a held-out directory holding one (default
    fixtures/heldout)."""
    return yaml.safe_load(heldout_path(path, "intents.yaml").read_text(encoding="utf-8"))["intents"]


def run(only: list[str] | None = None, api: InProcApi | None = None, heldout: Any = None, **_: Any) -> SuiteResult:
    quiet()
    from app.nl.rules import slots_from

    source = heldout_path(heldout, "intents.yaml")
    items = [i for i in load(source) if not only or i["id"] in only]
    api = api or InProcApi()
    res = SuiteResult(name="intent")
    rows = []
    lat: list[float] = []
    for it in items:
        api.reset()
        t0 = time.perf_counter()
        code, resp = api.post("/nl", {"session_id": f"heldout-{it['id']}", "actor": "OWNER", "text": it["text"]})
        lat.append((time.perf_counter() - t0) * 1000)
        state = api.rt.store.get_state()
        slots = slots_from(it["text"], state).model_dump()
        want_slots = it.get("slots") or {}
        slot_hits = {k: slots.get(k) == v for k, v in want_slots.items()}
        clar = bool(resp.get("clarification")) or resp.get("intent") == "AMBIGUOUS"
        executed = [o["kind"] for o in resp.get("operations", []) if o.get("status") == "EXECUTED"]
        rows.append({"id": it["id"], "text": it["text"], "http": code, "expect_intent": it["intent"],
                     "intent": resp.get("intent"), "intent_ok": resp.get("intent") == it["intent"],
                     "parse_source": resp.get("parse_source"), "ambiguous": bool(it.get("ambiguous")),
                     "clarified": clar, "expect_slots": want_slots,
                     "slots": {k: slots.get(k) for k in want_slots}, "slot_hits": slot_hits,
                     "executed": executed, "reply": (resp.get("reply") or "")[:200],
                     "latency_ms": round(lat[-1], 1)})
    n = len(rows)
    ok = sum(r["intent_ok"] for r in rows)
    slot_total = sum(len(r["slot_hits"]) for r in rows)
    slot_ok = sum(sum(r["slot_hits"].values()) for r in rows)
    amb = [r for r in rows if r["ambiguous"]]
    clear = [r for r in rows if not r["ambiguous"]]
    amb_ok = sum(r["clarified"] for r in amb)
    over = sum(r["clarified"] for r in clear)
    by_intent: dict[str, dict[str, int]] = {}
    for r in rows:
        d = by_intent.setdefault(r["expect_intent"], {"n": 0, "ok": 0})
        d["n"] += 1
        d["ok"] += r["intent_ok"]
    res.details = {"rows": rows, "by_intent": by_intent, "source": str(source), "latency_ms": {"p50": median(lat), "p95": pct(lat, 95)},
                   "counts": {"items": n, "zh": sum(any("一" <= c <= "鿿" for c in r["text"]) for r in rows)}}
    res.metrics += [
        Metric("intent_accuracy", "Intent accuracy (held-out owner utterances)", ratio(ok, n),
               f"{ok}/{n} ({(ratio(ok, n) or 0):.0%})", "informational", None, "intent"),
        Metric("slot_accuracy", "Slot accuracy (labelled key slots)", ratio(slot_ok, slot_total),
               f"{slot_ok}/{slot_total} ({(ratio(slot_ok, slot_total) or 0):.0%})", "informational", None, "intent"),
        Metric("clarification_rate", "Clarification rate on deliberately ambiguous requests", ratio(amb_ok, len(amb)),
               f"{amb_ok}/{len(amb)}", "informational", None, "intent",
               f"over-clarified {over}/{len(clear)} clear requests"),
    ]
    for r in rows:
        probs = []
        if not r["intent_ok"]:
            probs.append(f"intent {r['intent']} != {r['expect_intent']} (source {r['parse_source']})")
        bad = [f"{k}={r['slots'][k]!r} (want {r['expect_slots'][k]!r})" for k, hit in r["slot_hits"].items() if not hit]
        if bad:
            probs.append("slots " + ", ".join(bad))
        if r["ambiguous"] and not r["clarified"]:
            probs.append("no clarifying question")
        if probs:
            res.failures.append(Failure("intent", r["id"], f"{r['id']} {r['text']!r}: " + "; ".join(probs),
                                        REPRO.format(id=r["id"]), r))
    return res
