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
from app.persistence import CustomerInputRecord, InMemoryLedgerStore
from app.strategy import inputs as inputs_module
from app.strategy.inputs import (
    GOLDEN_INPUTS,
    InputRejected,
    inputs_from_rows,
    load_demo_inputs,
    seed_demo_inputs,
)
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BUYER = "BUYER-1"
DELAY = {"field": "typical_delay_days", "value": 15, "provenance": "OWNER_ENTERED", "source_ref": "the owner's call"}


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    monkeypatch.setenv("FEATURE_CUSTOMER_ECONOMICS", "1")  # most tests below store the economics fields too; the gate has its own tests
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


ECONOMICS: list[tuple[str | None, dict[str, Any]]] = [
    (BUYER, {"field": "annual_sales_fen", "value": 120_000_000, "provenance": "ERP", "source_ref": ""}),
    (BUYER, {"field": "margin_bp", "value": 2000, "provenance": "ESTIMATED", "source_ref": ""}),
    (BUYER, {"field": "margin_basis", "value": "GROSS", "provenance": "OWNER_ENTERED", "source_ref": ""}),
    (BUYER, {"field": "classification", "value": "STRATEGIC", "provenance": "OWNER_ENTERED", "source_ref": ""}),
    (None, {"field": "vat_rate_bp", "value": 1300, "provenance": "OWNER_ENTERED", "source_ref": ""}),
    (None, {"field": "company_gross_margin_bp", "value": 2376, "provenance": "ACCOUNTING_HISTORY", "source_ref": "FY2025"}),
]


@pytest.mark.parametrize(("buyer", "body"), ECONOMICS, ids=[b["field"] for _, b in ECONOMICS])
def test_the_economics_fields_are_refused_in_phase_1_with_a_sentence_naming_the_later_phase(
    api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch, buyer: str | None, body: dict[str, Any]
) -> None:
    monkeypatch.delenv("FEATURE_CUSTOMER_ECONOMICS")
    en = _post(api, body, buyer=buyer)
    assert en.status_code == 422 and en.json()["detail"]["code"] == "INPUT_REJECTED"
    assert "later phase (customer economics)" in en.json()["detail"]["message"]
    assert "FEATURE_CUSTOMER_ECONOMICS" in en.json()["detail"]["message"]
    zh = _post(api, body, buyer=buyer, lang="zh")
    assert zh.status_code == 422 and "后续阶段" in zh.json()["detail"]["message"]
    assert english_leaks([zh.json()["detail"]["message"]], names=["FEATURE_CUSTOMER_ECONOMICS"]) == []
    assert rt.store.all_customer_inputs() == []
    monkeypatch.setenv("FEATURE_CUSTOMER_ECONOMICS", "1")  # the same body is taken once the flag is on
    assert _post(api, body, buyer=buyer).status_code == 200


