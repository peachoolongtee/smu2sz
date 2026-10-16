"""R-10 verification: the keyed-buyer daily budget across /offers and /nl, and what one message still reveals."""
import json

from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
rt.reset()
set_runtime(rt)
from app.main import app  # noqa: E402

c = TestClient(app)
OW = {"X-Owner-Token": "demo-owner-token"}
B1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
B2 = {"X-Counterparty-Key": "demo-buyer-2-key"}


def nl(h, text):
    r = c.post("/nl", json={"actor": "COUNTERPARTY", "text": text}, headers=h)
    return r.status_code, (r.json().get("reply") or r.json().get("detail")) if r.headers.get("content-type", "").startswith("application/json") else r.text


def offer(h, i):
    r = c.post("/offers", headers=h, json={"documents": [{"doc_id": f"B1-M{i}", "channel": "email", "sender_id": "BUYER-1",
                                                          "received_day": rt.day, "text": "We can pay RCV-A early at 0.5%."}]})
    return r.status_code, r.json().get("detail") if r.status_code != 200 else "ok"


print("--- one keyed message: what does it reveal?")
for rate in ["0.5", "0.86"]:
    print(rate, nl(B1, f"We can pay this one early at {rate}%. Nothing else changes."))
print("--- spend the rest of BUYER-1's budget across both routes")
for i in range(5):
    print("offers" if i % 2 == 0 else "nl", offer(B1, i) if i % 2 == 0 else nl(B1, f"We can pay early at 0.{60 + i}%."))
print("--- BUYER-2 is unaffected:", nl(B2, "We can pay early at 0.5%.")[0])
ev = [e for e in rt.store.security_events() if e.id.startswith("SEC-BUDGET")]
print("SEC-BUDGET events:", [(e.id, e.counterparty_id, e.day) for e in ev])
print("--- keyless message naming BUYER-1 after the budget (anonymous path, proposal only):",
      c.post("/nl", json={"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": "We can pay early at 0.86%."}).json().get("reply", "")[:120])
print("--- owner advances one day; budget resets?")
print("advance", c.post("/clock/advance", headers=OW, json={"days": 1}).status_code, "->", nl(B1, "We can pay early at 0.5%.")[0])
print("approvals queued by buyer probes:", [(a.id, a.status.value) for a in rt.store.approvals()])
