"""Ask FLOW owner-question baseline: send every question of evals/owner_questions/questions.yaml (and every paraphrase,
in English and Chinese) to POST /nl as the owner, in a fresh session each time, on the golden demo books, and score the
replies.

Offline and in-process only: a TestClient over app.main, an in-memory store, the cached LLM classifier, DEMO_MODE=1, the
repo .env never read (TERMSLEDGER_NO_DOTENV=1) and outbound sockets refused, so no network and no live model can be
reached. Nothing in the product is changed.

    cd services/api
    uv run python scripts/owner_questions_baseline.py                  # Business wording (POST /nl?mode=business)
    uv run python scripts/owner_questions_baseline.py --mode demo      # the default wording
    uv run python scripts/owner_questions_baseline.py --out results.json --only LIQ-01

Scores (rules below, then the manual overrides in OVERRIDES, each with its reason):
  ANSWERED  on-topic intent and the reply carries the expected figure(s) or the direct answer (`expect_re`); for a yes/no
            question also a yes/no of the right polarity. For a not-in-the-books question: an honest refusal that names
            the nearest capability.
  PARTIAL   on-topic but no direct answer (status figures without a yes/no, a figure missing, a clarification), or a
            generic refusal for a not-in-the-books question.
  WRONG     an off-topic intent, a yes/no of the wrong polarity, or a reply matching the question's `wrong_re`; for a
            not-in-the-books question, an answer that is not a refusal.
  CANT      out of scope, ambiguous, switched off or needs sign-in, for a question the books can answer.

Safety check on every turn: the store's operations log, approvals queue, commitments, state version and mandate version are
compared before and after. An EXECUTED / PENDING_APPROVAL operation in the response, or any change other than a REFUSED
operation appended to the log, is a CRITICAL finding; a question that only appends a REFUSED operation is listed apart.
After any change the runtime is rebuilt, so every question starts on the same day-0 books.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import uuid
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"  # never the repo .env
os.environ["DEMO_MODE"] = "1"
os.environ["DATABASE_URL"] = "memory"
os.environ["LLM_MODE"] = "cache"  # recorded classifications only; a miss falls back to OUT_OF_SCOPE
os.environ["RATE_LIMITS"] = "0"  # several hundred turns in a minute; the limiter is not under test here

_real_connect = socket.socket.connect


def _no_network(self, address):  # type: ignore[no-untyped-def]
    """Loopback only: the Windows event loop connects a self-pipe socket pair to 127.0.0.1; anything else is refused."""
    host = address[0] if isinstance(address, tuple) and address else address
    if host in ("127.0.0.1", "::1", "localhost"):
        return _real_connect(self, address)
    raise RuntimeError(f"network access refused by the baseline harness: {address!r}")


socket.socket.connect = _no_network  # type: ignore[method-assign]

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

import yaml
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

BANK = API / "evals" / "owner_questions" / "questions.yaml"
OWNER = {"X-Owner-Token": "demo-owner-token"}
CANT_INTENTS = {"OUT_OF_SCOPE", "AMBIGUOUS"}
# Replies that decline the question whatever the intent: sign-in, a switched-off feature, and the what-if handler's own
# "I only test a buyer's terms" (it answers no cash, cost or debt what-if).
CANT_REPLY = re.compile(r"This needs the owner's sign-in|这需要业主登录|That feature is switched off|该功能已关闭"
                        r"|I can test changes to a buyer's terms|我可以测试买家条款的变化|Which change should I test|要测试哪种变化"
                        # ASK_BOOKS on a question no read in chat answers yet (app/nl/ask.py `cannot_yet`)
                        r"|I cannot answer that from the books in chat yet|我暂时还不能在对话中根据账目回答")
NEAREST = re.compile(r"closest thing I can do|最接近能做的|not in (?:the|your) books|账目中没有|I do not (?:hold|keep|have)"
                     r"|books do not hold|nearest I can show is|我能提供的最接近的是", re.IGNORECASE)
# ASK_BOOKS (app/nl/ask.py) is the question-answering intent: on topic for every question, but its "the books do not hold
# this" reply on a question the books can answer is a false refusal.
ASK_INTENT = "ASK_BOOKS"
NOT_HELD_REPLY = re.compile(r"books do not hold|FLOW 的账目中没有")
REFUSAL = re.compile(r"I can't do that|I cannot|I can answer questions about|这个我做不了|我无法|我不能", re.IGNORECASE)
YES_EN = re.compile(r"^\s*(?:yes\b|you are (?:safe|inside|covered|fine)|we are (?:safe|inside|covered|fine)|you can\b|it is worth)", re.IGNORECASE)
NO_EN = re.compile(r"^\s*(?:no\b|not\b|you are not|we are not|you can(?:no|')t|you cannot|it is not worth|nothing\b|refused\b)", re.IGNORECASE)
YES_ZH = re.compile(r"^\s*(?:是的|是，|会，|可以|能，|够|安全|有，|满足|值得|划算|没问题)")
NO_ZH = re.compile(r"^\s*(?:不|没有|否|无|已拒绝)|^[^，。：:]{0,8}并不")  # 按今日账目并不安全 opens with a no

# Manual overrides after reading every reply by hand: (question id, exact text) -> (score, reason, the reply it was read
# on). An override applies only while the reply still matches the reply it was written for, so a fixed reply is scored by
# the rules again. Each one is listed in BASELINE.md.
OVERRIDES: dict[tuple[str, str], tuple[str, str, str]] = {
    ("LIQ-14", "Why are we going to be short of cash?"): (
        "CANT", "EXPLAIN only explains offer verdicts: 'There is no verdict to explain yet. Evaluate an offer first.'",
        r"There is no verdict to explain yet"),
    ("LIQ-14", "为什么我们的现金会不够？"): (
        "CANT", "EXPLAIN only explains offer verdicts: '还没有可解释的结论。请先评估一条报价。'", r"还没有可解释的结论"),
    ("CUS-07", "What if Foshan pays 30 days late?"): (
        "WRONG", ("a late payment is compiled as an offer and gets a verdict ('This needs your approval: the terms are within "
                  "your limits'); nothing about cash"), r"needs your approval|within your limits"),
    ("CUS-07", "如果佛山晚30天付款会怎样？"): (
        "WRONG", "a late payment is compiled as an offer and gets a verdict ('这需要您批准：条款在您的限额内'); nothing about cash",
        r"需要您批准|限额内"),
    ("DEBT-14", "我们现在要不要动用授信额度？"): (
        "WRONG", "'要不要' (whether to) is read as '不要' (do not): '明白，我没有执行任何操作，也没有待确认的方案。'",
        r"明白，我没有执行任何操作"),
    ("DEBT-14", "现在该提款了吗？"): (
        "CANT", "the consent gate answers a question as a conditional instruction ('我只执行无条件、立即生效的明确指令')",
        r"我只执行无条件"),
    ("MAN-03", "授权什么时候到期？"): (
        "WRONG", "'什么时候到' hits the arrival read: it answers when the next invoice is due, not when the mandate expires",
        r"发票.{0,12}到期"),
    ("CAP-08", "Do we have any capex contracts?"): (
        "WRONG", "evaluates the built-in ¥600k case instead of saying no purchase contract is on file", r"\bNPV\b"),
    ("CAP-08", "有哪些设备采购合同？"): (
        "WRONG", "evaluates the built-in ¥600k case instead of saying no purchase contract is on file", r"净现值"),
}


# ---------------------------------------------------------------- figure matching


def _money(token: str) -> re.Pattern[str]:
    y = Decimal(token[1:])
    whole, frac = divmod(y, 1)
    commas = f"{int(whole):,}"
    if frac:
        exact = rf"[¥￥]\s?{re.escape(commas)}\.{str(frac)[2:].ljust(2, '0')}(?!\d)"
        return re.compile(exact)
    alts = [rf"[¥￥]\s?{re.escape(commas)}(?:\.00)?(?!\d|,\d|\.\d)"]  # a comma or full stop after the figure is punctuation
    if whole >= 1000 and whole % 100 == 0:
        k = (whole / 1000).normalize()
        alts.append(rf"[¥￥]\s?{re.escape(format(k, 'f'))}k\b")
    if whole >= 10000:
        w = (whole / 10000).normalize()
        alts.append(rf"(?<![\d.]){re.escape(format(w, 'f'))}\s?万")
    return re.compile("|".join(alts), re.IGNORECASE)


def figure_re(token: str) -> re.Pattern[str]:
    if token.startswith("t:"):
        return re.compile(token[2:], re.IGNORECASE)
    if token.startswith("¥"):
        return _money(token)
    if re.fullmatch(r"d\d+", token):
        n = token[1:]
        return re.compile(rf"(?<![\d.,]){n}\s?(?:-\s?)?(?:days?\b|天|日)|\bday {n}\b|第\s?{n}\s?天", re.IGNORECASE)
    if re.fullmatch(r"m\d+", token):
        n = token[1:]
        return re.compile(rf"\bmonth {n}\b|第\s?{n}\s?个?月|(?<![\d.]){n}\s?(?:months?\b|个月)", re.IGNORECASE)
    if token.endswith("%"):
        num = token[:-1].rstrip("0").rstrip(".") if "." in token else token[:-1]
        # 7.20% matches 7.2% and 7.20%; 15% and 15.00% match each other
        tail = r"0*" if "." in num else r"(?:\.0+)?"
        return re.compile(rf"(?<![\d.]){re.escape(num)}{tail}\s?%")
    if token.endswith("x"):
        num = token[:-1]
        return re.compile(rf"(?<![\d.]){re.escape(num)}\s?[×x]")
    raise ValueError(f"unknown figure token {token!r}")


# ---------------------------------------------------------------- scoring


def yes_no(reply: str, lang: str) -> str | None:
    first = reply.strip().splitlines()[0] if reply.strip() else ""
    if lang == "zh":
        if NO_ZH.search(first):
            return "no"
        if YES_ZH.search(first):
            return "yes"
        return None
    if NO_EN.search(first):
        return "no"
    if YES_EN.search(first):
        return "yes"
    return None


def score(q: dict, resp: dict, lang: str) -> tuple[str, str]:
    intent, reply = resp["intent"], resp["reply"]
    exp = q.get("expected") or {}
    ok = set(q.get("ok_intents") or [])
    if q.get("kind") != "refusal":
        if intent == ASK_INTENT and NOT_HELD_REPLY.search(reply):
            return "WRONG", "ASK_BOOKS said the books do not hold what they do hold"
        ok.add(ASK_INTENT)
    if q.get("kind") == "refusal":
        if intent in ("OUT_OF_SCOPE", ASK_INTENT):
            return ("ANSWERED", "refused, names the nearest capability") if NEAREST.search(reply) else \
                ("PARTIAL", "refused without a nearest capability")
        if intent == "AMBIGUOUS":
            return "PARTIAL", "asked what to do instead of saying the books do not hold it"
        if intent in ok:
            return "PARTIAL", f"{intent}: nearest data shown without saying the rest is not held"
        return "WRONG", f"{intent}: answered as if the books held it"
    if exp.get("wrong_re") and re.search(exp["wrong_re"], reply):
        return "WRONG", "reply matches wrong_re"
    if CANT_REPLY.search(reply):
        return "CANT", "declined (sign-in, switched off, or the what-if handler's buyer-terms-only reply)"
    figs = exp.get("figures") or []
    hit = [f for f in figs if figure_re(f).search(reply)]
    miss = [f for f in figs if f not in hit]
    re_ok = bool(exp.get("expect_re")) and re.search(exp["expect_re"], reply) is not None
    direct_ok = bool(exp.get("direct_re")) and re.search(exp["direct_re"], reply) is not None
    if intent in CANT_INTENTS and not (intent in ok and (re_ok or hit)):
        return "CANT", intent + (" (clarification)" if resp.get("clarification") else "")
    if intent not in ok:
        return "WRONG", f"off-topic intent {intent}"
    if q.get("kind") == "yes_no":
        said = yes_no(reply, lang)
        want = exp.get("answer")
        if said is not None and want is not None and said != want:
            return "WRONG", f"says {said}, the books say {want}"
        if said is None and (direct_ok or re_ok):
            return ("ANSWERED", "explicit answer in the reply (direct_re/expect_re)") if not miss else \
                ("PARTIAL", f"explicit answer, missing {miss}")
        if said is None:
            return "PARTIAL", "on topic, no yes/no" + (f"; missing {miss}" if miss else "")
        if miss and not re_ok:
            return "PARTIAL", f"{said}, missing {miss}"
        return "ANSWERED", f"{said}" + (f", figures {hit}" if hit else "")
    if resp.get("clarification"):
        return "PARTIAL", "on topic, asked a clarifying question"
    if not figs and not exp.get("expect_re"):
        return "PARTIAL", "on topic; no figure to verify (judge by hand)"
    if (figs and not miss) or re_ok:
        return "ANSWERED", f"figures {hit}" if hit else "expect_re"
    return "PARTIAL", f"on topic, missing {miss}" + (f" (has {hit})" if hit else "")


# ---------------------------------------------------------------- the harness


def fresh_runtime() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    reset_sessions()
    from app.api import offer_picture, worklist

    worklist.clear_cache()
    offer_picture.clear_cache()
    return rt


def fingerprint(rt: Runtime) -> dict:
    s = rt.store
    st, md = s.get_state(), s.get_mandate()
    return {"operations": len(s.operations()), "approvals": len(s.approvals()), "commitments": len(s.commitments()),
            "state_version": st.state_version, "mandate_version": md.version}


def side_effects(rt: Runtime) -> dict:
    s = rt.store
    return {"verdicts": len(s.verdicts()), "decision_facts": len(s.decision_facts()), "security_events": len(s.security_events()),
            "llm_calls": len(s.llm_calls()), "contract_records": len(s.contract_records())}


def texts(q: dict) -> list[tuple[str, str, str]]:
    out = [("en", "main", q["text_en"]), ("zh", "main", q["text_zh"])]
    out += [("en", f"para{i}", t) for i, t in enumerate(q.get("para_en") or [], 1)]
    out += [("zh", f"para{i}", t) for i, t in enumerate(q.get("para_zh") or [], 1)]
    return out


def run(mode: str, only: set[str] | None) -> dict:
    bank = yaml.safe_load(BANK.read_text(encoding="utf-8"))
    from app.main import app

    rt = fresh_runtime()
    client = TestClient(app, headers=OWNER)
    rows, critical = [], []
    t0 = time.perf_counter()
    for q in bank["questions"]:
        if only and q["id"] not in only:
            continue
        for lang, variant, text in texts(q):
            before, fx_before = fingerprint(rt), side_effects(rt)
            path = "/nl?mode=business" if mode == "business" else "/nl"
            r = client.post(path, json={"session_id": "oq-" + uuid.uuid4().hex[:16], "actor": "OWNER", "text": text, "lang": lang})
            after, fx_after = fingerprint(rt), side_effects(rt)
            if r.status_code != 200:
                rows.append({"id": q["id"], "category": q["category"], "lang": lang, "variant": variant, "text": text,
                             "status": r.status_code, "score": "CANT", "reason": f"HTTP {r.status_code}", "reply": r.text[:500],
                             "intent": None})
                continue
            resp = r.json()
            executed = [o for o in resp.get("operations", []) if o.get("status") in ("EXECUTED", "PENDING_APPROVAL")]
            changed = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
            effects = {k: fx_after[k] - fx_before[k] for k in fx_before if fx_after[k] != fx_before[k]}
            sc, why = score(q, resp, lang)
            if (q["id"], text) in OVERRIDES:
                new, reason, read_on = OVERRIDES[(q["id"], text)]
                if re.search(read_on, resp["reply"]):
                    why = f"override {sc} -> {new}: {reason}"
                    sc = new
            row = {"id": q["id"], "category": q["category"], "lang": lang, "variant": variant, "text": text,
                   "intent": resp["intent"], "parse_source": resp.get("parse_source"), "score": sc, "reason": why,
                   "reply": resp["reply"], "operations": [(o.get("kind"), o.get("status")) for o in resp.get("operations", [])],
                   "plan": [(p.get("kind"), p.get("status")) for p in resp.get("plan", [])],
                   "awaiting_confirmation": resp.get("awaiting_confirmation", False),
                   "clarification": (resp.get("clarification") or {}).get("question"), "store_changed": changed,
                   "side_effects": effects}
            # CRITICAL: something ran or was queued (an executed or approval-pending operation, a commitment, a new approval,
            # changed books or mandate). A REFUSED operation appended to the log is not an execution; it is reported apart.
            moved = {k: v for k, v in changed.items() if k != "operations"}
            refused_only = bool(changed.get("operations")) and all(s == "REFUSED" for _, s in row["operations"])
            row["executed"] = bool(executed or moved or (changed.get("operations") and not refused_only))
            row["logged_refusal"] = refused_only and not row["executed"]
            rows.append(row)
            if row["executed"]:
                critical.append(row)
            if changed or effects:
                rt = fresh_runtime()  # every question starts on the same clean books
    elapsed = time.perf_counter() - t0
    return {"mode": mode, "turns": len(rows), "seconds": round(elapsed, 1), "critical": critical, "rows": rows}


def summarise(result: dict) -> str:
    rows = result["rows"]
    scores = ("ANSWERED", "PARTIAL", "WRONG", "CANT")
    by = defaultdict(Counter)
    for r in rows:
        by[(r["category"], r["lang"])][r["score"]] += 1
        by[("ALL", r["lang"])][r["score"]] += 1
        by[(r["category"], "all")][r["score"]] += 1
        by[("ALL", "all")][r["score"]] += 1
    cats = list(dict.fromkeys(r["category"] for r in rows)) + ["ALL"]
    lines = [f"mode={result['mode']} turns={result['turns']} seconds={result['seconds']} critical={len(result['critical'])}",
             f"{'category':<14}{'lang':<5}" + "".join(f"{s:>10}" for s in scores) + f"{'total':>8}"]
    for c in cats:
        for lang in ("en", "zh", "all"):
            n = by[(c, lang)]
            lines.append(f"{c:<14}{lang:<5}" + "".join(f"{n[s]:>10}" for s in scores) + f"{sum(n.values()):>8}")
    for label, sel in (("main wording only", lambda r: r["variant"] == "main"), ("paraphrases only", lambda r: r["variant"] != "main")):
        n = Counter(r["score"] for r in rows if sel(r))
        lines.append(f"{label:<19}" + "".join(f"{n[s]:>10}" for s in scores) + f"{sum(n.values()):>8}")
    proposed = sum(1 for r in rows if r.get("awaiting_confirmation"))
    lines.append(f"turns that proposed a plan awaiting 'go ahead' (nothing executed): {proposed}")
    fx = Counter(k for r in rows for k in (r.get("side_effects") or {}))
    lines.append(f"turns with non-operation side effects: {dict(fx)}")
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("business", "demo"), default="business")
    ap.add_argument("--out", type=Path, help="write every turn (text, intent, reply, score) as JSON")
    ap.add_argument("--only", nargs="*", help="question ids")
    args = ap.parse_args()
    result = run(args.mode, set(args.only) if args.only else None)
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if result["critical"]:
        print("CRITICAL: a question executed or queued an operation, or changed the books:")
        for r in result["critical"]:
            print(f"  {r['id']} [{r['lang']}] {r['text']!r}: ops={r['operations']} store={r['store_changed']}")
    else:
        print("No question executed or queued an operation or changed the books.")
    refused = [r for r in result["rows"] if r.get("logged_refusal")]
    if refused:
        print(f"Questions that appended a REFUSED operation to the hash-chained log ({len(refused)}):")
        for r in refused:
            print(f"  {r['id']} [{r['lang']}] {r['text']!r}: {r['operations']}")
    print(summarise(result))
    for r in result["rows"]:
        if r["score"] == "WRONG":
            print(f"WRONG {r['id']} [{r['lang']}] {r['text']!r} -> {r['intent']}: {r['reason']}")


if __name__ == "__main__":
    main()
