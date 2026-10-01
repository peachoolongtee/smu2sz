"""Current books (ADR-0006): closed days, outstanding face, live and lapsed obligations."""

from __future__ import annotations

from app.books import current_books
from app.domain.fixtures import load_scenario
from app.domain.models import (
    BaseKind,
    Commitment,
    CommitmentStatus,
    Contingency,
    Duration,
    DurationKind,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    SourceSpan,
)
from app.financial import project

H = 120


def _state():
    return load_scenario("golden_sme")[0]


def _early_pay(rid: str, face: int, day: int, bp: int = 85) -> Obligation:
    return Obligation(id=f"OB-{rid}", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id="BUYER-1", rate_bp=bp,
                      effective_day=day, base=ObligationBase(kind=BaseKind.INVOICE, receivable_id=rid, amount_fen=face),
                      contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF),
                      spans=[SourceSpan(doc_id="T", start=0, end=0, text="")], confidence=1.0)


def _commitment(ob: Obligation, status: CommitmentStatus = CommitmentStatus.ACTIVE) -> Commitment:
    return Commitment(id=f"CMT-{ob.id}", offer_id="OFF", offer_version=1, counterparty_id=ob.counterparty_id,
                      verdict_id="V", terms_hash="h", obligations=[ob], status=status, nonce="n", expires_day=7,
                      mandate_version=1, forward_value_fen=0)


def test_day_zero_books_equal_raw_state():
    s = _state()
    b = current_books(s, [])
    assert b.state is s and b.obligations == () and b.lapsed == () and b.day == 0


def test_closed_days_drop_posted_flows_and_unpaid_receipts():
    s = _state()
    base = project(s, [], [], Mode.CONSERVATIVE, H)
    first_flow = min(f.day for f in s.flows if f.day > 0)
    later = s.model_copy(update={"as_of_day": first_flow + 1})
    t = project(later, [], [], Mode.CONSERVATIVE, H)
    dropped = sum(f.amount_fen for f in s.flows if f.day <= first_flow and (f.confirmed or f.amount_fen < 0))
    overdue = sum(r.outstanding_fen for r in s.receivables if r.status == "OPEN" and r.due_day <= first_flow)
    assert t.days[H].closing_fen == base.days[H].closing_fen - dropped - overdue
    assert all(d.closing_fen == later.cash_fen for d in t.days[: first_flow + 1])  # the past is flat


def test_overdue_receivable_is_not_assumed_to_arrive():
    s = _state()
    r = min((r for r in s.receivables if r.status == "OPEN"), key=lambda r: r.due_day)
    # same flows posted or not, only the receipt differs: compare two states that differ only in that receivable
    late = s.model_copy(update={"as_of_day": r.due_day + 2})
    paid = late.model_copy(update={"receivables": [x.model_copy(update={"status": "SETTLED"}) if x.id == r.id else x
                                                    for x in late.receivables]})
    assert project(late, [], [], Mode.CONSERVATIVE, H).days[H].closing_fen == \
        project(paid, [], [], Mode.CONSERVATIVE, H).days[H].closing_fen


def test_partial_settlement_projects_the_outstanding_face():
    s = _state()
    r = next(r for r in s.receivables if r.status == "OPEN")
    part = r.face_fen // 2
    s2 = s.model_copy(update={"receivables": [x.model_copy(update={"settled_fen": part}) if x.id == r.id else x
                                               for x in s.receivables]})
    a, b = project(s, [], [], Mode.CONSERVATIVE, H), project(s2, [], [], Mode.CONSERVATIVE, H)
    assert a.days[H].closing_fen - b.days[H].closing_fen == part
    assert a.days[max(0, r.due_day - 1)].closing_fen == b.days[max(0, r.due_day - 1)].closing_fen


def test_live_obligation_is_in_the_books_and_proposed_is_not():
    s = _state()
    r = next(r for r in s.receivables if r.status == "OPEN" and r.due_day > 5)
    ob = _early_pay(r.id, r.face_fen, 2)
    assert current_books(s, [_commitment(ob)]).obligations == (ob,)
    assert current_books(s, [_commitment(ob, CommitmentStatus.PROPOSED)]).obligations == ()
    assert current_books(s, [_commitment(ob, CommitmentStatus.REVOKED)]).obligations == ()


def test_missed_early_payment_lapses_and_the_receivable_reverts():
    s = _state()
    r = next(r for r in s.receivables if r.status == "OPEN" and r.due_day > 10)
    ob = _early_pay(r.id, r.face_fen, 2)
    later = s.model_copy(update={"as_of_day": 5})
    b = current_books(later, [_commitment(ob)])
    assert b.obligations == () and [x.reason for x in b.lapsed] == ["EARLY_PAYMENT_MISSED"]
    t = project(b.state, list(b.obligations), [], Mode.CONSERVATIVE, H)
    assert any(e.ref == r.id and e.day == r.due_day for d in t.days for e in d.events)  # back on its due day


def test_settled_receivable_lapses_its_obligation():
    s = _state()
    r = next(r for r in s.receivables if r.status == "OPEN" and r.due_day > 5)
    ob = _early_pay(r.id, r.face_fen, 2)
    done = s.model_copy(update={"receivables": [x.model_copy(update={"status": "SETTLED", "settled_fen": x.face_fen})
                                                 if x.id == r.id else x for x in s.receivables]})
    b = current_books(done, [_commitment(ob)])
    assert b.obligations == () and b.lapsed[0].reason == "RECEIVABLE_SETTLED"
