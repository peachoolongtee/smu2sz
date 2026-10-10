"""The three strategy routes (envelope, price curve, receivables worth): errors, the runtime lock, the answer cache.

Each route snapshots the books under `rt.lock` and computes outside it; a second request for a key being computed
waits for the first. Read-only throughout: the runtime is a fresh in-memory one per test, nothing is written.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.financial import EngineError
from app.funding import NoPermanentSourceError
from app.strategy.cache import AnswerCache, cache_key
from app.whatif.params import WhatIfParamError

from .conftest import OWNER, _runtime

GOLDEN_BUYER = "BUYER-1"
ROUTES = {  # name -> (path, the module of its route, the compute function the route calls)
    "envelope": (f"/buyers/{GOLDEN_BUYER}/envelope", "strategy_envelope", "envelope_facts"),
    "curve": ("/cash/price-curve", "strategy_curve", "price_curve"),
    "worth": ("/receivables/worth", "strategy_collections", "receivables_worth"),
}


def clear_caches() -> None:
    from app.api import strategy_collections, strategy_curve, strategy_envelope

    for module in (strategy_collections, strategy_curve, strategy_envelope):
        module.clear_cache()


class TrackedLock:
    """The runtime's lock, counting how deep the current holders are, so a test can ask whether it is held."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.depth = 0
        self.entries = 0

    def __enter__(self) -> Self:
        self._lock.acquire()
        self.depth += 1
        self.entries += 1
        return self

    def __exit__(self, *_exc: object) -> None:
        self.depth -= 1
        self._lock.release()


@pytest.fixture
def rt() -> Iterator[Runtime]:
    clear_caches()
    runtime = _runtime()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)
    clear_caches()


