"""Route sweep against a deployed demo over HTTPS, through its password gate: every route of the app's own route table, called as
every caller of the demo (anonymous, a wrong owner token, the agent key, the bank-feed key, a buyer key, the owner token), with the
placeholder ids and empty bodies of authz_sweep_v3.py, so the output has the same shape and sweep_policy.py checks it.

Unlike the in-process sweep, the deployment's books are shared: one caller's write can change what a later call sees. That does not
weaken the policy check (a refused caller must be refused whatever the state); it can change the owner's answers. Run POST /demo/reset
afterwards.

usage (from services/api): DEMO_GATE=<path to .credentials: url=, user=, password=> uv run python <this> <out.json>
Prints no credential."""
import json
import os
import re
import sys
import time

import httpx

os.environ.update(TERMSLEDGER_NO_DOTENV="1", DATABASE_URL="memory", LLM_MODE="cache", DEMO_MODE="1")
for f in ["TERMS_GUARD", "DEBT_DESK", "CAPEX", "BORROWER_FILE", "BUYER_NEGOTIATION", "SECURITY_SCENES", "ALERTS",
          "EXPECTED_PLANS", "ENVELOPE", "PRICE_CURVE", "COLLECTIONS_WORTH", "EXPOSURE", "CUSTOMER_ECONOMICS",
          "CONTRACTS", "PILOT_JOURNAL", "CAPEX_CONTRACTS"]:
    os.environ["FEATURE_" + f] = "1"
from app.main import app  # noqa: E402  (the route table only; nothing is served locally)

cred = dict(line.split("=", 1) for line in open(os.environ["DEMO_GATE"], encoding="utf-8").read().splitlines() if "=" in line)
BASE = cred["url"].rstrip("/") + "/api"
ROLES = {
    "anon": {},
    "bad_owner": {"X-Owner-Token": "nope"},
    "agent": {"X-Agent-Key": "demo-agent-key"},
    "bank": {"X-Bank-Feed-Key": "demo-bank-feed-key"},
    "buyer1": {"X-Counterparty-Key": "demo-buyer-1-key"},
    "owner": {"X-Owner-Token": "demo-owner-token"},
}
routes = [(m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops]
routes += [("GET", "/docs"), ("GET", "/redoc"), ("GET", "/openapi.json")]


def fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "ZZ-NOPE", path)


client = httpx.Client(timeout=120.0, auth=(cred["user"], cred["password"]))
out, n429 = [], 0
for m, p in sorted(set(routes), key=lambda x: (x[1], x[0])):
    row = {"method": m, "path": p, "status": {}}
    for role, hdrs in ROLES.items():
        for attempt in range(4):
            resp = client.get(BASE + fill(p), headers=hdrs) if m == "GET" else client.request(m, BASE + fill(p), headers=hdrs, json={})
            if resp.status_code != 429:
                break
            n429 += 1
            time.sleep(15)
        code, detail = resp.status_code, ""
        try:
            j = resp.json()
            d = j.get("detail") if isinstance(j, dict) else None
            detail = d.get("code", "") if isinstance(d, dict) else ("validation" if isinstance(d, list) else "")
        except Exception:
            pass
        row["status"][role] = f"{code}{':' + detail if detail else ''}"
        time.sleep(0.12)
    out.append(row)

json.dump(out, open(sys.argv[1], "w"), indent=1)
w = max(len(f"{r['method']} {r['path']}") for r in out)
print(f"target: the judges' demo through its password gate; {len(out)} routes x {len(ROLES)} callers; 429 retries: {n429}")
print(" " * w, "  ".join(f"{k:>14}" for k in ROLES))
for r in out:
    print(f"{r['method']} {r['path']}".ljust(w), "  ".join(f"{r['status'][k]:>14}"[:14] for k in ROLES))
