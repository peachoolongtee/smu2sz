"""GET /customers/{id}/overview (map #88, ticket #108, the server half): the Customer overview read.

Golden day 0: the Foshan offer (60-day terms, a 1% rebate, early payment) is evaluated, and FLOW's plan (a ¥150k credit-line draw and
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
from app.domain.models import FundingLot
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
ID_KEYS = ("key", "customer_id", "lang")


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
    """The board's facts: ¥5.46m of sales projected from the books, a 20% margin the Demo assumed, a Normal customer."""
    _input(rt, "annual_sales_fen", 546_000_000, "PROJECTED", by="FLOW")
    _input(rt, "margin_bp", 2000, "ESTIMATED", by="DEMO")
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
    assert (value["label"], value["value_display"], value["note"]) == ("Relationship value", "about ¥1.09m", "a year, estimated contribution")
    assert (owed["value_display"], owed["note"], owed["tone"]) == ("¥420,000", "due in 32 days, nothing overdue", "neutral")
    assert (financing["label"], financing["value_display"], financing["note"]) == (
        "Financing linked", "None", "nothing is financed against Foshan's invoices")
    assert (share["value_display"], share["note"], share["tone"]) == (
        "100%", "one open invoice; not its share of your sales", "warn")
    d = b["decision"]
    assert d["eyebrow"] == "One commercial decision waits for you"
    assert d["text"] == ("Foshan wants early settlement of ¥420,000.00 at 1.20%, payment terms to 60 days and a 1.00% rebate. "
                         "FLOW recommends countering with Option A, ¥3,027.77 once if accepted.")
    assert (d["headline_short"], d["authority_text"]) == ("Counter instead of accepting as asked", "FLOW can send it")
    picture = api.get(f"/offers/{offer_id}/picture").json()
    recommended = next(p for p in picture["paths"] if p["recommended"])
    assert d["primary"] == {"label": "Review the counter",
                            "href": f"/deals?decision=deal%3A{offer_id}&path={recommended['key']}"}
    assert [(a["label"], a["href"]) for a in d["secondary"]] == [
        ("View the invoices", "/receivables?customer=BUYER-1&invoice=RCV-A"),
        ("Stress-test payment", "/cash?stress=BUYER-1:30&invoice=RCV-A")]
    assert d["secondary"] == b["actions"] and b["none_text"] is None
    assert [(r["key"], r["value_display"], r["note"], r["tone"]) for r in b["economics"]] == [
        ("annual_sales", "¥5,460,000", "projected from your books' schedule, not yet happened", "neutral"),
        ("gross_margin", "20%", "assumed for the Demo, not confirmed by you", "warn"),
        ("contribution", "about ¥1,092,000", "under today's terms", "neutral"),
        ("open_request", "about 2.6% of it as asked", "the cost of keeping the same sales on softer terms, not profit gained", "neutral"),
        ("classification", "Normal", "context only", "neutral")]
    assert b["economics_note"] == ("A customer worth ¥1.09m a year does not by itself justify a ¥28,330 concession; the question is how "
                                   "much of that is at risk if you counter. None of this changes what FLOW may do on its own.")
    assert (b["edit_label"], b["edit_href"]) == ("Edit these facts", "/inputs?customer=BUYER-1")
    assert b["note"] is None


def test_before_the_plan_the_exposure_rows_are_the_exposure_layers_own(api, rt):
    offer_id = _before(api, rt)
    b = _get(api)
    rows = b["exposure"]["rows"]
    assert [r["key"] for r in rows] == ["payments", "financing", "stress", "capacity"]  # no financing, so no "financing then"
    assert (rows[0]["value_display"], rows[0]["tone"]) == ("not enough history yet", "neutral")
    assert rows[1]["value_display"] == "none against this customer's invoices"
    assert (rows[2]["label"], rows[2]["value_display"], rows[2]["tone"]) == (
        "Paid 30 days late", "−¥250,000 in 60 days; 65 days below your minimum; ¥550,000 uncovered", "bad")
    assert (rows[3]["value_display"], rows[3]["note"]) == (
        "¥81,000 today; ¥0 if Foshan accepts Option A", "Option A leaves ¥0 of room for another payment for the next 31 days; today ¥81,000.")
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
    assert any("¥255,000.00" in x["text"] and x["href"] and x["href"].startswith("/decisions/") for x in b["history"])


