import sys
sys.path.insert(0, r"C:\Users\ian\Documents\Projects\smu2sz\.claude\worktrees\cert-719c\services\api")
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.nl import reset_sessions
from tests.nl.conftest import build_app

for profile in ("hard_line", "cooperative"):
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset(); set_runtime(rt); reset_sessions()
    c = TestClient(build_app(), headers={"X-Owner-Token": "demo-owner-token"})
    s = rt.store.get_state()
    print([(f.id, f.kind.value, f.status.value, f.limit_fen, f.drawn_fen) for f in s.facilities])
    line = next(f for f in s.facilities if f.id == "FAC-LINE")
    # the owner draws the whole line through the API before the offer is evaluated
    r = c.post("/operations", json={"kind": "DRAW_FACILITY", "op_id": "own-draw-1", "idempotency_key": "own-draw-1",
                                    "mandate_version": rt.store.get_mandate().version, "requested_by": "OWNER", "day": rt.day,
                                    "facility_id": "FAC-LINE", "amount_fen": line.limit_fen - line.drawn_fen}).json()
    print("owner draw:", r.get("result", r).get("status") if isinstance(r, dict) else r, str(r)[:300])
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    ev = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    v = ev.get("verdict") or ev
    print("verdict:", v.get("outcome"), "counters:", [x.get("id") for x in v.get("counters", [])], "state_version", v.get("state_version"))
    body = {"buyer_profile": profile}
    if v.get("counters"):
        body.update(verdict_id=v.get("id"), counter_id=v["counters"][0]["id"], state_version=v.get("state_version"))
    resp = c.post(f"/negotiate/{oid}", json=body)
    n = resp.json()
    print(f"=== {profile} http={resp.status_code} outcome={n.get('outcome')} funding_status={n.get('funding_status')} legs={len(n.get('funding_legs') or [])}")
    p = n.get("plan") or {}
    print("  plan need_fen", p.get("need_fen"), "admissible", p.get("admissible"), "label", p.get("label"))
    print("  message_when:", n.get("message_when") or n)
