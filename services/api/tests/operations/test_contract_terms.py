"""ADR-0014 §2, §3, §7: SetUpContractTerms and its compensation UndoContractTerms through the executor, on both stores.

Always Tier 2 and owner-only: the owner's request is queued and only the owner's approval runs it; anyone else is refused
before anything is queued, with a PRIVILEGE_ESCALATION event. On approval the executor derives the terms again from the
stored record on today's books and refuses unless they and their hash are the ones shown. Every outcome is on the hash
chain; the undo removes exactly what the set-up wrote."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.contracts import read_document
from app.contracts.terms_setup import derive
from app.domain.fixtures import contract_fixture_bytes
from app.domain.models import (
    Actor,
    DocumentKind,
    OperationStatus,
    RecurringInvoice,
    SecurityEventKind,
    SetUpContractTerms,
    Tier,
    UndoContractTerms,
)
from app.ingest import extract_text
from app.operations import security_summary
from tests.operations.builders import Clock, op

DGOS = (Path(__file__).resolve().parents[4] / "fixtures" / "contract_terms" / "dgos-2026-09-supply-agreement.md").read_text(
    encoding="utf-8")
EXECUTED, REFUSED, PENDING, DUPLICATE = (OperationStatus.EXECUTED, OperationStatus.REFUSED,
                                         OperationStatus.PENDING_APPROVAL, OperationStatus.DUPLICATE)


@pytest.fixture(autouse=True)
def _on(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "1")


def _confirmed(store: Any, ex: Any, text: str = DGOS, cp: str = "BUYER-2") -> str:
    rec = read_document(text, DocumentKind.BUYER_CONTRACT, cp, title="Supply agreement DGOS-2026-09", source="text", day=0,
                        facilities=store.get_state().facilities)
    rid = store.add_contract_record(rec)
    assert ex.decide_document(rid, Actor.OWNER, confirm=True, doc_hash=rec.doc_hash).status == EXECUTED
    return rid


def _set_up(store: Any, clock: Clock, rid: str, *, actor: Actor = Actor.OWNER, key: str | None = None,
            **over: Any) -> SetUpContractTerms:
    rec = store.get_contract_record(rid)
    d = derive(rec, store.get_state(), today=clock.day, horizon_days=store.get_mandate().horizon_days)
    assert d.recurring is not None and d.terms_hash is not None
    ri = d.recurring
    fields = {"document_id": rid, "doc_hash": rec.doc_hash, "terms_hash": d.terms_hash, "counterparty_id": ri.counterparty_id,
              "face_fen": ri.face_fen, "every_days": ri.every_days, "next_issue_day": ri.next_issue_day,
              "terms_days": ri.terms_days, **over}
    return op(SetUpContractTerms, clock, actor=actor, key=key, **fields)


def _run(ex: Any, o: Any) -> Any:
    """The owner's press: queue, then the owner's approval."""
    queued = ex.execute(o)
    assert queued.status == PENDING and queued.tier == Tier.TIER_2, queued.message
    return ex.decide(queued.approval_id, True, Actor.OWNER)


def _buyer2(store: Any) -> list[RecurringInvoice]:
    return [r for r in store.get_state().recurring_invoices if r.counterparty_id == "BUYER-2"]


def test_the_owners_approval_sets_up_the_repeating_invoice_and_the_log_holds_both_rows(store, ex, clock):
    rid = _confirmed(store, ex)
    version = store.get_state().state_version
    r = _run(ex, _set_up(store, clock, rid))
    assert r.status == EXECUTED and r.tier == Tier.TIER_2 and r.approval_id
    # CT-2: written unconfirmed, until the clock issues the first invoice
    assert _buyer2(store) == [RecurringInvoice(counterparty_id="BUYER-2", face_fen=18_000_000, every_days=30,
                                               next_issue_day=14, terms_days=45, confirmed=False)]
    assert store.get_state().state_version == version + 1
    rows = [(o.kind, OperationStatus(__import__("json").loads(o.result_json)["status"])) for o in store.operations()[-2:]]
    assert rows == [("SET_UP_CONTRACT_TERMS", PENDING), ("SET_UP_CONTRACT_TERMS", EXECUTED)]
    s = security_summary(store)
    assert s["unauthorised_executions"] == 0 and s["chain_valid"]


def test_nothing_else_in_the_books_changes(store, ex, clock):
    rid = _confirmed(store, ex)
    before = store.get_state().model_dump(mode="json")
    _run(ex, _set_up(store, clock, rid))
    after = store.get_state().model_dump(mode="json")
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"recurring_invoices", "state_version"}
    assert after["recurring_invoices"][:-1] == before["recurring_invoices"]


@pytest.mark.parametrize("actor", [Actor.AGENT, Actor.COUNTERPARTY, Actor.SYSTEM])
def test_nobody_but_the_owner_can_request_it_and_nothing_is_queued(store, ex, clock, actor):
    rid = _confirmed(store, ex)
    r = ex.execute(_set_up(store, clock, rid, actor=actor))
    assert r.status == REFUSED and r.approval_id is None
    assert r.violations[0].code.value == "INSUFFICIENT_AUTHORITY"
    assert r.violations[0].inputs["refusal"] == "CONTRACT_TERMS_OWNER_ONLY"
    assert not store.approvals() and not _buyer2(store)
    assert store.security_events()[-1].kind == SecurityEventKind.PRIVILEGE_ESCALATION
    assert store.verify_chain()


def test_the_agent_cannot_approve_the_owners_request(store, ex, clock):
    rid = _confirmed(store, ex)
    queued = ex.execute(_set_up(store, clock, rid))
    r = ex.decide(queued.approval_id, True, Actor.AGENT)
    assert r.status == REFUSED and r.violations[0].code.value == "INSUFFICIENT_AUTHORITY"
    assert not _buyer2(store)
    assert store.security_events()[-1].kind == SecurityEventKind.PRIVILEGE_ESCALATION


def test_the_same_set_up_twice_is_one_operation(store, ex, clock):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid, key="contract-terms:test:0")
    assert _run(ex, o).status == EXECUTED
    again = ex.execute(o)
    assert again.status == DUPLICATE and len(_buyer2(store)) == 1


def test_a_second_set_up_under_a_new_key_is_refused_as_already_in_the_books(store, ex, clock):
    rid = _confirmed(store, ex)
    assert _run(ex, _set_up(store, clock, rid)).status == EXECUTED
    o = op(SetUpContractTerms, clock, actor=Actor.OWNER, **{k: v for k, v in _set_up(store, clock, rid).model_dump().items()
                                                         if k not in ("op_id", "idempotency_key", "day", "kind",
                                                                      "requested_by", "mandate_version", "source_verdict_id")})
    queued = ex.execute(o)
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "TERMS_ALREADY_IN_BOOKS"
    assert len(_buyer2(store)) == 1


@pytest.mark.parametrize("over", [
    {"face_fen": 99_000_000},  # figures the owner was not shown
    {"next_issue_day": 2},
    {"terms_hash": "0" * 64},
    {"doc_hash": "1" * 64},
    {"counterparty_id": "BUYER-1"},
])
def test_the_operation_is_bound_to_the_document_and_the_terms_shown(store, ex, clock, over):
    rid = _confirmed(store, ex)
    r = _run(ex, _set_up(store, clock, rid, **over))
    assert r.status == REFUSED and r.violations[0].code.value == "TERMS_CHANGED"
    assert not _buyer2(store)


def test_a_reading_edited_after_confirmation_is_refused_on_approval(store, ex, clock, monkeypatch):
    """The document hash binds the text, not the reading: a stored reading changed after the preview (a row edited in the
    database, which the stores themselves refuse to do once a record is decided) is caught when the executor parses the
    quotes again."""
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    queued = ex.execute(o)
    rec = store.get_contract_record(rid)
    terms = [t.model_copy(update={"amount_fen": 99_000_000}) if t.field.value == "PRICE" else t for t in rec.contract.terms]
    tampered = rec.model_copy(update={"contract": rec.contract.model_copy(update={"terms": terms})})
    monkeypatch.setattr(store, "get_contract_record", lambda _id: tampered)  # what the edited row now loads as
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "TERMS_BLOCKED"
    assert "FIGURE_NOT_IN_QUOTE" in r.violations[0].inputs["problems"]
    assert not _buyer2(store)


def test_terms_shown_on_another_day_are_refused(store, ex, clock):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)  # the next invoice on day 14
    clock.day = 20  # the contract's next invoice is now day 44
    r = _run(ex, o.model_copy(update={"day": 20}))
    assert r.status == REFUSED and r.violations[0].code.value == "TERMS_CHANGED"


def test_a_customer_with_other_repeating_invoices_is_refused_on_conflict(store, ex, clock):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    queued = ex.execute(o)
    s = store.get_state()
    other = RecurringInvoice(counterparty_id="BUYER-2", face_fen=10_000_000, every_days=30, next_issue_day=5, terms_days=30)
    store.put_state(s.model_copy(update={"recurring_invoices": [*s.recurring_invoices, other],
                                         "state_version": s.state_version + 1}), expected_version=s.state_version)
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "REPEATING_INVOICE_EXISTS"
    assert _buyer2(store) == [other]


def test_the_demo_customers_contract_is_already_in_the_books(store, ex, clock):
    name, data = contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")
    rid = _confirmed(store, ex, extract_text(name, data), "BUYER-1")
    before = store.get_state().recurring_invoices
    r = _run(ex, _set_up(store, clock, rid))
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "TERMS_ALREADY_IN_BOOKS"
    assert store.get_state().recurring_invoices == before


def test_an_unconfirmed_document_sets_nothing_up(store, ex, clock):
    rec = read_document(DGOS, DocumentKind.BUYER_CONTRACT, "BUYER-2", title="t", source="text", day=0, facilities=[])
    rid = store.add_contract_record(rec)
    d = derive(rec.model_copy(update={"status": "CONFIRMED"}), store.get_state(), today=0, horizon_days=120)
    ri = d.recurring
    o = op(SetUpContractTerms, clock, actor=Actor.OWNER, document_id=rid, doc_hash=rec.doc_hash, terms_hash=d.terms_hash,
           counterparty_id="BUYER-2", face_fen=ri.face_fen, every_days=ri.every_days, next_issue_day=ri.next_issue_day,
           terms_days=ri.terms_days)
    r = _run(ex, o)
    assert r.status == REFUSED and "NOT_CONFIRMED" in r.violations[0].inputs["problems"]


def test_switched_off_it_sets_nothing_up_whichever_route_queued_it(store, ex, clock, monkeypatch):
    rid = _confirmed(store, ex)
    queued = ex.execute(_set_up(store, clock, rid))
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "0")
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == REFUSED and r.violations[0].code.value == "FEATURE_DISABLED"
    assert not _buyer2(store)


# ---------------------------------------------------------------- the compensating operation


def _undo(clock: Clock, set_up_op_id: str, actor: Actor = Actor.OWNER, cp: str = "BUYER-2") -> UndoContractTerms:
    return op(UndoContractTerms, clock, actor=actor, set_up_op_id=set_up_op_id, counterparty_id=cp)


def test_the_undo_removes_what_the_set_up_wrote_and_is_logged(store, ex, clock):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    _run(ex, o)
    r = _run(ex, _undo(clock, o.op_id))
    assert r.status == EXECUTED and not _buyer2(store)
    assert store.operations()[-1].kind == "UNDO_CONTRACT_TERMS" and store.verify_chain()
    assert security_summary(store)["unauthorised_executions"] == 0


def test_the_undo_runs_once_and_only_for_the_owner(store, ex, clock):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    _run(ex, o)
    agent = ex.execute(_undo(clock, o.op_id, Actor.AGENT))
    assert agent.status == REFUSED and agent.approval_id is None and len(_buyer2(store)) == 1
    assert _run(ex, _undo(clock, o.op_id)).status == EXECUTED
    twice = _run(ex, _undo(clock, o.op_id))
    assert twice.status == REFUSED and "already undone" in twice.message


def test_the_undo_refuses_when_the_books_no_longer_hold_what_was_set_up(store, ex, clock):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    _run(ex, o)
    s = store.get_state()
    changed = [r.model_copy(update={"face_fen": 1}) if r.counterparty_id == "BUYER-2" else r for r in s.recurring_invoices]
    store.put_state(s.model_copy(update={"recurring_invoices": changed, "state_version": s.state_version + 1}),
                    expected_version=s.state_version)
    r = _run(ex, _undo(clock, o.op_id))
    assert r.status == REFUSED and "no longer the one in the books" in r.message


def test_an_undone_set_up_can_be_set_up_again_as_a_new_operation(store, ex, clock):
    rid = _confirmed(store, ex)
    first = _set_up(store, clock, rid, key="contract-terms:x:0")
    _run(ex, first)
    _run(ex, _undo(clock, first.op_id))
    assert _run(ex, _set_up(store, clock, rid, key="contract-terms:x:1")).status == EXECUTED
    assert len(_buyer2(store)) == 1


def test_an_undo_of_a_set_up_that_never_ran_is_refused(store, ex, clock):
    r = _run(ex, _undo(clock, "terms-DOC-000009-abc-0"))
    assert r.status == REFUSED and "nothing to undo" in r.message
