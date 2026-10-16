"""Review findings on the buyer-message feature (F2 to F5): the state and the API agree, a late reply is a request of its own, a stronger
sender upgrades how a request arrived, and "I've sent it" is bound to the words the owner copied."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, get_runtime
from tests.api.conftest import client  # noqa: F401
from tests.api.test_buyer_message import _accepted, _decision, _sent


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
    assert body["offer_closed"] is True and "had closed" in body["message_when"]
    stored = rt.store.get_offer(body["reply_offer_id"])
    assert stored is not None and stored.counterparty_id == "BUYER-1" and stored.obligations  # compiled on its own, from the deal's buyer
    assert _decision(api, body["reply_offer_id"])["state"] == "RECEIVED"
    old = _decision(api, oid)
    assert old["state"] == "NO_DEAL" and old["outbound"]["answer"] == "no_answer"  # not REPLIED
    assert not any(f.fact == "REPLIED" for f in rt.store.decision_facts(f"deal:{oid}"))
