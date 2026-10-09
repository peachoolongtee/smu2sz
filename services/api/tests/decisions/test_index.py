"""Map #65 debt, ticket #87: deriving many decisions reads the shared records once (`RecordIndex`), and the index answers exactly
what the per-decision scans it replaced answered, in the same order."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.decisions import DecisionInputs, decision_id_for, derive, derive_all
from app.decisions import state as state_module
from app.decisions.state import RecordIndex, _approval_members, _lots_of, _run_members
from app.domain.models import FundingLot, OperationStatus
from app.persistence.records import ApprovalStatus

from .builders import accept_approval, accept_run, approval, books, fact_row, leg_run, quoted

OK, PENDING = OperationStatus.EXECUTED, OperationStatus.PENDING_APPROVAL
DECISIONS = 25


def _cure(n: int) -> str:
    return f"alert:ALERT-X{n}:v1"


def _records(count: int = DECISIONS):
    """One request's records: `count` cure decisions, each with two logged legs, one approval and a quote; a deal beside them."""
    log, approvals, facts, lots = [], [], [], []
    seq = 0
    for n in range(count):
        for leg in range(2):
            seq += 1
            log.append(leg_run(seq, leg, OK if leg == 0 else PENDING, base=_cure(n), approval_id=f"APR-{n}" if leg else None))
        approvals.append(approval(f"APR-{n}", "DRAW_FACILITY", f"{_cure(n)}:1", ApprovalStatus.PENDING, op_id=f"{_cure(n)}:1",
                                  facility_id="FAC-LINE", amount_fen=1))
        facts.append(fact_row(_cure(n), _cure(n), quoted(legs=2), seq=n + 1, day=n))
        lots.append(FundingLot(id=f"{_cure(n)}:0#1", facility_id="FAC-LINE", principal_fen=1, remaining_fen=1, request_day=1,
                               arrival_day=2, settled=False))
    seq += 1
    log.append(accept_run(seq, OK))
    approvals.append(accept_approval("APR-ACCEPT", ApprovalStatus.PENDING))
    return tuple(log), tuple(approvals), tuple(facts), tuple(lots)


def _inputs(count: int = DECISIONS) -> list[DecisionInputs]:
    log, approvals, facts, lots = _records(count)
    state = books(lots=list(lots))
    return [DecisionInputs(decision_id=_cure(n), today=40, approvals=approvals, log=log, facts=facts, state=state)
            for n in range(count)]


def test_deriving_many_decisions_identifies_each_record_once(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = _inputs()
    calls = 0
    real = decision_id_for

    def counted(*a, **k):
        nonlocal calls
        calls += 1
        return real(*a, **k)

    monkeypatch.setattr(state_module, "decision_id_for", counted)
    states = derive_all(inputs)
    log_len, approvals_len = len(inputs[0].log), len(inputs[0].approvals)
    assert len(states) == DECISIONS
    assert calls == log_len + approvals_len  # not once per decision over the whole log


def test_the_work_does_not_grow_with_the_number_of_decisions(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    real = decision_id_for

    def counted(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(state_module, "decision_id_for", counted)
    derive_all(_inputs(10))
    small = calls["n"] / (10 * 3 + 2)
    calls["n"] = 0
    derive_all(_inputs(40))
    assert calls["n"] / (40 * 3 + 2) == small == 1.0  # one identification per stored record, whatever the number of decisions


def test_the_index_finds_the_same_members_as_the_scans_it_replaced() -> None:
    inputs = _inputs()
    extra = frozenset({f"{_cure(3)}:0", "accept-CMT-1"})
    idx = RecordIndex.for_inputs(inputs[0])
    for i in [*inputs, replace(inputs[0], decision_id="deal:OFF-1")]:
        indexed = replace(i, index=idx)
        want_runs = [e for e in i.log if decision_id_for(e.payload, e.idempotency_key, i.commitments,
                                                          approval_id=e.result.approval_id) == i.decision_id
                     or e.payload.get("op_id") in extra]
        assert _run_members(indexed, extra) == want_runs
        want_approvals = [a for a in i.approvals if decision_id_for(
            json.loads(a.op_json), json.loads(a.op_json).get("idempotency_key") or "", i.commitments, approval_id=a.id) == i.decision_id]
        assert _approval_members(indexed) == want_approvals


def test_lots_are_found_by_operation_id_in_the_books_order() -> None:
    i = _inputs(6)[0]
    assert i.state is not None
    idx = RecordIndex.for_inputs(i)
    op_ids = [f"{_cure(4)}:0", f"{_cure(1)}:0", "unknown"]
    scan = tuple(lot for lot in i.state.lots if any(lot.id == o or lot.id.startswith(o + "#") for o in op_ids))
    assert _lots_of(i.state, op_ids, idx) == scan and len(scan) == 2
    other = books(lots=list(i.state.lots))  # other books: the index is not trusted, the scan answers
    assert _lots_of(other, op_ids, idx) == scan


def test_an_unreadable_approval_belongs_to_its_own_record_but_names_no_candidate() -> None:
    bad = approval("APR-BAD", "DRAW_FACILITY", "k", ApprovalStatus.PENDING)
    bad = replace(bad, op_json="not json")
    idx = RecordIndex.of(log=(), approvals=(bad,), commitments=(), facts=(), verdicts=(), promised=())
    assert idx.approvals == {"approval:APR-BAD": (bad,)} and idx.approval_candidates == ()


def test_derive_without_an_index_gives_the_same_state_as_with_one() -> None:
    inputs = _inputs(8)
    shared = derive_all(inputs)
    alone = [derive(i) for i in inputs]
    assert shared == alone
