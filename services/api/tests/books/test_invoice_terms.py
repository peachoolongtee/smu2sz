"""ADR-0009: accepted terms are written onto invoices with a scope fixed at acceptance (audit A06, A07).

The flows go through the same path as the audit scripts (docs/research/independent-audit-evidence-2026-10-03):
compile, evaluate, propose, AcceptOffer, owner approval, the clock and bank receipts, and assert the stored state,
the projection, the reconciliation report and the alerts.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.alerts import AlertKind, alerts, reconcile
from app.api.runtime import Runtime
from app.books import current_books
from app.clock import advance, close_days
from app.compiler import compile_offer
from app.config import Settings
from app.domain.fixtures import offer_documents
from app.domain.models import (
    AcceptOffer,
    Actor,
    BaseKind,
    Commitment,
    CommitmentStatus,
    Contingency,
    Duration,
    DurationKind,
    FinancialState,
    LedgerEventKind,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    OperationStatus,
    ReceivePayment,
    SourceDocument,
    SourceSpan,
)
from app.domain.money import bp, post
from app.financial import invoices, project
from app.mandate import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.verifier import evaluate
from tests.operations.builders import Clock, make_executor, op, seeded_store

RI2 = "RI:BUYER-1:2"
FACE = 42_000_000  # BUYER-1's recurring invoice, every 30 days from day 2, 45-day terms
AGREED = FACE + post(bp(45) * FACE)  # +0.45%: ¥421,890
SPAN = [SourceSpan(doc_id="T", start=0, end=0, text="")]
MANDATE_LAST_DAY = 89


# ---------------------------------------------------------------- helpers


def _runtime() -> Runtime:
    rt = Runtime(settings=Settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    return rt


def _accept(rt: Runtime, verdict_id: str, counter_id: str | None = None, *, delay: int = 0) -> Commitment:
    """Propose, (optionally let the books move first), AcceptOffer, owner approval."""
    c = rt.executor.propose_commitment(verdict_id, expires_day=7, counter_id=counter_id)
    if delay:
        rt.advance_to(rt.day + delay)
    r = rt.executor.execute(AcceptOffer(op_id="acc", idempotency_key="acc", mandate_version=1,
                                        requested_by=Actor.AGENT, day=rt.day, offer_id=c.offer_id,
                                        offer_version=c.offer_version, terms_hash=c.terms_hash, nonce=c.nonce))
    if r.approval_id:
        r = rt.executor.decide(r.approval_id, True, Actor.OWNER)
    assert r.status == OperationStatus.EXECUTED, r.message
    stored = rt.store.get_commitment(c.id)
    assert stored is not None and stored.status == CommitmentStatus.ACTIVE
    return stored


def _option_b(rt: Runtime, *, delay: int = 0) -> Commitment:
    """EX01 Option B: the counter of 60-day terms with a +0.45% price adjustment on future invoices."""
    o = compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1")
    rt.store.put_offer(o)
    b = evaluate(o, rt.store.get_state(), rt.store.get_mandate(), trusted_owner_key_hex=rt.owner_key_hex)
    rt.store.put_verdict(b.verdict)
    ctr = next(c for c in b.verdict.counters
               if any(ob.type == ObligationType.PRICE_ADJUSTMENT for ob in c.obligations))
    return _accept(rt, b.verdict.id, ctr.id, delay=delay)


def _next_three(rt: Runtime) -> Commitment:
    text = "We'd like 50 days on the next 3 invoices instead of 45."
    doc = SourceDocument(doc_id="BOUND3", channel="chat", sender_id="BUYER-1", received_day=0, text=text)
    o = compile_offer([doc], "BUYER-1")
    rt.store.put_offer(o)
    b = evaluate(o, rt.store.get_state(), rt.store.get_mandate(), trusted_owner_key_hex=rt.owner_key_hex)
    rt.store.put_verdict(b.verdict)
    return _accept(rt, b.verdict.id)


def _receive(rt: Runtime, rid: str, amount: int, key: str) -> Any:
    return rt.executor.execute(ReceivePayment(op_id=key, idempotency_key=key, mandate_version=1,
                                              requested_by=Actor.SYSTEM, day=rt.day, receivable_id=rid,
                                              amount_fen=amount))


def _projection(rt: Runtime, horizon: int = 220, mode: Mode = Mode.CONSERVATIVE) -> Any:
    s = rt.store.get_state()
    books = current_books(s, rt.store.commitments())
    return project(books.state, list(books.obligations), [], mode, horizon)


def _receipts(t: Any, prefix: str = "RI:") -> dict[str, tuple[int, int]]:
    """receivable id -> (day, amount) of its RECEIPT event."""
    return {e.ref: (p.day, e.amount_fen) for p in t.days for e in p.events
            if e.kind == LedgerEventKind.RECEIPT and (e.ref or "").startswith(prefix)}


def _rcv(rt: Runtime, rid: str) -> Any:
    return next(r for r in rt.store.get_state().receivables if r.id == rid)


def _ob(oid: str, kind: ObligationType, *, days: int | None = None, rate: int | None = None,
        duration: Duration | None = None, contingency: Contingency = Contingency.FIRM) -> Obligation:
    return Obligation(id=oid, type=kind, counterparty_id="BUYER-1", days_delta=days, rate_bp=rate,
                      base=ObligationBase(kind=BaseKind.FUTURE_INVOICES), contingency=contingency,
                      duration=duration or Duration(kind=DurationKind.RECURRING_PERPETUAL), spans=SPAN, confidence=1.0)


def _commitment(cid: str, *obs: Obligation) -> Commitment:
    return Commitment(id=cid, offer_id="OFF", offer_version=1, counterparty_id="BUYER-1", verdict_id="V",
                      terms_hash="h", obligations=list(obs), status=CommitmentStatus.ACTIVE, nonce=f"n-{cid}",
                      expires_day=7, mandate_version=1, forward_value_fen=0)


# ---------------------------------------------------------------- 1. EX01 Option B (audit A06)


def test_option_b_invoice_is_issued_at_the_agreed_face_and_due_day_and_the_agreed_receipt_settles_it() -> None:
    rt = _runtime()
    c = _option_b(rt)
    [terms, price] = [a for a in rt.store.get_state().invoice_adjustments if a.commitment_id == c.id]
    assert terms.days_delta == 15 and terms.receivable_ids is None and terms.until_issue_day is None  # perpetual
    assert price.price_bp == 45 and price.from_issue_day == 0
    rt.advance_to(3)
    r = _rcv(rt, RI2)
    assert (r.face_fen, r.due_day, r.terms_days) == (AGREED, 62, 60) == (42_189_000, 62, 60)
    assert (r.base_face_fen, r.base_terms_days) == (FACE, 45)
    assert r.applied == [terms.id, price.id]
    assert _receipts(_projection(rt))[RI2] == (62, AGREED)
    result = _receive(rt, RI2, AGREED, "recv")
    assert result.status == OperationStatus.EXECUTED, result.message
    r = _rcv(rt, RI2)
    assert r.status == "SETTLED" and r.settled_fen == r.face_fen == AGREED
    assert RI2 not in _receipts(_projection(rt))


def test_option_b_partial_receipt_loses_no_value_anywhere() -> None:
    rt = _runtime()
    _option_b(rt)
    rt.advance_to(3)
    assert _receive(rt, RI2, 10_000_000, "part").status == OperationStatus.EXECUTED
    left = AGREED - 10_000_000
    assert left == 32_189_000
    r = _rcv(rt, RI2)
    assert (r.outstanding_fen, r.face_fen, r.settled_fen, r.status) == (left, AGREED, 10_000_000, "OPEN")
    assert _receipts(_projection(rt))[RI2] == (62, left)  # nothing recomputed on the balance
    rt.advance_to(50)
    report = reconcile(rt.store, 50)
    row = next(o for o in report.outstanding if o.receivable_id == RI2)
    assert (row.face_fen, row.due_day, row.past_due) == (left, 62, False)
    state = rt.store.get_state()
    late = [a for a in alerts(state, rt.store.get_mandate(), rt.store, 50) if a.receivable_id == RI2]
    assert not [a for a in late if a.kind == AlertKind.RECEIVABLE_PAST_DUE]
    rt.advance_to(63)
    state = rt.store.get_state()
    [past] = [a for a in alerts(state, rt.store.get_mandate(), rt.store, 63)
              if a.kind == AlertKind.RECEIVABLE_PAST_DUE and a.receivable_id == RI2]
    assert (past.day, past.amount_fen) == (62, left)
    row = next(o for o in reconcile(rt.store, 63).outstanding if o.receivable_id == RI2)
    assert (row.face_fen, row.due_day, row.past_due) == (left, 62, True)


# ---------------------------------------------------------------- 2. "the next 3 invoices" (audit A07)


def test_next_three_invoices_stays_on_the_three_chosen_at_acceptance() -> None:
    rt = _runtime()
    c = _next_three(rt)
    [adj] = rt.store.get_state().invoice_adjustments
    assert adj.receivable_ids == ["RI:BUYER-1:2", "RI:BUYER-1:32", "RI:BUYER-1:62"] and adj.days_delta == 5
    before = _receipts(_projection(rt))
    assert [before[f"RI:BUYER-1:{d}"][0] for d in (2, 32, 62, 92)] == [52, 82, 112, 137]  # not the fourth
    for day in (3, 33, 63):
        rt.advance_to(day)
        rid = f"RI:BUYER-1:{day - 1}"
        assert _rcv(rt, rid).due_day == day - 1 + 50
        assert _receive(rt, rid, FACE, f"recv{day}").status == OperationStatus.EXECUTED
    # the third scoped invoice is issued: the adjustment is consumed, the commitment fulfilled, its concession gone
    state = rt.store.get_state()
    assert state.invoice_adjustments == []
    assert rt.store.get_commitment(c.id).status == CommitmentStatus.FULFILLED
    assert not [fc for fc in state.forward_concessions if fc.commitment_id == c.id]
    after = _receipts(_projection(rt))
    assert [after[f"RI:BUYER-1:{d}"][0] for d in (92, 122, 152)] == [137, 167, 197]
    rt.advance_to(153)
    for d in (92, 122, 152):
        r = _rcv(rt, f"RI:BUYER-1:{d}")
        assert (r.due_day, r.applied, r.base_terms_days) == (d + 45, [], None)


# ---------------------------------------------------------------- 3. property: no value lost, scope fixed


def _store_with_adjustments() -> tuple[Any, Clock, Any, Commitment]:
    store = seeded_store()
    clock = Clock(0)
    ex = make_executor(store, clock)
    c = _commitment("CMT-P",
                    _ob("OB-PRICE", ObligationType.PRICE_ADJUSTMENT, rate=45),
                    _ob("OB-TERMS", ObligationType.TERMS_EXTENSION, days=10,
                        duration=Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=3)))
    store.put_commitment(c)
    store.put_state(invoices.accept(store.get_state(), c))
    return store, clock, ex, c


_steps = st.lists(st.one_of(
    st.tuples(st.just("advance"), st.integers(min_value=1, max_value=40)),
    st.tuples(st.just("pay"), st.integers(min_value=0, max_value=20), st.floats(min_value=0.05, max_value=1.0)),
), min_size=1, max_size=14)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(steps=_steps)
def test_receipts_and_clock_in_any_order_lose_nothing_and_never_move_the_scope(steps: list[tuple]) -> None:
    store, clock, ex, _ = _store_with_adjustments()
    [finite] = [a for a in store.get_state().invoice_adjustments if a.receivable_ids is not None]
    scope = list(finite.receivable_ids or [])
    assert scope == ["RI:BUYER-1:2", "RI:BUYER-1:32", "RI:BUYER-1:62"]
    received: dict[str, int] = {}
    for step in steps:
        if step[0] == "advance":
            clock.day = min(MANDATE_LAST_DAY, clock.day + step[1])  # the demo mandate expires on day 90
            advance(store, clock.day)
        else:
            open_ = [r for r in store.get_state().receivables if r.status in ("OPEN", "FINANCED")
                     and r.outstanding_fen > 0]
            if not open_:
                continue
            r = open_[step[1] % len(open_)]
            amount = max(1, int(r.outstanding_fen * step[2]))
            res = ex.execute(op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id=r.id, amount_fen=amount))
            assert res.status == OperationStatus.EXECUTED, res.message
            received[r.id] = received.get(r.id, 0) + amount
        state = store.get_state()
        for adj in state.invoice_adjustments:
            if adj.receivable_ids is not None:
                assert adj.receivable_ids == scope
        for r in state.receivables:
            assert r.settled_fen + r.outstanding_fen == r.face_fen
            assert r.settled_fen == received.get(r.id, 0)
            if r.id.startswith("RI:BUYER-1:"):
                assert r.face_fen == AGREED  # the agreed face, to the fen, whatever was received
                assert (finite.id in r.applied) == (r.id in scope)
                assert r.terms_days == (55 if r.id in scope else 45)
            else:
                assert r.applied == []  # issued before the effective day: out of scope


# ---------------------------------------------------------------- 4. projection and clock agree


@pytest.mark.parametrize("start", [0, 37])
def test_projection_and_issued_invoices_agree_for_a_live_perpetual_extension(start: int) -> None:
    store, _, _, _ = _store_with_adjustments()
    state: FinancialState = close_days(store.get_state(), start)[0] if start else store.get_state()
    t = project(state, [], [], Mode.CONSERVATIVE, 400)
    projected = {ref: (day, amt) for ref, (day, amt) in _receipts(t, "RI:BUYER-1:").items()}
    seen = 0
    for d in range(start + 1, start + 121):
        state, adv = close_days(state, d)
        for rid in adv.issued_receivable_ids:
            r = next(x for x in state.receivables if x.id == rid)
            assert projected[rid] == (r.due_day, r.face_fen), rid
            seen += 1
    assert seen == 4


# ---------------------------------------------------------------- 5. revocation


def test_revocation_removes_what_is_left_and_issued_invoices_keep_their_terms() -> None:
    rt = _runtime()
    c = _option_b(rt)
    rt.advance_to(3)
    res = rt.executor.revoke_commitment(c.id, Actor.OWNER)
    assert res.status == OperationStatus.EXECUTED, res.message
    state = rt.store.get_state()
    assert not [a for a in state.invoice_adjustments if a.commitment_id == c.id]
    assert not [fc for fc in state.forward_concessions if fc.commitment_id == c.id]
    r = _rcv(rt, RI2)
    assert (r.face_fen, r.due_day) == (AGREED, 62)  # a credit or debit note would be needed to change it
    rt.advance_to(33)
    r32 = _rcv(rt, "RI:BUYER-1:32")
    assert (r32.face_fen, r32.due_day, r32.applied) == (FACE, 77, [])
    assert _receipts(_projection(rt))["RI:BUYER-1:62"] == (107, FACE)


# ---------------------------------------------------------------- 6. contingent gains


def test_a_contingent_gain_is_never_written_and_counts_only_in_expected() -> None:
    store = seeded_store()
    c = _commitment("CMT-G", _ob("OB-G", ObligationType.PRICE_ADJUSTMENT, rate=45, contingency=Contingency.CONTINGENT))
    store.put_commitment(c)
    store.put_state(invoices.accept(store.get_state(), c))
    [adj] = store.get_state().invoice_adjustments
    assert adj.contingent_gain is True
    advance(store, 3)
    state = store.get_state()
    r = next(x for x in state.receivables if x.id == RI2)
    assert (r.face_fen, r.applied) == (FACE, [])
    conservative = _receipts(project(state, [], [], Mode.CONSERVATIVE, 120))
    expected = _receipts(project(state, [], [], Mode.EXPECTED, 120))
    assert conservative[RI2] == (47, FACE) and conservative["RI:BUYER-1:32"] == (77, FACE)
    assert expected[RI2] == (47, AGREED) and expected["RI:BUYER-1:32"] == (77, AGREED)


# ---------------------------------------------------------------- stored states


def test_adjusted_state_round_trips_through_the_sql_store_and_old_states_serialise_unchanged() -> None:
    plain = seeded_store().get_state()
    assert "invoice_adjustments" not in plain.model_dump_json() and '"applied"' not in plain.model_dump_json()
    store = seeded_store("sqlite")
    c = _commitment("CMT-S", _ob("OB-P", ObligationType.PRICE_ADJUSTMENT, rate=45),
                    _ob("OB-T", ObligationType.TERMS_EXTENSION, days=10,
                        duration=Duration(kind=DurationKind.RECURRING_BOUNDED, invoices=3)))
    store.put_state(invoices.accept(store.get_state(), c))
    advance(store, 3)
    state = store.get_state()
    assert [a.id for a in state.invoice_adjustments] == ["CMT-S:OB-P", "CMT-S:OB-T"]
    r = next(x for x in state.receivables if x.id == RI2)
    assert (r.face_fen, r.terms_days, r.base_face_fen, r.applied) == (AGREED, 55, FACE, ["CMT-S:OB-P", "CMT-S:OB-T"])
    assert FinancialState.model_validate_json(state.model_dump_json()) == state


# ---------------------------------------------------------------- 7. never applied twice


def test_an_accepted_commitment_is_applied_once_also_after_reverification() -> None:
    rt = _runtime()
    c = _option_b(rt, delay=1)  # the books move before acceptance: the executor re-verifies the commitment
    books = current_books(rt.store.get_state(), rt.store.commitments())
    assert not [o for o in books.obligations if o.type in invoices.ADJUSTING]
    assert _receipts(_projection(rt))[RI2] == (62, AGREED)  # +15 days once, +0.45% once
    assert _receipts(_projection(rt, mode=Mode.EXPECTED))[RI2] == (62, AGREED)
    rt.advance_to(3)
    assert (_rcv(rt, RI2).face_fen, _rcv(rt, RI2).due_day) == (AGREED, 62)
    assert len(_rcv(rt, RI2).applied) == len(set(_rcv(rt, RI2).applied)) == 2
    # re-verifying the active commitment does not add its terms on top of the state
    assert rt.reverify(c, rt.store.get_state(), rt.store.get_mandate(), rt.day) is not None
