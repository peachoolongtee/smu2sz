"""Record the Ask FLOW router's routes for a list of questions into app/nl/router/route_cache/ (ADR-0015).

    uv run python scripts/record_router_cache.py --questions evals/owner_questions/general.yaml --estimate
    uv run python scripts/record_router_cache.py --questions qs.yaml --fake --out /tmp/route_cache
    uv run python scripts/record_router_cache.py --questions qs.yaml --live --provider deepseek   # PAID: one call per question

Each question is redacted as the product redacts it (LLM_REDACT), the prompt is built exactly as `route.build_prompt` builds it
(the catalogue and the redacted question: nothing from the books), and the model's reply is validated by `route.parse_route`
before it is written. An invalid reply is reported and not recorded. A question already recorded for this prompt version is
skipped unless --force.

--fake records the scripted keyword model (`app.nl.router.fake`) for tests: no network, no key.
--live calls the provider. It needs the explicit flag AND the provider's key in the environment (ANTHROPIC_API_KEY or
DEEPSEEK_API_KEY); this script never reads .env. The owner pays for every call: run --estimate first.
--estimate prints the number of calls and an estimate of the tokens, and calls nothing.

Questions: a YAML file with `items: [{q|text, lang}]` (the general set), or `questions: [{text_en, text_zh, para_en, para_zh}]`
(the bank), or a text file with one question per line (language detected).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

API = Path(__file__).resolve().parents[1]
if str(API) not in sys.path:
    sys.path.insert(0, str(API))
os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")  # never .env: a live key must be given in the environment, on purpose

import yaml

from app.compiler.redaction import redact_text
from app.nl.lexicon import detect_lang
from app.nl.router import route as rt

OUTPUT_TOKENS_PER_CALL = 60  # a route is about 20 to 60 tokens of JSON


def load_questions(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
        out: list[tuple[str, str]] = []
        for it in data.get("items", []):
            q = it.get("q") or it.get("text")
            if q:
                out.append((str(q), it.get("lang") or detect_lang(str(q))))
        for it in data.get("questions", []):
            for lang in ("en", "zh"):
                for q in [it.get(f"text_{lang}"), *(it.get(f"para_{lang}") or [])]:
                    if q:
                        out.append((str(q), lang))
        return out
    return [(ln.strip(), detect_lang(ln.strip())) for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]


def est_tokens(s: str) -> int:
    """A rough count: about four ASCII characters a token, one token a CJK character."""
    ascii_n = sum(1 for c in s if ord(c) < 128)
    return ascii_n // 4 + (len(s) - ascii_n)


def sent_text(q: str) -> str:
    from app.config import get_settings

    return redact_text(q.strip())[0] if get_settings().llm_redact else q.strip()


def estimate(questions: list[tuple[str, str]]) -> dict[str, Any]:
    system = rt.system_prompt()
    sys_t = est_tokens(system)
    users = [est_tokens(rt.user_message(sent_text(q), lang)) for q, lang in questions]
    calls = len(questions)
    return {"calls": calls, "system_tokens_per_call": sys_t, "user_tokens_avg": round(sum(users) / max(1, calls), 1),
            "input_tokens_total": calls * sys_t + sum(users), "output_tokens_total": calls * OUTPUT_TOKENS_PER_CALL,
            "note": "the system prompt is identical on every call, so provider prompt caching bills most of it at the cached rate"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", type=Path, required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fake", action="store_true", help="the scripted keyword model; no network")
    mode.add_argument("--live", action="store_true", help="PAID: call the provider once per question")
    mode.add_argument("--estimate", action="store_true", help="count calls and tokens; call nothing")
    ap.add_argument("--provider", choices=("claude", "deepseek"), default="deepseek")
    ap.add_argument("--model", default=None, help="the provider model (default: CLAUDE_MODEL / DEEPSEEK_MODEL settings)")
    ap.add_argument("--out", type=Path, default=rt.CACHE_DIR)
    ap.add_argument("--force", action="store_true", help="record again a question already recorded")
    args = ap.parse_args(argv)

    questions = list(dict.fromkeys(load_questions(args.questions)))
    if args.estimate:
        print(json.dumps(estimate(questions), indent=2))
        return 0
    if args.fake:
        from app.nl.router.fake import fake_complete

        backend: Any = rt.CallableBackend("fake", "fake-router", fake_complete)
    else:
        key = "ANTHROPIC_API_KEY" if args.provider == "claude" else "DEEPSEEK_API_KEY"
        if not os.environ.get(key):
            print(f"refusing to record live: {key} is not set in the environment (this script never reads .env)", file=sys.stderr)
            return 2
        from app.config import get_settings

        s = get_settings()
        model = args.model or (s.claude_model if args.provider == "claude" else s.deepseek_model)
        complete = rt._claude_complete(model) if args.provider == "claude" else rt._deepseek_complete(model)
        backend = rt.CallableBackend(args.provider, model, complete)

    written = skipped = invalid = 0
    for q, lang in questions:
        sent = sent_text(q)
        prompt = rt.build_prompt(sent, lang)
        if (args.out / f"{prompt.key}.json").is_file() and not args.force:
            skipped += 1
            continue
        try:
            raw, model_id = backend.route(prompt)
            rt.parse_route(raw)  # the same validation as the product; an invalid reply is not recorded
        except (rt.RouterError, rt.Rejected) as e:
            invalid += 1
            print(f"not recorded ({type(e).__name__}: {str(e)[:60]}): {rt._q_hash(sent)}", file=sys.stderr)
            continue
        rt.write_cache_entry(sent, lang, json.loads(raw), model_id, args.out)
        written += 1
    print(f"recorded {written}, already recorded {skipped}, invalid {invalid} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
