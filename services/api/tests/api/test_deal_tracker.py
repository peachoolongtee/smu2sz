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
from tests.api.conftest import agree_on_rcv_a

pytestmark = pytest.mark.usefixtures("fast_busy")  # the busy seed is replayed once per process (tests/api/busy_snapshot.py)

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
    later = [x for x in cost["lines"] if x["key"] not in ("terms", "planned_funding")]
    assert cost["difference_fen"] == sum(x["actual_fen"] for x in later if x["actual_fen"] is not None) >= 0
    assert all(x["counted"] == (x["actual_fen"] is not None) for x in later) and all(x["relation"] for x in later)
    assert cost["related_fen"] == sum(x["related_fen"] for x in later if x["related_fen"] is not None)
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
    assert d["cost"]["actual"]["amount_fen"] == 84157 and d["cost"]["difference_fen"] == 0 and d["cost"]["unmeasured_fen"] == 0
    assert d["cost"]["actual"]["note_text"] == ("Includes ¥841.57 of funding planned when you agreed. "
                                                "Nothing has been paid under the agreement yet.") and d["cost"]["actual"]["tone"] == "neutral"
    assert [x["key"] for x in d["cost"]["lines"]] == ["terms", "planned_funding"]
    terms, planned = d["cost"]["lines"]
    assert terms["expected_fen"] + planned["expected_fen"] == EXPECTED_FEN  # 218,620 + 84,157 = 302,777: the two stored components
    assert terms["expected_fen"] == POSTED_DISCOUNT_FEN and planned["expected_fen"] == 84157
    assert terms["actual_fen"] == 0 and terms["certainty"] == "RECORDED"
    assert terms["actual_note_text"] == "Nothing has been paid under the agreement yet."
    # the gap plan FLOW ran when the deal was agreed (the credit line was drawn) is already a cost, at its stored figure
    assert planned["actual_fen"] == 84157 and planned["certainty"] == "QUOTED" and planned["actual_note_text"] is None
    assert "funding" not in _lines(d)
    assert d["headline_text"] == "The planned funding has run; the buyer's payment is still awaited"
    assert [(p["party"], p["state"]) for p in d["promises"]] == [("buyer", "awaited"), ("buyer", "awaited"), ("you", "in_force")]
    assert d["promise_counts"] == {"buyer_kept": 0, "buyer_total": 2, "buyer_paid_late": 0, "buyer_due": 0, "buyer_to_come": 2,
                                  "text": "The buyer has made two promises on this deal; none is due yet."}
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
    assert terms["actual_note_text"] is None and terms["expected_fen"] == POSTED_DISCOUNT_FEN  # nothing is unmeasured: 218,620 + 84,157 = 302,777
    assert d["cost"]["actual"]["amount_fen"] == EXPECTED_FEN == POSTED_DISCOUNT_FEN + 84157 and d["cost"]["difference_fen"] == 0
    assert d["cost"]["unmeasured_fen"] == 0 and d["cost"]["unmeasured_display"] == "¥0.00"
    assert d["cost"]["actual"]["note_text"] == "Includes ¥841.57 of funding planned when you agreed." and d["cost"]["actual"]["tone"] == "neutral"
    assert "below" not in d["headline_text"] and "less than expected" not in d["cost"]["actual"]["note_text"]
    zh = _tracker(api, did, "zh")["cost"]
    assert zh["unmeasured_fen"] == 0 and "¥841.57" in zh["actual"]["note_text"] and re.search(r"[一-鿿]", zh["actual"]["note_text"])
    states = {(p["party"], p["state"]) for p in d["promises"]}
    assert ("buyer", "kept") in states and ("you", "kept") in states
    assert d["promise_counts"]["buyer_kept"] == 1 and d["promise_counts"]["text"] == "The buyer has kept one of one promise due so far; one more is still to come."
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
    assert "approve" in f["actual_note_text"] and f["relation"] == "after_late_payment" and f["counted"] is False
    assert queued["cost"]["actual"]["amount_fen"] == EXPECTED_FEN and queued["cost"]["to_come"]["amount_fen"] == 178219
    assert queued["cost"]["difference_fen"] == 0 and queued["cost"]["unmeasured_fen"] == 0 and queued["cost"]["related_fen"] == 178219
    assert "The records do not show how much of it this deal caused" in f["certainty_text"]
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
    assert d["cost"]["actual"]["amount_fen"] == POSTED_DISCOUNT_FEN + 84157 + 178219 == 480996 and f["counted"] is True
    assert d["cost"]["difference_fen"] == 178219 == f["actual_fen"] == d["cost"]["related_fen"] and d["cost"]["unmeasured_fen"] == 0
    assert d["cost"]["actual"]["note_text"] == ("Includes ¥841.57 of funding planned when you agreed. "
                                                "Includes ¥1,782.19 of funding on top of the terms you agreed.")
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
    assert _tracker(api, did)["cost"]["actual"]["amount_fen"] == 480996  # settlement books the cash, it changes no quoted cost


