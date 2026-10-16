"""SEC-07, the owner's decision of 16 Oct 2026: DEMO_MODE is off unless set. Unset, the published demo credentials are refused (the
owner and agent routes fail closed until OWNER_TOKEN / AGENT_KEY are set); with DEMO_MODE=1 the demo works."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.auth import (
    DEMO_AGENT_KEY,
    DEMO_COUNTERPARTY_KEYS,
    DEMO_OWNER_TOKEN,
    counterparty_for_key,
    demo_mode,
    is_agent,
    is_owner,
)
from app.api.runtime import Runtime, set_runtime
from app.config import demo_mode as configured_demo_mode
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

CREDENTIALS = ("DEMO_MODE", "OWNER_TOKEN", "AGENT_KEY", "BANK_FEED_KEY", "COUNTERPARTY_KEYS")


@pytest.fixture
def api():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


@pytest.fixture
def unset(monkeypatch):
    for k in CREDENTIALS:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_the_default_is_off(unset):
    assert configured_demo_mode() is False and demo_mode() is False


@pytest.mark.parametrize("value", ["0", "", "no", "off", "false"])
def test_anything_but_an_explicit_yes_is_off(unset, value):
    unset.setenv("DEMO_MODE", value)
    assert demo_mode() is False


def test_unset_the_demo_credentials_are_refused(unset, api):
    assert not is_owner(DEMO_OWNER_TOKEN) and not is_agent(DEMO_AGENT_KEY)
    assert counterparty_for_key(DEMO_COUNTERPARTY_KEYS["BUYER-1"]) is None
    assert api.get("/home", headers={"X-Owner-Token": DEMO_OWNER_TOKEN}).status_code == 503
    assert api.post("/nl", headers={"X-Agent-Key": DEMO_AGENT_KEY}, json={"text": "show cash status"}).status_code == 401
    assert api.post("/demo/reset", headers={"X-Owner-Token": DEMO_OWNER_TOKEN}).status_code in (401, 403, 503)


def test_with_demo_mode_on_the_demo_works(unset, api):
    unset.setenv("DEMO_MODE", "1")
    assert demo_mode() is True and is_owner(DEMO_OWNER_TOKEN) and is_agent(DEMO_AGENT_KEY)
    assert api.get("/home", headers={"X-Owner-Token": DEMO_OWNER_TOKEN}).status_code == 200
    assert api.post("/nl", headers={"X-Agent-Key": DEMO_AGENT_KEY}, json={"text": "show cash status"}).status_code == 200
    assert api.post("/demo/reset", headers={"X-Owner-Token": DEMO_OWNER_TOKEN}).status_code == 200
