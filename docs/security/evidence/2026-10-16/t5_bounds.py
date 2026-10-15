import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *
rt, c = make_client()
rt.reset_demo("blank")
def timed(path, body):
    raw = json.dumps(body); t = time.time()
    r = c.post(path, headers={**OWNER, "Content-Type": "application/json"}, content=raw)
    return r, time.time() - t, len(raw)
# 1) many monthly bills
for n in ():
    d = draft(); d["bills"] = [{"label": "B", "kind": "OTHER", "amount": "1", "next_date": "2026-10-15", "repeats": "MONTHLY"}] * n
    r, dt, sz = timed("/setup/preview", {"draft": d})
    print(f"preview bills={n} body={sz/1e6:.2f}MB status={r.status_code} ok={r.json().get('ok') if r.status_code==200 else r.text[:100]} t={dt:.1f}s")
# 2) many customers with daily recurring contracts
n = 0
d = draft(); d["customers"] = [{"name": f"C{i}", "contract": {"amount": "1", "every_days": 1, "terms_days": 0, "next_invoice_date": "2026-10-14"}} for i in range(n)]
r, dt, sz = timed("/setup/preview", {"draft": d}); print(f"preview daily contracts={n} body={sz/1e6:.2f}MB status={r.status_code} t={dt:.1f}s")
# 3) unbounded unused field
d = draft(); d["business"]["what_you_sell"] = "x" * 20_000_000
r, dt, sz = timed("/setup/preview", {"draft": d}); print(f"what_you_sell 20MB status={r.status_code} ok={r.json().get('ok')} t={dt:.1f}s")
d = draft(); d["business"]["cash"] = "9" * 5_000_000
r, dt, sz = timed("/setup/preview", {"draft": d}); print(f"cash 5M digits status={r.status_code} t={dt:.1f}s body={r.text[:150]}")
for v in ("9"*5000, "9"*4301, "0."+"0"*30000+"1"):
    d = draft(); d["business"]["cash"] = v
    r, dt, sz = timed("/setup/preview", {"draft": d}); print(f"cash len {len(v)} status={r.status_code} t={dt:.2f}s body={r.text[:150]}")
d = draft(); d["business"]["cash"] = int("9"*4000)
r, dt, sz = timed("/setup/preview", {"draft": d}); print(f"cash 4000-digit int status={r.status_code} t={dt:.1f}s")
# 4) extreme dates then open and read pages
d = draft()
d["customers"] = [{"name": "Old", "contract": {"amount": "1,000", "every_days": 366, "terms_days": 365, "next_invoice_date": "9999-12-31"},
                   "invoices": [{"sent_on": "0001-01-01", "amount": "100", "terms_days": 365}]}]
d["loans"] = [{"label": "L", "owed": "1000", "repayment": "10", "every": "QUARTERLY", "next_payment_date": "9999-12-31"}]
d["bills"].append({"label": "Far", "kind": "OTHER", "amount": "5", "next_date": "9999-12-01", "repeats": "MONTHLY", "until": "0001-01-01"})
r, dt, sz = timed("/setup/preview", {"draft": d}); print("extreme preview", r.status_code, r.json().get("ok"), [e["text"][:80] for e in r.json().get("errors", [])])
r = c.post("/setup/open", headers=OWNER, json={"draft": d, "password": "demo-owner-token"}); print("extreme open", r.status_code, str(r.json())[:120])
from app.main import app
bad = []
gets = sorted({rt_.path for rt_ in app.routes if "GET" in getattr(rt_, "methods", set()) and "{" not in rt_.path})
for p in gets:
    try:
        rr = c.get(p, headers=OWNER)
        if rr.status_code >= 500: bad.append((p, rr.status_code, rr.text[:80]))
    except Exception as e:
        bad.append((p, repr(e)[:80]))
print("GET routes", len(gets), "500s:", bad)
rr = c.post("/clock/advance", headers=OWNER, json={"days": 30}); print("advance", rr.status_code, rr.text[:100])