def test_a_landed_advance_is_received_and_the_figure_keeps_its_one_state(api, rt):
    _after(api, rt)
    state = rt.store.get_state()
    lot = next(x for x in state.lots if x.receivable_id == "RCV-A")
    rt.store.put_state(state.model_copy(update={"lots": [FundingLot(**{**lot.model_dump(), "arrival_day": -2, "settled": True})]}))
    overview.clear_cache()
    offer_picture._cache.clear()
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
    assert [f["value_display"] for f in zh["figures"]] == ["约 ¥109 万", "¥420,000", "无", "100%"]
    assert zh["figures"][1]["note"] == "32 天后到期，没有逾期"
    assert zh["figures"][3]["note"] == "1 张未收发票；这不是其占您销售额的比例"
    assert zh["decision"]["eyebrow"] == "有一项商务决定等待您处理"
    assert zh["decision"]["primary"]["label"] == "查看还价" and zh["decision"]["authority_text"] == "FLOW 可以直接发送"
    assert "FLOW 建议以方案 A（如被接受，一次性成本 ¥3,027.77）还价" in zh["decision"]["text"]
    assert [r["value_display"] for r in zh["economics"][:3]] == ["¥5,460,000", "20%", "约 ¥1,092,000"]
    assert zh["economics"][1]["note"] == "为演示而假设，尚未经您确认"
    assert zh["economics"][4]["value_display"] == "普通"
    assert "您" in zh["economics_note"]
    stress = _row(zh["exposure"]["rows"], "stress")
    assert stress["label"] == "晚付 30 天" and stress["value_display"].startswith("60 天后降至 −¥250,000；有 65 天低于您的最低现金")
    assert zh["history"][1]["text"].startswith("尚无已确认的协议；账期为自开票日起 45 天")
    assert zh["context"]["back"]["label"] == "Back to Deals".replace("Back to Deals", "返回交易")


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
    overview.clear_cache()
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
    assert [f["value_display"] for f in b["figures"]] == ["Not known yet", "¥0", "None", "0%"]
    assert b["figures"][1]["note"] == "nothing is owed by them"
    assert [a["key"] for a in b["actions"]] == ["invoices"]  # nothing is open, so there is nothing to pay late
    rows = b["exposure"]["rows"]
    assert _row(rows, "stress")["value_display"] == "No late-payment test for Dongguan: no open invoice is left to pay late."
    assert _row(rows, "capacity")["value_display"] == "¥81,000 today" and b["history"] == []
    zh = _get(api, "BUYER-2", lang="zh")
    assert zh["none_text"] == "目前没有需要您对Dongguan作出的商务决定。" and zh["decision"] is None
    assert english_leaks(zh, NAMES, raw_fields=[HREFS]) == []


def test_a_buyer_with_no_financing_says_none_and_never_a_state_word(api, rt):
    _before(api, rt)
    b = _get(api)
    f = _fig(b, "financing")
    assert (f["value_display"], f["note"]) == ("None", "nothing is financed against Foshan's invoices")
    assert not any(w in json.dumps(b["exposure"]) for w in ("arranged", "received", "repaid"))
    assert _row(b["exposure"]["rows"], "financing")["value_display"] == "none against this customer's invoices"


def test_without_inputs_nothing_about_the_economics_is_invented(api, rt):
    _offer(api)
    b = _get(api)
    assert b["figures"][0]["value_display"] == "Not known yet"
    assert [(r["key"], r["value_display"], r["note"]) for r in b["economics"]] == [
        ("annual_sales", "not entered yet", None), ("gross_margin", "not entered yet", None), ("classification", "not entered yet", None)]
    assert b["economics_note"] == "None of this changes what FLOW may do on its own."  # no contribution, so no verdict on the concession


def test_a_margin_the_owner_entered_is_not_called_a_demo_assumption(api, rt):
    _offer(api)
    _input(rt, "annual_sales_fen", 546_000_000, "ACCOUNTING_HISTORY")
    _input(rt, "margin_bp", 1850, "OWNER_ENTERED")
    b = _get(api)
    sales, margin = b["economics"][:2]
    assert (sales["note"], sales["tone"]) == ("from your accounts", "neutral")
    assert (margin["value_display"], margin["note"], margin["tone"]) == ("18.50%", "entered by you", "neutral")
    assert _row(b["economics"], "contribution")["value_display"] == "about ¥1,010,100"


def test_the_share_of_sales_is_never_stated_unless_the_inputs_hold_it(api, rt):
    _before(api, rt)
    b = _get(api)
    shares = json.dumps([_fig(b, "share"), b["economics"], b["economics_note"]])
    assert "not its share of your sales" in _fig(b, "share")["note"]
    assert not re.search(r"of your sales(?!\")", _fig(b, "share")["note"].replace("not its share of your sales", ""))
    assert "% of your sales" not in shares and "share of sales" not in shares
    # the concentration holds one only when the inputs give every customer's sales; then, and only then, it is said
    r = SimpleNamespace(lang="en", rows=[{"x": 1}], conc=SimpleNamespace(
        is_aggregate=False, ar_total_fen=100, ar_buyer_fen=50, ar_share_bp=5000, annual_sales_share_bp=1234, aggregate_note=None))
    assert overview._share(r)["note"] == "one open invoice; 12.3% of your sales"


def test_an_aggregate_buyer_has_no_share_of_its_own(api, rt):
    _before(api, rt)
    _input(rt, "aggregate", True, "OWNER_ENTERED")
    f = _fig(_get(api), "share")
    assert f["value_display"] == "—" and "stand for many small customers" in f["note"]


def test_an_overdue_invoice_is_named_in_the_outstanding_figure():
    rows = [{"outstanding_fen": 10_000_000, "past_due": True, "due_when": "3 days ago"},
            {"outstanding_fen": 32_000_000, "past_due": False, "due_when": "in 9 days"}]
    en = overview._outstanding(SimpleNamespace(lang="en", rows=rows))
    zh = overview._outstanding(SimpleNamespace(lang="zh", rows=[{**rows[0], "due_when": "3 天前"}, {**rows[1], "due_when": "9 天后"}]))
    assert (en["value_display"], en["note"], en["tone"]) == ("¥420,000", "¥100,000 overdue; next due in 9 days", "bad")
    assert zh["note"] == "其中 ¥100,000 已逾期；下一笔9 天后到期"
    several = overview._outstanding(SimpleNamespace(lang="en", rows=rows[1:] * 2))
    assert several["note"] == "next due in 9 days, nothing overdue"


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
