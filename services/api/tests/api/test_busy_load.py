"""The busy books load fast in the running app: the seed is replayed once per process (or ahead of the first click, by the warm-up) and
every later reset restores a snapshot of what the replay left (`app.api.seeded_books`). Restored books are replayed books."""

from __future__ import annotations

import dataclasses
import re
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import demo_seed, offer_picture, seeded_books, worklist
from app.api.runtime import Runtime, get_runtime, set_runtime, using_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import agree_on_rcv_a

OWNER = {"X-Owner-Token": "demo-owner-token"}
# Rows stamp the wall-clock time they were written at (`recorded_at`), which no two runs share; the rest of a row is compared.
_WALL = re.compile(r"recorded_at='[^']*'")
_BUSY = {"ok": True, "scenario": "busy", "day": 0}


def _runtime() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    worklist.clear_cache()  # as the `client` fixture leaves them before a test opens the busy books
    offer_picture._cache.clear()
    return rt


def _api(rt: Runtime) -> TestClient:
    from app.main import app

    set_runtime(rt)
    return TestClient(app, headers=OWNER)


def _view(rt: Runtime) -> dict[str, Any]:
    """Everything a test can see of the books: each store container, the chain, the runtime fields and the reads in both languages."""
    store: Any = rt.store
    api = _api(rt)
    ops = store.operations()
    out: dict[str, Any] = {
        "ledger": {n: _WALL.sub("<wall clock>", repr(getattr(store, n))) for n in seeded_books.LEDGER if n != "_ops"},
        "ops": [(e.seq, e.op_id, e.kind, e.idempotency_key, e.payload_json, e.result_json, e.prev_hash, e.entry_hash) for e in ops],
        "op_count": len(ops), "head": ops[-1].entry_hash, "chain_valid": store.verify_chain(),
        "state": store.get_state().model_dump_json(), "mandate": store.get_mandate().model_dump_json(),
        "commitments": [c.model_dump_json() for c in store.commitments()],
        "telemetry": {n: len(getattr(store, n)) for n in seeded_books.TELEMETRY},
        "runtime": {n: repr(getattr(rt, n)) for n in (*seeded_books.RUNTIME_FIELDS, "fresh")},
    }
    for lang in ("en", "zh"):
        for name, url in (("home", "/home"), ("deals", "/deals"), ("worklist", "/worklist")):
            r = api.get(url, params={"lang": lang})
            assert r.status_code == 200, (url, r.text)
            out[f"{name}_{lang}"] = r.json()
    return out


def _same(a: dict[str, Any], b: dict[str, Any]) -> None:
    assert a.keys() == b.keys()
    for k, value in a.items():
        assert value == b[k], f"{k} differs"


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    yield
    set_runtime(None)
    worklist.clear_cache()
    offer_picture._cache.clear()


@pytest.fixture(autouse=True)
def _seeded_books_forgotten() -> Iterator[None]:
    """(Overrides the conftest's: this module's `books` fixture keeps its snapshot across its tests, and forgets it at the end.)"""
    yield


@pytest.fixture(scope="module")
def books() -> Iterator[dict[str, Any]]:
    """The busy books replayed for real through the route (the reference), and the snapshot the warm-up builds (private runtime, then the
    home and worklist read in both languages), kept where a reset finds it."""
    seeded_books.reset_for_tests()
    real = _runtime()
    r = _api(real).post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 200 and r.json() == _BUSY
    replayed = _view(real)
    assert replayed["op_count"] > 5 and len(real.store.verdicts()) >= 11  # the seed really ran: this is not an empty comparison
    set_runtime(real)
    snap = seeded_books.build("busy", seeded_books.key_of("busy", get_settings(), demo_owner_public_key_hex()), get_settings(),
                              demo_owner_public_key_hex())
    seeded_books._ready["busy"] = snap
    set_runtime(None)
    yield {"replayed": replayed, "snap": snap, "real": real}
    seeded_books.reset_for_tests()
    set_runtime(None)


