"""Slice B round two, the server words batch (feat/slice-b-r2-api): the negotiations' own counts, a distinct subject and a lifecycle for each negotiation,
the funding assumption and the terms days of each path, the send receipt's three statements, the cost as table rows, the Customer's relationship
sentence, flow and comparison, and the Approvals' exact-authorization words. On the busy books and the golden story (EX01 on the Demo), in both languages."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.approval_review import approval_review
from app.api.runtime import Runtime, set_runtime
from app.api.subjects import LIFECYCLE, lifecycle_text
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy import exposure as assembly
from tests.api.conftest import agree_on_rcv_a, english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai",
         "Bank credit line", "Invoice financing (onboarded platform)", "Government-guaranteed working-capital loan"]
RAW_ID = re.compile(r"\b(?:RCV|BUYER|FAC|LOT|CMT|OFF|CTR|VER|OP|APR|DOC)-[A-Za-z0-9]|RI:|\bday -?\d|\bNone\b")
QUOTED = re.compile(r"“[^”]*”")  # the buyer's own words, in whatever language it wrote them
HREFS = r".*href"


@pytest.fixture
def rt(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, assembly.clear_cache, offer_picture._cache.clear):
        clear()
    yield runtime
    set_runtime(None)
    for clear in (worklist.clear_cache, customer_overview.clear_cache, assembly.clear_cache, offer_picture._cache.clear):
        clear()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


def _busy(api: TestClient) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200


def _golden(api: TestClient, lang: str = "en") -> tuple[str, dict[str, Any]]:
    """EX01 on the Demo: the offer id and its evaluate view."""
    offer_id = str(api.post("/offers", json=EX01).json()["offer"]["offer_id"])
    view: dict[str, Any] = api.post(f"/offers/{offer_id}/evaluate", params={"lang": lang}, json=EX01).json()
    return offer_id, view


def _queue(api: TestClient, lang: str = "en") -> dict[str, Any]:
    r = api.get("/deals", params={"lang": lang})
    assert r.status_code == 200, r.text
    q: dict[str, Any] = r.json()["queue"]
    return q


def _negotiation_rows(q: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in (*q["needs_you"], *q["waiting"], *q["agreements"]) if r["kind"] in ("DECISION", "BUYER_REPLY", "AGREEMENT")]


def _bare(text: str) -> str:
    """A subject without the buyer's quoted words, for the leak check."""
    return QUOTED.sub("", text)


# ---------------------------------------------------------------- 1. queue.deals


def test_deals_counts_are_the_negotiations_only_and_the_other_counts_stay(api: TestClient) -> None:
    _busy(api)
    q = _queue(api)
    # five decisions (Zhuhai, Dongguan, Foshan x3) and the Foshan clarification; the collection and the approval are Home's, in `counts` only
    assert q["deals"] == {"needs_you": 5, "waiting": 1, "agreements": 0}
    assert q["counts"] == {"needs_you": 7, "waiting": 1, "agreements": 0, "customers": 3}
    assert q["deals"]["needs_you"] == sum(1 for r in q["needs_you"] if r["kind"] == "DECISION")
    assert {r["kind"] for r in q["needs_you"]} == {"DECISION", "COLLECTION", "APPROVAL"}  # the tiers still hold them for Home
    assert _queue(api, "zh")["deals"] == q["deals"]


def test_an_agreement_and_its_promise_are_counted_under_agreements(api: TestClient) -> None:
    _busy(api)
    agree_on_rcv_a(api)
    q = _queue(api)
    agreements = [r for r in q["agreements"]]
    assert {r["kind"] for r in agreements} == {"AGREEMENT", "PROMISE"}
    assert q["deals"]["agreements"] == len(agreements) == q["counts"]["agreements"]
    assert all(r["lifecycle"] == "agreed" and r["status_text"] == "Agreed" for r in agreements if r["kind"] == "AGREEMENT")


def test_the_golden_story_has_one_decision(api: TestClient) -> None:
    _golden(api)
    assert _queue(api)["deals"] == {"needs_you": 1, "waiting": 0, "agreements": 0}


# ---------------------------------------------------------------- 2. subjects


BUSY_SUBJECTS_EN = {
    "Zhuhai": ["Zhuhai · 75-day terms on the next invoice"],
    "Dongguan": ["Dongguan · 1% rebate next quarter"],
    "Foshan": ["Foshan · 60-day terms on future invoices and 2 more terms",
               "Foshan · Early payment, 1.5% off · “Early pay at 1.5%”",
               "Foshan · Early payment, 1.5% off · “pay this one early at 1.5%”",
               "Foshan · 1% rebate, scope to confirm"],
}


def test_every_negotiation_has_its_own_subject_in_words_on_the_busy_books(api: TestClient) -> None:
    _busy(api)
    rows = _negotiation_rows(_queue(api))
    by_customer: dict[str, list[str]] = {}
    for r in rows:
        by_customer.setdefault(r["customer_short"], []).append(r["subject_text"])
    assert {k: sorted(v) for k, v in by_customer.items()} == {k: sorted(v) for k, v in BUSY_SUBJECTS_EN.items()}
    for subjects in by_customer.values():
        assert len(subjects) == len(set(subjects))  # no two open negotiations of one customer share a subject
    assert not [r["subject_text"] for r in rows if RAW_ID.search(r["subject_text"])]  # Business shows no id
    # the Demo's text is the same words with the offer's id
    for r in rows:
        assert r["subject_demo_text"].startswith(r["subject_text"] + " · OFF-")
    # a row that is not a negotiation has none
    other = [r for r in (*_queue(api)["needs_you"],) if r["kind"] in ("COLLECTION", "APPROVAL")]
    assert other and all(r["subject_demo_text"] is None and r["lifecycle"] is None for r in other)


