#!/usr/bin/env python3
"""EX01 worked example, recomputed in-process on the golden books (evidence pack, section 3). Read-only.

Runs POST /offers + /offers/{id}/evaluate for EX01_PACKAGE through FastAPI's TestClient on an in-memory runtime, then
GET /offers/{id}/picture, and writes the verdict, the trajectory figures and the picture to <out>/ex01.json.

  LLM_MODE=cache TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 \
    uv run --project services/api python scripts/analysis/ex01_reconcile.py --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
os.environ.setdefault("LLM_MODE", "cache")
os.environ.setdefault("TERMSLEDGER_NO_DOTENV", "1")
os.environ.setdefault("DEMO_MODE", "1")


def client():
    from fastapi.testclient import TestClient

    from app.api.runtime import Runtime, set_runtime
    from app.config import get_settings
    from app.mandate.fixture import demo_owner_public_key_hex
    from app.persistence import InMemoryLedgerStore

    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    return TestClient(app, headers={"X-Owner-Token": "demo-owner-token"})


def days_of(traj: dict) -> list[dict]:
    return traj.get("days") or traj.get("points") or []


def closing(d: dict) -> int:
    for k in ("closing_fen", "closing"):
        v = d.get(k)
        if isinstance(v, dict):
            return int(v.get("fen"))
        if v is not None:
            return int(v)
    raise KeyError(d.keys())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fixture", default="EX01_PACKAGE")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    api = client()
    offer = api.post("/offers", json={"fixture_id": a.fixture}).json()["offer"]
    oid = offer["offer_id"]
    r = api.post(f"/offers/{oid}/evaluate", json={"fixture_id": a.fixture})
    assert r.status_code == 200, r.text
    v = r.json()
    pic = api.get(f"/offers/{oid}/picture").json()
    base = api.get("/trajectory", params={"mode": "CONSERVATIVE"}).json()
    plan = api.post("/router/plan", json={}).json()
    doc = {"offer": offer, "evaluate": v, "picture": pic, "trajectory_today": base, "router_plan": plan}
    (out / f"{a.fixture}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    verdict = v.get("verdict", v)
    floor = 30000000
    for name, t in (("verdict.trajectory", verdict.get("trajectory") or v.get("trajectory")),
                    ("verdict.cured_trajectory", verdict.get("cured_trajectory") or v.get("cured_trajectory")),
                    ("today", base)):
        if not t:
            print(name, "missing"); continue
        ds = days_of(t)
        series = [(d.get("day"), closing(d)) for d in ds]
        below = [(dd, c) for dd, c in series if c < floor]
        low = min(series, key=lambda x: x[1])
        print(f"{name}: lowest {low[1]/100:,.2f} on day {low[0]}; days below floor {len(below)}; "
              f"first below {below[0] if below else None}; last below {below[-1] if below else None}")
        print("  closing on days 0,12,20,30,31,32,46,47,59,60,61,62:",
              {dd: c / 100 for dd, c in series if dd in (0, 12, 20, 30, 31, 32, 46, 47, 59, 60, 61, 62)})
    print("outcome", verdict.get("outcome"), "tier", verdict.get("required_tier"))
    for x in verdict.get("violations", []):
        print("VIOL", x.get("code"), "|", x.get("observed"), "|", x.get("limit"), "|", json.dumps(x.get("inputs"), ensure_ascii=False)[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
