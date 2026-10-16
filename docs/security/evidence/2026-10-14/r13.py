"""R-13 reproduction on a scratch SQLite file. Read-only w.r.t. the repo."""
import hashlib, json, os, sqlite3, sys, pathlib

SCR = pathlib.Path(sys.argv[1])
DB = SCR / "r13.db"
for p in SCR.glob("r13.db*"):
    p.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["DEMO_MODE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.api.runtime import get_runtime  # noqa: E402

OWNER = {"X-Owner-Token": "demo-owner-token"}
c = TestClient(app)
r = c.post("/demo/reset", params={"scenario": os.environ.get("SC","golden_sme")}, headers=OWNER)
print("demo/reset", r.status_code)
# some anonymous refusals -> security events
for _ in range(3):
    c.get("/ledger")
rt = get_runtime()

def ledger():
    j = c.get("/ledger", headers=OWNER).json()
    return j["chain_valid"], j["chain_length"], (j["head_hash"] or "")[:12]

def counts():
    con = sqlite3.connect(DB)
    out = {t: con.execute(f"select count(*) from {t}").fetchone()[0]
           for t in ("operations", "security_events", "approvals", "evidence_exports", "used_nonces")}
    con.close()
    return out

print("baseline ledger", ledger(), counts())
con = sqlite3.connect(DB)
print("triggers:", [r[0] for r in con.execute("select name from sqlite_master where type='trigger'")])

# (0) direct DELETE on operations: trigger refuses
try:
    con.execute("delete from operations where seq = (select max(seq) from operations)"); con.commit()
    print("(0) delete tail WITHOUT dropping trigger: succeeded (!)")
except Exception as e:
    print("(0) delete tail without dropping trigger:", type(e).__name__, e)

# (c) security events and approvals: no triggers at all
con.execute("delete from security_events"); con.commit()
n_appr = con.execute("select count(*) from approvals").fetchone()[0]
con.execute("update approvals set status='REJECTED', decided_by='OWNER' where status='PENDING'"); con.commit()
con.execute("delete from evidence_exports"); con.commit()
print("(c) deleted all security_events, rewrote", n_appr, "approvals, deleted evidence_exports; ledger:", ledger(), counts())

# (a) truncate tail: anyone with DDL drops the trigger (SQLite) / table owner on PG
con.execute("drop trigger trg_operations_no_delete")
before = counts()["operations"]
con.execute("delete from operations where seq > ?", (before - 2,)); con.commit()
print("(a) truncated tail from", before, "->", counts()["operations"], "; ledger:", ledger())

# (b) rewrite whole chain consistently: alter payload of seq 1 and recompute every hash forward
con.execute("drop trigger trg_operations_no_update")
rows = con.execute("select seq, payload_json, result_json from operations order by seq").fetchall()
prev = "0" * 64
for i, (seq, pj, rj) in enumerate(rows):
    if i == 0:
        p = json.loads(pj); p["requested_by"] = "FORGED"; pj = json.dumps(p, separators=(",", ":"), sort_keys=True)
    h = hashlib.sha256((prev + pj + rj).encode()).hexdigest()
    con.execute("update operations set payload_json=?, prev_hash=?, entry_hash=? where seq=?", (pj, prev, h, seq))
    prev = h
con.commit()
print("(b) rewrote seq 1 payload (requested_by=FORGED) and re-hashed", len(rows), "entries; ledger:", ledger())
print("    rt.store.verify_chain() =", rt.store.verify_chain())
# recreate triggers so the file looks untouched
from app.persistence import guards
for _n, stmt in guards.SQLITE_TRIGGERS:
    con.execute(stmt)
con.commit()
print("    triggers restored:", [r[0] for r in con.execute("select name from sqlite_master where type='trigger'")])

# evidence export + external verifier
ev = c.get("/evidence", headers=OWNER).text
(SCR / "r13_evidence.jsonl").write_text(ev, encoding="utf-8")
con.close()

# (d) owner-credential API erase: POST /demo/reset on the persistent SQLite store (DEMO_MODE default on)
c.get("/ledger")  # one more refusal
print("pre-reset", ledger(), counts())
r = c.post("/demo/reset", params={"scenario": "short_facilities"}, headers=OWNER)
print("(d) POST /demo/reset scenario=short_facilities ->", r.status_code, "; ledger:", ledger(), counts())
