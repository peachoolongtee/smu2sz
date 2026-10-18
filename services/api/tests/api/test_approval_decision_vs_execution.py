"""SEC-27, the visible half (authority audit, 18 Oct): the owner's decision on an approval and what its re-run did are two facts.

The executor still leaves the approval row APPROVED when the re-run is refused (engine code, unchanged). What the owner is told is
not: the decision response, the approvals queue and the chat reply all say "approved, did not run" with the reason, and a repeated
decision changes nothing.
"""

from __future__ import annotations

import json

from app.api.runtime import get_runtime
from tests.api.test_time_semantics import _act, _queue, _walk

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def _expired(client) -> str:
    _walk(client)
    _act(client)
    row = _queue(client)[0]
    client.post("/clock/advance", json={"to_day": 91})  # the mandate expired on day 90
    return row["id"]


def test_the_decision_response_separates_the_approval_from_a_refused_run(client):
    aid = _expired(client)
    r = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    assert r.status_code == 200
    body = r.json()
    assert body["result"]["status"] == "REFUSED"
    a = body["approval"]
    assert (a["id"], a["decision"], a["execution_status"], a["ran"]) == (aid, "APPROVED", "REFUSED", False)
    assert a["text"].startswith("You approved it, but it could not run:") and "No money moved" in a["text"]


def test_the_queue_row_says_approved_did_not_run(client):
    aid = _expired(client)
    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    row = next(x for x in _queue(client) if x["id"] == aid)
    assert row["status"] == "APPROVED" and row["presentation"]["execution_status"] == "REFUSED"
    assert row["result_state_text"] == "Approved, did not run. No money moved." and row["result_tone"] == "bad"


def test_a_repeated_decision_is_idempotent_and_changes_nothing(client):
    aid = _expired(client)
    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"})
    rt = get_runtime()
    log = [(o.seq, o.kind) for o in rt.store.operations()]
    state = rt.store.get_state().state_version
    for decision in ("APPROVE", "REJECT"):
        again = client.post(f"/approvals/{aid}", json={"decision": decision})
        assert again.status_code == 409 and again.json()["detail"]["code"] == "APPROVAL_ALREADY_DECIDED"
    assert [(o.seq, o.kind) for o in rt.store.operations()] == log and rt.store.get_state().state_version == state
    assert next(x for x in _queue(client) if x["id"] == aid)["status"] == "APPROVED"


def test_a_decline_reads_declined_and_ran_nothing(client):
    _walk(client)
    _act(client)
    aid = _queue(client)[0]["id"]
    r = client.post(f"/approvals/{aid}", json={"decision": "REJECT"}).json()
    assert r["approval"] == {"id": aid, "decision": "REJECTED", "execution_status": "DECLINED", "ran": False,
                             "text": "You declined it. Nothing ran."}


def test_an_approved_run_that_succeeds_says_it_ran(client):
    _walk(client)
    _act(client)
    aid = _queue(client)[0]["id"]
    r = client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}).json()
    assert r["result"]["status"] == "EXECUTED"
    assert (r["approval"]["decision"], r["approval"]["execution_status"], r["approval"]["ran"]) == ("APPROVED", "EXECUTED", True)


def test_a_stale_receipt_is_rechecked_against_the_books_at_decision_time(client):
    """The approval re-runs every gate on today's books: a receipt the bank feed booked after it was queued is refused, not booked twice."""
    _walk(client)
    version = client.get("/mandate").json()["mandate"]["version"]
    promise = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
    body = {"kind": "RECEIVE_PAYMENT", "requested_by": "AGENT", "op_id": "AG-R", "idempotency_key": "AG-R", "mandate_version": version,
            "receivable_id": promise["receivable_id"], "amount_fen": 10_000}
    queued = client.post("/operations", json=body, headers={"X-Agent-Key": "demo-agent-key"}).json()["result"]
    assert queued["status"] == "PENDING_APPROVAL"
    feed = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "BK-R", "idempotency_key": "BK-R", "mandate_version": version, "requested_by": "SYSTEM",
        "receivable_id": promise["receivable_id"], "amount_fen": 10_000, "bank_reference": "BANK-9"}).json()["result"]
    assert feed["status"] == "EXECUTED"
    cash = client.get("/state").json()["state"]["cash_fen"] if client.get("/state").status_code == 200 else None
    r = client.post(f"/approvals/{queued['approval_id']}", json={"decision": "APPROVE"}).json()
    assert r["result"]["status"] == "REFUSED" and r["approval"]["execution_status"] == "REFUSED" and r["approval"]["ran"] is False
    if cash is not None:
        assert client.get("/state").json()["state"]["cash_fen"] == cash
    assert json.dumps(r["approval"]).count("approved it, but it could not run") == 1