def test_without_a_receipt_the_missed_promise_costs_nothing_until_the_cure_runs(api: TestClient) -> None:
    did = _agree(api)
    d0 = _tracker(api, did)
    assert d0["cost"]["actual"]["amount_fen"] == 84157  # only the funding planned at agreement, already drawn
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
    assert _lines(d)["funding"]["actual_fen"] == 138132 and d["cost"]["actual"]["amount_fen"] == 138132 + 84157
    assert d["cost"]["difference_fen"] == 138132 and d["cost"]["unmeasured_fen"] == 0
    assert d["cost"]["actual"]["note_text"] == ("Includes ¥841.57 of funding planned when you agreed. "
                                                "Includes ¥1,381.32 of funding on top of the terms you agreed. "
                                                "The early payment did not arrive, so no discount has been given under the agreement.")
    _check_sums(d)


def test_the_busy_books_agreed_deal(api: TestClient) -> None:
    # the busy seed holds no agreement now (Slice B): the deal is agreed through the routes the web uses, on invoice RCV-A
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    assert not [x for x in api.get("/decisions", params={"family": "DEAL"}).json()["decisions"] if x["state"] == "AGREED"]
    ids = [f"deal:{agree_on_rcv_a(api)}"]
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
    funding = [x for x in d["cost"]["lines"] if x["key"] not in ("terms", "planned_funding")]
    assert len(funding) == 1 and funding[0]["certainty"] == "ATTRIBUTED"
    assert funding[0]["actual_fen"] is None and funding[0]["actual_display"] is None
    assert funding[0]["actual_note_text"] == "This funding followed late payments from several buyers, so it is not counted in this deal's cost."
    assert "The records do not show how much of it this deal caused" in funding[0]["certainty_text"] and funding[0]["counted"] is False
    assert d["cost"]["difference_fen"] == 0 and d["cost"]["actual"]["amount_fen"] == 84157 and d["cost"]["to_come"]["amount_fen"] is None and d["cost"]["related_fen"] == 138132
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
            if line["key"] not in ("terms", "planned_funding") and line["actual_fen"] is not None:
                counted[line["evidence_href"]] = counted.get(line["evidence_href"], 0) + 1
    assert all(n == 1 for n in counted.values()) and not counted  # here no tracker counts it
    d = _tracker(api, did)
    assert _lines(d)["funding"]["actual_fen"] is None and d["cost"]["difference_fen"] == 0 and d["cost"]["actual"]["amount_fen"] == 84157
    zh = _tracker(api, did, "zh")["cost"]["lines"][2]
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
    assert d["cost"]["actual"]["amount_fen"] == 480996 and d["cost"]["unmeasured_fen"] == 0 and d["cost"]["difference_fen"] == 178219
    late = next(p for p in d["promises"] if p["state"] == "paid_late")
    assert late["tone"] == "warn" and late["state_word"] == ("Paid late" if lang == "en" else "逾期支付") and "34" not in late["detail_text"]
    assert d["promise_counts"]["buyer_kept"] == 1 and d["promise_counts"]["buyer_paid_late"] == 1
    if lang == "en":
        assert late["detail_text"].endswith("2 days ago, 2 days late.") or "days late" in late["detail_text"]
        assert d["promise_counts"]["text"] == "The buyer has kept one of two promises on this deal; one was paid late."
        assert d["closeout_text"] == ("This deal cost ¥4,809.96 against ¥3,027.77 expected, including ¥1,782.19 of funding on top. "
                                      "The buyer kept 1 of 2 promises; 1 was paid late.")
        assert d["headline_text"] == "This deal closed with extra cost on top of the terms you agreed" and d["state_word"] == "Paid late"
        assert d["state_text"] == "The buyer paid the early part it promised. Every invoice on this deal has been paid."
    else:
        assert "¥4,809.96" in d["closeout_text"] and "¥1,782.19" in d["closeout_text"] and re.search(r"[\u4e00-\u9fff]", d["closeout_text"])
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


BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def _pay(api: TestClient, key: str, amount: int, rid: str = "RCV-A") -> str:
    version = api.get("/mandate").json()["mandate"]["version"]
    r = api.post("/operations", headers=BANK, json={"kind": "RECEIVE_PAYMENT", "op_id": key, "idempotency_key": key, "mandate_version": version,
                                                    "requested_by": "SYSTEM", "receivable_id": rid, "amount_fen": amount, "bank_reference": "B-" + key})
    return str(r.json()["result"]["status"])


def _money_and_promises(d: dict[str, Any]) -> dict[str, Any]:
    return {"cost": d["cost"], "promises": d["promises"], "counts": d["promise_counts"], "stages": d["stages"], "headline": d["headline_text"],
            "state_text": d["state_text"], "word": d["state_word"]}


def test_a_whole_invoice_paid_at_face_after_the_early_payment_lapsed_gave_no_discount(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 3})
    assert _tracker(api, did)["promises"][0]["state"] == "missed"
    assert _pay(api, "all", 42_000_000) == "EXECUTED"  # the whole ¥420,000.00 at face: cash shows no discount
    d = _tracker(api, did)
    assert _lines(d)["terms"]["actual_fen"] == 0 and d["cost"]["actual"]["amount_fen"] == 84157  # only the planned funding
    assert d["closeout_text"].startswith("This deal cost ¥841.57 against ¥3,027.77 expected")
    assert "2,186.20" not in d["closeout_text"] and d["promise_counts"]["buyer_kept"] == 1  # the invoice promise is kept, the early one is not
    _check_sums(d)


def test_paying_the_whole_invoice_before_the_promised_day_keeps_the_promise_and_ends_the_deal(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 1})
    assert _pay(api, "all", 42_000_000) == "EXECUTED"
    d = _tracker(api, did)
    early = d["promises"][0]
    assert early["state"] == "kept" and early["state_word"] == "Paid in full, without the discount" and early["tone"] == "ok"
    assert d["closeout_text"] is not None and d["promise_counts"]["buyer_kept"] == 2 and _lines(d)["terms"]["actual_fen"] == 0
    assert d["headline_text"] != "This deal ended with the buyer's promise missed" and all(s["state"] == "done" for s in d["stages"])
    api.post("/clock/advance", json={"to_day": 34})  # and it stays ended when the commitment lapses
    again = _tracker(api, did)
    assert again["closeout_text"] is not None and again["promise_counts"]["buyer_kept"] == 2 and again["state_word"] != "Promise missed"
    assert _tracker(api, did, "zh")["promises"][0]["state_word"] == "已全额付清（未享受折扣）"


