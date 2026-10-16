"""Dynamic authorization sweep: call every route as every role, in-process, memory store, all features on.

usage (from services/api): uv run python <this> <out.json>
Env decides DEMO_MODE. With DEMO_MODE=0 we set explicit non-demo credentials and pin the demo public key
(the fixture mandate is signed with it) so the runtime can start; demo values must then be REFUSED.
"""
import json
import os
import re
import sys

for f in ["TERMS_GUARD", "DEBT_DESK", "CAPEX", "BORROWER_FILE", "BUYER_NEGOTIATION", "SECURITY_SCENES", "ALERTS",
          "EXPECTED_PLANS", "ENVELOPE", "PRICE_CURVE", "COLLECTIONS_WORTH", "EXPOSURE", "CUSTOMER_ECONOMICS",
          "CONTRACTS", "PILOT_JOURNAL", "CAPEX_CONTRACTS"]:
    os.environ["FEATURE_" + f] = "1"
os.environ.update(TERMSLEDGER_NO_DOTENV="1", DATABASE_URL="memory", LLM_MODE="cache", SKIP_PERF_BENCH="1")
MODE = os.environ.get("SWEEP_MODE", "demo")  # demo | prod (DEMO_MODE=0) | unset (DEMO_MODE not set at all)
if MODE == "demo":
    os.environ["DEMO_MODE"] = "1"
elif MODE == "prod":
    os.environ["DEMO_MODE"] = "0"
else:
    os.environ.pop("DEMO_MODE", None)
DEMO = MODE == "demo"
if not DEMO:
    from app.mandate.fixture import demo_owner_public_key_hex
    os.environ.update(OWNER_TOKEN="prod-owner-xyz", AGENT_KEY="prod-agent-xyz", BANK_FEED_KEY="prod-bank-xyz",
                      COUNTERPARTY_KEYS="BUYER-1=prod-b1-xyz", OWNER_PUBLIC_KEY_HEX=demo_owner_public_key_hex())

from fastapi.testclient import TestClient  # noqa: E402

from app.api.runtime import set_runtime  # noqa: E402
from app.main import app  # noqa: E402

if DEMO:
    ROLES = {
        "anon": {},
        "bad_owner": {"X-Owner-Token": "nope"},
        "agent": {"X-Agent-Key": "demo-agent-key"},
        "bank": {"X-Bank-Feed-Key": "demo-bank-feed-key"},
        "buyer1": {"X-Counterparty-Key": "demo-buyer-1-key"},
        "owner": {"X-Owner-Token": "demo-owner-token"},
    }
else:
    ROLES = {
        "anon": {},
        "demo_owner": {"X-Owner-Token": "demo-owner-token"},
        "demo_agent": {"X-Agent-Key": "demo-agent-key"},
        "agent": {"X-Agent-Key": "prod-agent-xyz"},
        "bank": {"X-Bank-Feed-Key": "prod-bank-xyz"},
        "buyer1": {"X-Counterparty-Key": "prod-b1-xyz"},
        "owner": {"X-Owner-Token": "prod-owner-xyz"},
    }

routes = [(m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops]
routes += [("GET", "/docs"), ("GET", "/redoc"), ("GET", "/openapi.json")]


def fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "ZZ-NOPE", path)


out = []
for m, p in sorted(set(routes), key=lambda x: (x[1], x[0])):
    row = {"method": m, "path": p, "status": {}}
    for role, hdrs in ROLES.items():
        set_runtime(None)  # fresh books per call: no write from an earlier role can mask a later one
        c = TestClient(app, raise_server_exceptions=False)
        url = fill(p)
        if m == "GET":
            resp = c.get(url, headers=hdrs)
        else:
            resp = c.request(m, url, headers=hdrs, json={})
        code = resp.status_code
        detail = ""
        try:
            j = resp.json()
            d = j.get("detail") if isinstance(j, dict) else None
            if isinstance(d, dict):
                detail = d.get("code", "")
            elif isinstance(d, list):
                detail = "validation"
        except Exception:
            pass
        row["status"][role] = f"{code}{':' + detail if detail else ''}"
    out.append(row)

json.dump(out, open(sys.argv[1], "w"), indent=1)
w = max(len(f"{r['method']} {r['path']}") for r in out)
print(" " * w, "  ".join(f"{k:>14}" for k in ROLES))
for r in out:
    print(f"{r['method']} {r['path']}".ljust(w), "  ".join(f"{r['status'][k]:>14}"[:14] for k in ROLES))
