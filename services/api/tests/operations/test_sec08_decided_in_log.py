"""SEC-08 (security register), executor half: an approval the log shows as decided is never decided again.

The database refuses to put a decided approval back to PENDING (`app/persistence/guards.py`), but whoever owns the tables can drop that
guard. Before this, a REJECTED approval reset to PENDING that way was then approved and EXECUTED, the hash chain still valid (reproduced
on SQLite and PostgreSQL 17). The executor now also reads the log: the owner's decision for an approval is already there (the decline,
a refusal at decision time, or the approved run), so a second decision is refused as already decided and nothing runs."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.domain.models import AcceptOffer, Actor, OperationStatus
from app.persistence import ApprovalAlreadyDecided, ApprovalStatus
from tests.operations.builders import Clock, extension, op, seed_offer


def _queue(ex: Any, store: Any, clock: Clock) -> tuple[Any, str]:
    c = seed_offer(store, ex, obligations=[extension()], expires_day=30)
    pending = ex.execute(op(AcceptOffer, clock, offer_id=c.offer_id, offer_version=1, terms_hash=c.terms_hash, nonce=c.nonce))
    assert pending.status == OperationStatus.PENDING_APPROVAL and pending.approval_id
    return c, pending.approval_id


def _back_to_pending(store: Any, aid: str, db: Path) -> None:
    """What someone with the tables can do: the memory store's row replaced, or SQLite's guard dropped and the row updated."""
    if hasattr(store, "_approvals"):
        store._approvals[aid] = replace(store._approvals[aid], status=ApprovalStatus.PENDING, decided_by=None, decided_day=None)
    else:
        with sqlite3.connect(db) as conn:
            conn.execute("DROP TRIGGER IF EXISTS trg_approvals_decide_once")
            conn.execute("UPDATE approvals SET status='PENDING', decided_by=NULL, decided_day=NULL WHERE id=?", (aid,))
    assert store.get_approval(aid).status == ApprovalStatus.PENDING


def test_a_declined_approval_put_back_to_pending_is_not_approved(ex: Any, store: Any, clock: Clock, tmp_path: Path) -> None:
    c, aid = _queue(ex, store, clock)
    assert ex.decide(aid, False, Actor.OWNER).status == OperationStatus.REFUSED
    before, rows = store.get_state(), len(store.operations())
    _back_to_pending(store, aid, tmp_path / "ledger.db")
    with pytest.raises(ApprovalAlreadyDecided, match="already decided"):
        ex.decide(aid, True, Actor.OWNER)
    assert store.get_state() == before and len(store.operations()) == rows  # nothing ran, nothing logged
    assert store.get_commitment(c.id).status == "PROPOSED"
    assert store.verify_chain()


def test_an_approved_approval_put_back_to_pending_runs_once(ex: Any, store: Any, clock: Clock, tmp_path: Path) -> None:
    _c, aid = _queue(ex, store, clock)
    assert ex.decide(aid, True, Actor.OWNER).status == OperationStatus.EXECUTED
    rows = len(store.operations())
    _back_to_pending(store, aid, tmp_path / "ledger.db")
    for approved in (True, False):
        with pytest.raises(ApprovalAlreadyDecided):
            ex.decide(aid, approved, Actor.OWNER)
    assert len(store.operations()) == rows
    assert len(store.get_state().forward_concessions) == 1


def test_another_actors_refused_attempt_is_not_the_owners_decision(ex: Any, store: Any, clock: Clock) -> None:
    _c, aid = _queue(ex, store, clock)
    assert ex.decide(aid, True, Actor.AGENT).status == OperationStatus.REFUSED  # logged under `#decide:`
    assert ex.decide(aid, False, Actor.OWNER).status == OperationStatus.REFUSED  # the owner still decides
    assert store.get_approval(aid).status == ApprovalStatus.REJECTED
