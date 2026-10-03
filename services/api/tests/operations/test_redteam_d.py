"""Regression tests for the fourth red team of 3 Oct 2026 (docs/research/redteam-2026-10-03d): F1 to F7.

Each test asserts the stored state (the store's FinancialState, commitments, approvals and log), not only a reply or
a message. F4 (the consent grammar) is tested in tests/nl/test_consent.py and F6 (reconciliation) also in
tests/alerts/test_reconcile_promises.py.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.api.decide as decide_mod
from app.alerts import MatchStatus, PromiseStatus, reconcile
from app.api.runtime import Runtime, set_runtime
from app.books import current_books
from app.clock import advance, close_days
from app.config import get_settings
from app.domain.models import (
    AcceptOffer,
    Actor,
    AddFacility,
    BaseKind,
    CommitmentStatus,
    Contingency,
    CostLine,
    DrawFacility,
    Duration,
    DurationKind,
    Facility,
    FundingAction,
    FundingActionKind,
    FundingPlan,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    OperationStatus,
    ReceivePayment,
    ViolationCode,
)
from app.domain.money import bp, post
from app.financial import project
from app.funding import plan
from app.funding.search import Search
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.nl.plans import legs_from_plan, runnable_legs
from app.persistence import InMemoryLedgerStore
from tests.funding import cases
from tests.operations.builders import Clock, early_pay, make_executor, op, seed_offer, seeded_store, span

EXECUTED, REFUSED, PENDING = OperationStatus.EXECUTED, OperationStatus.REFUSED, OperationStatus.PENDING_APPROVAL
OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
BUYER1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
RCV_A = 42_000_000


@pytest.fixture
def rt() -> Any:
    r = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    r.reset()
    set_runtime(r)
    reset_sessions()
    yield r
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def client(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app)


def post_op(client: TestClient, rt: Runtime, headers: dict, body: dict) -> dict:
    body = {"mandate_version": rt.store.get_mandate().version, "day": rt.day, **body}
    body.setdefault("idempotency_key", body["op_id"])
    r = client.post("/operations", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()["result"]


def move(client: TestClient, day: int) -> None:
    assert client.post("/clock/advance", json={"to_day": day}, headers=OWNER).status_code == 200


def say(client: TestClient, text: str, session: str = "rtd") -> dict:
    r = client.post("/nl", headers=OWNER, json={"text": text, "actor": "OWNER", "session_id": session})
    assert r.status_code == 200, r.text
    return r.json()


def rcv(rt: Runtime, rid: str = "RCV-A") -> Any:
    return next(r for r in rt.store.get_state().receivables if r.id == rid)


def drawn(rt: Runtime) -> dict[str, int]:
    return {f.id: f.drawn_fen for f in rt.store.get_state().facilities if f.drawn_fen}


def breach_day(rt: Runtime) -> int | None:
    books = current_books(rt.store.get_state(), rt.store.commitments())
    m = rt.store.get_mandate()
    return project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, m.horizon_days,
                   m.min_cash_fen).first_breach_day


PRICED = (FundingActionKind.EARLY_PAY, FundingActionKind.DISCOUNT_BILL)


# ================================================================ F1: early pay and bill legs never run silently


def test_f1_the_router_flags_early_pay_and_bill_legs_as_not_runnable_today() -> None:
    s, m = cases.no_new_borrowing()  # only the buyer's early payment can fund this gap
    p = plan(s, [], m)
    assert p.admissible and [a.kind for a in p.actions] == [FundingActionKind.EARLY_PAY]
    assert p.executable_now is False and "needs the buyer's agreement to pay early" in p.not_executable_reason
    assert [c.executable_now for c in p.costs] == [False]
    s, m = cases.bill_held()
    search = Search(s, [], m, "COMMITTED")
    bill = FundingAction(kind=FundingActionKind.DISCOUNT_BILL, facility_id=next(
        f.id for f in s.facilities if f.kind.value == "BANK_ACCEPTANCE_BILL"), day=0, amount_fen=1_000_000)
    assert search.unrunnable(bill) == "needs a bill in hand"
    # where a line and an advance can fund the gap, that plan wins (the golden ¥3,113.93), not the cheaper bill
    p = plan(s, [], m)
    assert p.executable_now and p.total_cost_fen == 311_393 and not any(a.kind in PRICED for a in p.actions)


def _plan_with_early_pay(executable_now: bool) -> FundingPlan:
    actions = [FundingAction(kind=FundingActionKind.EARLY_PAY, facility_id="FAC-EARLYPAY", day=0, amount_fen=1_000_000,
                             receivable_id="RCV-A", rate_bp=120)]
    costs = [CostLine(label="Buyer early-payment offer: early payment", fen=12_000, facility_id="FAC-EARLYPAY",
                      formula="test", executable_now=executable_now,
                      not_executable_reason="" if executable_now else "needs the buyer's agreement to pay early")]
    return FundingPlan(id="PLAN-T", basis="COMMITTED", need_fen=1_000_000, actions=actions, costs=costs,
                       total_cost_fen=12_000, admissible=True, executable_now=executable_now,
                       not_executable_reason="" if executable_now else "Buyer early-payment offer: needs the buyer's "
                                                                       "agreement to pay early")


@pytest.mark.parametrize("flagged", [True, False])
def test_f1_a_plan_with_an_early_pay_leg_yields_no_legs_to_send(flagged: bool) -> None:
    ctx: Any = SimpleNamespace(lang="en")
    p = _plan_with_early_pay(executable_now=not flagged)
    legs, note = runnable_legs(ctx, p)
    assert legs == [] and "cannot run today" in note
    with pytest.raises(ValueError):
        legs_from_plan(ctx, p)  # never a partial list that silently leaves the early-pay leg out
    assert decide_mod._runnable(p) is not None


def test_f1_chat_go_ahead_runs_a_plan_that_cures_the_gap_and_no_early_pay_leg(client: TestClient, rt: Runtime) -> None:
    """p09: with EX01's Option B in force the router used to plan on the buyer's early-pay programme; the go-ahead
    ran the draw and the advance only, said "cost as quoted" and left the reserve breach the plan was sized for."""
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"}).json()
    b = next(k for k in v["counters"] if "terms" in k["text"])
    cm = rt.executor.propose_commitment(v["id"], expires_day=rt.day + 7, counter_id=b["id"])
    res = post_op(client, rt, AGENT, {"kind": "ACCEPT_OFFER", "op_id": "accept-b", "requested_by": "AGENT",
                                      "source_verdict_id": v["id"], "offer_id": cm.offer_id,
                                      "offer_version": cm.offer_version, "terms_hash": cm.terms_hash, "nonce": cm.nonce})
    if res["status"] == "PENDING_APPROVAL":
        r = client.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"})
        assert r.json()["result"]["status"] == "EXECUTED"
    committed = client.post("/router/plan", headers=OWNER).json()["committed"]
    assert committed["executable_now"] and not any(a["kind"] in ("EARLY_PAY", "DISCOUNT_BILL")
                                                   for a in committed["actions"])
    assert breach_day(rt) is not None
    say(client, "fund the cash gap")
    say(client, "3")
    out = say(client, "go ahead")
    ran = [(o["kind"], o["status"]) for o in out["operations"]]
    assert ran and all(s == "EXECUTED" for _, s in ran)
    # the books hold exactly the plan's legs, and nothing the plan was sized for is left uncured
    want: dict[str, int] = {}
    for a in committed["actions"]:
        want[a["facility_id"]] = want.get(a["facility_id"], 0) + a["amount_fen"]
    assert drawn(rt) == want
    assert breach_day(rt) is None


def test_f1_negotiate_runs_nothing_from_a_plan_that_cannot_run(client: TestClient, rt: Runtime, monkeypatch) -> None:
    """p13: on NO DEAL /negotiate used to drop the plan's early-pay leg and still say the gap was funded."""
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", headers=OWNER, json={"fixture_id": "EX01_PACKAGE"})
    for flagged in (True, False):  # flagged by the router, or (defence in depth) not flagged
        monkeypatch.setattr(decide_mod, "plan", lambda *a, _f=flagged, **k: _plan_with_early_pay(not _f))
        before = (rt.store.get_state(), len(rt.store.operations()))
        n = client.post(f"/negotiate/{oid}", headers=OWNER, json={"buyer_profile": "hard_line"}).json()
        assert n["outcome"] == "NO_DEAL" and n["operations"] == []
        assert "not funded" in n["message"] and "funds the near-term gap" not in n["message"]
        assert "Nothing was executed" in n["message"]
        assert rt.store.get_state() == before[0] and drawn(rt) == {}


