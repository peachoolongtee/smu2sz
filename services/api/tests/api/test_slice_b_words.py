"""The Deals-relevant words of ticket #138 (map #121, Slice B): a facility's speed to cash is said in the page's language, and the chart moments
say a distance from today (`when`), never "Day N". On the Demo and on the busy company, in both languages."""

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
from tests.api.conftest import english_leaks

pytestmark = pytest.mark.usefixtures("fast_busy")  # the busy seed is replayed once per process (tests/api/busy_snapshot.py)

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Bank credit line", "Invoice financing (onboarded platform)", "Buyer early-payment offer",
         "Government-guaranteed working-capital loan", "Equipment lease"]
DAY_NUMBER = re.compile(r"\bDay \d+|第 ?\d+ ?天")


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    for clear in (worklist.clear_cache, offer_picture._cache.clear):
        clear()
    yield runtime
    set_runtime(None)
    for clear in (worklist.clear_cache, offer_picture._cache.clear):
        clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _speeds(api: TestClient, lang: str) -> dict[str, str]:
    plan = api.post("/router/plan", params={"lang": lang}).json()
    return {m["facility"]["id"]: m["time_to_cash_display"] for m in plan["menu"]}


def test_the_speed_to_cash_is_said_in_the_pages_language(api: TestClient) -> None:
    en, zh = _speeds(api, "en"), _speeds(api, "zh")
    assert en and set(en) == set(zh)
    assert all(re.fullmatch(r"same day|1 day|\d+ days", v) for v in en.values())
    assert all(re.fullmatch(r"当天|\d+ 天", v) for v in zh.values())
    assert {k: v.replace("same day", "当天").replace(" days", " 天").replace(" day", " 天") for k, v in en.items()} == zh
    assert not english_leaks({"menu": list(zh.values())}, NAMES)
    assert _speeds(api, "en") == en  # English is the default and unchanged


def _moments(api: TestClient, offer_id: str, lang: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = api.get(f"/offers/{offer_id}/picture", params={"lang": lang}).json()["moments"]
    return out


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_chart_moments_say_when_and_the_end_is_a_relative_word(api: TestClient, lang: str) -> None:
    oid = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    api.post(f"/offers/{oid}/evaluate", json=EX01)
    moments = _moments(api, oid, lang)
    assert [(m["day"], m["when"]) for m in moments] == {
        "en": [(0, "today"), (30, "in 30 days"), (47, "in 47 days"), (60, "in 60 days"), (62, "in 62 days"), (66, "in 66 days")],
        "zh": [(0, "今天"), (30, "30 天后"), (47, "47 天后"), (60, "60 天后"), (62, "62 天后"), (66, "66 天后")]}[lang]
    for m in moments:
        assert m["when"] and not DAY_NUMBER.search(m["word"]) and not DAY_NUMBER.search(m["when"]) and "day" in m  # `day` stays for the Demo
    end = moments[-1]
    assert end["kind"] == "end" and end["word"] == {"en": "End, in 66 days", "zh": "终点，66 天后"}[lang] and end["day"] == 66
    if lang == "zh":
        assert not english_leaks({"w": [m["word"] for m in moments] + [m["when"] for m in moments]}, NAMES)


def test_the_busy_company_pictures_carry_when_on_every_moment(api: TestClient) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    offers = [d["id"].removeprefix("deal:") for d in api.get("/decisions").json()["decisions"]
              if d["family"] == "DEAL" and d["state"] == "RESPONSE_READY"]
    assert offers
    for oid in offers:
        for lang in ("en", "zh"):
            for m in _moments(api, oid, lang):
                assert m["when"] and not DAY_NUMBER.search(m["word"]), (oid, lang, m["word"])
