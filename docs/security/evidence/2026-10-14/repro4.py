"""Demo routes vs DEMO_MODE, memory vs sqlite."""
import os, sys, tempfile
mode, kind = sys.argv[1], sys.argv[2]
os.environ["DEMO_MODE"] = mode
os.environ["OWNER_TOKEN"] = "real-owner"; os.environ["AGENT_KEY"] = "real-agent"
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime, _seed
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore, SqlLedgerStore
OWNER = {"X-Owner-Token": "real-owner"}
if kind == "sql":
    d = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(__file__)))
    store = SqlLedgerStore(f"sqlite:///{d}/l.db")
else:
    store = InMemoryLedgerStore()
_seed(store, "golden_sme")
rt = Runtime(settings=get_settings(), store=store, owner_key_hex=demo_owner_public_key_hex()); rt.hydrate()
set_runtime(rt)
from app.main import app
c = TestClient(app)
c.post("/clock/advance", headers=OWNER, json={"days": 3})
c.post("/approvals/APR-NOPE", headers=OWNER, json={"decision": "APPROVE"})  # a security event
print(f"[DEMO_MODE={mode} store={kind}] before: ops", len(store.operations()), "sec", len(store.security_events()), "day", rt.day)
for path in ("/demo/reset", "/demo/restore", "/demo/bank-receipt"):
    r = c.post(path, headers=OWNER)
    print(" ", path, r.status_code, (r.json().get("detail") or {}).get("code") if r.status_code != 200 else "ok")
print("  after: ops", len(store.operations()), "sec", len(store.security_events()), "day", rt.day, "chain_valid", store.verify_chain())