def test_phase_1_still_takes_the_delay_and_the_aggregate_with_the_economics_flag_off(
    api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FEATURE_CUSTOMER_ECONOMICS")
    assert _post(api, DELAY).status_code == 200
    assert _post(api, {"field": "aggregate", "value": True, "provenance": "OWNER_ENTERED", "source_ref": ""}).status_code == 200
    assert len(rt.store.all_customer_inputs()) == 2


def test_a_buyer_field_on_the_firm_route_is_a_422_with_a_sentence_in_the_language_asked(api: TestClient, rt: Runtime) -> None:
    en = _post(api, DELAY, buyer=None)
    assert en.status_code == 422 and en.json()["detail"]["code"] == "INPUT_REJECTED"
    assert en.json()["detail"]["message"].startswith("Usual delay in paying was not saved: it is a buyer field")
    zh = _post(api, DELAY, buyer=None, lang="zh")
    assert zh.status_code == 422 and zh.json()["detail"]["message"].startswith("“通常的延迟付款天数”未保存")
    assert rt.store.all_customer_inputs() == []


def test_a_value_out_of_range_says_why(api: TestClient) -> None:
    r = _post(api, {**DELAY, "value": 400})
    # the field's own rule in the owner's words (ticket #97), never the field's id
    assert r.status_code == 422 and r.json()["detail"]["reason"] == "the usual delay is a whole number of days late, from 0 to 365"


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


def test_the_digest_follows_what_a_row_says_not_only_its_seq(rt: Runtime) -> None:
    """`seq` restarts after a reset: two rows with the same seq but another value, provenance or time are different keys."""
    from dataclasses import replace

    from app.strategy.inputs import inputs_from_store

    row = rt.store.add_customer_input(CustomerInputRecord(
        org_id="O", counterparty_id=BUYER, field="typical_delay_days", value_json="45", provenance="OWNER_ENTERED", source_ref="",
        entered_by="OWNER", entered_day=0, state_version=1))
    base = inputs_from_rows([row]).digest()
    assert base == inputs_from_store(rt.store).digest() == inputs_from_rows([replace(row)]).digest()
    for changed in (replace(row, value_json="15"), replace(row, provenance="ESTIMATED"), replace(row, recorded_at="2030-01-01T00:00:00+00:00")):
        assert changed.seq == row.seq and inputs_from_rows([changed]).digest() != base


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


# ---------------------------------------------------------------- the Inputs sheet (ticket #97)


def _sheet(api: TestClient, lang: str = "en", query: str = "") -> Any:
    return api.get(f"/buyers/{BUYER}/inputs?lang={lang}{query}", headers=OWNER).json()


def _by(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["key"]: r for r in rows}


def test_the_sheet_reads_the_three_facts_and_the_delay_in_the_boards_order(api: TestClient) -> None:
    b = _sheet(api)
    assert [r["key"] for r in b["fields"]] == ["annual_sales", "gross_margin", "margin_basis", "classification", "typical_delay"]
    rows = _by(b["fields"])
    sales, margin = rows["annual_sales"], rows["gross_margin"]
    assert (sales["label"], sales["value_display"], sales["input_text"], sales["provenance_text"]) == (
        "Annual sales to Foshan", "¥5,460,000", "¥5,460,000", "projected from your books")
    assert sales["note"] == "From your books: ¥420,000 every 30 days, 13 invoices in the next 12 months"
    assert (margin["label"], margin["value_display"], margin["provenance_text"], margin["entered_day_text"]) == (
        "Gross margin on Foshan's orders", "20%", "assumed for the Demo", None)
    assert margin["note"] == "Your company-wide gross margin until you enter Foshan's own"
    assert [o["value"] for o in rows["classification"]["options"]] == ["NORMAL", "IMPORTANT", "STRATEGIC"]
    assert rows["classification"]["note"] == "This changes nothing FLOW does on its own."
    assert rows["classification"]["options"][2]["note"].startswith('Context only: FLOW says "Foshan is marked Strategic')
    assert all(r["editable"] for r in b["fields"]) and b["economics_on"] is True and b["economics_off_text"] is None
    assert [r["key"] for r in b["firm"]] == ["company_gross_margin", "vat_rate"]
    assert b["vat_note"] == "as invoiced (VAT status not set)"
    assert b["consistency"] == [{"key": "ebitda_floor", "lead": "Check against your books:",
                                 "text": "your EBITDA is ¥1,080,000 a year and Foshan is your only invoicing customer, so Foshan's "
                                         "margin is at least 19.8%. 20% passes."}]
    assert b["footer_text"].startswith("Saved as a dated entry in your name.")
    assert b["context"]["back"] == {"label": "Back to Foshan", "href": "/customers/BUYER-1"}
    assert b["inputs"] == [] and b["rows_stored"] == 0  # the earlier fields stay as they were


def test_the_sheet_in_chinese_leaves_no_english(api: TestClient) -> None:
    b = _sheet(api, "zh")
    rows = _by(b["fields"])
    assert rows["gross_margin"]["provenance_text"] == "为演示而假设" and rows["annual_sales"]["provenance_text"] == "根据您的账目推算"
    assert rows["annual_sales"]["note"] == "来自您的账目：每 30 天 ¥420,000，未来 12 个月 13 张发票"
    assert b["vat_note"] == "按开票金额（未设置增值税状态）"
    words = {"rows": [{k: v for k, v in r.items() if k in ("label", "value_display", "provenance_text", "note")} for r in b["fields"] + b["firm"]],
             "options": [o["label"] + o["note"] for r in b["fields"] for o in r["options"]], "vat": b["vat_note"],
             "consistency": b["consistency"], "footer": b["footer_text"]}
    assert english_leaks(words, ("Foshan Home Retail Co.",)) == []


def test_what_the_owner_typed_is_parsed_by_the_server(api: TestClient, rt: Runtime) -> None:
    for field, text, stored in (("annual_sales_fen", "¥5,460,000", 546_000_000), ("annual_sales_fen", "5,460,000.50", 546_000_050),
                                ("margin_bp", "20%", 2000), ("margin_bp", "-5", -500), ("margin_basis", "Contribution margin", "CONTRIBUTION"),
                                ("classification", "Strategic", "STRATEGIC"), ("classification", "重要", "IMPORTANT"),
                                ("typical_delay_days", "10", 10)):
        r = _post(api, {"field": field, "value_text": text, "provenance": "OWNER_ENTERED"})
        assert r.status_code == 200, (field, text, r.text)
        assert r.json()["input"]["value"] == stored, (field, text)
    assert _post(api, {"field": "vat_rate_bp", "value_text": "13%", "provenance": "OWNER_ENTERED"}, buyer=None).json()["input"]["value"] == 1300


@pytest.mark.parametrize(("field", "text", "en", "zh"), [
    ("margin_bp", "150%", "a gross margin is a percentage between −100% and 100%, such as 20%", "毛利率应为 −100% 到 100% 之间的百分比"),
    ("annual_sales_fen", "lots", "annual sales are an amount in yuan of zero or more", "年销售额应为不小于零的人民币金额"),
    ("classification", "VIP", "a customer is classed Normal, Important or Strategic", "客户分类应为普通、重要或战略"),
    ("margin_basis", "net", "the margin basis is gross margin or contribution margin", "毛利率口径应为毛利率或边际贡献率"),
])
def test_a_value_the_field_does_not_take_is_refused_in_both_languages(api: TestClient, rt: Runtime, field: str, text: str, en: str,
                                                                       zh: str) -> None:
    r = _post(api, {"field": field, "value_text": text, "provenance": "OWNER_ENTERED"})
    assert r.status_code == 422 and r.json()["detail"]["reason"].startswith(en)
    z = _post(api, {"field": field, "value_text": text, "provenance": "OWNER_ENTERED"}, lang="zh")
    assert zh in z.json()["detail"]["message"] and english_leaks({"m": z.json()["detail"]["message"]}) == []
    assert rt.store.all_customer_inputs() == []


def test_a_class_or_basis_sent_as_a_value_must_be_one_of_its_keys(api: TestClient) -> None:
    assert _post(api, {"field": "classification", "value": "VIP", "provenance": "OWNER_ENTERED"}).status_code == 422
    assert _post(api, {"field": "classification", "value": "STRATEGIC", "provenance": "OWNER_ENTERED"}).status_code == 200
    both = _post(api, {"field": "margin_bp", "value": 2000, "value_text": "20%", "provenance": "OWNER_ENTERED"})
    neither = _post(api, {"field": "margin_bp", "provenance": "OWNER_ENTERED"})
    assert both.status_code == neither.status_code == 422


def test_saving_a_margin_turns_the_demo_assumption_into_what_you_entered(api: TestClient) -> None:
    before = api.get(f"/customers/{BUYER}/overview", headers=OWNER).json()
    assert _by(before["economics"])["gross_margin"]["note"] == "assumed for the Demo, not confirmed by you"
    assert before["edit_href"] == "/customers/BUYER-1/inputs"
    assert _post(api, {"field": "margin_bp", "value_text": "25%", "provenance": "OWNER_ENTERED"}).status_code == 200
    rows = _by(_sheet(api)["fields"])
    assert (rows["gross_margin"]["value_display"], rows["gross_margin"]["provenance_text"], rows["gross_margin"]["entered_day_text"]) == (
        "25%", "you entered", "entered today")
    assert rows["gross_margin"]["note"] is None
    after = api.get(f"/customers/{BUYER}/overview", headers=OWNER).json()
    assert (_by(after["economics"])["gross_margin"]["value_display"], _by(after["economics"])["gross_margin"]["note"]) == ("25%", "you entered")


def test_the_company_average_stands_in_until_the_buyers_own(api: TestClient) -> None:
    _post(api, {"field": "company_gross_margin_bp", "value_text": "23.76%", "provenance": "OWNER_ENTERED"}, buyer=None)
    margin = _by(_sheet(api)["fields"])["gross_margin"]
    assert (margin["value_display"], margin["provenance_text"]) == ("23.76%", "company average, estimated")
    overview = api.get(f"/customers/{BUYER}/overview", headers=OWNER).json()
    assert _by(overview["economics"])["gross_margin"]["note"] == "company average, estimated"
    firm = api.get("/firm/inputs", headers=OWNER).json()
    assert _by(firm["firm"])["company_gross_margin"]["value_display"] == "23.76%" and firm["vat_note"] == "as invoiced (VAT status not set)"


def test_the_owners_sales_far_from_the_books_are_both_shown(api: TestClient) -> None:
    _post(api, {"field": "annual_sales_fen", "value_text": "¥7,000,000", "provenance": "OWNER_ENTERED"})
    keys = {c["key"]: c for c in _sheet(api)["consistency"]}
    assert keys["sales_gap"]["text"] == "your books project ¥5,460,000 a year; you entered ¥7,000,000. Both are shown."
    assert _by(_sheet(api)["fields"])["annual_sales"]["provenance_text"] == "you entered"


def test_with_economics_off_the_sheet_says_why_and_saves_nothing(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_CUSTOMER_ECONOMICS")
    b = _sheet(api)
    assert b["economics_on"] is False and b["economics_off_text"] == (
        "These facts cannot be saved yet: it belongs to a later phase (customer economics), which is switched off "
        "(FEATURE_CUSTOMER_ECONOMICS).")
    assert not _by(b["fields"])["gross_margin"]["editable"] and _by(b["fields"])["typical_delay"]["editable"]
    assert api.get(f"/customers/{BUYER}/overview", headers=OWNER).json()["edit_href"] is None
    zh = _sheet(api, "zh")
    assert zh["economics_off_text"].startswith("这些信息暂时无法保存：") and english_leaks({"t": zh["economics_off_text"]}) == []
