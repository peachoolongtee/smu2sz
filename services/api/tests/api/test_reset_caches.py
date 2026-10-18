"""A reset on a long-running server (`pnpm demo:keep`) forgets what was read on the books it replaced, and the strategy warm-up never
blocks the owner (17 Oct, the video recorder's take).

- The worklist, the Deals queue and the customer overview were cached by the log's counts: after a reset the counts start again, so a
  buyer's chat offer on the new books found the earlier books' answer under the same key, and Deals listed a deal the new books never
  held ("Which negotiation?" when opened). Every cache whose key is not pure in the books' contents is cleared on a replacement and
  keyed by the books' generation (`app.api.caches`).
- The strategy caches keyed by the books' contents stay: a reset to the same books reads them again, and other books read other keys.
- The warm-up computes in a process of its own and holds no cache entry: a reset while it runs stops it, and the Home reads at once.
"""

from __future__ import annotations

import pickle
import re
import sys
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import caches, customer_overview, strategy_curve, strategy_envelope, strategy_warm, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
DEAL = re.compile(r"deal%3A(OFF-[0-9a-f]+)")
FIRST = "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter."
SECOND = "We will pay the ¥420k invoice 10 days early for a 1% discount."


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset_demo("golden_sme")
    set_runtime(runtime)
    yield runtime
    strategy_warm.cancel()
    set_runtime(None)


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _chat_offer(api: TestClient, text: str) -> str:
    r = api.post("/nl", json={"actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": text, "lang": "en"})
    assert r.status_code == 200, r.text
    return _deals_on_worklist(api)[-1]


def _deals_on_worklist(api: TestClient) -> list[str]:
    body = api.get("/worklist?lang=en").json()
    return DEAL.findall(str(body["needs_you"] + body["waiting"]))


def _reset(api: TestClient, scenario: str = "golden_sme") -> None:
    assert api.post(f"/demo/reset?scenario={scenario}").status_code == 200


# ---------------------------------------------------------------- the caches across a reset


def test_after_a_reset_the_worklist_and_deals_never_list_a_deal_of_the_books_it_replaced(api: TestClient, rt: Runtime) -> None:
    first = _chat_offer(api, FIRST)
    assert _deals_on_worklist(api) == [first]
    assert first in str(api.get("/deals").json()["queue"])
    assert first in str(api.get("/customers/BUYER-1/overview?lang=en").json())
    marker = rt.store.change_marker()
    _reset(api)
    assert _deals_on_worklist(api) == []
    # A different buyer message on the new books brings the log's counts back to where they were: the same counts, other books.
    second = _chat_offer(api, SECOND)
    assert rt.store.change_marker() == marker and second != first
    assert _deals_on_worklist(api) == [second]
    queue = str(api.get("/deals").json()["queue"])
    assert second in queue and first not in queue
    assert first not in str(api.get("/customers/BUYER-1/overview?lang=en").json())
    customers = api.get("/customers?lang=en").json()
    assert first not in str(customers)


def test_every_replacement_moves_the_generation_on_and_clears_the_caches_it_keys(api: TestClient, rt: Runtime) -> None:
    api.get("/worklist?lang=en")
    api.get("/customers/BUYER-1/overview?lang=en")
    assert len(worklist._CACHE) and len(customer_overview._CACHE)
    before = caches.books_generation()
    _reset(api)
    assert caches.books_generation() > before
    assert len(worklist._CACHE) == 0 and len(customer_overview._CACHE) == 0
    # the story's restore and a swap to another scenario are replacements too
    api.get("/worklist?lang=en")
    gen = caches.books_generation()
    assert api.post("/demo/restore").status_code == 200
    assert caches.books_generation() > gen and len(worklist._CACHE) == 0
    api.get("/worklist?lang=en")
    gen = caches.books_generation()
    _reset(api, "short_facilities")
    assert caches.books_generation() > gen and len(worklist._CACHE) == 0


def test_an_answer_put_after_the_clear_under_the_old_generation_is_never_read(api: TestClient, rt: Runtime) -> None:
    """A read that started on the old books and finishes after the reset puts its answer under the old generation's key: never found."""
    body = api.get("/worklist?lang=en").json()
    stale = {**body, "needs_you": [{"stale": True}]}
    key_parts = dict(worklist._CACHE._data)
    _reset(api)
    for key in key_parts:  # what a slow read of the old books would put back after the clear
        worklist._CACHE.put(key, stale)
    assert "stale" not in str(api.get("/worklist?lang=en").json()["needs_you"])


