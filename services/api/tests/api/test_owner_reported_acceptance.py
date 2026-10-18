"""Authority audit item 4: the buyer's yes recorded on an offer sent outside FLOW is the OWNER's report.

It is bound to the exact offer sent (verdict, message hash, terms hash, expiry, books version), the pasted evidence is kept unverified
and never called authenticated, and the record states the funding requirement either way: the gap and the plan to run, or that none
is needed.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, get_runtime
from tests.api.test_buyer_message import EX02, _accepted, _decision, _evaluate, _message, _sent


@pytest.fixture
def api(client: TestClient) -> TestClient:
    return client


@pytest.fixture
def rt(client: TestClient) -> Runtime:
    return get_runtime()


def _no_commitment(rt, oid) -> bool:
    return not [c for c in rt.store.commitments() if c.offer_id == oid]


def test_a_yes_on_stale_books_is_refused_and_records_nothing(api, rt) -> None:
    oid, v, m = _sent(api)
    stale = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                     json={"verdict_id": v["id"], "state_version": rt.store.get_state().state_version - 1, "message_hash": m["message_hash"]})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "BOOKS_CHANGED"
    assert _no_commitment(rt, oid)


def test_a_yes_bound_to_another_verdict_or_message_is_not_the_offer_sent(api, rt) -> None:
    oid, v, m = _sent(api)
    version = rt.store.get_state().state_version
    for body in ({"verdict_id": "VER-OTHER", "state_version": version, "message_hash": m["message_hash"]},
                 {"verdict_id": v["id"], "state_version": version, "message_hash": "f" * 64}):
        r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted", json=body)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_OFFERED", body
    assert _no_commitment(rt, oid)


def test_a_yes_after_the_offer_expired_is_refused(api, rt) -> None:
    oid, v, m = _sent(api)
    api.post("/clock/advance", json={"to_day": m["valid_until_day"] + 1})
    late = _accepted(api, oid, v, m, rt)
    assert late.status_code == 409 and late.json()["detail"]["code"] == "OFFER_EXPIRED"
    assert _no_commitment(rt, oid)


def test_a_yes_on_an_offer_never_marked_sent_is_refused(api, rt) -> None:
    oid, v = _evaluate(api, EX02)
    m = _message(api, oid, v["counters"][0]["id"])
    r = _accepted(api, oid, v, m, rt)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_OFFERED" and _no_commitment(rt, oid)


def test_a_second_yes_is_refused_and_books_one_agreement(api, rt) -> None:
    oid, v, m = _sent(api)
    assert _accepted(api, oid, v, m, rt).status_code == 200
    assert _accepted(api, oid, v, m, rt).status_code == 409
    assert len([c for c in rt.store.commitments() if c.offer_id == oid]) == 1


def test_the_pasted_evidence_is_kept_unverified_and_never_called_authenticated(api, rt) -> None:
    oid, v, m = _sent(api)
    r = api.post(f"/offers/{oid}/counters/{m['counter_id']}/buyer-accepted",
                 json={"verdict_id": v["id"], "state_version": rt.store.get_state().state_version, "message_hash": m["message_hash"],
                       "evidence_text": "Agreed. Signed, the CFO (verified sender)"})
    assert r.status_code == 200
    out = _decision(api, oid)["outbound"]
    assert out["provenance_text"] == "Source: recorded by you, with the buyer's message"
    assert out["text"].startswith("You confirmed that")  # the owner's report, not the buyer's message
    blob = json.dumps(_decision(api, oid)).lower()
    assert "authenticated" not in blob.replace("not authenticated", "")
    # the pasted text is only a stored document: nothing in the booked fact names it as proof, and it is not a channel message
    doc = next(d for d in rt.documents.values() if d.doc_id.startswith("accept-"))
    assert doc.text.startswith("Agreed.") and doc.channel == "email"


def test_the_record_states_the_funding_still_to_run_when_a_gap_is_ahead(api, rt) -> None:
    oid, v, m = _sent(api)
    assert _accepted(api, oid, v, m, rt).status_code == 200
    consequences = _decision(api, oid)["outbound"]["consequences"]
    assert any(c.startswith("The agreement ran no funding: cash still falls") and "it runs only when you run it" in c for c in consequences)


def test_a_yes_on_books_that_moved_after_the_send_is_refused_by_the_reverification(api, rt) -> None:
    oid, v, m = _sent(api)
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"cash_fen": state.cash_fen + 10_000_000, "state_version": state.state_version + 1}))
    r = _accepted(api, oid, v, m, rt)  # a fresh state_version in the body: the executor still re-verifies the terms on today's books
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_RECORDED"
    assert not [c for c in rt.store.commitments() if c.offer_id == oid and c.status.value != "PROPOSED"]  # a reusable proposal at most (SEC-03)


def test_the_record_says_none_is_needed_when_no_gap_is_ahead(api, rt, monkeypatch) -> None:
    # The EX02 books always leave a reserve gap and the executor re-verifies on today's books (a changed state is refused), so the
    # "no breach ahead" reading is set by making the record see no reserve alert.
    monkeypatch.setattr("app.api.decisions.RESERVE_ALERT", "NO_SUCH_ALERT")
    oid, v, m = _sent(api)
    got = _accepted(api, oid, v, m, rt)
    assert got.status_code == 200, got.text
    consequences = _decision(api, oid)["outbound"]["consequences"]
    assert consequences[-1] == ("The agreement ran no funding, and none is needed: no cash shortfall below your minimum is ahead on "
                                "today's books.")
    assert not any("cash still falls" in c for c in consequences)