def test_a_refused_receipt_changes_nothing_in_the_read(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    api.post("/clock/advance", json={"to_day": 30})
    assert _pay(api, "rest", 16_280_000) == "EXECUTED"
    api.post("/clock/advance", json={"to_day": 40})
    before = _money_and_promises(_tracker(api, did))
    assert [p["state"] for p in before["promises"] if p["party"] == "buyer"] == ["kept", "kept"]
    assert _pay(api, "stray", 100) == "REFUSED"
    assert _money_and_promises(_tracker(api, did)) == before


def test_the_expected_cost_is_the_two_stored_components_and_the_gap_plan_ran(api: TestClient) -> None:
    did = _agree(api)
    d = _tracker(api, did)
    terms, planned = d["cost"]["lines"]
    assert (terms["expected_fen"], planned["expected_fen"]) == (218620, 84157) and terms["expected_fen"] + planned["expected_fen"] == 302777
    record = api.get(f"/decisions/{did}").json()
    assert any(o["kind"] == "DRAW_FACILITY" and o["status"] == "EXECUTED" for o in record["operations"])  # the planned funding ran
    assert planned["label"] == "Funding planned when you agreed" and planned["actual_fen"] == 84157 and d["cost"]["unmeasured_fen"] == 0


def test_the_related_funding_switch_counts_only_late_payment_funding(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.deal_tracker as tracker

    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    approval = _cure(api)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    on = _tracker(api, did)
    assert tracker.COUNT_RELATED_FUNDING is True
    f = _lines(on)["funding"]
    assert (f["relation"], f["counted"], f["actual_fen"], f["certainty"]) == ("after_late_payment", True, 178219, "ATTRIBUTED")
    assert on["cost"]["actual"]["amount_fen"] == 480996 and on["cost"]["difference_fen"] == 178219 == on["cost"]["related_fen"]
    monkeypatch.setattr(tracker, "COUNT_RELATED_FUNDING", False)
    off = _tracker(api, did)
    f = _lines(off)["funding"]
    assert (f["relation"], f["counted"], f["actual_fen"]) == ("after_late_payment", False, None) and f["related_fen"] == 178219
    assert off["cost"]["actual"]["amount_fen"] == 302777 and off["cost"]["difference_fen"] == 0 and off["cost"]["related_fen"] == 178219
    assert "set not to count" in f["actual_note_text"]
    _check_sums(off)


def test_a_cure_is_counted_in_neither_tracker_when_the_buyer_has_a_second_late_deal(api: TestClient, rt: Runtime) -> None:
    did = _agree(api)
    _to_day34(api)
    first = rt.store.commitments()[0]
    second = first.model_copy(update={"id": "CMT-second-deal", "offer_id": "OFF-second-deal", "nonce": "second-deal-nonce"})
    rt.store.put_commitment(second)
    approval = _cure(api)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    trackers = [_tracker(api, did), _tracker(api, "deal:OFF-second-deal")]
    assert all(x["available"] for x in trackers)
    for x in trackers:
        later = [ln for ln in x["cost"]["lines"] if ln["key"] not in ("terms", "planned_funding")]
        assert later and all(ln["counted"] is False and ln["actual_fen"] is None for ln in later), x["cost"]["lines"]
        assert "several of this buyer's deals" in later[0]["actual_note_text"] and x["cost"]["difference_fen"] == 0
        assert x["cost"]["related_fen"] == 138132


def test_funding_on_time_then_a_cure_is_not_related_by_lateness(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    api.post("/clock/advance", json={"to_day": 30})
    assert _pay(api, "rest", 16_280_000) == "EXECUTED"  # on time: it was due on day 32
    api.post("/clock/advance", json={"to_day": 34})
    action = api.get("/home").json()["next_action"]
    if action is not None:
        api.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    d = _tracker(api, did)
    assert all(ln["relation"] != "after_late_payment" for ln in d["cost"]["lines"] if ln["key"] not in ("terms", "planned_funding"))
    assert d["cost"]["difference_fen"] == 0 and [p["state"] for p in d["promises"] if p["party"] == "buyer"] == ["kept", "kept"]


def test_an_invoice_that_failed_is_not_late_and_the_deal_is_not_ended(api: TestClient, rt: Runtime) -> None:
    did = _agree(api)
    _to_day34(api)
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"receivables": [r.model_copy(update={"status": "FAILED"}) if r.id == "RCV-A" else r
                                                                for r in state.receivables]}))
    d = _tracker(api, did)
    inv = [p for p in d["promises"] if p["party"] == "buyer"][1]
    assert inv["state"] == "failed" and inv["state_word"] == "Failed" and d["closeout_text"] is None
    assert d["headline_text"] != "This deal closed as expected" and d["state_word"] in ("Promise missed", "Payment failed")


