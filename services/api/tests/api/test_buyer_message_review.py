"""Review findings on the buyer-message feature (F2 to F5): the state and the API agree, a late reply is a request of its own, a stronger
sender upgrades how a request arrived, and "I've sent it" is bound to the words the owner copied."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, get_runtime
from app.domain.fixtures import offer_documents
from tests.api.conftest import client  # noqa: F401
from tests.api.test_buyer_message import EX02, _accepted, _decision, _evaluate, _message, _sent


@pytest.fixture
def api(client: TestClient) -> TestClient:  # noqa: F811
    return client


@pytest.fixture
def rt(client: TestClient) -> Runtime:  # noqa: F811
    return get_runtime()


def _set_cash(rt: Runtime, cash_fen: int) -> int:
    """Move the books under the owner (the cash a later check reads); returns the cash that was there."""
    st = rt.store.get_state()
    rt.store.put_state(st.model_copy(update={"cash_fen": cash_fen, "state_version": st.state_version + 1}), expected_version=st.state_version)
    return st.cash_fen


# ================================================================ F2: a refused yes does not end the deal while the offer is open


def test_a_refused_yes_leaves_the_deal_waiting_with_the_refusal_shown_and_a_retry_works(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    cash = _set_cash(rt, 1)
    refused = _accepted(api, oid, v, m, rt)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "NOT_RECORDED"
    d = _decision(api, oid)
    assert d["state"] == "AWAITING_BUYER" and d["terminal"] is False
    ob = d["outbound"]
    assert ob["answer"] is None and ob["actions"] is not None  # the answer buttons are still there
    assert "could not record their yes" in ob["refusal_text"]
    zh = _decision(api, oid, "zh")["outbound"]["refusal_text"]
    assert "未能记录" in zh and zh != ob["refusal_text"]
    _set_cash(rt, cash)  # the books recover
    again = _accepted(api, oid, v, m, rt)
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "agreed"
    after = _decision(api, oid)
    assert after["state"] == "AGREED" and "refusal_text" not in after["outbound"]
    assert after["outbound"]["answer"] == "accepted"


def test_a_refused_yes_after_the_window_is_no_deal_and_a_later_yes_is_expired(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    _set_cash(rt, 1)
    assert _accepted(api, oid, v, m, rt).status_code == 409
    assert api.post("/clock/advance", json={"to_day": m["valid_until_day"] + 1}).status_code == 200
    d = _decision(api, oid)
    assert d["state"] == "NO_DEAL" and d["outbound"]["answer"] == "no_answer"
    late = _accepted(api, oid, v, m, rt)
    assert late.status_code == 409 and late.json()["detail"]["code"] == "OFFER_EXPIRED"


# ================================================================ F3: a reply after the offer closed is a request of its own and answers nothing


def test_a_reply_after_the_window_is_a_new_request_and_does_not_mark_the_expired_offer_replied(api: TestClient, rt: Runtime) -> None:
    oid, v, m = _sent(api)
    assert api.post("/clock/advance", json={"to_day": m["valid_until_day"] + 1}).status_code == 200
    assert _decision(api, oid)["state"] == "NO_DEAL"
    r = api.post(f"/offers/{oid}/buyer-reply", json={"verdict_id": v["id"], "counter_id": m["counter_id"],
                                                     "text": "Could you do 50-day terms instead?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("offer_closed") is True and "had closed" in body["message_when"]
    stored = rt.store.get_offer(body["reply_offer_id"])
    assert stored is not None and stored.counterparty_id == "BUYER-1" and stored.obligations  # compiled on its own, from the deal's buyer
    assert _decision(api, body["reply_offer_id"])["state"] == "RECEIVED"
    old = _decision(api, oid)
    assert old["state"] == "NO_DEAL" and old["outbound"]["answer"] == "no_answer"  # not REPLIED
    assert not any(f.fact == "REPLIED" for f in rt.store.decision_facts(f"deal:{oid}"))


# ================================================================ F4: a stronger sender upgrades how a request arrived, never the reverse


def _file(who: TestClient, docs: list[dict[str, Any]]) -> str:
    r = who.post("/offers", json={"counterparty_id": "BUYER-1", "documents": docs})
    assert r.status_code == 200, r.text
    return r.json()["offer"]["offer_id"]


def _arrived(api: TestClient, oid: str) -> tuple[str, str | None]:
    v = api.post(f"/offers/{oid}/evaluate").json()
    m = api.get(f"/offers/{oid}/counters/{v['counters'][0]['id']}/message").json()
    return m["provenance"]["via"], (m["blocked"] or {}).get("code")


def test_the_owner_filing_after_an_anonymous_one_is_the_owners_own_request(api: TestClient, rt: Runtime) -> None:
    docs = [d.model_dump(mode="json") for d in offer_documents(EX02)]
    oid = _file(TestClient(api.app), docs)  # nobody's token: anonymous
    assert _file(api, docs) == oid  # the owner files the same documents
    assert _arrived(api, oid) == ("owner", None)
    received = [f for f in rt.store.decision_facts(f"deal:{oid}") if f.fact == "RECEIVED"]
    assert len(received) == 2  # the anonymous filing stands in the record; the owner's is a fact of its own


def test_an_anonymous_filing_after_the_owners_never_downgrades_it(api: TestClient, rt: Runtime) -> None:
    docs = [d.model_dump(mode="json") for d in offer_documents(EX02)]
    oid = _file(api, docs)
    assert _file(TestClient(api.app), docs) == oid
    assert _arrived(api, oid) == ("owner", None)
    assert len([f for f in rt.store.decision_facts(f"deal:{oid}") if f.fact == "RECEIVED"]) == 1


# ================================================================ F5: "I've sent it" is bound to the words the owner copied


def test_marking_sent_with_the_other_languages_copy_is_refused_in_the_owners_words(api: TestClient, rt: Runtime) -> None:
    oid, v = _evaluate(api, EX02)
    cid = v["counters"][0]["id"]
    english, chinese = _message(api, oid, cid, "en"), _message(api, oid, cid, "zh")
    assert english["message_hash"] != chinese["message_hash"]

    def mark(shown: dict[str, Any], lang: str, lang_ui: str = "en"):
        return api.post(f"/offers/{oid}/counters/{cid}/offered", params={"lang": lang_ui},
                        json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": shown["message_hash"], "lang": lang})

    wrong = mark(english, "zh")  # copied English, Chinese on screen
    assert wrong.status_code == 409
    d = wrong.json()["detail"]
    assert d["code"] == "MESSAGE_LANGUAGE" and d["message_hash"] == chinese["message_hash"]
    assert "English" in d["message_when"] and "Chinese" in d["message_when"]
    assert "英文" in mark(english, "zh", "zh").json()["detail"]["message_when"]  # the same refusal in the page's other language
    assert "OFFERED" not in {f.fact for f in rt.store.decision_facts(f"deal:{oid}")}  # nothing was recorded
    assert mark(chinese, "en").json()["detail"]["code"] == "MESSAGE_LANGUAGE"
    nonsense = api.post(f"/offers/{oid}/counters/{cid}/offered",
                        json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": "0" * 64, "lang": "zh"})
    assert nonsense.json()["detail"]["code"] == "MESSAGE_CHANGED"  # a hash that is nobody's message stays the old refusal
    ok = mark(chinese, "zh")
    assert ok.status_code == 200 and ok.json()["offered"]["lang"] == "zh"
    assert ok.json()["offered"]["message_hash"] == chinese["message_hash"]


def test_a_buyer_yes_whose_fact_cannot_be_recorded_does_not_report_success(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import outbound

    oid, v, m = _sent(api)
    real = outbound.record_fact
    monkeypatch.setattr(outbound, "record_fact", lambda *a, **k: False if str(a[2]).startswith("accept-") else real(*a, **k))
    r = _accepted(api, oid, v, m, rt)
    assert r.status_code == 500 and r.json()["detail"]["code"] == "NOT_RECORDED"
    assert "could not record that the buyer accepted" in r.json()["detail"]["message_when"]
