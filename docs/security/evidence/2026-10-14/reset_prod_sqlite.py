"""Does /demo/reset or /demo/restore wipe a persistent (SQLite) store when DEMO_MODE=0?
Step 1 seeds a SQLite file under DEMO_MODE=1 (the only way to provision books here), then step 2 restarts with DEMO_MODE=0."""
import os, sys, json
db = sys.argv[1]; phase = sys.argv[2]
os.environ.update(TERMSLEDGER_NO_DOTENV="1", DATABASE_URL=f"sqlite:///{db}", LLM_MODE="cache")
if phase == "prod":
    from app.mandate.fixture import demo_owner_public_key_hex
    os.environ.update(DEMO_MODE="0", OWNER_TOKEN="prod-owner-xyz", AGENT_KEY="prod-agent-xyz", OWNER_PUBLIC_KEY_HEX=demo_owner_public_key_hex())
else:
    os.environ["DEMO_MODE"] = "1"
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app, raise_server_exceptions=False)
H = {"X-Owner-Token": "prod-owner-xyz" if phase == "prod" else "demo-owner-token"}
led = c.get("/ledger", headers=H).json()
n = lambda j: len(j.get("entries", j.get("operations", []))) if isinstance(j, dict) else None
print(phase, "ledger before:", n(led), "chain_valid", led.get("chain_valid"))
if phase == "prod":
    for path in ["/demo/reset", "/demo/restore", "/demo/reset?scenario=busy"]:
        r = c.post(path, headers=H, json={})
        print(path, r.status_code, json.dumps(r.json())[:200])
    led2 = c.get("/ledger", headers=H).json()
    print("ledger after:", n(led2), "chain_valid", led2.get("chain_valid"))
