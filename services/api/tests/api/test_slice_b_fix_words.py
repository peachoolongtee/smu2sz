"""Slice B fix S7, the words the verifier caught: a pending approval's consequence is what approving does, not what declining comes to; the
result of an approved application does not say PENDING nor overstate ("Approved and submitted"); an agreed negotiation's decision read keeps the
verdict the agreement was made from; a term a path does not carry is null, never the word "None"; the abstention sentence has a Business phrasing
in both languages; an agreement that is only an immediate discount says its forward cost is ¥0.00 under a "forward" label with the discount on a
line of its own."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import agree_on_rcv_a, english_leaks

pytestmark = pytest.mark.usefixtures("fast_busy")  # the busy seed is replayed once per process (tests/api/busy_snapshot.py)

OWNER = {"X-Owner-Token": "demo-owner-token"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Government-guaranteed working-capital loan"]


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


def _busy(api: TestClient) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200


# ---------------------------------------------------------------- (a) a pending approval's consequence


@pytest.mark.parametrize("lang,expected", [
    ("en", "Approving submits the application; nothing runs until the bank commits."),
    ("zh", "批准后将提交这份申请；在银行承诺之前不会执行任何操作。")])
def test_a_pending_application_in_the_queue_says_what_approving_does(api: TestClient, lang: str, expected: str) -> None:
    _busy(api)
    [row] = [r for r in api.get("/deals", params={"lang": lang}).json()["queue"]["needs_you"] if r["kind"] == "APPROVAL"]
    assert row["consequence_text"] == expected
    assert "request is closed" not in row["consequence_text"] and "该请求关闭" not in row["consequence_text"]
    worklist_row = next(r for r in api.get("/worklist", params={"lang": lang}).json()["needs_you"] if r["kind"] == "APPROVAL")
    assert worklist_row["consequence_text"] == expected  # the Home's row says the same


# ---------------------------------------------------------------- (b) after approve


def test_after_approve_the_result_words_have_no_status_code_and_do_not_overstate(api: TestClient) -> None:
    _busy(api)
    approval = api.get("/approvals/queue").json()["approvals"][0]
    r = api.post(f"/approvals/{approval['id']}", params={"lang": "en"}, json={"decision": "APPROVE"}).json()
    said = r["result"]["message_when"]
    assert said == ("Applied for ¥200,000.00 on Government-guaranteed working-capital loan; "
                    "the application is submitted and counts as zero cash until the bank commits")
    assert "PENDING" not in said and "PENDING" not in r["result"]["event_text"]
    row = api.get("/approvals/queue").json()["approvals"][0]
    assert row["result_state_text"] == "Approved and submitted" and row["result_tone"] == "info"
    assert row["presentation"]["result_message"] == said and "PENDING" not in json.dumps(row["presentation"])
    assert row["execution"]["summary_text"] == said


def test_after_approve_in_chinese_the_application_is_submitted_not_pending(api: TestClient) -> None:
    _busy(api)
    approval = api.get("/approvals/queue", params={"lang": "zh"}).json()["approvals"][0]
    r = api.post(f"/approvals/{approval['id']}", params={"lang": "zh"}, json={"decision": "APPROVE"}).json()
    assert r["result"]["message_when"] == "已向Government-guaranteed working-capital loan申请 ¥200,000.00；申请已提交，在银行承诺之前按零现金计算"
    row = api.get("/approvals/queue", params={"lang": "zh"}).json()["approvals"][0]
    assert row["result_state_text"] == "已批准并已提交"
    assert not english_leaks({"a": r["result"]["message_when"], "b": row["result_state_text"]}, NAMES)


def test_a_repayment_approved_is_still_done(api: TestClient) -> None:
    from app.api.presentation import approval_result_state

    assert approval_result_state(kind="REPAY_FACILITY", status="APPROVED", execution_status="EXECUTED", lands_day=None, today=0,
                                 lang="en") == ("Approved, done", "ok")


# ---------------------------------------------------------------- (c) an agreed negotiation keeps the verdict it was made from


def test_an_agreed_decision_does_not_surface_a_later_unreadable_verdict(api: TestClient) -> None:
    _busy(api)
    offer_id = agree_on_rcv_a(api)
    # the page reads the offer again on the books the agreement changed: the new verdict cannot be read (its invoice was settled)
    again = api.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": "EX03_AS_USUAL"}).json()
    assert again["business_action"] == "cannot"
    d = api.get(f"/decisions/deal:{offer_id}").json()
    assert d["state"] == "AGREED" and d["state_text"] == "Agreed"
    assert d["evaluation"]["business_action"] == "counter" and d["evaluation"]["verdict_id"] != again["id"]
    assert d["response"]["recommended_counter_id"] and d["response"]["sent"]["outcome"] == "DEAL"
    assert "Cannot be decided yet" not in json.dumps(d) and "Clarify" not in json.dumps(d)
    listed = next(x for x in api.get("/decisions").json()["decisions"] if x["id"] == f"deal:{offer_id}")
    assert listed["state"] == "AGREED"


# ---------------------------------------------------------------- (d) no "None"


def _strings(x: Any) -> Iterator[tuple[str, str]]:
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, str):
                yield k, v
            else:
                yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_term_a_path_does_not_carry_and_no_financing_are_null_not_the_word_none(api: TestClient, lang: str) -> None:
    ex = {"fixture_id": "EX01_PACKAGE"}
    offer_id = api.post("/offers", json=ex).json()["offer"]["offer_id"]
    api.post(f"/offers/{offer_id}/evaluate", json=ex)
    picture = api.get(f"/offers/{offer_id}/picture", params={"lang": lang}).json()
    rows = {p["key"]: {t["key"]: t for t in p["terms"]} for p in picture["paths"]}
    a, b = (p for p in picture["paths"] if p["kind"] == "reply")
    assert rows[a["key"]]["rebate_or_price"]["value_text"] is None  # Option A carries no rebate or price
    assert rows[b["key"]]["early_payment"]["value_text"] is None  # Option B carries no early payment
    assert rows[a["key"]]["early_payment"]["value_text"] and rows[b["key"]]["rebate_or_price"]["value_text"]
    # what the buyer asked for in its place is still said, so dropping a term is not silent
    assert rows[b["key"]]["early_payment"]["instead_of_text"] and rows["asked"]["early_payment"]["instead_of_text"] is None
    _busy(api)  # Zhuhai: nothing is financed against its invoice and no plan is about to finance it
    overview = api.get("/customers/BUYER-3/overview", params={"lang": lang}).json()
    financing = next(f for f in overview["figures"] if f["key"] == "financing")
    assert financing["value_display"] is None and financing["note"]
    for body in (picture, overview):
        assert not [(k, v) for k, v in _strings(body) if k in ("value_text", "value_display", "instead_of_text") and v.strip() in ("None", "none", "null", "无")]


# ---------------------------------------------------------------- (e) the abstention sentence


@pytest.mark.parametrize("lang,expected", [
    ("en", "The message and its attachment give two different order sizes."),
    ("zh", "消息及其附件给出了两个不同的订单量。")])
def test_the_conflicting_sources_abstention_has_a_business_sentence(api: TestClient, lang: str, expected: str) -> None:
    r = api.post("/offers", params={"lang": lang}, json={"fixture_id": "EX07_CONFLICT"}).json()
    [abstention] = r["offer"]["abstentions"]
    assert abstention["reason"].startswith("conflicting sources")  # the compiler's own sentence stays for the audit
    assert abstention["reason_when"] == expected
    got = api.get(f"/offers/{r['offer']['offer_id']}", params={"lang": lang}).json()["offer"]["abstentions"][0]["reason_when"]
    assert got == expected


def test_an_abstention_with_no_sentence_of_its_own_gets_the_business_rewrite_or_null() -> None:
    from app.api.presentation import abstention_words

    assert abstention_words("conflicting sources: the documents state 3 different values for invoice_amount", ["chat"], "en") == (
        "The documents give three different invoice amounts.")
    assert abstention_words("something else entirely", ["chat"], "en") is None


# ---------------------------------------------------------------- (f) the agreements footer


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_agreement_that_is_only_an_immediate_discount_says_forward_and_shows_the_discount_on_its_own_line(api: TestClient, lang: str) -> None:
    _busy(api)
    agree_on_rcv_a(api, "EX02_EARLY_1_5")
    [c] = api.get("/ledger", params={"lang": lang}).json()["commitments"]
    assert c["forward_value_display"] == "¥0.00"  # honestly zero: the discount is immediate, not forward
    assert c["forward_label_text"] == {"en": "Forward cost you have promised", "zh": "您已承诺的远期成本"}[lang]
    assert c["immediate_label_text"] == {"en": "Immediate discount", "zh": "立即折扣"}[lang]
    assert c["immediate_text"] == {"en": "0.85% off ¥420,000.00", "zh": "¥420,000.00 减免 0.85%"}[lang]
    ws_items = api.get("/ledger", params={"lang": lang}).json()["commitments"]
    assert ws_items and all(x["forward_label_text"] for x in ws_items)


def test_an_agreement_with_no_discount_has_no_discount_line() -> None:
    from types import SimpleNamespace

    from app.api.presentation import commitment_cost_words

    words = commitment_cost_words(SimpleNamespace(obligations=[]), "en")
    assert words["immediate_label_text"] is None and words["immediate_text"] is None and "Forward" in str(words["forward_label_text"])