@pytest.fixture
def api(rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.main import app

    for flag in ("ENVELOPE", "PRICE_CURVE", "COLLECTIONS_WORTH"):
        monkeypatch.setenv(f"FEATURE_{flag}", "1")
    return TestClient(app)


def test_the_envelope_route_never_answers_500_for_a_value_off_the_grid(api, monkeypatch):
    from app.api import strategy_envelope as route

    def off_the_grid(*_a: Any, **_k: Any) -> Any:
        raise WhatIfParamError("settle_face_fen 1 is above the open face of RCV-A (0)")

    monkeypatch.setattr(route, "envelope_facts", off_the_grid)
    for lang, start in (("en", "FLOW cannot value a deal with Foshan Home Retail Co."), ("zh", "FLOW 目前无法为Foshan Home Retail Co.估值")):
        r = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?lang={lang}", headers=OWNER)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["refused"].startswith(start) and body["packages"] == [] and body["levers"] == []
        assert body["unlisted_counters"] == [] and body["hypothetical"] is True


def test_the_envelope_route_maps_an_engine_error_to_422(api, monkeypatch):
    from app.api import strategy_envelope as route
    from app.financial import EngineError

    def broken(*_a: Any, **_k: Any) -> Any:
        raise EngineError("no permanent funding source")

    monkeypatch.setattr(route, "envelope_facts", broken)
    r = api.get(f"/buyers/{GOLDEN_BUYER}/envelope", headers=OWNER)
    assert r.status_code == 422 and "cannot project" in r.json()["detail"]


def test_the_envelope_route_answers_books_with_32_day_terms(rt, api):
    state = rt.store.get_state()
    recurring = [r.model_copy(update={"terms_days": 32}) if r.counterparty_id == GOLDEN_BUYER else r
                 for r in state.recurring_invoices]
    rt.store.put_state(state.model_copy(update={"recurring_invoices": recurring, "state_version": state.state_version + 1}))
    r = api.get(f"/buyers/{GOLDEN_BUYER}/envelope?zone=1", headers=OWNER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refused"] is None and body["primary"].startswith("You can live with: ")
    assert 32 in [z["terms_days"] for z in body["zone"]] and any(p["package"]["terms_days"] == 32 for p in body["packages"])


# ---------------------------------------------------------------- the runtime lock and the answer cache


def _patched(monkeypatch: pytest.MonkeyPatch, name: str, wrap: Any) -> None:
    """Replace the route's compute function by `wrap(real)`."""
    import importlib

    _path, module, func = ROUTES[name]
    route = importlib.import_module(f"app.api.{module}")
    monkeypatch.setattr(route, func, wrap(getattr(route, func)))


@pytest.mark.parametrize("name", list(ROUTES))
def test_the_books_are_read_under_the_lock_and_computed_outside_it(name, rt, api, monkeypatch):
    lock = TrackedLock()
    monkeypatch.setattr(rt, "lock", lock)
    seen: list[int] = []

    def wrap(real: Any) -> Any:
        def compute(*a: Any, **k: Any) -> Any:
            seen.append(lock.depth)
            return real(*a, **k)

        return compute

    _patched(monkeypatch, name, wrap)
    r = api.get(ROUTES[name][0], headers=OWNER)
    assert r.status_code == 200, r.text
    assert lock.entries >= 1 and seen == [0], "computed while the runtime lock was held"


def test_two_requests_for_one_key_compute_once(rt, api, monkeypatch):
    calls: list[int] = []
    entered, release = threading.Event(), threading.Event()

    def wrap(real: Any) -> Any:
        def compute(*a: Any, **k: Any) -> Any:
            calls.append(1)
            entered.set()
            assert release.wait(10)
            return real(*a, **k)

        return compute

    _patched(monkeypatch, "envelope", wrap)
    results: list[Any] = []

    def ask() -> None:
        results.append(api.get(ROUTES["envelope"][0], headers=OWNER))

    first = threading.Thread(target=ask)
    first.start()
    assert entered.wait(10)
    second = threading.Thread(target=ask)
    second.start()
    time.sleep(0.3)  # the second request reaches the cache while the first is still computing
    release.set()
    first.join(30)
    second.join(30)
    assert len(results) == 2 and all(r.status_code == 200 for r in results)
    assert len(calls) == 1
    assert results[0].json()["primary"] == results[1].json()["primary"]


def test_the_cache_single_flight_hands_the_error_to_the_waiting_request():
    cache: AnswerCache[int] = AnswerCache(4)
    entered, release = threading.Event(), threading.Event()
    calls: list[int] = []
    outcome: list[str] = []

    def boom() -> int:
        calls.append(1)
        entered.set()
        release.wait(10)
        raise EngineError("no")

    def ask() -> None:
        try:
            cache.get_or_compute("k", boom)
        except EngineError:
            outcome.append("error")

    threads = [threading.Thread(target=ask) for _ in range(2)]
    threads[0].start()
    assert entered.wait(10)
    threads[1].start()
    time.sleep(0.2)
    release.set()
    for th in threads:
        th.join(30)
    assert outcome == ["error", "error"] and calls == [1]
    assert "k" not in cache and cache.get_or_compute("k", lambda: 7) == 7  # a failure is not cached


def test_the_cache_is_an_lru_of_the_given_size():
    cache: AnswerCache[int] = AnswerCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # a is now the most recent
    cache.put("c", 3)
    assert len(cache) == 2 and cache.get("b") is None and cache.get("a") == 1 and cache.get("c") == 3
    assert AnswerCache[int]().size == 32


def test_the_key_follows_every_input(rt):
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    commitments = rt.store.commitments()
    base = cache_key(state, mandate, 0, commitments, "BUYER-1", 0)
    assert base == cache_key(state, mandate, 0, commitments, "BUYER-1", 0)
    assert len({base, cache_key(state, mandate, 1, commitments, "BUYER-1", 0),
                cache_key(state, mandate, 0, commitments, "BUYER-1", 1), cache_key(state, mandate, 0, commitments, "BUYER-2", 0),
                cache_key(state, mandate.model_copy(update={"version": mandate.version + 1}), 0, commitments, "BUYER-1", 0),
                cache_key(state, mandate, 0, commitments, "BUYER-10")}) == 6


@pytest.mark.parametrize("name", list(ROUTES))
def test_a_cache_hit_computes_nothing_and_reports_its_own_time(name, rt, api, monkeypatch):
    calls: list[int] = []

    def wrap(real: Any) -> Any:
        def compute(*a: Any, **k: Any) -> Any:
            calls.append(1)
            return real(*a, **k)

        return compute

    _patched(monkeypatch, name, wrap)
    first = api.get(ROUTES[name][0], headers=OWNER).json()
    second = api.get(ROUTES[name][0], headers=OWNER).json()
    assert calls == [1]
    assert second["computed_in_seconds"] != first["computed_in_seconds"] or first["computed_in_seconds"] == 0


@pytest.mark.skipif(os.environ.get("SKIP_PERF_BENCH") == "1", reason="SKIP_PERF_BENCH=1")
@pytest.mark.parametrize("name", list(ROUTES))
def test_computed_in_seconds_on_a_hit_is_its_own_near_zero_time(name, rt, api):
    first = api.get(ROUTES[name][0], headers=OWNER).json()
    hit = api.get(ROUTES[name][0], headers=OWNER).json()
    assert hit["computed_in_seconds"] < 0.05, (hit["computed_in_seconds"], first["computed_in_seconds"])


# ---------------------------------------------------------------- errors are 422 with a sentence, never 500


@pytest.mark.parametrize("error", [NoPermanentSourceError("no permanent source"), EngineError("bad books")])
@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_curve_route_maps_its_errors_to_422(api, monkeypatch, error, lang):
    from app.api import strategy_curve as route

    def broken(*_a: Any, **_k: Any) -> Any:
        raise error

    real = route.price_curve
    monkeypatch.setattr(route, "price_curve", broken)
    r = api.get(f"/cash/price-curve?lang={lang}", headers=OWNER)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, str) and detail and " fen" not in detail
    # the failure is not cached: the next request computes again
    monkeypatch.setattr(route, "price_curve", real)
    assert api.get("/cash/price-curve", headers=OWNER).status_code == 200


def test_a_value_above_the_ceiling_is_a_200_with_above_guard_not_a_422(api, monkeypatch):
    from app.strategy import price_curve as module

    monkeypatch.setattr(module, "_ceiling_fen", lambda *_: 1)
    r = api.get("/cash/price-curve", headers=OWNER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [b["above_guard"] for b in body["bands"]] == [False, True, False]  # the band keeps its value
    assert body["bands"][1]["value_fen"] == 8911 and body["sentence"].startswith("Cash in the next 30 days saves you ¥89.11")


@pytest.mark.parametrize("error", [EngineError("bad books"), NoPermanentSourceError("no permanent source")])
def test_the_worth_route_maps_its_errors_to_422(api, monkeypatch, error):
    from app.api import strategy_collections as route

    def broken(*_a: Any, **_k: Any) -> Any:
        raise error

    monkeypatch.setattr(route, "receivables_worth", broken)
    r = api.get("/receivables/worth", headers=OWNER)
    assert r.status_code == 422 and r.json()["detail"].startswith("cannot project")