# ================================================================ F2: a queued agent receipt after the bank booked it


def test_f2_an_approved_agent_receipt_is_refused_when_the_bank_booked_the_receivable_since(
        client: TestClient, rt: Runtime) -> None:
    move(client, 10)
    q = post_op(client, rt, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rx", "requested_by": "AGENT",
                                    "receivable_id": "RCV-A", "amount_fen": 20_000_000})
    assert q["status"] == "PENDING_APPROVAL"
    cash0 = rt.store.get_state().cash_fen
    bank = post_op(client, rt, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "bank-rx", "requested_by": "SYSTEM",
                                      "receivable_id": "RCV-A", "amount_fen": 20_000_000})
    assert bank["status"] == "EXECUTED"
    r = client.post(f"/approvals/{q['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
    assert r["status"] == "REFUSED" and [v["code"] for v in r["violations"]] == ["PRECONDITION_FAILED"]
    assert "bank-rx" in r["message"] and f"seq {bank['seq']}" in r["message"]
    s = rt.store.get_state()
    assert s.cash_fen == cash0 + 20_000_000 and rcv(rt).settled_fen == 20_000_000  # booked once
    assert [a.status for a in rt.store.approvals()] == ["APPROVED"]  # the owner decided; the executor refused
    entries = [json.loads(o.result_json)["status"] for o in rt.store.operations() if o.kind == "RECEIVE_PAYMENT"]
    assert entries == ["PENDING_APPROVAL", "EXECUTED", "REFUSED"]


def test_f2_a_different_amount_booked_since_also_refuses(client: TestClient, rt: Runtime) -> None:
    q = post_op(client, rt, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rx2", "requested_by": "AGENT",
                                    "receivable_id": "RCV-A", "amount_fen": 20_000_000})
    post_op(client, rt, OWNER, {"kind": "RECEIVE_PAYMENT", "op_id": "owner-rx2", "requested_by": "OWNER",
                                "receivable_id": "RCV-A", "amount_fen": 5_000_000})
    r = client.post(f"/approvals/{q['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
    assert r["status"] == "REFUSED" and rcv(rt).settled_fen == 5_000_000


def test_f2_with_nothing_booked_since_the_approval_still_books_the_receipt(client: TestClient, rt: Runtime) -> None:
    q = post_op(client, rt, AGENT, {"kind": "RECEIVE_PAYMENT", "op_id": "agent-rx3", "requested_by": "AGENT",
                                    "receivable_id": "RCV-A", "amount_fen": 20_000_000})
    cash0 = rt.store.get_state().cash_fen
    r = client.post(f"/approvals/{q['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
    assert r["status"] == "EXECUTED"
    assert rt.store.get_state().cash_fen == cash0 + 20_000_000 and rcv(rt).settled_fen == 20_000_000


# ================================================================ F3: a lapsed early-pay agreement holds nothing


def _buyer_early_pay(client: TestClient, rt: Runtime) -> Any:
    client.post("/nl", headers=BUYER1, json={"text": "We can pay invoice RCV-A of ¥420,000 early at 0.6%. Nothing "
                                                     "else changes.", "actor": "COUNTERPARTY"})
    [cm] = rt.store.commitments()
    assert cm.status == CommitmentStatus.ACTIVE and cm.obligations[0].effective_day == 2
    return cm


def _finance(client: TestClient, rt: Runtime, op_id: str) -> dict:
    return post_op(client, rt, OWNER, {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": op_id, "requested_by": "OWNER",
                                       "facility_id": "FAC-IF", "receivable_id": "RCV-A", "advance_fen": 25_500_000})


def test_f3_a_live_agreement_refuses_financing_and_a_lapsed_one_does_not(client: TestClient, rt: Runtime) -> None:
    cm = _buyer_early_pay(client, rt)
    move(client, 1)
    r = _finance(client, rt, "fin-1")  # the promised day has not passed: the agreement is live
    assert r["status"] == "REFUSED" and [v["code"] for v in r["violations"]] == ["PRECONDITION_FAILED"]
    assert cm.id in r["message"] and "early-payment agreement" in r["message"]
    assert rcv(rt).status == "OPEN" and drawn(rt) == {}
    move(client, 3)  # day 2 passed unpaid
    ended = rt.store.get_commitment(cm.id)
    assert ended.status == CommitmentStatus.EXPIRED and ended.lapsed_obligations == [cm.obligations[0].id]
    clock = [json.loads(o.payload_json) for o in rt.store.operations() if o.kind == "ADVANCE_CLOCK"][-1]
    assert clock["lapsed_commitment_ids"] == [cm.id]
    books = current_books(rt.store.get_state(), rt.store.commitments())
    assert books.obligations == () and [(x.commitment_id, x.reason) for x in books.lapsed] == [
        (cm.id, "EARLY_PAYMENT_MISSED")]  # the owner still sees what did not arrive
    r = _finance(client, rt, "fin-3")
    assert r["status"] == "EXECUTED", r["message"]
    assert rcv(rt).status == "FINANCED" and drawn(rt) == {"FAC-IF": 25_500_000}
    alerts = client.get("/alerts", headers=OWNER).json()["alerts"]
    assert any(a["commitment_id"] == cm.id and a["receivable_id"] == "RCV-A" for a in alerts)


def test_f3_the_alert_cure_runs_once_the_agreement_lapsed(client: TestClient, rt: Runtime) -> None:
    """p03: the cure button used to draw the line and have the advance refused, leaving the breach ahead."""
    _buyer_early_pay(client, rt)
    move(client, 3)
    alert = next(a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")
    r = client.post(f"/alerts/{alert['id']}/act", headers=OWNER).json()
    assert r["executed"] == len(alert["suggested"]) and r["refused"] == 0 and r["cured"] is True
    assert rcv(rt).status == "FINANCED" and breach_day(rt) is None


def _mixed(oid: str = "OFF-MIX") -> list[Obligation]:
    ep = early_pay("OB-EP", rate_bp=60).model_copy(update={"effective_day": 2})
    terms = Obligation(id="OB-TE", type=ObligationType.TERMS_EXTENSION, counterparty_id=ep.counterparty_id,
                       days_delta=5, base=ObligationBase(kind=BaseKind.FUTURE_INVOICES), contingency=Contingency.FIRM,
                       duration=Duration(kind=DurationKind.RECURRING_PERPETUAL), spans=[span("terms +5 days")],
                       confidence=0.9)
    price = Obligation(id="OB-PA", type=ObligationType.PRICE_ADJUSTMENT, counterparty_id=ep.counterparty_id,
                       rate_bp=50, base=ObligationBase(kind=BaseKind.FUTURE_INVOICES), contingency=Contingency.FIRM,
                       duration=Duration(kind=DurationKind.RECURRING_PERPETUAL), spans=[span("price +0.5%")],
                       confidence=0.9)
    return [ep, terms, price]


def _accept(store: Any, ex: Any, clock: Clock, offer_id: str, obligations: list[Obligation]) -> Any:
    c = seed_offer(store, ex, offer_id, obligations=obligations, value_fen=0, expires_day=clock.day + 7)
    r = ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=c.offer_version, terms_hash=c.terms_hash,
                      nonce=c.nonce))
    if r.status == PENDING:
        r = ex.decide(r.approval_id, True, Actor.OWNER)
    assert r.status == EXECUTED, r.message
    return store.get_commitment(c.id)


def test_f3_a_lapsed_early_payment_in_a_package_leaves_the_package_active_and_revocable() -> None:
    store, clock = seeded_store("memory"), Clock(0)
    ex = make_executor(store, clock)
    c = _accept(store, ex, clock, "OFF-MIX", _mixed())
    advance(store, 5)
    clock.day = 5
    kept = store.get_commitment(c.id)
    assert kept.status == CommitmentStatus.ACTIVE and kept.lapsed_obligations == []
    assert ex.revoke_commitment(c.id, Actor.OWNER).status == EXECUTED
    assert store.get_commitment(c.id).status == CommitmentStatus.REVOKED
    assert not any(a.commitment_id == c.id for a in store.get_state().invoice_adjustments)


# ================================================================ F5: an early receipt does not close a package


def test_f5_an_early_receipt_settles_its_obligation_and_keeps_the_package_active() -> None:
    store, clock = seeded_store("memory"), Clock(0)
    ex = make_executor(store, clock)
    c = _accept(store, ex, clock, "OFF-PKG", _mixed())
    adjustments = [a.id for a in store.get_state().invoice_adjustments if a.commitment_id == c.id]
    assert len(adjustments) == 2
    agreed = RCV_A - post(bp(60) * RCV_A)
    r = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=agreed))
    assert r.status == EXECUTED and "early-payment discount" in r.message
    after = store.get_commitment(c.id)
    assert after.status == CommitmentStatus.ACTIVE and after.settled_obligations == ["OB-EP"]
    s = store.get_state()
    assert next(x for x in s.receivables if x.id == "RCV-A").status == "SETTLED"
    assert [a.id for a in s.invoice_adjustments if a.commitment_id == c.id] == adjustments
    # the paid early payment is neither live nor lapsed on the books
    books = current_books(s, store.commitments())
    assert books.obligations == () and books.lapsed == ()
    # the clock does not end it (it is not only early pay) and the owner can still revoke its perpetual terms
    advance(store, 3)
    clock.day = 3
    assert store.get_commitment(c.id).status == CommitmentStatus.ACTIVE
    assert ex.revoke_commitment(c.id, Actor.OWNER).status == EXECUTED
    assert store.get_commitment(c.id).status == CommitmentStatus.REVOKED
    assert not [a for a in store.get_state().invoice_adjustments if a.commitment_id == c.id]


