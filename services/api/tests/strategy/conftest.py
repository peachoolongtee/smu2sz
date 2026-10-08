"""Fixtures of the strategy MVP's tests: the golden books on day 0 and the demo path's books on day 34.

Both are in-memory runtimes (no database, no network). The day-34 books are reached by replaying the demo path in
process, as scripts/demo_run.py and tests/alerts/test_repay_alert.py::to_day34 do: EX01 evaluated, Option A agreed, the
agreed receipt on day 2, the clock to day 34. Module-scoped: the replay takes a few seconds and nothing here writes.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.books import Books, books_from_store
from app.config import get_settings
from app.domain.money import bp, post
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def _runtime() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    return rt


def _replay_to_day34(rt: Runtime) -> None:
    from app.main import app

    set_runtime(rt)
    try:
        c = TestClient(app)
        oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
        c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
        n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
        commitment = rt.store.get_commitment(n["commitment"]["id"])
        assert commitment is not None
        ob = commitment.obligations[0]
        assert ob.base.amount_fen is not None and ob.rate_bp is not None and ob.effective_day is not None
        agreed = ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
        c.post("/clock/advance", json={"to_day": ob.effective_day}, headers=OWNER)
        r = c.post("/operations", headers=BANK, json={
            "kind": "RECEIVE_PAYMENT", "op_id": "strategy-receipt-1", "idempotency_key": "strategy-receipt-1",
            "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
            "receivable_id": ob.base.receivable_id, "amount_fen": agreed}).json()
        assert r["result"]["status"] == "EXECUTED", r
        c.post("/clock/advance", json={"to_day": 30}, headers=OWNER)
        c.post("/clock/advance", json={"to_day": 34}, headers=OWNER)
    finally:
        set_runtime(None)


@pytest.fixture(scope="module")
def rt_day0() -> Runtime:
    """The in-memory runtime on the golden books as loaded (day 0)."""
    return _runtime()


@pytest.fixture(scope="module")
def books_day0(rt_day0: Runtime) -> Books:
    return books_from_store(rt_day0.store)


@pytest.fixture(scope="module")
def rt_day34() -> Iterator[Runtime]:
    """The demo path replayed in process to day 34: cash ¥300,000, need ¥200,000, three open receivables."""
    rt = _runtime()
    _replay_to_day34(rt)
    yield rt


@pytest.fixture(scope="module")
def books_day34(rt_day34: Runtime) -> Books:
    return books_from_store(rt_day34.store)
