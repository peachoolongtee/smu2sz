import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *
rt, c = make_client()
rt.reset_demo("blank")
n = 20000
d = draft(); d["bills"] = [{"label": "B", "kind": "OTHER", "amount": "1", "next_date": "2026-10-15", "repeats": "MONTHLY"}] * n
raw = json.dumps({"draft": d})
t = time.time(); r = c.post("/setup/preview", headers={**OWNER, "Content-Type": "application/json"}, content=raw)
print(f"preview {n} bills body={len(raw)/1e6:.1f}MB -> {r.status_code} in {time.time()-t:.1f}s")
n = 3000
d = draft(); d["bills"] = [{"label": "B", "kind": "OTHER", "amount": "1", "next_date": "2026-10-15", "repeats": "MONTHLY"}] * n
t = time.time(); r = c.post("/setup/open", headers=OWNER, json={"draft": d, "password": "demo-owner-token"}); print(f"open {n} bills -> {r.status_code} in {time.time()-t:.1f}s flows={len(rt.store.get_state().flows)}")
for p in ("/home", "/ledger", "/setup/status"):
    t = time.time(); rr = c.get(p, headers=OWNER); print(p, rr.status_code, f"{time.time()-t:.1f}s")
