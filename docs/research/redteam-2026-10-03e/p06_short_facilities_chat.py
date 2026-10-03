"""The short_facilities scenario driven through the owner's chat on several days, two devices (two sessions).

Each day: device A asks for the opener, device B asks for alerts; device A says go ahead, then approves anything it
was shown; device B then says go ahead on its own (older) proposal. The clock then moves with exactly the projected
receipts. Printed: every reply, the operations each produced, and the state. Checks: nothing executes twice for one
proposal, conservation, the chain."""
import sys

from _harness import *  # noqa

scenario = sys.argv[1] if len(sys.argv) > 1 else "short_facilities"
days = [int(x) for x in sys.argv[2:]] or [0, 12, 30, 34, 42]
rt, c = fresh()
rt.reset(scenario)
A, B = "devA", "devB"


def say(sid, text):
    out = nl(c, OWNER, text, session_id=sid)
    ops = [(o.get("kind"), o.get("status"), (o.get("message") or "")[:120]) for o in out.get("operations", [])]
    print(f"  [{sid}] > {text}\n      < {out['reply'][:600]}\n      ops {ops}")
    return out


for d in days:
    if d > rt.day:
        t = projection(rt)
        live(c, rt, t, d, tag=f"p{d}")
    print("=" * 20, "day", rt.day)
    snap(rt, f"day {rt.day} start")
    r = c.post("/nl/opener", json={"session_id": A}, headers=OWNER).json()
    print(f"  [{A}] opener < {r['reply'][:600]}")
    say(B, "show me the alerts")
    say(B, "fund the gap")
    n_before = len(rt.store.operations())
    say(A, "go ahead")
    q = [a for a in c.get("/approvals/queue", headers=OWNER).json()["approvals"] if a["status"] == "PENDING"]
    for a in q:
        say(A, f"approve {a['id']}")
    say(B, "go ahead")
    q = [a for a in c.get("/approvals/queue", headers=OWNER).json()["approvals"] if a["status"] == "PENDING"]
    for a in q:
        print("  still pending:", a["id"], a["reason"][:120])
    executed = [e for e in rt.store.operations()[n_before:] if '"status":"EXECUTED"' in e.result_json
                and e.kind in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")]
    for e in executed:
        print("  EXECUTED", e.seq, e.kind, e.payload_json[:160])
    snap(rt, f"day {rt.day} after chat")
    print("  conservation", conservation(rt), "chain", rt.store.verify_chain())
    t = projection(rt)
    print(f"  projection: first breach {t.first_breach_day}, low {t.min_cash_fen} on day {t.min_cash_day}")