def test_the_subjects_agree_across_the_queue_the_worklist_the_decisions_and_the_overview(api: TestClient) -> None:
    _busy(api)
    queue_rows = {r["decision_id"]: r["subject_text"] for r in _negotiation_rows(_queue(api))}
    work = api.get("/worklist").json()
    assert {r["key"].partition(":")[2]: r["subject_text"] for r in work["needs_you"] if r["kind"] == "DECISION"} == {
        k.partition(":")[2]: v for k, v in queue_rows.items() if k.startswith("deal:") and v and not v.endswith("1% rebate, scope to confirm")}
    listed = {d["id"]: d for d in api.get("/decisions", params={"family": "DEAL"}).json()["decisions"]}
    for did, subject in queue_rows.items():
        assert listed[did]["subject_text"] == subject
        detail = api.get(f"/decisions/{quote(did, safe='')}").json()
        assert detail["subject_text"] == subject and detail["subject_demo_text"].endswith(did.partition(":")[2])
    over = api.get("/customers/BUYER-1/overview").json()["open_negotiations"]
    assert sorted(r["subject_text"] for r in over) == sorted(BUSY_SUBJECTS_EN["Foshan"])
    assert all(r["decision_id"] in queue_rows and queue_rows[r["decision_id"]] == r["subject_text"] for r in over)


def test_the_golden_story_subject(api: TestClient) -> None:
    _golden(api)
    [row] = _negotiation_rows(_queue(api))
    assert row["subject_text"] == "Foshan · 60-day terms on future invoices and 2 more terms"


def test_subjects_in_chinese_are_distinct_and_carry_no_english_but_the_names_and_the_buyers_quotes(api: TestClient) -> None:
    _busy(api)
    zh = _negotiation_rows(_queue(api, "zh"))
    en = _negotiation_rows(_queue(api, "en"))
    assert [r["decision_id"] for r in zh] == [r["decision_id"] for r in en]
    for cid in {r["customer_id"] for r in zh}:
        mine = [r["subject_text"] for r in zh if r["customer_id"] == cid]
        assert len(mine) == len(set(mine))
    assert "Zhuhai · 75 天账期（下一张发票）" in [r["subject_text"] for r in zh]
    assert "Dongguan · 下季度 1% 返利" in [r["subject_text"] for r in zh]
    assert not english_leaks({"s": [_bare(r["subject_text"]) for r in zh]}, NAMES)
    assert not [r["subject_text"] for r in zh if RAW_ID.search(r["subject_text"])]


def test_a_subject_does_not_change_when_a_sibling_negotiation_closes(api: TestClient) -> None:
    _busy(api)
    before = {r["decision_id"]: r["subject_text"] for r in _negotiation_rows(_queue(api))}
    agree_on_rcv_a(api)  # the EX03 early-payment offer is agreed; the other 1.5% offer lapses
    after = {r["decision_id"]: r["subject_text"] for r in _negotiation_rows(_queue(api))}
    for did, subject in after.items():
        assert before.get(did, subject) == subject


def test_a_negotiation_row_keeps_its_coarse_topic_for_a_sentence_that_names_it(api: TestClient) -> None:
    _busy(api)
    q = _queue(api)
    topics = {(r["customer_short"], r["kind"], r["topic_text"]) for r in _negotiation_rows(q)}
    assert {("Zhuhai", "DECISION", "Payment terms"), ("Dongguan", "DECISION", "Rebate"), ("Foshan", "BUYER_REPLY", "Rebate"),
            ("Foshan", "DECISION", "Payment terms"), ("Foshan", "DECISION", "Early-payment discount")} == topics
    assert all(r["topic_text"] is None for r in (*q["needs_you"], *q["waiting"]) if r["kind"] in ("COLLECTION", "APPROVAL"))
    zh = {r["topic_text"] for r in _negotiation_rows(_queue(api, "zh"))}
    assert zh == {"付款账期", "返利", "提前付款折扣"}


# ---------------------------------------------------------------- 3. lifecycle


