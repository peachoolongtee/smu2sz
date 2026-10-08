"""Wave 2 (map #65, ticket #71): the durable decision record end to end on the golden EX01 books. The state and its words come
from stored data only (the commitment, the approvals, the log, the lots and the three small facts), never from the page."""

from __future__ import annotations

from typing import Any, cast

import pytest

from app.api.runtime import get_runtime
from tests.api.test_time_semantics import _walk

EX01 = "EX01_PACKAGE"
CLEAN = "Deduct 0.6% and we'll settle the open ¥420,000 invoice early."
SCOPE = ("Sends Option A to the buyer (the reply is simulated); records the agreement, with your approval when it changes "
         "terms; runs the funding for any remaining gap within your limits.")


def _offer(client, fixture: str = EX01) -> str:
    return client.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]


def _evaluate(client, oid: str, fixture: str = EX01) -> dict:
    return client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fixture}).json()


def _record(client, decision_id: str, lang: str = "en") -> dict:
    r = client.get(f"/decisions/{decision_id}", params={"lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def test_evaluate_records_the_verdict_day_and_the_record_reads_response_ready(client):
    oid = _offer(client)
    v = _evaluate(client, oid)
    assert v["decision_id"] == f"deal:{oid}" and v["decision_recorded"] is True
    assert v["evaluated_day"] == 0 and v["evaluated_when"] == "today"
    assert all(c["send_scope"] == SCOPE.replace("Option A", c["label"]) for c in v["counters"])
    d = _record(client, v["decision_id"])
    assert d["state"] == "RESPONSE_READY" and d["state_text"] == "Counter recommended"
    assert d["evaluation"]["business_action"] == "counter" and d["evaluation"]["evaluated_day"] == 0
    assert d["evaluation"]["verdict_id"] == v["id"] and d["recorded"]["evaluated"] is True
    assert d["waiting_for"]["code"] == "OWNER_RESPONSE" and d["waiting_for"]["party"] == "owner"
    assert d["execution"]["summary_text"] == "Nothing has been executed yet."
    assert d["agreement"] is None and d["operations"] == []
    client.post("/clock/advance", json={"to_day": 9})
    assert _record(client, v["decision_id"])["evaluation"]["evaluated_when"] == "9 days ago"


def test_an_acceptable_offer_is_acceptable_awaiting_agreement_never_agreed(client):
    oid = client.post("/offers", json={"documents": [{"doc_id": "t1", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0,
                                                       "text": CLEAN}], "counterparty_id": "BUYER-1"}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={}).json()
    assert v["outcome"] == "ACCEPT"
    d = _record(client, v["decision_id"])
    assert d["state"] == "RESPONSE_READY" and d["state_text"] == "Acceptable, awaiting agreement"
    assert d["evaluation"]["business_action_text"] == "Acceptable, awaiting agreement"
    assert d["agreement"] is None and "Agreed" not in d["state_text"]
    assert _record(client, v["decision_id"], "zh")["state_text"] == "可接受，等待达成协议"


def test_a_cooperative_buyer_agrees_and_the_funding_is_listed_with_a_summary(client):
    oid = _offer(client)
    v = _evaluate(client, oid)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    assert n["outcome"] == "DEAL" and n["decision_id"] == v["decision_id"] and n["decision_recorded"] is True
    assert n["execution"]["summary_text"]
    d = _record(client, v["decision_id"])
    assert d["state"] == "AGREED" and d["state_text"] == "Agreed" and d["terminal"] is False
    assert d["agreement"]["status"] == "ACTIVE" and d["agreement"]["status_text"] == "Agreed"
    kinds = [(o["kind"], o["status"]) for o in d["operations"]]
    assert kinds[0] == ("ACCEPT_OFFER", "EXECUTED") and ("DRAW_FACILITY", "EXECUTED") in kinds
    assert d["execution"]["summary_text"] == n["execution"]["summary_text"]
    assert "Agreement with Foshan Home Retail Co. recorded." in d["execution"]["summary_text"]
    assert "Funding of" in d["execution"]["summary_text"]
    assert d["response"]["sent"]["recorded"] is True and d["response"]["sent"]["outcome"] == "DEAL"
    assert d["response"]["sent"]["accepted_label"] == "Option A" and d["response"]["sent"]["simulated"] is True
    assert d["response"]["sent"]["chosen_counter_id"] is None  # an unbound send records no chosen counter
    assert d["waiting_for"]["code"] == "BANK_RECEIPT" and d["waiting_for"]["party_name"] == "Foshan Home Retail Co."
    assert len(d["settlement"]) == 1 and d["settlement"][0]["settled"] is True


def test_a_hard_line_buyer_gives_no_deal_with_the_gap_funded_and_never_nothing_executed(client):
    oid = _offer(client)
    v = _evaluate(client, oid)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "hard_line"}).json()
    assert n["outcome"] == "NO_DEAL"
    d = _record(client, v["decision_id"])
    assert d["state"] == "NO_DEAL" and d["terminal"] is True and d["state_text"] == "No deal: the buyer did not accept"
    assert [o["status"] for o in d["operations"]] == ["EXECUTED", "EXECUTED"]
    text = d["execution"]["summary_text"]
    assert "nothing" not in text.lower() and "Funding of" in text
    assert n["execution"]["summary_text"] == text
    assert d["agreement"] is None and d["response"]["sent"]["outcome"] == "NO_DEAL"


