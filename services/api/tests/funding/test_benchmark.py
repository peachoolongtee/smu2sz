"""Latency targets for the router on the golden fixture (cold: every cross-evaluation cache cleared).

- every what-if preset, uncached: under 400 ms;
- golden EX01 (the buyer's package) through `evaluate`: under 250 ms;
- the golden committed plan and comparison: under 100 ms each.

Each figure is the best of three cold runs. Set SKIP_PERF_BENCH=1 to skip on slow CI runners.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

import pytest

from app.compiler import compile_offer
from app.domain.fixtures import load_offers, load_scenario, offer_documents
from app.funding import compare, plan
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import clear_caches, evaluate
from app.whatif import PRESETS, clear_cache, simulate

pytestmark = pytest.mark.skipif(os.environ.get("SKIP_PERF_BENCH") == "1", reason="SKIP_PERF_BENCH=1")

RUNS = 3


def _cold_ms(fn: Callable[[], object]) -> float:
    best = float("inf")
    for _ in range(RUNS):
        clear_cache()
        clear_caches()
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best * 1000


@pytest.fixture(scope="module")
def golden():
    return load_scenario()[0], load_signed_mandate(), demo_owner_public_key_hex()


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_whatif_preset_uncached_under_400ms(golden, preset):
    state, mandate, key = golden
    ms = _cold_ms(lambda: simulate(state, mandate, PRESETS[preset], trusted_owner_key_hex=key))
    assert ms < 400, f"{preset}: {ms:.0f} ms"


def test_ex01_evaluate_under_250ms(golden):
    state, mandate, key = golden
    o = load_offers()["EX01_PACKAGE"]
    offer = compile_offer(offer_documents("EX01_PACKAGE"), o["counterparty_id"])
    declared = dict(o.get("declared_costs") or {})
    ms = _cold_ms(lambda: evaluate(offer, state, mandate, trusted_owner_key_hex=key, owner_declared=declared))
    assert ms < 250, f"EX01 evaluate: {ms:.0f} ms"


@pytest.mark.parametrize("fn", [plan, compare], ids=["plan", "compare"])
def test_router_golden_under_100ms(golden, fn):
    state, mandate, _ = golden
    ms = _cold_ms(lambda: fn(state, [], mandate))
    assert ms < 100, f"router {fn.__name__}: {ms:.0f} ms"
