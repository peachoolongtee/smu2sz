"""A TestClient over the real app with an in-memory runtime and /nl mounted (main may not mount it yet)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import DEMO_COUNTERPARTY_KEYS
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}  # the agent channel: no owner authority


def build_app() -> FastAPI:
    from app.api.nl import router as nl_router
    from app.main import app as main_app

    if any(getattr(r, "path", None) == "/nl" for r in main_app.routes):
        return main_app
    app = FastAPI()
    app.include_router(main_app.router)
    app.include_router(nl_router)
    return app


@pytest.fixture
def rt() -> Runtime:
    r = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    r.reset()
    set_runtime(r)
    reset_sessions()
    yield r
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def client(rt: Runtime) -> TestClient:
    return TestClient(build_app())


class Chat:
    """A multi-turn owner (or counterparty) conversation."""

    def __init__(self, client: TestClient, session_id: str, actor: str = "OWNER", owner: bool = True,
                 counterparty_id: str | None = None, buyer_profile: str | None = None,
                 key: str | None = "demo") -> None:
        self.client, self.session_id, self.actor = client, session_id, actor
        self.owner, self.counterparty_id, self.buyer_profile = owner, counterparty_id, buyer_profile
        # The counterparty channel key: "demo" (default) sends the published demo key of counterparty_id when it has
        # one (a registered buyer); None sends no key (an unauthenticated sender); any other string is sent as given.
        self.key = DEMO_COUNTERPARTY_KEYS.get(counterparty_id or "") if key == "demo" else key

    def say(self, text: str, **kw) -> dict:
        body = {"session_id": self.session_id, "actor": self.actor, "text": text}
        if self.counterparty_id:
            body["counterparty_id"] = self.counterparty_id
        if self.buyer_profile:
            body["buyer_profile"] = self.buyer_profile
        owner = kw.pop("owner", self.owner)
        key = kw.pop("key", self.key)
        body.update(kw)
        headers = dict(OWNER if owner else AGENT)
        if self.actor == "COUNTERPARTY" and key:
            headers["X-Counterparty-Key"] = key
        r = self.client.post("/nl", json=body, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()


def ops(resp: dict) -> list[tuple[str, str]]:
    return [(o["kind"], o["status"]) for o in resp["operations"]]


def stored_verdict(rt: Runtime, resp: dict) -> dict:
    """The verdict behind a COUNTERPARTY turn, read owner-side from the store: the /nl response withholds it."""
    from app.nl.sessions import SESSIONS

    session = SESSIONS.get(resp["session_id"])
    assert session is not None and session.last_verdict_id is not None
    verdict = rt.store.get_verdict(session.last_verdict_id)
    assert verdict is not None
    return verdict.model_dump(mode="json")


def stored_ops(rt: Runtime, since: int = 0) -> list[tuple[str, str]]:
    """(kind, status) of the operations logged after the first `since`: what a COUNTERPARTY turn executed."""
    import json

    return [(r.kind, json.loads(r.result_json)["status"]) for r in rt.store.operations()[since:]]


def codes(resp: dict) -> list[str]:
    v = resp.get("verdict") or {}
    return list(dict.fromkeys(x["code"] for x in v.get("violations", [])))
