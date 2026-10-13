"""Ask FLOW's scope (map #121, ticket #130): `POST /nl` accepts `scope` {customer, invoice, decision, scenario} from the URL contract and uses it in
place of the stored prior-offer context; the response echoes `scope_used` {kind, label}; a scope the server cannot honour is answered with a
clarification sentence, never a guess. On the Demo and on the busy company, in both languages."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
EXPLAIN = "Why are we countering this?"
NO_VERDICT = "There is no verdict to explain yet. Evaluate an offer first."
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan"]


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    reset_sessions()
    for clear in (worklist.clear_cache, offer_picture._cache.clear):
        clear()
    yield runtime
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _ask(api: TestClient, session: str, text: str, lang: str = "en", **body: Any) -> dict[str, Any]:
    r = api.post("/nl", json={"session_id": session, "text": text, "lang": lang, **body})
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def _evaluated(api: TestClient) -> str:
    oid = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    api.post(f"/offers/{oid}/evaluate", json=EX01)
    return oid


def test_a_request_without_a_scope_is_answered_as_before_and_echoes_none(api: TestClient) -> None:
    oid = _evaluated(api)
    r = _ask(api, "s-bare", EXPLAIN, context={"page": "/deals", "offer_id": oid})
    assert r["scope_used"] is None and r["context_echo"]["offer_id"] == oid and r["reply"].startswith("About the Foshan")


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_scope_names_the_decision_and_replaces_the_pages_stale_offer(api: TestClient, lang: str) -> None:
    oid = _evaluated(api)
    r = _ask(api, "s-dec", EXPLAIN, lang, context={"page": "/deals", "offer_id": "OFF-stale"}, scope={"decision": f"deal:{oid}"})
    assert r["scope_used"] == {"kind": "decision", "label": {"en": "The negotiation with Foshan Home Retail Co.",
                                                           "zh": "与Foshan Home Retail Co.的谈判"}[lang]}
    assert r["context_echo"]["offer_id"] == oid and r["verdict"] is not None  # the scope's deal answers, not the stale id the page sent


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_company_scope_forgets_the_deal_the_page_last_pointed_at(api: TestClient, lang: str) -> None:
    oid = _evaluated(api)
    first = _ask(api, "s-forget", EXPLAIN, "en", context={"page": "/deals", "offer_id": oid})
    assert first["verdict"] is not None  # bound to the deal by the page
    r = _ask(api, "s-forget", EXPLAIN, lang, context={"page": "/customers", "offer_id": oid}, scope={})
    assert r["scope_used"] == {"kind": "company", "label": {"en": "Your whole company", "zh": "整个公司"}[lang]}
    assert r["verdict"] is None and r["context_echo"] is None
    if lang == "en":
        assert r["reply"] == NO_VERDICT


def test_a_customer_scope_and_an_invoice_scope_are_echoed_with_their_labels(api: TestClient) -> None:
    _evaluated(api)
    c = _ask(api, "s-cust", "How is cash?", scope={"customer": "BUYER-1"})
    assert c["scope_used"] == {"kind": "customer", "label": "Foshan Home Retail Co."} and c["context_echo"] is None
    i = _ask(api, "s-inv", "What happens if this payment is late?", scope={"invoice": "RCV-A", "customer": "BUYER-1"})
    assert i["scope_used"] == {"kind": "invoice", "label": "The invoice to Foshan Home Retail Co."}
    assert i["context_echo"]["invoice_id"] == "RCV-A"


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_scope_the_server_cannot_honour_is_a_clarification_never_a_guess(api: TestClient, lang: str) -> None:
    oid = _evaluated(api)
    _ask(api, "s-bad", EXPLAIN, "en", context={"page": "/deals", "offer_id": oid})  # a deal is bound; the bad scope must not fall back to it
    unknown = _ask(api, "s-bad", EXPLAIN, lang, scope={"decision": "deal:OFF-nothing"})
    assert unknown["intent"] == "AMBIGUOUS" and unknown["parse_source"] == "scope"
    assert unknown["scope_used"] is None and unknown["verdict"] is None and unknown["operations"] == []
    assert unknown["reply"] == {"en": "I cannot find the negotiation you selected, so I have not guessed. Which negotiation do you mean?",
                                "zh": "我找不到您选择的谈判，所以没有猜测。您指的是哪一项谈判？"}[lang]
    other = _ask(api, "s-bad2", "What happens if this payment is late?", lang, scope={"customer": "BUYER-2", "invoice": "RCV-A"})
    assert other["intent"] == "AMBIGUOUS" and other["scope_used"] is None
    assert other["reply"] == {"en": "The invoice you selected is not Dongguan's, so I cannot tell which one you mean. Tell me which customer or invoice to look at.",
                              "zh": "您选择的发票不属于Dongguan，我无法确定您指的是哪一个。请告诉我要看哪位客户或哪张发票。"}[lang]
    if lang == "zh":
        assert not english_leaks({"a": unknown["reply"], "b": other["reply"]}, NAMES)
    mismatch = _ask(api, "s-bad3", EXPLAIN, lang, scope={"customer": "BUYER-2", "decision": f"deal:{oid}"})
    assert mismatch["intent"] == "AMBIGUOUS" and mismatch["scope_used"] is None
    assert _ask(api, "s-bad4", EXPLAIN, lang, scope={"customer": "BUYER-9"})["intent"] == "AMBIGUOUS"
    assert _ask(api, "s-bad5", EXPLAIN, lang, scope={"invoice": "RCV-NOPE"})["scope_used"] is None
    assert _ask(api, "s-bad6", EXPLAIN, lang, scope={"decision": f"deal:{oid}", "scenario": "counter:99"})["scope_used"] is None
    assert _ask(api, "s-bad7", EXPLAIN, lang, scope={"scenario": "asked"})["intent"] == "AMBIGUOUS"  # a scenario is of a decision


def test_a_valid_scenario_of_the_decision_is_honoured(api: TestClient) -> None:
    oid = _evaluated(api)
    r = _ask(api, "s-scn", EXPLAIN, scope={"decision": f"deal:{oid}", "scenario": "counter:1"})
    assert r["scope_used"]["kind"] == "decision" and r["verdict"] is not None


def test_the_busy_company_scopes_each_customer_apart(api: TestClient) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    reset_sessions()
    a = _ask(api, "s-busy", "What happens if this payment is late?", scope={"invoice": "RCV-B1"})
    b = _ask(api, "s-busy", "What happens if this payment is late?", scope={"invoice": "RCV-A"})
    assert a["scope_used"]["label"] == "The invoice to Dongguan Office Supplies Ltd."
    assert b["scope_used"]["label"] == "The invoice to Foshan Home Retail Co."
    assert a["context_echo"]["invoice_id"] == "RCV-B1" and b["context_echo"]["invoice_id"] == "RCV-A" and a["reply"] != b["reply"]
    wrong = _ask(api, "s-busy", "What happens if this payment is late?", scope={"customer": "BUYER-1", "invoice": "RCV-B1"})
    assert wrong["intent"] == "AMBIGUOUS" and wrong["scope_used"] is None


def test_a_counterparty_turn_never_carries_a_scope_echo(api: TestClient) -> None:
    from app.api.auth import DEMO_COUNTERPARTY_KEYS

    r = api.post("/nl", json={"session_id": "s-cp", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1", "text": "Hello",
                              "scope": {"customer": "BUYER-1"}}, headers={"X-Counterparty-Key": DEMO_COUNTERPARTY_KEYS["BUYER-1"]})
    assert r.status_code == 200, r.text
    assert "scope_used" not in r.json() and r.json()["intent"] == "COUNTERPARTY_MESSAGE"


# ---------------------------------------------------------------- Slice B (S5): a narrower scope is honoured, or the answer says it was not

_COMPANY = {"en": "Your whole company", "zh": "整个公司"}


@pytest.mark.parametrize("lang,text", [("en", "Who owes us money?"), ("zh", "谁欠我们钱？")])
def test_a_company_wide_cash_status_says_company_whatever_customer_was_asked(api: TestClient, lang: str, text: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    r = _ask(api, f"s-status-{lang}", text, lang, scope={"customer": "BUYER-1"})
    assert r["intent"] == "SHOW_STATUS"  # the question is answered with the company's cash status
    assert r["scope_used"] == {"kind": "company", "label": _COMPANY[lang]}  # so the page shows the mismatch, not "Foshan"
    for scope in ({"invoice": "RCV-A", "customer": "BUYER-1"}, {"customer": "BUYER-2"}):
        assert _ask(api, f"s-status2-{lang}", text, lang, scope=scope)["scope_used"] == {"kind": "company", "label": _COMPANY[lang]}


@pytest.mark.parametrize("lang,text", [("en", "What changed today?"), ("zh", "今天有什么变化？")])
def test_what_changed_is_the_companys_and_says_so(api: TestClient, lang: str, text: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    r = _ask(api, f"s-changed-{lang}", text, lang, scope={"customer": "BUYER-1"})
    assert r["intent"] == "CHANGES" and r["scope_used"] == {"kind": "company", "label": _COMPANY[lang]}
    assert _ask(api, f"s-changed2-{lang}", text, lang, scope={})["scope_used"] == {"kind": "company", "label": _COMPANY[lang]}  # unchanged for a company scope


@pytest.mark.parametrize("lang,text", [("en", "What are we waiting for?"), ("zh", "我们在等什么？")])
def test_what_is_waiting_lists_only_the_scoped_customers_rows(api: TestClient, lang: str, text: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    dongguan = _ask(api, f"s-wait-b2-{lang}", text, lang, scope={"customer": "BUYER-2"})
    assert dongguan["scope_used"] == {"kind": "customer", "label": "Dongguan Office Supplies Ltd."}
    assert "Dongguan" in dongguan["reply"] and "Foshan" not in dongguan["reply"] and "200,000.00" not in dongguan["reply"]  # not the facility application
    assert dongguan["reply"].count("120,000.00") == 1 and dongguan["reply"].count("80,000.00") == 1
    company = _ask(api, f"s-wait-all-{lang}", text, lang)
    assert company["scope_used"] is None and "200,000.00" in company["reply"]  # the unscoped read still lists the company's items
    foshan = _ask(api, f"s-wait-b1-{lang}", text, lang, scope={"customer": "BUYER-1"})  # nothing of Foshan's is open at day 0
    assert "Foshan" in foshan["reply"] and "Dongguan" not in foshan["reply"]
    if lang == "zh":
        assert not english_leaks({"a": dongguan["reply"], "b": foshan["reply"]}, NAMES)


@pytest.mark.parametrize("lang,text", [("en", "What is overdue?"), ("zh", "什么逾期了？")])
def test_what_is_overdue_is_the_scoped_customers_own(api: TestClient, lang: str, text: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    foshan = _ask(api, f"s-od-b1-{lang}", text, lang, scope={"customer": "BUYER-1"})
    assert foshan["intent"] == "RECONCILE" and foshan["scope_used"]["kind"] == "customer"
    assert "Foshan" in foshan["reply"] and "Dongguan" not in foshan["reply"] and "120,000.00" not in foshan["reply"]
    dongguan = _ask(api, f"s-od-b2-{lang}", text, lang, scope={"customer": "BUYER-2"})
    assert "Dongguan" in dongguan["reply"] and "Foshan" not in dongguan["reply"] and "200,000.00" in dongguan["reply"]
    inv = _ask(api, f"s-od-inv-{lang}", text, lang, scope={"invoice": "RCV-B2", "customer": "BUYER-2"})
    assert inv["scope_used"]["kind"] == "invoice" and "80,000.00" in inv["reply"] and "120,000.00" not in inv["reply"]


@pytest.mark.parametrize("lang,text", [("en", "When does the money arrive?"), ("zh", "资金什么时候到账？")])
def test_when_money_arrives_is_the_scoped_customers_own(api: TestClient, lang: str, text: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    foshan = _ask(api, f"s-ar-b1-{lang}", text, lang, scope={"customer": "BUYER-1"})
    assert "Foshan" in foshan["reply"] and "Dongguan" not in foshan["reply"] and "420,000.00" in foshan["reply"]
    dongguan = _ask(api, f"s-ar-b2-{lang}", text, lang, scope={"customer": "BUYER-2"})
    assert "Dongguan" in dongguan["reply"] and "Foshan" not in dongguan["reply"] and "420,000.00" not in dongguan["reply"]


@pytest.mark.parametrize("lang,text", [("en", "What happens if this payment is late?"), ("zh", "如果这笔款项晚到会怎样？")])
def test_a_late_payment_of_a_customer_is_about_its_own_invoice(api: TestClient, lang: str, text: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    foshan = _ask(api, f"s-lp-b1-{lang}", text, lang, scope={"customer": "BUYER-1"})
    dongguan = _ask(api, f"s-lp-b2-{lang}", text, lang, scope={"customer": "BUYER-2"})
    assert "Foshan" in foshan["reply"] and "420,000.00" in foshan["reply"] and "Dongguan" not in foshan["reply"]
    assert "Dongguan" in dongguan["reply"] and "120,000.00" in dongguan["reply"] and "Foshan" not in dongguan["reply"]


def test_a_negotiation_scope_on_a_customer_read_says_customer(api: TestClient) -> None:
    oid = _evaluated(api)
    r = _ask(api, "s-dec-wait", "What are we waiting for?", scope={"decision": f"deal:{oid}"})
    assert r["scope_used"] == {"kind": "customer", "label": "Foshan Home Retail Co."}  # the read's rows are the customer's, not the negotiation's
    explain = _ask(api, "s-dec-expl", EXPLAIN, scope={"decision": f"deal:{oid}"})
    assert explain["scope_used"]["kind"] == "decision"  # a read about the negotiation keeps it
