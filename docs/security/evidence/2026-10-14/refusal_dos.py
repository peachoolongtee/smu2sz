"""Q2: anonymous refusals -> security_events growth and per-refusal cost. argv: scratch dir, 'memory'|'sqlite', N."""
import os, sys, time, pathlib, collections, threading

SCR = pathlib.Path(sys.argv[1]); kind = sys.argv[2]; N = int(sys.argv[3])
if kind == "sqlite":
    for p in SCR.glob("dos.db*"):
        p.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{(SCR / 'dos.db').as_posix()}"
else:
    os.environ["DATABASE_URL"] = "memory"
os.environ["DEMO_MODE"] = "1"
import logging; logging.disable(logging.CRITICAL)
from fastapi.testclient import TestClient
from app.main import app
from app.api.runtime import get_runtime

c = TestClient(app)
rt = get_runtime()
OWNER = {"X-Owner-Token": "demo-owner-token"}
B = N // 8
t_all = time.perf_counter()
for b in range(8):
    t0 = time.perf_counter()
    for i in range(B):
        r = c.get("/ledger")  # no credential -> 401 + one security event
    dt = time.perf_counter() - t0
    print(f"batch {b}: events={len(rt.store.security_events())} status={r.status_code} ms/refusal={1000*dt/B:.2f}")
print(f"total {time.perf_counter()-t_all:.1f}s for {N} refusals")
t0 = time.perf_counter(); r = c.get("/audit", headers=OWNER); print(f"GET /audit {r.status_code} {len(r.content)//1024} KiB in {time.perf_counter()-t0:.2f}s")
t0 = time.perf_counter(); r = c.get("/ledger", headers=OWNER); print(f"GET /ledger (owner) {r.status_code} in {time.perf_counter()-t0:.2f}s")
ids = [e.id for e in rt.store.security_events()]
print("distinct ids", len(set(ids)), "of", len(ids))

# concurrent refusals: same method/path/why/day read the same len() -> same id
from app.api.auth import log_refusal
class FakeURL: path = "/ledger"
class FakeReq: method = "GET"; url = FakeURL()
barrier = threading.Barrier(16)
def go():
    barrier.wait(); log_refusal(FakeReq(), "owner token missing or wrong")
before = len(rt.store.security_events())
ts = [threading.Thread(target=go) for _ in range(16)]
[t.start() for t in ts]; [t.join() for t in ts]
new = [e.id for e in rt.store.security_events()[before:]]
dup = {k: v for k, v in collections.Counter(new).items() if v > 1}
print(f"16 concurrent refusals: {len(new)} rows, {len(set(new))} distinct ids, duplicated ids: {dup}")
