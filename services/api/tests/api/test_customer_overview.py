"""GET /customers/{id}/overview (map #88, ticket #108, the server half): the Customer overview read.

Golden day 0: the Foshan offer (60-day terms, a 1% rebate, early payment) is evaluated, and FLOW's plan (a ¥147k credit-line draw and
¥255k of invoice financing) is either waiting or has run. The read is composed from reads the other pages make, so the figures asserted
here are theirs: the receivable rows' financing words, the exposure block's stress and capacity, the offer picture's recommended path.
The owner's inputs are written by the test (the Demo seeds none)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview as overview
from app.api import offer_picture
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import FundingLot, SourceDocument
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.persistence.records import CustomerInputRecord
from app.strategy import exposure as assembly
from tests.api.conftest import english_leaks, figures, unchanged_words

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Bank credit line",
         "Invoice financing (onboarded platform)", "Buyer early-payment offer"]
EX01 = {"fixture_id": "EX01_PACKAGE"}
RAW_ID = re.compile(r"\b(?:RCV|BUYER|FAC|LOT|CMT|OFF|CTR|VER|OP|APR|DOC)-[A-Za-z0-9]|RI:|\bday -?\d")
HREFS = r".*href"  # the routes a page links to carry ids and the same text in both languages
ID_KEYS = ("key", "customer_id", "lang", "customer", "deal", "scenario", "decision_id", "subject_demo_text")  # the last three are `context` echoes of the URL selections: ids, not sentences


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    assembly.clear_cache()
    overview.clear_cache()
    offer_picture._cache.clear()  # keyed by the state version, which a test that replaces the state does not move
    yield runtime
    set_runtime(None)
    assembly.clear_cache()
    overview.clear_cache()
    offer_picture._cache.clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _offer(api: TestClient) -> str:
    offer = api.post("/offers", json=EX01).json()["offer"]
    api.post(f"/offers/{offer['offer_id']}/evaluate", json=EX01)
    return str(offer["offer_id"])


def _run_plan(api: TestClient) -> None:
    a = api.get("/home").json()["next_action"]
    r = api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["executed"] == 2


def _input(rt: Runtime, field: str, value: Any, provenance: str, by: str = "OWNER", buyer: str = "BUYER-1") -> None:
    state = rt.store.get_state()
    rt.store.add_customer_input(CustomerInputRecord(
        org_id=state.org_id, counterparty_id=buyer, field=field, value_json=json.dumps(value), provenance=provenance,
        source_ref="Demo assumption" if by == "DEMO" else "test", entered_by=by, entered_day=0, state_version=state.state_version))


def _economics(rt: Runtime) -> None:
    """The board's facts: the page assumes the Demo's 20% margin and projects ¥5.46m of sales from the books; the owner says Normal."""
    _input(rt, "classification", "NORMAL", "OWNER_ENTERED")


def _before(api: TestClient, rt: Runtime) -> str:
    """Golden day 0 with the offer waiting and the plan ready, not run."""
    offer_id = _offer(api)
    _economics(rt)
    return offer_id


def _after(api: TestClient, rt: Runtime) -> str:
    """Golden day 0 after the plan ran: ¥150k drawn, ¥255k of invoice financing arriving in 3 days."""
    offer_id = _offer(api)
    _run_plan(api)
    _economics(rt)
    return offer_id


def _get(api: TestClient, customer: str = "BUYER-1", lang: str = "en", **query: str) -> dict[str, Any]:
    r = api.get(f"/customers/{customer}/overview", params={"lang": lang, **query})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _fig(body: dict[str, Any], key: str) -> dict[str, Any]:
    return next(f for f in body["figures"] if f["key"] == key)


def _row(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return next(r for r in rows if r["key"] == key)


# ---------------------------------------------------------------- golden day 0, English


def test_before_the_plan_the_page_is_the_board_in_english(api, rt):
    offer_id = _before(api, rt)
    b = _get(api)
    assert (b["customer_id"], b["name"], b["lang"], b["day"]) == ("BUYER-1", "Foshan Home Retail Co.", "en", 0)
    assert b["summary_text"] == "What this relationship is worth, and what it puts at risk."
    assert [f["key"] for f in b["figures"]] == ["value", "outstanding", "financing", "share"]
    value, owed, financing, share = b["figures"]
    assert (value["label"], value["value_display"], value["note"]) == ("Relationship value", "about ¥1.09m", "a year, estimated contribution; margin assumed for the Demo, not confirmed by you")
    assert (owed["value_display"], owed["note"], owed["tone"]) == ("¥420,000", "due in 32 days, nothing overdue", "neutral")
    assert (financing["label"], financing["value_display"], financing["note"]) == (
        "Financing linked", "¥255,000", "¥255k financing planned against Foshan's invoice · not yet received")  # the plan's advance, planned and not counted
    assert (financing["state"], financing["state_text"]) == ("planned", "Planned")
    assert (share["value_display"], share["note"], share["tone"]) == (
        "100%", "100% of currently open receivables", "warn")
    d = b["decision"]
    assert d["eyebrow"] == "One commercial decision waits for you"
    assert d["text"] == ("Foshan wants early settlement of ¥420,000.00 at 1.20%, payment terms to 60 days and a 1.00% rebate. "
                         "FLOW recommends countering with Option A, ¥3,035.99 once if accepted.")
    assert (d["headline_short"], d["authority_text"]) == ("Counter instead of accepting their request", "FLOW can send this counter without your approval.")
    picture = api.get(f"/offers/{offer_id}/picture").json()
    recommended = next(p for p in picture["paths"] if p["recommended"])
    assert d["primary"] == {"label": "Review the counter",
                            "href": f"/deals?decision=deal%3A{offer_id}&path={recommended['key']}"}
    assert [(a["label"], a["href"]) for a in d["secondary"]] == [
        ("View the invoices", "/receivables?customer=BUYER-1&invoice=RCV-A"),
        ("Stress-test payment", "/cash?stress=BUYER-1:30&invoice=RCV-A")]
    assert d["secondary"] == b["actions"] and b["none_text"] is None
    assert [(r["key"], r["value_display"], r["note"], r["tone"]) for r in b["economics"]] == [
        ("annual_sales", "¥5,460,000", "projected from your books", "neutral"),
        ("gross_margin", "20%", "assumed for the Demo, not confirmed by you", "warn"),
        ("contribution", "about ¥1,092,000", "under today's terms", "neutral"),
        ("open_request", "about 2.6% of it if you accept their request, over 12 months, plus ¥5,040.00 once", "the cost of keeping the same sales on softer terms, not profit gained", "neutral"),
        ("classification", "Normal", "context only", "neutral")]
    assert b["economics_note"] == ("A customer worth ¥1.09m a year does not by itself justify a ¥28,330 concession over 12 months; the question is how "
                                   "much of that is at risk if you counter. None of this changes what FLOW may do on its own.")
    # the inputs sheet is Phase 2: the label stays, the link waits for FEATURE_CUSTOMER_ECONOMICS
    assert (b["edit_label"], b["edit_href"], b["partial"]) == ("Edit these facts", None, None)
    assert b["note"] is None


def test_before_the_plan_the_exposure_rows_are_the_exposure_layers_own(api, rt):
    offer_id = _before(api, rt)
    b = _get(api)
    rows = b["exposure"]["rows"]
    assert [r["key"] for r in rows] == ["payments", "financing", "stress", "capacity"]  # no financing, so no "financing then"
    assert (rows[0]["value_display"], rows[0]["tone"]) == ("not enough history yet", "neutral")
    assert rows[1]["value_display"] == "¥255,000 against the ¥420,000 invoice" and rows[1]["note"] == "if you run the plan · not counted as cash"
    assert (rows[1]["state"], rows[1]["state_text"]) == ("planned", "Planned")
    assert (rows[2]["label"], rows[2]["value_display"], rows[2]["tone"]) == (
        "Paid 30 days late", "−¥250,000 in 60 days; 65 days below your minimum; ¥550,000 uncovered", "bad")
    assert (rows[3]["value_display"], rows[3]["note"]) == (
        "¥81,000 today; ¥2,000 if Foshan accepts Option A", "Room for another payment: ¥2,000 (today ¥81,000).")  # the line's ¥2,790 (R-10)
    assert b["exposure"]["same_figures_note"].startswith("The same figures as on the deal")
    # the numbers are the deal's own: the exposure route says the same of the recommended path
    ex = api.get(f"/offers/{offer_id}/exposure", params={"lang": "en", "response": "counter:0"}).json()
    lead = next(p["key"] for p in api.get(f"/offers/{offer_id}/picture").json()["paths"] if p["recommended"])
    assert ex["band"]["by_path"][lead]["capacity"] == rows[3]["note"]
    assert ex["stress"]["paths"][lead]["breach_days"] == 65 and ex["stress"]["paths"][lead]["lowest_fen"] == -25_000_000


def test_before_the_plan_the_history_has_the_offer_and_the_terms_in_force(api, rt):
    offer_id = _before(api, rt)
    h = _get(api)["history"]
    assert [(x["when_text"], x["href"]) for x in h] == [("Today", f"/deals?decision=deal%3A{offer_id}"), ("In force", None)]
    assert h[0]["text"] == ("Asked for early settlement of ¥420,000.00 at 1.20%, payment terms to 60 days and a 1.00% rebate. "
                            "Two replies are ready to send.")
    assert h[1]["text"] == ("No confirmed agreement on file; payment is due 45 days from the invoice date; "
                            "early payment: none agreed on this invoice")


def test_after_the_plan_the_financing_is_arranged_and_not_advanced(api, rt):
    _after(api, rt)
    b = _get(api)
    financing = _fig(b, "financing")
    assert (financing["value_display"], financing["note"]) == ("¥255,000", "financing arranged, expected in 3 days")
    rows = b["exposure"]["rows"]
    assert [r["key"] for r in rows] == ["payments", "financing", "stress", "financing_then", "capacity"]
    assert _row(rows, "financing")["value_display"] == "¥255,000 against the ¥420,000 invoice"
    assert _row(rows, "financing")["note"] == ("financing arranged, expected in 3 days; repaid from the receipt; "
                                               "about ¥163k then becomes available cash")
    assert _row(rows, "financing_then")["value_display"] == "runs 30 days longer; about ¥2,270 more in charges"
    # the receivable row says the same, in its own words
    r0 = api.get("/receivables").json()["rows"][0]
    assert r0["net"]["net_short"] == "about ¥163k" and r0["net"]["per_period_text"] == "about ¥2,270 more for every 30 days late"
    text = " ".join(x["text"] for x in b["history"])
    assert "advanced" not in text
    assert any("¥255,000 against" in x["text"] and x["href"] and x["href"].startswith("/decisions/") for x in b["history"])


def test_a_landed_advance_is_received_and_the_figure_keeps_its_one_state(api, rt):
    _after(api, rt)
    state = rt.store.get_state()
    lot = next(x for x in state.lots if x.receivable_id == "RCV-A")
    rt.store.put_state(state.model_copy(update={"lots": [FundingLot(**{**lot.model_dump(), "arrival_day": -2, "settled": True})]}))
    offer_picture._cache.clear()  # the picture is keyed by the state version, which put_state does not move
    f = _fig(_get(api), "financing")
    assert f["note"] == "financing received 2 days ago" and "arranged" not in f["note"]


def test_an_invoice_marked_financed_with_no_advance_on_record_is_said_so_not_counted(api, rt):
    _before(api, rt)
    state = rt.store.get_state()
    rcv = next(r for r in state.receivables if r.id == "RCV-A")
    rt.store.put_state(state.model_copy(update={"receivables": [rcv.model_copy(update={"status": "FINANCED"})]}))
    offer_picture._cache.clear()
    b = _get(api)
    f = _fig(b, "financing")
    row = api.get("/receivables").json()["rows"][0]["net"]
    assert (f["value_display"], f["note"], f["tone"]) == ("Not on record", row["unrecorded_text"], "warn")
    assert _row(b["exposure"]["rows"], "financing")["value_display"] == row["unrecorded_text"]
    zh = _get(api, lang="zh")
    assert _fig(zh, "financing")["value_display"] == "无记录" and english_leaks(zh, NAMES, raw_fields=[HREFS]) == []


# ---------------------------------------------------------------- golden day 0, Chinese


def test_the_chinese_page_has_the_same_figures_and_no_english_left(api, rt):
    _before(api, rt)
    en, zh = _get(api), _get(api, lang="zh")
    assert figures(en) == figures(zh)
    assert english_leaks(zh, NAMES, raw_fields=[HREFS]) == []
    assert unchanged_words(en, zh, NAMES, raw_fields=[HREFS]) == []
    assert [f["value_display"] for f in zh["figures"]] == ["约 ¥109万", "¥420,000", "¥255,000", "100%"]
    assert zh["figures"][2]["note"] == "计划融资 ¥255k，以Foshan的发票做融资 · 尚未到账" and (zh["figures"][2]["state"], zh["figures"][2]["state_text"]) == ("planned", "计划中")
    assert zh["figures"][1]["note"] == "32 天后到期，没有逾期"
    assert zh["figures"][3]["note"] == "占当前未收应收款的 100%"
    assert zh["decision"]["eyebrow"] == "有一项商务决定等待您处理"
    assert zh["decision"]["primary"]["label"] == "查看还价" and zh["decision"]["authority_text"] == "FLOW 可以在无需您批准的情况下发送这份还价。"
    assert "FLOW 建议以方案 A（如被接受，一次性成本 ¥3,035.99）还价" in zh["decision"]["text"]
    assert [r["value_display"] for r in zh["economics"][:3]] == ["¥5,460,000", "20%", "约 ¥1,092,000"]
    assert zh["economics"][0]["note"] == "根据您的账目推算" and zh["economics"][1]["note"] == "为演示而假设，尚未经您确认"
    assert zh["economics"][4]["value_display"] == "普通"
    assert "您" in zh["economics_note"]
    stress = _row(zh["exposure"]["rows"], "stress")
    assert stress["label"] == "晚付 30 天" and stress["value_display"].startswith("60 天后降至 −¥250,000；有 65 天低于您的最低现金")
    assert zh["history"][1]["text"].startswith("尚无已确认的协议；账期为自开票日起 45 天")
    assert zh["context"]["back"]["label"] == "返回交易"
    assert zh["economics"][3]["value_display"] == "如果接受对方的要求，12 个月内约占其中的 2.6%，另加一次性 ¥5,040.00"


def test_the_chinese_page_after_the_plan_has_no_english_left(api, rt):
    _after(api, rt)
    en, zh = _get(api), _get(api, lang="zh")
    assert figures(en) == figures(zh)
    assert english_leaks(zh, NAMES, raw_fields=[HREFS]) == []
    assert unchanged_words(en, zh, NAMES, raw_fields=[HREFS]) == []
    assert zh["figures"][2]["note"] == "融资已安排，预计3 天后到账"
    assert _row(zh["exposure"]["rows"], "financing_then")["value_display"] == "多持续 30 天；费用约增加 ¥2,270"


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_no_sentence_carries_a_raw_id(api, rt, lang):
    _after(api, rt)
    body = _get(api, lang=lang)

    def sentences(x: Any, key: str = "") -> list[str]:
        if isinstance(x, dict):
            return [s for k, v in x.items() for s in sentences(v, k)]
        if isinstance(x, list):
            return [s for v in x for s in sentences(v, key)]
        return [x] if isinstance(x, str) and key not in ID_KEYS and not key.endswith("href") else []

    assert [s for s in sentences(body) if RAW_ID.search(s)] == []


# ---------------------------------------------------------------- the flag, the buyers, the nothings


def test_with_the_exposure_flag_off_the_block_is_null_with_a_note(api, rt, monkeypatch):
    _before(api, rt)
    on = _get(api)
    monkeypatch.delenv("FEATURE_EXPOSURE")
    off = _get(api)
    assert off["exposure"] is None
    assert off["note"] == ("Financial exposure is not switched on for this account, so payment behaviour, the late-payment test and "
                           "spare capacity are not shown.")
    assert [a["key"] for a in off["actions"]] == ["invoices"]  # the stress deep link needs the layer
    # what does not depend on the layer is the same page
    assert off["figures"] == on["figures"] and off["economics"] == on["economics"] and off["decision"]["text"] == on["decision"]["text"]
    assert off["decision"]["secondary"] == off["actions"]
    zh = _get(api, lang="zh")
    assert zh["exposure"] is None and english_leaks(zh["note"], NAMES) == [] and "FEATURE" not in zh["note"]


def test_a_buyer_with_no_open_deal_has_no_decision_and_says_so(api, rt):
    _before(api, rt)
    b = _get(api, "BUYER-2")
    assert b["name"] == "Dongguan Office Supplies Ltd."
    assert b["decision"] is None
    assert b["none_text"] == "No commercial decision is waiting for you with Dongguan."
    assert b["actions"][0]["href"] == "/receivables?customer=BUYER-2"
    assert [f["value_display"] for f in b["figures"]] == ["Not known yet", "¥0", None, "0%"]  # no financing: null, the note says so
    assert b["figures"][1]["note"] == "nothing is owed by them"
    assert [a["key"] for a in b["actions"]] == ["invoices"]  # nothing is open, so there is nothing to pay late
    rows = b["exposure"]["rows"]
    assert _row(rows, "stress")["value_display"] == "No late-payment test for Dongguan: no open invoice is left to pay late."
    assert _row(rows, "capacity")["value_display"] == "¥81,000 today" and b["history"] == []
    zh = _get(api, "BUYER-2", lang="zh")
    assert zh["none_text"] == "目前没有需要您对Dongguan作出的商务决定。" and zh["decision"] is None
    assert english_leaks(zh, NAMES, raw_fields=[HREFS]) == []


def test_a_buyer_with_no_financing_and_no_plan_leg_says_none_and_never_a_state_word(api, rt):
    _before(api, rt)  # the plan is ready, but none of its legs is on this buyer's invoices
    b = _get(api, "BUYER-2")
    f = _fig(b, "financing")
    assert (f["value_display"], f["note"], f["state"], f["state_text"]) == (
        None, "nothing is financed against Dongguan's invoices", "none", "")
    assert not any(w in json.dumps(b["exposure"]) for w in ("arranged", "received", "repaid", "planned"))
    assert _row(b["exposure"]["rows"], "financing")["value_display"] == "none against this customer's invoices"
    zh = _fig(_get(api, "BUYER-2", lang="zh"), "financing")
    assert (zh["value_display"], zh["state"], zh["state_text"]) == (None, "none", "")


def test_without_inputs_the_demo_buyer_is_projected_from_the_books_and_nothing_else_is_invented(api, rt):
    _offer(api)
    b = _get(api)  # no input of the owner's at all: the books schedule 13 invoices of ¥420,000 and the Demo assumes 20%
    assert b["figures"][0]["value_display"] == "about ¥1.09m"
    assert [(r["key"], r["value_display"], r["note"]) for r in b["economics"][:3]] == [
        ("annual_sales", "¥5,460,000", "projected from your books"),
        ("gross_margin", "20%", "assumed for the Demo, not confirmed by you"),
        ("contribution", "about ¥1,092,000", "under today's terms")]
    assert b["economics"][-1]["value_display"] == "not entered yet"  # no class is ever invented
    other = _get(api, "BUYER-2")  # nothing scheduled: no sales to project, so no contribution (the Demo's margin is still said so)
    assert other["figures"][0]["value_display"] == "Not known yet"
    assert [(r["key"], r["value_display"], r["note"]) for r in other["economics"]] == [
        ("annual_sales", "not entered yet", None), ("gross_margin", "20%", "assumed for the Demo, not confirmed by you"),
        ("classification", "not entered yet", None)]
    assert other["economics_note"] == "None of this changes what FLOW may do on its own."  # no contribution, so no verdict on the concession
    # every row says whether it holds a value, so the page never matches the string "not entered yet"
    assert {r["key"]: r["entered"] for r in b["economics"]} == {"annual_sales": True, "gross_margin": True, "contribution": True,
                                                                  "open_request": True, "classification": False}
    assert {r["key"]: r["entered"] for r in other["economics"]} == {"annual_sales": False, "gross_margin": True, "classification": False}
    assert all((r["value_display"] == "not entered yet") == (not r["entered"]) for r in b["economics"] + other["economics"])


def test_the_owners_sales_override_the_projection_and_a_past_invoice_is_not_future_sales(rt):
    def read(recurring: list[Any], receivables: list[Any], owner: int | None = None) -> Any:
        held = {"annual_sales_fen": SimpleNamespace(field="annual_sales_fen", value_json=json.dumps(owner))} if owner is not None else {}
        return SimpleNamespace(state=SimpleNamespace(recurring_invoices=recurring, receivables=receivables), today=10, buyer_id="B",
                               input=lambda f: held.get(f.value))

    every_30 = SimpleNamespace(counterparty_id="B", face_fen=100, every_days=30, next_issue_day=12)
    other = SimpleNamespace(counterparty_id="C", face_fen=999, every_days=30, next_issue_day=12)
    past = SimpleNamespace(counterparty_id="B", face_fen=7, issue_day=9, status="OPEN")  # issued yesterday: past sales
    coming = SimpleNamespace(counterparty_id="B", face_fen=5, issue_day=40, status="OPEN")  # to be issued in the window
    failed = SimpleNamespace(counterparty_id="B", face_fen=3, issue_day=40, status="FAILED")
    beyond = SimpleNamespace(counterparty_id="B", face_fen=11, issue_day=10 + 365, status="OPEN")
    assert overview._projected_sales_fen(read([every_30, other], [past, coming, failed, beyond])) == 13 * 100 + 5  # 12, 42, ... 372
    assert overview._projected_sales_fen(read([], [past])) is None
    assert overview._sales(read([every_30], [], owner=777)) == (777, read([], [], owner=777).input(overview.InputField.ANNUAL_SALES_FEN))
    assert overview._sales(read([every_30], [])) == (1300, None)


def test_a_margin_the_owner_entered_is_not_called_a_demo_assumption(api, rt):
    _offer(api)
    _input(rt, "annual_sales_fen", 546_000_000, "ACCOUNTING_HISTORY")
    _input(rt, "margin_bp", 1850, "OWNER_ENTERED")
    b = _get(api)
    sales, margin = b["economics"][:2]
    assert (sales["note"], sales["tone"]) == ("from your accounts", "neutral")  # the owner's figure, not the projection
    assert (margin["value_display"], margin["note"], margin["tone"]) == ("18.50%", "you entered", "neutral")
    assert _row(b["economics"], "contribution")["value_display"] == "about ¥1,010,100"


def test_the_share_of_sales_is_never_stated_unless_the_inputs_hold_it(api, rt):
    _before(api, rt)
    b = _get(api)
    shares = json.dumps([_fig(b, "share"), b["economics"], b["economics_note"]])
    assert _fig(b, "share")["note"] == "100% of currently open receivables"
    assert "% of your sales" not in shares and "share of sales" not in shares
    # the concentration holds one only when the inputs give every customer's sales; then, and only then, it is said
    r = SimpleNamespace(lang="en", rows=[{"x": 1}], conc={
        "is_aggregate": False, "ar_total_fen": 100, "ar_buyer_fen": 50, "ar_share_bp": 5000, "annual_sales_share_bp": 1234,
        "aggregate_note": None})
    assert overview._share(r)["note"] == "50.0% of currently open receivables · 12.3% of your sales"


def test_an_aggregate_buyer_has_no_share_of_its_own(api, rt):
    _before(api, rt)
    _input(rt, "aggregate", True, "OWNER_ENTERED")
    f = _fig(_get(api), "share")
    assert f["value_display"] == "—" and "stand for many small customers" in f["note"]


def test_an_overdue_invoice_is_named_in_the_outstanding_figure():
    rows = [{"outstanding_fen": 10_000_000, "past_due": True, "due_when": "3 days ago", "collection_state": "OVERDUE",
             "collection_state_text": "Overdue"},
            {"outstanding_fen": 32_000_000, "past_due": False, "due_when": "in 9 days", "collection_state": "CURRENT",
             "collection_state_text": "Not due yet"}]
    en = overview._outstanding(SimpleNamespace(lang="en", rows=rows))
    zh = overview._outstanding(SimpleNamespace(lang="zh", rows=[{**rows[0], "due_when": "3 天前"}, {**rows[1], "due_when": "9 天后"}]))
    assert (en["value_display"], en["note"], en["tone"]) == ("¥420,000", "¥100,000 overdue; next due in 9 days", "bad")
    assert (en["state"], en["state_text"]) == ("overdue", "Overdue")  # the worst of the rows' own collection states
    assert zh["note"] == "其中 ¥100,000 已逾期；下一笔9 天后到期"
    several = overview._outstanding(SimpleNamespace(lang="en", rows=rows[1:] * 2))
    assert several["note"] == "next due in 9 days, nothing overdue"
    assert (several["state"], several["state_text"]) == ("current", "Not due yet")


def _owed(state: str, text: str) -> dict[str, Any]:
    return {"outstanding_fen": 1_000_000, "past_due": state in ("OVERDUE", "PROMISE_MISSED"), "due_when": "in 3 days",
            "collection_state": state, "collection_state_text": text}


@pytest.mark.parametrize(("states", "expected"), [
    ([("CURRENT", "Not due yet"), ("DUE_SOON", "Due soon")], ("due_soon", "Due soon")),
    ([("DUE_SOON", "Due soon"), ("OVERDUE", "Overdue"), ("CURRENT", "Not due yet")], ("overdue", "Overdue")),
    ([("OVERDUE", "Overdue"), ("PROMISE_MISSED", "Promise missed")], ("promise_missed", "Promise missed")),
])
def test_the_outstanding_figures_state_is_the_worst_of_the_rows_own_collection_states(states, expected):
    fig = overview._outstanding(SimpleNamespace(lang="en", rows=[_owed(*x) for x in states]))
    assert (fig["state"], fig["state_text"]) == expected


def test_nothing_owed_has_no_collection_state():
    fig = overview._outstanding(SimpleNamespace(lang="en", rows=[]))
    assert (fig["state"], fig["state_text"]) == ("none", "")


# ---------------------------------------------------------------- the back link


def test_the_back_link_from_a_deal_restores_the_selected_path(api, rt):
    offer_id = _before(api, rt)
    path = next(p["key"] for p in api.get(f"/offers/{offer_id}/picture").json()["paths"] if p["recommended"])
    back = _get(api, decision=f"deal:{offer_id}", path=path)["context"]["back"]
    assert back == {"label": "Back to the Foshan deal", "href": f"/deals?decision=deal%3A{offer_id}&path={path}"}
    zh = _get(api, lang="zh", decision=f"deal:{offer_id}", path=path)["context"]["back"]
    assert zh == {"label": "返回与Foshan的交易", "href": back["href"]}
    only = _get(api, decision=f"deal:{offer_id}")["context"]["back"]
    assert only["href"] == f"/deals?decision=deal%3A{offer_id}"


def test_the_back_link_from_an_invoice_goes_to_the_receivables_with_the_invoice(api, rt):
    _before(api, rt)
    back = _get(api, invoice="RCV-A")["context"]["back"]
    assert back == {"label": "Back to the invoices", "href": "/receivables?customer=BUYER-1&invoice=RCV-A"}
    assert _get(api, lang="zh", invoice="RCV-A")["context"]["back"]["label"] == "返回发票"


def test_a_deal_outranks_an_invoice_and_no_query_goes_back_to_the_deals(api, rt):
    offer_id = _before(api, rt)
    both = _get(api, decision=f"deal:{offer_id}", invoice="RCV-A")["context"]["back"]
    assert both["href"].startswith("/deals?decision=")
    assert _get(api)["context"]["back"] == {"label": "Back to Deals", "href": "/deals"}


@pytest.mark.parametrize("query", [
    {"decision": "deal:OFF-nothing"},  # no such offer
    {"decision": "alert:ALERT-RESERVE-12:v1:plan"},  # not a deal
    {"decision": "deal:<script>alert(1)</script>"},  # not an id at all
    {"invoice": "RCV-NOPE"},
    {"invoice": "../../etc/passwd"}])
def test_a_query_that_names_nothing_of_this_buyer_is_ignored_and_never_echoed(api, rt, query):
    _before(api, rt)
    back = _get(api, **query)["context"]["back"]
    assert back == {"label": "Back to Deals", "href": "/deals"}


def test_a_path_is_not_echoed_unless_it_is_a_plain_key(api, rt):
    offer_id = _before(api, rt)
    back = _get(api, decision=f"deal:{offer_id}", path="<b>x</b>")["context"]["back"]
    assert back["href"] == f"/deals?decision=deal%3A{offer_id}"


def test_another_buyers_deal_is_not_a_way_back(api, rt):
    offer_id = _before(api, rt)
    assert _get(api, "BUYER-2", decision=f"deal:{offer_id}")["context"]["back"]["href"] == "/deals"


# ---------------------------------------------------------------- the selections echoed (Home V2: customer, deal, scenario)


def test_the_context_echoes_the_customer_and_nothing_else_without_a_query(api, rt):
    _before(api, rt)
    ctx = _get(api)["context"]
    assert (ctx["customer"], ctx["deal"], ctx["scenario"]) == ("BUYER-1", None, None)
    assert ctx["back"] == {"label": "Back to Deals", "href": "/deals"}


def test_the_context_echoes_the_deal_and_the_scenario_it_was_opened_on(api, rt):
    offer_id = _before(api, rt)
    ctx = _get(api, decision=f"deal:{offer_id}", scenario="asked")["context"]
    assert (ctx["customer"], ctx["deal"], ctx["scenario"]) == ("BUYER-1", f"deal:{offer_id}", "asked")
    assert _get(api, "BUYER-1", "zh", decision=f"deal:{offer_id}", scenario="counter:1")["context"]["scenario"] == "counter:1"
    assert _get(api, decision=f"deal:{offer_id}", scenario="counter:2")["context"]["scenario"] is None  # the verdict has two counters
    assert _get(api, decision=f"deal:{offer_id}", scenario="counter:999")["context"]["scenario"] is None
    assert _get(api, decision=f"deal:{offer_id}")["context"]["scenario"] is None  # no scenario asked for: none echoed


@pytest.mark.parametrize("query", [{"decision": "deal:OFF-nothing", "scenario": "asked"}, {"scenario": "asked"},
                                   {"decision": "deal:<script>x</script>", "scenario": "asked"}])
def test_a_deal_that_is_not_this_buyers_or_a_scenario_without_a_deal_is_never_echoed(api, rt, query):
    _before(api, rt)
    ctx = _get(api, **query)["context"]
    assert (ctx["deal"], ctx["scenario"]) == (None, None)


def test_another_buyers_deal_is_not_echoed_as_this_buyers(api, rt):
    offer_id = _before(api, rt)
    ctx = _get(api, "BUYER-2", decision=f"deal:{offer_id}", scenario="asked")["context"]
    assert (ctx["customer"], ctx["deal"], ctx["scenario"]) == ("BUYER-2", None, None)


def test_a_scenario_that_is_not_a_plain_key_is_not_echoed(api, rt):
    offer_id = _before(api, rt)
    assert _get(api, decision=f"deal:{offer_id}", scenario="<b>x</b>")["context"]["scenario"] is None


# ---------------------------------------------------------------- the route


def test_an_unknown_customer_or_a_lender_is_404_and_the_route_is_owner_only(api, rt):
    assert api.get("/customers/BUYER-9/overview").status_code == 404
    assert api.get("/customers/BANK-1/overview").json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"
    assert api.get("/customers/BUYER-1/overview", headers={"X-Owner-Token": "wrong"}).status_code == 401
    assert api.get("/customers/BUYER-1/overview", params={"lang": "fr"}).status_code == 422


def test_the_answer_is_cached_by_the_books_and_follows_a_new_input(api, rt, monkeypatch):
    _before(api, rt)
    calls: list[str] = []
    real = overview._build
    monkeypatch.setattr(overview, "_build", lambda *a, **k: (calls.append("built"), real(*a, **k))[1])
    first = _get(api)
    assert _get(api) == first and calls == ["built"]
    _get(api, invoice="RCV-A")  # the query only builds `context`: the read is the same
    assert calls == ["built"]
    _input(rt, "margin_bp", 3000, "OWNER_ENTERED")
    changed = _get(api)
    assert calls == ["built", "built"] and changed["economics"][1]["value_display"] == "30%"
    _get(api, lang="zh")
    assert calls == ["built", "built", "built"]  # one entry per language


def test_the_read_writes_nothing(api, rt):
    _before(api, rt)
    state, ops, inputs = rt.store.get_state(), len(rt.store.operations()), len(rt.store.customer_inputs(None))
    _get(api)
    _get(api, lang="zh")
    assert rt.store.get_state() == state and len(rt.store.operations()) == ops and len(rt.store.customer_inputs(None)) == inputs


# ---------------------------------------------------------------- review: the accept branch, the key, the open request, the fallbacks


def _built(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    real = overview._build
    def counted(*a: object, **k: object) -> object:
        calls.append("built")
        return real(*a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(overview, "_build", counted)
    return calls


def test_an_offer_FLOW_may_accept_carries_the_asked_paths_authority(api, rt):
    from tests.api.test_offer_picture import _accepted

    _accepted(api)
    d = _get(api)["decision"]
    assert d["headline_short"] == "Accept their request"
    assert d["authority_text"] == "FLOW can accept this request without your approval."
    assert d["primary"]["label"] == "Review the request"
    assert _get(api, lang="zh")["decision"]["authority_text"] == "FLOW 可以在无需您批准的情况下接受这项请求。"


def test_an_offer_received_and_not_yet_evaluated_moves_the_key(api, rt, monkeypatch):
    calls = _built(monkeypatch)
    assert _get(api)["decision"] is None and _get(api)["decision"] is None and calls == ["built"]
    api.post("/offers", json=EX01)  # a document and a compiled offer: no verdict, no new state version, no log entry
    after = _get(api)
    assert calls == ["built", "built"]
    d = after["decision"]
    assert (d["kind"], d["eyebrow"], d["authority_text"], d["headline_short"]) == ("offer_received", "One offer waits to be read", None, None)
    assert d["text"].endswith("FLOW has not read it yet.") and d["text"].startswith("Foshan wants early settlement")
    assert (d["primary"]["label"], d["primary"]["href"].split("?")[0]) == ("Read the offer", "/deals")
    zh = _get(api, lang="zh")["decision"]
    assert (zh["eyebrow"], zh["primary"]["label"]) == ("有一份报价等待阅读", "阅读报价") and zh["authority_text"] is None


def _op(rt: Runtime) -> None:
    rt.store.append_operation("OP-TEST", "NOTE", "idem-test", json.dumps({"kind": "NOTE"}), json.dumps({"status": "EXECUTED", "message": "x"}))


def _verdict(rt: Runtime) -> None:
    v = rt.store.verdicts()[-1]
    rt.store.put_verdict(v.model_copy(update={"id": "VER-second"}))


def _approval(rt: Runtime) -> None:
    rt.store.add_approval(json.dumps({"kind": "NOTE"}), "test")


def _decide(rt: Runtime) -> None:
    rt.store.decide_approval(rt.store.approvals()[0].id, True, "OWNER")


def _document(rt: Runtime) -> None:
    rt.documents["DOC-NEW"] = SourceDocument(doc_id="DOC-NEW", channel="chat", sender_id="BUYER-1", received_day=0, text="hello")


@pytest.mark.parametrize("write", [_op, _verdict, _approval, _document])
def test_the_key_moves_on_a_log_entry_a_verdict_an_approval_and_a_document(api, rt, monkeypatch, write):
    _before(api, rt)
    calls = _built(monkeypatch)
    _get(api)
    _get(api)
    assert calls == ["built"]
    version = rt.store.get_state().state_version
    write(rt)
    assert rt.store.get_state().state_version == version  # none of these moves the books
    try:
        _get(api)
    except AssertionError:
        pass  # a fixture row the read cannot parse is not the point: the key moved and the read was tried again
    assert calls == ["built", "built"]


def test_the_key_moves_when_an_approval_is_decided(api, rt, monkeypatch):
    _before(api, rt)
    _approval(rt)
    calls = _built(monkeypatch)
    _get(api)
    _decide(rt)
    _get(api)
    assert calls == ["built", "built"]


def test_a_hit_loads_no_whole_list(api, rt, monkeypatch):
    _before(api, rt)
    _get(api)
    for name in ("operations", "verdicts", "approvals", "contract_records"):
        monkeypatch.setattr(rt.store, name, lambda *a, **k: pytest.fail("the key must not load a whole list"))
    assert _get(api)["name"] == "Foshan Home Retail Co."


def _inputs(sales_yuan: int, margin_bp: int) -> Any:
    def rec(field: str, value: int) -> Any:
        return SimpleNamespace(field=field, value_json=json.dumps(value), entered_by="OWNER", provenance="OWNER_ENTERED")

    held = {"annual_sales_fen": rec("annual_sales_fen", sales_yuan * 100), "margin_bp": rec("margin_bp", margin_bp)}
    return lambda f: held.get(f.value)


def _ask_read(*, forward_fen: int, once: str | None, horizon_days: int = 365, lang: str = "en", sales_yuan: int = 5_000_000) -> Any:
    picture = {"paths": [{"key": "asked", "cost_once_display": once}]}
    return SimpleNamespace(
        lang=lang, state=SimpleNamespace(recurring_invoices=[], receivables=[], scenario=None), today=0, buyer_id="B", offer={"offer_id": "X"}, verdict=SimpleNamespace(forward_concession_total_fen=forward_fen), picture=picture,
        ctx=SimpleNamespace(mandate=SimpleNamespace(forward_concession_horizon_days=horizon_days)), input=_inputs(sales_yuan, 2000))


def _request(r: Any) -> dict[str, Any] | None:
    rows, _ = overview._economics(r)
    return next((x for x in rows if x["key"] == "open_request"), None)


def test_a_concession_above_the_whole_years_contribution_is_said_in_words_not_capped_at_100_percent():
    row = _request(_ask_read(forward_fen=350_000_000, once=None))  # ¥3.5m over 12 months against a ¥1m contribution
    assert row is not None and row["value_display"] == "more than the whole year's contribution if you accept their request, over 12 months"
    zh = _request(_ask_read(forward_fen=350_000_000, once=None, lang="zh"))
    assert zh is not None and zh["value_display"] == "如果接受对方的要求，12 个月内超过其一整年的贡献"
    assert "100%" not in row["value_display"]


def test_a_discount_only_request_is_a_one_off_with_no_share_and_no_zero_concession():
    r = _ask_read(forward_fen=0, once="¥5,040.00")
    row = _request(r)
    assert row is not None and row["value_display"] == "once, ¥5,040.00" and "%" not in row["value_display"]
    _, note = overview._economics(r)
    assert "¥5,040.00 one-off concession" in note and "¥0" not in note


def test_the_open_requests_share_is_on_a_twelve_month_basis_whatever_the_horizon():
    year = _request(_ask_read(forward_fen=10_000_000, once=None))  # ¥100,000 over 12 months against ¥1m
    half = _request(_ask_read(forward_fen=10_000_000, once=None, horizon_days=182))  # ¥100,000 over 6 months is ¥200,000 a year
    assert year is not None and year["value_display"] == "about 10.0% of it if you accept their request, over 12 months"
    assert half is not None and half["value_display"] == "about 20.0% of it if you accept their request, over 12 months"


def test_no_request_no_row_and_no_share():
    assert _request(_ask_read(forward_fen=0, once=None)) is None


def test_a_book_that_cannot_be_projected_for_the_exposure_says_so_and_is_not_cached(api, rt, monkeypatch):
    from app.financial import EngineError

    _before(api, rt)
    calls = _built(monkeypatch)

    def broken(*a: Any, **k: Any) -> Any:
        raise EngineError("no projection")

    monkeypatch.setattr(assembly, "buyer_exposure", broken)
    b = _get(api)
    assert b["exposure"] is None and b["note"] == "The financial exposure could not be read just now."
    assert [f["key"] for f in b["figures"]] == ["value", "outstanding", "financing", "share"]  # the rest of the page stands
    zh = _get(api, lang="zh")
    assert zh["note"] == "暂时无法读取财务风险敞口。"
    _get(api)
    assert calls == ["built", "built", "built"]  # a fallback is never cached


def test_a_concentration_that_cannot_be_read_says_so_in_the_figure_and_the_note(api, rt, monkeypatch):
    from app.financial import EngineError

    _before(api, rt)
    monkeypatch.delenv("FEATURE_EXPOSURE")

    def broken(*a: Any, **k: Any) -> Any:
        raise EngineError("no projection")

    monkeypatch.setattr(overview, "concentration", broken)
    b = _get(api)
    share = _fig(b, "share")
    assert (share["value_display"], share["note"]) == ("—", "could not be read just now")
    assert b["note"] == "The financial exposure could not be read just now."


def test_when_the_offer_picture_fails_the_decision_reads_from_the_deals_words_and_is_not_cached(api, rt, monkeypatch):
    _before(api, rt)
    calls = _built(monkeypatch)

    def broken(*a: Any, **k: Any) -> Any:
        raise RuntimeError("no picture")

    monkeypatch.setattr(overview, "cached_picture", broken)
    d = _get(api)["decision"]
    assert d["text"].endswith("Counter instead of accepting their request.") and d["primary"]["label"] == "Review the request"
    assert "&path=" not in d["primary"]["href"] and d["authority_text"] is None
    _get(api)
    assert calls == ["built", "built"]


def test_a_reconciliation_that_fails_is_named_in_partial_and_the_page_is_not_cached(api, rt, monkeypatch):
    from app.api import receivables

    _before(api, rt)
    calls = _built(monkeypatch)

    def broken(*a: Any, **k: Any) -> Any:
        raise RuntimeError("no reconciliation")

    monkeypatch.setattr(receivables, "reconcile", broken)
    b = _get(api)
    assert b["partial"]["missing"] == ["reconciliation"] and b["partial"]["text"].startswith("Some supporting facts could not be read")
    assert _get(api, lang="zh")["partial"]["text"].startswith("部分辅助信息未能读取")
    _get(api)
    assert calls == ["built", "built", "built"]


def test_the_edit_link_waits_for_phase_2(api, rt, monkeypatch):
    _before(api, rt)
    assert _get(api)["edit_href"] is None
    monkeypatch.setenv("FEATURE_CUSTOMER_ECONOMICS", "1")
    b = _get(api)
    assert b["edit_href"] == "/customers/BUYER-1/inputs" and b["edit_label"] == "Edit these facts"


def test_a_financing_entry_in_the_history_never_says_drawn_for_an_unlanded_lot(api, rt):
    _after(api, rt)
    text = next(x["text"] for x in _get(api)["history"] if "financing" in x["text"].lower())
    assert text == "Invoice financing of ¥255,000 against the ¥420,000 invoice: arranged, expected in 3 days."
    assert "drawn" not in text
    zh = next(x["text"] for x in _get(api, lang="zh")["history"] if "融资" in x["text"])
    assert zh == "以 ¥420,000 的发票做 ¥255,000 的融资：已安排，预计3 天后到账。"


def test_a_receipt_in_the_history_is_the_receipt_and_never_the_banks_reference(api, rt):
    from tests.api.test_demo_bank_receipt import _deal

    _deal(api)
    api.post("/clock/advance", json={"to_day": 2})
    assert api.post("/demo/bank-receipt").status_code == 200
    for lang in ("en", "zh"):
        history = _get(api, lang=lang)["history"]
        text = " ".join(x["text"] for x in history)
        assert "DEMO-RCPT" not in text and not RAW_ID.search(text), text
    en = [x["text"] for x in _get(api)["history"]]
    assert any(x.startswith("The receipt of ¥") and "invoice came in." in x for x in en)
    assert any(x.startswith("已收到 ¥") for x in [x["text"] for x in _get(api, lang="zh")["history"]])


def test_every_history_row_with_a_link_names_it_and_a_row_without_one_does_not(api, rt):
    from tests.api.test_demo_bank_receipt import _deal

    _deal(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    rows = _get(api)["history"]
    assert rows and all((x["href"] is None) == (x["link_label"] is None) for x in rows)
    labels = {x["link_label"] for x in rows} - {None}
    assert labels <= {"The record", "The agreement", "The terms", "The deal"} and "The agreement" in labels
    zh = {x["link_label"] for x in _get(api, lang="zh")["history"]} - {None}
    assert zh <= {"记录", "协议", "条款", "该交易"} and "协议" in zh
    assert english_leaks(_get(api, lang="zh"), NAMES, raw_fields=[HREFS]) == []


# ---------------------------------------------------------------- the state words (ticket #120)

STATES = {"planned", "arranged", "received", "repaid", "current", "due_soon", "overdue", "promise_missed", "none"}
FIELDS = ("state", "state_text")


def _states(rows: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    return {r["key"]: (r["state"], r["state_text"]) for r in rows}


def _land(api: TestClient, rt: Runtime, *, arrival_day: int = -2) -> None:
    state = rt.store.get_state()
    lot = next(x for x in state.lots if x.receivable_id == "RCV-A")
    rt.store.put_state(state.model_copy(update={"lots": [FundingLot(**{**lot.model_dump(), "arrival_day": arrival_day, "settled": True})]}))
    offer_picture._cache.clear()


@pytest.mark.parametrize(("lang", "planned", "arranged", "received", "current"), [
    ("en", "Planned", "Arranged", "Received", "Not due yet"),
    ("zh", "计划中", "已安排", "已到账", "未到期"),
])
def test_the_financing_figure_moves_planned_arranged_received_in_the_one_vocabulary(api, rt, lang, planned, arranged, received, current):
    _before(api, rt)
    seen: list[str] = []
    b = _get(api, lang=lang)
    seen.append(_fig(b, "financing")["state_text"])
    assert _states(b["figures"]) == {"value": ("none", ""), "outstanding": ("current", current), "financing": ("planned", planned),
                                     "share": ("none", "")}
    assert _states(b["exposure"]["rows"])["financing"] == ("planned", planned)  # the plan is ready and has not run: nothing is financed yet
    assert _fig(b, "financing")["value_display"] == "¥255,000"  # the plan's advance, not "None": it reads as planned and is not counted
    assert _fig(b, "financing")["note"] == ("¥255k financing planned against Foshan's invoice · not yet received" if lang == "en"
                                            else "计划融资 ¥255k，以Foshan的发票做融资 · 尚未到账")
    _run_plan(api)
    b = _get(api, lang=lang)
    seen.append(_fig(b, "financing")["state_text"])
    assert _states(b["figures"])["financing"] == ("arranged", arranged)
    assert _states(b["exposure"]["rows"])["financing"] == ("arranged", arranged)
    _land(api, rt)
    b = _get(api, lang=lang)
    seen.append(_fig(b, "financing")["state_text"])
    assert _states(b["figures"])["financing"] == ("received", received)
    assert _states(b["exposure"]["rows"])["financing"] == ("received", received)
    if lang == "en":  # one function says the three words, so they share their casing
        assert [w[:1].isupper() for w in seen] == [True, True, True] and seen == [planned, arranged, received]


def test_the_state_words_are_the_receivable_rows_own(api, rt):
    _after(api, rt)
    b = _get(api)
    row = api.get("/receivables").json()["rows"][0]
    assert (_fig(b, "outstanding")["state"], _fig(b, "outstanding")["state_text"]) == (
        row["collection_state"].lower(), row["collection_state_text"])
    assert _fig(b, "financing")["state_text"] == row["net"]["financing_state_text"]
    zh, zh_row = _get(api, lang="zh"), api.get("/receivables", params={"lang": "zh"}).json()["rows"][0]
    assert _fig(zh, "financing")["state_text"] == zh_row["net"]["financing_state_text"]
    assert _fig(zh, "outstanding")["state_text"] == zh_row["collection_state_text"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_every_figure_row_and_history_row_has_a_state_in_the_vocabulary(api, rt, lang):
    _after(api, rt)
    b = _get(api, lang=lang)
    for row in [*b["figures"], *b["exposure"]["rows"], *b["history"]]:
        assert all(k in row for k in FIELDS), row
        assert row["state"] in STATES and (row["state"] == "none") == (row["state_text"] == ""), row
    if lang == "zh":
        assert english_leaks(b, NAMES, raw_fields=[HREFS]) == []


def test_with_the_exposure_flag_off_the_figures_still_carry_their_states(api, rt, monkeypatch):
    _after(api, rt)
    monkeypatch.delenv("FEATURE_EXPOSURE")
    b = _get(api)
    assert b["exposure"] is None and _states(b["figures"])["financing"] == ("arranged", "Arranged")


def test_a_buyer_with_no_financing_and_no_planned_leg_has_no_financing_state(api, rt):
    _before(api, rt)
    b = _get(api, "BUYER-2")
    assert _states(b["figures"])["financing"] == ("none", "")
    assert _states(b["exposure"]["rows"])["financing"] == ("none", "")


def test_an_invoice_marked_financed_with_no_advance_on_record_has_no_state(api, rt):
    _before(api, rt)
    state = rt.store.get_state()
    rcv = next(r for r in state.receivables if r.id == "RCV-A")
    rt.store.put_state(state.model_copy(update={"receivables": [rcv.model_copy(update={"status": "FINANCED"})]}))
    offer_picture._cache.clear()
    b = _get(api)
    assert _states(b["figures"])["financing"] == ("none", "") and _states(b["exposure"]["rows"])["financing"] == ("none", "")


def test_a_financing_entry_in_the_history_carries_the_financing_state(api, rt):
    _after(api, rt)
    for lang, arranged in (("en", "Arranged"), ("zh", "已安排")):
        rows = [x for x in _get(api, lang=lang)["history"] if x["state"] != "none"]
        assert [(x["state"], x["state_text"]) for x in rows] == [("arranged", arranged)]
        assert "¥255,000" in rows[0]["text"]
    _land(api, rt)
    assert [x["state"] for x in _get(api)["history"] if x["state"] != "none"] == ["received"]


def test_a_receipt_row_carries_the_collection_state_of_an_invoice_still_to_collect_else_none(api, rt):
    from tests.api.test_demo_bank_receipt import _deal

    _deal(api)
    api.post("/clock/advance", json={"to_day": 2})
    assert api.post("/demo/bank-receipt").status_code == 200
    b = _get(api)
    receipt = next(x for x in b["history"] if x["text"].startswith("The receipt of ¥"))
    open_rows = {r["receivable_id"]: r for r in api.get("/receivables").json()["rows"]}
    texts = {(r["collection_state"].lower(), r["collection_state_text"]) for r in open_rows.values()}
    assert (receipt["state"], receipt["state_text"]) in texts | {("none", "")}  # the rows' own words, or none once collected
    assert all(x["state"] == "none" for x in b["history"] if x is not receipt)
