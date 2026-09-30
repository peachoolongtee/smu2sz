"""Every operation is checked against the current, owner-signed mandate (INVARIANT 8)."""

from __future__ import annotations

from typing import Any

import pytest
from nacl.signing import SigningKey

from app.domain.fixtures import load_scenario
from app.domain.models import (
    AcceptOffer,
    CounterOffer,
    DrawFacility,
    OperationStatus,
    ReceivePayment,
    RejectOffer,
    RepayFacility,
    SecurityEventKind,
    SubmitInvoiceForFinancing,
    ViolationCode,
)
from app.mandate import load_demo_owner_key, load_signed_mandate, revoke, sign
from app.persistence import InMemoryLedgerStore
from tests.operations.builders import Clock, make_executor, op, seed_offer


def sample_ops(clock: Clock) -> list[Any]:
    return [
        op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000),
        op(RepayFacility, clock, facility_id="FAC-LINE", amount_fen=1),
        op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A", advance_fen=1_000_000),
        op(ReceivePayment, clock, receivable_id="RCV-A", amount_fen=1_000_000),
        op(RejectOffer, clock, offer_id="OFF-1", reason_codes=[]),
        op(CounterOffer, clock, offer_id="OFF-1", counter_id="CTR-A"),
        op(AcceptOffer, clock, offer_id="OFF-1", offer_version=1, terms_hash="x", nonce="NONCE-OFF-1"),
    ]


def assert_all_refused_with(ex: Any, store: Any, clock: Clock, code: ViolationCode) -> None:
    before = store.get_state()
    for o in sample_ops(clock):
        r = ex.execute(o)
        assert r.status == OperationStatus.REFUSED, o.kind
        assert code in [v.code for v in r.violations], o.kind
    assert store.get_state() == before
    assert store.approvals() == []
    assert store.verify_chain()


def test_revoked_mandate_refuses_everything(ex: Any, store: Any, clock: Clock) -> None:
    seed_offer(store, ex)
    store.put_mandate(revoke(load_signed_mandate(), load_demo_owner_key()["private_key_hex"]))
    assert_all_refused_with(ex, store, clock, ViolationCode.MANDATE_REVOKED)


def test_mandate_version_mismatch_refuses(ex: Any, store: Any, clock: Clock) -> None:
    r = ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1_000_000, mandate_version=2))
    assert r.status == OperationStatus.REFUSED
    assert [v.code for v in r.violations] == [ViolationCode.MANDATE_VERSION_MISMATCH]


def test_mandate_resigned_with_foreign_key_refuses(ex: Any, store: Any, clock: Clock) -> None:
    foreign = SigningKey.generate().encode().hex()
    loosened = load_signed_mandate().model_copy(update={"min_cash_fen": 0, "tier2_single_commitment_fen": 10**12})
    store.put_mandate(sign(loosened, foreign))
    assert_all_refused_with(ex, store, clock, ViolationCode.BAD_SIGNATURE)


def test_mandate_tampered_by_one_fen_refuses(ex: Any, store: Any, clock: Clock) -> None:
    m = load_signed_mandate()
    store.put_mandate(m.model_copy(update={"min_cash_fen": m.min_cash_fen - 1}))
    assert_all_refused_with(ex, store, clock, ViolationCode.BAD_SIGNATURE)


def test_expired_mandate_refuses(ex: Any, store: Any, clock: Clock) -> None:
    clock.day = 91
    assert_all_refused_with(ex, store, clock, ViolationCode.MANDATE_EXPIRED)


def test_unsigned_golden_mandate_refuses(ex: Any, store: Any, clock: Clock) -> None:
    _, unsigned = load_scenario()
    store.put_mandate(unsigned)
    assert_all_refused_with(ex, store, clock, ViolationCode.BAD_SIGNATURE)


def test_no_mandate_refuses() -> None:
    store = InMemoryLedgerStore()
    store.put_state(load_scenario()[0])
    clock = Clock(0)
    r = make_executor(store, clock).execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=1))
    assert r.status == OperationStatus.REFUSED
    assert [v.code for v in r.violations] == [ViolationCode.BAD_SIGNATURE]


def test_executor_requires_a_pinned_owner_key() -> None:
    with pytest.raises(ValueError):
        from app.operations import Executor

        Executor(InMemoryLedgerStore(), trusted_owner_key_hex="", clock=lambda: 0)


def test_misdated_operation_is_stale_and_backdating_is_also_replay(ex: Any, store: Any, clock: Clock) -> None:
    clock.day = 3
    before = store.get_state()
    back = ex.execute(op(DrawFacility, Clock(2), facility_id="FAC-LINE", amount_fen=1_000_000))
    assert [v.code for v in back.violations] == [ViolationCode.STALE_OPERATION, ViolationCode.REPLAY]
    assert [e.kind for e in store.security_events()] == [SecurityEventKind.REPLAY]
    ahead = ex.execute(op(DrawFacility, Clock(4), facility_id="FAC-LINE", amount_fen=1_000_000))
    assert [v.code for v in ahead.violations] == [ViolationCode.STALE_OPERATION]
    assert len(store.security_events()) == 1
    assert back.effective_day == ahead.effective_day == 3
    assert store.get_state() == before
