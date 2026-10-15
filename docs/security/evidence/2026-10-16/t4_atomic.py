import os, sys, json, threading
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from app.persistence import SqlLedgerStore
db = os.path.join(os.path.dirname(__file__), "t4.sqlite")
if os.path.exists(db): os.remove(db)
rt, c = make_client(SqlLedgerStore("sqlite:///" + db.replace("\\", "/")))
rt.reset_demo("blank")
c.post("/clock/advance", headers=OWNER, json={"days": 3})
print("before ops", [o.kind for o in rt.store.operations()])
orig = rt.store.append_operation
def boom(op_id, kind, *a):
    if kind == "OPEN_BOOKS": raise RuntimeError("disk full /secret/path")
    return orig(op_id, kind, *a)
rt.store.append_operation = boom
r = c.post("/setup/open", headers=OWNER, json={"draft": draft(), "password": "demo-owner-token"})
print("open", r.status_code, r.json())
rt.store.append_operation = orig
print('mandate ok', rt.store.get_mandate().version)
print("after: scenario", rt.store.get_state().scenario, "rt.scenario", rt.scenario, "ops", [o.kind for o in rt.store.operations()], "day", rt.day)
# same-runtime thread race
res = []
def go(i):
    d = draft(); d["business"]["company_name"] = f"Co {i}"
    res.append(c.post("/setup/open", headers=OWNER, json={"draft": d, "password": "demo-owner-token"}).status_code)
ts = [threading.Thread(target=go, args=(i,)) for i in range(6)]
[t.start() for t in ts]; [t.join() for t in ts]
print("thread race statuses", sorted(res), "ops", [(o.kind, json.loads(o.payload_json).get("company_name")) for o in rt.store.operations()])
