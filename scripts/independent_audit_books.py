"""Read-only audit probes against isolated in-memory stores; never uses live credentials.

Run: services/api/.venv/bin/python scripts/independent_audit_books.py
These assert the observed defects at the audited revision, not desirable regression expectations.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["TERMSLEDGER_NO_DOTENV"] = "1"
os.environ["DATABASE_URL"] = "memory"
os.environ["LLM_MODE"] = "cache"
os.environ["DEMO_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))

from fastapi.testclient import TestClient
from app.api.runtime import Runtime, set_runtime
from app.config import Settings
from app.covenants import evaluate as covenants
from app.domain.models import FundingAction, FundingActionKind, Mode
from app.domain.money import bp, post
from app.financial import project
from app.mandate.fixture import demo_owner_public_key_hex
from app.main import app
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {**AGENT, "X-Bank-Feed-Key": "demo-bank-feed-key"}


def fresh():
    rt = Runtime(Settings(), InMemoryLedgerStore(), demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    return rt, TestClient(app)


def operation(c, kind, key, headers=AGENT, actor="AGENT", **fields):
    response = c.post("/operations", headers=headers, json={"kind": kind, "op_id": key,
        "idempotency_key": key, "mandate_version": 1, "requested_by": actor, **fields})
    assert response.status_code == 200, response.text
    return response.json()["result"]


def report(case, **facts):
    print(json.dumps({"case": case, **facts}, ensure_ascii=False))


def main():
    rt, c = fresh()
    operation(c, "RECEIVE_PAYMENT", "partial", BANK, "SYSTEM", receivable_id="RCV-A", amount_fen=35_000_000)
    before = rt.store.get_state()
    try:
        project(before, [], [FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id="FAC-IF",
                receivable_id="RCV-A", day=0, amount_fen=10_000_000)], Mode.CONSERVATIVE, 90)
        planner_error = None
    except Exception as e:
        planner_error = str(e)
    res = operation(c, "SUBMIT_INVOICE_FOR_FINANCING", "advance-partial", facility_id="FAC-IF",
                    receivable_id="RCV-A", advance_fen=10_000_000)
    assert res["status"] == "EXECUTED" and planner_error is not None
    report("advance_exceeds_remaining_invoice", outstanding_fen=before.receivables[0].outstanding_fen,
           advance_fen=10_000_000, planner_error=planner_error, executor=res)

    rt, c = fresh()
    c.post("/clock/advance", headers=OWNER, json={"to_day": 31})
    before = rt.store.get_state()
    try:
        project(before, [], [FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id="FAC-IF",
                receivable_id="RCV-A", day=31, amount_fen=10_000_000)], Mode.CONSERVATIVE, 90)
        planner_error = None
    except Exception as e:
        planner_error = str(e)
    res = operation(c, "SUBMIT_INVOICE_FOR_FINANCING", "late-advance", facility_id="FAC-IF",
                    receivable_id="RCV-A", advance_fen=10_000_000)
    assert res["status"] == "EXECUTED" and planner_error is not None
    report("funds_before_lead_time", day=rt.day, cash_change_fen=rt.store.get_state().cash_fen-before.cash_fen,
           planner_error=planner_error, executor=res)

    rt, c = fresh()
    s = rt.store.get_state()
    # Controlled, legitimate business input: lender's committed tariff exceeds owner's APR maximum.
    rt.store.put_state(s.model_copy(update={"facilities": [f.model_copy(update={"rate_bp": 3000})
                            if f.id == "FAC-IF" else f for f in s.facilities]}))
    res = operation(c, "SUBMIT_INVOICE_FOR_FINANCING", "apr-bypass", facility_id="FAC-IF",
                    receivable_id="RCV-A", advance_fen=10_000_000)
    assert res["status"] == "EXECUTED" and res["tier"] == "TIER_1"
    report("direct_agent_apr_bypass", facility_rate_bp=3000, mandate_max_apr_bp=rt.store.get_mandate().max_apr_bp,
           executor=res)

    rt, c = fresh()
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"monthly_ebitda_fen": 100_000}))
    res = operation(c, "DRAW_FACILITY", "dscr-bypass", facility_id="FAC-LINE", amount_fen=10_000_000)
    t = project(rt.store.get_state(), [], [], Mode.CONSERVATIVE, 90, rt.store.get_mandate().min_cash_fen)
    failures = covenants(t, rt.store.get_state().facilities, rt.store.get_mandate())
    assert res["status"] == "EXECUTED" and any(v.code.value == "DSCR_BREACH" for v in failures)
    report("direct_agent_covenant_bypass", executor=res, violations=sorted({v.code.value for v in failures}))

    rt, c = fresh()
    oid = c.post("/offers", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"})
    deal = c.post(f"/negotiate/{oid}", headers=OWNER, json={"buyer_profile": "cooperative"})
    assert deal.status_code == 200, deal.text
    com = rt.store.get_commitment(deal.json()["commitment"]["id"])
    ob = com.obligations[0]
    face = ob.base.amount_fen
    agreed = face - post(bp(ob.rate_bp) * face)
    c.post("/clock/advance", headers=OWNER, json={"to_day": 34})
    before = rt.store.get_state()
    res = operation(c, "RECEIVE_PAYMENT", "late-discount", BANK, "SYSTEM", receivable_id=ob.base.receivable_id,
                    amount_fen=agreed)
    r = next(r for r in rt.store.get_state().receivables if r.id == ob.base.receivable_id)
    assert r.settled_fen == face and rt.store.get_commitment(com.id).status.value == "FULFILLED"
    report("expired_early_payment_discount_still_granted", promised_day=ob.effective_day, actual_day=rt.day,
           receipt_fen=agreed, face_settled_fen=r.settled_fen, discount_fen=face-agreed, executor=res)

    rt, c = fresh()
    res = operation(c, "DRAW_FACILITY", "line-draw", facility_id="FAC-LINE", amount_fen=15_000_000)
    c.post("/clock/advance", headers=OWNER, json={"to_day": 2})
    operation(c, "RECEIVE_PAYMENT", "full-receipt", BANK, "SYSTEM", receivable_id="RCV-A", amount_fen=42_000_000)
    t = project(rt.store.get_state(), [], [], Mode.CONSERVATIVE, 90, rt.store.get_mandate().min_cash_fen)
    repayments = [(d.day, e.amount_fen) for d in t.days for e in d.events if e.kind.value == "REPAYMENT" and e.ref == "FAC-LINE"]
    day = repayments[0][0]
    cash = rt.store.get_state().cash_fen
    c.post("/clock/advance", headers=OWNER, json={"to_day": day+1})
    balance = next(f.drawn_fen for f in rt.store.get_state().facilities if f.id == "FAC-LINE")
    assert balance == 15_000_000
    report("projection_repayment_never_posted_by_clock", projected_repayment=repayments[0], current_day=rt.day,
           actual_drawn_fen=balance, actual_cash_fen=rt.store.get_state().cash_fen, prior_cash_fen=cash)
    set_runtime(None)


if __name__ == "__main__":
    main()
