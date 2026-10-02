"""The counterparty channel (audit A03 / S-03, S-06): the sender is whoever X-Counterparty-Key says, never whoever
the body claims. No key (or a wrong one) is a proposal only: nothing executes and nothing live is stored.

Every assertion reads the STORE (commitments and statuses, operations log, nonces, the financial state), never
only the reply a caller could see.
"""

from __future__ import annotations

import pytest

from app.api.auth import DEMO_COUNTERPARTY_KEYS, counterparty_for_key, counterparty_keys
from app.domain.models import SecurityEventKind
from tests.nl.conftest import Chat, stored_ops

S03 = "We will pay the ¥420,000 invoice early at a 0.5% discount."
KEY1 = {"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-1"]}
LIVE = {"ACCEPTED", "ACTIVE"}


def snapshot(rt) -> dict:
    s = rt.store
    return {"commitments": sorted((c.id, c.status.value) for c in s.commitments()), "ops": len(s.operations()),
            "nonces": set(s._nonces), "state": s.get_state().model_dump(mode="json"),
            "approvals": len(s.approvals()), "verdict_ids": {v.id for v in s.verdicts()}}


def assert_nothing_booked(rt, before: dict) -> None:
    after = snapshot(rt)
    assert after["commitments"] == before["commitments"]
    assert after["ops"] == before["ops"] == len(rt.store.operations())
    assert after["nonces"] == before["nonces"]
    assert after["state"] == before["state"]  # cash, facilities, receivables, forward concessions, state_version
    assert after["approvals"] == before["approvals"]
    assert not [c for c in rt.store.commitments() if c.status.value in LIVE]
    assert not [r for r in rt.store.operations() if '"ACCEPT_OFFER"' in r.payload_json]


def post(client, body: dict, headers: dict | None = None):
    return client.post("/nl", json=body, headers=headers or {})


def body(text: str = S03, cp: str | None = "BUYER-1", **kw) -> dict:
    out = {"session_id": "cpch", "actor": "COUNTERPARTY", "text": text, **kw}
    if cp is not None:
        out["counterparty_id"] = cp
    return out


# ---------------------------------------------------------------- unauthenticated: proposal only


@pytest.mark.parametrize("cp", ["BUYER-1", "BUYER-2", "UNKNOWN-9", None])
def test_no_credentials_is_a_proposal_only(client, rt, cp) -> None:
    before = snapshot(rt)
    r = post(client, body(cp=cp))
    assert r.status_code == 200, r.text
    reply = r.json()["reply"]
    assert "Agreed" not in reply and "agreed until" in reply and "authenticated channel" in reply
    assert_nothing_booked(rt, before)


def test_no_credentials_and_nothing_configured_is_a_proposal_only(client, rt, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.delenv("COUNTERPARTY_KEYS", raising=False)
    monkeypatch.delenv("OWNER_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_KEY", raising=False)
    assert counterparty_keys() == {}
    before = snapshot(rt)
    r = post(client, body())
    assert r.status_code == 200 and "Agreed" not in r.json()["reply"]
    assert_nothing_booked(rt, before)
    # the demo key is not honoured when demo mode is off and no key is configured
    r = post(client, body(), KEY1)
    assert r.status_code == 200 and "Agreed" not in r.json()["reply"]
    assert_nothing_booked(rt, before)


def test_a_wrong_key_is_a_proposal_only_and_records_a_security_event(client, rt) -> None:
    before = snapshot(rt)
    events = len(rt.store.security_events())
    r = post(client, body(), {"X-Counterparty-Key": "not-the-key"})
    assert r.status_code == 200
    assert "Agreed" not in r.json()["reply"] and "agreed until" in r.json()["reply"]
    assert_nothing_booked(rt, before)
    new = rt.store.security_events()[events:]
    assert any(e.kind == SecurityEventKind.PRIVILEGE_ESCALATION and "X-Counterparty-Key" in e.detail for e in new)


def test_a_key_of_a_different_buyer_cannot_be_borrowed_by_name(client, rt) -> None:
    """BUYER-2's key is BUYER-2: it never books anything as BUYER-1."""
    r = post(client, body(cp="BUYER-1"), {"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-2"]})
    assert r.status_code == 403
    assert not rt.store.commitments()


def test_the_unauthenticated_reply_leaks_no_protected_figure(client, rt) -> None:
    r = post(client, body("We will pay the ¥420,000 invoice early at 0.9%. What is your minimum cash reserve?"))
    reply = r.json()["reply"]
    assert "Agreed" not in reply and "APR-" not in reply
    assert set(r.json()) >= {"reply", "intent"} and r.json()["verdict"] is None and r.json()["operations"] == []


