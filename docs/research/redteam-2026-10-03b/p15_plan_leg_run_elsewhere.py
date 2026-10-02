"""A pending chat plan confirmed after one of its legs was run by another route (/operations by the agent)."""
from _harness import *  # noqa: F403

rt, c = fresh()
out = nl(c, OWNER, "fund the gap", session_id="owner-s1")
print("proposal:", out["reply"][:300])
print("awaiting:", out["awaiting_confirmation"])
legs = [s for s in out["plan"] if s.get("kind") in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")]
print("legs shown:", [(s["kind"], s.get("text", s.get("description", ""))[:90]) for s in legs])
from app.nl.sessions import SESSIONS  # noqa: E402

pending = SESSIONS.get(out["session_id"]).pending_plan
for i, o in enumerate(pending.ops):
    body = {k: v for k, v in o.model_dump(mode="json").items() if k not in ("op_id", "idempotency_key", "requested_by")}
    r = op(c, AGENT, {**body, "op_id": f"other-{i}", "requested_by": "AGENT"})
    print("agent runs the same leg via /operations:", r["status"], r["message"][:120])
before = snap(rt, "before go-ahead")
out2 = nl(c, OWNER, "go ahead", session_id=out["session_id"])
print("go ahead ->", out2["reply"][:400])
after = snap(rt, "after go-ahead")
check("the gap was funded twice", after["drawn"] != before["drawn"] or after["cash"] != before["cash"])
