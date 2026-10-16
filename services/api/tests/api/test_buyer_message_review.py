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