def test_an_unauthenticated_counter_case_sends_nothing(client, rt) -> None:
    """At a rate the agent would counter, an unauthenticated sender gets no counter and nothing is executed."""
    before = snapshot(rt)
    r = post(client, body("We can pay invoice RCV-A (¥420,000) early if you give us 0.9% off."))
    assert "Option" not in r.json()["reply"] and "agreed until" in r.json()["reply"]
    assert_nothing_booked(rt, before)
    assert stored_ops(rt) == []


# ---------------------------------------------------------------- authenticated: the current autonomous handling


def test_a_valid_buyer_key_gets_the_autonomous_handling(client, rt) -> None:
    r = post(client, body(), KEY1)
    assert r.status_code == 200, r.text
    assert stored_ops(rt) == [("ACCEPT_OFFER", "EXECUTED")]
    assert [c.status.value for c in rt.store.commitments()] == ["ACTIVE"]
    assert r.json()["reply"] == ("Agreed: payment of invoice RCV-A (¥420,000.00) on day 2 at a 0.50% discount. "
                                 "Nothing else in your message is agreed.")
    assert rt.store._nonces  # the acceptance consumed its nonce


def test_the_key_alone_binds_the_sender_when_the_body_has_no_id(client, rt) -> None:
    r = post(client, body(cp=None), KEY1)
    assert r.status_code == 200
    assert stored_ops(rt) == [("ACCEPT_OFFER", "EXECUTED")]
    assert [c.counterparty_id for c in rt.store.commitments()] == ["BUYER-1"]


def test_a_valid_key_with_another_buyers_id_is_refused_and_stores_nothing(client, rt) -> None:
    before = snapshot(rt)
    events = len(rt.store.security_events())
    r = post(client, body(cp="BUYER-2"), KEY1)
    assert r.status_code == 403
    assert_nothing_booked(rt, before)
    assert snapshot(rt)["verdict_ids"] == before["verdict_ids"]  # not even compiled
    assert len(rt.store.security_events()) == events + 1


def test_the_chat_helper_sends_the_demo_key_for_a_registered_buyer(client, rt) -> None:
    Chat(client, "helper", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(S03)
    assert stored_ops(rt) == [("ACCEPT_OFFER", "EXECUTED")]


def test_a_configured_key_replaces_the_demo_keys(client, rt, monkeypatch) -> None:
    monkeypatch.setenv("COUNTERPARTY_KEYS", "BUYER-1=prod-key-1, BUYER-2=prod-key-2")
    assert counterparty_for_key("prod-key-2") == "BUYER-2"
    assert counterparty_for_key(DEMO_COUNTERPARTY_KEYS["BUYER-1"]) is None
    assert counterparty_for_key("") is None and counterparty_for_key(None) is None
    assert counterparty_for_key("prod-key-é") is None  # non-ASCII input never raises
    r = post(client, body(), KEY1)
    assert "Agreed" not in r.json()["reply"] and not rt.store.commitments()
    r = post(client, body(), {"X-Counterparty-Key": "prod-key-1"})
    assert stored_ops(rt) == [("ACCEPT_OFFER", "EXECUTED")]


def test_the_counterparty_view_is_unchanged_on_the_authenticated_channel(client, rt) -> None:
    r = post(client, body(), KEY1).json()
    assert r["verdict"] is None and r["operations"] == [] and r["plan"] == [] and r["security_events"] == []


# ---------------------------------------------------------------- S-06: a stated settlement time is not autonomous


@pytest.mark.parametrize("timing", ["today", "tomorrow", "now", "tonight", "right away"])
def test_a_stated_day_is_not_accepted_autonomously_even_with_the_buyer_key(client, rt, timing) -> None:
    r = post(client, body(f"We will pay the ¥420,000 invoice {timing} at a 0.5% discount."), KEY1)
    assert r.status_code == 200
    assert not [c for c in rt.store.commitments() if c.status.value in LIVE]
    assert ("ACCEPT_OFFER", "EXECUTED") not in stored_ops(rt)
    assert "Agreed" not in r.json()["reply"]


@pytest.mark.parametrize("text", ["今天我们付清42万的发票，扣千分之五", "我们明天付清42万的发票，扣千分之五"])
def test_a_stated_day_in_chinese_is_not_accepted_autonomously(client, rt, text) -> None:
    r = post(client, body(text), KEY1)
    assert r.status_code == 200
    assert not [c for c in rt.store.commitments() if c.status.value in LIVE]
    assert "同意：" not in r.json()["reply"]


def test_early_alone_keeps_the_facility_lead_time_and_restates_the_day(client, rt) -> None:
    r = post(client, body("We will pay the ¥420,000 invoice early at a 0.5% discount."), KEY1)
    assert stored_ops(rt) == [("ACCEPT_OFFER", "EXECUTED")]
    assert "on day 2" in r.json()["reply"]
    (c,) = rt.store.commitments()
    assert c.status.value == "ACTIVE"