def test_the_strategy_cache_is_kept_across_a_reset_to_the_same_books_and_misses_on_other_books(
        api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_PRICE_CURVE", "1")
    strategy_curve.clear_cache()
    first = api.get("/cash/price-curve?lang=en")
    assert first.status_code == 200, first.text
    entries = len(strategy_curve._cache)
    _reset(api)  # the same golden books: the same key, the same answer, read from the cache
    again = api.get("/cash/price-curve?lang=en").json()
    assert len(strategy_curve._cache) == entries
    assert {k: v for k, v in again.items() if k != "computed_in_seconds"} == {k: v for k, v in first.json().items() if k != "computed_in_seconds"}
    assert api.post("/clock/advance", json={"to_day": 2}).status_code == 200  # other books: another key, computed on them
    moved = api.get("/cash/price-curve?lang=en").json()
    assert moved["day"] == 2 and len(strategy_curve._cache) == entries + 1
    strategy_curve.clear_cache()


# ---------------------------------------------------------------- the warm-up never blocks the owner

SLOW_WORKER = [sys.executable, "-c", "import sys, time; sys.stdin.buffer.read(); time.sleep(120)"]
# answers every read with a marker after a short wait, as the real worker answers with the route's own values
MARKING_WORKER = [sys.executable, "-c", (
    "import pickle, sys, time; job = pickle.loads(sys.stdin.buffer.read()); time.sleep(float(sys.argv[1]));"
    "sys.stdout.buffer.write(pickle.dumps([(k, key, 'MARK') for k, key, _ in job['reads']]))")]


@pytest.fixture
def warming(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for flag in ("FEATURE_ENVELOPE", "FEATURE_PRICE_CURVE"):
        monkeypatch.setenv(flag, "1")
    monkeypatch.setenv("DEMO_WARM_STRATEGY", "1")
    strategy_envelope.clear_cache()
    strategy_curve.clear_cache()
    yield
    strategy_warm.cancel()
    strategy_envelope.clear_cache()
    strategy_curve.clear_cache()


def _started(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    started: list[Any] = []
    real = strategy_warm.warm_strategy_reads
    monkeypatch.setattr(strategy_warm, "warm_strategy_reads", lambda: started.append(real()) or started[-1])
    return started


def _wait_running() -> None:
    deadline = time.monotonic() + 30
    while not strategy_warm.running():
        assert time.monotonic() < deadline, "the warm-up's worker never started"
        time.sleep(0.05)


def test_a_reset_during_a_warm_up_stops_it_and_the_home_reads_at_once(api: TestClient, warming: None,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(strategy_warm, "WORKER", SLOW_WORKER)
    started = _started(monkeypatch)
    _reset(api)
    _wait_running()
    # the warm-up holds no lock and no entry of the caches: an owner's read of the same answer never waits for it
    assert not strategy_envelope._cache._flights and not strategy_curve._cache._flights
    assert not strategy_envelope._zone_cache._flights
    t0 = time.perf_counter()
    assert api.get("/home?lang=en").status_code == 200
    assert api.get("/worklist?lang=en").status_code == 200
    reads_during = time.perf_counter() - t0
    proc = strategy_warm._current
    assert proc is not None and proc.poll() is None
    t0 = time.perf_counter()
    _reset(api)  # the reset stops the warm-up of the books it replaced, then starts the new books' own
    assert proc.wait(timeout=10) is not None
    first = started[0]
    first.join(timeout=10)
    assert not first.is_alive()
    assert api.get("/home?lang=en").status_code == 200
    after = time.perf_counter() - t0
    assert reads_during < 10 and after < 20, (reads_during, after)


def test_an_answer_that_arrives_after_the_books_were_replaced_is_dropped(api: TestClient, rt: Runtime, warming: None,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(strategy_warm, "WORKER", [*MARKING_WORKER, "2"])
    thread = strategy_warm.warm_strategy_reads()
    assert thread is not None
    _wait_running()
    rt.clear_session_caches()  # a replacement while it runs
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert len(strategy_curve._cache) == 0 and len(strategy_envelope._cache) == 0 and len(strategy_envelope._zone_cache) == 0


def test_the_warm_ups_answers_land_under_the_keys_the_routes_read(api: TestClient, rt: Runtime, warming: None,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(strategy_warm, "WORKER", [*MARKING_WORKER, "0"])
    thread = strategy_warm.warm_strategy_reads()
    assert thread is not None
    thread.join(timeout=60)
    state, mandate, commitments = rt.store.get_state(), rt.store.get_mandate(), tuple(rt.store.commitments())
    assert strategy_curve._cache.get(strategy_curve.curve_key(state, mandate, rt.day, commitments)) == "MARK"
    key = strategy_envelope.envelope_key(state, mandate, rt.day, commitments, "BUYER-1")
    assert strategy_envelope._cache.get(key) == "MARK" and strategy_envelope._zone_cache.get(key) == "MARK"
    # nothing left to warm on these books: no worker is started again
    again = strategy_warm.warm_strategy_reads()
    assert again is not None
    again.join(timeout=10)
    assert not strategy_warm.running()


def test_the_worker_computes_the_routes_own_answer(rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real worker, in its own process, on the books' snapshot: the curve it returns is the one the route computes."""
    import subprocess

    from app.books import books_from_store

    monkeypatch.setenv("FEATURE_PRICE_CURVE", "1")
    books, mandate, commitments = books_from_store(rt.store), rt.store.get_mandate(), tuple(rt.store.commitments())
    key = strategy_curve.curve_key(books.state, mandate, rt.day, commitments)
    job = {"books": books, "mandate": mandate, "day": rt.day, "commitments": commitments, "owner_key_hex": rt.owner_key_hex,
           "reads": [("curve", key, None)]}
    done = subprocess.run(strategy_warm.WORKER, cwd=strategy_warm.API_ROOT, input=pickle.dumps(job), capture_output=True, timeout=300,
                          check=True)
    ((kind, got_key, value),) = pickle.loads(done.stdout)  # this test's own worker, over its own pipe
    assert kind == "curve" and got_key == key
    assert value == strategy_curve.compute_curve(books, mandate, strategy_curve.CommitmentsSnapshot(commitments), rt.day)
