"""The integrated demo path, in process: EX01 -> deal on Counter A -> the agreed early payment arrives on
day 2 -> clock to day 34 -> alerts and reconciliation. Prints what the owner would see. Nothing is written
outside memory. Run from the repo root:

    PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "memory")
os.environ.setdefault("LLM_MODE", "cache")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.runtime import get_runtime  # noqa: E402
from app.domain.money import bp, fmt_yuan, post  # noqa: E402
from app.main import app  # noqa: E402

OWNER = {"X-Owner-Token": "demo-owner-token"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def show_alerts(c: TestClient, title: str) -> list[dict]:
    body = c.get("/alerts", headers=OWNER).json()
    print(f"\n== {title} (day {body['day']}): {body['counts']}")
    for a in body["alerts"]:
        print(f"  [{a['severity']}] {a['id']}: {a['title']}")
        print(f"      {a['detail']}")
        for s in a["suggested"]:
            print(f"      -> {s['operation_kind']} {s.get('facility_id') or ''} {s.get('receivable_id') or ''} "
                  f"{fmt_yuan(s['amount_fen']) if s.get('amount_fen') else ''}")
    return body["alerts"]


def main() -> int:
    rt = get_runtime()
    rt.reset()
    c = TestClient(app)
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()
    verdict = v.get("verdict", v)
    print("verdict:", verdict.get("outcome"), "| counters:", [x["text"] for x in verdict.get("counters", [])])
    n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    print("negotiation:", n["outcome"])
    com = rt.store.get_commitment(n["commitment"]["id"])
    ob = com.obligations[0]
    face, agreed = ob.base.amount_fen, ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
    print(f"commitment {com.id}: {fmt_yuan(face)} of {ob.base.receivable_id} at {ob.rate_bp} bp on day "
          f"{ob.effective_day}; agreed receipt {fmt_yuan(agreed)}")
    critical = [a for a in show_alerts(c, "after the deal") if a["severity"] == "CRITICAL"]

    c.post("/clock/advance", json={"to_day": ob.effective_day}, headers=OWNER)
    r = c.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "demo-receipt-1", "idempotency_key": "demo-receipt-1",
        "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
        "receivable_id": ob.base.receivable_id, "amount_fen": agreed}).json()
    print("\nbank receipt:", r.get("result", r).get("status"), r.get("result", r).get("message", r))
    c.post("/clock/advance", json={"to_day": 30}, headers=OWNER)
    c.post("/clock/advance", json={"to_day": 34}, headers=OWNER)
    late = show_alerts(c, "buyer has not paid the residual")
    rec = c.get("/reconciliation", headers=OWNER).json()["reconciliation"]
    print("\nreconciliation: matched", rec["matched"], "flagged", rec["flagged"], "lapsed promises", rec["lapsed_promises"])
    for p in rec["promised"]:
        print("  promised:", p["status"], p["detail"])
    for o in rec["outstanding"]:
        print("  outstanding:", o["receivable_id"], o.get("face_display", o["face_fen"]), "due", o["due_day"],
              "past due" if o["past_due"] else "")
    cure = [a for a in late if a["kind"] == "RESERVE_BREACH_AHEAD" and a.get("committed_cure")]
    cured = False
    if cure:
        r = c.post(f"/alerts/{cure[0]['id']}/act", headers=OWNER)
        act = r.json()
        print(f"\n== act on {cure[0]['id']}: HTTP {r.status_code}")
        for res in act.get("results", []):
            print(f"  {res['kind']} {res['status']} (tier {res['tier']}, seq {res['seq']}): {res['message']}")
        cured = r.status_code == 200 and act["executed"] >= 1 and act["cured"]
        show_alerts(c, "after the cure")
    print(f"\nRESULT: critical alerts after the deal: {len(critical)}; breach alerts with a committed cure on day 34: "
          f"{len(cure)}; cure executed and alert cleared: {cured}")
    return 0 if not critical and cure and cured else 1


if __name__ == "__main__":
    raise SystemExit(main())
