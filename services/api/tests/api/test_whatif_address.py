"""The what-if sandbox runs on the negotiation it is addressed to (Slice B fix S6). `POST /whatif` and `GET /whatif/presets` take `offer_id` (else
`buyer_id`) and simulate that buyer's recurring invoice and earliest open receivable, and name the invoice in words; a buyer with no recurring invoice
to extend gets a `scope_text` that says why, not a bare verdict on another buyer's invoice."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
ACTUAL = {"terms_days": 60, "discount_bp": 120, "rebate_bp": 100}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai", "Dongguan Office Supplies Ltd.", "Dongguan"]


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


@pytest.fixture
def busy(api: TestClient) -> dict[str, str]:
    """The busy books and the offer ids of Foshan (EX01), Dongguan (EX08B) and Zhuhai (EX09)."""
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    ids: dict[str, str] = {}
    for key, fixture in (("foshan", "EX01_PACKAGE"), ("dongguan", "EX08B_JOINT_BUYER2"), ("zhuhai", "EX09_TERMS_BUYER3")):
        ids[key] = str(api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"])
    return ids


def _post(api: TestClient, lang: str = "en", **address: Any) -> dict[str, Any]:
    r = api.post("/whatif", params={"lang": lang}, json={**ACTUAL, **address})
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def test_zhuhais_offer_simulates_zhuhais_invoice_and_foshans_gives_rcv_a_as_before(api: TestClient, busy: dict[str, str]) -> None:
    unaddressed = _post(api)
    foshan = _post(api, offer_id=busy["foshan"])
    zhuhai = _post(api, offer_id=busy["zhuhai"])
    assert unaddressed["params"]["receivable_id"] == foshan["params"]["receivable_id"] == "RCV-A"  # Foshan's: as before
    assert {k: foshan[k] for k in ("outcome", "codes", "forward", "reserve")} == {k: unaddressed[k] for k in ("outcome", "codes", "forward", "reserve")}
    assert zhuhai["params"]["receivable_id"] == "RCV-C1" and zhuhai["params"]["receivable_face_fen"] == 15_000_000
    assert zhuhai["params"]["current_terms_days"] == 60 and zhuhai["forward"] != foshan["forward"]  # its own recurring invoice, its own figures
    assert zhuhai["buyer_id"] == "BUYER-3" and foshan["buyer_id"] == "BUYER-1"
    assert zhuhai["available"] is True and zhuhai["scope_text"] is None
    assert zhuhai["controls"]["receivable_id"] == "RCV-C1" and zhuhai["controls"]["receivable_face_fen"] == 15_000_000
    assert zhuhai["controls"]["current_terms_days"] == 60


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_response_names_the_invoice_in_words_with_no_id(api: TestClient, busy: dict[str, str], lang: str) -> None:
    zhuhai = _post(api, lang, offer_id=busy["zhuhai"])
    foshan = _post(api, lang, offer_id=busy["foshan"])
    assert zhuhai["invoice_text"] == {"en": "the ¥150,000.00 invoice to Zhuhai Kitchenware Wholesale Co., due in 57 days",
                                      "zh": "Zhuhai Kitchenware Wholesale Co. 的 ¥150,000.00 发票，57 天后到期"}[lang]
    assert foshan["invoice_text"] == {"en": "the ¥420,000.00 invoice to Foshan Home Retail Co., due in 32 days",
                                      "zh": "Foshan Home Retail Co. 的 ¥420,000.00 发票，32 天后到期"}[lang]
    for body in (zhuhai, foshan):
        assert "RCV-" not in body["invoice_text"] and "BUYER-" not in body["invoice_text"]
    if lang == "zh":
        assert not english_leaks({"a": zhuhai["invoice_text"], "b": foshan["invoice_text"]}, NAMES)


def test_the_buyer_id_addresses_the_sandbox_when_no_offer_is_named(api: TestClient, busy: dict[str, str]) -> None:
    by_buyer = _post(api, buyer_id="BUYER-3")
    by_offer = _post(api, offer_id=busy["zhuhai"])
    assert by_buyer["params"] == by_offer["params"] and by_buyer["invoice_text"] == by_offer["invoice_text"]
    named = _post(api, offer_id=busy["foshan"], buyer_id="BUYER-3")  # the negotiation wins
    assert named["buyer_id"] == "BUYER-1"


@pytest.mark.parametrize("lang,expected", [
    ("en", "Dongguan has no recurring invoice to extend; the sandbox needs one."),
    ("zh", "Dongguan没有可延期的经常性发票，沙盘需要一张。")])
def test_a_buyer_with_no_recurring_invoice_says_why_instead_of_a_verdict(api: TestClient, busy: dict[str, str], lang: str, expected: str) -> None:
    body = _post(api, lang, offer_id=busy["dongguan"])
    assert body["available"] is False and body["scope_text"] == expected and body["buyer_id"] == "BUYER-2"
    assert "outcome" not in body and body["controls"] is None and body["hypothetical"] is True
    assert body["invoice_text"] and "RCV-" not in body["invoice_text"]  # the invoice it does have is still said, in words
    presets = api.get("/whatif/presets", params={"offer_id": busy["dongguan"], "lang": lang}).json()
    assert presets["available"] is False and presets["scope_text"] == expected and "presets" not in presets


def test_presets_follow_the_same_address(api: TestClient, busy: dict[str, str]) -> None:
    zhuhai = api.get("/whatif/presets", params={"offer_id": busy["zhuhai"]}).json()
    foshan = api.get("/whatif/presets", params={"offer_id": busy["foshan"]}).json()
    bare = api.get("/whatif/presets").json()
    assert zhuhai["receivable_id"] == "RCV-C1" and zhuhai["receivable_face_fen"] == 15_000_000 and zhuhai["current_terms_days"] == 60
    assert foshan["receivable_id"] == bare["receivable_id"] == "RCV-A" and foshan["receivable_face_fen"] == 42_000_000
    assert zhuhai["grid"]["settle_face_fen"]["max"] == 15_000_000 and foshan["grid"]["settle_face_fen"]["max"] == 42_000_000
    assert zhuhai["available"] is True and zhuhai["invoice_text"].startswith("the ¥150,000.00 invoice to Zhuhai")
    assert api.get("/whatif/presets", params={"buyer_id": "BUYER-3"}).json()["receivable_id"] == "RCV-C1"


def test_a_part_settle_above_the_addressed_invoice_is_refused_against_that_invoice(api: TestClient, busy: dict[str, str]) -> None:
    ok = api.post("/whatif", json={**ACTUAL, "settle_face_fen": 20_000_000, "offer_id": busy["foshan"]})  # fits RCV-A (¥420,000)
    assert ok.status_code == 200
    too_big = api.post("/whatif", json={**ACTUAL, "settle_face_fen": 20_000_000, "offer_id": busy["zhuhai"]})  # above RCV-C1 (¥150,000)
    assert too_big.status_code == 422


def test_an_offer_or_a_buyer_the_books_do_not_have_is_a_404_not_a_guess(api: TestClient, busy: dict[str, str]) -> None:
    for address in ({"offer_id": "OFF-nothing"}, {"buyer_id": "BUYER-9"}):
        r = api.post("/whatif", json={**ACTUAL, **address})
        assert r.status_code == 404, (address, r.text)
        assert api.get("/whatif/presets", params=address).status_code == 404


def test_an_addressed_run_does_not_share_the_cache_with_another_buyer(api: TestClient, busy: dict[str, str]) -> None:
    first = _post(api, offer_id=busy["zhuhai"])
    again = _post(api, offer_id=busy["foshan"])
    third = _post(api, offer_id=busy["zhuhai"])
    assert first["key"] != again["key"] and third["cached"] is True and third["params"]["receivable_id"] == "RCV-C1"
