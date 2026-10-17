"""SEC-21 (security register): a chat session belongs to whoever opened it.

Before, a session was bound only to the actor and whether the owner token was shown: a sender with no key could continue a buyer's keyed
session by its id, and 1,001 agent turns with fresh ids evicted the owner's session and its pending plan."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import sessions as sessions_mod
from app.nl.sessions import SessionStore
from app.persistence import InMemoryLedgerStore

B1 = {"X-Counterparty-Key": "demo-buyer-1-key"}


@pytest.fixture
def c():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def test_a_sender_without_the_key_cannot_continue_a_buyers_keyed_session(c):
    keyed = c.post("/nl", headers=B1, json={"actor": "COUNTERPARTY", "session_id": "b1-chat", "text": "hello"}).json()
    assert keyed["session_id"] == "b1-chat"
    anon = c.post("/nl", json={"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "session_id": "b1-chat", "text": "hello"}).json()
    assert anon["session_id"] != "b1-chat"
    again = c.post("/nl", headers=B1, json={"actor": "COUNTERPARTY", "session_id": "b1-chat", "text": "hello again"}).json()
    assert again["session_id"] == "b1-chat" and again["turn"] == 2  # the buyer's own session went on untouched


def test_a_flood_of_other_sessions_never_evicts_the_owners(monkeypatch):
    monkeypatch.setattr(sessions_mod, "MAX_SESSIONS", 5)
    store = SessionStore()
    owner, _ = store.get_or_create("owner-main", "OWNER", owner_auth=True, principal="owner")
    for i in range(50):
        store.get_or_create(f"agent-{i}", "OWNER", owner_auth=False, principal="agent")
    assert store.get("owner-main") is owner
    assert len(store) <= 6  # trimmed before each new session is added, so at most one over the limit


def test_a_session_continues_only_for_the_same_principal():
    store = SessionStore()
    s, new = store.get_or_create("x", "COUNTERPARTY", principal="buyer:BUYER-1")
    assert new
    other, new_other = store.get_or_create("x", "COUNTERPARTY", principal="buyer:BUYER-2")
    assert new_other and other.id != "x"
    same, new_same = store.get_or_create("x", "COUNTERPARTY", principal="buyer:BUYER-1")
    assert not new_same and same is s
