"""The egress guard against the reserve floor (¥300,000), the line limit (¥150,000) and the line rate (6.4%) written in
unusual forms in a text bound for BUYER-1. Prints which forms are caught (a leak found) and which pass."""
from _harness import *  # noqa
from app.egress import ProtectedSet, scan

rt, c = fresh()
ps = ProtectedSet.build(rt.store.get_state(), rt.store.get_mandate())
forms = ["¥300,000", "¥300000", "300,000 yuan", "¥30万", "30万元", "三十万元", "叁拾万元", "300 000 RMB", "３００，０００元",
         "¥300,\n000", "RMB 300k", "¥0.3 million", "300 thousand yuan", "three hundred thousand yuan", "CNY300000.00",
         "¥ 3 0 0 , 0 0 0", "¥300.000", "¥299,999.99 plus one fen", "¥150,000", "15万", "一十五万元", "6.4%", "6.40 %",
         "640 bp", "百分之六点四", "６．４％", "0.064", "6,4%", "six point four percent"]
caught, missed = [], []
for f in forms:
    text = f"For your information our figure is {f} this quarter."
    leaks = scan(text, ps, recipient_id="BUYER-1")
    (caught if leaks else missed).append((f, [x.label for x in leaks][:2]))
for f, labels in caught:
    print(f"  caught   {f!r:36} {labels}")
for f, _ in missed:
    print(f"  PASSES   {f!r}")
