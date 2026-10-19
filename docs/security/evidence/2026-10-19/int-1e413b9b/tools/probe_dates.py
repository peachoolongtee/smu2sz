import sys, json, importlib.util
spec = importlib.util.spec_from_file_location("rs", sys.argv[1]); rs = importlib.util.module_from_spec(spec); sys.modules["rs"]=rs; spec.loader.exec_module(rs)
t = rs.InProc()
msgs = [
 "We can pay the ¥420,000 invoice tomorrow at a 0.5% discount.",
 "We won't pay the ¥420,000 invoice tomorrow at a 0.5% discount.",
 "We can't pay the ¥420,000 invoice tomorrow at a 0.5% discount.",
 "We will never pay the ¥420,000 invoice tomorrow at a 0.5% discount.",
 "We can pay half of the ¥420,000 invoice tomorrow at a 0.5% discount.",
 "We can pay the ¥420,000 invoice tomorrow at a 0.5% discount, and the same 0.5% on every future invoice.",
 "We can pay the ¥420,000 invoice tomorrow at a 0.5% discount once the goods pass inspection.",
 "我们明天不会以0.5%的折扣支付¥420,000的发票。",
 "我们明天可以以0.5%的折扣支付¥420,000的发票。",
 "We can pay the ¥420,000 invoice within 5 days at a 0.5% discount.",
 "We can pay the ¥420,000 invoice within 50 days at a 0.5% discount.",
 "We could pay the ¥420,000 invoice tomorrow at a 0.5% discount if you also extend our next invoice by 30 days.",
]
for i, m in enumerate(msgs):
    t.call("POST", "/demo/reset", "OWNER"); t.after_reset()
    s, b, _ = t.call("POST", "/nl", "BUYER-1", {"session_id": f"n{i}", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": m})
    v = b.get("verdict") or {}
    ops = [f"{o.get('kind')}:{o.get('status') or (o.get('result') or {}).get('status')}" for o in (b.get("operations") or [])]
    s2, q, _ = t.call("GET", "/approvals/queue", "OWNER")
    items = q if isinstance(q, list) else next((x for x in q.values() if isinstance(x, list)), [])
    print(f"[{i}] {m}\n    status {s} decision={v.get('decision')} notes={v.get('autonomy_notes')} ops={ops} queue={[a.get('kind') for a in items]}\n    reply: {(b.get('reply') or '')[:160]}")
