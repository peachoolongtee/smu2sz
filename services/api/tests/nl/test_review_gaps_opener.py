"""The chat opener for review gaps G2 and G3: an expiring or expired mandate is named, and a cure that only keeps cash
at or above zero says that it does not restore the reserve."""

from __future__ import annotations

import pytest

from tests.alerts.test_review_gaps import _short_facilities_state


@pytest.mark.parametrize("lang,needle", [("en", "mandate"), ("zh", "授权")])
def test_the_opener_mentions_an_expiring_mandate(rt, client, lang, needle):
    store = rt.store
    store.put_mandate(store.get_mandate().model_copy(update={"expires_day": 10}))
    r = client.post("/nl/opener", json={"session_id": f"mand-{lang}", "lang": lang},
                    headers={"X-Owner-Token": "demo-owner-token"})
    assert r.status_code == 200 and r.json()["has_news"] is True
    reply = r.json()["reply"]
    assert needle in reply and ("10" in reply)
    assert ("offline" in reply) if lang == "en" else ("线下" in reply)


def test_the_opener_says_an_expired_mandate_stops_the_agent(rt, client):
    h = {"X-Owner-Token": "demo-owner-token"}
    client.post("/clock/advance", json={"to_day": 4}, headers=h)
    rt.store.put_mandate(rt.store.get_mandate().model_copy(update={"expires_day": 3}))
    reply = client.post("/nl/opener", json={"session_id": "mand-exp"}, headers=h).json()["reply"]
    assert "mandate expired on day 3" in reply and "no longer act" in reply


def test_the_opener_proposes_the_zero_floor_cure_and_says_what_it_does_not_do(rt, client):
    rt.store.put_state(_short_facilities_state())
    reply = client.post("/nl/opener", json={"session_id": "g3"}, headers={"X-Owner-Token": "demo-owner-token"}).json()["reply"]
    assert "goes below zero" in reply and "does not restore your reserve" in reply and "Go ahead?" in reply
    assert "nothing I can do" not in reply
