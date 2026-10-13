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


def _live(d: dict[str, Any]) -> None:
    """The deal is live: no close-out, no word of closing or completion, and a state text that says what has happened."""
    assert d["closeout_text"] is None
    low = d["headline_text"].lower()
    assert "closed" not in low and "complete" not in low and "ended" not in low
    assert len(d["state_text"]) > 12 and d["state_text"].rstrip(".") != d["state_word"] and "Fulfilled" not in d["state_text"]
    assert [x["state"] for x in d["stages"]][-1] != "done"


def _lines(d: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {x["key"]: x for x in d["cost"]["lines"]}


def _check_sums(d: dict[str, Any]) -> None:
    cost = d["cost"]
    assert sum(x["actual_fen"] for x in cost["lines"] if x["actual_fen"] is not None) == cost["actual"]["amount_fen"]
    # the difference is the cost on top of the agreed terms: the counted funding lines, unsigned
    assert cost["difference_fen"] == sum(x["actual_fen"] for x in cost["lines"] if x["key"] != "terms" and x["actual_fen"] is not None) >= 0
    assert cost["unmeasured_display"] == (f"¥{cost['unmeasured_fen'] / 100:,.2f}" if cost["unmeasured_fen"] is not None else None)
    assert "less than expected" not in cost["actual"]["note_text"] and cost["actual"]["tone"] in ("bad", "neutral", "ok")
    if d["headline_text"] and "closed below" in d["headline_text"]:
        assert cost["unmeasured_fen"] == 0
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
    assert d["cost"]["actual"]["amount_fen"] == 0 and d["cost"]["difference_fen"] == 0 and d["cost"]["unmeasured_fen"] == EXPECTED_FEN
    assert d["cost"]["actual"]["note_text"] == "Nothing has been paid under the agreement yet." and d["cost"]["actual"]["tone"] == "neutral"
    [terms] = d["cost"]["lines"]
    assert terms["key"] == "terms" and terms["actual_fen"] == 0 and terms["certainty"] == "RECORDED"
    assert terms["actual_note_text"] == "Nothing has been paid under the agreement yet."
    assert "funding" not in _lines(d)
    assert d["headline_text"] == "Nothing has happened on this deal yet"
    assert [(p["party"], p["state"]) for p in d["promises"]] == [("buyer", "awaited"), ("buyer", "awaited"), ("you", "in_force")]
    assert d["promise_counts"] == {"buyer_kept": 0, "buyer_total": 2, "buyer_paid_late": 0, "text": "The buyer has kept zero of two promises on this deal."}
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
    assert terms["actual_note_text"].startswith("Not measured yet:") and "¥841.57" in terms["actual_note_text"]  # 302,777 - 218,620 = 84,157 fen
    assert d["cost"]["actual"]["amount_fen"] == POSTED_DISCOUNT_FEN and d["cost"]["difference_fen"] == 0
    assert d["cost"]["unmeasured_fen"] == 84157 == EXPECTED_FEN - POSTED_DISCOUNT_FEN and d["cost"]["unmeasured_display"] == "¥841.57"
    assert d["cost"]["actual"]["note_text"] == "¥841.57 of the expected cost is not measured yet." and d["cost"]["actual"]["tone"] == "neutral"
    assert "below" not in d["headline_text"] and "less than expected" not in d["cost"]["actual"]["note_text"]
    zh = _tracker(api, did, "zh")["cost"]
    assert zh["unmeasured_fen"] == 84157 and "¥841.57" in zh["actual"]["note_text"] and re.search(r"[\u4e00-\u9fff]", zh["actual"]["note_text"])
    states = {(p["party"], p["state"]) for p in d["promises"]}
    assert ("buyer", "kept") in states and ("you", "kept") in states
    assert d["promise_counts"]["buyer_kept"] == 1 and d["promise_counts"]["text"] == "The buyer has kept one of two promises on this deal."
    _live(d)  # the early part is paid, the rest of the invoice is not due yet: the commitment is fulfilled but the deal is not over
    assert d["headline_text"] == "This deal is on the agreed terms so far" and d["state_word"] == "On plan"
    assert d["state_text"] == "The buyer paid the early part it promised. The rest of the invoice falls due in 30 days."
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
    _live(d)
    assert d["headline_text"] == "The buyer is late on this deal" and d["state_word"] == "Payment late"
    assert d["state_text"] == "The buyer paid the early part it promised. The rest of the invoice is 2 days late."
    assert _tracker(api, did, "zh")["closeout_text"] is None
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
    assert queued["cost"]["difference_fen"] == 0 and queued["cost"]["unmeasured_fen"] == 84157
    assert "plainly" not in f["certainty_text"] and "do not tie the funding to this deal by itself" in f["certainty_text"]
    _live(queued)
    assert queued["state_text"].endswith("is 2 days late, and funding arranged after it is waiting for your approval.")
    assert queued["next"]["label"] == "Review the funding approval" and queued["next"]["href"] == "/approvals"  # cash safety before chasing
    assert queued["cost"]["to_come"]["amount_fen"] is not None and quote["state"] == "AUTHORIZATION_REQUIRED"
    _check_sums(queued)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    d = _tracker(api, did)
    f = _lines(d)["funding"]
    stored = next(x for x in get_runtime().store.decision_facts() if x.fact == "QUOTED")
    import json

    assert f["actual_fen"] == json.loads(stored.body_json)["total_cost_fen"] == 178219 and f["certainty"] == "ATTRIBUTED"
    assert d["cost"]["actual"]["amount_fen"] == POSTED_DISCOUNT_FEN + 178219 == 396839
    assert d["cost"]["difference_fen"] == 178219 == f["actual_fen"] and d["cost"]["unmeasured_fen"] == 84157
    assert d["cost"]["actual"]["note_text"] == ("Includes ¥1,782.19 of funding on top of the terms you agreed. "
                                                "¥841.57 of the expected cost is not measured yet.")
    assert d["cost"]["actual"]["tone"] == "bad" and d["headline_text"] == "This deal is costing more than you agreed to"
    _live(d)
    assert d["state_text"] == "The buyer paid the early part it promised. The rest of the invoice is 2 days late, and you arranged funding after it."
    assert d["state_word"] == "Payment late"
    assert not any(_live(z) for z in [_tracker(api, did, "zh")]) and re.search(r"[\u4e00-\u9fff]", _tracker(api, did, "zh")["state_text"])
    assert d["next"]["label"] == "Chase payment"  # the approval is done, the collection action is next
    zh = _tracker(api, did, "zh")["cost"]["actual"]["note_text"]
    assert "¥1,782.19" in zh and "¥841.57" in zh and re.search(r"[\u4e00-\u9fff]", zh)
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
    assert d["headline_text"] == "A promise on this deal was missed"
    _live(d)
    assert _lines(d)["terms"]["actual_note_text"] == "The early payment did not arrive, so no discount has been given under the agreement."
    approval = _cure(api)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    d = _tracker(api, did)
    assert _lines(d)["funding"]["actual_fen"] == 138132 and d["cost"]["actual"]["amount_fen"] == 138132
    assert d["cost"]["difference_fen"] == 138132 and d["cost"]["unmeasured_fen"] == 84157  # the lapsed promise's discount was never given
    assert d["cost"]["actual"]["note_text"] == ("Includes ¥1,381.32 of funding on top of the terms you agreed. "
                                                "¥841.57 of the expected cost is not measured yet.")
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


def test_a_cure_after_several_buyers_were_late_is_not_counted_and_no_two_trackers_count_one_cure(api: TestClient, rt: Runtime) -> None:
    """Another buyer's invoice is overdue too on the day the cure is quoted: the cure followed late payments from several buyers, so its
    line stays on the deal, uncounted (null), and no cure is in the total or the difference of any tracker."""
    did = _agree(api)
    _to_day34(api)
    state = rt.store.get_state()
    other = state.counterparties[0].model_copy(update={"id": "BUYER-LATE", "name": "Late Buyer Ltd.", "role": "BUYER"})
    late = state.receivables[0].model_copy(update={"id": "RCV-LATE", "counterparty_id": "BUYER-LATE", "issue_day": 0, "terms_days": 10,
                                                   "settled_fen": 0, "applied": []})
    rt.store.put_state(state.model_copy(update={"counterparties": [*state.counterparties, other], "receivables": [*state.receivables, late]}))
    approval = _cure(api)
    d = _tracker(api, did)
    funding = [x for x in d["cost"]["lines"] if x["key"] != "terms"]
    assert len(funding) == 1 and funding[0]["certainty"] == "ATTRIBUTED"
    assert funding[0]["actual_fen"] is None and funding[0]["actual_display"] is None
    assert funding[0]["actual_note_text"] == "This funding followed late payments from several buyers, so it is not counted in this deal's cost."
    assert "do not tie the funding to this deal by itself" in funding[0]["certainty_text"]
    assert d["cost"]["difference_fen"] == 0 and d["cost"]["actual"]["amount_fen"] == 0 and d["cost"]["to_come"]["amount_fen"] is None
    assert d["next"]["label"] == "Review the funding approval"
    _check_sums(d)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    counted: dict[str, int] = {}
    for row in api.get("/decisions", params={"family": "DEAL"}).json()["decisions"]:
        t_ = _tracker(api, row["id"])
        if not t_["available"]:
            continue
        _check_sums(t_)
        for line in t_["cost"]["lines"]:
            if line["key"] != "terms" and line["actual_fen"] is not None:
                counted[line["evidence_href"]] = counted.get(line["evidence_href"], 0) + 1
    assert all(n == 1 for n in counted.values()) and not counted  # here no tracker counts it
    d = _tracker(api, did)
    assert _lines(d)["funding"]["actual_fen"] is None and d["cost"]["difference_fen"] == 0 and d["cost"]["actual"]["amount_fen"] == 0
    zh = _tracker(api, did, "zh")["cost"]["lines"][1]
    assert zh["actual_fen"] is None and "多位买方" in zh["actual_note_text"]


def test_no_note_says_less_than_expected_while_the_deal_is_live(api: TestClient) -> None:
    did = _agree(api)
    for day in (None, 2):
        if day:
            api.post("/clock/advance", json={"to_day": day})
        d = _tracker(api, did)
        assert "less than expected" not in d["cost"]["actual"]["note_text"] and d["cost"]["actual"]["tone"] != "ok"
        assert all("less than expected" not in (x["actual_note_text"] or "") for x in d["cost"]["lines"])


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_once_every_invoice_of_the_deal_is_paid_the_deal_has_ended_with_its_close_out(api: TestClient, lang: str) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    approval = _cure(api)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    before = _tracker(api, did, lang)
    assert before["closeout_text"] is None and before["state_word"] in ("Payment late", "付款逾期")
    rest = next(r for r in get_runtime().store.get_state().receivables if r.id == "RCV-A")
    bank = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
    version = api.get("/mandate").json()["mandate"]["version"]
    paid = api.post("/operations", headers=bank, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "rc-rest", "idempotency_key": "rc-rest", "mandate_version": version, "requested_by": "SYSTEM",
        "receivable_id": "RCV-A", "amount_fen": rest.face_fen - rest.settled_fen, "bank_reference": "BANK-REST"})
    assert paid.json()["result"]["status"] == "EXECUTED", paid.text
    d = _tracker(api, did, lang)
    assert d["next"] is None and [p["state"] for p in d["promises"] if p["party"] == "buyer"] == ["kept", "paid_late"]
    assert d["stages"][-1]["state"] == "done" and d["stages"][-1]["key"] == "fulfilled"
    assert d["cost"]["actual"]["amount_fen"] == 396839 and d["cost"]["unmeasured_fen"] == 84157 and d["cost"]["difference_fen"] == 178219
    late = next(p for p in d["promises"] if p["state"] == "paid_late")
    assert late["tone"] == "warn" and late["state_word"] == ("Paid late" if lang == "en" else "逾期支付") and "34" not in late["detail_text"]
    assert d["promise_counts"]["buyer_kept"] == 1 and d["promise_counts"]["buyer_paid_late"] == 1
    if lang == "en":
        assert late["detail_text"].endswith("2 days ago, 2 days late.") or "days late" in late["detail_text"]
        assert d["promise_counts"]["text"] == "The buyer has kept one of two promises on this deal; one was paid late."
        assert d["closeout_text"] == ("This deal cost ¥3,968.39 against ¥3,027.77 expected, including ¥1,782.19 of funding on top; "
                                      "¥841.57 of the expected cost was never measured. The buyer kept 1 of 2 promises; 1 was paid late.")
        assert d["headline_text"] == "This deal closed with extra cost on top of the terms you agreed" and d["state_word"] == "Paid late"
        assert d["state_text"] == "The buyer paid the early part it promised. Every invoice on this deal has been paid."
    else:
        assert "¥3,968.39" in d["closeout_text"] and "¥1,782.19" in d["closeout_text"] and re.search(r"[\u4e00-\u9fff]", d["closeout_text"])
        assert d["state_text"].startswith("买方已支付")
    _no_leaks(d)
    _check_sums(d)