def test_the_buyer_text_is_the_behaviour_sentence_or_null_never_the_count_again(api: TestClient) -> None:
    d = _tracker(api, _agree(api))
    assert d["buyer"]["text"] != d["promise_counts"]["text"] and (d["buyer"]["text"] is None or isinstance(d["buyer"]["text"], str))


def test_no_english_sentence_is_left_in_chinese(api: TestClient) -> None:
    did = _agree(api)
    names = ["Foshan Home Retail Co.", "FLOW"]
    for day in (None, 2, 30, 34):
        if day is not None:
            api.post("/clock/advance", json={"to_day": day})
        for key, text in _texts(_tracker(api, did, "zh")):
            cleaned = text
            for n in names:
                cleaned = cleaned.replace(n, " ")
            assert not re.search(r"[A-Za-z]{3,}", cleaned), (key, text)


def test_a_day_five_cure_on_the_busy_books_is_never_counted_in_the_agreed_deal(api: TestClient) -> None:
    """Only the other buyer (Dongguan, overdue from the first day) is late on day 5, so the cure quoted then is not this deal's to count."""
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    did = f"deal:{agree_on_rcv_a(api)}"  # the busy seed holds no agreement now: agree one the way the web does
    api.post("/clock/advance", json={"to_day": 5})
    alert = next(a for a in api.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")
    assert api.post(f"/alerts/{alert['id']}/act").status_code == 200
    d = _tracker(api, did)
    later = [ln for ln in d["cost"]["lines"] if ln["key"] not in ("terms", "planned_funding")]
    assert all(ln["counted"] is False and ln["actual_fen"] is None for ln in later)
    assert d["cost"]["difference_fen"] == 0
    _check_sums(d)


def test_a_cure_that_finances_the_deals_own_invoice_is_shown_as_secured_and_never_counted(api: TestClient) -> None:
    """The verifier's day-3 case: the early payment has lapsed but the invoice is not due, so nobody is late; the cure FLOW quotes finances
    this deal's own invoice."""
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/clock/advance", json={"to_day": 3})
    action = api.get("/home").json()["next_action"]
    assert action is not None and "invoice" in str(action["suggestions"]).lower()
    assert api.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"],
                                                              "suggestions": action["suggestions"]}).status_code == 200
    for a in [x for x in api.get("/approvals/queue").json()["approvals"] if x["status"] == "PENDING"]:
        api.post(f"/approvals/{a['id']}", json={"decision": "APPROVE"})
    for lang in ("en", "zh"):
        d = _tracker(api, did, lang)
        [line] = [x for x in d["cost"]["lines"] if x["key"] not in ("terms", "planned_funding")]
        assert line["relation"] == "secured_on_invoice" and line["counted"] is False and line["actual_fen"] is None
        assert line["figure_fen"] is not None and line["figure_fen"] == line["related_fen"] and line["figure_display"]
        assert line["counted_note_text"] and line["certainty"] == "QUOTED"
        assert d["cost"]["difference_fen"] == 0 and d["cost"]["related_fen"] == line["figure_fen"]
        if lang == "en":
            assert "secured on one of this deal's invoices" in line["certainty_text"]
            assert "records do not show how much of it this deal caused" in line["certainty_text"]
        _check_sums(d)


