import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from app.persistence import SqlLedgerStore
db = os.path.join(os.path.dirname(__file__), "t2.sqlite")
if os.path.exists(db): os.remove(db)
store = SqlLedgerStore("sqlite:///" + db.replace("\\", "/"))
rt, c = make_client(store)
rt.reset_demo("blank")
AG = {"X-Agent-Key": "demo-agent-key"}
m = rt.store.get_mandate()
base = {"mandate_version": m.version, "requested_by": "AGENT", "day": 0}
r = c.post("/operations", headers=AG, json={**base, "kind": "REQUEST_OWNER_APPROVAL", "op_id": "a1", "idempotency_key": "a1", "subject": "Please approve X", "payload_op_id": "p1"})
print("agent approval", r.status_code, str(r.json())[:200])
r = c.post("/operations", headers=AG, json={**base, "kind": "CHANGE_MANDATE", "op_id": "a2", "idempotency_key": "a2", "new_version": 9})
print("agent change mandate", r.status_code, str(r.json())[:200])
c.get("/setup/status", headers={"X-Owner-Token": "bad"})  # security event
r = c.post("/clock/advance", headers=OWNER, json={"days": 20}); print("advance", r.status_code)
s = rt.store
print("BEFORE: scenario", s.get_state().scenario, "day", rt.day, "ops", [(o.seq, o.kind) for o in s.operations()],
      "approvals", len(s.approvals()) if hasattr(s, "approvals") else "?", "secevents", len(s.security_events()))
print("status", c.get("/setup/status", headers=OWNER).json())
r = c.post("/setup/open", headers=OWNER, json={"draft": draft(), "password": "demo-owner-token"})
print("open", r.status_code, str(r.json())[:200])
print("AFTER: scenario", s.get_state().scenario, "day", rt.day, "ops", [(o.seq, o.kind) for o in s.operations()],
      "approvals", len(s.approvals()) if hasattr(s, "approvals") else "?", "secevents", len(s.security_events()), "chain", s.verify_chain())
from app.mandate import verify_signature
from app.mandate.fixture import demo_owner_public_key_hex
mm = s.get_mandate(); print("mandate v", mm.version, "sig ok", verify_signature(mm, demo_owner_public_key_hex()) if True else None)
# second open
r = c.post("/setup/open", headers=OWNER, json={"draft": draft(), "password": "demo-owner-token"}); print("second open", r.status_code, r.json())
