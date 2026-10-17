"""OUT-1 residual probe on 719c9dcf: after the owner marks a counter sent outside FLOW, can POST /operations (owner token or agent key)
still answer the buyer's request (RejectOffer, CounterOffer, AcceptOffer on an existing proposal)? Run from services/api."""
import json, os, sys
sys.path.insert(0, r"C:\Users\ian\Documents\Projects\smu2sz\.claude\worktrees\sec-fix3\docs\security\evidence\2026-10-16\dev-b8c65b24")
from common import *
from fastapi.testclient import TestClient
from app.operations.log import read_entries

for who in ("owner", "agent"):
    rt, api, app = fresh()
    oid, v, m = sent(api)
    c = api if who == "owner" else TestClient(app, headers={"X-Agent-Key": AGENT})
    day = rt.day
    props = [x for x in rt.store.commitments() if x.offer_id == oid]
    print(who, "proposals after mark:", [(x.id, x.status) for x in props])
    base = {"requested_by": "OWNER" if who == "owner" else "AGENT", "mandate_version": rt.store.get_mandate().version, "day": day}
    rej = {**base, "kind": "REJECT_OFFER", "op_id": f"probe-rej-{who}", "idempotency_key": f"probe-rej-{who}",
           "source_verdict_id": v["id"], "offer_id": oid, "reason_codes": []}
    r = c.post("/operations", json=rej); print(who, "RejectOffer:", r.status_code, (r.json().get("result") or {}).get("status") if r.status_code == 200 else r.text[:160])
    cnt = {**base, "kind": "COUNTER_OFFER", "op_id": f"probe-cnt-{who}", "idempotency_key": f"probe-cnt-{who}",
           "source_verdict_id": v["id"], "offer_id": oid, "counter_id": m["counter_id"]}
    r = c.post("/operations", json=cnt); print(who, "CounterOffer:", r.status_code, (r.json().get("result") or {}).get("status") if r.status_code == 200 else r.text[:200])
    for p in props:
        acc = {**base, "kind": "ACCEPT_OFFER", "op_id": f"probe-acc-{who}", "idempotency_key": f"probe-acc-{who}", "source_verdict_id": v["id"],
               "offer_id": oid, "offer_version": p.offer_version, "terms_hash": p.terms_hash, "nonce": p.nonce}
        r = c.post("/operations", json=acc); print(who, "AcceptOffer on", p.id, ":", r.status_code, (r.json().get("result") or {}).get("status") if r.status_code == 200 else r.text[:200])
    e, _ = read_entries(rt.store.operations())
    print(who, "log for offer:", [(x.kind, x.result.status.value, x.payload.get("requested_by")) for x in e if x.payload.get("offer_id") == oid])
    print(who, "decision state:", decision(api, oid).get("state"))