def test_every_line_has_its_own_figure_and_the_headline_follows_the_counted_total_only(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.deal_tracker as tracker

    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    approval = _cure(api)
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    on = _tracker(api, did)
    assert [x["figure_fen"] for x in on["cost"]["lines"]] == [218620, 84157, 178219]
    assert all(x["counted_note_text"] is None for x in on["cost"]["lines"]) and on["headline_text"] == "This deal is costing more than you agreed to"
    monkeypatch.setattr(tracker, "COUNT_RELATED_FUNDING", False)
    off = _tracker(api, did)
    assert [x["figure_fen"] for x in off["cost"]["lines"]] == [218620, 84157, 178219]
    assert [x["actual_fen"] for x in off["cost"]["lines"]] == [218620, 84157, None]
    assert off["cost"]["lines"][2]["counted_note_text"] == off["cost"]["lines"][2]["actual_note_text"] and off["cost"]["lines"][2]["counted_note_text"]
    assert off["headline_text"] == "The buyer is late on this deal"
    assert off["cost"]["actual"]["tone"] == "neutral" and off["cost"]["difference_fen"] == 0
    assert off["state_text"] == on["state_text"]
    zh = _tracker(api, did, "zh")["cost"]["lines"][2]
    assert re.search(r"[\u4e00-\u9fff]", zh["counted_note_text"])


def _offer_evaluated(api: TestClient) -> tuple[str, str]:
    offer = api.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()
    return str(offer), str(v["decision_id"])


def test_an_invoice_paid_before_the_cure_was_quoted_is_not_late_for_that_cure(api: TestClient) -> None:
    """Paid on the quote day, but earlier in the log than the quote: the cure is not 'after this buyer's late payment', and a cure that is
    not related to the deal never reopens it."""
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    api.post("/clock/advance", json={"to_day": 30})
    api.post("/clock/advance", json={"to_day": 34})
    assert _pay(api, "rest", 16_280_000) == "EXECUTED"
    before = _tracker(api, did)
    assert before["closeout_text"] is not None
    action = api.get("/home").json()["next_action"]
    assert action is not None
    assert api.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]}).status_code == 200
    queued = _tracker(api, did)
    assert queued["closeout_text"] is not None and queued["cost"]["actual"]["amount_fen"] == before["cost"]["actual"]["amount_fen"]
    for a in [x for x in api.get("/approvals/queue").json()["approvals"] if x["status"] == "PENDING"]:
        api.post(f"/approvals/{a['id']}", json={"decision": "APPROVE"})
    after = _tracker(api, did)
    assert after["closeout_text"] == before["closeout_text"] and after["cost"]["difference_fen"] == 0
    assert all(ln["relation"] != "after_late_payment" for ln in after["cost"]["lines"])
    assert after["cost"]["actual"]["amount_fen"] == before["cost"]["actual"]["amount_fen"]


def test_evaluated_today_and_agreed_tomorrow_keeps_the_agreed_discount_and_shows_the_plan_that_ran(api: TestClient, rt: Runtime) -> None:
    """Evaluated on day 0, agreed on day 1 without the state version: the terms are the discount as agreed (218,620), the planned funding
    was quoted at 84,157 and the plan that ran cost 81,527; the funding's change of price is not a change in the terms."""
    offer, did = _offer_evaluated(api)
    api.post("/clock/advance", json={"to_day": 1})
    assert api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    d = _tracker(api, did)
    supplier, plan = _stored_split(rt)
    assert supplier == 302777 and plan == 81527  # the SENT fact: the supplier cost priced at evaluation, the plan that ran at the send
    terms, planned = d["cost"]["lines"]
    assert (terms["expected_fen"], planned["expected_fen"]) == (218620, 84157) and d["cost"]["expected"]["amount_fen"] == supplier
    assert planned["actual_fen"] == planned["figure_fen"] == 81527 and d["cost"]["unmeasured_fen"] == 0
    assert planned["actual_note_text"] == "The plan that ran cost ¥815.27 against ¥841.57 quoted."
    assert d["cost"]["actual"]["amount_fen"] == 81527 and d["agreed_text"] == "Agreed today"
    _check_sums(d)


