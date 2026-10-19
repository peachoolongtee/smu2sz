import sys
sys.path.insert(0, r"C:\Users\ian\Documents\Projects\smu2sz\.claude\worktrees\cert-719c\services\api")
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.nl import reset_sessions
from app.api.funding_report import funding_status
from tests.nl.conftest import build_app
print("funding_status([]) =", funding_status([]))

for lang in ("en", "zh"):
  for profile in ("hard_line", "cooperative"):
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset(); set_runtime(rt); reset_sessions()
    c = TestClient(build_app(), headers={"X-Owner-Token": "demo-owner-token"})
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    # the books lose their funding headroom after the evaluation (another user drew the lines): no admissible plan
    s = rt.store.get_state()
    s2 = s.model_copy(update={"facilities": [f.model_copy(update={"limit_fen": f.drawn_fen}) for f in s.facilities]})
    rt.store.put_state(s2)
    n = c.post(f"/negotiate/{oid}?lang={lang}", json={"buyer_profile": profile}).json()
    print(f"\n=== {profile} {lang}: outcome={n.get('outcome')} funding_status={n.get('funding_status')} legs={n.get('funding_legs')}")
    p = n.get("plan") or {}
    print("  plan: need_fen=", p.get("need_fen"), "admissible=", p.get("admissible"), "actions=", len(p.get("actions") or []), "label=", p.get("label"))
    print("  message:", n.get("message")); print("  message_when:", n.get("message_when"))
    print("  execution:", (n.get("execution") or {}).get("summary_text"))
