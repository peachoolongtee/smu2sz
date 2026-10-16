import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
rt, c = make_client()
from app.main import app
paths = sorted(p for p, ops in app.openapi()["paths"].items() if "get" in ops and "{" not in p)
def sweep(tag):
    bad = []
    for p in paths:
        if p.startswith("/demo") or p in ("/docs", "/redoc", "/openapi.json"): continue
        try:
            rr = c.get(p, headers=OWNER)
            if rr.status_code >= 500: bad.append((p, rr.status_code))
        except Exception as e:
            bad.append((p, repr(e)[:100]))
    print(tag, "GET routes", len(paths), "5xx:", bad)
rt.reset_demo("blank")
sweep("blank")
d = draft()
d["customers"] = [{"name": "Old", "contract": {"amount": "1,000", "every_days": 366, "terms_days": 365, "next_invoice_date": "9999-12-31"},
                   "invoices": [{"sent_on": "0001-01-01", "amount": "100", "terms_days": 365}]}]
d["loans"] = [{"label": "L", "owed": "1000", "repayment": "10", "every": "QUARTERLY", "next_payment_date": "9999-12-31"}]
r = c.post("/setup/open", headers=OWNER, json={"draft": d, "password": "demo-owner-token"}); print("extreme open", r.status_code)
sweep("extreme")
rr = c.post("/clock/advance", headers=OWNER, json={"days": 30}); print("advance", rr.status_code)
sweep("extreme+30")
