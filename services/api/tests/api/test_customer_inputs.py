"""The customer-inputs routes (map #88 Phase 1, brief H.4): owner only, behind FEATURE_EXPOSURE, append-only, the latest row
per field in force, a 422 that writes nothing, cleared by the reset, and the Demo's rows seeded as ESTIMATED."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy import inputs as inputs_module
from app.strategy.inputs import GOLDEN_INPUTS, InputRejected, load_demo_inputs, seed_demo_inputs
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BUYER = "BUYER-1"
DELAY = {"field": "typical_delay_days", "value": 15, "provenance": "OWNER_ENTERED", "source_ref": "the owner's call"}


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app)


def _post(api: TestClient, body: dict[str, Any], buyer: str | None = BUYER, lang: str = "en") -> Any:
    path = f"/buyers/{buyer}/inputs" if buyer else "/firm/inputs"
    return api.post(f"{path}?lang={lang}", json=body, headers=OWNER)


# ---------------------------------------------------------------- the gate


def test_every_route_is_403_with_the_flag_off(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_EXPOSURE", raising=False)
    for r in (api.post(f"/buyers/{BUYER}/inputs", json=DELAY, headers=OWNER), api.post("/firm/inputs", json=DELAY, headers=OWNER),
              api.get(f"/buyers/{BUYER}/inputs", headers=OWNER)):
        assert r.status_code == 403 and r.json()["detail"]["code"] == "FEATURE_DISABLED"
        assert r.json()["detail"]["message"] == "Buyer exposure is switched off (FEATURE_EXPOSURE)."


def test_the_owner_alone_may_write_or_read(api: TestClient, rt: Runtime) -> None:
    for headers in ({}, AGENT, {"X-Owner-Token": "wrong"}):
        assert api.post(f"/buyers/{BUYER}/inputs", json=DELAY, headers=headers).status_code == 401
        assert api.post("/firm/inputs", json=DELAY, headers=headers).status_code == 401
        assert api.get(f"/buyers/{BUYER}/inputs", headers=headers).status_code == 401
    assert rt.store.all_customer_inputs() == []  # a refused caller wrote nothing


# ---------------------------------------------------------------- a write


def test_a_write_echoes_the_row_with_its_recorded_at_and_stores_it(api: TestClient, rt: Runtime) -> None:
    r = _post(api, DELAY)
    assert r.status_code == 200
    row = r.json()["input"]
    assert row["field"] == "typical_delay_days" and row["value"] == 15 and row["value_display"] == "15 days"
    assert row["provenance"] == "OWNER_ENTERED" and row["provenance_text"] == "entered by you"
    assert row["source_ref"] == "the owner's call" and row["entered_by"] == "OWNER" and row["entered_day"] == 0
    assert row["counterparty_id"] == BUYER and row["seq"] == 1 and row["recorded_at"].endswith("+00:00")
    [stored] = rt.store.customer_inputs(BUYER)
    assert (stored.recorded_at, stored.value_json, stored.org_id) == (row["recorded_at"], "15", rt.store.get_state().org_id)


def test_a_write_changes_neither_the_books_nor_the_log(api: TestClient, rt: Runtime) -> None:
    state, chain = rt.store.get_state(), [e.entry_hash for e in rt.store.operations()]
    assert _post(api, DELAY).status_code == 200 and _post(api, {**DELAY, "value": 20}).status_code == 200
    assert rt.store.get_state() == state and [e.entry_hash for e in rt.store.operations()] == chain
    assert rt.store.verify_chain()


def test_the_table_is_append_only_and_the_latest_row_is_the_one_in_force(api: TestClient, rt: Runtime) -> None:
    _post(api, DELAY)
    _post(api, {**DELAY, "value": 25, "provenance": "ESTIMATED", "source_ref": "a guess"})
    _post(api, {"field": "aggregate", "value": True, "provenance": "OWNER_ENTERED", "source_ref": ""})
    assert [r.value_json for r in rt.store.customer_inputs(BUYER)] == ["15", "25", "true"]  # the history stays
    got = api.get(f"/buyers/{BUYER}/inputs", headers=OWNER).json()
    assert got["rows_stored"] == 3
    assert [(i["field"], i["value"], i["provenance"]) for i in got["inputs"]] == [
        ("typical_delay_days", 25, "ESTIMATED"), ("aggregate", True, "OWNER_ENTERED")]
    delay = got["inputs"][0]
    assert delay["provenance_text"] == "an estimate, not a record" and delay["source_ref"] == "a guess"
    assert got["inputs"][1]["value_display"] == "yes"


def test_a_buyers_rows_are_apart_from_another_buyers_and_the_firms(api: TestClient) -> None:
    _post(api, DELAY)
    _post(api, {**DELAY, "value": 3}, buyer="BUYER-2")
    assert _post(api, {"field": "vat_rate_bp", "value": 1300, "provenance": "OWNER_ENTERED", "source_ref": ""}, buyer=None).status_code == 200
    assert [i["value"] for i in api.get(f"/buyers/{BUYER}/inputs", headers=OWNER).json()["inputs"]] == [15]
    assert [i["value"] for i in api.get("/buyers/BUYER-2/inputs", headers=OWNER).json()["inputs"]] == [3]


def test_a_firm_row_is_stored_with_no_counterparty(api: TestClient, rt: Runtime) -> None:
    r = _post(api, {"field": "company_gross_margin_bp", "value": 2376, "provenance": "ACCOUNTING_HISTORY", "source_ref": "FY2025"},
              buyer=None)
    assert r.status_code == 200 and r.json()["input"]["counterparty_id"] is None and r.json()["input"]["value_display"] == "23.76%"
    assert [x.field for x in rt.store.customer_inputs(None)] == ["company_gross_margin_bp"]


def test_an_unknown_buyer_is_a_404_and_writes_nothing(api: TestClient, rt: Runtime) -> None:
    for r in (_post(api, DELAY, buyer="NOBODY"), api.get("/buyers/NOBODY/inputs", headers=OWNER)):
        assert r.status_code == 404 and r.json()["detail"]["code"] == "BUYER_NOT_FOUND"
    assert rt.store.all_customer_inputs() == []


# ---------------------------------------------------------------- what is refused (422, nothing written)


@pytest.mark.parametrize("body", [
    {**DELAY, "field": "not_a_field"},
    {**DELAY, "provenance": "GUESSED"},
    {**DELAY, "value": "15"},  # a string is never coerced to a number
    {**DELAY, "value": 15.5},
    {**DELAY, "value": True},  # a boolean is not a number of days
    {**DELAY, "value": None},
    {**DELAY, "value": [15]},
    {**DELAY, "value": -1},
    {**DELAY, "value": 366},
    {"field": "aggregate", "value": 1, "provenance": "OWNER_ENTERED", "source_ref": ""},
    {"field": "aggregate", "value": "true", "provenance": "OWNER_ENTERED", "source_ref": ""},
    {"field": "annual_sales_fen", "value": -5, "provenance": "ERP", "source_ref": ""},
    {"field": "margin_bp", "value": 10_001, "provenance": "ERP", "source_ref": ""},
    {"field": "classification", "value": "  ", "provenance": "OWNER_ENTERED", "source_ref": ""},
    {"field": "classification", "value": 4, "provenance": "OWNER_ENTERED", "source_ref": ""},
    {"field": "margin_basis", "value": "x" * 65, "provenance": "OWNER_ENTERED", "source_ref": ""},
    {**DELAY, "unexpected": 1},
    {"field": "typical_delay_days", "provenance": "ESTIMATED"},
    {"field": "vat_rate_bp", "value": 1300, "provenance": "OWNER_ENTERED", "source_ref": ""},  # a firm field on a buyer route
])
def test_a_bad_body_is_a_422_and_writes_nothing(api: TestClient, rt: Runtime, body: dict[str, Any]) -> None:
    assert _post(api, body).status_code == 422
    assert rt.store.all_customer_inputs() == []


def test_a_buyer_field_on_the_firm_route_is_a_422_with_a_sentence_in_the_language_asked(api: TestClient, rt: Runtime) -> None:
    en = _post(api, DELAY, buyer=None)
    assert en.status_code == 422 and en.json()["detail"]["code"] == "INPUT_REJECTED"
    assert en.json()["detail"]["message"].startswith("Usual delay in paying was not saved: it is a buyer field")
    zh = _post(api, DELAY, buyer=None, lang="zh")
    assert zh.status_code == 422 and zh.json()["detail"]["message"].startswith("“通常的延迟付款天数”未保存")
    assert rt.store.all_customer_inputs() == []


def test_a_value_out_of_range_says_why(api: TestClient) -> None:
    r = _post(api, {**DELAY, "value": 400})
    assert r.status_code == 422 and r.json()["detail"]["reason"] == "typical_delay_days must be between 0 and 365"


# ---------------------------------------------------------------- words in both languages


def test_the_read_answers_in_chinese_with_the_same_figures(api: TestClient) -> None:
    _post(api, DELAY)
    _post(api, {"field": "margin_bp", "value": 2000, "provenance": "ESTIMATED", "source_ref": "Demo assumption"})
    en = api.get(f"/buyers/{BUYER}/inputs?lang=en", headers=OWNER).json()
    zh = api.get(f"/buyers/{BUYER}/inputs?lang=zh", headers=OWNER).json()
    assert [(i["field"], i["value"], i["provenance"]) for i in en["inputs"]] == [(i["field"], i["value"], i["provenance"]) for i in zh["inputs"]]
    assert zh["inputs"][0]["provenance_text"] == "估计值，不是记录" and zh["inputs"][1]["provenance_text"] == "由您填写"
    assert zh["inputs"][1]["value_display"] == "15 天" and zh["inputs"][0]["value_display"] == "20.00%"
    visible = [{k: v for k, v in i.items() if k.endswith(("_text", "_display", "_label"))} for i in zh["inputs"]]
    assert english_leaks(visible) == []


def test_an_estimate_is_never_worded_as_observed(api: TestClient) -> None:
    for prov in ("ESTIMATED", "PROJECTED", "DERIVED", "OWNER_ENTERED"):
        _post(api, {"field": "margin_bp", "value": 1, "provenance": prov, "source_ref": ""})
        text = api.get(f"/buyers/{BUYER}/inputs", headers=OWNER).json()["inputs"][0]["provenance_text"]
        assert not any(w in text.lower() for w in ("observed", "recorded in", "measured")), text


# ---------------------------------------------------------------- reset and the Demo's rows


def test_the_demo_reset_clears_the_inputs(api: TestClient, rt: Runtime) -> None:
    _post(api, DELAY)
    _post(api, {"field": "vat_rate_bp", "value": 1300, "provenance": "OWNER_ENTERED", "source_ref": ""}, buyer=None)
    assert len(rt.store.all_customer_inputs()) == 2
    assert api.post("/demo/reset", headers=OWNER).status_code == 200
    assert rt.store.all_customer_inputs() == []
    assert api.get(f"/buyers/{BUYER}/inputs", headers=OWNER).json()["inputs"] == []


def test_the_shipped_demo_fixture_seeds_no_row_in_phase_1() -> None:
    raw = json.loads(GOLDEN_INPUTS.read_text(encoding="utf-8"))
    assert raw["inputs"] == [] and "schema" in raw
    assert load_demo_inputs() == []


def _fixture(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    path = tmp_path / "golden_inputs.json"
    path.write_text(json.dumps({"inputs": rows}), encoding="utf-8")
    return path


def test_the_demo_seed_is_estimated_demo_assumption_and_never_owner_entered(
    api: TestClient, rt: Runtime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _fixture(tmp_path, [{"counterparty_id": BUYER, "field": "typical_delay_days", "value": 12},
                               {"counterparty_id": "BUYER-2", "field": "aggregate", "value": True},
                               {"counterparty_id": None, "field": "vat_rate_bp", "value": 1300}])
    monkeypatch.setattr(inputs_module, "GOLDEN_INPUTS", path)
    assert api.post("/demo/reset", headers=OWNER).status_code == 200  # the reset seeds from the fixture
    rows = rt.store.all_customer_inputs()
    assert [(r.counterparty_id, r.field, r.value_json) for r in rows] == [
        (BUYER, "typical_delay_days", "12"), ("BUYER-2", "aggregate", "true"), (None, "vat_rate_bp", "1300")]
    assert {(r.provenance, r.source_ref, r.entered_by) for r in rows} == {("ESTIMATED", "Demo assumption", "DEMO")}
    shown = api.get(f"/buyers/{BUYER}/inputs", headers=OWNER).json()["inputs"][0]
    assert shown["provenance_text"] == "an estimate, not a record" and shown["source_ref"] == "Demo assumption"
    assert api.post("/demo/reset", headers=OWNER).status_code == 200  # a second reset starts again from the same rows, not on top of them
    assert len(rt.store.all_customer_inputs()) == 3


def test_a_demo_row_that_fails_validation_stops_the_seed(rt: Runtime, tmp_path: Path) -> None:
    state = rt.store.get_state()
    rt.store.reset()
    for rows in ([{"counterparty_id": BUYER, "field": "typical_delay_days", "value": "soon"}],
                 [{"counterparty_id": "NOBODY", "field": "aggregate", "value": True}],
                 [{"counterparty_id": BUYER, "field": "vat_rate_bp", "value": 1300}]):
        with pytest.raises(InputRejected):
            seed_demo_inputs(rt.store, state, _fixture(tmp_path, rows))
    with pytest.raises(ValueError):  # a field outside the enum
        seed_demo_inputs(rt.store, state, _fixture(tmp_path, [{"counterparty_id": BUYER, "field": "mood", "value": 1}]))
    assert rt.store.all_customer_inputs() == []
