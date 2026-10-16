import os, sys, json, threading
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from app.persistence import SqlLedgerStore
from app.api.runtime import Runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
import app.api.setup as S
from starlette.requests import Request
db = os.path.join(os.path.dirname(__file__), "t3.sqlite")
if os.path.exists(db): os.remove(db)
url = "sqlite:///" + db.replace("\\", "/")
rtA = Runtime(settings=get_settings(), store=SqlLedgerStore(url), owner_key_hex=demo_owner_public_key_hex())
rtA.reset_demo("blank")
rtB = Runtime(settings=get_settings(), store=SqlLedgerStore(url), owner_key_hex=demo_owner_public_key_hex())
rtB.hydrate()
local = threading.local()
S.get_runtime = lambda: local.rt
b_at_reset, a_done = threading.Event(), threading.Event()
orig = rtB.store.reset
def slow_reset(*a, **k):
    b_at_reset.set(); a_done.wait(10); return orig(*a, **k)
rtB.store.reset = slow_reset
req = Request({"type": "http", "method": "POST", "path": "/setup/open", "headers": [], "client": ("t", 1)})
res = {}
def run(name, rt, company):
    local.rt = rt
    d = draft(); d["business"]["company_name"] = company
    try:
        res[name] = S.setup_open(S.OpenIn.model_validate({"draft": d, "password": "demo-owner-token"}), req)
    except Exception as e:
        res[name] = repr(e)[:200]
tb = threading.Thread(target=run, args=("B", rtB, "Company B")); tb.start()
b_at_reset.wait(10)
run("A", rtA, "Company A"); a_done.set(); tb.join()
print("A:", str(res["A"])[:160]); print("B:", str(res["B"])[:160])
st = SqlLedgerStore(url)
print("final ops", [(o.seq, o.kind, json.loads(o.payload_json).get("company_name")) for o in st.operations()], "chain", st.verify_chain())
