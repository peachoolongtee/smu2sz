"""The three strategy routes (envelope, price curve, receivables worth): errors, the runtime lock, the answer cache.

Each route snapshots the books under `rt.lock` and computes outside it; a second request for a key being computed
waits for the first. Read-only throughout: the runtime is a fresh in-memory one per test, nothing is written.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.whatif.params import WhatIfParamError

from .conftest import OWNER, _runtime

GOLDEN_BUYER = "BUYER-1"


@pytest.fixture
def rt() -> Iterator[Runtime]:
    from app.api.strategy_envelope import clear_cache

    clear_cache()
    runtime = _runtime()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)
    clear_cache()


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
