"""F02 with the record: an agreement waiting for approval carries its terms and its decision; missing, expired and revoked
agreements fail closed with a reason; an approved one keeps the terms it was approved on."""

from __future__ import annotations

from app.api.runtime import get_runtime
from tests.api.test_time_semantics import _queue, _queue_counter


def test_a_queued_accept_offer_for_option_b_has_terms_a_decision_and_no_funding_quote(client):
    queued = _queue_counter(client, 1)
    row = queued["row"]
    p = row["presentation"]
    assert p["terms_available"] is True and len(p["terms"]) == 2 and all(s.endswith(")") for s in p["terms"])
    assert p["what_you_agree_to"].endswith(".")
    offer_id = queued["commitment"].offer_id
    assert row["decision_id"] == f"deal:{offer_id}" and row["decision_state"] == "AUTHORIZATION_REQUIRED"
    assert row["quote"] is None, "an agreement has terms, not a funding quote"
    assert row["execution"] == {"status": "PENDING", "summary_text": "Waiting for your approval. Nothing has run."}
    d = client.get(f"/decisions/{row['decision_id']}").json()
    assert d["state"] == "AUTHORIZATION_REQUIRED" and d["waiting_for"]["code"] == "OWNER_APPROVAL"
    assert d["waiting_for"]["day"] == queued["commitment"].expires_day  # the offer expires on the commitment's day
    assert d["authorization"]["approval_id"] == row["id"] and d["authorization"]["status"] == "PENDING"
    assert d["execution"]["summary_text"] == "The agreement is waiting for your approval and is not in force."


def test_the_decided_agreement_is_agreed_and_keeps_its_terms(client):
    queued = _queue_counter(client, 1)
    row = queued["row"]
    assert client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    decided = next(a for a in _queue(client) if a["id"] == row["id"])
    assert decided["decision_state"] == "AGREED" and decided["presentation"]["terms_available"] is True
    assert decided["execution"]["status"] == "EXECUTED"
    d = client.get(f"/decisions/{row['decision_id']}").json()
    assert d["state"] == "AGREED" and d["agreement"]["status_text"] == "Agreed" and d["authorization"]["status"] == "APPROVED"


def test_a_missing_expired_or_revoked_agreement_fails_closed_and_the_record_says_why(client):
    queued = _queue_counter(client, 1)
    rt = get_runtime()
    commitment = queued["commitment"]
    for status, state, reason in (("EXPIRED", "EXPIRED", "has expired."), ("REVOKED", "REVOKED", "was revoked.")):
        rt.store.put_commitment(commitment.model_copy(update={"status": status}))
        row = next(a for a in _queue(client) if a["kind"] == "RECORD_COMMITMENT")
        assert row["presentation"]["terms_available"] is False
        assert row["presentation"]["terms_unavailable_reason"] == f"The agreement this approval refers to {reason}"
        assert row["decision_state"] == state
    # the commitment cannot be found at all
    rt.store.put_commitment(commitment.model_copy(update={"id": "CMT-gone"}))
    row = next(a for a in _queue(client) if a["kind"] == "RECORD_COMMITMENT")
    assert row["presentation"]["terms_available"] is False or row["presentation"]["terms"]


def test_an_expired_agreement_that_is_approved_anyway_is_refused_and_reads_expired(client):
    queued = _queue_counter(client, 1)
    row = queued["row"]
    client.post("/clock/advance", json={"to_day": 20})  # past the commitment's expiry (day 14)
    r = client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"})
    assert r.status_code == 200 and r.json()["result"]["status"] == "REFUSED"
    after = next(a for a in _queue(client) if a["id"] == row["id"])
    assert after["status"] == "APPROVED" and after["execution"]["status"] == "REFUSED"
    assert "declined" not in (after["presentation"]["result_message"] or "").lower()
    assert after["decision_state"] == "EXPIRED"  # the table: the agreement lapsed before it was agreed (row 6 before row 9)
    d = client.get(f"/decisions/{row['decision_id']}").json()
    assert d["state"] == "EXPIRED" and d["terminal"] is True and d["waiting_for"]["code"] == "NOTHING"