def test_f5_an_early_pay_only_commitment_is_still_fulfilled_by_its_receipt() -> None:
    store, clock = seeded_store("memory"), Clock(0)
    ex = make_executor(store, clock)
    c = _accept(store, ex, clock, "OFF-EPO", [early_pay("OB-EP", rate_bp=60)])
    r = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A",
                      amount_fen=RCV_A - post(bp(60) * RCV_A)))
    assert r.status == EXECUTED
    done = store.get_commitment(c.id)
    assert done.status == CommitmentStatus.FULFILLED and done.settled_obligations == []


# ================================================================ F6: a late discounted receipt is a plain receipt


def test_f6_a_late_discounted_receipt_is_not_the_agreed_early_payment(client: TestClient, rt: Runtime) -> None:
    cm = _buyer_early_pay(client, rt)
    move(client, 3)  # one day late
    disc = post(bp(60) * RCV_A)
    r1 = post_op(client, rt, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-late", "requested_by": "SYSTEM",
                                    "receivable_id": "RCV-A", "amount_fen": RCV_A - disc})
    r2 = post_op(client, rt, BANK, {"kind": "RECEIVE_PAYMENT", "op_id": "rx-rest", "requested_by": "SYSTEM",
                                    "receivable_id": "RCV-A", "amount_fen": disc})
    assert r1["status"] == r2["status"] == "EXECUTED" and rcv(rt).status == "SETTLED"
    rep = reconcile(rt.store, day=rt.day)
    assert [m.status for m in rep.receipts] == [MatchStatus.DISCOUNT_IGNORED, MatchStatus.MATCHED]
    [row] = rep.promised
    assert row.commitment_id == cm.id and row.status != PromiseStatus.RECEIVED and row.receipt_seq is None


