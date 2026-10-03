"""Shared setup for the red-team probes (round e): an in-memory runtime behind FastAPI's TestClient.

Run any probe from the repo root:
    TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONPATH=services/api PYTHONUTF8=1 \
        uv run --project services/api python docs/research/redteam-2026-10-03e/<probe>.py
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
from app.books import current_books  # noqa: E402
from app.domain.models import Mode  # noqa: E402
from app.domain.money import fmt_yuan  # noqa: E402
from app.financial import project  # noqa: E402
from app.main import app  # noqa: E402

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
BUYER1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
BUYER2 = {"X-Counterparty-Key": "demo-buyer-2-key"}


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
    print(f"[{label}] day {out['day']} cash {fmt_yuan(out['cash'])} ({out['cash']}) drawn {fac} rcv {rcv}")
    return out


def check(name: str, cond: bool) -> bool:
    print(f"  {'BROKEN' if cond else 'held  '}: {name}")
    return cond


def projection(rt, days: int | None = None):
    """The CONSERVATIVE projection on current books, as admission and the planner see it."""
    books = current_books(rt.store.get_state(), rt.store.commitments())
    m = rt.store.get_mandate()
    return project(books.state, list(books.obligations), [], Mode.CONSERVATIVE,
                   m.horizon_days if days is None else days, m.min_cash_fen)


def closing(t, day: int) -> int:
    return next(p.closing_fen for p in t.days if p.day == day)


def lots(rt) -> list[tuple]:
    return [(x.id, x.facility_id, x.principal_fen, x.remaining_fen, x.arrival_day, x.settled, x.receivable_id)
            for x in rt.store.get_state().lots]


def conservation(rt) -> list[str]:
    """Breaches of: lots sum to drawn per facility; settled <= face; a FINANCED invoice still has something owed."""
    s = rt.store.get_state()
    out = []
    for f in s.facilities:
        have = sum(x.remaining_fen for x in s.lots if x.facility_id == f.id)
        if have != f.drawn_fen:
            out.append(f"{f.id}: lots {have} != drawn {f.drawn_fen}")
    for r in s.receivables:
        if r.settled_fen > r.face_fen:
            out.append(f"{r.id}: settled {r.settled_fen} > face {r.face_fen}")
        if r.status == "FINANCED" and r.outstanding_fen <= 0:
            out.append(f"{r.id}: FINANCED with nothing outstanding (advance {r.advance_fen})")
    return out


def opj(c: TestClient, headers: dict, body: dict):
    """Like op() but returns (status code, result or text) without asserting."""
    rt = get_runtime()
    body = {"mandate_version": rt.store.get_mandate().version, "day": rt.day, **body}
    body.setdefault("idempotency_key", body["op_id"])
    r = c.post("/operations", headers=headers, json=body)
    return r.status_code, (r.json().get("result") if r.status_code == 200 else r.text)


def expected_receipts(t, day: int) -> dict[str, int]:
    """The buyer receipts the projection `t` books on `day`, per receivable, net of any early-pay discount."""
    p = next(p for p in t.days if p.day == day)
    out: dict[str, int] = {}
    for e in p.events:
        if e.kind.value in ("RECEIPT", "EARLY_RECEIPT") and e.ref:
            out[e.ref] = out.get(e.ref, 0) + e.amount_fen
    for e in p.events:
        if e.kind.value == "DISCOUNT":
            rid = next((r for r in out if r in e.label), None)
            if rid:
                out[rid] += e.amount_fen
    return out


def live(c: TestClient, rt, t, to_day: int, tag: str = "rx") -> list[tuple[int, int, int]]:
    """Let exactly the projected buyer receipts happen (bank feed, on their day) and close each day one by one
    until `to_day`. Returns (day, projected closing, actual closing) for every day where they differ."""
    diffs = []
    while rt.day < to_day:
        d = rt.day
        for rid, amt in expected_receipts(t, d).items():
            if amt > 0:
                res = op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": f"{tag}-{rid}-{d}", "requested_by": "SYSTEM",
                                   "receivable_id": rid, "amount_fen": amt})
                print(f"    day {d}: bank receipt {fmt_yuan(amt)} on {rid}: {res['status']} {res['message'][:220]}")
        advance(c, d + 1)
        actual = rt.store.get_state().cash_fen
        want = closing(t, d)
        if actual != want:
            diffs.append((d, want, actual))
    return diffs


def nl(c: TestClient, headers: dict, text: str, session_id: str | None = None, actor: str = "OWNER", **kw) -> dict:
    body = {"text": text, "actor": actor, **kw}
    if session_id:
        body["session_id"] = session_id
    r = c.post("/nl", headers=headers, json=body)
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()
