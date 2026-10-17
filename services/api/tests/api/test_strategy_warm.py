"""The local demo's warm-up of the strategy reads (app/api/strategy_warm.py): with DEMO_WARM_STRATEGY=1 a demo reset reads the price
curve and BUYER-1's envelope with its table in the background, so the owner's first visit is a cache hit; off by default, and a
warm-up on books without BUYER-1 does nothing."""

from __future__ import annotations

import pytest

from app.api import strategy_curve, strategy_envelope, strategy_warm
from app.api.runtime import get_runtime
from app.strategy.cache import cache_key


@pytest.fixture
def strategy_on(monkeypatch):
    for flag in ("FEATURE_ENVELOPE", "FEATURE_PRICE_CURVE"):
        monkeypatch.setenv(flag, "1")
    strategy_envelope.clear_cache()
    strategy_curve._cache.clear()
    yield
    strategy_envelope.clear_cache()
    strategy_curve._cache.clear()


def _key(*extra: object) -> str:
    rt = get_runtime()
    return cache_key(rt.store.get_state(), rt.store.get_mandate(), rt.day, rt.store.commitments(), *extra)


def test_off_by_default_nothing_starts(client, strategy_on, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_WARM_STRATEGY", raising=False)
    assert strategy_warm.warm_strategy_reads() is None


def test_a_demo_reset_warms_the_envelope_and_the_price_curve(client, strategy_on, monkeypatch) -> None:
    started = []
    real = strategy_warm.warm_strategy_reads
    monkeypatch.setenv("DEMO_WARM_STRATEGY", "1")
    monkeypatch.setattr(strategy_warm, "warm_strategy_reads", lambda: started.append(real()) or started[-1])
    assert client.post("/demo/reset").status_code == 200
    (thread,) = started
    thread.join(timeout=300)
    assert not thread.is_alive()
    key = _key("BUYER-1")
    assert key in strategy_envelope._cache and key in strategy_envelope._zone_cache
    assert _key() in strategy_curve._cache
    # the page's own read is now the cached answer
    r = client.get("/buyers/BUYER-1/envelope?lang=en&zone=1")
    assert r.status_code == 200 and r.json()["computed_in_seconds"] < 2


def test_books_without_buyer_1_warm_nothing_and_raise_nothing(client, strategy_on, monkeypatch) -> None:
    assert client.post("/demo/reset?scenario=blank").status_code == 200
    monkeypatch.setenv("DEMO_WARM_STRATEGY", "1")
    thread = strategy_warm.warm_strategy_reads()
    assert thread is not None
    thread.join(timeout=120)
    assert len(strategy_envelope._cache) == 0
