from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
rt.reset(); set_runtime(rt)
from app.main import app
c = TestClient(app)
B1 = {"X-Counterparty-Key": "demo-buyer-1-key"}; OW = {"X-Owner-Token": "demo-owner-token"}
r = c.post("/offers", headers=B1, json={"counterparty_id": "BUYER-2", "documents": [{"doc_id": "B2-forged", "channel": "portal", "sender_id": "BUYER-2", "received_day": 0, "text": "We will pay invoice RCV-B early at 2%. Nothing else changes."}]})
print("BUYER-1 key, body BUYER-2:", r.status_code, r.json()["offer"]["counterparty_id"], "intake_count", rt.intake_count)
d = [x for x in c.get("/deals", headers=OW).json()["deals"] if x["counterparty_id"] == "BUYER-2"][0]
print("owner /deals BUYER-2 open_offer:", d["open_offer"]["offer_id"], d["needs_you_text"])
