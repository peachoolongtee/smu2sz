"""The early-pay settlement day defaults to the early-pay facility's lead time as an ABSOLUTE day (2), not today + lead:
`verifier/bind.early_pay_lead` and `trajectory._early_pay_lead`. From day 3 on, every early-payment offer that names
no date binds to a day already closed and cannot be verified, so the buyer's early cash is never taken."""
from _harness import *  # noqa: F403

for day in (0, 1, 3, 10):
    rt, c = fresh()
    if day:
        advance(c, day)
    docs = [{"doc_id": f"EP-{day}", "channel": "chat", "sender_id": "BUYER-1", "received_day": day,
             "text": "We can pay RCV-A early at 0.5%. Nothing else changes."}]
    o = c.post("/offers", json={"counterparty_id": "BUYER-1", "documents": docs}).json()["offer"]
    v = c.post(f"/offers/{o['offer_id']}/evaluate", headers=OWNER, json={}).json()
    eff = [b.get("effective_day") for b in v.get("bound_obligations", [])]
    print(f"day {day}: verdict {v['outcome']}, settle day {eff}, codes {sorted({x['code'] for x in v['violations']})}")
    if day >= 3:
        from app.domain.models import Obligation
        from app.financial import EngineError
        from app.verifier.bind import early_pay_lead
        ob = rt.store.get_offer(o["offer_id"]).obligations[0]
        print(f"   bind's default settle day on day {day}: {early_pay_lead(rt.store.get_state(), 'BUYER-1')}")
        try:
            project(rt.store.get_state(), [ob], [], Mode.CONSERVATIVE, 30)
            print("   engine: binds")
        except EngineError as exc:
            print("   engine:", exc)
        check(f"day {day}: an early-pay offer on an open invoice due day 32 cannot be accepted",
              v["outcome"] not in ("ACCEPT", "NEEDS_OWNER_APPROVAL", "COUNTER"))
