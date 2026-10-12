"""GET /customers (Home V2 wave 1, the server half): one row per buyer on the books, the worklist's own rows, and the terms a page filters by."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks, figures
from tests.api.test_time_semantics import _walk

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan"]
FIELDS = {"customer_id", "short", "name", "negotiations_count", "needs_you_count", "outstanding_display", "share_text", "tone", "status_text",
          "detail_text", "href"}


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_HOME_V2", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    worklist.clear_cache()
    offer_picture._cache.clear()
    yield runtime
    set_runtime(None)
    worklist.clear_cache()
    offer_picture._cache.clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _offer(api: TestClient, fixture: str = "EX01_PACKAGE") -> None:
    offer = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]
    api.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": fixture})


def _get(api: TestClient, lang: str = "en") -> dict[str, Any]:
    r = api.get("/customers", params={"lang": lang})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def test_the_route_is_the_standard_403_with_the_flag_off(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_HOME_V2", raising=False)
    r = api.get("/customers")
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "FEATURE_DISABLED" and r.json()["detail"]["feature"] == "home_v2"


def test_the_owner_alone_may_read(api: TestClient) -> None:
    from app.main import app

    bare = TestClient(app)
    for headers in ({}, {"X-Owner-Token": "wrong"}):
        assert bare.get("/customers", headers=headers).status_code == 401
    assert bare.get("/customers", headers=OWNER).status_code == 200


def test_one_row_per_buyer_with_the_documented_fields(api: TestClient) -> None:
    _offer(api)
    body = _get(api)
    assert [c["customer_id"] for c in body["customers"]] == ["BUYER-1", "BUYER-2"]
    assert all(set(c) == FIELDS for c in body["customers"])
    foshan, dongguan = body["customers"]
    assert (foshan["short"], foshan["name"], foshan["negotiations_count"], foshan["needs_you_count"]) == (
        "Foshan", "Foshan Home Retail Co.", 1, 1)
    assert (foshan["outstanding_display"], foshan["share_text"], foshan["tone"], foshan["href"]) == (
        "¥420,000", "100% of what you are owed", "warn", "/?customer=BUYER-1")
    assert foshan["status_text"] == "1 open negotiation · 1 needs you"
    assert foshan["detail_text"] == "¥420,000 outstanding · 100% of what you are owed"
    assert (dongguan["status_text"], dongguan["tone"], dongguan["outstanding_display"]) == ("Nothing open", "neutral", "¥0")


def test_it_is_the_worklists_own_rows(api: TestClient) -> None:
    _offer(api)
    assert _get(api)["customers"] == api.get("/worklist").json()["customers"]
    _walk(api, receipt="half")
    listed, wl = _get(api), api.get("/worklist").json()
    assert listed["customers"] == wl["customers"]
    assert listed["customers"][0]["tone"] == "bad"  # the customer with the missed receipt leads, and says so
    assert listed["customers"][0]["needs_you_count"] == wl["counts"]["needs_you"] == 1


def test_search_terms_are_each_customers_name_and_short_name(api: TestClient) -> None:
    body = _get(api)
    assert body["search_terms"] == [{"customer_id": "BUYER-1", "terms": ["Foshan Home Retail Co.", "Foshan"]},
                                    {"customer_id": "BUYER-2", "terms": ["Dongguan Office Supplies Ltd.", "Dongguan"]}]
    assert "search_terms" not in api.get("/worklist").json()


def test_a_customer_is_listed_before_any_offer_and_the_list_is_cached_with_the_worklist(api: TestClient) -> None:
    body = _get(api)
    assert [c["needs_you_count"] for c in body["customers"]] == [0, 0] and body["partial"] is None
    assert _get(api) == body and len(worklist._CACHE) >= 1


def test_the_chinese_list_has_the_same_figures_and_no_english(api: TestClient) -> None:
    _offer(api)
    en, zh = _get(api), _get(api, "zh")
    assert figures(en) == figures(zh)
    assert not english_leaks(zh, NAMES, raw_fields=[r".*href"])
    foshan = zh["customers"][0]
    assert (foshan["status_text"], foshan["share_text"], foshan["detail_text"]) == (
        "1 项进行中的谈判 · 1 项需要您处理", "占您应收款的 100%", "未收 ¥420,000 · 占您应收款的 100%")
    assert zh["customers"][1]["status_text"] == "没有进行中的事项"
