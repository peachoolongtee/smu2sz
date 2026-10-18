"""FLOW live-model demonstration (18 Oct 2026): a new Chinese buyer message and a new contract read by the LIVE model,
then FLOW's deterministic evaluation and the permission gate. Talks to a running API; never reads any key."""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path

BASE, LOG, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
OWNER = {"X-Owner-Token": "demo-owner-token"}
BUYER1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
HERE = Path(__file__).parent

def call(method, path, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(BASE + path, method=method, headers=h, data=json.dumps(body).encode() if body is not None else None)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b"null"), round(time.perf_counter() - t, 2)
    except urllib.error.HTTPError as e:
        try: d = json.loads(e.read() or b"null")
        except Exception: d = None
        return e.code, d, round(time.perf_counter() - t, 2)

def log_since(n):
    raw = b""
    for _ in range(50):
        try:
            raw = LOG.read_bytes() if LOG.exists() else b""
            break
        except PermissionError:
            time.sleep(0.1)
    return raw[n:].decode("utf-8", "replace"), len(raw)

def model_lines(text):
    keep = ("compiler.call", "compiler.cross_check", "ask.router", "model.redaction", "nl.classify")
    return [l.strip() for l in text.splitlines() if any(k in l for k in keep)]

health = call("GET", "/health")[1]
assert health and health.get("llm_mode") == "live", f"API is not in live mode: {health}"
out = {"date": time.strftime("%Y-%m-%d %H:%M:%S %z"), "base": BASE, "health": {k: health.get(k) for k in ("llm_mode",)},
       "provider": "DeepSeek (deepseek-flash via the OpenAI-compatible API), redaction on", "steps": []}
call("POST", "/demo/reset", {})
_, pos = log_since(0)

# 1. A new Chinese buyer message on Foshan's channel key, never seen before.
msg = "我们下个月起想把账期延长到60天，如果你们同意，这张发票我们可以提前10天付，给1%折扣。另外下个季度的订单量会增加，希望价格能优惠0.5%。"
doc = {"doc_id": "LIVE-DEMO-ZH-2", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0, "text": msg}
s, r, ms = call("POST", "/offers?lang=zh", {"counterparty_id": "BUYER-1", "documents": [doc]}, BUYER1)
lines, pos2 = log_since(pos)
offer = (r or {}).get("offer") or {}
step = {"step": "buyer message read by the live model", "status": s, "seconds": ms, "input": msg,
        "compiler": offer.get("compiler"), "prompt_version": offer.get("prompt_version"),
        "obligations": [{k: o.get(k) for k in ("type", "rate_bp", "days_delta", "target_terms_days", "base", "contingency", "spans", "unresolved")}
                        for o in offer.get("obligations") or []],
        "abstentions": [{k: a.get(k) for k in ("field", "reason", "reason_when")} for a in offer.get("abstentions") or []],
        "model_log": model_lines(lines)}
out["steps"].append(step); pos = pos2
if offer.get("offer_id"):
    s, v, ms = call("POST", f"/offers/{offer['offer_id']}/evaluate?lang=en", {}, OWNER)
    out["steps"].append({"step": "deterministic evaluation and the permission gate", "status": s, "seconds": ms,
                         "outcome": (v or {}).get("outcome"), "required_tier": (v or {}).get("required_tier"),
                         "summary": (v or {}).get("summary_when") or (v or {}).get("summary"),
                         "codes": sorted({x.get("code") for x in (v or {}).get("violations") or []}),
                         "counters": [{"label": c.get("label"), "text": c.get("text")} for c in (v or {}).get("counters") or []],
                         "accepted_alone": ((v or {}).get("autonomy") or {}).get("accepted_alone")})

# 2. A new synthetic contract for Dongguan, never seen before.
text = (HERE / "dongguan_framework_agreement.md").read_text(encoding="utf-8")
s, r, ms = call("POST", "/documents?lang=en", {"kind": "BUYER_CONTRACT", "counterparty_id": "BUYER-2", "text": text}, OWNER)
lines, pos2 = log_since(pos)
d = (r or {}).get("document") or {}
out["steps"].append({"step": "contract read by the live model", "status": s, "seconds": ms, "compiler": d.get("compiler"),
                     "reading_status": d.get("reading_status"), "can_confirm": d.get("can_confirm"),
                     "flags": [f.get("kind") for f in d.get("flags") or []],
                     "terms": [{k: t.get(k) for k in ("field", "value_display", "quote")} for t in d.get("terms") or []],
                     "model_log": model_lines(lines)})
pos = pos2

# 3. A question for the read-only router.
s, r, ms = call("POST", "/nl", {"actor": "OWNER", "text": "Which of my debts costs me the most, and what would early collection from Foshan save?", "lang": "en"}, OWNER)
lines, pos2 = log_since(pos)
out["steps"].append({"step": "owner question routed by the live model", "status": s, "seconds": ms,
                     "parse_source": (r or {}).get("parse_source"), "reply": (r or {}).get("reply"), "model_log": model_lines(lines)})

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "live_demo_2026-10-18.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
