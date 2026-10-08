"""F14: an approval the owner gave and the run refused is a finished record. The row is APPROVED beside a REFUSED run, the record
is FAILED and waits for nothing, and no sentence calls it a decline."""

from __future__ import annotations

from tests.api.test_time_semantics import _act, _queue, _walk


def test_approving_after_the_mandate_expired_is_a_failed_record_that_waits_for_nothing(client):
    _walk(client)
    acted = _act(client)
    row = _queue(client)[0]
    client.post("/clock/advance", json={"to_day": 91})  # the mandate expired on day 90
    result = client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"})
    assert result.status_code == 200 and result.json()["result"]["status"] == "REFUSED"
    after = _queue(client)[0]
    assert after["status"] == "APPROVED" and after["execution"]["status"] == "REFUSED"
    assert after["decision_id"] == acted["decision_id"] and after["decision_state"] == "FAILED"
    text = after["execution"]["summary_text"]
    assert text == "You approved it, but it could not run: Mandate v1 expired yesterday. No money moved."
    assert "declined" not in text.lower() and after["presentation"]["lands_day"] is None
    d = client.get(f"/decisions/{acted['decision_id']}").json()
    assert d["state"] == "FAILED" and d["state_text"] == "Could not run. No money moved" and d["terminal"] is True
    assert d["waiting_for"] == {"code": "NOTHING", "party": "none", "party_name": None, "day": None, "when": None,
                                "text": "Nothing is waiting: the action is complete."}
    assert d["authorization"]["status"] == "APPROVED" and d["operations"][-1]["status"] == "REFUSED"
    assert d["execution"]["summary_text"] == "One step could not run. No money moved for it."
    assert d["settlement"] == []
    # the quote the owner approved on is still there, and still no money moved
    assert after["quote"]["recorded"] is True and after["quote"]["actual"] == []


def test_a_failed_record_is_closed_for_the_home_and_the_open_list(client):
    _walk(client)
    acted = _act(client)
    row = _queue(client)[0]
    client.post("/clock/advance", json={"to_day": 91})
    client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"})
    open_ids = [d["id"] for d in client.get("/decisions", params={"open": "true"}).json()["decisions"]]
    assert acted["decision_id"] not in open_ids
    assert acted["decision_id"] not in [d["id"] for d in client.get("/home").json()["open_decisions"]]


def test_the_shared_words_never_call_a_refusal_after_an_approval_a_decline():
    from app.api.presentation import event_words, result_words
    from app.domain.fixtures import load_scenario

    state, _ = load_scenario()
    payload = {"kind": "DRAW_FACILITY", "op_id": "op-1", "facility_id": "FAC-LINE", "amount_fen": 10_000_000, "day": 3}
    text = result_words(state, kind="DRAW_FACILITY", status="REFUSED", payload=payload, day=3, today=3, approval_status="APPROVED",
                        message="Refused: Mandate v1 expired on day 90")
    assert text and text.startswith("You approved it, but it could not run") and "declined" not in text.lower()
    declined = result_words(state, kind="DRAW_FACILITY", status="REFUSED", payload=payload, day=3, today=3, approval_status="REJECTED",
                            message="Declined by the owner (APR-000001); nothing executed")
    assert declined and declined.startswith("You declined")
    log_refused = event_words(state, kind="DRAW_FACILITY", status="REFUSED", payload=payload, message="Refused: Mandate v1 expired on day 90",
                              approval_id="APR-000001", day=3, today=3)
    assert "declined" not in (log_refused["event_text"] or "").lower()