def test_without_a_receipt_the_agreement_is_missed_or_expired_never_agreed(client):
    _walk(client, to=34)
    deals = client.get("/decisions", params={"family": "DEAL"}).json()["decisions"]
    assert len(deals) == 1
    assert deals[0]["state"] == "MISSED" and deals[0]["state_text"] == "Early payment did not arrive"  # the golden walk is MISSED
    d = _record(client, deals[0]["id"])
    assert d["terminal"] is True and d["agreement"]["status_text"] != "Agreed"
    assert d["waiting_for"]["code"] == "BANK_RECEIPT" and d["waiting_for"]["day"] is not None


def test_with_the_half_receipt_no_sentence_says_by_today(client):
    _walk(client, receipt="half", to=34)
    deal = client.get("/decisions", params={"family": "DEAL"}).json()["decisions"][0]
    d = _record(client, deal["id"])
    rows = d["receipts"] + d["promises"]
    assert rows, "the half receipt and the promise it belongs to are part of the record"
    for row in rows:
        assert row["detail_when"] and "by today" not in row["detail_when"]
    assert any(r["status"] == "SHORT_PAYMENT" or r["status"] == "MATCHED" for r in d["receipts"])


def test_the_list_is_newest_first_and_filters_by_family_open_and_limit(client):
    _walk(client, to=34)
    action = client.get("/home").json()["next_action"]
    client.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    all_ = client.get("/decisions").json()
    assert all_["count"] == 2 and all_["day"] == 34
    assert [x["family"] for x in all_["decisions"]] == ["FUNDING", "DEAL"]  # the cure ran on day 34, after the deal's day
    assert [x["family"] for x in client.get("/decisions", params={"family": "FUNDING"}).json()["decisions"]] == ["FUNDING"]
    assert client.get("/decisions", params={"limit": 1}).json()["decisions"][0]["family"] == "FUNDING"
    open_ = client.get("/decisions", params={"open": "true"}).json()["decisions"]
    assert all(x["terminal"] is False for x in open_) and [x["family"] for x in open_] == ["FUNDING"]
    zh = client.get("/decisions", params={"lang": "zh"}).json()["decisions"][0]
    assert zh["state_text"] == "等待您批准" and "Waiting" not in zh["waiting_for"]["text"]
    assert client.get("/decisions", params={"family": "NOPE"}).status_code == 422