def test_a_restored_busy_runtime_equals_a_replayed_one(books: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    # A second replay would fail loudly: the reset must restore.
    monkeypatch.setattr(demo_seed, "evaluate_offer", lambda *a, **k: (_ for _ in ()).throw(AssertionError("replayed")))
    fast = _runtime()
    api = _api(fast)
    started = time.perf_counter()
    r = api.post("/demo/reset", params={"scenario": "busy"})
    took = time.perf_counter() - started
    assert r.status_code == 200 and r.json() == _BUSY
    assert took < 10, f"a restore took {took:.1f}s"
    restored = _view(fast)
    _same(books["replayed"], restored)
    assert fast.store is not books["real"].store and fast.store._ops is not books["real"].store._ops
    assert restored["chain_valid"] is True and restored["head"] == books["replayed"]["head"]


def test_the_first_reads_after_a_restore_do_not_plan_again(books: dict[str, Any]) -> None:
    fast = _runtime()
    api = _api(fast)
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    for lang in ("en", "zh"):
        for url in ("/worklist", "/deals"):
            started = time.perf_counter()
            assert api.get(url, params={"lang": lang}).status_code == 200
            took = time.perf_counter() - started
            assert took < 5, f"the first {url} in {lang} took {took:.1f}s"


def test_a_write_after_a_restore_leaves_nothing_for_the_next_reset(books: dict[str, Any]) -> None:
    fast = _runtime()
    api = _api(fast)
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    agree_on_rcv_a(api)  # a deal agreed, the caches and the log moved
    assert fast.store.commitments() and len(fast.store.operations()) > books["replayed"]["op_count"]
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    _same(books["replayed"], _view(fast))
    # and the snapshot itself is what the replay left
    assert len(books["snap"].ledger["_ops"]) == books["replayed"]["op_count"] and books["snap"].ledger["_commitments"] == {}


def test_a_changed_seed_flag_fixture_or_owner_key_gives_another_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings, owner = get_settings(), demo_owner_public_key_hex()
    base = seeded_books.key_of("busy", settings, owner)
    assert base == seeded_books.key_of("busy", settings, owner) and base != seeded_books.key_of("golden_sme", settings, owner)
    flipped = dataclasses.replace(settings, features=dataclasses.replace(settings.features, envelope=not settings.features.envelope))
    assert seeded_books.key_of("busy", flipped, owner) != base
    assert seeded_books.key_of("busy", settings, "00" * 32) != base
    real_seed = demo_seed.scenario_seed("busy")
    assert real_seed is not None
    monkeypatch.setattr(demo_seed, "scenario_seed", lambda name: {**real_seed, "offers": real_seed["offers"][:-1]})
    assert seeded_books.key_of("busy", settings, owner) != base
    monkeypatch.undo()
    monkeypatch.setattr(seeded_books, "_fixtures_digest", lambda root: "another fixtures tree")
    assert seeded_books.key_of("busy", settings, owner) != base


def test_a_snapshot_under_another_key_is_dropped_and_the_real_replay_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    seeded_books.reset_for_tests()
    rt = _runtime()
    set_runtime(rt)
    stale = seeded_books.Snapshot(key="built under other flags", ledger={}, runtime={}, caches={})
    seeded_books._ready["busy"] = stale
    snap, key = seeded_books.lookup(rt, "busy")
    assert snap is None and key == seeded_books.key_of("busy", rt.settings, rt.owner_key_hex)
    assert "busy" not in seeded_books._ready


def test_the_snapshot_steps_aside_unless_it_is_provably_the_same_call(monkeypatch: pytest.MonkeyPatch) -> None:
    rt = _runtime()
    set_runtime(rt)
    assert seeded_books.eligible(rt, "busy") and not seeded_books.eligible(rt, "golden_sme")  # (the golden books have no seed)
    monkeypatch.setattr(demo_seed, "replay", lambda rt, scenario: None)
    assert not seeded_books.eligible(rt, "busy")
    monkeypatch.undo()
    rt.store._llm_calls.append(object())  # type: ignore[arg-type]  # ids derive from telemetry: not the same call any more
    assert not seeded_books.eligible(rt, "busy")
    assert not seeded_books.eligible(_runtime(), "busy")  # not the process runtime: the real seed refuses it, so the real call answers


def test_the_warm_up_does_not_block_start_up_or_the_live_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    seeded_books.reset_for_tests()
    release, building, built = threading.Event(), threading.Event(), []
    fake = seeded_books.Snapshot(key="", ledger={}, runtime={}, caches={})

    def slow_build(scenario: str, key: str, settings: Any, owner_key_hex: str, warm_reads: bool = True) -> seeded_books.Snapshot:
        building.set()
        built.append(key)
        release.wait(30)
        return dataclasses.replace(fake, key=key)

    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(seeded_books, "build", slow_build)
    rt = _runtime()
    set_runtime(rt)

    started = time.perf_counter()
    from app.main import app

    with TestClient(app, headers=OWNER):  # the start-up event runs here
        took = time.perf_counter() - started
        assert building.wait(5)
        assert took < 5, f"start-up took {took:.1f}s"
        # The live runtime's lock is free while the warm-up builds, and its books are served.
        got = []

        def take() -> None:
            got.append(rt.lock.acquire(timeout=5))
            rt.lock.release()

        t = threading.Thread(target=take)
        t.start()
        t.join()
        assert got == [True]
        assert seeded_books._building.get("busy") is not None
        # A reset that arrives meanwhile waits for it (nothing held), then finds the snapshot ready.
        waited = []
        w = threading.Thread(target=lambda: (seeded_books.await_warm_up("busy"), waited.append(True)))
        w.start()
        w.join(0.3)
        assert waited == [] and w.is_alive()
        release.set()
        w.join(10)
        assert waited == [True]
    assert "busy" in seeded_books._ready and "busy" not in seeded_books._building
    assert built == [seeded_books._ready["busy"].key]


def test_the_build_sees_its_own_runtime_in_its_thread_only() -> None:
    live, private = _runtime(), _runtime()
    set_runtime(live)
    seen: list[Runtime] = []
    with using_runtime(private):
        assert get_runtime() is private
        t = threading.Thread(target=lambda: seen.append(get_runtime()))
        t.start()
        t.join()
    assert seen == [live] and get_runtime() is live


def test_a_failed_warm_up_leaves_nothing_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    seeded_books.reset_for_tests()
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(seeded_books, "build", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    thread = seeded_books.warm_up("busy")
    assert thread is not None
    thread.join(10)
    assert "busy" not in seeded_books._building and "busy" not in seeded_books._ready
    seeded_books.await_warm_up("busy")  # returns at once


def test_a_live_model_mode_never_warms_up_or_restores(monkeypatch: pytest.MonkeyPatch) -> None:
    live = dataclasses.replace(get_settings(), llm_mode="live")
    monkeypatch.setenv("DEMO_MODE", "1")
    rt = Runtime(settings=live, store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    assert not seeded_books.eligible(rt, "busy")  # the runtime's own settings say live
    cached = _runtime()
    set_runtime(cached)
    assert seeded_books.eligible(cached, "busy")
    monkeypatch.setattr(seeded_books, "get_settings", lambda: live)  # and the process's
    assert not seeded_books.eligible(cached, "busy")
    seeded_books.reset_for_tests()
    assert seeded_books.warm_up("busy") is None and not seeded_books._building


def test_a_wait_for_a_warm_up_is_bounded_and_never_made_holding_the_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    seeded_books.reset_for_tests()
    rt = _runtime()
    set_runtime(rt)
    key = seeded_books.key_of("busy", rt.settings, rt.owner_key_hex)
    seeded_books._building["busy"] = seeded_books._Build(key)  # a warm-up that never ends
    try:
        monkeypatch.setattr(seeded_books, "WAIT_SECONDS", 0.3)
        started = time.perf_counter()
        seeded_books.await_warm_up("busy")
        assert 0.25 < time.perf_counter() - started < 5
        started = time.perf_counter()
        assert seeded_books.lookup(rt, "busy") == (None, key)  # timed out: the real replay answers
        assert 0.25 < time.perf_counter() - started < 5
        monkeypatch.setattr(seeded_books, "WAIT_SECONDS", 30.0)
        with rt.lock:  # the caller holds the runtime's lock (the route): no wait at all
            started = time.perf_counter()
            assert seeded_books.lookup(rt, "busy") == (None, key)
            assert time.perf_counter() - started < 2
    finally:
        seeded_books._building.pop("busy", None)


def test_the_key_follows_the_settings_fixture_dir(tmp_path: Any) -> None:
    settings, owner = get_settings(), demo_owner_public_key_hex()
    (tmp_path / "compiler_cache").mkdir()
    other = dataclasses.replace(settings, fixture_dir=str(tmp_path))
    first = seeded_books.key_of("busy", other, owner)
    assert first != seeded_books.key_of("busy", settings, owner)
    (tmp_path / "compiler_cache" / "x.json").write_text("{}", encoding="utf-8")
    second = seeded_books.key_of("busy", other, owner)
    assert second != first
    (tmp_path / "compiler_cache" / "x.json").write_text('{"a": 1}', encoding="utf-8")
    assert seeded_books.key_of("busy", other, owner) not in (first, second)


def test_a_restore_writes_the_ordered_caches_under_their_locks_and_limits() -> None:
    import importlib

    evaluate = importlib.import_module("app.verifier.evaluate")  # (`app.verifier.evaluate` as an attribute is the function)
    rt = _runtime()
    set_runtime(rt)
    snap = seeded_books._capture(rt, "k")
    snap.caches["app.api.offer_picture._cache"] = [((i,), {"i": i}) for i in range(offer_picture._CACHE_SIZE + 20)]
    snap.caches["app.verifier.evaluate._COMPARE_CACHE"] = [((str(i), "", ""), []) for i in range(evaluate._COMPARE_SIZE + 20)]
    offer_picture._cache.clear()
    evaluate._COMPARE_CACHE.clear()
    done = threading.Event()
    with offer_picture._lock:  # a writer holds the picture cache's lock: the restore waits for it
        t = threading.Thread(target=lambda: (seeded_books.restore(rt, snap), done.set()))
        t.start()
        assert not done.wait(0.5)
    t.join(30)
    assert done.is_set()
    assert len(offer_picture._cache) == offer_picture._CACHE_SIZE and len(evaluate._COMPARE_CACHE) == evaluate._COMPARE_SIZE
    assert list(offer_picture._cache)[-1] == (offer_picture._CACHE_SIZE + 19,)  # the newest are the ones kept
