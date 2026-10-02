"""Capex, the borrower file and the alerts on current books and a clock past day 0 (ADR-0006, audit C3)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.alerts import Alert, AlertKind, alerts
from app.api.alerts import router as alerts_router
from app.api.auth import DEMO_OWNER_TOKEN
from app.api.borrower_file import router as borrower_router
from app.api.capex import router as capex_router
from app.api.runtime import Runtime, set_runtime
from app.books import current_books
from app.borrower_file import build
from app.capex import CapexRequest, evaluate_capex
from app.clock import advance
from app.config import get_settings
from app.domain.models import (
    CashFlow,
    Commitment,
    CommitmentStatus,
    DrawFacility,
    FlowKind,
    LedgerEventKind,
    Mode,
    Obligation,
    OperationStatus,
    SubmitInvoiceForFinancing,
)
from app.domain.money import fmt_yuan
from app.financial import invoices, project
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.books.test_current_books import _commitment, _early_pay
from tests.operations.builders import Clock, extension, make_executor, op, seeded_store

BORROWER = {"facility_id": "FAC-GGL", "amount_fen": 36_000_000, "use_of_proceeds": "Working capital for payroll"}
OK = (OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL)


def _with(store: Any, *obligations: Obligation) -> list[Commitment]:
    for ob in obligations:
        c = _commitment(ob, CommitmentStatus.ACTIVE)
        store.put_commitment(c)
        store.put_state(invoices.accept(store.get_state(), c))  # ADR-0009: what the executor writes at ACTIVE
    return store.commitments()


def _of(found: list[Alert], kind: AlertKind) -> list[Alert]:
    return [a for a in found if a.kind == kind]


def _run(store: Any, day: int | None = None, **kw: Any) -> list[Alert]:
    state = store.get_state()
    return alerts(state, store.get_mandate(), store, state.as_of_day if day is None else day, **kw)


def _episodes(t: Any, floor: int) -> list[tuple[int, int]]:
    """(first day, shortfall on it) of each run of days closing below the floor."""
    out: list[tuple[int, int]] = []
    prev_short = False
    for p in t.days:
        short = p.closing_fen < floor
        if short and not prev_short:
            out.append((p.day, floor - p.closing_fen))
        prev_short = short
    return out


def _typed(action: Any, clock: Clock) -> Any:
    if action.operation_kind == "DRAW_FACILITY":
        return op(DrawFacility, clock, facility_id=action.facility_id, amount_fen=action.amount_fen)
    assert action.operation_kind == "SUBMIT_INVOICE_FOR_FINANCING"
    return op(SubmitInvoiceForFinancing, clock, facility_id=action.facility_id, receivable_id=action.receivable_id,
              advance_fen=action.amount_fen)


def _after_day_zero_funding(day: int) -> tuple[Any, Clock, Any]:
    """The golden scenario with a ¥150,000 line draw and a ¥210,000 advance on RCV-A made on day 0, the clock at
    `day` and no receipt recorded."""
    store = seeded_store()
    clock = Clock(0)
    ex = make_executor(store, clock)
    assert ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=15_000_000)).status \
        == OperationStatus.EXECUTED
    assert ex.execute(op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A",
                         advance_fen=21_000_000)).status == OperationStatus.EXECUTED
    advance(store, day)
    clock.day = day
    return store, clock, ex


# ---------------------------------------------------------------- 1. day 0, no commitments: nothing moves


def test_day_zero_without_commitments_is_unchanged():
    store = seeded_store()
    state, mandate = store.get_state(), store.get_mandate()
    assert evaluate_capex(CapexRequest(), state, mandate, commitments=[]) == evaluate_capex(CapexRequest(), state, mandate)
    found = _run(store)
    [breach] = _of(found, AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.day == 12 and breach.amount_fen == 24_000_000 and breach.committed_cure is True
    assert breach.id == "ALERT-RESERVE-12"
    assert {s.operation_kind for s in breach.suggested} == {"DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"}
    assert all(s.receivable_id == "RCV-A" for s in breach.suggested if s.receivable_id)  # a real invoice only
    assert not _of(found, AlertKind.RECEIVABLE_PAST_DUE)
    assert build(store, day=0, **BORROWER).generated_day == 0


# ---------------------------------------------------------------- 2. a live +15-day terms extension


def test_live_terms_extension_reaches_capex_borrower_file_and_alerts():
    store = seeded_store()
    state, mandate = store.get_state(), store.get_mandate()
    # a day-40 outflow after the golden receipt: the low point is then reached after day 32, where the extension bites
    rich = state.model_copy(update={"cash_fen": state.cash_fen + 50_000_000, "flows": [
        *state.flows, CashFlow(id="F-TOOLING", day=40, amount_fen=-45_000_000, kind=FlowKind.OTHER,
                               label="Tooling", confirmed=True)]})
    plain = {"capex": evaluate_capex(CapexRequest(price_fen=10_000_000), rich, mandate),
             "file": build(store, day=0, **BORROWER), "alerts": _run(store)}
    commitments = _with(store, extension())
    # ADR-0009: the accepted extension is in the state (an adjustment on the next 3 invoices), not re-applied
    state = store.get_state()
    books = current_books(state, commitments)
    assert books.obligations == () and [a.id for a in state.invoice_adjustments] == ["CMT-OB-T:OB-T"]
    rich = rich.model_copy(update={"invoice_adjustments": state.invoice_adjustments,
                                   "receivables": state.receivables})
    horizon, floor = mandate.horizon_days, mandate.min_cash_fen
    t = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, horizon, floor)

    # capex: the cash-line trajectory (the purchase posted today) and the leverage headroom
    request = CapexRequest(price_fen=10_000_000)
    result = evaluate_capex(request, rich, mandate, commitments=commitments)
    purchase = CashFlow(id="CAPEX-PURCHASE", day=0, amount_fen=-request.price_fen, kind=FlowKind.OTHER, label="x")
    expected = project(rich.model_copy(update={"flows": [*rich.flows, purchase]}), list(books.obligations), [],
                       Mode.CONSERVATIVE, horizon, floor)
    low = min(expected.days, key=lambda p: (p.closing_fen, p.day))
    line = next(s for s in result.structures if s.kind == "CASH_LINE")
    working = next(w for w in line.workings if w.label == "Lowest projected cash")
    assert working.inputs["day"] == str(low.day) and working.value == fmt_yuan(low.closing_fen)
    before = next(w for w in next(s for s in plain["capex"].structures if s.kind == "CASH_LINE").workings
                  if w.label == "Lowest projected cash")
    assert (before.inputs["day"], before.value) != (working.inputs["day"], working.value)

    # borrower file: the 13-week forecast is the projection on current books
    bf = build(store, day=0, **BORROWER)
    h = max(horizon, 91, 360)
    tb = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, h)
    forecast = next(s for s in bf.sections if s.key == "forecast_13w")
    for k, row in enumerate(forecast.rows, start=1):
        assert row.figures[2].fen == tb.days[7 * k].closing_fen
    old = next(s for s in plain["file"].sections if s.key == "forecast_13w")
    assert [r.figures[2].fen for r in forecast.rows] != [r.figures[2].fen for r in old.rows]

    # alerts: the reserve alerts are the breach episodes of that same projection
    found = _of(_run(store), AlertKind.RESERVE_BREACH_AHEAD)
    assert [(a.day, a.amount_fen) for a in found] == _episodes(t, floor)
    assert found[0].day == t.first_breach_day
    assert [a.inputs["max_shortfall"] for a in found] != [
        a.inputs["max_shortfall"] for a in _of(plain["alerts"], AlertKind.RESERVE_BREACH_AHEAD)]


def test_capex_leverage_counts_a_live_extension():
    store = seeded_store()
    state, mandate = store.get_state(), store.get_mandate()
    plain = evaluate_capex(CapexRequest(price_fen=10_000_000), state, mandate)
    commitments = _with(store, extension())
    result = evaluate_capex(CapexRequest(price_fen=10_000_000), store.get_state(), mandate, commitments=commitments)
    assert result.leverage_financed.value > plain.leverage_financed.value  # less covenant headroom
    assert all(s.leverage.value > p.leverage.value for s, p in zip(
        [s for s in result.structures if s.kind != "CASH_LINE"],
        [s for s in plain.structures if s.kind != "CASH_LINE"], strict=True))


# ---------------------------------------------------------------- 3. the missed receipt


def test_missed_receipt_on_a_financed_invoice():
    store, _clock, _ex = _after_day_zero_funding(34)
    state = store.get_state()
    assert state.as_of_day == 34 and state.cash_fen == 30_000_000
    found = _run(store)

    [late] = _of(found, AlertKind.RECEIVABLE_PAST_DUE)
    assert late.receivable_id == "RCV-A" and late.day == 32 and late.amount_fen == 42_000_000
    assert late.title == "Receivable RCV-A is 2 day(s) past due"
    assert "¥420,000.00 outstanding" in late.detail and "due on day 32" in late.detail and "FINANCED" in late.detail

    books = current_books(state, store.commitments())
    t = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, store.get_mandate().horizon_days,
                store.get_mandate().min_cash_fen)
    [breach] = _of(found, AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.day == t.first_breach_day == 34 and breach.day >= 34
    assert breach.amount_fen == 21_374_260
    assert breach.inputs["last_day"] == "46" and breach.inputs["max_shortfall"] == "¥213,742.60"
    # the advance falls due with the missed receipt; every committed facility is spent or too slow, so no cure
    assert breach.committed_cure is False and breach.suggested == []


def test_a_cure_after_a_missed_receipt_is_dated_today_and_the_executor_accepts_it():
    store, clock, ex = _after_day_zero_funding(34)
    state = store.get_state()
    # more cash and a later outflow, so that a breach starts on day 40 and the committed advance can land first
    store.put_state(state.model_copy(update={
        "cash_fen": state.cash_fen + 25_000_000,
        "flows": [*state.flows, CashFlow(id="F-BIG", day=40, amount_fen=-8_000_000, kind=FlowKind.OTHER,
                                         label="Tooling", confirmed=True)]}))
    [breach] = _of(_run(store), AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.day == 40 and breach.committed_cure is True and breach.suggested
    for action in breach.suggested:
        result = ex.execute(_typed(action, clock))  # dated day 34 by `op`
        assert result.status in OK, result.message


def test_a_cure_on_day_5_is_dated_day_5_and_accepted():
    store = seeded_store()
    advance(store, 5)
    clock = Clock(5)
    ex = make_executor(store, clock)
    [breach] = _of(_run(store), AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.day == 12 and breach.committed_cure is True
    for action in breach.suggested:
        typed = _typed(action, clock)
        assert typed.day == 5
        assert ex.execute(typed).status in OK


# ---------------------------------------------------------------- 4. a lapsed early payment


def test_lapsed_early_payment_is_a_past_due_alert_and_the_invoice_is_back_on_day_32():
    store = seeded_store()
    commitments = _with(store, _early_pay("RCV-A", 42_000_000, 2))
    advance(store, 5)
    state = store.get_state()
    books = current_books(state, commitments)
    assert books.obligations == () and [x.reason for x in books.lapsed] == ["EARLY_PAYMENT_MISSED"]

    found = _run(store)
    [lapsed] = [a for a in _of(found, AlertKind.RECEIVABLE_PAST_DUE) if a.commitment_id]
    assert lapsed.commitment_id == "CMT-OB-RCV-A" and lapsed.receivable_id == "RCV-A"
    assert lapsed.day == 5 and lapsed.amount_fen == 42_000_000
    assert lapsed.inputs["promised_day"] == "2" and lapsed.inputs["due_day"] == "32"
    assert ("early payment promised under commitment CMT-OB-RCV-A for day 2 did not arrive" in lapsed.detail
            and "back on its original due day, day 32" in lapsed.detail)
    assert lapsed.id.startswith("ALERT-EARLYPAY-") and lapsed.id == _run(store)[found.index(lapsed)].id
    assert not [a for a in _of(found, AlertKind.RECEIVABLE_PAST_DUE) if not a.commitment_id]  # RCV-A is not yet due

    t = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, store.get_mandate().horizon_days)
    receipts = [(p.day, e.amount_fen) for p in t.days for e in p.events
                if e.kind == LedgerEventKind.RECEIPT and e.ref == "RCV-A"]
    assert receipts == [(32, 42_000_000)]
    [breach] = _of(found, AlertKind.RESERVE_BREACH_AHEAD)
    t2 = project(books.state, list(books.obligations), [], Mode.CONSERVATIVE, store.get_mandate().horizon_days,
                 store.get_mandate().min_cash_fen)
    assert breach.day == t2.first_breach_day


# ---------------------------------------------------------------- 5. nothing refers to a day before today


@pytest.mark.parametrize("scenario", ["day0", "extension", "missed_receipt", "lapsed", "day5"])
def test_no_alert_refers_to_a_closed_day(scenario: str):
    if scenario == "missed_receipt":
        store, _, _ = _after_day_zero_funding(34)
    else:
        store = seeded_store()
        if scenario == "extension":
            _with(store, extension())
        if scenario == "lapsed":
            _with(store, _early_pay("RCV-A", 42_000_000, 2))
        if scenario in ("lapsed", "day5"):
            advance(store, 5)
    today = store.get_state().as_of_day
    found = _run(store)
    assert found
    assert len({a.id for a in found}) == len(found)  # ids are unique ...
    assert [a.id for a in found] == [a.id for a in _run(store)]  # ... and stable
    for a in found:
        if a.kind == AlertKind.RECEIVABLE_PAST_DUE and not a.commitment_id:
            assert a.day is not None and a.day < today  # the day it was due: that is what is reported
            continue
        assert a.day is None or a.day >= today, (a.id, a.day)
        if a.month is not None:
            assert 30 * a.month >= today, (a.id, a.month)


# ---------------------------------------------------------------- the API layer passes the live commitments


def test_api_routes_read_current_books():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    try:
        app = FastAPI()
        for router in (alerts_router, borrower_router, capex_router):
            app.include_router(router)
        client = TestClient(app, headers={"X-Owner-Token": DEMO_OWNER_TOKEN})
        plain = client.post("/capex/evaluate", json={}).json()
        _with(rt.store, extension(), _early_pay("RCV-A", 42_000_000, 2))
        # the route projects from the current books (its leverage no longer sees the extension: see the xfail above)
        assert client.post("/capex/evaluate", json={}).json() != plain
        rt.advance_to(5)
        body = client.get("/alerts").json()
        assert body["day"] == 5
        assert any(a["commitment_id"] == "CMT-OB-RCV-A" and a["kind"] == "RECEIVABLE_PAST_DUE" for a in body["alerts"])
        file = client.post("/borrower-file", json={"facility_id": "FAC-GGL", "amount_fen": 36_000_000,
                                                   "use_of_proceeds": "Working capital for payroll"}).json()
        assert file["generated_day"] == 5
    finally:
        set_runtime(None)
