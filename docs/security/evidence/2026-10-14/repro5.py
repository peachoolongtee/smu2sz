"""Two workers (two Runtime objects, separate rt.lock, one shared store): concurrent owner accepts of one request."""
import threading
exec(open(__file__.replace("repro5.py", "repro2.py")).read().split('print("=== D')[0])
import app.api.accept as acc
rtA, c = fresh()
oid = c.post("/offers", json={"fixture_id": ZHUHAI}, headers=OWNER).json()["offer"]["offer_id"]
v = c.post(f"/offers/{oid}/evaluate", json={"fixture_id": ZHUHAI}, headers=OWNER).json()
rtB = Runtime(settings=get_settings(), store=rtA.store, owner_key_hex=rtA.owner_key_hex); rtB.hydrate()
local = threading.local()
acc.get_runtime = lambda: local.rt
orig_bound = acc._bound
gate, passed = threading.Event(), threading.Event()
def bound(rt, *a, **k):
    out = orig_bound(rt, *a, **k)
    if rt is rtA:
        passed.set(); gate.wait(30)  # worker A has checked; worker B runs now
    return out
acc._bound = bound
body = acc.AcceptIn(verdict_id=v["id"], state_version=v["state_version"])
res = {}
def run(name, rt):
    local.rt = rt
    try:
        res[name] = ("ok", acc.accept_as_asked(oid, body)["decision"]["state"])
    except Exception as e:
        res[name] = ("err", getattr(e, "status_code", None), (getattr(e, "detail", None) or {}).get("code") if isinstance(getattr(e, "detail", None), dict) else str(e)[:120])
tA = threading.Thread(target=run, args=("A", rtA)); tA.start(); passed.wait(30)
tB = threading.Thread(target=run, args=("B", rtB)); tB.start(); tB.join(60); gate.set(); tA.join(60)
print("results", res)
print("commitments", [(x.id[:14], x.status.value) for x in rtA.store.commitments() if x.offer_id == oid])
print("forward concessions", [(f.commitment_id[:14], f.value_fen) for f in rtA.store.get_state().forward_concessions])
print("approvals", [(a.id, str(getattr(a.status, "value", a.status))) for a in rtA.store.approvals()])
