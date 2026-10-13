"""The deal tracker read (GET /decisions/{id}/tracker): one agreed deal, the cost expected at agreement against the cost so far, the
promises of each side, what that says about the buyer, and the one next step. The walk is the golden story (EX01, a cooperative buyer
agrees, day 2, optionally the synthetic bank receipt, day 34, the cure queued and approved), asserted through the routes the web calls."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
EXPECTED_FEN = 302777  # the supplier cost the sent counter stored: the figure the decision record shows
POSTED_DISCOUNT_FEN = 218620  # 85 bp of the 25,720,000 fen the agreement covers, by hand: 25_720_000 * 85 // 10_000 = 218_620
BAD_TEXT = [re.compile(p) for p in (r"\bday \d+\b", r"\bNone\b", r"\b(?:OFF|CMT|RCV|VER|APR|CTR|ALERT)-[\w-]+", r"\b[A-Z]{2,}_[A-Z_]+\b")]


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    worklist.clear_cache()
    offer_picture._cache.clear()
    yield runtime
    set_runtime(None)
    worklist.clear_cache()
    offer_picture._cache.clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _agree(api: TestClient) -> str:
    offer = api.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    assert api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    return str(v["decision_id"])


def _tracker(api: TestClient, did: str, lang: str = "en") -> dict[str, Any]:
    r = api.get(f"/decisions/{did}/tracker", params={"lang": lang})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _to_day34(api: TestClient) -> None:
    for day in (2, 30, 34):
        assert api.post("/clock/advance", json={"to_day": day}).status_code == 200


def _cure(api: TestClient) -> str:
    action = api.get("/home").json()["next_action"]
    r = api.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    assert r.status_code == 200, r.text
    [row] = [a for a in api.get("/approvals/queue").json()["approvals"] if a["status"] == "PENDING"]
    return str(row["id"])


def _lines(d: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {x["key"]: x for x in d["cost"]["lines"]}


def _check_sums(d: dict[str, Any]) -> None:
    cost = d["cost"]
    assert sum(x["actual_fen"] for x in cost["lines"] if x["actual_fen"] is not None) == cost["actual"]["amount_fen"]
    assert cost["difference_fen"] == cost["actual"]["amount_fen"] - cost["expected"]["amount_fen"]
    assert sum(x["expected_fen"] for x in cost["lines"]) == cost["expected"]["amount_fen"]


def _texts(x: Any, key: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "context":
                continue
            yield from _texts(v, k)
    elif isinstance(x, list):
        for v in x:
            yield from _texts(v, key)
    elif isinstance(x, str) and (key.endswith(("_text", "_word", "_display")) or key in ("label", "headline_text", "agreed_when", "buyer_name")):
        yield key, x


def _no_leaks(d: dict[str, Any]) -> None:
    for key, text in _texts(d):
        for bad in BAD_TEXT:
            assert not bad.search(text), (key, text)


def test_just_after_the_agreement_expected_is_set_and_nothing_has_been_paid(api: TestClient) -> None:
    did = _agree(api)
    d = _tracker(api, did)
    assert d["available"] is True and d["unavailable_text"] is None and d["lang"] == "en"
    assert d["buyer_name"] == "Foshan Home Retail Co." and d["agreed_when"] == "today"
    assert d["cost"]["expected"]["amount_fen"] == EXPECTED_FEN and d["cost"]["expected"]["amount_display"] == "¥3,027.77"
    assert d["cost"]["expected"]["certainty"] == "QUOTED"
    assert d["cost"]["actual"]["amount_fen"] == 0 and d["cost"]["difference_fen"] == -EXPECTED_FEN
    [terms] = d["cost"]["lines"]
    assert terms["key"] == "terms" and terms["actual_fen"] == 0 and terms["certainty"] == "RECORDED"
    assert terms["actual_note_text"] == "Nothing has been paid under the agreement yet."
    assert "funding" not in _lines(d)
    assert d["headline_text"] == "Nothing has happened on this deal yet"
    assert [(p["party"], p["state"]) for p in d["promises"]] == [("buyer", "awaited"), ("buyer", "awaited"), ("you", "in_force")]
    assert d["promise_counts"] == {"buyer_kept": 0, "buyer_total": 2, "text": "The buyer has kept zero of two promises on this deal."}
    assert d["cost"]["to_come"]["amount_fen"] == POSTED_DISCOUNT_FEN  # the discount posted on the awaited promise
    assert d["next"] is None and d["closeout_text"] is None
    assert d["links"]["record_href"] == f"/decisions/{did}" and d["links"]["activity_href"] == f"/activity?decision={did}"
    assert d["buyer"]["href"] == "/customers/BUYER-1" and d["context"]["decision"] == did
    assert [s["key"] for s in d["stages"]][-1] == "fulfilled"
    _check_sums(d)


def test_the_expected_figure_equals_the_decision_record_to_the_fen(api: TestClient) -> None:
    did = _agree(api)
    record = api.get(f"/decisions/{did}").json()
    shown = record["response"]["sent"]["economics"]
    assert shown["supplier_cost_display"] == _tracker(api, did)["cost"]["expected"]["amount_display"] == "¥3,027.77"
    assert _tracker(api, did)["terms_text"] and _tracker(api, did)["cost"]["expected"]["basis_text"]


def test_after_the_bank_receipt_the_booked_discount_is_in_the_terms_line(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    assert api.post("/demo/bank-receipt").status_code == 200
    d = _tracker(api, did)
    promise = api.get("/reconciliation").json()["reconciliation"]["promised"][0]
    assert promise["face_fen"] * 85 // 10_000 == POSTED_DISCOUNT_FEN  # by hand: 25,720,000 fen at 85 basis points
    terms = _lines(d)["terms"]
    assert terms["actual_fen"] == POSTED_DISCOUNT_FEN == promise["discount_fen"] and terms["actual_display"] == "¥2,186.20"
    assert terms["certainty"] == "RECORDED" and terms["evidence_href"].startswith("/trust?view=evidence&entry=")
    assert terms["evidence_href"].endswith("&from=tracker")
    assert terms["actual_note_text"].startswith("Not measured:") and "¥841.57" in terms["actual_note_text"]  # 302,777 - 218,620 = 84,157 fen
    assert d["cost"]["actual"]["amount_fen"] == POSTED_DISCOUNT_FEN and d["cost"]["difference_fen"] == POSTED_DISCOUNT_FEN - EXPECTED_FEN
    states = {(p["party"], p["state"]) for p in d["promises"]}
    assert ("buyer", "kept") in states and ("you", "kept") in states
    assert d["promise_counts"]["buyer_kept"] == 1 and d["promise_counts"]["text"] == "The buyer has kept one of two promises on this deal."
    assert d["closeout_text"] and "¥2,186.20" in d["closeout_text"]
    _check_sums(d)


def test_at_the_late_day_a_promise_is_late_and_the_next_step_is_to_chase(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    d = _tracker(api, did)
    assert [p["state"] for p in d["promises"] if p["party"] == "buyer"] == ["kept", "late"]
    late = next(p for p in d["promises"] if p["state"] == "late")
    assert late["tone"] == "bad" and late["state_word"] == "Late" and late["evidence_href"].startswith("/receivables?invoice=")
    assert d["next"]["label"] == "Chase payment" and d["next"]["href"].startswith("/receivables?invoice=")
    assert "¥162,800.00" in d["next"]["text"] and d["state_tone"] == "bad" and d["state_word"] == "Payment late"
    _check_sums(d)


def test_the_cure_queued_then_approved_adds_the_attributed_funding_line(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    approval = _cure(api)
    queued = _tracker(api, did)
    f = _lines(queued)["funding"]
    quote = next(x for x in api.get("/decisions", params={"family": "FUNDING"}).json()["decisions"])
    assert f["certainty"] == "ATTRIBUTED" and f["actual_fen"] is None and f["expected_fen"] == 0
    assert "approve" in f["actual_note_text"] and f["certainty_text"] and "attributed to this deal" in f["certainty_text"]
    assert queued["cost"]["actual"]["amount_fen"] == POSTED_DISCOUNT_FEN and queued["cost"]["to_come"]["amount_fen"] == 178219
    assert queued["cost"]["to_come"]["amount_fen"] is not None and quote["state"] == "AUTHORIZATION_REQUIRED"
    _check_sums(queued)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    d = _tracker(api, did)
    f = _lines(d)["funding"]
    stored = next(x for x in get_runtime().store.decision_facts() if x.fact == "QUOTED")
    import json

    assert f["actual_fen"] == json.loads(stored.body_json)["total_cost_fen"] == 178219 and f["certainty"] == "ATTRIBUTED"
    assert d["cost"]["actual"]["amount_fen"] == POSTED_DISCOUNT_FEN + 178219 == 396839
    assert d["cost"]["difference_fen"] == 396839 - EXPECTED_FEN == 94062 and d["cost"]["actual"]["note_text"] == "¥940.62 more than expected"
    assert d["cost"]["actual"]["tone"] == "bad" and d["headline_text"] == "This deal closed above the expected cost"
    _check_sums(d)
    api.post("/clock/advance", json={"to_day": 45})
    assert _tracker(api, did)["cost"]["actual"]["amount_fen"] == 396839  # settlement books the cash, it changes no quoted cost


def test_without_a_receipt_the_missed_promise_costs_nothing_until_the_cure_runs(api: TestClient) -> None:
    did = _agree(api)
    d0 = _tracker(api, did)
    assert d0["cost"]["actual"]["amount_fen"] == 0
    _to_day34(api)
    d = _tracker(api, did)
    assert [p["state"] for p in d["promises"] if p["party"] == "buyer"] == ["missed", "late"]
    assert [p["state"] for p in d["promises"] if p["party"] == "you"] == ["ended"]
    assert d["state_word"] == "Promise missed" and d["state_tone"] == "bad" and d["next"]["label"] == "Chase payment"
    assert d["headline_text"] == "This deal ended with the buyer's promise missed"
    assert _lines(d)["terms"]["actual_note_text"] == "The early payment did not arrive, so no discount has been given under the agreement."
    approval = _cure(api)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    d = _tracker(api, did)
    assert _lines(d)["funding"]["actual_fen"] == 138132 and d["cost"]["actual"]["amount_fen"] == 138132
    assert d["cost"]["difference_fen"] == 138132 - EXPECTED_FEN
    _check_sums(d)


def test_the_busy_books_agreed_deal(api: TestClient) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    ids = [x["id"] for x in api.get("/decisions", params={"family": "DEAL"}).json()["decisions"] if x["state"] == "AGREED"]
    assert len(ids) == 1
    d = _tracker(api, ids[0])
    assert d["available"] is True and d["buyer_id"] == "BUYER-1" and d["cost"]["lines"][0]["key"] == "terms"
    assert d["promises"] and d["promise_counts"]["buyer_total"] >= 1
    _check_sums(d)
    _no_leaks(d)


def test_a_decision_with_no_agreement_is_available_false_with_a_sentence(api: TestClient) -> None:
    offer = api.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    api.post(f"/offers/{offer}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    d = _tracker(api, f"deal:{offer}")
    assert d["available"] is False and d["unavailable_text"] == "This deal has not been agreed yet, so there is nothing to track."
    assert d["cost"]["lines"] == [] and d["promises"] == [] and d["next"] is None
    assert _tracker(api, f"deal:{offer}", "zh")["unavailable_text"] == "这笔交易尚未达成，因此没有可跟踪的内容。"


def test_a_funding_decision_is_available_false(api: TestClient) -> None:
    _agree(api)
    _to_day34(api)
    _cure(api)
    [funding] = api.get("/decisions", params={"family": "FUNDING"}).json()["decisions"]
    d = _tracker(api, funding["id"])
    assert d["available"] is False and "funding decision" in d["unavailable_text"]


def test_an_unknown_decision_is_404_and_the_read_is_owner_only(api: TestClient) -> None:
    assert api.get("/decisions/deal:OFF-nothing/tracker").status_code == 404
    from app.main import app

    assert TestClient(app).get("/decisions/deal:OFF-nothing/tracker").status_code == 401


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_both_languages_carry_the_same_figures_and_no_ids_or_enums(api: TestClient, lang: str) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    _cure(api)
    d = _tracker(api, did, lang)
    en = _tracker(api, did, "en")
    assert d["lang"] == lang
    assert d["cost"]["expected"]["amount_fen"] == en["cost"]["expected"]["amount_fen"]
    assert [x["actual_fen"] for x in d["cost"]["lines"]] == [x["actual_fen"] for x in en["cost"]["lines"]]
    assert [p["state"] for p in d["promises"]] == [p["state"] for p in en["promises"]]
    _no_leaks(d)
    if lang == "zh":
        assert d["headline_text"] != en["headline_text"] and re.search(r"[一-鿿]", d["state_text"])
        assert re.search(r"[一-鿿]", d["promise_counts"]["text"]) and re.search(r"[一-鿿]", d["cost"]["method_text"])


def test_the_read_changes_nothing(api: TestClient, rt: Runtime) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    _cure(api)

    def counts() -> tuple[int, ...]:
        s: Any = rt.store
        return (len(s.operations()), len(s.approvals()), len(s.commitments()), len(s.security_events()), len(s.decision_facts()))

    before = counts()
    for lang in ("en", "zh"):
        _tracker(api, did, lang)
    assert api.get(f"/decisions/{did}/tracker", params={"customer": "BUYER-1", "from": "home"}).status_code == 200
    assert counts() == before


def test_the_selection_context_is_the_decision_records(api: TestClient) -> None:
    did = _agree(api)
    d = api.get(f"/decisions/{did}/tracker", params={"customer": "BUYER-9", "from": "home"}).json()
    assert d["context"]["customer"] == "BUYER-1" and d["context"]["irrelevant_text"] and d["context"]["back"]["href"] == "/"
