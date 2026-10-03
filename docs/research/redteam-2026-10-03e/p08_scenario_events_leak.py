"""The demo scenario's outside-world events are applied to books that are not that scenario's.

`Runtime.advance_to` always passes `scenario_events(self.scenario)` to the clock, and `Runtime.scenario` is process
memory only, defaulting to "golden_sme": it is set by `reset()` and nowhere else, and it is not in the store.

A. Production-like start (DEMO_MODE=0, explicit credentials, the owner's own provisioned books: here the
   short_facilities state stands in for any business's state). The owner moves the clock from day 0 to day 30.
   The golden demo's ADD_FLOW event (a -¥200,000 "Payroll, month 2" on day 42, scenario golden_sme.events.json) is
   written into these books and logged as an executed ADVANCE_CLOCK.
B. Demo: /demo/reset?scenario=short_facilities, clock to day 20, then the API restarts (the runtime is hydrated
   from the same store exactly as get_runtime does). Closing day 25 now injects the golden payroll into the
   short_facilities books; without the restart it does not.
"""
import os
import sys

from _harness import *  # noqa
import app.api.runtime as runtime_mod  # noqa: E402
from app.api.runtime import Runtime, get_runtime, set_runtime  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.domain.fixtures import load_scenario  # noqa: E402
from app.mandate.fixture import demo_owner_public_key_hex  # noqa: E402

part = sys.argv[1] if len(sys.argv) > 1 else "both"


def flows(rt):
    return {f.id: (f.day, f.amount_fen) for f in rt.store.get_state().flows}


if part in ("A", "both"):
    print("=== A: DEMO_MODE=0, the owner's own books")
    os.environ.update({"DEMO_MODE": "0", "OWNER_TOKEN": "prod-owner-token", "AGENT_KEY": "prod-agent-key",
                       "BANK_FEED_KEY": "prod-bank-key", "OWNER_PUBLIC_KEY_HEX": demo_owner_public_key_hex()})
    set_runtime(None)
    rt = get_runtime()
    own, _ = load_scenario("short_facilities")  # stands in for the business's provisioned state
    rt.store.put_state(own)
    rt.day = own.as_of_day
    print("runtime scenario:", rt.scenario, "| flows before:", flows(rt))
    c = TestClient(app)
    r = c.post("/clock/advance", json={"to_day": 30}, headers={"X-Owner-Token": "prod-owner-token"})
    print("advance:", r.status_code, r.json()["result"]["message"])
    after = flows(rt)
    print("flows after:", after)
    last = rt.store.operations()[-1]
    print("log:", last.kind, last.payload_json[:260])
    check("a production start applies the golden demo's -¥200,000 payroll event to the owner's own books",
          "F-PAYROLL-M2" in after)
    for k in ("DEMO_MODE", "OWNER_TOKEN", "AGENT_KEY", "BANK_FEED_KEY", "OWNER_PUBLIC_KEY_HEX"):
        os.environ.pop(k, None)
    set_runtime(None)

if part in ("B", "both"):
    print("=== B: demo, short_facilities, API restart on day 20")
    for restart in (False, True):
        rt, c = fresh()
        r = c.post("/demo/reset", params={"scenario": "short_facilities"}, headers=OWNER)
        print("reset:", r.json())
        advance(c, 20)
        if restart:  # what get_runtime() does on start-up with a store that already holds books
            rt = Runtime(settings=get_settings(), store=rt.store, owner_key_hex=rt.owner_key_hex)
            rt.day = rt.store.get_state().as_of_day
            set_runtime(rt)
        advance(c, 30)
        f = flows(rt)
        print(f"  restart={restart}: runtime scenario {rt.scenario}; flows {f}; cash {rt.store.get_state().cash_fen}")
        if restart:
            check("after a restart the clock injects the golden payroll into the short_facilities books",
                  "F-PAYROLL-M2" in f)
        set_runtime(None)
