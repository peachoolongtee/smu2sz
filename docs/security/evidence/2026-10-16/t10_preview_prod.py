"""SETUP-7: with DEMO_MODE=0, the owner's valid /setup/preview is refused."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from app.mandate.fixture import demo_owner_public_key_hex
os.environ.update(DEMO_MODE="0", OWNER_TOKEN="prod-owner-xyz", AGENT_KEY="prod-agent-xyz", OWNER_PUBLIC_KEY_HEX=demo_owner_public_key_hex())
from common import draft
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.post("/setup/preview", headers={"X-Owner-Token": "prod-owner-xyz"}, json={"draft": draft()})
print("prod owner preview", r.status_code, str(r.json())[:160])
