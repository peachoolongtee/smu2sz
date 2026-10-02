"""Shared setup for the red-team probes: an in-memory runtime behind FastAPI's TestClient.

Run any probe from the repo root:
    TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONPATH=services/api PYTHONUTF8=1 \
        uv run --project services/api python docs/research/redteam-2026-10-03/<probe>.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "memory")
os.environ.setdefault("LLM_MODE", "cache")
os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "services" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.runtime import get_runtime  # noqa: E402
from app.domain.money import fmt_yuan  # noqa: E402
from app.main import app  # noqa: E402

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
BUYER1 = {"X-Counterparty-Key": "demo-buyer-1-key"}


def fresh():
    rt = get_runtime()
    rt.reset()
    return rt, TestClient(app)


def op(c: TestClient, headers: dict, body: dict) -> dict:
    rt = get_runtime()
    body = {"mandate_version": rt.store.get_mandate().version, "day": rt.day, **body}
    body.setdefault("idempotency_key", body["op_id"])
    r = c.post("/operations", headers=headers, json=body)
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()["result"]


def advance(c: TestClient, to_day: int) -> dict:
    r = c.post("/clock/advance", json={"to_day": to_day}, headers=OWNER)
    assert r.status_code == 200, r.text
    return r.json()


def snap(rt, label: str) -> dict:
    s = rt.store.get_state()
    fac = {f.id: f.drawn_fen for f in s.facilities if f.drawn_fen}
    rcv = {r.id: (r.status, r.face_fen, r.settled_fen, r.advance_fen) for r in s.receivables}
    out = {"day": s.as_of_day, "cash": s.cash_fen, "drawn": fac, "receivables": rcv,
           "commitments": {c.id: c.status.value for c in rt.store.commitments()},
           "approvals": {a.id: str(getattr(a.status, "value", a.status)) for a in rt.store.approvals()},
           "log_len": len(rt.store.operations())}
    print(f"[{label}] day {out['day']} cash {fmt_yuan(out['cash'])} drawn {fac} rcv {rcv}")
    return out


def check(name: str, cond: bool) -> bool:
    print(f"  {'BROKEN' if cond else 'held  '}: {name}")
    return cond
