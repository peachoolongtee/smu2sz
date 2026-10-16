import os, sys, json, threading, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *
import app.api.setup as S
rt, c = make_client()
rt.reset_demo("blank")
text = open(os.path.join(os.getcwd(), "..", "..", "fixtures", "contracts", os.listdir(os.path.join(os.getcwd(), "..", "..", "fixtures", "contracts"))[0]), encoding="utf-8").read() if os.path.isdir(os.path.join(os.getcwd(), "..", "..", "fixtures", "contracts")) else "Buyer: Foshan Home Retail. Price 420,000 per invoice. Invoice every 30 days. Payment within 45 days."
codes = []
def go(i):
    r = c.post("/setup/documents", headers=OWNER, json={"kind": "BUYER_CONTRACT", "text": text + f"\nRef {i} " + "padding " * 20000})
    codes.append(r.status_code)
ts = [threading.Thread(target=go, args=(i,)) for i in range(40)]
t = time.time(); [x.start() for x in ts]; [x.join() for x in ts]
print("statuses", sorted(codes), "held", len(S._setup_docs), "ids", sorted(S._setup_docs)[:3], f"{time.time()-t:.1f}s")
# stale docs survive a reset
c.post("/demo/reset?scenario=golden_sme", headers=OWNER); c.post("/demo/reset?scenario=blank", headers=OWNER)
print("after two resets held", len(S._setup_docs))
