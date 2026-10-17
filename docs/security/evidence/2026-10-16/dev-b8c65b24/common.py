import os, sys
sys.path.insert(0, os.getcwd())
from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime, get_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = os.environ.get("OWNER_TOKEN", "demo-owner-token")
AGENT = os.environ.get("AGENT_KEY", "demo-agent-key")

def fresh():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app
    return rt, TestClient(app, headers={"X-Owner-Token": OWNER}), app

def evaluate(api, fixture="EX02_EARLY_1_5"):
    oid = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
    return oid, api.post(f"/offers/{oid}/evaluate", json={"fixture_id": fixture}).json()

def message(api, oid, cid, lang="en"):
    r = api.get(f"/offers/{oid}/counters/{cid}/message", params={"lang": lang}); assert r.status_code == 200, r.text
    return r.json()

def offered(api, oid, v, m, lang="en"):
    return api.post(f"/offers/{oid}/counters/{m['counter_id']}/offered",
                    json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": m["message_hash"], "lang": lang})

def sent(api, fixture="EX02_EARLY_1_5", counter=0):
    oid, v = evaluate(api, fixture)
    m = message(api, oid, v["counters"][counter]["id"])
    r = offered(api, oid, v, m); assert r.status_code == 200, r.text
    return oid, v, m

def accepted(api, oid, v, m, rt):
    return api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                    json={"verdict_id": v["id"], "state_version": rt.store.get_state().state_version, "message_hash": m["message_hash"]})

def decision(api, oid, lang="en"):
    return api.get(f"/decisions/deal:{oid}", params={"lang": lang}).json()

def set_cash(rt, cash):
    st = rt.store.get_state()
    rt.store.put_state(st.model_copy(update={"cash_fen": cash, "state_version": st.state_version + 1}), expected_version=st.state_version)
    return st.cash_fen