def test_the_lifecycle_vocabulary_is_seven_keys_in_both_languages() -> None:
    assert LIFECYCLE == ("counter_ready", "owner_review", "awaiting_buyer", "more_information", "agreed", "declined", "lapsed")
    assert [lifecycle_text(k, "en") for k in LIFECYCLE] == ["Counter ready", "Owner review needed", "Awaiting buyer", "More information needed",
                                                          "Agreed", "Declined", "Lapsed"]
    assert [lifecycle_text(k, "zh") for k in LIFECYCLE] == ["还价已就绪", "需要您审核", "等待买方回复", "需要更多信息", "已达成", "已拒绝", "已失效"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_queue_and_worklist_rows_carry_the_lifecycle_and_severity_stays_separate(api: TestClient, lang: str) -> None:
    _busy(api)
    rows = _negotiation_rows(_queue(api, lang))
    seen = {r["subject_text"].split(" · ")[0] + ":" + r["kind"]: r for r in rows}
    assert all(r["lifecycle"] in LIFECYCLE and r["status_text"] == lifecycle_text(r["lifecycle"], lang) for r in rows)
    assert {r["lifecycle"] for r in rows if r["kind"] == "BUYER_REPLY"} == {"more_information"}
    assert {r["lifecycle"] for r in rows if r["kind"] == "DECISION" and r["customer_short"] == "Foshan"} == {"counter_ready"}
    pairs = {(r["severity"], r["lifecycle"]) for r in rows if r["kind"] == "DECISION"}
    assert {r["severity"] for r in rows} <= {"CRITICAL", "CAUTION", "NORMAL"}
    assert {("CAUTION", "counter_ready"), ("CRITICAL", seen["Zhuhai:DECISION"]["lifecycle"])} <= pairs  # the risk mark varies on its own, whatever the status
    work = api.get("/worklist", params={"lang": lang}).json()["needs_you"]
    assert all(r["lifecycle"] in LIFECYCLE and r["status_text"] == lifecycle_text(r["lifecycle"], lang) for r in work if r["kind"] == "DECISION")
    assert all(r["lifecycle"] is None for r in work if r["kind"] != "DECISION")


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_decision_read_carries_the_lifecycle(api: TestClient, lang: str) -> None:
    _busy(api)
    agree_on_rcv_a(api)
    rows = api.get("/decisions", params={"lang": lang, "family": "DEAL"}).json()["decisions"]
    assert {d["lifecycle"] for d in rows} >= {"agreed"}
    assert all(d["lifecycle"] in LIFECYCLE and d["status_text"] == lifecycle_text(d["lifecycle"], lang) for d in rows)
    funding = api.get("/decisions", params={"lang": lang, "family": "FUNDING"}).json()["decisions"]
    assert all(d["lifecycle"] is None and d["status_text"] is None and d["subject_text"] is None for d in funding)
    detail = api.get(f"/decisions/{quote(rows[0]['id'], safe='')}", params={"lang": lang}).json()
    assert detail["lifecycle"] == rows[0]["lifecycle"] and detail["state_text"]  # the existing state words stay


def test_a_declined_negotiation_is_declined(api: TestClient) -> None:
    _golden(api)
    offer = api.get("/deals").json()["deals"][0]["open_offer"]["offer_id"]
    api.post(f"/negotiate/{offer}", json={"buyer_profile": "hard_line"})
    did = f"deal:{offer}"
    detail = api.get(f"/decisions/{quote(did, safe='')}").json()
    assert detail["lifecycle"] in ("declined", "agreed", "awaiting_buyer", "owner_review", "counter_ready")
    assert detail["status_text"] == lifecycle_text(detail["lifecycle"], "en")


# ---------------------------------------------------------------- 4. the funding assumption and the terms days


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_each_path_says_its_funding_assumption_and_its_terms_days(api: TestClient, lang: str) -> None:
    offer_id, _ = _golden(api, lang)
    pic = api.get(f"/offers/{offer_id}/picture", params={"lang": lang}).json()
    assert pic["current_terms_days"] == 45
    asked, a, b = pic["paths"]
    assert (asked["terms_days"], a["terms_days"], b["terms_days"]) == (60, 45, 55)
    assert asked["funding_assumption_text"] == {"en": "No new funding", "zh": "不新增融资"}[lang]
    assert a["funding_assumption_text"] == {"en": "Funding plan required: ¥150k credit-line draw today",
                                            "zh": "需要融资方案：信用额度提款 ¥150k（今天）"}[lang]
    assert b["funding_assumption_text"].startswith({"en": "Funding plan required: ", "zh": "需要融资方案："}[lang])
    if lang == "zh":
        assert not english_leaks({"p": [p["funding_assumption_text"] for p in pic["paths"]]}, NAMES)


def test_a_reply_that_needs_no_funding_says_so_and_the_busy_paths_have_days(api: TestClient) -> None:
    _busy(api)
    for deal in api.get("/deals").json()["deals"]:
        offer = deal["open_offer"]
        if offer is None:
            continue
        pic = api.get(f"/offers/{offer['offer_id']}/picture").json()
        if not pic["available"]:
            continue
        assert pic["current_terms_days"] is None or isinstance(pic["current_terms_days"], int)  # null for a buyer with no recurring invoice
        for p in pic["paths"]:
            assert p["terms_days"] is None or isinstance(p["terms_days"], int)
            assert p["funding_assumption_text"] and "None" not in p["funding_assumption_text"]
            if p["kind"] == "asked":
                assert p["funding_assumption_text"] == "No new funding"


def test_the_unavailable_picture_still_names_the_current_terms(api: TestClient) -> None:
    _busy(api)
    agree_on_rcv_a(api)
    lapsed = [d["open_offer"] for d in api.get("/deals").json()["deals"] if d["open_offer"]]
    for offer in lapsed:
        pic = api.get(f"/offers/{offer['offer_id']}/picture").json()
        assert "current_terms_days" in pic


def test_the_recommendation_reason_names_what_it_turns_on(api: TestClient) -> None:
    from app.api.offer_picture import FLOW_MAY, NEEDS_OWNER, OVER_LIMIT, _reason_kind

    offer_id, _ = _golden(api)
    paths = api.get(f"/offers/{offer_id}/picture").json()["paths"]
    recommended = [p for p in paths if p["recommended"]]
    assert [p["recommended_reason_kind"] for p in recommended] == ["cash"]  # the request breaches the reserve, Option A does not
    assert all(p["recommended_reason_kind"] is None for p in paths if not p["recommended"])
    assert recommended[0]["recommended_reason_text"]  # beside the existing sentence
    _busy(api)
    kinds = []
    for deal in api.get("/deals").json()["deals"]:
        if deal["open_offer"] is None:
            continue
        pic = api.get(f"/offers/{deal['open_offer']['offer_id']}/picture").json()
        for p in pic["paths"]:
            if p["recommended"] and p["kind"] == "reply":
                assert p["recommended_reason_kind"] in ("cost", "cash", "authority")
                breaches = next(x for x in pic["paths"] if x["kind"] == "asked")["first_breach_when"] is not None
                assert (p["recommended_reason_kind"] == "cash") == (breaches and p["first_breach_when"] is None)
                kinds.append(p["recommended_reason_kind"])
    assert "cash" in kinds
    # the rule itself: cash first, then authority, else cost
    assert _reason_kind(True, False, True, FLOW_MAY) == "cash" and _reason_kind(True, True, True, NEEDS_OWNER) == "authority"
    assert _reason_kind(False, False, True, OVER_LIMIT) == "cost" and _reason_kind(False, False, False, FLOW_MAY) == "cost"


# ---------------------------------------------------------------- 5. the send receipt


GOLDEN_RECEIPT = {
    "en": {"authorizes_text": "Send the exact Option A counter to Foshan; FLOW records it as a proposed agreement that stands only if Foshan accepts.",
           "remaining_text": "The terms take effect only when Foshan accepts; no payment and no financing settles because the counter is sent."},
    "zh": {"authorizes_text": "向Foshan原样发送方案 A 的还价；FLOW 将其记为拟议中的协议，只有Foshan接受后才成立。",
           "remaining_text": "只有Foshan接受后条款才会生效；发送还价本身不会结算任何付款或融资。"},
}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_send_receipt_has_three_exact_statements_specific_to_this_send(api: TestClient, lang: str) -> None:
    _, view = _golden(api, lang)
    pr = view["workspace"]["priced_response"]
    r = pr["receipt"]
    assert r["authorizes_text"] == GOLDEN_RECEIPT[lang]["authorizes_text"] == pr["send_scope_lines"][0]
    assert r["remaining_text"] == GOLDEN_RECEIPT[lang]["remaining_text"]
    assert "（" not in r["authorizes_text"] and "(" not in r["authorizes_text"]  # no parenthetical about approval
    assert "approval" not in r["authorizes_text"] and "批准" not in r["authorizes_text"]  # authority is said once, in `authority_text`
    assert r["authority_text"] == {"en": "FLOW can send it. Your approval is not needed.", "zh": "FLOW 可以发送。无需您批准。"}[lang]
    assert r["executes_now_text"] == ("; " if lang == "en" else "；").join(pr["send_scope_lines"][1:])  # the gap plan's draw, then its cost
    assert ("Draws ¥149,986.20" if lang == "en" else "提款 ¥149,986.20") in r["executes_now_text"]
    if lang == "zh":
        assert not english_leaks({"receipt": r}, NAMES)


def test_every_priced_reply_names_its_own_option_in_what_it_authorizes(api: TestClient) -> None:
    _, view = _golden(api)
    texts = [p["receipt"]["authorizes_text"] for p in view["workspace"]["priced_responses"]]
    assert len(texts) == len(set(texts)) >= 1
    for p in view["workspace"]["priced_responses"]:
        assert f"Send the exact {p['label_text']} counter to Foshan;" in p["receipt"]["authorizes_text"]


def test_a_send_that_runs_no_funding_says_why() -> None:
    from app.api.receipt import send_receipt

    base: dict[str, Any] = {"buyer": "Foshan Home Retail Co.", "lines": ["x"], "recheck_text": None, "cost_display": None, "funds_when": None,
                            "funds_today": False, "authority_text": None, "who": "Foshan"}
    said = {s: send_receipt("en", funding=s, option="Option A", **base)["executes_now_text"] for s in ("none_needed", "cannot_run", "no_plan", "unknown")}
    assert all(v.startswith("No funding runs when you send") for v in said.values()) and len(set(said.values())) == 4
    declined = send_receipt("en", funding="none_needed", if_declined_lines=["Draws ¥1 today"], option="Option A", **base)
    assert declined["executes_now_text"].startswith("No funding runs when you send if the buyer agrees")  # it still runs if the buyer declines
    zh = send_receipt("zh", funding="no_plan", option="方案 A", **base)
    assert zh["executes_now_text"].startswith("发送时不会办理融资") and not english_leaks({"z": zh}, NAMES + ["x"])


def test_the_busy_books_receipts_are_exact_for_their_own_option(api: TestClient) -> None:
    _busy(api)
    offer = next(d["open_offer"]["offer_id"] for d in api.get("/deals").json()["deals"] if d["counterparty_id"] == "BUYER-1")
    view = api.post(f"/offers/{offer}/evaluate", json=EX01).json()
    for p in view["workspace"]["priced_responses"]:
        assert p["receipt"]["remaining_text"] == GOLDEN_RECEIPT["en"]["remaining_text"]
        assert p["receipt"]["authorizes_text"].startswith("Send the exact Option")


# ---------------------------------------------------------------- 6. the cost rows


def _fen(display: str) -> int:
    return round(float(display.replace("¥", "").replace(",", "")) * 100)


def _rows(path: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["key"]: r for r in path["cost_rows"]}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_cost_rows_are_table_rows_with_the_totals_basis_as_it_is_today(api: TestClient, lang: str) -> None:
    offer_id, _ = _golden(api, lang)
    pic = api.get(f"/offers/{offer_id}/picture", params={"lang": lang}).json()
    asked, a, b = pic["paths"]
    for p in pic["paths"]:
        assert all(set(r) == {"key", "label", "amount_display", "basis_text"} for r in p["cost_rows"])
        assert p["cost_rows"][0]["key"] == "immediate_discount" and p["cost_rows"][-1]["key"] == "total"
        total = _rows(p)["total"]
        assert total["basis_text"] == p["cost_basis_text"] and total["amount_display"] == p["cost_total_display"]  # the basis exactly as today
    assert a["cost_components"] == [] and [c["display"] for c in b["cost_components"]][:2] == ["¥16,217.95", "¥16,380.00"]  # the existing field is untouched
    ra, rb = _rows(asked), _rows(a)
    assert [ra[k]["amount_display"] for k in ("immediate_discount", "payment_terms", "rebate", "funding", "total")] == [
        "¥5,040.00", "¥24,326.92", "¥4,000.00", None, None]  # the asked path: two horizons, never added, no total
    assert [rb[k]["amount_display"] for k in ("immediate_discount", "payment_terms", "rebate", "funding", "total")] == [
        "¥2,186.20", None, None, "¥841.57", "¥3,027.77"]  # Option A: the discount and the funding add up to its once-cost
    assert rb["total"]["basis_text"] == {"en": "once, nothing ongoing", "zh": "一次性，之后无持续成本"}[lang]
    assert ra["total"]["basis_text"] == {"en": "two parts: once, and over 12 months", "zh": "两部分：一次性，以及 12 个月内"}[lang]
    assert ra["payment_terms"]["basis_text"] == {"en": "over 12 months", "zh": "12 个月内"}[lang]  # a horizon is said, never normalised
    assert ra["immediate_discount"]["basis_text"] == {"en": "once", "zh": "一次性"}[lang]


def test_option_b_nets_a_price_offset_in_its_own_row(api: TestClient) -> None:
    offer_id, _ = _golden(api)
    b = api.get(f"/offers/{offer_id}/picture").json()["paths"][2]
    rows = _rows(b)
    assert [r["key"] for r in b["cost_rows"]] == ["immediate_discount", "payment_terms", "rebate", "price_offset", "funding", "total"]
    assert rows["payment_terms"]["amount_display"] == "¥16,217.95" and rows["price_offset"]["amount_display"] == "−¥16,380.00"
    assert rows["total"]["basis_text"] == "net over 12 months" and rows["immediate_discount"]["amount_display"] is None


def test_cost_rows_of_the_busy_books_reconcile_with_their_totals(api: TestClient) -> None:
    _busy(api)
    for deal in api.get("/deals").json()["deals"]:
        if deal["open_offer"] is None:
            continue
        pic = api.get(f"/offers/{deal['open_offer']['offer_id']}/picture").json()
        for p in pic["paths"]:
            assert p["cost_rows"] and all(isinstance(r["basis_text"], str) and r["basis_text"] for r in p["cost_rows"])
            assert not [r for r in p["cost_rows"] if "None" in (r["amount_display"] or "")]
            rows = _rows(p)
            if p["kind"] == "reply" and "price_offset" not in rows and rows["total"]["amount_display"] and not (
                    rows["payment_terms"]["amount_display"] or rows["rebate"]["amount_display"]):
                once = [rows[k]["amount_display"] for k in ("immediate_discount", "funding") if rows[k]["amount_display"]]
                assert sum(_fen(x) for x in once) == _fen(rows["total"]["amount_display"])  # a once-only reply: the parts add up to the total


# ---------------------------------------------------------------- 7. the Customer overview


def _overview(api: TestClient, cid: str, lang: str = "en") -> dict[str, Any]:
    r = api.get(f"/customers/{cid}/overview", params={"lang": lang})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def test_the_golden_story_relationship_sentence_and_decision(api: TestClient) -> None:
    _golden(api)
    ov = _overview(api, "BUYER-1")
    assert ov["relationship_text"] == ("Foshan contributes an estimated ¥1.09m a year, owes ¥420k (100% of your open receivables), "
                                      "and has one negotiation that could change your cash.")
    fig = {f["key"]: f for f in ov["figures"]}
    assert fig["financing"]["note"] == "¥255k financing planned against Foshan's invoice · not yet received"  # the golden plan finances ¥255k
    assert ov["primary_decision"]["text"] == "Foshan has one commercial decision requiring your response."
    assert ov["primary_decision"]["recommends_text"] == "FLOW recommends Option A."
    assert ov["primary_decision"]["href"] == ov["decision"]["primary"]["href"]
    assert ov["other_open_count"] == 0 and [r["is_primary"] for r in ov["open_negotiations"]] == [True]


def test_the_busy_books_metrics_say_the_exact_words(api: TestClient) -> None:
    _busy(api)
    ov = _overview(api, "BUYER-1")
    fig = {f["key"]: f for f in ov["figures"]}
    assert ov["relationship_text"] == ("Foshan contributes an estimated ¥1.09m a year, owes ¥420k (54.5% of your open receivables), "
                                      "and has four negotiations that could change your cash.")
    assert fig["financing"]["note"] == "¥336k financing planned against Foshan's invoice · not yet received" and fig["financing"]["value_display"] == "¥336,000"
    assert fig["share"]["note"] == "54.5% of currently open receivables" and fig["share"]["value_display"] == "54.5%"
    zh = {f["key"]: f for f in _overview(api, "BUYER-1", "zh")["figures"]}
    assert zh["financing"]["note"] == "计划融资 ¥336k，以Foshan的发票做融资 · 尚未到账"
    assert zh["share"]["note"] == "占当前未收应收款的 54.5%"


def test_the_busy_books_primary_decision_and_the_others(api: TestClient) -> None:
    _busy(api)
    ov = _overview(api, "BUYER-1")
    assert ov["relationship_text"].endswith("and has four negotiations that could change your cash.")
    assert ov["primary_decision"]["text"] == "Foshan has three commercial decisions requiring your response."
    assert ov["primary_decision"]["recommends_text"] == "FLOW recommends Option A."
    assert ov["other_open_count"] == 3 == len(ov["open_negotiations"]) - 1
    assert ov["open_negotiations"][0]["is_primary"] and [r["lifecycle"] for r in ov["open_negotiations"]].count("more_information") == 1
    dong = _overview(api, "BUYER-2")  # an overdue invoice and one open offer
    assert dong["primary_decision"]["text"] == "Dongguan has one commercial decision requiring your response."
    assert dong["other_open_count"] == 0


def test_a_customer_with_no_negotiation_has_no_primary_decision(api: TestClient) -> None:
    _golden(api)
    ov = _overview(api, "BUYER-2")
    assert ov["primary_decision"] is None and ov["other_open_count"] == 0 and ov["open_negotiations"] == []
    assert ov["relationship_text"].endswith("has no open negotiation.")


def test_the_flow_follows_the_plan_from_planned_to_arranged(api: TestClient) -> None:
    _busy(api)
    flow = _overview(api, "BUYER-1")["receivable_flow"]
    assert [s["key"] for s in flow] == ["owed", "financing", "arrives", "customer_pays", "repayment", "net"]
    assert all(set(s) == {"key", "label", "amount_display", "when_text", "note", "href"} for s in flow)
    by = {s["key"]: s for s in flow}
    assert by["owed"]["amount_display"] == "¥420,000.00" and by["owed"]["label"] == "Foshan owes you"
    assert by["financing"]["label"] == "Financing planned" and by["financing"]["amount_display"] == "¥336,000.00"
    assert by["arrives"]["when_text"] == "in 3 days if the plan runs"
    assert (by["customer_pays"]["amount_display"], by["customer_pays"]["when_text"]) == ("¥420,000.00", "due in 32 days")
    assert (by["repayment"]["amount_display"], by["repayment"]["note"]) == ("¥338,994.08", "¥336,000 advance plus ¥2,994.08 in charges")
    assert by["net"]["amount_display"] == "about ¥81,010" and by["net"]["note"] == "if Foshan pays on the due day"
    a = api.get("/home").json()["next_action"]  # run the plan: the same figures now come from the lot and the receivables read
    assert api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()["executed"] == 2
    row = next(r for r in api.get("/receivables").json()["rows"] if r["receivable_id"] == "RCV-A")
    ran = {s["key"]: s for s in _overview(api, "BUYER-1")["receivable_flow"]}
    assert ran["financing"]["label"] == "Financing arranged" and ran["repayment"]["amount_display"] == "¥338,994.08"
    assert ran["net"]["amount_display"] == row["net_after_repayment_display"] == "about ¥81,010" and ran["arrives"]["when_text"] == "arrives in 3 days"


def test_the_golden_flow_has_the_golden_plans_figures(api: TestClient) -> None:
    _golden(api)
    by = {s["key"]: s for s in _overview(api, "BUYER-1")["receivable_flow"]}
    assert by["financing"]["amount_display"] == "¥255,000.00" and by["owed"]["amount_display"] == "¥420,000.00"


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_flow_in_both_languages(api: TestClient, lang: str) -> None:
    _busy(api)
    flow = _overview(api, "BUYER-1", lang)["receivable_flow"]
    assert [s["amount_display"] for s in flow if s["key"] in ("owed", "financing", "arrives", "customer_pays")] == ["¥420,000.00", "¥336,000.00",
                                                                                                                  "¥336,000.00", "¥420,000.00"]
    assert all(s["when_text"] is None or s["when_text"] == s["when_text"].strip() for s in flow)  # no stray space before a Chinese distance
    if lang == "zh":
        assert not english_leaks({"f": flow}, NAMES, raw_fields=[HREFS])
        assert {s["key"]: s["when_text"] for s in flow}["arrives"] == "执行方案后 3 天后到账"


def test_with_no_financing_linked_the_flow_is_two_steps(api: TestClient) -> None:
    _busy(api)
    flow = _overview(api, "BUYER-2")["receivable_flow"]  # Dongguan's overdue invoice: nothing financed, nothing planned
    assert [s["key"] for s in flow] == ["owed", "customer_pays"]
    assert flow[1]["when_text"] == "overdue by 30 days"
    assert _overview(api, "BUYER-3")["receivable_flow"] == [] or len(_overview(api, "BUYER-3")["receivable_flow"]) == 2


def test_the_flow_chooses_the_largest_open_invoice(api: TestClient) -> None:
    _busy(api)
    ov = _overview(api, "BUYER-1")
    assert ov["receivable_flow"][0]["amount_display"] == "¥420,000.00"


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_exposure_comparison_is_four_rows_of_two_columns(api: TestClient, lang: str) -> None:
    _golden(api)
    cmp = _overview(api, "BUYER-1", lang)["exposure_comparison"]
    assert [c["key"] for c in cmp["columns"]] == ["expected", "late"]
    assert [c["label"] for c in cmp["columns"]] == {"en": ["Expected payment", "30 days late"], "zh": ["按期付款", "晚付 30 天"]}[lang]
    assert [r["label"] for r in cmp["rows"]] == {"en": ["Lowest cash", "Reserve breach", "Maximum shortfall", "Additional funding needed"],
                                                 "zh": ["最低现金", "储备缺口", "最大缺口", "需要额外融资"]}[lang]
    assert all(set(r) == {"label", "expected_text", "late_text"} and r["expected_text"] and r["late_text"] for r in cmp["rows"])
    assert not [r for r in cmp["rows"] if "None" in r["expected_text"] + r["late_text"]]
    # the late column is the stress sentence's own figures (the lowest point and the uncovered need)
    ex = api.get("/buyers/BUYER-1/exposure", params={"lang": lang}).json()
    assert ex["stress"]["now"]["lowest_fen"] is not None
    if lang == "zh":
        assert not english_leaks({"c": cmp}, NAMES)


def test_the_exposure_comparison_is_null_while_the_exposure_is_off(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_EXPOSURE")
    customer_overview.clear_cache()
    _golden(api)
    ov = _overview(api, "BUYER-1")
    assert ov["exposure"] is None and ov["exposure_comparison"] is None and ov["relationship_text"]


def _strings(x: Any) -> Iterator[tuple[str, str]]:
    if isinstance(x, dict):
        for k, v in x.items():
            for path, text in _strings(v):
                yield f"{k}.{path}" if path else k, text
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)
    elif isinstance(x, str):
        yield "", x


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_customer_words_carry_no_id_and_no_english_in_chinese(api: TestClient, lang: str) -> None:
    _busy(api)
    ov = _overview(api, "BUYER-1", lang)
    words = {k: ov[k] for k in ("relationship_text", "receivable_flow", "exposure_comparison", "primary_decision", "open_negotiations")}
    sentences = [(p, s) for p, s in _strings(words) if not p.endswith(("href", "decision_id", "subject_demo_text"))]
    assert not [(p, s) for p, s in sentences if RAW_ID.search(s)]
    if lang == "zh":
        bare = [(p, _bare(s)) for p, s in sentences]
        assert not english_leaks({"w": [s for _, s in bare]}, NAMES)


# ---------------------------------------------------------------- 8. the Approvals' exact authorization


APPLY_EN = {"commit_label": "Authorize the application",
            "authorize_text": "Approval sends an application to the lender. It does not mean the loan is approved or that funds have arrived.",
            "terms_state_text": "Loan terms are not yet confirmed: you are authorizing an application, not accepting a financing offer."}


def _apply(api: TestClient, lang: str) -> dict[str, Any]:
    _busy(api)
    return next(a for a in api.get("/approvals/queue", params={"lang": lang}).json()["approvals"] if a["kind"] == "APPLY_FOR_FACILITY")


def test_an_application_waiting_for_approval_says_exactly_what_it_authorizes(api: TestClient) -> None:
    item = _apply(api, "en")
    assert {k: item[k] for k in APPLY_EN} == APPLY_EN and item["terms_rows"] == []
    assert [(s["label"], s["state"]) for s in item["lifecycle"]] == [("You authorize", "current"), ("Lender reviews", "next"), ("Funding decision", "next")]
    assert all(set(s) == {"label", "text", "state"} for s in item["lifecycle"])
    rows = item["summary_rows"]
    assert [r["label"] for r in rows] == ["Amount requested", "Facility", "What happens now", "Does money move now",
                                          "Who decides whether funds are offered", "What if you decline"]
    values = {r["label"]: r["value_text"] for r in rows}
    assert values["Amount requested"] == "¥200,000.00" == item["receipt"]["gross_display"]
    assert values["Facility"] == "Government-guaranteed working-capital loan"
    assert values["What if you decline"] == item["presentation"]["if_decline"] == "Nothing runs; the request is closed."
    assert values["Does money move now"].startswith("No.") and all(v for v in values.values())
    assert item["receipt"] and item["presentation"]  # every existing field stays


def test_an_application_in_chinese(api: TestClient) -> None:
    item = _apply(api, "zh")
    assert item["commit_label"] == "授权提交申请" and item["terms_state_text"] and item["authorize_text"].startswith("批准后")
    assert [s["state"] for s in item["lifecycle"]] == ["current", "next", "next"]
    assert len(item["summary_rows"]) == 6
    assert not english_leaks({k: item[k] for k in ("commit_label", "authorize_text", "terms_state_text", "terms_rows", "lifecycle", "summary_rows")}, NAMES)


def test_the_lifecycle_never_shows_a_stage_done_before_it_is(api: TestClient) -> None:
    item = _apply(api, "en")
    decided = api.post(f"/approvals/{item['id']}", json={"decision": "APPROVE"})
    assert decided.status_code == 200, decided.text
    after = next(a for a in api.get("/approvals/queue").json()["approvals"] if a["id"] == item["id"])
    assert after["status"] == "APPROVED" and after["summary_rows"] is None
    if after["lifecycle"] is not None:
        states = [s["state"] for s in after["lifecycle"]]
        assert states == ["done", "current", "next"]  # authorized, with the lender; the lender's answer is not on the books


def test_a_declined_application_has_no_lifecycle_to_follow(api: TestClient) -> None:
    item = _apply(api, "en")
    assert api.post(f"/approvals/{item['id']}", json={"decision": "REJECT"}).status_code == 200
    after = next(a for a in api.get("/approvals/queue").json()["approvals"] if a["id"] == item["id"])
    assert after["lifecycle"] is None and after["summary_rows"] is None and after["commit_label"] == "Authorize the application"


def test_other_kinds_are_named_by_what_they_do() -> None:
    def review(kind: str, lang: str = "en") -> dict[str, Any]:
        return approval_review(lang, item={"kind": kind, "status": "PENDING", "presentation": {"facility_name": "F", "if_decline": "x"},
                                            "quote": None, "receipt": {"gross_display": "¥1.00", "executes_now_text": "e"}})

    assert review("REPAY_FACILITY")["commit_label"] == "Authorize the repayment"
    assert review("REPAY_FACILITY", "zh")["commit_label"] == "授权还款"
    assert review("RECORD_COMMITMENT")["commit_label"] == "Authorize the agreement" and review("RECORD_COMMITMENT")["summary_rows"] is None
    assert review("DRAW_FACILITY")["terms_state_text"] is None and review("DRAW_FACILITY")["lifecycle"] is None
    assert len(review("DRAW_FACILITY")["summary_rows"]) == 6


def test_a_quote_with_terms_shows_them_and_drops_the_not_confirmed_sentence() -> None:
    quote_with_terms = {"total_fen": 84157, "total_display": "¥841.57", "lands_when": "in 3 days", "rate_basis": "11.2% a year",
                        "lines": [{"amount_display": "¥150,000.00", "cost_fen": 84157, "cost_display": "¥841.57", "rate_text": "11.2%",
                                   "lands_when": "in 3 days"}]}
    got = approval_review("en", item={"kind": "APPLY_FOR_FACILITY", "status": "PENDING", "quote": quote_with_terms, "presentation": {}, "receipt": None})
    assert got["terms_state_text"] is None
    assert got["terms_rows"] == [{"label": "Amount", "value_text": "¥150,000.00"}, {"label": "Cost", "value_text": "¥841.57"},
                                 {"label": "Rate", "value_text": "11.2%"}, {"label": "Cash lands", "value_text": "in 3 days"},
                                 {"label": "Basis", "value_text": "11.2% a year"}]
    assert approval_review("en", item={"kind": "APPLY_FOR_FACILITY", "status": "PENDING", "quote": {"lines": [{"amount_display": "¥1"}]},
                                       "presentation": {}, "receipt": None})["terms_state_text"] == APPLY_EN["terms_state_text"]


# ---------------------------------------------------------------- the web's six words


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_picture_names_the_current_terms_and_how_far_each_path_is_from_them(api: TestClient, lang: str) -> None:
    offer_id, _ = _golden(api, lang)
    pic = api.get(f"/offers/{offer_id}/picture", params={"lang": lang}).json()
    assert pic["current_terms_text"] == {"en": "45 days", "zh": "45 天"}[lang] and pic["current_terms_days"] == 45
    asked, a, b = pic["paths"]
    assert [p["terms_delta_text"] for p in (asked, a, b)] == {
        "en": ["+15 days requested by buyer", "no change", "+10 days in this counter"],
        "zh": ["买方要求延长 15 天", "无变化", "此还价延长 10 天"]}[lang]
    if lang == "zh":
        assert not english_leaks({"d": [p["terms_delta_text"] for p in pic["paths"]], "c": pic["current_terms_text"]}, NAMES)


def test_a_path_with_unknown_terms_has_no_delta_and_a_shorter_term_says_so() -> None:
    from app.api.offer_picture import _terms_delta

    assert _terms_delta("en", None, 45, "asked") is None and _terms_delta("en", 60, None, "reply") is None
    assert _terms_delta("en", 30, 45, "asked") == "−15 days requested by buyer" and _terms_delta("zh", 30, 45, "reply") == "此还价缩短 15 天"
    assert _terms_delta("en", 46, 45, "reply") == "+1 day in this counter"


def test_the_busy_pictures_carry_the_current_terms_text_or_null(api: TestClient) -> None:
    _busy(api)
    for deal in api.get("/deals").json()["deals"]:
        if deal["open_offer"] is None:
            continue
        pic = api.get(f"/offers/{deal['open_offer']['offer_id']}/picture").json()
        assert (pic["current_terms_text"] is None) == (pic["current_terms_days"] is None)
        if pic["current_terms_days"] is not None:
            assert pic["current_terms_text"] == f"{pic['current_terms_days']} days"
            for p in pic["paths"]:
                assert (p["terms_delta_text"] is None) == (p["terms_days"] is None)


def test_the_share_figure_carries_the_proportion_the_word_is_built_from(api: TestClient) -> None:
    _busy(api)
    ov = _overview(api, "BUYER-1")
    fig = {f["key"]: f for f in ov["figures"]}
    assert 0 <= fig["share"]["proportion"] <= 1 and f"{fig['share']['proportion'] * 100:.1f}%" == fig["share"]["value_display"] == "54.5%"
    assert all("proportion" not in f for k, f in fig.items() if k != "share")
    assert _overview(api, "BUYER-1", "zh")["figures"][3]["proportion"] == fig["share"]["proportion"]


def test_the_golden_story_owes_all_of_it_to_foshan(api: TestClient) -> None:
    _golden(api)
    assert {f["key"]: f for f in _overview(api, "BUYER-1")["figures"]}["share"]["proportion"] == 1.0


def test_aggregate_buyers_have_no_proportion() -> None:
    from types import SimpleNamespace

    assert customer_overview._proportion(SimpleNamespace(conc={"is_aggregate": True, "ar_total_fen": 10, "ar_buyer_fen": 5})) is None
    assert customer_overview._proportion(SimpleNamespace(conc={"is_aggregate": False, "ar_total_fen": 0, "ar_buyer_fen": 0})) is None
    assert customer_overview._proportion(SimpleNamespace(conc=None)) is None


def test_the_flow_steps_and_the_links_carry_their_pages(api: TestClient) -> None:
    _busy(api)
    invoice = "/receivables?customer=BUYER-1&invoice=RCV-A&from=customer"
    ov = _overview(api, "BUYER-1")
    by = {s["key"]: s["href"] for s in ov["receivable_flow"]}
    assert by == {"owed": invoice, "financing": "/cash#facility-FAC-IF", "arrives": "/cash#facility-FAC-IF", "customer_pays": invoice,
                  "repayment": "/cash#facility-FAC-IF", "net": None}
    deal = ov["primary_decision"]["decision_id"]
    assert ov["links"] == [{"label": "The negotiation", "href": f"/deals?customer=BUYER-1&decision={quote(deal, safe='')}"},
                           {"label": "The invoice", "href": invoice}, {"label": "The financing", "href": "/cash#facility-FAC-IF"},
                           {"label": "Payment status: Not due yet", "href": invoice}]
    a = api.get("/home").json()["next_action"]  # run the plan: the financing is then a request on the record
    assert api.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()["executed"] == 2
    ran = _overview(api, "BUYER-1")
    # the plan's requests have no record the owner can open yet, so the step points at the facility the lot was drawn on
    assert {s["key"]: s["href"] for s in ran["receivable_flow"]}["financing"] == "/cash#facility-FAC-IF"
    assert [lk["label"] for lk in ran["links"]] == ["The negotiation", "The invoice", "The financing", "Payment status: Not due yet"]
    zh = _overview(api, "BUYER-1", "zh")["links"]
    assert [lk["label"] for lk in zh] == ["谈判", "发票", "融资", "付款状态：未到期"]


def test_the_links_hold_only_what_exists(api: TestClient) -> None:
    _golden(api)
    assert _overview(api, "BUYER-2")["links"] == []  # no invoice, no financing, no negotiation
    assert _overview(api, "BUYER-1")["links"][0]["label"] == "The negotiation"
    _busy(api)
    dong = _overview(api, "BUYER-2")["links"]  # an overdue invoice and an open offer, nothing financed
    assert [lk["label"] for lk in dong] == ["The negotiation", "The invoice", "Payment status: Overdue"]
    assert dong[1]["href"] == "/receivables?customer=BUYER-2&invoice=RCV-B1&from=customer"


def test_queue_rows_say_when_they_last_moved(api: TestClient) -> None:
    _busy(api)
    q = _queue(api)
    rows = [*q["needs_you"], *q["waiting"], *q["agreements"]]
    assert all(set(r) >= {"last_activity_day", "last_activity_text"} for r in rows)
    for r in rows:
        assert (r["last_activity_day"] is None) == (r["last_activity_text"] is None)
        if r["kind"] in ("DECISION", "BUYER_REPLY"):
            assert r["last_activity_day"] == 0 and r["last_activity_text"] == "today"
        if r["kind"] == "COLLECTION":
            assert r["last_activity_day"] < 0 and r["last_activity_text"].endswith("days ago")
    work = api.get("/worklist").json()
    assert all(r["last_activity_day"] == 0 for r in work["needs_you"] if r["kind"] == "DECISION")
    assert all("last_activity_text" in r for r in work["waiting"])
    zh = _queue(api, "zh")
    assert {r["last_activity_text"] for r in zh["needs_you"] if r["kind"] == "DECISION"} == {"今天"}


def test_an_agreements_row_says_when_it_last_moved(api: TestClient) -> None:
    _busy(api)
    agree_on_rcv_a(api)
    rows = [r for r in _queue(api)["agreements"] if r["kind"] == "AGREEMENT"]
    assert rows and all(r["last_activity_day"] == 0 and r["last_activity_text"] == "today" for r in rows)


def _queued_counter(api: TestClient) -> None:
    from app.api.runtime import get_runtime

    api.post("/demo/reset", json={})
    offer_id = api.post("/offers", json=EX01).json()["offer"]["offer_id"]
    ev = api.post(f"/offers/{offer_id}/evaluate", json=EX01).json()
    verdict = ev.get("verdict", ev)
    commitment = get_runtime().executor.propose_commitment(verdict["id"], expires_day=14, counter_id=verdict["counters"][1]["id"])
    version = api.get("/mandate").json()["mandate"]["version"]
    r = api.post("/operations", headers={"X-Agent-Key": "demo-agent-key"}, json={
        "kind": "RECORD_COMMITMENT", "op_id": "rec-1", "idempotency_key": "rec-1", "mandate_version": version, "requested_by": "AGENT",
        "commitment_id": commitment.id, "nonce": commitment.nonce})
    assert r.json()["result"]["status"] == "PENDING_APPROVAL", r.text


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_waiting_agreement_says_when_it_expires_and_a_decided_one_says_nothing(api: TestClient, lang: str) -> None:
    _queued_counter(api)
    item = api.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]
    assert (item["deadline_day"], item["deadline_text"]) == (14, {"en": "Expires in 14 days", "zh": "14 天后到期"}[lang])
    assert item["commit_label"] == {"en": "Authorize the agreement", "zh": "授权记录协议"}[lang]
    assert api.post(f"/approvals/{item['id']}", json={"decision": "REJECT"}).status_code == 200
    after = api.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]
    assert after["deadline_text"] is None and after["deadline_day"] is None


def test_an_approval_with_no_deadline_says_none_and_the_words_are_by_kind() -> None:
    from app.api.approval_review import deadline_view

    assert deadline_view("APPLY_FOR_FACILITY", None, 0, "en") == {"deadline_day": None, "deadline_text": None}
    assert deadline_view("DRAW_FACILITY", 12, 0, "en")["deadline_text"] == "Cash needed in 12 days"
    assert deadline_view("DRAW_FACILITY", 0, 0, "zh")["deadline_text"] == "今天需要资金到位"
    assert deadline_view("RECORD_COMMITMENT", 1, 0, "en")["deadline_text"] == "Expires tomorrow"


def test_the_busy_application_has_no_deadline(api: TestClient) -> None:
    item = _apply(api, "en")
    assert item["deadline_text"] is None and item["deadline_day"] is None
