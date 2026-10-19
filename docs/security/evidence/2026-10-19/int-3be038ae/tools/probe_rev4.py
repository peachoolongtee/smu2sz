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



E = "the ¥420,000 invoice early at a 0.5% discount"
Z = "提前支付420,000元发票，折扣0.5%。"
# P: the writer's own ten (must be held)
for m in [f"You can pay {E}.", f"You could pay {E}.", "你们可以"+Z, "贵司可以"+Z, f"> We can pay {E}.", f">> We can pay {E}.",
          f"» We can pay {E}.", f"| We can pay {E}.", "「我们可以"+Z[:-1]+"」", "> 我们可以"+Z]:
    add("P writer's ten", m)
# B2 second person (a Tier-1 accept here is a blocker)
for m in [f"You guys can pay {E}.", f"Y'all can pay {E}.", f"Your side will pay {E}.", f"You're able to pay {E}.", f"You’re able to pay {E}.",
          f"U can pay {E}.", f"YOU CAN PAY {E.upper()}.", f"You can settle {E}.", f"You may pay {E}.", f"You pay {E}.",
          f"You'll pay {E}.", f"You’ll pay {E}.", f"You'd pay {E}.", f"You'll settle {E}.", f"You, if ok, can pay {E}.",
          f"You, if ok, will pay {E}.", f"You - can pay {E}.", f"You: pay {E}.", f"You\ncan pay {E}.", f"You  can   pay {E}.",
          f"You can, if ok, pay {E}.", f"You can do the payment of {E}.", f"Your company can pay {E}.", f"Your accounts team can pay {E}.",
          f"Your finance team can pay {E}.", f"Your people can pay {E}.", f"Your CFO can pay {E}.", f"You and your team can pay {E}.",
          f"You yourselves can pay {E}.", f"You can then pay {E}.", f"You can so pay {E}.", f"Can you pay {E}?", f"Could you pay {E}?",
          f"Thank you, you can pay {E}.", f"Thanks you can pay {E}.", f"Thank you you can pay {E}.", f"Ya can pay {E}.", f"Yu can pay {E}.",
          f"Yοu can pay {E}.", f"Ｙｏｕ can pay {E}.", f"You can pаy {E}.", f"It's you who can pay {E}.", f"The payer is you: pay {E}.",
          "您们可以"+Z, "你方可以"+Z, "贵单位可以"+Z, "贵公司可以"+Z, "贵方可以"+Z, "你们可以付清420,000元发票，折扣0.5%。",
          "你们可以结清420,000元发票，折扣0.5%。", "你们可以结算420,000元发票，折扣0.5%。", "你们可以付款420,000元发票，折扣0.5%。",
          "你们，可以"+Z, "你们 可以 "+Z, "你们也可以就是想"+Z, "您可以"+Z, "你可以"+Z, "你们明天付清420,000元发票，折扣0.5%。",
          "您好你们可以"+Z, "你们好，你们可以"+Z, "贵司，"+Z, "由你们"+Z, "你们去"+Z, "請你們"+Z]:
    add("B2 second person", m)
# B3 quoting (a Tier-1 accept here is a blocker)
for m in [f"We can pay {E}.\n> earlier note", f"Hi,\n> We can pay {E}.", f"We can pay {E}.\n> Thanks", f"Re: We can pay {E}.",
          f"Fwd: We can pay {E}.", f"-----Original Message-----\nWe can pay {E}.", f"On Monday Li wrote:\nWe can pay {E}.",
          f"＞ We can pay {E}.", f"》 我们可以"+Z, "『我们可以"+Z[:-1]+"』", f"“We can pay {E}.”", f"\"We can pay {E}.\"",
          f"\"We can pay {E}.\"\nThanks, Li Wei", f"“We can pay {E}.”\nThanks!", f"Hi, \"We can pay {E}.\"", f"Hi, “We can pay {E}.”",
          f"'We can pay {E}.'", f"‘We can pay {E}.’", f"＂We can pay {E}.＂", f"› We can pay {E}.", f"‹ We can pay {E}.",
          f"│ We can pay {E}.", f"¦ We can pay {E}.", f"〉 We can pay {E}.", "《我们可以"+Z[:-1]+"》", f"  > We can pay {E}.",
          f"\t> We can pay {E}.", f"​> We can pay {E}.", f" > We can pay {E}.", f"Thanks!\n> We can pay {E}.",
          f"We said: \"We can pay {E}.\"", f"«We can pay {E}.»", f"„We can pay {E}.“", f"```\nWe can pay {E}.\n```",
          "我们可以"+Z+"\n——转发——"]:
    add("B3 quoting", m)
# OK plain offers (should still be accepted alone; a hold here is a false hold)
for m in [f"We can pay {E}.", f"We will pay {E}.", f"We would like to pay {E}.", f"Can we pay {E}?", f"Hi, we can pay {E}. Thanks!",
          f"Thank you, we can pay {E}.", f"Thank you we can pay {E}.", f"If you agree we can pay {E}.", f"If you agree, we can pay {E}.",
          f"Could you confirm, we can pay {E}.", f"Please confirm: we can pay {E}.", f"We can pay you {E}.", f"Can we pay you {E}?",
          f"Hope you are well, we can pay {E}.", f"Hope you are well we can pay {E}.", f"Thanks to you we can pay {E}.",
          f"If you prefer we can pay {E}.", f"As you know, we can pay {E}.", f"We can pay {E}, if that works for you.",
          f"Let us know if you agree. We can pay {E}.", f"Thank you so much, we can pay {E}.", f"Thanks! We can pay {E}.",
          "我们可以"+Z, "您好，我们可以"+Z, "您好我们可以"+Z, "谢谢你们，我们可以"+Z, "感谢贵司，我们可以"+Z, "如果你们同意，我们可以"+Z,
          "如果你们同意我们可以"+Z, "请您确认，我们可以"+Z, "麻烦您确认一下，我们可以"+Z, "我们可以付清420,000元发票，提前付款，折扣0.5%。",
          "谢谢您，我们可以"+Z, "感谢您的配合，我们可以"+Z, "您看我们可以"+Z, "你们看我们"+Z]:
    add("OK plain offer", m, 2)
# N negations (must still not be accepted alone)
for neg in ["won't", "can't", "cannot", "will never", "are unable to", "refuse to", "wouldn't", "couldn't", "decline to", "are not able to"]:
    add("N negation", f"We {neg} pay {E}.")
for neg in ["不会", "不能", "无法", "没法", "不可能", "拒绝", "不打算", "不愿意"]:
    add("N negation", f"我们{neg}"+Z)

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
            "timing": (getattr(o, "payment_timing", None).expression.text if getattr(o, "payment_timing", None) else None)} for c in new_c for o in c.obligations]
    auto = any(k == "ACCEPT_OFFER" and s == "EXECUTED" for k, s, _, _ in ops)
    queued = any(k == "ACCEPT_OFFER" and s == "PENDING_APPROVAL" for k, s, _, _ in ops)
    outcome = "AUTO" if auto else "QUEUED" if queued else (
        "COUNTER" if any(k == "COUNTER_OFFER" for k, *_ in ops) else "REJECT" if any(k == "REJECT_OFFER" for k, *_ in ops) else "HELD")
    bound = next((o["effective_day"] for o in obl if o["type"] == "IMMEDIATE_DISCOUNT"), None)
    if outcome == "AUTO":
        verdict = "ok" if ok_day is not None else ("BLOCKER" if group.startswith(("B2","B3","P ")) else "CHECK")
    elif ok_day is not None:
        verdict = "FALSE HOLD"
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