# ================================================================ F7: a bullet term loan's landing fee is level


TERM = {"id": "FAC-TL", "name": "Term loan", "kind": "GOV_GUARANTEED_LOAN", "lender_id": "BANK-2",
        "status": "COMMITTED", "owner_approved": True, "limit_fen": 60_000_000, "drawn_fen": 0, "rate_bp": 500,
        "upfront_fee_bp": 200, "lead_time_days": 5, "term_months": 12, "repayment": "BULLET"}


def _with_term_loan(store: Any, ex: Any, clock: Clock, **update: Any) -> None:
    fac = Facility.model_validate_json(json.dumps({**TERM, **update}))
    r = ex.execute(op(AddFacility, clock, actor=Actor.OWNER, facility=fac))
    if r.status == PENDING:
        r = ex.decide(r.approval_id, True, Actor.OWNER)
    assert r.status == EXECUTED, r.message


def _ds(state: Any, mandate: Any) -> dict[int, int]:
    t = project(state, [], [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    return {m.month: m.debt_service_fen for m in t.months}


def test_f7_the_draw_admission_accepts_shows_no_dscr_breach_in_the_next_projection(client: TestClient,
                                                                                    rt: Runtime) -> None:
    """p14: the largest draw admission accepts used to show a month-1 DSCR breach once executed, until it landed."""
    from app.covenants import evaluate as evaluate_covenants
    from app.funding.admission import admit

    r = post_op(client, rt, OWNER, {"kind": "ADD_FACILITY", "op_id": "add-tl", "requested_by": "OWNER",
                                    "facility": TERM})
    if r["status"] == "PENDING_APPROVAL":
        r = client.post(f"/approvals/{r['approval_id']}", headers=OWNER, json={"decision": "APPROVE"}).json()["result"]
    assert r["status"] == "EXECUTED"

    def admitted(amount: int) -> bool:
        m = rt.store.get_mandate()
        o = DrawFacility(op_id="probe", idempotency_key="probe", mandate_version=m.version, requested_by=Actor.AGENT,
                         day=rt.day, facility_id="FAC-TL", amount_fen=amount)
        return not admit(o, current_books(rt.store.get_state(), rt.store.commitments()), m).violations

    lo, hi = 100_000, 60_000_000
    while hi - lo > 100:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if admitted(mid) else (lo, mid)
    res = post_op(client, rt, AGENT, {"kind": "DRAW_FACILITY", "op_id": "tl-draw", "requested_by": "AGENT",
                                      "facility_id": "FAC-TL", "amount_fen": lo})
    assert res["status"] == "EXECUTED"
    s, m = rt.store.get_state(), rt.store.get_mandate()
    t = project(s, [], [], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    binding = [f for f in s.facilities if f.status.value == "COMMITTED"]
    assert not [v for v in evaluate_covenants(t, binding, m) if v.code == ViolationCode.DSCR_BREACH]
    before = _ds(s, m)
    move(client, 6)  # the loan has landed
    assert {k: v for k, v in _ds(rt.store.get_state(), m).items() if k in before} == before


@pytest.mark.parametrize("amount", [1_000_000, 30_299_693, 55_000_000])
@pytest.mark.parametrize(("lead", "fee_bp", "months"), [(1, 0, 6), (5, 200, 12), (12, 350, 12), (20, 100, 3)])
def test_f7_property_the_monthly_debt_service_is_the_same_the_day_before_and_after_landing(
        amount: int, lead: int, fee_bp: int, months: int) -> None:
    store, clock = seeded_store("memory"), Clock(0)
    ex = make_executor(store, clock)
    _with_term_loan(store, ex, clock, lead_time_days=lead, upfront_fee_bp=fee_bp, term_months=months)
    assert ex.execute(op(DrawFacility, clock, actor=Actor.OWNER, facility_id="FAC-TL", amount_fen=amount)).status \
        == EXECUTED
    s, m = store.get_state(), store.get_mandate()
    [lot] = [x for x in s.lots if x.facility_id == "FAC-TL"]
    assert lot.arrival_day == lead and not lot.settled
    day_before = close_days(s, lead - 1)[0] if lead > 1 else s
    day_after, adv = close_days(s, lead + 1)
    assert lot.id in adv.settled_lot_ids
    a, b = _ds(day_before, m), _ds(day_after, m)
    common = sorted(set(a) & set(b))
    assert common and {k: a[k] for k in common} == {k: b[k] for k in common}
