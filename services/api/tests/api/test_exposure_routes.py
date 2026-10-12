"""The buyer-exposure routes (map #88 Phase 1): owner only, behind FEATURE_EXPOSURE, the concentration and the payment behaviour
with the stress test and the capacity still null (`partial`), the two ids resolving to the same buyer, one answer per key in the
cache, and the Chinese read with the same figures as the English one (the helper of map #65 Wave 7)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import strategy_exposure as route
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks, figures, unchanged_words

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan"]
EX01 = {"fixture_id": "EX01_PACKAGE"}


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    route.clear_cache()
    yield runtime
    set_runtime(None)
    route.clear_cache()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


@pytest.fixture
def offer_id(api: TestClient) -> str:
    return str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])


# ---------------------------------------------------------------- the gate


def test_both_routes_are_403_with_the_flag_off(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    for url in (f"/offers/{offer_id}/exposure", f"/decisions/deal:{offer_id}/exposure", "/offers/NOPE/exposure"):
        r = api.get(url)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"
        assert r.json()["detail"]["feature"] == "exposure"


def test_the_flag_is_off_by_default_and_listed_on_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    assert get_settings().features.exposure is False
    from app.main import app

    assert TestClient(app).get("/health").json()["features"]["exposure"] is False
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    assert get_settings().features.exposure is True


def test_the_owner_alone_may_read(api: TestClient, offer_id: str) -> None:
    from app.main import app

    bare = TestClient(app)  # no default credentials
    for headers in ({}, AGENT, {"X-Owner-Token": "wrong"}):
        assert bare.get(f"/offers/{offer_id}/exposure", headers=headers).status_code == 401
        assert bare.get(f"/decisions/deal:{offer_id}/exposure", headers=headers).status_code == 401
    assert bare.get(f"/offers/{offer_id}/exposure", headers=OWNER).status_code == 200


def test_an_unknown_offer_or_decision_is_a_404(api: TestClient, offer_id: str) -> None:
    r = api.get("/offers/OFF-nope/exposure")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "OFFER_NOT_FOUND"
    for decision in ("deal:OFF-nope", "alert:ALERT-RESERVE-12:v1", "nonsense"):  # no such deal, and a funding decision has no buyer
        r = api.get(f"/decisions/{decision}/exposure")
        assert r.status_code == 404 and r.json()["detail"]["code"] == "DECISION_NOT_FOUND", decision


def test_the_response_is_asked_or_a_counter_that_exists(api: TestClient, offer_id: str) -> None:
    assert api.get(f"/offers/{offer_id}/exposure?response=asked").status_code == 200
    for bad in ("counter", "counter:", "counter:-1", "counter:x", "ASKED", "other"):
        assert api.get(f"/offers/{offer_id}/exposure", params={"response": bad}).status_code == 422, bad
    assert api.get(f"/offers/{offer_id}/exposure?response=counter:0").status_code == 404  # not evaluated yet: no counters
    verdict = api.post(f"/offers/{offer_id}/evaluate", json=EX01).json()
    assert verdict["counters"], "EX01 has counter-offers on the golden books"
    ok = api.get(f"/offers/{offer_id}/exposure?response=counter:0")
    assert ok.status_code == 200 and ok.json()["response"] == "counter:0"
    missing = api.get(f"/offers/{offer_id}/exposure?response=counter:{len(verdict['counters'])}")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "COUNTER_NOT_FOUND"
    assert api.get(f"/offers/{offer_id}/exposure?lang=fr").status_code == 422


# ---------------------------------------------------------------- the block


def test_the_block_holds_the_concentration_and_the_payments_and_nothing_else_yet(api: TestClient, offer_id: str) -> None:
    body = api.get(f"/offers/{offer_id}/exposure").json()
    assert body["offer_id"] == offer_id and body["buyer_id"] == "BUYER-1" and body["buyer_name"] == "Foshan Home Retail Co."
    assert body["response"] == "asked" and body["day"] == 0 and body["partial"] is True
    assert body["stress"] is None and body["capacity"] is None
    c, p = body["concentration"], body["payments"]
    assert c["sentence"] == ("Foshan is 100% of what you are owed today (¥420,000). "
                             "No customer receipts are due in the next 30 days.")
    assert c["ar_share_bp"] == 10_000 and c["ar_buyer_display"] == "¥420,000.00" and c["receipts_share_bp"] is None
    assert p["insufficient"] is True and p["completed"] == 0 and p["median_days_late"] is None
    assert p["insufficient_text"].startswith("FLOW has no completed payments from Foshan in the last 12 months")
    assert body["state_version"] == 1


def test_the_read_writes_nothing(api: TestClient, rt: Runtime, offer_id: str) -> None:
    state, chain = rt.store.get_state().model_dump_json(), [e.entry_hash for e in rt.store.operations()]
    facts, inputs = len(rt.store.decision_facts()), len(rt.store.all_customer_inputs())  # type: ignore[attr-defined]
    for url in (f"/offers/{offer_id}/exposure", f"/decisions/deal:{offer_id}/exposure?lang=zh"):
        assert api.get(url).status_code == 200
    assert rt.store.get_state().model_dump_json() == state and [e.entry_hash for e in rt.store.operations()] == chain
    assert (len(rt.store.decision_facts()), len(rt.store.all_customer_inputs())) == (facts, inputs)  # type: ignore[attr-defined]


def test_the_offer_and_its_deal_decision_resolve_to_the_same_buyer_and_the_same_block(api: TestClient, offer_id: str) -> None:
    by_offer = api.get(f"/offers/{offer_id}/exposure").json()
    by_decision = api.get(f"/decisions/deal:{offer_id}/exposure").json()
    assert by_decision["decision_id"] == f"deal:{offer_id}" and by_decision["offer_id"] == offer_id
    drop = {"decision_id", "computed_in_seconds"}
    assert {k: v for k, v in by_decision.items() if k not in drop} == {k: v for k, v in by_offer.items() if k not in drop}
    assert by_decision["buyer_id"] == by_offer["buyer_id"] == "BUYER-1"


def test_an_offer_from_the_other_buyer_shows_that_buyer(api: TestClient, rt: Runtime, offer_id: str) -> None:
    stored = rt.store.get_offer(offer_id)
    assert stored is not None
    rt.store.put_offer(stored.model_copy(update={"offer_id": "OFF-dongguan", "counterparty_id": "BUYER-2"}))
    body = api.get("/offers/OFF-dongguan/exposure").json()
    assert body["buyer_id"] == "BUYER-2" and body["concentration"]["ar_text"] == "Dongguan owes you nothing today."


def test_the_owners_inputs_reach_the_block(api: TestClient, offer_id: str) -> None:
    before = api.get(f"/offers/{offer_id}/exposure").json()
    assert before["payments"]["delay_basis"] == "NONE" and before["concentration"]["is_aggregate"] is False
    for body in ({"field": "typical_delay_days", "value": 15, "provenance": "OWNER_ENTERED", "source_ref": ""},
                 {"field": "aggregate", "value": True, "provenance": "OWNER_ENTERED", "source_ref": ""}):
        assert api.post("/buyers/BUYER-1/inputs", json=body).status_code == 200
    after = api.get(f"/offers/{offer_id}/exposure").json()  # the new rows are part of the key: not the cached block
    assert after["payments"]["typical_delay_days"] == 15 and after["payments"]["delay_basis"] == "OWNER_ENTERED"
    assert after["concentration"]["is_aggregate"] is True and after["concentration"]["ar_share_bp"] is None


# ---------------------------------------------------------------- the cache


def test_one_computation_serves_every_repeat_and_both_ids(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = route.concentration

    def counted(*a: Any, **k: Any) -> Any:
        calls.append("c")
        return real(*a, **k)

    monkeypatch.setattr(route, "concentration", counted)
    for url in (f"/offers/{offer_id}/exposure", f"/offers/{offer_id}/exposure", f"/decisions/deal:{offer_id}/exposure"):
        assert api.get(url).status_code == 200
    assert calls == ["c"]
    api.get(f"/offers/{offer_id}/exposure?lang=zh")  # the language is part of the key ...
    assert calls == ["c", "c"]
    api.post(f"/offers/{offer_id}/evaluate", json=EX01)
    api.get(f"/offers/{offer_id}/exposure?response=counter:0")  # ... and so is the response
    assert calls == ["c", "c", "c"]
    api.get(f"/offers/{offer_id}/exposure?response=counter:0")
    assert calls == ["c", "c", "c"]


def test_the_key_follows_the_books_the_day_and_the_commitments(api: TestClient, rt: Runtime, offer_id: str,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = route.concentration

    def counted(*a: Any, **k: Any) -> Any:
        calls.append("c")
        return real(*a, **k)

    monkeypatch.setattr(route, "concentration", counted)
    api.get(f"/offers/{offer_id}/exposure")
    assert api.post("/clock/advance", json={"to_day": 3}).status_code == 200
    body = api.get(f"/offers/{offer_id}/exposure").json()
    assert body["day"] == 3 and len(calls) == 2


def test_a_failed_computation_is_not_cached(api: TestClient, offer_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.financial import EngineError

    real = route.concentration

    def boom(*a: Any, **k: Any) -> Any:
        raise EngineError("cannot")

    monkeypatch.setattr(route, "concentration", boom)
    r = api.get(f"/offers/{offer_id}/exposure")
    assert r.status_code == 422 and "cannot project" in r.json()["detail"]
    monkeypatch.setattr(route, "concentration", real)
    assert api.get(f"/offers/{offer_id}/exposure").status_code == 200


# ---------------------------------------------------------------- language


def test_the_chinese_read_has_the_same_figures_and_no_english_sentence_left(api: TestClient, offer_id: str) -> None:
    en = api.get(f"/offers/{offer_id}/exposure?lang=en").json()
    zh = api.get(f"/offers/{offer_id}/exposure?lang=zh").json()
    assert zh["lang"] == "zh"
    assert figures({k: v for k, v in en.items() if k not in ("computed_in_seconds", "lang")}) == figures(
        {k: v for k, v in zh.items() if k not in ("computed_in_seconds", "lang")})
    assert english_leaks(zh, NAMES) == []
    assert unchanged_words(en, zh, NAMES) == []
    assert zh["concentration"]["sentence"] == "Foshan占您目前全部应收款的 100%（¥420,000）。未来 30 天内没有客户回款到期。"
    assert zh["payments"]["insufficient_text"].startswith("FLOW 在过去 12 个月内没有Foshan的已完成付款")


def test_the_chinese_read_of_a_buyer_with_owner_input_and_an_aggregate_is_in_chinese(api: TestClient, offer_id: str) -> None:
    api.post("/buyers/BUYER-1/inputs", json={"field": "typical_delay_days", "value": 15, "provenance": "ESTIMATED",
                                              "source_ref": "Demo assumption"})
    zh = api.get(f"/decisions/deal:{offer_id}/exposure?lang=zh").json()
    assert english_leaks(zh, NAMES) == []
    assert zh["payments"]["owner_delay_text"] == "通常的延迟：15 天，估计值，不是记录（FLOW 的收款记录太少，无法衡量）。"
