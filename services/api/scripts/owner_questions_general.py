"""Ask FLOW on general owner wording: send every item of evals/owner_questions/general.yaml to POST /nl as the owner, in a
fresh session each time, on the golden demo books (day 0), and score whether it reached the answer it should.

Same offline harness as scripts/owner_questions_baseline.py (imported from it): a TestClient over app.main, an in-memory
store, the cached LLM classifier (a miss is OUT_OF_SCOPE: no live model), DEMO_MODE=1, the repo .env never read and
outbound sockets refused. Nothing in the product is changed; the answer module's `answer` is wrapped only to record which
answer (question id) a turn used.

    cd services/api
    uv run python scripts/owner_questions_general.py --part tune      # the 60% the matcher may be tuned on
    uv run python scripts/owner_questions_general.py --part heldout   # the 40% held out (report only)
    uv run python scripts/owner_questions_general.py --part all       # both parts and all, with every miss

The split is fixed by a hash of the text (sha1 % 10 < 6 is the tuning part), so it never depends on the matcher.

Outcomes, per item:
  RIGHT  the answer module answered with the item's id (or one of its `also` ids); a page read the bank already counts as
         that question's own answer (who owes us, what is overdue, what is waiting, what changed); for `not_in_books`,
         the honest "FLOW's books do not hold ..." reply; for `out_of_scope_ok`, any reply that is not a books answer.
  WRONG  wrong topic: the answer module answered with another id, a books answer to chatter, or "the books do not hold
         this" for a question they hold.
  MISS   any other reply (out of scope, a clarification, an older read, "cannot answer yet").
A turn that executes or queues anything, or changes the books, is CRITICAL whatever its outcome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import owner_questions_baseline as base
import yaml
from fastapi.testclient import TestClient

GENERAL = base.API / "evals" / "owner_questions" / "general.yaml"
# Questions whose own answer is a page read (app/nl/reads.py), which the answer module leaves to it (rules._page_read).
PAGE_READ_OK = {"CUS-01": {"SHOW_STATUS"}, "CUS-03": {"RECONCILE"}, "DEAL-01": {"SHOW_ALERTS", "SHOW_STATUS"},
                "ACT-01": {"CHANGES"}}


def part_of(text: str) -> str:
    return "tune" if int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % 10 < 6 else "heldout"


class Recorder:
    """Wraps app.nl.answers.answer to note the question id of the answer a turn used (ask.py imports it per call)."""

    def __init__(self) -> None:
        import app.nl.answers as pkg

        self.pkg, self.inner, self.last = pkg, pkg.answer, None

        def wrapped(question, lang, ctx):  # type: ignore[no-untyped-def]
            got = self.inner(question, lang, ctx)
            if got is not None:
                self.last = got.question_id
            return got

        pkg.answer = wrapped


def outcome(item: dict, answered: str | None, intent: str, reply: str) -> tuple[str, str]:
    want = item["id"]
    ok = {want, *(item.get("also") or [])}
    if want == "out_of_scope_ok":
        return ("WRONG", f"answered {answered}") if answered else ("RIGHT", intent)
    if want == "not_in_books":
        if answered:
            return "WRONG", f"answered {answered}"
        return ("RIGHT", "not held") if base.NOT_HELD_REPLY.search(reply) else ("MISS", intent)
    if answered:
        return ("RIGHT", answered) if answered in ok else ("WRONG", f"answered {answered}")
    if intent in PAGE_READ_OK.get(want, set()):
        return "RIGHT", f"page read {intent}"
    if intent == base.ASK_INTENT and base.NOT_HELD_REPLY.search(reply):
        return "WRONG", "said the books do not hold it"
    return "MISS", intent


def run(mode: str) -> list[dict]:
    items = yaml.safe_load(GENERAL.read_text(encoding="utf-8"))["items"]
    from app.main import app

    rt = base.fresh_runtime()
    rec = Recorder()
    client = TestClient(app, headers=base.OWNER)
    rows = []
    path = "/nl?mode=business" if mode == "business" else "/nl"
    for item in items:
        before = base.fingerprint(rt)
        rec.last = None
        r = client.post(path, json={"session_id": "gq-" + uuid.uuid4().hex[:16], "actor": "OWNER", "text": item["q"],
                                    "lang": item["lang"]})
        after = base.fingerprint(rt)
        resp: dict[str, Any] = r.json() if r.status_code == 200 else {"intent": f"HTTP {r.status_code}", "reply": r.text[:300], "operations": []}
        sc, why = outcome(item, rec.last, resp["intent"], resp["reply"])
        executed = [o for o in resp.get("operations", []) if o.get("status") in ("EXECUTED", "PENDING_APPROVAL")]
        changed = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        rows.append({"q": item["q"], "lang": item["lang"], "id": item["id"], "also": item.get("also") or [], "part": part_of(item["q"]),
                     "answered": rec.last, "intent": resp["intent"], "score": sc, "why": why, "reply": resp["reply"],
                     "critical": bool(executed or changed)})
        if changed:
            rt = base.fresh_runtime()
    return rows


def table(rows: list[dict], label: str) -> list[str]:
    out = [f"{label}: {'lang':<5}{'right':>7}{'wrong':>7}{'miss':>7}{'total':>7}{'right %':>9}{'wrong %':>9}"]
    for lang in ("en", "zh", "all"):
        sel = [r for r in rows if lang == "all" or r["lang"] == lang]
        n = Counter(r["score"] for r in sel)
        t = len(sel) or 1
        out.append(f"{'':<{len(label) + 2}}{lang:<5}{n['RIGHT']:>7}{n['WRONG']:>7}{n['MISS']:>7}{len(sel):>7}"
                   f"{100 * n['RIGHT'] / t:>8.1f}%{100 * n['WRONG'] / t:>8.1f}%")
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined,union-attr,unused-ignore]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("business", "demo"), default="business")
    ap.add_argument("--part", choices=("tune", "heldout", "all"), default="tune")
    ap.add_argument("--out", type=Path, help="write every turn as JSON")
    args = ap.parse_args()
    rows = run(args.mode)
    shown = rows if args.part == "all" else [r for r in rows if r["part"] == args.part]
    if args.out:
        args.out.write_text(json.dumps(shown, ensure_ascii=False, indent=1), encoding="utf-8")
    crit = [r for r in rows if r["critical"]]
    print(f"mode={args.mode} items={len(rows)} critical={len(crit)}")
    for r in crit:
        print(f"  CRITICAL [{r['lang']}] {r['q']!r} -> {r['intent']}")
    parts = ("tune", "heldout", "all") if args.part == "all" else (args.part,)
    for p in parts:
        print("\n".join(table(rows if p == "all" else [r for r in rows if r["part"] == p], p)))
    for r in shown:
        if r["score"] != "RIGHT":
            print(f"{r['score']} {r['part']} [{r['lang']}] {r['id']} {r['q']!r} -> {r['why']} | {r['reply'][:110]!r}")


if __name__ == "__main__":
    main()
