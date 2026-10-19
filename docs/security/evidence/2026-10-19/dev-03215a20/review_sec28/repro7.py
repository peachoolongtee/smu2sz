import sys
sys.path.insert(0, r"C:\Users\ian\Documents\Projects\smu2sz\.claude\worktrees\cert-719c\services\api")
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.nl import reset_sessions
from tests.nl.conftest import build_app
for mode in ("business", None):
  for lang in ("en", "zh"):
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset(); set_runtime(rt); reset_sessions()
    c = TestClient(build_app(), headers={"X-Owner-Token": "demo-owner-token"})
    s = rt.store.get_state()
    caps = {"FAC-LINE": 5_000_000, "FAC-IF": 5_000_000, "FAC-EARLYPAY": 0}
    rt.store.put_state(s.model_copy(update={"facilities": [f.model_copy(update={"limit_fen": caps.get(f.id, f.limit_fen)}) for f in s.facilities]}))
    params = {"mode": mode} if mode else {}
    sid = f"inf-{mode}-{lang}"
    def say(text):
        return c.post("/nl", params=params, json={"session_id": sid, "actor": "OWNER", "text": text, "lang": lang, "buyer_profile": "BUYER-1-HARDLINE"}).json()
    a = say("Evaluate EX01")
    b = say("go ahead" if lang == "en" else "好，执行")
    print(f"=== CHAT infeasible hard_line mode={mode} lang={lang}")
    print("  first (tail):", a.get("reply", "")[-400:])
    print("  go-ahead reply:", b.get("reply", "").splitlines()[1:])
    print("  ops:", [(o['kind'], o['status']) for o in b.get("operations", [])])
