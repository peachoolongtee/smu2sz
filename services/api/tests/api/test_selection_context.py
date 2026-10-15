"""The selection contract (map #121, ticket #126): every page read accepts `customer`, `decision`, `path`, `invoice`, `scenario` and `from` and
answers with `context` {customer, decision, path, invoice, scenario, back, irrelevant_text}. A key the page can honour is echoed; one it cannot
(an invoice of another customer, an unknown decision, a decision that is not the page's) is echoed as null with a sentence that asks the question,
never substituted. On the Demo and on the busy company, in both languages."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks

pytestmark = pytest.mark.usefixtures("fast_busy")  # the busy seed is replayed once per process (tests/api/busy_snapshot.py)

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
KEYS = {"customer", "decision", "path", "invoice", "scenario", "back", "irrelevant_text"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai"]


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()
    yield runtime
    set_runtime(None)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _offer(api: TestClient) -> str:
    offer_id = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    assert api.post(f"/offers/{offer_id}/evaluate", json=EX01).status_code == 200
    return offer_id


def _reads(offer_id: str) -> dict[str, str]:
    """The six page reads that carry a context, by name."""
    return {"deals": "/deals", "offer": f"/offers/{offer_id}", "picture": f"/offers/{offer_id}/picture",
            "overview": "/customers/BUYER-1/overview", "receivables": "/receivables", "decision": f"/decisions/deal:{offer_id}"}


def _ctx(api: TestClient, url: str, lang: str = "en", **query: str) -> dict[str, Any]:
    params = {"lang": lang, **{("from" if k == "origin" else k): v for k, v in query.items()}}
    r = api.get(url, params=params)
    assert r.status_code == 200, r.text
    ctx: dict[str, Any] = r.json()["context"]
    assert set(ctx) >= KEYS
    return ctx


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_every_page_read_carries_the_context_and_an_empty_query_selects_nothing_it_does_not_own(api: TestClient, lang: str) -> None:
    offer_id = _offer(api)
    for name, url in _reads(offer_id).items():
        ctx = _ctx(api, url, lang)
        assert ctx["irrelevant_text"] is None, name
        assert ctx["scenario"] is None and ctx["path"] is None and ctx["invoice"] is None, name
    # the pages about one record say which: the offer's, the picture's and the decision record's own deal and customer
    for name in ("offer", "picture", "decision"):
        ctx = _ctx(api, _reads(offer_id)[name], lang)
        assert (ctx["customer"], ctx["decision"]) == ("BUYER-1", f"deal:{offer_id}"), name
    assert _ctx(api, "/deals", lang)["customer"] is None and _ctx(api, "/deals", lang)["decision"] is None


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_honoured_selections_are_echoed_on_every_page(api: TestClient, lang: str) -> None:
    offer_id = _offer(api)
    path = next(p["key"] for p in api.get(f"/offers/{offer_id}/picture").json()["paths"] if p["recommended"])
    query = {"customer": "BUYER-1", "decision": f"deal:{offer_id}", "path": path, "invoice": "RCV-A", "scenario": "asked"}
    for name, url in _reads(offer_id).items():
        if name == "decision":  # a record page is about its own decision; the rest are echoed
            continue
        ctx = _ctx(api, url, lang, **query)
        assert ctx["irrelevant_text"] is None, name
        assert {k: ctx[k] for k in query} == query, name


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_invoice_of_another_customer_is_null_with_a_question_never_substituted(api: TestClient, lang: str) -> None:
    _offer(api)
    for url in ("/deals", "/receivables"):  # the Demo's one invoice is Foshan's: with Dongguan selected it is not Dongguan's
        ctx = _ctx(api, url, lang, customer="BUYER-2", invoice="RCV-A")
        assert (ctx["customer"], ctx["invoice"]) == ("BUYER-2", None), url
        assert ctx["irrelevant_text"] and "RCV" not in ctx["irrelevant_text"], url
    en = _ctx(api, "/receivables", "en", customer="BUYER-2", invoice="RCV-A")["irrelevant_text"]
    assert en == "The invoice you selected is not Dongguan's, so it has not been used. Which invoice?"
    zh = _ctx(api, "/receivables", "zh", customer="BUYER-2", invoice="RCV-A")["irrelevant_text"]
    assert zh == "您选择的发票不属于Dongguan，因此没有采用。您想看哪张发票？"
    assert not english_leaks({"t": zh}, NAMES)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_unknown_decision_or_invoice_or_customer_is_asked_about(api: TestClient, lang: str) -> None:
    offer_id = _offer(api)
    for name, url in _reads(offer_id).items():
        ctx = _ctx(api, url, lang, decision="deal:OFF-nothing", invoice="RCV-NOPE")
        assert ctx["invoice"] is None, name
        assert ctx["irrelevant_text"], name
        assert ctx["decision"] is None, name  # an offer's own pages do not swap in another negotiation; they ask which
    ctx = _ctx(api, "/deals", lang, customer="BUYER-9")
    assert ctx["customer"] is None and ctx["irrelevant_text"]
    en = _ctx(api, "/deals", "en", decision="deal:OFF-nothing")["irrelevant_text"]
    assert en == "FLOW cannot find the negotiation you selected, so it has not used it. Which negotiation?"
    zh = _ctx(api, "/deals", "zh", decision="deal:OFF-nothing")["irrelevant_text"]
    assert zh == "FLOW 找不到您选择的谈判，因此没有采用。您想看哪一项谈判？"


def test_a_decision_that_is_not_the_pages_is_not_substituted_for_it(api: TestClient) -> None:
    offer_id = _offer(api)
    other = str(api.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}).json()["offer"]["offer_id"])
    for url in (f"/offers/{offer_id}", f"/offers/{offer_id}/picture", f"/decisions/deal:{offer_id}"):
        ctx = _ctx(api, url, decision=f"deal:{other}")
        assert (ctx["customer"], ctx["decision"]) == ("BUYER-1", None)
        assert ctx["irrelevant_text"] == "The negotiation you selected is not the one on this page, so it has not been used. Which negotiation?"
    # and the deals queue holds both of one customer's negotiations as its own
    ctx = _ctx(api, "/deals", customer="BUYER-1", decision=f"deal:{other}")
    assert ctx["decision"] == f"deal:{other}" and ctx["irrelevant_text"] is None


def test_a_path_is_a_reply_of_the_decision_and_a_scenario_needs_its_decision(api: TestClient) -> None:
    offer_id = _offer(api)
    paths = [p["key"] for p in api.get(f"/offers/{offer_id}/picture").json()["paths"]]
    assert _ctx(api, "/deals", decision=f"deal:{offer_id}", path=paths[-1])["path"] == paths[-1]
    bad = _ctx(api, "/deals", decision=f"deal:{offer_id}", path="CTR-nothing")
    assert bad["path"] is None and "reply you selected" in bad["irrelevant_text"]
    no_decision = _ctx(api, "/deals", path="asked", scenario="asked")
    assert (no_decision["path"], no_decision["scenario"]) == (None, None)
    assert "reply you selected" in no_decision["irrelevant_text"] and "scenario you selected" in no_decision["irrelevant_text"]
    assert _ctx(api, "/deals", "zh", decision=f"deal:{offer_id}", scenario="counter:99")["irrelevant_text"] == "您选择的情景不属于这项谈判，因此没有采用。"


def test_the_way_back_follows_from_and_never_names_the_page_itself(api: TestClient) -> None:
    offer_id = _offer(api)
    deal = f"deal%3A{offer_id}"
    base = {"customer": "BUYER-1", "decision": f"deal:{offer_id}", "invoice": "RCV-A"}
    assert _ctx(api, "/receivables", origin="customer", **base)["back"] == {
        "label": "Back to Foshan", "href": f"/customers/BUYER-1?decision={deal}&invoice=RCV-A"}
    assert _ctx(api, "/receivables", "zh", origin="deal", **base)["back"] == {
        "label": "返回与Foshan的交易", "href": f"/deals?decision={deal}&customer=BUYER-1"}
    assert _ctx(api, "/offers/" + offer_id, origin="invoice", **base)["back"] == {
        "label": "Back to the invoice", "href": "/receivables?invoice=RCV-A&customer=BUYER-1"}
    assert _ctx(api, "/deals", origin="activity")["back"] == {"label": "Back to Activity", "href": "/activity"}
    assert _ctx(api, "/deals", "zh", origin="home")["back"] == {"label": "返回首页", "href": "/"}
    # the page itself is no way back, a target the selections do not support is none, and the page's own default stands in
    assert _ctx(api, f"/offers/{offer_id}", origin="deal", customer="BUYER-1")["back"]["href"].startswith("/customers/BUYER-1")
    assert _ctx(api, "/deals", origin="invoice")["back"] is None
    assert _ctx(api, "/deals", origin="nowhere")["back"] is None
    assert _ctx(api, "/customers/BUYER-1/overview", origin="customer")["back"] == {"label": "Back to Deals", "href": "/deals"}
    assert _ctx(api, "/customers/BUYER-1/overview", origin="cash")["back"] == {"label": "Back to Cash", "href": "/cash"}


def test_the_deals_pages_default_back_is_the_customer_and_another_customers_parts_are_dropped(api: TestClient) -> None:
    offer_id = _offer(api)
    back = _ctx(api, "/deals", customer="BUYER-1", decision=f"deal:{offer_id}", invoice="RCV-B1")["back"]
    assert back == {"label": "Back to Foshan", "href": f"/customers/BUYER-1?decision=deal%3A{offer_id}"}


def test_the_customer_overview_keeps_its_deal_alias_and_its_own_back(api: TestClient) -> None:
    offer_id = _offer(api)
    ctx = _ctx(api, "/customers/BUYER-1/overview", decision=f"deal:{offer_id}", scenario="asked")
    assert (ctx["customer"], ctx["decision"], ctx["deal"], ctx["scenario"]) == ("BUYER-1", f"deal:{offer_id}", f"deal:{offer_id}", "asked")
    other = _ctx(api, "/customers/BUYER-2/overview", decision=f"deal:{offer_id}", customer="BUYER-1")
    assert (other["customer"], other["decision"], other["deal"]) == ("BUYER-2", None, None)
    assert "This page is about Dongguan" in other["irrelevant_text"]


# ---------------------------------------------------------------- the busy company


def _busy(api: TestClient) -> dict[str, str]:
    r = api.post("/demo/reset", params={"scenario": "busy"})
    assert r.status_code == 200, r.text
    decisions = api.get("/decisions").json()["decisions"]
    foshan = next(d["id"] for d in decisions if d["state"] == "RESPONSE_READY" and (d["counterparty_name"] or "").startswith("Foshan"))
    return {"foshan": foshan, "foshan_offer": foshan.removeprefix("deal:"),
            "dongguan": next(d["id"] for d in decisions if (d["counterparty_name"] or "").startswith("Dongguan"))}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_busy_company_a_negotiation_of_another_customer_is_asked_about(api: TestClient, lang: str) -> None:
    ids = _busy(api)
    ctx = _ctx(api, "/deals", lang, customer="BUYER-1", decision=ids["dongguan"])
    assert ctx["decision"] is None and ctx["irrelevant_text"]
    assert (ctx["customer"], ctx["back"]["href"]) == ("BUYER-1", "/customers/BUYER-1")
    if lang == "zh":
        assert not english_leaks({"t": ctx["irrelevant_text"]}, NAMES)
    for name, url in {"offer": ids["foshan_offer"], "picture": ids["foshan_offer"] + "/picture"}.items():  # a page about Foshan's offer
        ctx = _ctx(api, "/offers/" + url, lang, invoice="RCV-B1")
        assert ctx["invoice"] is None and ctx["irrelevant_text"] and (ctx["customer"], ctx["decision"]) == ("BUYER-1", ids["foshan"]), name
    ok = _ctx(api, "/deals", lang, customer="BUYER-2", decision=ids["dongguan"], invoice="RCV-B1")
    assert (ok["decision"], ok["invoice"], ok["irrelevant_text"]) == (ids["dongguan"], "RCV-B1", None)
    mixed = _ctx(api, "/receivables", lang, invoice="RCV-B1", decision=ids["foshan"])  # the decision outranks the invoice: it names the customer
    assert (mixed["customer"], mixed["invoice"], mixed["decision"]) == ("BUYER-1", None, ids["foshan"])
    assert mixed["irrelevant_text"] and "RCV" not in mixed["irrelevant_text"]
