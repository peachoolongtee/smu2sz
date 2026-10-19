import time, sys
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
rt.reset(); set_runtime(rt)
from app.main import app
c = TestClient(app)
for n in [100, 400, 1600]:
    txt = "We will pay early at 0.5%. " * n
    t0 = time.time(); r = c.post("/offers", json={"documents": [{"doc_id": f"X{n}", "channel": "email", "sender_id": "BUYER-1", "received_day": 0, "text": txt}]})
    print(n, len(txt), "chars:", r.status_code, round(time.time()-t0, 2), "s", len(r.content), "bytes back", flush=True)
for n in [50]:
    docs = [{"doc_id": f"D{n}-{i}", "channel": "email", "sender_id": "BUYER-1", "received_day": 0, "text": f"Note {i}."} for i in range(n)]
    t0 = time.time(); r = c.post("/offers", json={"documents": docs}); print(n, "docs:", r.status_code, round(time.time()-t0, 2), "s", flush=True)
print("intake count", rt.intake_count, "cap", rt.settings.intake_cap_per_day)
