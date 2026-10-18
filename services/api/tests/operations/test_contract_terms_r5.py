"""Round five, the engine half (owner-approved): contract terms fail closed in the executor, on both stores.

- CT-6: a set-up is refused before it is queued while FEATURE_CONTRACT_TERMS is off (logged, nothing queued); the undo runs
  with the flag off, so the owner can always remove what a set-up wrote.
- CT-7: anyone but the owner is refused by the owner-only check before any other gate or lookup, whatever the operation
  carries (a wrong mandate version, a stale day, an unknown document, a reused key), with a PRIVILEGE_ESCALATION event.
- REG-5: deciding a refile-closed record again is refused, never answered with the REFILE entry; a refile-closed or a
  party-not-named record never sets anything up at execution time.
- CT-2: the CONSERVATIVE forecast does not count a set-up's invoices until the clock has issued the first one; EXPECTED
  does; the executor re-derives the terms with the mandate, as the preview does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.clock import advance
from app.contracts import read_document
from app.contracts.terms_setup import derive
from app.domain.fixtures import load_scenario
from app.domain.models import (
    Actor,
    DocumentFlag,
    DocumentKind,
    Mode,
    OperationStatus,
    SecurityEventKind,
    SetUpContractTerms,
    SourceSpan,
    Tier,
    UndoContractTerms,
)
from app.financial import project
from app.persistence.canonical import canonical_json
from tests.operations.builders import Clock, op

DGOS = (Path(__file__).resolve().parents[4] / "fixtures" / "contract_terms" / "dgos-2026-09-supply-agreement.md").read_text(
    encoding="utf-8")
EXECUTED, REFUSED, PENDING = OperationStatus.EXECUTED, OperationStatus.REFUSED, OperationStatus.PENDING_APPROVAL


@pytest.fixture(autouse=True)
def _on(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "1")


def _confirmed(store: Any, ex: Any, cp: str = "BUYER-2") -> str:
    rec = read_document(DGOS, DocumentKind.BUYER_CONTRACT, cp, title="Supply agreement DGOS-2026-09", source="text", day=0,
                        facilities=store.get_state().facilities)
    rid = store.add_contract_record(rec)
    assert ex.decide_document(rid, Actor.OWNER, confirm=True, doc_hash=rec.doc_hash).status == EXECUTED
    return rid


def _set_up(store: Any, clock: Clock, rid: str, *, actor: Actor = Actor.OWNER, **over: Any) -> SetUpContractTerms:
    rec = store.get_contract_record(rid)
    d = derive(rec, store.get_state(), today=clock.day, horizon_days=store.get_mandate().horizon_days)
    assert d.recurring is not None and d.terms_hash is not None
    ri = d.recurring
    fields = {"document_id": rid, "doc_hash": rec.doc_hash, "terms_hash": d.terms_hash, "counterparty_id": ri.counterparty_id,
              "face_fen": ri.face_fen, "every_days": ri.every_days, "next_issue_day": ri.next_issue_day,
              "terms_days": ri.terms_days, **over}
    return op(SetUpContractTerms, clock, actor=actor, **fields)


def _undo(clock: Clock, set_up_op_id: str, actor: Actor = Actor.OWNER, **over: Any) -> UndoContractTerms:
    return op(UndoContractTerms, clock, actor=actor, **{"set_up_op_id": set_up_op_id, "counterparty_id": "BUYER-2", **over})


def _run(ex: Any, o: Any) -> Any:
    queued = ex.execute(o)
    assert queued.status == PENDING and queued.tier == Tier.TIER_2, queued.message
    return ex.decide(queued.approval_id, True, Actor.OWNER)


def _buyer2(store: Any) -> list[Any]:
    return [r for r in store.get_state().recurring_invoices if r.counterparty_id == "BUYER-2"]


def _last_row(store: Any) -> tuple[str, str]:
    row = store.operations()[-1]
    return row.kind, json.loads(row.result_json)["status"]


# ---------------------------------------------------------------- CT-6


def test_ct6_switched_off_a_set_up_is_refused_before_it_is_queued_and_logged(store, ex, clock, monkeypatch):
    rid = _confirmed(store, ex)
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "0")
    n = len(store.operations())
    r = ex.execute(_set_up(store, clock, rid))
    assert r.status == REFUSED and r.approval_id is None
    assert r.violations[0].code.value == "FEATURE_DISABLED" and r.violations[0].inputs["refusal"] == "CONTRACT_TERMS_OFF"
    assert "nothing was queued" in r.message
    assert not store.approvals() and not _buyer2(store)
    assert len(store.operations()) == n + 1 and _last_row(store) == ("SET_UP_CONTRACT_TERMS", "REFUSED")
    assert store.verify_chain()


def test_ct6_switched_off_the_owner_can_still_undo_a_set_up(store, ex, clock, monkeypatch):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    assert _run(ex, o).status == EXECUTED and len(_buyer2(store)) == 1
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "0")
    r = _run(ex, _undo(clock, o.op_id))
    assert r.status == EXECUTED and not _buyer2(store)
    assert _last_row(store) == ("UNDO_CONTRACT_TERMS", "EXECUTED")


def test_ct6_switched_off_the_undo_stays_owner_only(store, ex, clock, monkeypatch):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    _run(ex, o)
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "0")
    r = ex.execute(_undo(clock, o.op_id, Actor.AGENT))
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "CONTRACT_TERMS_OWNER_ONLY"
    assert len(_buyer2(store)) == 1


# ---------------------------------------------------------------- CT-7

_GARBAGE: list[dict[str, Any]] = [
    {"mandate_version": 99},  # a wrong mandate version: the mandate gate used to answer first, with no escalation logged
    {"day": 7},  # dated for another day
    {"document_id": "DOC-999999"},  # no such document
    {"doc_hash": "f" * 64, "terms_hash": "e" * 64, "face_fen": 1},
]


@pytest.mark.parametrize("actor", [Actor.AGENT, Actor.COUNTERPARTY, Actor.SYSTEM])
@pytest.mark.parametrize("over", _GARBAGE)
def test_ct7_a_non_owner_set_up_gets_the_owner_only_refusal_whatever_it_carries(store, ex, clock, actor, over):
    rid = _confirmed(store, ex)
    events = len(store.security_events())
    r = ex.execute(_set_up(store, clock, rid, actor=actor, **over))
    assert r.status == REFUSED and r.approval_id is None and r.tier == Tier.TIER_2
    assert [v.code.value for v in r.violations] == ["INSUFFICIENT_AUTHORITY"]
    assert r.violations[0].inputs["refusal"] == "CONTRACT_TERMS_OWNER_ONLY"
    new = store.security_events()[events:]
    assert [e.kind for e in new] == [SecurityEventKind.PRIVILEGE_ESCALATION] and new[0].counterparty_id == "BUYER-2"
    assert _last_row(store) == ("SET_UP_CONTRACT_TERMS", "REFUSED")
    assert not store.approvals() and not _buyer2(store)


@pytest.mark.parametrize("over", [{"mandate_version": 99}, {"day": 7}, {"counterparty_id": "BUYER-9"}])
def test_ct7_a_non_owner_undo_gets_the_owner_only_refusal_whatever_it_carries(store, ex, clock, over):
    events = len(store.security_events())
    r = ex.execute(_undo(clock, "terms-DOC-000009-abc-0", Actor.AGENT, **over))
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "CONTRACT_TERMS_OWNER_ONLY"
    assert [e.kind for e in store.security_events()[events:]] == [SecurityEventKind.PRIVILEGE_ESCALATION]


def test_ct7_the_owner_only_check_comes_before_the_feature_flag(store, ex, clock, monkeypatch):
    rid = _confirmed(store, ex)
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "0")
    r = ex.execute(_set_up(store, clock, rid, actor=Actor.AGENT))
    assert r.violations[0].inputs["refusal"] == "CONTRACT_TERMS_OWNER_ONLY"


def test_ct7_a_key_the_owner_used_does_not_change_a_non_owners_refusal(store, ex, clock):
    rid = _confirmed(store, ex)
    mine = _set_up(store, clock, rid)
    assert _run(ex, mine).status == EXECUTED
    agent = _set_up(store, clock, rid, actor=Actor.AGENT).model_copy(update={"idempotency_key": mine.idempotency_key})
    r = ex.execute(agent)
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "CONTRACT_TERMS_OWNER_ONLY"
    assert store.security_events()[-1].kind == SecurityEventKind.PRIVILEGE_ESCALATION


def test_ct7_the_owners_own_wrong_mandate_version_is_still_refused_by_the_mandate_gate(store, ex, clock):
    rid = _confirmed(store, ex)
    r = ex.execute(_set_up(store, clock, rid, mandate_version=99))
    assert r.status == REFUSED and r.violations[0].code.value == "MANDATE_VERSION_MISMATCH"
    assert not store.approvals()


# ---------------------------------------------------------------- REG-5, the executor half


def _refile(store: Any, rid: str, to: str, day: int = 0) -> str:
    """What POST /documents/{id}/refile writes: the record again under `to`, a REFILE_DOCUMENT entry, the old record closed."""
    from app.domain.models import OperationResult

    rec = store.get_contract_record(rid)
    new_id = store.add_contract_record(rec.model_copy(update={"counterparty_id": to}))
    op_id = f"REFILE-{rid}-{day}-{len(store.operations()) + 1}"
    payload = {"kind": "REFILE_DOCUMENT", "op_id": op_id, "document_id": rid, "new_document_id": new_id,
               "from_counterparty_id": rec.counterparty_id, "counterparty_id": to, "doc_hash": rec.doc_hash,
               "requested_by": "OWNER", "day": day}
    result = OperationResult(op_id=op_id, kind="REFILE_DOCUMENT", status=EXECUTED, tier=Tier.TIER_2, effective_day=day,
                             message=f"Document {rid} filed again under {to} as {new_id} by the owner")
    entry = store.append_operation(op_id, "REFILE_DOCUMENT", op_id, canonical_json(payload), canonical_json(result))
    store.close_refiled_record(rid, new_id, day, entry.seq)
    return new_id


def _proposed(store: Any, cp: str) -> str:
    rec = read_document(DGOS, DocumentKind.BUYER_CONTRACT, cp, title="Supply agreement", source="text", day=0,
                        facilities=store.get_state().facilities)
    return store.add_contract_record(rec)


@pytest.mark.parametrize("confirm", [False, True])
def test_reg5_deciding_a_refile_closed_record_again_is_refused_not_answered_with_the_refile(store, ex, confirm):
    wrong = _proposed(store, "BUYER-1")
    new_id = _refile(store, wrong, "BUYER-2")
    rec = store.get_contract_record(wrong)
    refile_seq = rec.decided_seq
    r = ex.decide_document(wrong, Actor.OWNER, confirm=confirm, doc_hash=rec.doc_hash)
    assert r.status == REFUSED and r.kind == ("CONFIRM_DOCUMENT" if confirm else "REJECT_DOCUMENT")
    assert r.seq != refile_seq and "REFILE" not in r.op_id
    assert r.violations[0].code.value == "PRECONDITION_FAILED" and r.violations[0].inputs["superseded_by"] == new_id
    assert f"filed again as {new_id}" in r.message
    assert store.get_contract_record(wrong).decided_seq == refile_seq  # the record is unchanged
    assert store.verify_chain()


def test_reg5_a_real_reject_sent_twice_is_still_answered_with_the_first(store, ex):
    rid = _proposed(store, "BUYER-2")
    rec = store.get_contract_record(rid)
    first = ex.decide_document(rid, Actor.OWNER, confirm=False, doc_hash=rec.doc_hash)
    n = len(store.operations())
    again = ex.decide_document(rid, Actor.OWNER, confirm=False, doc_hash=rec.doc_hash)
    assert first.status == again.status == EXECUTED and again.seq == first.seq and len(store.operations()) == n


def test_reg5_a_refile_closed_record_sets_nothing_up_at_execution(store, ex, clock, monkeypatch):
    """The owner's queued set-up of a contract later filed again (closed, REJECTED, superseded) is refused when it runs:
    the closed record never sets up its old customer's invoices."""
    rid = _proposed(store, "BUYER-2")
    rec = store.get_contract_record(rid)
    confirmed_view = rec.model_copy(update={"status": "CONFIRMED"})
    monkeypatch.setattr(store, "get_contract_record", lambda _id, _orig=store.get_contract_record:
                        confirmed_view if _id == rid else _orig(_id))
    o = _set_up(store, clock, rid)
    queued = ex.execute(o)
    monkeypatch.undo()
    monkeypatch.setenv("FEATURE_CONTRACT_TERMS", "1")
    _refile(store, rid, "BUYER-1")
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "TERMS_BLOCKED"
    problems = str(r.violations[0].inputs["problems"])
    assert "NOT_CONFIRMED" in problems or "SUPERSEDED" in problems
    assert not _buyer2(store)


