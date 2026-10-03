"""The consent grammar's executing answers on tricky English, Chinese and mixed messages (pure functions)."""
from _harness import *
from app.nl.consent import approval_verdict, bare_verdict, confirmation, money_gate, parse_command

rt, c = fresh()
st = rt.store.get_state()
cmds = [
    "draw ¥100,000 on the line", "draw ¥100,000 on the line now", "draw ¥100,000 on the line tomorrow",
    "don't draw ¥100,000 on the line", "draw ¥100,000 on the line?", "draw ¥1,000,000 on the line",
    "draw ¥100,000.001 on the line", "draw ¥0.01 on the line", "draw 10万元 on the line", "draw ¥10万 on the line",
    "从授信额度提款10万元", "从额度提10万", "提10万元从额度", "不从额度提款10万元", "从授信额度提款10万元吗",
    "现在从额度提款10万元吧", "从额度里提出10万元出来", "还额度10万元", "还了额度10万元", "别还额度10万元",
    "repay ¥150,000 on the line", "pay off the line by ¥150,000", "pay back ¥150,000 to the facility",
    "draw ¥100,000 on the facility", "draw rmb 100k on fac-if", "draw ¥100,000 on factoring",
    "please now draw ¥100,000 on the line thanks", "draw ¥100,000 on the line please now please",
    "draw ¥ 100,000 on the line", "draw ¥100 000 on the line", "draw ¥１００，０００ on the line",
    "draw ¥100,000 on our line, then", "pull ¥100,000 from the line", "take out ¥100,000 out of the line",
    "借10万元从额度", "提款 10 万元 从 授信额度", "从发票融资提款10万元", "向额度还10万元",
    "draw ¥100,000 on the line immediately right away", "draw ¥100,000 on the line now now now",
    "don’t draw ¥100,000 on the line",
]
for t in cmds:
    print(f"CMD  {t!r:52} -> {parse_command(t, st)}  gate={money_gate(t)}")
confs = ["go ahead", "yes", "ok then", "好的", "确认", "行吧", "对吧", "好了", "可以了", "不", "不行", "go ahead?",
         "go ahead if cash is low", "yes but not the line", "yes, not now", "sure, do it now please", "do it",
         "approve it", "okay fine", "great", "that works", "执行", "不执行", "办吧", "做吧", "继续", "开始", "对",
         "fine then", "ok thanks", "yes yes no", "no, go ahead", "nah go ahead", "go ahead, cancel", "嗯",
         "yes 不", "go ahead 不要", "proceed, never", "ok and then", "可以吧", "行不", "确定吗", "确定吧", "就这么办",
         "yes!", "yes.", "yes。", "yes~", "Yes!!!", "ok 👍", "y", "k", "ok?", "ok…", "好的，谢谢", "是吧"]
for t in confs:
    print(f"CONF {t!r:30} -> {confirmation(t)}")
apps = ["approve APR-000001", "yes, approve APR-000001", "批准 APR-000001", "不批准 APR-000001", "不同意 APR-000001",
        "同意 APR-000001", "approve APR-000001?", "approve APR-000001 thanks", "approve the APR-000001",
        "do not approve APR-000001", "don't approve APR-000001", "approve APR-000001, not", "ok approve APR-000001",
        "no approve APR-000001", "不，批准 APR-000001", "好的批准APR-000001", "批准APR-000001吧", "可以，批准 APR-000001",
        "approve APR-000001 APR-000002", "approve apr-000001", "Approve APR‑000001", "approve APR-0000001",
        "approve operation APR-000001 please", "decline APR-000001", "reject APR-000001", "不要批准 APR-000001",
        "approve APR-000001 不", "approve APR-000001 吧", "approve APR-000001 啊", "approve APR-000001 謝謝"]
for t in apps:
    print(f"APR  {t!r:40} -> {approval_verdict(t)}")
bares = ["approve it", "approve that", "批准", "批准这个", "不批准", "approve the pending one", "yes approve it",
         "no approve it", "approve", "approve!", "approve it?", "please approve it thanks", "同意", "不同意", "审批通过",
         "approve this", "好，批准", "对批准", "嗯批准", "可以批准"]
for t in bares:
    print(f"BARE {t!r:30} -> {bare_verdict(t)}")
