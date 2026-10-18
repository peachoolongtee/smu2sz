import sys
sys.path.insert(0, r"C:\Users\ian\Documents\Projects\smu2sz\.claude\worktrees\cert-719c\services\api")
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.nl import reset_sessions
from tests.nl.conftest import build_app
for lang in ("en", "zh"):
  for profile in ("hard_line", "cooperative"):
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset(); set_runtime(rt); reset_sessions()
    c = TestClient(build_app(), headers={"X-Owner-Token": "demo-owner-token"})
    s = rt.store.get_state()  # books whose committed lines are smaller (FAC-LINE ¥50,000, FAC-IF ¥50,000), set before the offer is evaluated
    caps = {"FAC-LINE": 5_000_000, "FAC-IF": 5_000_000, "FAC-EARLYPAY": 0}
    rt.store.put_state(s.model_copy(update={"facilities": [f.model_copy(update={"limit_fen": caps.get(f.id, f.limit_fen)}) for f in s.facilities]}))
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    v = c.post(f"/offers/{oid}/evaluate?lang={lang}", json={"fixture_id": "EX01_PACKAGE"}).json()
    v = v.get("verdict") or v
    body = {"buyer_profile": profile}
    if v.get("counters"):
        body.update(verdict_id=v["id"], counter_id=v["counters"][0]["id"], state_version=v["state_version"])
    resp = c.post(f"/negotiate/{oid}?lang={lang}", json=body); n = resp.json()
    p = n.get("plan") or {}
    print(f"=== {profile} {lang} bound={bool(v.get('counters'))} http={resp.status_code} outcome={n.get('outcome')} funding_status={n.get('funding_status')} legs={len(n.get('funding_legs') or [])} need_fen={p.get('need_fen')} admissible={p.get('admissible')} label={p.get('label')}")
    print("  message:", n.get("message")); print("  message_when:", n.get("message_when") or str(n)[:400])
