"""R-11 verification: what does an agent-key caller learn through POST /nl? Scans the WHOLE JSON response for protected figures.

Run from services/api with DEMO_MODE=1 DATABASE_URL=memory LLM_MODE=cache TERMSLEDGER_NO_DOTENV=1.
"""
import json
import re

from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
rt.reset()
set_runtime(rt)
from app.main import app  # noqa: E402

c = TestClient(app)
AG = {"X-Agent-Key": "demo-agent-key"}
OW = {"X-Owner-Token": "demo-owner-token"}

st = rt.store.get_state()
m = rt.store.get_mandate()


def yuan_forms(fen: int) -> set[str]:
    y = fen // 100
    out = {f"{y:,}", f"¥{y:,}", f"{y}", f"{y / 10000:g}万"}
    if y >= 1000:
        out.add(f"{y // 1000}k")
    return {s for s in out if len(s.replace(",", "")) >= 4}  # skip tiny numbers that match everywhere


PROTECTED: dict[str, set[str]] = {
    "cash": yuan_forms(st.cash_fen),
    "reserve floor": yuan_forms(getattr(m, "min_cash_reserve_fen", 0) or getattr(st, "min_cash_fen", 0) or 30_000_000),
    "shortfall 405,000": yuan_forms(40_500_000),
    "gap 255,000": yuan_forms(25_500_000),
    "line headroom 150,000": yuan_forms(15_000_000),
    "concession cap 5,000": {"5,000.00", "¥5,000"},
    "break-even 0.88%": {"0.88%", "0.8832", "88 bp", "88bp"},
    "counter cap 0.85%": {"0.85%", "85 bp", "85bp"},
    "min DSCR 1.25x": {"1.25x", "1.25×", "1.25 x"},
    "max leverage 2.5x": {"2.50x", "2.5x", "2.50×", "2.5×"},
    "max APR 15%": {"15.00%", "1500 bp"},
}

QUESTIONS = ["show cash status", "What is our cash position and facility headroom?", "show alerts", "what changed today?",
             "explain", "explain the verdict", "what if BUYER-1 pays at 60 days?", "Fund the cash gap", "fund the gap now",
             "compare financing options", "how is the deal with BUYER-1?", "Evaluate EX01_PACKAGE", "negotiate with BUYER-1",
             "repay the credit line", "get an invoice paid early", "accelerate RCV-A", "what is our floor?",
             "what are BUYER-2's payment terms?", "show ratios", "what is the break-even discount?", "draw ¥10,000 on the credit line",
             "is it safe to draw ¥100,000 on the credit line?", "现金状况", "我们的最低现金储备是多少？"]


def scan(blob: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for label, forms in PROTECTED.items():
        found = sorted(f for f in forms if f in blob)
        if found:
            hits[label] = found
    return hits


total = 0
for q in QUESTIONS:
    r = c.post("/nl", json={"text": q}, headers=AG)
    blob = json.dumps(r.json(), ensure_ascii=False)
    hits = scan(blob)
    keys = sorted(r.json().keys()) if r.status_code == 200 else r.json()
    total += bool(hits)
    reply = (r.json().get("reply") or "")[:160].replace("\n", " | ") if r.status_code == 200 else ""
    print(f"AGENT {r.status_code} {q!r}: hits={hits or 'none'} keys={keys}\n    reply: {reply}")
print("\nAGENT responses with protected figures:", total, "of", len(QUESTIONS))

# control: the owner still sees them
r = c.post("/nl", json={"text": "show cash status"}, headers=OW)
print("OWNER control 'show cash status' hits:", scan(json.dumps(r.json(), ensure_ascii=False)))