def test_a_send_after_a_receipt_on_the_invoice_is_closed(api: TestClient) -> None:
    # the path the verifier used (a receipt on the invoice, then a send without the version check) is closed: the offer has lapsed
    offer, _did = _offer_evaluated(api)
    assert _pay(api, "face", 1_000_000) == "EXECUTED"
    closed = api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"})
    assert closed.status_code == 409


def test_a_receipt_at_face_right_after_the_agreement_books_no_discount(api: TestClient) -> None:
    agreed = _agree(api)
    assert _pay(api, "face-2", 42_000_000) == "EXECUTED"
    d = _tracker(api, agreed)
    assert _lines(d)["terms"]["actual_fen"] == 0 and d["cost"]["actual"]["amount_fen"] == 84157
    _check_sums(d)


def test_the_headline_after_the_agreement_says_the_planned_funding_has_run_and_agreed_text_is_given(api: TestClient) -> None:
    did = _agree(api)
    d = _tracker(api, did)
    assert d["headline_text"] == "The planned funding has run; the buyer's payment is still awaited" and d["agreed_text"] == "Agreed today"
    api.post("/clock/advance", json={"to_day": 2})
    assert _tracker(api, did)["agreed_text"] == "Agreed 2 days ago"
    assert re.search(r"[\u4e00-\u9fff]", _tracker(api, did, "zh")["agreed_text"]) and "天前" in _tracker(api, did, "zh")["agreed_text"]


def test_every_deal_state_dev_has_reads_without_an_error_and_is_available_only_with_an_agreement(api: TestClient, rt: Runtime) -> None:
    """On the busy books after one agreement the other Foshan replies are LAPSED; the seed also holds received, clarification and response
    states. Each answers 200: available exactly when the decision has an agreement, else a sentence."""
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    agreed = f"deal:{agree_on_rcv_a(api)}"
    api.post("/clock/advance", json={"to_day": 34})
    seen: dict[str, bool] = {}
    for row in api.get("/decisions", params={"family": "DEAL", "limit": 200}).json()["decisions"]:
        r = api.get(f"/decisions/{row['id']}/tracker")
        assert r.status_code == 200, (row["state"], r.text)
        d = r.json()
        has_agreement = bool([c for c in rt.store.commitments() if f"deal:{c.offer_id}" == row["id"]])
        assert d["available"] is has_agreement, (row["state"], d["unavailable_text"])
        assert (d["unavailable_text"] is None) == d["available"]
        seen[row["state"]] = d["available"]
    assert "LAPSED" in seen and seen["LAPSED"] is False
    assert any(seen.get(k) for k in ("AGREED", "MISSED", "FULFILLED", "EXPIRED", "REVOKED")) and _tracker(api, agreed)["available"]


def _stored_split(rt: Runtime) -> tuple[int, int]:
    """(supplier cost, gap plan cost) as the SENT fact stored them."""
    import json

    sent = next(json.loads(f.body_json) for f in rt.store.decision_facts() if f.fact == "SENT")
    return int(sent["counter_economics"]["supplier_cost_fen"]), int(sent["gap_plan"]["total_cost_fen"])


