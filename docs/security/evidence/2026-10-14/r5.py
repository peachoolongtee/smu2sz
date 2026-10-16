import time
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
rt.reset(); set_runtime(rt)
from app.main import app
c = TestClient(app)
txt = ("We will pay early at 0.5%. " * 200)[:4000]
t0 = time.time(); r = c.post("/nl", json={"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": txt}); print("/nl 4000 chars anon:", r.status_code, round(time.time()-t0, 2), "s (held under rt.lock)", flush=True)
docs = [{"doc_id": f"D-{i}", "channel": "email", "sender_id": "BUYER-1", "received_day": 0, "text": f"We pay early at 0.{i%9+1}%."} for i in range(60)]
t0 = time.time(); r = c.post("/offers", json={"documents": docs}); print("60 docs:", r.status_code, round(time.time()-t0, 2), "s", flush=True)
# cap exhaustion
codes = {}
for i in range(205):
    r = c.post("/nl", json={"actor": "COUNTERPARTY", "text": f"hello {i}"}); codes[r.status_code] = codes.get(r.status_code, 0) + 1
print("anon /nl x205:", codes, flush=True)
r = c.post("/offers", json={"documents": [{"doc_id": "Z", "channel": "email", "sender_id": "BUYER-2", "received_day": 0, "text": "legit buyer offer 0.5%"}]})
print("a different anonymous sender after the cap:", r.status_code, r.json(), flush=True)
r = c.post("/nl", json={"actor": "COUNTERPARTY", "text": "hello"}, headers={"X-Agent-Key": "demo-agent-key"})
print("agent-key COUNTERPARTY (cap bypass, body cp id honoured):", r.status_code, flush=True)
