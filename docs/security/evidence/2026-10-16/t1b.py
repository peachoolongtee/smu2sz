import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *
rt, c = make_client()
rt.reset("blank")
tok = OWNER["X-Owner-Token"]
for m, p, b in [("GET", "/setup/status", None), ("GET", "/setup/documents", None),
          ("POST", "/setup/documents", {"kind": "BUYER_CONTRACT", "text": "hello"}),
          ("POST", "/setup/preview", {"draft": draft()}),
          ("POST", "/setup/open", {"draft": draft(), "password": tok}),
          ("POST", "/demo/reset?scenario=blank", None)]:
    r = c.request(m, p, headers=OWNER, json=b)
    print("owner", m, p, r.status_code, str(r.json())[:260])
# demo token in DEMO_MODE=0
r = c.get("/setup/status", headers={"X-Owner-Token": "demo-owner-token"}); print("demo token", r.status_code)
