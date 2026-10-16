"""SEC-08 on PostgreSQL: do the append-only triggers hold, can the reset setting bypass them, and can an approval row be flipped?

usage (from services/api): python pg_guard_check.py <file holding the server URL ending in /postgres>
Uses its own database termsledger_sectest2 (created empty, dropped and recreated each run). Never prints the URL.
"""
import json
import os
import sys

from sqlalchemy import create_engine, text

base = open(sys.argv[1], encoding="ascii").read().strip()
url = base.rsplit("/", 1)[0] + "/termsledger_sectest2"
admin = create_engine(base, isolation_level="AUTOCOMMIT")
with admin.connect() as c:
    c.execute(text("DROP DATABASE IF EXISTS termsledger_sectest2"))
    c.execute(text("CREATE DATABASE termsledger_sectest2"))
admin.dispose()

os.environ.update(DATABASE_URL=url, DEMO_MODE="1", TERMSLEDGER_NO_DOTENV="1", LLM_MODE="cache")
from fastapi.testclient import TestClient  # noqa: E402

from app.api.runtime import get_runtime  # noqa: E402
from app.main import app  # noqa: E402

OWNER = {"X-Owner-Token": "demo-owner-token"}
c = TestClient(app)
print("reset busy:", c.post("/demo/reset", params={"scenario": "busy"}, headers=OWNER).status_code)
rt = get_runtime()
print("ops after seed:", len(rt.store.operations()), "| chain_valid:", c.get("/ledger", headers=OWNER).json()["chain_valid"])

eng = create_engine(url)


def attempt(label: str, *sql: str, rollback: bool = True) -> None:
    with eng.connect() as conn:
        tx = conn.begin()
        try:
            res = None
            for q in sql:
                res = conn.execute(text(q))
            n = res.rowcount if res is not None else None
            print(f"  {label}: SUCCEEDED (rows {n})" + (" -> rolled back" if rollback else " -> committed"))
            tx.rollback() if rollback else tx.commit()
        except Exception as e:  # noqa: BLE001
            tx.rollback()
            print(f"  {label}: REFUSED ({type(e).__name__}: {str(e).splitlines()[0][:110]})")


with eng.connect() as conn:
    trig = conn.execute(text("select tgrelid::regclass::text, tgname from pg_trigger where not tgisinternal order by 1, 2")).fetchall()
    print("triggers:", [f"{t}.{n}" for t, n in trig])
    print("connected role is table owner:", conn.execute(text("select tableowner = current_user from pg_tables where tablename='operations'")).scalar())

print("1. direct tampering with the log")
attempt("DELETE FROM operations", "DELETE FROM operations WHERE seq = (SELECT max(seq) FROM operations)")
attempt("UPDATE operations", "UPDATE operations SET result_json = result_json WHERE seq = 1")
attempt("TRUNCATE operations", "TRUNCATE operations")
attempt("DELETE FROM used_nonces", "DELETE FROM used_nonces")
print("2. the reset setting, from an ordinary session (SEC-08 suspected bypass)")
attempt("SET LOCAL termsledger.allow_reset='on'; DELETE tail", "SET LOCAL termsledger.allow_reset = 'on'",
        "DELETE FROM operations WHERE seq = (SELECT max(seq) FROM operations)")
print("3. tables outside the chain")
attempt("DELETE FROM security_events", "DELETE FROM security_events")
attempt("UPDATE approvals", "UPDATE approvals SET status = status")

print("4. approval flip (rejected -> pending -> approved), committed on this throwaway database")
a = next((x for x in rt.store.approvals() if x.status.value == "PENDING"), None)
if a is None:
    print("  no pending approval in the seed; skipped")
else:
    r = c.post(f"/approvals/{a.id}", json={"decision": "REJECT"}, headers=OWNER).json()["result"]
    print("  owner REJECT ->", r["status"])
    attempt("UPDATE approvals SET status='PENDING'", f"UPDATE approvals SET status='PENDING', decided_by=NULL, decided_day=NULL WHERE id='{a.id}'",
            rollback=False)
    r = c.post(f"/approvals/{a.id}", json={"decision": "APPROVE"}, headers=OWNER).json()
    res = r.get("result", r)
    print("  owner APPROVE after the flip ->", res.get("status") if isinstance(res, dict) else json.dumps(r)[:200])
    print("  log for", a.id, ":", [(o.seq, json.loads(o.result_json)["status"]) for o in rt.store.operations()
                                   if json.loads(o.result_json).get("approval_id") == a.id])
    print("  chain_valid:", c.get("/ledger", headers=OWNER).json()["chain_valid"])
eng.dispose()
rt.store.dispose()
