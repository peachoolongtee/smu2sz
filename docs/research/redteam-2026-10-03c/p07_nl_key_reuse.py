"""/nl idempotency keys are `nl:<session id>:t<turn>:<n>:<kind>` when the client sends no request_id. A session that
expires (30-minute TTL), is dropped by /nl/reset or by a restart (sessions are not persisted, the log is) starts again
at turn 1 under the same client-chosen id, so a later command reuses an earlier key. The executor's idempotency rule
ignores `day` ("a retry on a later day is the same operation"): the same draw days later is answered DUPLICATE and
nothing moves; a different one is refused as a REPLAY with a security event."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _harness import *  # noqa: E402,F403

rt, c = fresh()
S = "owner-phone"
r = nl(c, OWNER, "draw ¥50,000 on the credit line", session_id=S)
print("day 0 turn 1:", r["reply"][:200], "| awaiting", r["awaiting_confirmation"])
if r["awaiting_confirmation"]:
    r = nl(c, OWNER, "go ahead", session_id=S)
    print("day 0 turn 2:", r["reply"][:200])
for o in r["operations"]:
    print("   op", o["kind"], o["status"], o["op_id"], o["message"][:120])
a = snap(rt, "day 0 after draw")
res = op(c, OWNER, {"kind": "REPAY_FACILITY", "op_id": "own-repay-1", "requested_by": "OWNER", "facility_id": "FAC-LINE",
                    "amount_fen": 5_000_000})
print("owner repays the line:", res["status"], res["message"][:120])
advance(c, 5)
r = c.post("/nl/reset", headers=OWNER)  # the same effect as the 30-minute TTL or a server restart: sessions gone, log kept
print("sessions dropped:", r.status_code)
b = snap(rt, "day 5 before")
sec0 = len(rt.store.security_events())
r = nl(c, OWNER, "draw ¥50,000 on the credit line", session_id=S)
print("day 5 turn 1:", r["reply"][:200], "| awaiting", r["awaiting_confirmation"])
if r["awaiting_confirmation"]:
    r = nl(c, OWNER, "go ahead", session_id=S)
    print("day 5 turn 2:", r["reply"][:300])
for o in r["operations"]:
    print("   op", o["kind"], o["status"], o["op_id"], o["message"][:200])
after = snap(rt, "day 5 after")
check("the owner's day-5 draw did not happen (cash and drawn unchanged)", after["cash"] == b["cash"] and after["drawn"] == b["drawn"])
check("the reply reports it as done or as a duplicate of day 0", "done" in r["reply"].lower() or "duplicate" in r["reply"].lower())
# a different amount: refused as a replay, with a security event
r = c.post("/nl/reset", headers=OWNER)
r = nl(c, OWNER, "draw ¥60,000 on the credit line", session_id=S)
if r["awaiting_confirmation"]:
    r = nl(c, OWNER, "go ahead", session_id=S)
print("day 5, different amount:", r["reply"][:300])
new_sec = rt.store.security_events()[sec0:]
print("   security events:", [(e.kind.value, e.detail[:120]) for e in new_sec])
check("the owner's own command is logged as a REPLAY attack", any(e.kind.value == "REPLAY" for e in new_sec))
print("verify_chain", rt.store.verify_chain())
