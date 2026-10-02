"""Cash-flow alerts from the conservative trajectory (golden_sme, spec v2 §6–7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.alerts import Alert, AlertKind, Severity, SuggestedAction, alerts
from app.domain.fixtures import golden_values, load_scenario
from app.domain.models import (
    Actor,
    CashFlow,
    Commitment,
    CommitmentStatus,
    DebtPosition,
    DrawFacility,
    FinancialState,
    FlowKind,
)
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.operations import Executor
from app.persistence import InMemoryLedgerStore
from tests.verifier.conftest import bundle


def _store(state: FinancialState | None = None) -> InMemoryLedgerStore:
    store = InMemoryLedgerStore()
    store.put_state(state or load_scenario()[0])
    store.put_mandate(load_signed_mandate())
    return store


def _run(store: InMemoryLedgerStore, day: int = 0, **kw) -> list[Alert]:
    return alerts(store.get_state(), store.get_mandate(), store, day, **kw)


def _of(found: list[Alert], kind: AlertKind) -> list[Alert]:
    return [a for a in found if a.kind == kind]


def test_baseline_reserve_breach_on_day_12_with_a_committed_cure():
    found = _run(_store())
    [breach] = _of(found, AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.day == 12 and breach.severity == Severity.CRITICAL
    assert breach.amount_fen == 24_000_000  # ¥300,000 floor − ¥60,000 after payroll
    # the ¥405,000 need before day 32: the spec's ¥360,000 plus the existing loan's ¥45,000 day-30 payment
    assert breach.inputs["max_shortfall"] == "¥405,000.00"
    assert breach.committed_cure is True
    kinds = {s.operation_kind for s in breach.suggested}
    assert kinds == {"DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"}
    assert all(s.executes_automatically is False for s in breach.suggested)
    assert breach.formula.startswith("shortfall = floor − closing_d")
    assert found[0] == breach  # critical first


def test_ex01_package_moves_the_breach_to_day_47():
    g = golden_values()
    found = _run(_store(), obligations=bundle("EX01_PACKAGE").bound_obligations)
    [breach] = _of(found, AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.day == 47
    assert breach.amount_fen == g["reserve_shortfall_day47"]
    assert breach.committed_cure is True
    # the contingent rebate counts at maximum: ¥4,000 against the ¥5,000 cap
    [near] = _of(found, AlertKind.CONCESSIONS_NEAR_CAP)
    assert near.amount_fen == g["rebate_max"] and near.severity == Severity.WARNING


def test_no_committed_cure_when_committed_facilities_are_exhausted():
    state, _ = load_scenario()
    state = state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen}) if f.id in ("FAC-LINE", "FAC-IF") else f
        for f in state.facilities]})
    [breach] = _of(_run(_store(state)), AlertKind.RESERVE_BREACH_AHEAD)
    assert breach.committed_cure is False
    assert all(s.operation_kind == "APPLY_FOR_FACILITY" for s in breach.suggested)


def test_reserve_headroom_below_ten_percent():
    state, _ = load_scenario()
    state = state.model_copy(update={"cash_fen": 40_000_000 + 25_000_000})  # day-12 close ¥310,000
    found = _run(_store(state))
    [thin] = _of(found, AlertKind.RESERVE_HEADROOM_LOW)
    assert thin.severity == Severity.WARNING and thin.amount_fen < 3_000_000
    # day 20 still breaches (¥190,000)
    assert _of(found, AlertKind.RESERVE_BREACH_AHEAD)[0].day == 20


def test_covenant_headroom_alerts():
    state, _ = load_scenario()
    tight = state.model_copy(update={"debts": [DebtPosition(id="D-1", facility_id=None, label="loan",
                                                            principal_fen=150_000_000,
                                                            monthly_debt_service_fen=7_000_000)]})
    [a] = _of(_run(_store(tight)), AlertKind.COVENANT_HEADROOM_LOW)  # 90,000 / 70,000 = 1.29x
    assert a.severity == Severity.WARNING and a.title.startswith("DSCR") and a.month == 1
    breach = state.model_copy(update={"debts": [DebtPosition(id="D-1", facility_id=None, label="loan",
                                                             principal_fen=150_000_000,
                                                             monthly_debt_service_fen=8_000_000)]})
    [b] = _of(_run(_store(breach)), AlertKind.COVENANT_HEADROOM_LOW)  # 1.13x < 1.25x
    assert b.severity == Severity.CRITICAL and "breach" in b.title
    assert not _of(_run(_store()), AlertKind.COVENANT_HEADROOM_LOW)  # golden: DSCR 2.00x, leverage 1.39x


def _draw_line(store: InMemoryLedgerStore) -> None:
    ex = Executor(store, trusted_owner_key_hex=demo_owner_public_key_hex(), clock=lambda: 0)
    ex.execute(DrawFacility(op_id="OP-1", idempotency_key="k-1", mandate_version=1, requested_by=Actor.AGENT, day=0,
                            facility_id="FAC-LINE", amount_fen=15_000_000))


def test_a_drawn_line_the_projection_repays_on_a_receipt_keeps_the_clean_down():
    # The projection repays a balance already drawn on the first receipt that keeps cash above the floor
    # (day 32 here), so the line then stays at zero for the rest of the horizon.
    store = _store()
    _draw_line(store)
    assert not _of(_run(store), AlertKind.CLEAN_DOWN_AT_RISK)


def test_clean_down_at_risk_after_a_line_draw_no_receipt_can_repay():
    state = load_scenario()[0]
    big = CashFlow(id="F-BIG", day=115, amount_fen=-200_000_000, kind=FlowKind.OTHER, label="Big payment", confirmed=True)
    store = _store(state.model_copy(update={"flows": [*state.flows, big]}))
    assert not _of(_run(store), AlertKind.CLEAN_DOWN_AT_RISK)
    _draw_line(store)  # now no receipt keeps the floor after repaying: the line is repaid only on the last day
    [a] = _of(_run(store), AlertKind.CLEAN_DOWN_AT_RISK)
    assert a.inputs["facility_id"] == "FAC-LINE" and a.amount_fen == 15_000_000
    assert a.suggested[0].operation_kind == "REPAY_FACILITY"


def test_receivable_past_due():
    found = _run(_store(), day=40)
    [a] = _of(found, AlertKind.RECEIVABLE_PAST_DUE)
    assert a.inputs["receivable_id"] == "RCV-A" and a.day == 32 and a.amount_fen == 42_000_000
    assert a.suggested[0].operation_kind == "RECEIVE_PAYMENT"
    assert not _of(_run(_store(), day=32), AlertKind.RECEIVABLE_PAST_DUE)


def test_commitment_expiring_within_7_days():
    store = _store()
    offer = bundle("EX01_PACKAGE")
    for cid, expires, status in (("C-SOON", 5, CommitmentStatus.PROPOSED), ("C-LATER", 30, CommitmentStatus.PROPOSED),
                                 ("C-DONE", 3, CommitmentStatus.ACTIVE)):
        store.put_commitment(Commitment(
            id=cid, offer_id="OFF-1", offer_version=1, counterparty_id="BUYER-1", verdict_id="V-1",
            terms_hash="h", obligations=offer.bound_obligations[:1], status=status, nonce=f"n-{cid}",
            expires_day=expires, mandate_version=1, forward_value_fen=0))
    found = _of(_run(store), AlertKind.COMMITMENT_EXPIRING)
    assert [a.inputs["commitment_id"] for a in found] == ["C-SOON"]
    assert found[0].suggested[0].operation_kind == "ACCEPT_OFFER"


def test_alert_contract_is_strict():
    with pytest.raises(ValidationError):
        Alert(id="x", kind=AlertKind.RESERVE_BREACH_AHEAD, severity=Severity.INFO, title="t", detail="d",
              formula="f", surprise=1)
    with pytest.raises(ValidationError):  # a Tier-3 kind can never be suggested
        SuggestedAction(operation_kind="SIGN_PERSONAL_GUARANTEE")
    with pytest.raises(ValidationError):  # and nothing is ever executed automatically
        SuggestedAction(operation_kind="DRAW_FACILITY", executes_automatically=True)
