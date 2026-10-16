"""Q3/Q4: two runtimes (two API instances) on one SQLite file; rt.day is hydrated once and never re-read."""
import os, sys, json, pathlib
SCR = pathlib.Path(sys.argv[1])
for p in SCR.glob("stale.db*"):
    p.unlink()
URL = f"sqlite:///{(SCR / 'stale.db').as_posix()}"
os.environ["DATABASE_URL"] = URL; os.environ["DEMO_MODE"] = "1"
import logging; logging.disable(logging.CRITICAL)
from app.api.runtime import get_runtime, Runtime
from app.config import get_settings
from app.persistence import SqlLedgerStore
from app.domain.models import DrawFacility, Actor

A = get_runtime()
B = Runtime(settings=get_settings(), store=SqlLedgerStore(URL), owner_key_hex=A.owner_key_hex); B.hydrate()
print("A.day", A.day, "B.day", B.day)
A.advance_to(A.day + 20)
print("after A.advance_to: A.day", A.day, "B.day", B.day, "stored as_of_day", B.store.get_state().as_of_day)
st = B.store.get_state(); m = B.store.get_mandate()
for f in st.facilities:
    op = DrawFacility(op_id=f"OP-STALE-{f.id}", idempotency_key=f"STALE-{f.id}", mandate_version=m.version,
                      requested_by=Actor.OWNER, day=B.day, facility_id=f.id, amount_fen=100_000)
    r = B.executor.execute(op)
    print(f"B executes DrawFacility on {f.id} dated day {op.day}: {r.status.value} effective_day={r.effective_day} {r.message[:90]}")
    if r.status.value == "EXECUTED":
        break
ops = B.store.operations()
print("log (seq, kind, effective_day):", [(o.seq, o.kind, json.loads(o.result_json).get("effective_day")) for o in ops])
print("chain_valid", B.store.verify_chain(), "state as_of_day now", B.store.get_state().as_of_day)
