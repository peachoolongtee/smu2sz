"""Baseline: project on day 0, let exactly the projected receipts arrive, close days to 119. Compare."""
from _harness import *  # noqa

rt, c = fresh()
t = projection(rt)
for p in t.days[:130]:
    if p.events:
        print(p.day, p.closing_fen, [(e.kind.value, e.amount_fen, e.ref, e.label[:50]) for e in p.events])
diffs = live(c, rt, t, 119)
print("diffs", diffs[:20])
snap(rt, "end")
print(conservation(rt))
print(rt.store.verify_chain())
