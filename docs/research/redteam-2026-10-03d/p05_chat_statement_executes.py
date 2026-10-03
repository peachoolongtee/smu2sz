"""Chat: a past-tense Chinese statement ("还了额度10万元", "I repaid ¥100,000 on the line") and a Chinese tag question
("对吧" / "是吧", "right?") are read as a command and as a go-ahead."""
from _harness import *

# 1. "还了额度10万元" after a ¥150,000 line draw
rt, c = fresh()
advance(c, 32)
op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-a", "requested_by": "SYSTEM", "receivable_id": "RCV-A",
             "amount_fen": 42000000})
advance(c, 47)
op(c, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-2", "requested_by": "SYSTEM", "receivable_id": "RI:BUYER-1:2",
             "amount_fen": 42000000})
advance(c, 48)
op(c, OWNER, {"kind": "DRAW_FACILITY", "op_id": "d1", "requested_by": "OWNER", "facility_id": "FAC-LINE",
              "amount_fen": 15000000})
before = snap(rt, "after draw")
out = nl(c, OWNER, "还了额度10万元")
print("reply:", out["reply"][:240].replace("\n", " | "))
print("operations:", [(o.get("kind"), o.get("status")) for o in out.get("operations", [])])
after = snap(rt, "after the statement")
check("a past-tense statement ('I repaid 100k on the line') executed a ¥100,000 repayment",
      after["drawn"].get("FAC-LINE", 0) == 5000000 and after["cash"] < before["cash"])

# 2. a pending funding plan, then the tag question 对吧 ("right?")
for tag in ("对吧", "是吧"):
    rt, c = fresh()
    out = nl(c, OWNER, "帮我补足现金缺口", session_id=f"s-{ord(tag[0])}")
    print("plan reply:", out["reply"][:200].replace("\n", " | "), "awaiting", out.get("awaiting_confirmation"))
    b = snap(rt, f"before {tag}")
    out = nl(c, OWNER, tag, session_id=f"s-{ord(tag[0])}")
    print(f"{tag} reply:", out["reply"][:200].replace("\n", " | "))
    print("operations:", [(o.get("kind"), o.get("status")) for o in out.get("operations", [])])
    a = snap(rt, f"after {tag}")
    check(f"the tag question {tag!r} ('right?') ran the pending plan", a["log_len"] > b["log_len"] and a["drawn"] != b["drawn"])
