"""Audit A05 and A09: the executor admits a funding operation only if the planner's engine and predicates
would, and a late receipt does not earn an early-payment discount. Each case asserts stored state."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import Settings
from app.domain.models import CommitmentStatus
from app.domain.money import bp, post
from app.main import app
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {**AGENT, "X-Bank-Feed-Key": "demo-bank-feed-key"}


@pytest.fixture
def api():
    rt = Runtime(Settings(), InMemoryLedgerStore(), demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    yield rt, TestClient(app)
    set_runtime(None)


def op(c, kind, key, headers=AGENT, actor="AGENT", **fields):
    r = c.post("/operations", headers=headers, json={"kind": kind, "op_id": key, "idempotency_key": key,
                                                     "mandate_version": 1, "requested_by": actor, **fields})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def facility(rt, fid):
    return next(f for f in rt.store.get_state().facilities if f.id == fid)


def receivable(rt, rid):
    return next(r for r in rt.store.get_state().receivables if r.id == rid)


def test_advance_is_capped_by_the_outstanding_face_not_the_original(api):
    rt, c = api
    op(c, "RECEIVE_PAYMENT", "partial", BANK, "SYSTEM", receivable_id="RCV-A", amount_fen=35_000_000)
    before = rt.store.get_state()
    assert receivable(rt, "RCV-A").outstanding_fen == 7_000_000
    res = op(c, "SUBMIT_INVOICE_FOR_FINANCING", "too-much", facility_id="FAC-IF", receivable_id="RCV-A",
             advance_fen=10_000_000)
    assert res["status"] == "REFUSED"
    after = rt.store.get_state()
    assert after.cash_fen == before.cash_fen and facility(rt, "FAC-IF").drawn_fen == 0
    assert receivable(rt, "RCV-A").status == "OPEN"
    # 80% of the outstanding ¥70,000 is ¥56,000: at the limit it is admitted, one fen above it is not
    assert op(c, "SUBMIT_INVOICE_FOR_FINANCING", "one-over", facility_id="FAC-IF", receivable_id="RCV-A",
              advance_fen=5_600_001)["status"] == "REFUSED"


def test_advance_that_would_land_on_or_after_the_due_day_is_refused(api):
    rt, c = api
    c.post("/clock/advance", headers=OWNER, json={"to_day": 31})
    before = rt.store.get_state().cash_fen
    res = op(c, "SUBMIT_INVOICE_FOR_FINANCING", "late", facility_id="FAC-IF", receivable_id="RCV-A",
             advance_fen=10_000_000)
    assert res["status"] == "REFUSED" and "too late" in res["message"]
    assert rt.store.get_state().cash_fen == before and facility(rt, "FAC-IF").drawn_fen == 0


def test_rate_above_the_ceiling_waits_for_the_owner_and_runs_once_approved(api):
    rt, c = api
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"facilities": [
        f.model_copy(update={"rate_bp": 3000}) if f.id == "FAC-IF" else f for f in s.facilities]}))
    res = op(c, "SUBMIT_INVOICE_FOR_FINANCING", "dear", facility_id="FAC-IF", receivable_id="RCV-A",
             advance_fen=10_000_000)
    assert res["status"] == "PENDING_APPROVAL" and res["tier"] == "TIER_2"
    assert "ceiling" in res["message"]
    assert rt.store.get_state().cash_fen == s.cash_fen and facility(rt, "FAC-IF").drawn_fen == 0
    done = c.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"})
    assert done.status_code == 200, done.text
    assert facility(rt, "FAC-IF").drawn_fen == 10_000_000


def test_draw_that_breaches_dscr_is_refused_for_the_agent(api):
    rt, c = api
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"monthly_ebitda_fen": 100_000}))
    res = op(c, "DRAW_FACILITY", "dscr", facility_id="FAC-LINE", amount_fen=10_000_000)
    assert res["status"] == "REFUSED"
    assert {v["code"] for v in res["violations"]} & {"DSCR_BREACH", "LEVERAGE_BREACH"}
    assert rt.store.get_state().cash_fen == s.cash_fen and facility(rt, "FAC-LINE").drawn_fen == 0


def test_golden_plan_legs_are_still_admitted(api):
    _rt, c = api
    assert op(c, "DRAW_FACILITY", "line", facility_id="FAC-LINE", amount_fen=15_000_000)["status"] == "EXECUTED"
    assert op(c, "SUBMIT_INVOICE_FOR_FINANCING", "if", facility_id="FAC-IF", receivable_id="RCV-A",
              advance_fen=21_000_000)["status"] == "EXECUTED"


def test_repayment_that_takes_cash_below_the_reserve_is_refused(api):
    rt, c = api
    assert op(c, "DRAW_FACILITY", "line", facility_id="FAC-LINE", amount_fen=15_000_000)["status"] == "EXECUTED"
    s = rt.store.get_state()
    floor = rt.store.get_mandate().min_cash_fen
    rt.store.put_state(s.model_copy(update={"cash_fen": floor + 10_000_000, "state_version": s.state_version + 1}))
    res = op(c, "REPAY_FACILITY", "repay", facility_id="FAC-LINE", amount_fen=15_000_000)
    assert res["status"] == "REFUSED"
    assert facility(rt, "FAC-LINE").drawn_fen == 15_000_000


def _counter_a(rt, c):
    oid = c.post("/offers", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"})
    deal = c.post(f"/negotiate/{oid}", headers=OWNER, json={"buyer_profile": "cooperative"})
    assert deal.status_code == 200, deal.text
    com = rt.store.get_commitment(deal.json()["commitment"]["id"])
    ob = com.obligations[0]
    face = ob.base.amount_fen
    return com, ob, face, face - post(bp(ob.rate_bp) * face)


@pytest.mark.parametrize("pay_day, discounted", [(1, True), (2, True), (3, False), (34, False)])
def test_discount_is_earned_only_by_the_promised_day(api, pay_day, discounted):
    rt, c = api
    com, ob, face, agreed = _counter_a(rt, c)
    assert ob.effective_day == 2
    c.post("/clock/advance", headers=OWNER, json={"to_day": pay_day})
    res = op(c, "RECEIVE_PAYMENT", "receipt", BANK, "SYSTEM", receivable_id=ob.base.receivable_id, amount_fen=agreed)
    assert res["status"] == "EXECUTED"
    r = receivable(rt, ob.base.receivable_id)
    status = rt.store.get_commitment(com.id).status
    if discounted:
        assert r.settled_fen == face and status == CommitmentStatus.FULFILLED
    else:  # a plain receipt: the cash is booked, only that much face is settled, the discount is not granted
        assert r.settled_fen == agreed and status != CommitmentStatus.FULFILLED