def _stage_states(d: dict[str, Any]) -> dict[str, str]:
    return {x["key"]: x["state"] for x in d["stages"]}


def test_the_stages_follow_the_one_flag_on_the_demo_books_with_the_contract_confirmed(api: TestClient, rt: Runtime) -> None:
    """The recorder's walk: POST /demo/reset's books (the three demo documents confirmed, so the deal row has its own stages), then the
    story, then the rest of the invoice paid through the bank-feed route. Whichever source the labels come from, ended means every stage is
    done (missed or part for a promise missed or part kept) and live means collecting is the one stage that is now."""
    rt.reset_demo("golden_sme")
    did = _agree(api)
    d = _tracker(api, did)
    assert "read" in _stage_states(d), "the deal row's own stages are in use: the contract is confirmed"
    live_now = lambda x: [s["key"] for s in x["stages"] if s["state"] == "now"]
    assert _stage_states(d) == {"read": "done", "negotiated": "done", "early_payment": "part", "collecting": "now", "fulfilled": "todo"}
    assert live_now(d) == ["collecting"]
    api.post("/clock/advance", json={"to_day": 2})
    assert api.post("/demo/bank-receipt").status_code == 200
    d = _tracker(api, did)
    assert _stage_states(d) == {"read": "done", "negotiated": "done", "early_payment": "done", "collecting": "now", "fulfilled": "todo"}
    _to_day34(api)
    d = _tracker(api, did)
    assert d["closeout_text"] is None and live_now(d) == ["collecting"] and _stage_states(d)["fulfilled"] == "todo"
    approval = _cure(api)
    assert live_now(_tracker(api, did)) == ["collecting"]
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    d = _tracker(api, did)
    assert d["closeout_text"] is None and live_now(d) == ["collecting"]
    bank = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
    rest = next(r for r in rt.store.get_state().receivables if r.id == "RCV-A")
    paid = api.post("/operations", headers=bank, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "rc-rest", "idempotency_key": "rc-rest", "mandate_version": api.get("/mandate").json()["mandate"]["version"],
        "requested_by": "SYSTEM", "receivable_id": "RCV-A", "amount_fen": rest.face_fen - rest.settled_fen, "bank_reference": "BANK-REST"})
    assert paid.json()["result"]["status"] == "EXECUTED", paid.text
    for lang in ("en", "zh"):
        d = _tracker(api, did, lang)
        assert d["closeout_text"] and _stage_states(d) == {"read": "done", "negotiated": "done", "early_payment": "done",
                                                           "collecting": "done", "fulfilled": "done"}
        assert not live_now(d) and all(s["state"] not in ("now", "todo") for s in d["stages"])


def test_a_missed_early_payment_shows_its_stage_missed_and_collecting_now_when_live(api: TestClient, rt: Runtime) -> None:
    rt.reset_demo("golden_sme")
    did = _agree(api)
    _to_day34(api)
    states = _stage_states(_tracker(api, did))
    assert states["early_payment"] == "missed" and states["collecting"] == "now" and states["fulfilled"] == "todo"