def test_reg5_a_party_not_named_record_sets_nothing_up_at_execution(store, ex, clock, monkeypatch):
    rid = _confirmed(store, ex)
    queued = ex.execute(_set_up(store, clock, rid))
    rec = store.get_contract_record(rid)
    flagged = rec.model_copy(update={"flags": [*rec.flags, DocumentFlag(kind="PARTY_NOT_NAMED", span=SourceSpan(doc_id=rec.id, start=0, end=6, text=rec.document.text[:6]),
                                                                       blocking=True, note="the buyer is not named")]})
    monkeypatch.setattr(store, "get_contract_record", lambda _id: flagged)
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == REFUSED and r.violations[0].inputs["refusal"] == "TERMS_BLOCKED"
    assert "FLAGGED" in r.violations[0].inputs["problems"]
    assert not _buyer2(store)


# ---------------------------------------------------------------- CT-2


def _receipts(state: Any, mandate: Any, mode: Mode) -> list[tuple[int, int]]:
    traj = project(state, [], [], mode, mandate.horizon_days, mandate.min_cash_fen)
    return [(p.day, e.amount_fen) for p in traj.days for e in p.events if (e.ref or "").startswith("RI:BUYER-2:")]


def _closing(state: Any, mandate: Any, mode: Mode) -> list[tuple[int, int]]:
    traj = project(state, [], [], mode, mandate.horizon_days, mandate.min_cash_fen)
    return [(p.day, p.closing_fen) for p in traj.days]


