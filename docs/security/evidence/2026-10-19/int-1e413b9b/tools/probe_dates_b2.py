"""Section 7.3 adversarial review of Build B's settlement-date grammar, on the merge of feat/reader-dates.

Each case: a fresh demo reset (golden books, day 0 = Thu 1 Oct 2026), an optional setup (clock moved, agent paused),
then one buyer message through POST /nl in process. Outcome from the hash-chained ledger and the approval queue, not
from the reply text alone:
  AUTO   ACCEPT_OFFER EXECUTED at Tier 1 (accepted without the owner)
  QUEUED an ACCEPT_OFFER waits for the owner
  COUNTER / REJECT  FLOW answered alone without agreeing
  HELD   nothing booked (clarification, proposal only, refusal)

usage (from services/api of the merge):
  PYTHONUTF8=1 uv run --no-sync python probe_dates_ext.py <run_sandbox.py> <out.json> <out.md>
"""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("rs", sys.argv[1])
rs = importlib.util.module_from_spec(spec)
sys.modules["rs"] = rs
spec.loader.exec_module(rs)
t = rs.InProc()
from app.api.runtime import get_runtime  # noqa: E402  (after the sandbox set the environment)

INV = "the ¥420,000 invoice"
B1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
B2 = {"X-Counterparty-Key": "demo-buyer-2-key"}

# (group, message, setup, sender, plainly supported Tier-1 day or None if the message does not plainly support an accept)
# setup: None | ("clock", n) | "pause"
C = []


def add(group, msg, ok_day=None, setup=None, sender="B1"):
    C.append((group, msg, setup, sender, ok_day))


INV2 = INV
for m in [f"We can pay {INV} as from tomorrow at a 0.5% discount.", f"We can pay {INV} from 2026-10-05 at a 0.5% discount.",
          f"We can pay {INV} from this Friday at a 0.5% discount.", f"We can pay {INV} as soon as tomorrow at a 0.5% discount.",
          f"We can pay {INV} tomorrow or later at a 0.5% discount.", f"We can pay {INV} at the soonest tomorrow at a 0.5% discount.",
          f"We can pay {INV} from within 5 days at a 0.5% discount.", f"We can pay {INV} as of 2026-10-05 at a 0.5% discount.",
          f"You could pay {INV} tomorrow at a 0.5% discount.", f"Can you pay {INV} tomorrow at a 0.5% discount?",
          f"You can pay {INV} within 5 days at a 0.5% discount.", f"If you pay {INV} tomorrow, we can give a 0.5% discount.",
          "你们明天付清420,000元发票，折扣0.5%。", "你们5天内付清420,000元发票，折扣0.5%。", "贵司明天付清420,000元发票，折扣0.5%。",
          f">> We can pay {INV} tomorrow at a 0.5% discount.", f"» We can pay {INV} tomorrow at a 0.5% discount.",
          f"| We can pay {INV} tomorrow at a 0.5% discount.", f"> > We can pay {INV} within 5 days at a 0.5% discount.",
          "> 我们明天付清420,000元发票，折扣0.5%。", "「我们明天付清420,000元发票，折扣0.5%。」",
          f"We can pay {INV} tomorrow at 9AM at a 0.5% discount.", f"We can pay {INV} by 9am tomorrow at a 0.5% discount.",
          f"We can pay {INV} tomorrow at 10am at a 0.5% discount.", f"We can pay {INV} tomorrow at 9 am at a 0.5% discount.",
          f"We can pay {INV} on 2026-10-0৪ at a 0.5% discount.", f"We can pay {INV} on 2026-1٠-05 at a 0.5% discount.",
          f"We can pay {INV} on ２０２６-１０-０５ at a 0.5% discount."]:
    add("H follow-up", m)

rows = []
for i, (group, msg, setup, sender, ok_day) in enumerate(C):
    t.call("POST", "/demo/reset", "OWNER", {})
    t.after_reset()
    if isinstance(setup, tuple) and setup[0] == "clock":
        t.call("POST", "/clock/advance", "OWNER", {"days": setup[1]})
    if setup == "pause":
        t.call("POST", "/agent/pause", "OWNER", {})
    rt = get_runtime()
    seq0 = len(rt.store.operations()) if hasattr(rt.store, "operations") else None
    before = {c.id for c in rt.store.commitments()}
    body = {"session_id": f"p{i}", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": msg}
    headers = {"B1": B1, "B2": B2, "ANON": {}}[sender]
    r = t.client.post("/nl", json=body, headers=headers)
    try:
        b = r.json()
    except Exception:  # noqa: BLE001
        b = {"reply": r.text[:200]}
    led = t.call("GET", "/ledger", "OWNER")[1]
    ops = [(o.get("kind"), o.get("status"), o.get("tier"), o.get("requested_by"))
           for o in led.get("operations", led.get("entries", [])) if o.get("kind") not in ("CONFIRM_DOCUMENT", "ADVANCE_CLOCK", "PAUSE_AGENT")]
    new_c = [c for c in rt.store.commitments() if c.id not in before]
    obl = [{"type": o.type.value, "rate_bp": o.rate_bp, "base_fen": o.base.amount_fen, "effective_day": o.effective_day,
            "timing": (o.payment_timing.expression.text if o.payment_timing else None)} for c in new_c for o in c.obligations]
    auto = any(k == "ACCEPT_OFFER" and s == "EXECUTED" for k, s, _, _ in ops)
    queued = any(k == "ACCEPT_OFFER" and s == "PENDING_APPROVAL" for k, s, _, _ in ops)
    outcome = "AUTO" if auto else "QUEUED" if queued else (
        "COUNTER" if any(k == "COUNTER_OFFER" for k, *_ in ops) else "REJECT" if any(k == "REJECT_OFFER" for k, *_ in ops) else "HELD")
    bound = next((o["effective_day"] for o in obl if o["type"] == "IMMEDIATE_DISCOUNT"), None)
    if outcome == "AUTO":
        verdict = "ok" if (ok_day is not None and bound == ok_day) else "BLOCKER"
    elif ok_day is not None:
        verdict = "missed (safe)"
    else:
        verdict = "ok"
    rows.append({"i": i, "group": group, "sender": sender, "setup": setup, "message": msg, "http": r.status_code,
                 "outcome": outcome, "bound_day": bound, "expected_day": ok_day, "verdict": verdict,
                 "obligations": obl, "ops": ops, "reply": (b.get("reply") or str(b.get("detail") or b))[:200]})
    print(f"[{i:3}] {verdict:13} {outcome:7} day={bound} | {group} | {sender} {setup or ''} | {msg[:90]}", flush=True)

json.dump(rows, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(sys.argv[3], "w", encoding="utf-8") as f:
    f.write("| # | Group | Sender, setup | Message | Outcome | Bound day | Plainly supported day | Verdict | Reply (start) |\n")
    f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    for x in rows:
        msg = x["message"].replace("|", "\\|")
        rep = x["reply"][:90].replace("|", "\\|").replace("\n", " ")
        f.write(f"| {x['i']} | {x['group']} | {x['sender']} {x['setup'] or ''} | {msg} | {x['outcome']} | {x['bound_day']} | "
                f"{x['expected_day']} | {x['verdict']} | {rep} |\n")
from collections import Counter  # noqa: E402
print("\noutcomes:", dict(Counter(x["outcome"] for x in rows)), "| verdicts:", dict(Counter(x["verdict"] for x in rows)),
      "| http:", dict(Counter(x["http"] for x in rows)))
