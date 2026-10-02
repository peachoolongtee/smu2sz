"""Explore: how dated terms/price offers compile and value (window W = [today, today + 365))."""
from _harness import *  # noqa: F403

TEXTS = [
    "Give us 60 days instead of 45 on all invoices from next year. Nothing else changes.",
    "Starting in 13 months, move us to 60-day terms going forward.",
    "From 1 January 2028 our standard terms will be 60 days instead of 45.",
    "Give us 60 days instead of 45 on all invoices issued after day 400.",
    "Give us 60 days instead of 45 going forward.",
    "Give us 60 days instead of 45 on the next 12 invoices.",
]
rt, c = fresh()
for i, text in enumerate(TEXTS):
    docs = [{"doc_id": f"D-{i}", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0, "text": text}]
    o = c.post("/offers", json={"counterparty_id": "BUYER-1", "documents": docs}).json()["offer"]
    v = c.post(f"/offers/{o['offer_id']}/evaluate", headers=OWNER, json={}).json()
    obs = [(b["type"], b.get("days_delta"), b.get("effective_day"), b["duration"]["kind"], b["duration"].get("invoices"),
            b["duration"].get("end_day")) for b in v.get("bound_obligations", [])]
    print(repr(text))
    print("   ", v["outcome"], v.get("forward_concession_total_fen"), sorted({x["code"] for x in v.get("violations", [])}),
          obs, [cv["formula"][:70] for cv in v.get("concession_values", [])])
