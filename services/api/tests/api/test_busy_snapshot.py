"""The busy books restored from a snapshot (`tests/api/busy_snapshot.py`) are the busy books replayed: same store, same chain, same
runtime fields, same reads; and a test that writes to them leaves nothing for the next."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api import busy_snapshot
from tests.api.conftest import agree_on_rcv_a

OWNER = {"X-Owner-Token": "demo-owner-token"}


# Rows stamp the wall-clock time they were written at (`recorded_at`), which no two runs share; the rest of a row is compared.
_WALL = re.compile(r"recorded_at='[^']*'")


def _runtime() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    worklist.clear_cache()  # as the `rt` fixtures leave them before a test opens the busy books
    offer_picture._cache.clear()
    return rt


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    yield
    set_runtime(None)
    worklist.clear_cache()
    offer_picture._cache.clear()


def _api(rt: Runtime) -> TestClient:
    from app.main import app

    set_runtime(rt)
    return TestClient(app, headers=OWNER)


def _view(rt: Runtime) -> dict[str, Any]:
    """Everything a test can see of the books: each store container, the chain, the runtime fields and the reads in English."""
    store: Any = rt.store
    api = _api(rt)
    ops = rt.store.operations()
    out: dict[str, Any] = {
        "ledger": {n: _WALL.sub("<wall clock>", repr(getattr(store, n))) for n in busy_snapshot.LEDGER if n != "_ops"},
        "ops": [(e.seq, e.op_id, e.kind, e.idempotency_key, e.payload_json, e.result_json, e.prev_hash, e.entry_hash) for e in ops],
        "op_count": len(ops), "head": ops[-1].entry_hash,
        "state": store.get_state().model_dump_json(), "mandate": store.get_mandate().model_dump_json(),
        "commitments": [c.model_dump_json() for c in store.commitments()],
        "telemetry": {n: len(getattr(store, n)) for n in busy_snapshot.TELEMETRY},
        "runtime": {n: repr(getattr(rt, n)) for n in busy_snapshot.RUNTIME_FIELDS},
    }
    for name, url in (("home", "/home"), ("deals", "/deals"), ("worklist", "/worklist")):
        r = api.get(url, params={"lang": "en"})
        assert r.status_code == 200, (url, r.text)
        out[name] = r.json()
    return out


def _same(a: dict[str, Any], b: dict[str, Any]) -> None:
    assert a.keys() == b.keys()
    for k in a:
        assert a[k] == b[k], f"{k} differs"


def test_a_restored_busy_runtime_equals_a_replayed_one_and_no_write_leaks(monkeypatch: pytest.MonkeyPatch) -> None:
    # Replayed for real: the `rt` fixture's runtime, then POST /demo/reset?scenario=busy, as every test did.
    real = _runtime()
    r = _api(real).post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 200 and r.json() == {"ok": True, "scenario": "busy", "day": 0}
    replayed = _view(real)
    assert replayed["op_count"] > 5 and len(real.store.verdicts()) >= 11  # the seed really ran: this is not an empty comparison

    # Restored from the snapshot (a second, independent replay builds it): the same call through the same route.
    monkeypatch.setattr(Runtime, "reset_demo", busy_snapshot.fast_reset_demo(busy_snapshot._REAL_RESET_DEMO))
    fast = _runtime()
    r = _api(fast).post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 200 and r.json() == {"ok": True, "scenario": "busy", "day": 0}
    restored = _view(fast)
    _same(replayed, restored)
    assert fast.store is not real.store and fast.store._ops is not real.store._ops

    # A test that writes (a deal agreed, the clock's runtime caches filled) and a reset to busy again: nothing of it survives.
    api = _api(fast)
    agree_on_rcv_a(api)
    assert fast.store.commitments() and len(fast.store.operations()) > replayed["op_count"]
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    _same(replayed, _view(fast))

    # The snapshot itself is untouched by what the restored runtimes did.
    [snap] = busy_snapshot._built.values()
    assert len(snap.ledger["_ops"]) == replayed["op_count"] and snap.ledger["_commitments"] == {}


def test_the_fast_path_steps_aside_unless_it_is_provably_the_same_call(monkeypatch: pytest.MonkeyPatch) -> None:
    rt = _runtime()
    set_runtime(rt)
    assert busy_snapshot.eligible(rt)
    monkeypatch.setattr("app.api.demo_seed.scenario_seed", lambda name: {"offerz": []})
    assert not busy_snapshot.eligible(rt)  # a test that breaks the seed gets the real replay and its error
    monkeypatch.undo()
    monkeypatch.setattr("app.api.demo_seed.replay", lambda rt, scenario: None)
    assert not busy_snapshot.eligible(rt)
    monkeypatch.undo()
    rt.store._llm_calls.append(object())  # type: ignore[arg-type]  # ids derive from telemetry: not the same call any more
    assert not busy_snapshot.eligible(rt)
    other = _runtime()  # not the process runtime: the real seed refuses it, so the real call must be the one that answers
    assert not busy_snapshot.eligible(other)
