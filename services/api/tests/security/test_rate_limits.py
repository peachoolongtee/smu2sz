"""SEC-20 (security register): requests are rate-limited per caller. Before, nothing limited how fast anyone could call the API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import ratelimit
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
B1 = {"X-Counterparty-Key": "demo-buyer-1-key"}
B2 = {"X-Counterparty-Key": "demo-buyer-2-key"}


@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ANON", "5")
    monkeypatch.setenv("RATE_LIMIT_BUYER", "3")
    monkeypatch.delenv("RATE_LIMITS", raising=False)
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app)
    set_runtime(None)


def test_an_anonymous_burst_is_refused_with_429_and_retry_after(c):
    codes = [c.get("/health").status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    r = c.get("/health")
    assert r.status_code == 429 and r.json()["detail"]["code"] == "RATE_LIMITED"
    assert int(r.headers["Retry-After"]) >= 1


def test_a_wrong_token_is_an_anonymous_caller_and_the_owner_keeps_working(c):
    for _ in range(5):
        c.get("/ledger", headers={"X-Owner-Token": "guess"})
    assert c.get("/ledger", headers={"X-Owner-Token": "guess"}).status_code == 429
    assert c.get("/ledger", headers=OWNER).status_code == 200  # the owner has its own bucket


def test_each_buyer_has_its_own_bucket(c):
    for _ in range(3):
        c.get("/health", headers=B1)
    assert c.get("/health", headers=B1).status_code == 429
    assert c.get("/health", headers=B2).status_code == 200


def test_a_bucket_refills_with_time():
    ratelimit.reset()
    assert ratelimit.take("buyer", "X", now=0.0) is None
    for _ in range(ratelimit.limit_for("buyer") - 1):
        ratelimit.take("buyer", "X", now=0.0)
    wait = ratelimit.take("buyer", "X", now=0.0)
    assert wait is not None and wait > 0
    assert ratelimit.take("buyer", "X", now=wait + 0.01) is None


def test_the_limits_can_be_switched_off(c, monkeypatch):
    monkeypatch.setenv("RATE_LIMITS", "0")
    assert all(c.get("/health").status_code == 200 for _ in range(20))