def test_the_expected_columns_are_the_stored_facts_whatever_the_cash_does_afterwards(api: TestClient, rt: Runtime) -> None:
    did = _agree(api)
    supplier, plan = _stored_split(rt)
    expected = lambda d: [(x["key"], x["expected_fen"]) for x in d["cost"]["lines"]]
    before = _tracker(api, did)
    assert expected(before) == [("terms", 218620), ("planned_funding", 84157)] and supplier - plan == 218620 and plan == 84157
    api.post("/clock/advance", json={"to_day": 1})
    assert _pay(api, "part", 1_000_000) == "EXECUTED"  # a part early payment shrinks the reconciliation's current posted discount
    after = _tracker(api, did)
    assert expected(after) == expected(before) and after["cost"]["unmeasured_fen"] == 0
    assert after["cost"]["expected"]["amount_fen"] == supplier
    _check_sums(after)


def test_a_revoked_agreement_keeps_its_split_and_says_the_terms_were_withdrawn(api: TestClient, rt: Runtime) -> None:
    from app.domain.models import CommitmentStatus

    did = _agree(api)
    supplier, plan = _stored_split(rt)
    first = rt.store.commitments()[0]
    rt.store.put_commitment(first.model_copy(update={"status": CommitmentStatus.REVOKED}))
    assert _pay(api, "all", 42_000_000) == "EXECUTED"
    d = _tracker(api, did)
    assert [x["expected_fen"] for x in d["cost"]["lines"]] == [218620, 84157] and supplier - plan == 218620
    assert d["cost"]["unmeasured_fen"] == 0 and d["cost"]["actual"]["amount_fen"] == plan
    assert d["closeout_text"] is not None and "withdrawn before the discount was given" in d["closeout_text"]
    assert "never measured" not in d["closeout_text"] and _lines(d)["terms"]["actual_note_text"] == "The agreement was withdrawn before the discount was given."
    zh = _tracker(api, did, "zh")
    assert "撤回" in zh["closeout_text"]
    _check_sums(d)


def test_a_cure_quoted_while_the_buyer_was_late_counts_whether_it_is_approved_before_or_after_the_buyer_pays(api: TestClient) -> None:
    did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _to_day34(api)
    approval = _cure(api)  # queued while the rest of the invoice is late
    assert _pay(api, "rest", 16_280_000) == "EXECUTED"  # the buyer pays, then the owner approves
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    d = _tracker(api, did)
    f = _lines(d)["funding"]
    assert (f["relation"], f["counted"], f["actual_fen"]) == ("after_late_payment", True, 178219)
    assert d["cost"]["actual"]["amount_fen"] == 480996 and d["cost"]["difference_fen"] == 178219 == d["cost"]["related_fen"]
    _check_sums(d)


def test_the_unavailable_read_has_a_sentence_for_each_reason(api: TestClient) -> None:
    offer, did = _offer_evaluated(api)
    assert _tracker(api, did)["unavailable_text"] == "This deal has not been agreed yet, so there is nothing to track."
    sent = api.post(f"/negotiate/{offer}", json={"buyer_profile": "hard_line"}).json()
    assert sent["outcome"] == "NO_DEAL"
    assert _tracker(api, did)["unavailable_text"] == "No deal was agreed on this offer, so there is nothing to track."
    assert re.search(r"[\u4e00-\u9fff]", _tracker(api, did, "zh")["unavailable_text"])


def test_a_lapsed_offer_and_a_funding_decision_have_their_own_sentences(api: TestClient) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    agree_on_rcv_a(api)
    lapsed = [x for x in api.get("/decisions", params={"family": "DEAL", "limit": 200}).json()["decisions"] if x["state"] == "LAPSED"]
    assert lapsed
    assert _tracker(api, lapsed[0]["id"])["unavailable_text"] == "This offer lapsed before it was agreed, so there is nothing to track."
    assert re.search(r"[\u4e00-\u9fff]", _tracker(api, lapsed[0]["id"], "zh")["unavailable_text"])
    funding = [x for x in api.get("/decisions", params={"family": "FUNDING", "limit": 200}).json()["decisions"]]
    if funding:
        assert "funding decision" in _tracker(api, funding[0]["id"])["unavailable_text"]
