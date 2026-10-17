"""A reset starts a fresh Ask FLOW conversation (owner report, 17 Oct): "New conversation" ends the session on the server
(`POST /nl/session/reset`), and a demo reset ends every session. After either, a "go ahead" that meant the old plan runs nothing
and says so. Only the owner, or the caller that opened a session, may end it (SEC-21)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.nl.sessions import SESSIONS, SessionStore
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
B1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
B2 = {"X-Counterparty-Key": "demo-buyer-2-key"}
NOTHING_WAITS = "Nothing in this conversation is waiting for a yes"


@pytest.fixture
def c():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    reset_sessions()
    from app.main import app

    yield TestClient(app)
    reset_sessions()
    set_runtime(None)


def turn(c, sid: str, text: str, headers=OWNER, **extra) -> dict:
    r = c.post("/nl", headers=headers, json={"session_id": sid, "actor": "OWNER", "text": text, "lang": "en", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def pending(c, sid: str) -> dict:
    first = turn(c, sid, "Evaluate EX01")
    assert first["awaiting_confirmation"] is True
    assert SESSIONS.get(sid).pending_plan is not None
    return first


def test_go_ahead_runs_the_plan_when_nothing_was_reset(c):
    """The control: the same two turns with no reset in between do send the plan's operations."""
    pending(c, "web-keep")
    went = turn(c, "web-keep", "go ahead")
    assert went["operations"], went["reply"]


def test_new_conversation_forgets_the_plan_and_a_later_go_ahead_runs_nothing(c):
    pending(c, "web-old")
    r = c.post("/nl/session/reset", headers=OWNER, json={"session_id": "web-old"})
    assert r.status_code == 200
    assert r.json()["ended"] is True
    assert r.json()["message"].startswith("This conversation has ended.")
    assert SESSIONS.get("web-old") is None

    # A stale tab still holding the old id: the id is not continued, nothing runs, and the reply says nothing is waiting.
    late = turn(c, "web-old", "go ahead")
    assert late["session_id"] != "web-old"
    assert late["operations"] == [] and late["awaiting_confirmation"] is False
    assert NOTHING_WAITS in late["reply"]
    # The fresh conversation the web starts after the reset knows nothing of the old one either.
    fresh = turn(c, "web-new", "go ahead")
    assert fresh["operations"] == [] and NOTHING_WAITS in fresh["reply"]
    assert turn(c, "web-new", "why?")["reply"].startswith("There is no verdict to explain yet")


def test_a_replayed_request_id_from_the_ended_session_is_not_replayed(c):
    pending(c, "web-replay")
    went = turn(c, "web-replay", "go ahead", request_id="req-go-1")
    assert went["operations"]
    c.post("/nl/session/reset", headers=OWNER, json={"session_id": "web-replay"})
    again = turn(c, "web-replay", "go ahead", request_id="req-go-1")
    assert again["replayed"] is False and again["operations"] == []


def test_the_message_is_the_servers_in_both_languages(c):
    pending(c, "web-zh")
    zh = c.post("/nl/session/reset", headers=OWNER, json={"session_id": "web-zh", "lang": "zh"}).json()
    assert zh["ended"] is True and zh["message"].startswith("本次对话已结束")


def test_a_caller_without_a_credential_cannot_end_a_session(c):
    pending(c, "web-anon")
    r = c.post("/nl/session/reset", json={"session_id": "web-anon"})
    assert r.status_code == 401
    assert SESSIONS.get("web-anon").pending_plan is not None


def test_the_agent_cannot_end_the_owners_session_but_can_end_its_own(c):
    pending(c, "web-owner")
    r = c.post("/nl/session/reset", headers=AGENT, json={"session_id": "web-owner"})
    assert r.status_code == 200 and r.json()["ended"] is False
    assert SESSIONS.get("web-owner").pending_plan is not None  # untouched
    # The same answer for a session that does not exist: the agent learns nothing about the owner's ids.
    assert c.post("/nl/session/reset", headers=AGENT, json={"session_id": "no-such"}).json()["ended"] is False

    turn(c, "agent-chat", "status", headers=AGENT)
    assert c.post("/nl/session/reset", headers=AGENT, json={"session_id": "agent-chat"}).json()["ended"] is True
    assert SESSIONS.get("agent-chat") is None


def test_a_buyer_ends_only_its_own_keyed_session(c):
    c.post("/nl", headers=B1, json={"actor": "COUNTERPARTY", "session_id": "b1-chat", "text": "hello"})
    assert SESSIONS.get("b1-chat") is not None
    assert c.post("/nl/session/reset", headers=B2, json={"session_id": "b1-chat"}).json()["ended"] is False
    assert SESSIONS.get("b1-chat") is not None
    assert c.post("/nl/session/reset", headers=B1, json={"session_id": "b1-chat"}).json()["ended"] is True
    assert SESSIONS.get("b1-chat") is None


def test_the_owner_may_end_any_session(c):
    turn(c, "agent-2", "status", headers=AGENT)
    assert c.post("/nl/session/reset", headers=OWNER, json={"session_id": "agent-2"}).json()["ended"] is True


def test_the_body_is_checked(c):
    assert c.post("/nl/session/reset", headers=OWNER, json={"session_id": "bad id!"}).status_code == 422
    assert c.post("/nl/session/reset", headers=OWNER, json={"session_id": "x", "extra": 1}).status_code == 422


def test_a_demo_reset_ends_every_conversation(c):
    pending(c, "web-demo")
    turn(c, "agent-3", "status", headers=AGENT)
    assert c.post("/demo/reset", headers=OWNER, json={}).status_code == 200
    assert len(SESSIONS) == 0
    late = turn(c, "web-demo", "go ahead")
    assert late["operations"] == [] and late["awaiting_confirmation"] is False
    assert NOTHING_WAITS in late["reply"]


def test_the_story_restore_ends_every_conversation(c):
    pending(c, "web-story")
    r = c.post("/demo/restore", headers=OWNER, json={})
    assert r.status_code == 200, r.text
    assert SESSIONS.get("web-story") is None
    assert turn(c, "web-story", "go ahead")["operations"] == []


def test_an_ended_id_is_never_continued_by_anyone():
    store = SessionStore()
    s, _ = store.get_or_create("x", "OWNER", owner_auth=True, principal="owner")
    s.last_offer_id = "OFF-1"
    assert store.end("x", None) is True
    again, new = store.get_or_create("x", "OWNER", owner_auth=True, principal="owner")
    assert new and again.id != "x" and again.last_offer_id is None
    assert store.end("x", None) is False  # already gone
