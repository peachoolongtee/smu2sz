"""Approvals are outside the chain and unguarded: flip a REJECTED approval back to PENDING, then approve it."""
import os, sys, json, sqlite3, pathlib
SCR = pathlib.Path(sys.argv[1])
for p in SCR.glob("flip.db*"):
    p.unlink()
DB = SCR / "flip.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"; os.environ["DEMO_MODE"] = "1"
import logging; logging.disable(logging.CRITICAL)
from fastapi.testclient import TestClient
from app.main import app
from app.api.runtime import get_runtime
OWNER = {"X-Owner-Token": "demo-owner-token"}
c = TestClient(app)
print("reset busy", c.post("/demo/reset", params={"scenario": "busy"}, headers=OWNER).status_code)
rt = get_runtime()
a = rt.store.approvals()[0]
print("approval", a.id, a.kind, a.status.value)
r = c.post(f"/approvals/{a.id}", json={"decision": "REJECT"}, headers=OWNER).json()
print("owner REJECT ->", r.get("result", r).get("status") if isinstance(r.get("result", r), dict) else r)
con = sqlite3.connect(DB)
con.execute("update approvals set status='PENDING', decided_by=NULL, decided_day=NULL where id=?", (a.id,)); con.commit(); con.close()
print("after raw UPDATE:", rt.store.get_approval(a.id).status.value)
r = c.post(f"/approvals/{a.id}", json={"decision": "APPROVE"}, headers=OWNER).json()
res = r.get("result", r)
print("owner APPROVE ->", res.get("status") if isinstance(res, dict) else r)
print("log:", [(o.seq, o.kind, json.loads(o.result_json)["status"], json.loads(o.result_json).get("approval_id")) for o in rt.store.operations()])
print("chain_valid:", c.get("/ledger", headers=OWNER).json()["chain_valid"])
