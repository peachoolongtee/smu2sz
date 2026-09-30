"""A TestClient over the real app with an in-memory runtime and /nl mounted (main may not mount it yet)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}


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
                 counterparty_id: str | None = None, buyer_profile: str | None = None) -> None:
        self.client, self.session_id, self.actor = client, session_id, actor
        self.owner, self.counterparty_id, self.buyer_profile = owner, counterparty_id, buyer_profile

    def say(self, text: str, **kw) -> dict:
        body = {"session_id": self.session_id, "actor": self.actor, "text": text}
        if self.counterparty_id:
            body["counterparty_id"] = self.counterparty_id
        if self.buyer_profile:
            body["buyer_profile"] = self.buyer_profile
        owner = kw.pop("owner", self.owner)
        body.update(kw)
        r = self.client.post("/nl", json=body, headers=OWNER if owner else {})
        assert r.status_code == 200, r.text
        return r.json()


def ops(resp: dict) -> list[tuple[str, str]]:
    return [(o["kind"], o["status"]) for o in resp["operations"]]


def codes(resp: dict) -> list[str]:
    v = resp.get("verdict") or {}
    return list(dict.fromkeys(x["code"] for x in v.get("violations", [])))