def test_ct2_a_fresh_set_up_leaves_the_conservative_forecast_unchanged_until_the_first_issue(store, ex, clock):
    rid = _confirmed(store, ex)
    m = store.get_mandate()
    before = store.get_state()
    assert _run(ex, _set_up(store, clock, rid)).status == EXECUTED
    after = store.get_state()
    (ri,) = _buyer2(store)
    assert ri.confirmed is False and ri.next_issue_day == 14
    assert _closing(after, m, Mode.CONSERVATIVE) == _closing(before, m, Mode.CONSERVATIVE)
    assert _receipts(after, m, Mode.CONSERVATIVE) == []
    # EXPECTED counts them as before
    assert _receipts(after, m, Mode.EXPECTED) == [(59, 18_000_000), (89, 18_000_000), (119, 18_000_000)]
    # the day before the first issue the conservative forecast still waits
    advance(store, 14, Actor.SYSTEM)
    assert _buyer2(store)[0].confirmed is False and _receipts(store.get_state(), m, Mode.CONSERVATIVE) == []


def test_ct2_once_the_clock_issues_the_first_invoice_the_conservative_forecast_counts_them(store, ex, clock):
    rid = _confirmed(store, ex)
    m = store.get_mandate()
    _run(ex, _set_up(store, clock, rid))
    adv = advance(store, 15, Actor.SYSTEM)
    assert "RI:BUYER-2:14" in adv.issued_receivable_ids
    (ri,) = _buyer2(store)
    assert ri.confirmed is True and ri.next_issue_day == 44
    issued = next(r for r in store.get_state().receivables if r.id == "RI:BUYER-2:14")
    assert issued.confirmed
    assert _receipts(store.get_state(), m, Mode.CONSERVATIVE)[:3] == [(59, 18_000_000), (89, 18_000_000), (119, 18_000_000)]


