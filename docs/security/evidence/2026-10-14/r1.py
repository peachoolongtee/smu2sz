import json, sys
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
rt.reset(); set_runtime(rt)
from app.main import app
c = TestClient(app)
AG = {"X-Agent-Key": "demo-agent-key"}
def nl(text, h=None, **kw):
    body = {"text": text, **kw}
    r = c.post("/nl", json=body, headers=h or {})
    return r.status_code, r.json()
st = rt.store.get_state()
print("STATE cash/reserve:", {k: getattr(st, k) for k in ("cash_fen","reserve_fen","min_cash_fen") if hasattr(st,k)})
print("fields:", list(st.model_dump().keys()))
m = rt.store.get_mandate(); print("mandate:", json.dumps(m.model_dump(mode="json"))[:800])
for q in ["show cash status", "What is our cash position and facility headroom?", "show alerts", "what changed today?",
          "explain", "what if BUYER-1 pays at 60 days?", "Fund the cash gap", "compare financing options",
          "how is the deal with BUYER-1?", "Evaluate EX01_PACKAGE", "negotiate with BUYER-1", "repay the credit line",
          "get an invoice paid early", "what is our floor?", "what are BUYER-2's payment terms?"]:
    sc, j = nl(q, AG)
    print("\n=== AGENT:", q, sc)
    if sc == 200:
        print("intent", j["intent"], "| reply:", j["reply"][:900])
        if j.get("verdict"): print("verdict keys:", list(j["verdict"].keys())[:40])
        if j.get("plan"): print("plan:", [ (p["kind"], p["description"][:200]) for p in j["plan"]][:6])
    else:
        print(j)