def test_an_unknown_decision_is_404_and_the_record_is_owner_only(client):
    assert client.get("/decisions/deal:NOPE").status_code == 404
    assert client.get("/decisions/alert:NOPE:v1").status_code == 404
    from fastapi.testclient import TestClient

    from app.main import app

    anon = TestClient(app)
    assert anon.get("/decisions").status_code == 401
    assert anon.get("/decisions/deal:X").status_code == 401
    assert anon.get("/offers/OFF-X").status_code == 401


def test_an_offer_nothing_evaluated_yet_is_received_and_opens_by_its_id(client):
    oid = _offer(client)
    d = _record(client, f"deal:{oid}")
    assert d["state"] == "RECEIVED" and d["waiting_for"]["code"] == "OWNER_RESPONSE" and d["evaluation"] is None
    assert d["source"]["offer_id"] == oid and d["source"]["counterparty_name"] == "Foshan Home Retail Co."
    assert d["interpretation"]["terms"], "the offer's terms are written as sentences by the server"


def test_get_offer_returns_the_stored_offer_its_latest_verdict_and_decision_id(client):
    oid = _offer(client)
    before = client.get(f"/offers/{oid}").json()
    assert before["offer"]["offer_id"] == oid and before["latest_verdict_id"] is None and before["decision_id"] == f"deal:{oid}"
    assert before["documents"], "the offer's documents come with it"
    v = _evaluate(client, oid)
    assert client.get(f"/offers/{oid}").json()["latest_verdict_id"] == v["id"]
    get_runtime().latest_verdict.clear()  # a restart empties the session cache; the store still knows the verdict
    assert client.get(f"/offers/{oid}").json()["latest_verdict_id"] == v["id"]
    assert client.get("/offers/OFF-NOPE").status_code == 404


def test_the_ledger_links_each_entry_to_its_decision(client):
    oid = _offer(client)
    _evaluate(client, oid)
    client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    client.post("/clock/advance", json={"to_day": 2})
    ops = client.get("/ledger").json()["operations"]
    by_kind = {o["kind"]: o.get("decision_id") for o in ops}
    assert by_kind["ACCEPT_OFFER"] == f"deal:{oid}" and by_kind["DRAW_FACILITY"] == f"deal:{oid}"
    assert by_kind["ADVANCE_CLOCK"] is None


def test_a_demo_reset_clears_the_facts_with_the_ledger(client):
    oid = _offer(client)
    _evaluate(client, oid)
    store = get_runtime().store
    assert cast(Any, store).decision_facts()
    client.post("/demo/reset", json={})
    assert cast(Any, store).decision_facts() == [] and client.get("/decisions").json()["count"] == 0


def test_a_fact_that_cannot_be_stored_never_fails_the_route_and_the_record_says_so(client, monkeypatch):
    store = get_runtime().store

    def boom(record):
        raise RuntimeError("disk full")

    monkeypatch.setattr(store, "add_decision_fact", boom)
    oid = _offer(client)
    v = _evaluate(client, oid)
    assert v["decision_recorded"] is False and v["evaluated_when"]
    d = _record(client, v["decision_id"])
    assert d["state"] == "RESPONSE_READY" and d["evaluation"]["evaluated_when"] == "date not recorded"
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    assert n.status_code == 200 and n.json()["decision_recorded"] is False and n.json()["outcome"] == "DEAL"
    d = _record(client, v["decision_id"])
    assert d["state"] == "AGREED" and d["execution"]["summary_text"]
    assert d["response"]["sent"] == {"recorded": False, "text": "The counter sent was not recorded."}
    assert client.get("/ledger").json()["chain_valid"] is True


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_every_record_sentence_is_written_per_language(client, lang):
    oid = _offer(client)
    v = _evaluate(client, oid)
    client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    d = _record(client, v["decision_id"], lang)
    for text in (d["state_text"], d["waiting_for"]["text"], d["execution"]["summary_text"], d["remaining_task"]["text"]):
        assert text
        assert (any("一" <= ch <= "鿿" for ch in text)) == (lang == "zh"), text