def test_ct2_the_undo_still_removes_an_unconfirmed_and_a_confirmed_schedule(store, ex, clock):
    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    _run(ex, o)
    advance(store, 15, Actor.SYSTEM)
    clock.day = 15
    assert _run(ex, _undo(clock, o.op_id)).status == EXECUTED and not _buyer2(store)


def test_ct2_the_executor_re_derives_the_terms_with_the_mandate(store, ex, clock, monkeypatch):
    import app.contracts.terms_setup as ts

    rid = _confirmed(store, ex)
    o = _set_up(store, clock, rid)
    queued = ex.execute(o)
    seen: list[Any] = []
    real = ts.derive

    def spy(*a: Any, **k: Any) -> Any:
        seen.append(k.get("mandate"))
        return real(*a, **k)

    monkeypatch.setattr(ts, "derive", spy)
    assert ex.decide(queued.approval_id, True, Actor.OWNER).status == EXECUTED
    assert seen and seen[-1] is not None and seen[-1].version == store.get_mandate().version


def test_ct2_the_mandate_cap_refuses_an_outsized_invoice_at_execution(store, ex, clock, monkeypatch):
    """The preview and the executor apply the same cap: an invoice above max(3 x the customer's largest receivable, the
    mandate ceiling) is OUTSIZED when it runs, even when the owner's operation was queued from a laxer reading."""
    import app.contracts.terms_setup as ts

    rid = _confirmed(store, ex)
    queued = ex.execute(_set_up(store, clock, rid))
    real = ts._outsized

    def strict(state: Any, cp: str, face: int, every: int, mandate: Any) -> Any:
        if mandate is None:  # what the executor passed before CT-2: no mandate, no ceiling
            return real(state, cp, face, every, mandate)
        return real(state, cp, face, every, mandate.model_copy(update={"tier2_single_commitment_fen": 1, "min_cash_fen": 1}))

    monkeypatch.setattr(ts, "_outsized", strict)
    r = ex.decide(queued.approval_id, True, Actor.OWNER)
    assert r.status == REFUSED and "OUTSIZED" in r.violations[0].inputs["problems"]
    assert not _buyer2(store)


def test_ct2_the_golden_books_serialise_exactly_as_before():
    """Every repeating invoice outside a contract set-up is confirmed, so its serialised form (and every state digest and
    verdict id) is unchanged: no `confirmed` key."""
    state, _ = load_scenario()
    assert state.recurring_invoices and all(r.confirmed for r in state.recurring_invoices)
    assert all("confirmed" not in r.model_dump(mode="json") for r in state.recurring_invoices)
    assert "confirmed" not in json.dumps(state.model_dump(mode="json")["recurring_invoices"])
    unconfirmed = state.recurring_invoices[0].model_copy(update={"confirmed": False})
    assert unconfirmed.model_dump(mode="json")["confirmed"] is False
    assert type(unconfirmed).model_validate_json(unconfirmed.model_dump_json()) == unconfirmed
