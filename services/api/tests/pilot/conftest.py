"""Fixtures of the pilot journal's tests: an in-memory runtime on the golden books, owner-authenticated, flag on or off."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
HASH = "a" * 64


def entry(**changes: object) -> dict[str, object]:
    """A valid POST body; `changes` override fields."""
    body: dict[str, object] = {
        "week": 3, "sme": "sme-a", "answer": "envelope",
        "flow_said": "You can live with: up to 55-day terms if the price rises 0.30%.",
        "snapshot_hash": HASH, "owner_did": "Said yes to 45 days, no price change.", "choice": "partly",
        "recorded_on": "2026-10-19",
    }
    body.update(changes)
    return body


@pytest.fixture
def runtime() -> Iterator[Runtime]:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    yield rt
    set_runtime(None)


@pytest.fixture
def flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_PILOT_JOURNAL", raising=False)


@pytest.fixture
def flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_PILOT_JOURNAL", "1")


@pytest.fixture
def client(runtime: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)
