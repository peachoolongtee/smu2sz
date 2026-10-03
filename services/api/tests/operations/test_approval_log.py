"""The log row of an owner decision carries its approval id, and the approval its decision day (G1, G3)."""

from __future__ import annotations

import json
from typing import Any

from app.domain.models import Actor, DrawFacility, OperationStatus
from app.mandate import load_demo_owner_key, load_signed_mandate, revoke
from tests.operations.builders import Clock, op
from tests.operations.test_approvals_and_circuit import queue_terms_change


def _results(store: Any) -> list[dict]:
    return [json.loads(r.result_json) for r in store.operations()]


def test_the_executed_re_run_is_logged_under_the_approval_it_ran_under(ex: Any, store: Any, clock: Clock) -> None:
    _c, aid = queue_terms_change(ex, store, clock)
    queued = _results(store)[-1]
    assert queued["status"] == "PENDING_APPROVAL" and queued["approval_id"] == aid
    clock.day = 3
    done = ex.decide(aid, True, Actor.OWNER)
    assert done.status == OperationStatus.EXECUTED
    stored = _results(store)[-1]  # the log entry itself, not the response
    assert stored["status"] == "EXECUTED" and stored["effective_day"] == 3
    assert stored["approval_id"] == aid
    assert store.get_approval(aid).decided_day == 3
    assert store.verify_chain()


def test_a_decline_is_logged_under_its_approval_and_records_the_day(ex: Any, store: Any, clock: Clock) -> None:
    _c, aid = queue_terms_change(ex, store, clock)
    clock.day = 2
    ex.decide(aid, False, Actor.OWNER)
    stored = _results(store)[-1]
    assert stored["status"] == "REFUSED" and stored["approval_id"] == aid
    rec = store.get_approval(aid)
    assert (rec.status, rec.decided_day) == ("REJECTED", 2)


def test_an_approved_re_run_that_is_refused_is_still_logged_under_its_approval(
    ex: Any, store: Any, clock: Clock
) -> None:
    _c, aid = queue_terms_change(ex, store, clock)
    store.put_mandate(revoke(load_signed_mandate(), load_demo_owner_key()["private_key_hex"]))
    refused = ex.decide(aid, True, Actor.OWNER)
    assert refused.status == OperationStatus.REFUSED
    stored = _results(store)[-1]
    assert stored["status"] == "REFUSED" and stored["approval_id"] == aid
    assert store.get_approval(aid).decided_day == clock.day


def test_rows_written_outside_a_decision_carry_no_approval_id(ex: Any, store: Any, clock: Clock) -> None:
    ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=100_000))
    assert _results(store)[-1]["approval_id"] is None
    _c, aid = queue_terms_change(ex, store, clock)
    ex.decide(aid, True, Actor.OWNER)
    ex.execute(op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=200_000))
    assert _results(store)[-1]["approval_id"] is None  # nothing leaks past the decision
