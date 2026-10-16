import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *
rt, c = make_client()
rt.reset("blank")
creds = {"none": {}, "agent": {"X-Agent-Key": "demo-agent-key"}, "bank": {"X-Bank-Feed-Key": "demo-bank-feed-key"},
         "buyer": {"X-Counterparty-Key": "demo-buyer-1-key"}, "wrong-owner": {"X-Owner-Token": "x"},
         "agent-as-owner": {"X-Owner-Token": "demo-agent-key"}}
routes = [("GET", "/setup/status", None), ("GET", "/setup/documents", None),
          ("POST", "/setup/documents", {"kind": "BUYER_CONTRACT", "text": "hello"}),
          ("POST", "/setup/preview", {"draft": draft()}),
          ("POST", "/setup/open", {"draft": draft(), "password": "demo-owner-token"})]
print("DEMO_MODE", os.environ.get("DEMO_MODE"))
for name, h in creds.items():
    row = []
    for m, p, b in routes:
        r = c.request(m, p, headers=h, json=b)
        row.append(f"{m} {p}={r.status_code}")
    print(name, row)
# owner
for m, p, b in routes[:4]:
    r = c.request(m, p, headers=OWNER, json=b)
    print("owner", m, p, r.status_code, str(r.json())[:200])
print("state scenario after", rt.store.get_state().scenario)
