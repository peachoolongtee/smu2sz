"""Score FLOW's reading of contracts against an answer key. Read-only: it writes only under --out and --cache-dir.

    cd services/api
    uv run python scripts/eval_contracts.py DOC_OR_DIR... --key answer_key.json --out OUT_DIR \
        [--live] [--record] [--cache-dir DIR] [--deepseek-retries N]

Each document is read with `app.ingest.extract_text` and `app.compiler.service.compile_contract`; its
`ContractTerm`s are mapped to the answer key's field names wherever FLOW has an equivalent, written to
OUT_DIR/predictions.json in the key's shape (plus `_flow` notes) and scored field by field.

    offline (default)   the backend chain is [cache (if --cache-dir), rules grammar]; no key, no network.
    --live              LLM_MODE=live, LLM_PRIMARY=deepseek; the chain is [cache, DeepSeek, rules grammar]. Claude is left
                        out of the chain so that an Anthropic key in the environment is never used here. Keys are loaded
                        only through `app.config.load_dotenv` from the repo's .env (DATABASE_URL=memory first); this
                        script never reads that file itself and prints only whether a key is set.
    --record            with --live: write each live answer into --cache-dir (outside the repo), so a re-run with the
                        same --cache-dir and the same text and prompt costs nothing.

Mapping (FLOW term -> key field). Where FLOW states no term the prediction is null (or 0 for retention, [] for stages).
    CONTRACT_REFERENCE -> contract_no          SIGNED_DATE -> sign_date          PARTY_BUYER/PARTY_SUPPLIER -> buyer/seller.name
    PRICE (largest) -> amount_total            START_DATE/END_DATE -> performance.start_date/end_date
    MILESTONE.rate_bp -> payment_stages[].percent (a single PAYMENT_TERMS and no MILESTONE reads as one 100% stage)
    PAYMENT_TERMS -> payment_stages[].days_after_trigger / days_unit (business_days -> working) / trigger
                     (basis INVOICE/DELIVERY/ACCEPTANCE -> invoice/delivery/acceptance; other or no basis -> null)
    RETENTION.rate_bp -> retention_pct         LATE_INTEREST (rate with a per-day period) -> late_payment_interest daily_rate
Not expressible by FLOW (reported, never guessed): see NOT_EXPRESSIBLE.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOTENV = Path("C:/Users/ian/Documents/Projects/smu2sz/.env")

NOT_EXPRESSIBLE = {
    "payment_stages[].instrument": "payment instrument (bank transfer, acceptance bill, commercial bill): no ContractField",
    "payment_stages[].trigger = sign/quarter/audit/warranty_end/milestone":
        "PaymentBasis has only INVOICE, DELIVERY, ACCEPTANCE, MONTH_END",
    "payment_stages[] days per stage": "PAYMENT_TERMS is one value for the contract, not one per stage",
    "payment_stages[].requires_invoice": "no field",
    "late_payment_interest = lpr_multiple": "LATE_INTEREST holds a rate in bp, not a multiple of the LPR",
    "flags (GOV_TERM_OVER_60, GOV_TERM_31_60, NON_CASH_INSTRUMENT, NO_LATE_INTEREST_CLAUSE)":
        "Order 802 and instrument warnings are not computed",
    "performance.delivery_days_after_sign, place, acceptance_period_days, warranty_months, performance_bond, late_delivery_penalty":
        "no ContractField (DELIVERABLE and AMENDMENT are display-only text)",
}

TRIGGER_OF_BASIS = {"INVOICE": "invoice", "DELIVERY": "delivery", "ACCEPTANCE": "acceptance"}


def _norm(s: Any) -> str | None:
    return None if s is None else "".join(str(s).split())


# ---------------------------------------------------------------- mapping


def predict(compiled: Any, doc_id: str, filename: str) -> dict[str, Any]:
    by: dict[str, list[Any]] = {}
    for t in compiled.terms:
        by.setdefault(t.field.value, []).append(t)

    def first(name: str) -> Any:
        return by[name][0] if by.get(name) else None

    def text(name: str) -> str | None:
        t = first(name)
        return t.text if t is not None else None

    price = max(by.get("PRICE", []), key=lambda t: t.amount_fen or 0, default=None)
    milestones = by.get("MILESTONE", [])
    pay = by.get("PAYMENT_TERMS", [])
    stages: list[dict[str, Any]] = []
    for i, m in enumerate(milestones, 1):
        stages.append({"seq": i, "percent": (m.rate_bp or 0) / 100, "trigger_text": m.text})
    if not milestones and len(pay) == 1:
        stages.append({"seq": 1, "percent": 100.0, "trigger_text": None, "implied": True})
    pay_terms = [{"days_after_trigger": t.days, "days_unit": "working" if t.business_days else "calendar",
                  "trigger": TRIGGER_OF_BASIS.get(t.basis.value) if t.basis else None} for t in pay]
    for i, p in enumerate(pay_terms):
        if i < len(stages):
            stages[i].update(p)
        else:
            stages.append({"seq": len(stages) + 1, "percent": None, **p})
    ret = first("RETENTION")
    late = first("LATE_INTEREST")
    interest: dict[str, Any] = {"type": "not_specified"}
    if late is not None and late.rate_bp is not None:
        period = late.text or ""
        if any(w in period for w in ("日", "天", "day", "Day")):
            interest = {"type": "daily_rate", "rate_pct": late.rate_bp / 100}
        else:
            interest = {"type": "annual_rate", "rate_pct": late.rate_bp / 100}
    return {
        "id": doc_id, "file": filename,
        "contract_no": text("CONTRACT_REFERENCE"),
        "sign_date": first("SIGNED_DATE").date if first("SIGNED_DATE") else None,
        "buyer": {"name": text("PARTY_BUYER")},
        "seller": {"name": text("PARTY_SUPPLIER")},
        "amount_total": price.amount_fen / 100 if price is not None and price.amount_fen is not None else None,
        "performance": {"start_date": first("START_DATE").date if first("START_DATE") else None,
                        "end_date": first("END_DATE").date if first("END_DATE") else None},
        "payment_stages": stages,
        "retention_pct": (ret.rate_bp / 100 if ret is not None and ret.rate_bp is not None else 0),
        "late_payment_interest": interest,
        "_flow": {"compiler": compiled.compiler, "status": compiled.status.value, "chunks": compiled.chunks,
                  "terms": len(compiled.terms),
                  "abstentions": [f"{a.field}: {a.reason}" for a in compiled.abstentions]},
    }


# ---------------------------------------------------------------- scoring


def _multiset(items: list[Any]) -> Counter:
    """Items counted without regard to order; 30 and 30.0 are the same percent."""
    return Counter(json.dumps(round(i, 4) if isinstance(i, float) else i, ensure_ascii=False)
                   if not (isinstance(i, float) and i == int(i)) else str(int(i)) for i in items)


def _close(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 0.005
    return a == b


def _interest_equal(k: dict[str, Any], p: dict[str, Any]) -> bool:
    if k.get("type") != p.get("type"):
        return False
    if k["type"] == "daily_rate":
        return _close(k.get("rate_pct"), p.get("rate_pct"))
    return k["type"] == "not_specified"


def score(key: dict[str, Any], pred: dict[str, Any]) -> dict[str, tuple[int, int, int]]:
    """field -> (key items, matched items, extra predicted items). A scalar field is one item."""
    out: dict[str, tuple[int, int, int]] = {}

    def scalar(name: str, k: Any, p: Any, eq=_close) -> None:  # type: ignore[no-untyped-def]
        out[name] = (1, int(p is not None and eq(k, p)), int(p is not None and not eq(k, p)))

    scalar("contract_no", _norm(key["contract_no"]), _norm(pred["contract_no"]), lambda a, b: a == b)
    scalar("sign_date", key["sign_date"], pred["sign_date"])
    scalar("buyer.name", _norm(key["buyer"]["name"]), _norm(pred["buyer"]["name"]), lambda a, b: a == b)
    scalar("seller.name", _norm(key["seller"]["name"]), _norm(pred["seller"]["name"]), lambda a, b: a == b)
    scalar("amount_total", key["amount_total"], pred["amount_total"])
    scalar("performance.start_date", key["performance"]["start_date"], pred["performance"]["start_date"])
    scalar("performance.end_date", key["performance"]["end_date"], pred["performance"]["end_date"])
    out["retention_pct"] = (1, int(_close(key["retention_pct"], pred["retention_pct"])),
                            int(not _close(key["retention_pct"], pred["retention_pct"])))
    ki, pi = key["late_payment_interest"], pred["late_payment_interest"]
    ok = _interest_equal(ki, pi)
    out["late_payment_interest"] = (1, int(ok), int(not ok and pi.get("type") != "not_specified"))
    for name in ("percent", "days_after_trigger", "days_unit", "trigger"):
        kk = _multiset([s[name] for s in key["payment_stages"]])
        pp = _multiset([s[name] for s in pred["payment_stages"] if s.get(name) is not None])
        matched = sum((kk & pp).values())
        out[f"payment_stages[].{name}"] = (sum(kk.values()), matched, sum(pp.values()) - matched)
    return out


def table(rows: dict[str, dict[str, tuple[int, int, int]]]) -> str:
    fields = list(next(iter(rows.values())))
    ids = list(rows)
    head = "| field | " + " | ".join(ids) + " | matched/key | accuracy | extra |"
    lines = [head, "|" + "---|" * (len(ids) + 4)]
    for f in fields:
        cells = [f"{rows[i][f][1]}/{rows[i][f][0]}" for i in ids]
        k = sum(rows[i][f][0] for i in ids)
        m = sum(rows[i][f][1] for i in ids)
        x = sum(rows[i][f][2] for i in ids)
        lines.append(f"| {f} | " + " | ".join(cells) + f" | {m}/{k} | {m / k:.0%} | {x} |")
    k = sum(v[0] for r in rows.values() for v in r.values())
    m = sum(v[1] for r in rows.values() for v in r.values())
    lines.append(f"| ALL | " + " | ".join(str(sum(v[1] for v in rows[i].values())) + "/" + str(sum(v[0] for v in rows[i].values()))
                                          for i in ids) + f" | {m}/{k} | {m / k:.0%} | |")
    return "\n".join(lines)


# ---------------------------------------------------------------- reading


def _backends(args: argparse.Namespace) -> list[Any]:
    from app.compiler.base import BackendError
    from app.compiler.backends import DeepSeekBackend
    from app.compiler.cache import CacheBackend, write_entry
    from app.compiler.prompts import CONTRACT_PROMPT_VERSION
    from app.compiler.rules import RulesBackend

    chain: list[Any] = []
    cache = Path(args.cache_dir) if args.cache_dir else None
    if cache is not None:
        chain.append(CacheBackend(cache))
    if args.live:
        deepseek = DeepSeekBackend(retries=args.deepseek_retries)

        class Live:
            name = "deepseek"

            def extract_contract(self, chunk):  # type: ignore[no-untyped-def]
                try:
                    res = deepseek.extract_contract(chunk)
                except BackendError as e:
                    print(f"  deepseek: {e}", file=sys.stderr)
                    raise
                if args.record and cache is not None:
                    write_entry(cache, CONTRACT_PROMPT_VERSION, [chunk], res.extraction, res.model_id, chunk.doc_id)
                return res

        chain.append(Live())
    chain.append(RulesBackend())
    return chain


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="contract files or directories of them")
    ap.add_argument("--key", required=True, help="answer_key.json (a list of records with 'file')")
    ap.add_argument("--out", required=True, help="directory for predictions.json and report.md")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--cache-dir", default=None, help="recorded answers, outside the repo")
    ap.add_argument("--deepseek-retries", type=int, default=2, help="extra attempts after the first (default 2)")
    args = ap.parse_args()
    if args.record and not (args.live and args.cache_dir):
        ap.error("--record needs --live and --cache-dir")
    if args.cache_dir and ROOT.parent.parent in Path(args.cache_dir).resolve().parents:
        ap.error("--cache-dir must be outside the repo")

    os.environ["DATABASE_URL"] = "memory"
    if args.live:
        os.environ["LLM_MODE"] = "live"
        os.environ["LLM_PRIMARY"] = "deepseek"
        from app.config import load_dotenv

        load_dotenv(DOTENV)
        print("DEEPSEEK_API_KEY:", "set" if os.environ.get("DEEPSEEK_API_KEY") else "NOT set")
        if not os.environ.get("DEEPSEEK_API_KEY"):
            return 2

    from app.compiler import service
    from app.compiler.contract import contract_document
    from app.domain.models import DocumentKind
    from app.ingest import extract_text

    service._default_compiler = lambda: service.Compiler(_backends(args))  # type: ignore[assignment]
    keys = {r["file"]: r for r in json.loads(Path(args.key).read_text(encoding="utf-8"))}
    files: list[Path] = []
    for p in map(Path, args.paths):
        files += sorted(f for f in p.iterdir() if f.name in keys) if p.is_dir() else [p]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    preds, rows = [], {}
    for f in files:
        key = keys.get(f.name)
        if key is None:
            print(f"{f.name}: not in the answer key, skipped")
            continue
        text = extract_text(f.name, f.read_bytes())
        compiled = service.compile_contract(contract_document(text, DocumentKind.BUYER_CONTRACT, key["id"]))
        pred = predict(compiled, key["id"], f.name)
        preds.append(pred)
        rows[key["id"]] = score(key, pred)
        print(f"{key['id']}: compiler={compiled.compiler} status={compiled.status.value} terms={len(compiled.terms)}")
    if not rows:
        print("nothing scored")
        return 1
    (out_dir / "predictions.json").write_text(json.dumps(preds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = table(rows) + "\n\nNot expressible by FLOW (not scored):\n" + "\n".join(
        f"- {k}: {v}" for k, v in NOT_EXPRESSIBLE.items()) + "\n"
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    print()
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
