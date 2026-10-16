"""Slice B round three, the server words batch (feat/slice-b-r3-api): the per-path short words and the terms by scope, the recommendation, the scenarios,
the chart's pairs and the whole life of a deal. On the golden books (EX01, Option A and Option B), the busy books' Zhuhai deal (one request for the owner's
review, no counter) and the golden story walked to its end, in both languages."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy import exposure as assembly
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01, ZHUHAI = "EX01_PACKAGE", "EX09_TERMS_BUYER3"
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai",
         "Bank credit line", "Invoice financing (onboarded platform)", "Government-guaranteed working-capital loan"]
# an id, a day number, a raw enum or the word None in a sentence; "best" and "safe" are never said
BAD = re.compile(r"\b(?:RCV|BUYER|FAC|LOT|CMT|OFF|CTR|VER|OP|APR|DOC)-[A-Za-z0-9]|RI:|\bday -?\d|\bNone\b(?! in this scenario)|\bnull\b|\b(?:flow_may|needs_owner|over_limit)\b"
                 r"|(?i:\bbest\b|\bsafe\b|\bcheaper\b)")


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


def _evaluate(api: TestClient, fixture: str, lang: str = "en") -> str:
    offer_id: str = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
    r = api.post(f"/offers/{offer_id}/evaluate", params={"lang": lang}, json={"fixture_id": fixture})
    assert r.status_code == 200, r.text
    return offer_id


def _picture(api: TestClient, offer_id: str, lang: str = "en") -> dict[str, Any]:
    r = api.get(f"/offers/{offer_id}/picture", params={"lang": lang})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _golden(api: TestClient, lang: str = "en") -> tuple[str, dict[str, Any]]:
    offer_id = _evaluate(api, EX01, lang)
    return offer_id, _picture(api, offer_id, lang)


def _busy_zhuhai(api: TestClient, lang: str = "en") -> tuple[str, dict[str, Any]]:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    offer_id = _evaluate(api, ZHUHAI, lang)
    return offer_id, _picture(api, offer_id, lang)


def _by_label(pic: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {("asked" if p["kind"] == "asked" else p["label"]): p for p in pic["paths"]}


def _texts(x: Any, key_ok: Any = lambda k: k.endswith(("_text", "_short", "_display")) or k == "label") -> Iterator[tuple[str, str]]:
    """Every string under a key that is words (a `*_text`, `*_short`, `*_display` or `label`), with its dotted key."""
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, str) and key_ok(k):
                yield k, v
            else:
                yield from _texts(v, key_ok)
    elif isinstance(x, list):
        for v in x:
            yield from _texts(v, key_ok)


# ================================================================ task 1: per-path words and the terms by scope


def test_golden_day_zero_each_path_says_its_short_words(api: TestClient) -> None:
    _, pic = _golden(api)
    by = _by_label(pic)
    asked, a, b = by["asked"], by["Option A"], by["Option B"]
    assert [p["authority_short_text"] for p in (asked, a, b)] == ["Outside mandate", "Within your mandate", "Needs your approval"]
    assert asked["reserve_state_text"] == "Breached by ¥135k for 15 days" and asked["headroom_short"] == "−¥135k"
    assert a["reserve_state_text"] == b["reserve_state_text"] == "Held, no buffer at the lowest point"
    assert a["headroom_short"] == "¥0"
    assert asked["financing_needed_text"] == "None in this scenario"
    assert a["financing_needed_text"] == "¥150k credit-line draw today"
    assert b["financing_needed_text"] == "¥90k credit-line draw today, ¥315k invoice financing in 3 days"
    assert [p["buyer_status_text"] for p in (asked, a, b)] == ["Asked by Foshan", "Not yet sent", "Not yet sent"]
    assert (asked["economic_headline_text"], asked["economic_basis_text"]) == ("¥5,040.00 once, ¥28,326.92 over 12 months", "Two parts, not added together")
    assert (a["economic_headline_text"], a["economic_basis_text"]) == ("¥3,027.77", "One-off cost, nothing ongoing")
    assert (b["economic_headline_text"], b["economic_basis_text"]) == ("About ¥0", "Net economic cost over 12 months")


def test_the_lowest_day_is_the_day_of_the_lowest_point_and_the_figures_are_the_paths_own(api: TestClient) -> None:
    _, pic = _golden(api)
    floor = pic["floor_fen"]
    for p in pic["paths"]:
        low = min(p["series"], key=lambda pt: (pt["closing_fen"], pt["day"]))
        assert p["lowest_fen"] == low["closing_fen"]
        assert p["series"][[pt["day"] for pt in p["series"]].index(p["lowest_day"])]["closing_fen"] == p["lowest_fen"]
        assert (p["headroom_short"] == "¥0") == (p["lowest_fen"] == floor)


def test_the_terms_are_grouped_by_scope_and_an_untouched_scope_says_unchanged(api: TestClient) -> None:
    _, pic = _golden(api)
    by = _by_label(pic)
    for p in pic["paths"]:
        assert [(t["key"], t["scope"]) for t in p["terms"]] == [("payment_terms", "future_invoices"), ("early_payment", "existing_invoice"),
                                                                 ("rebate_or_price", "next_quarter")]
        assert [t["scope_label"] for t in p["terms"]] == ["Future invoices", "Existing invoice", "Next quarter"]
    cells = {k: {t["scope"]: t["cell_text"] for t in p["terms"]} for k, p in by.items()}
    assert cells["Option A"] == {"future_invoices": "45 days", "existing_invoice": "0.85% off ¥257,200.00", "next_quarter": "Not offered"}
    assert cells["Option B"]["existing_invoice"] == "Not offered" and cells["Option B"]["next_quarter"] == "0.30% price rise"
    # the round-two reading of `value_text` is as it was: null where the path carries nothing
    assert [t["value_text"] for t in by["Option A"]["terms"]] == ["45 days", "0.85% off ¥257,200.00", None]


# ================================================================ task 2: the recommendation


GOLDEN_RULE = "FLOW recommends the first reply it may send within your mandate; it does not rank replies by cost."


def test_golden_day_zero_recommendation(api: TestClient) -> None:
    _, pic = _golden(api)
    assert pic["recommendation"] == {
        "mandate_text": "Option A is the reply within your mandate.",
        "alternative_text": "Option B needs your approval for 55-day terms. Its net economic cost over 12 months is stated as about ¥0 under the model's assumptions.",
        "rule_text": GOLDEN_RULE}


def test_the_rule_sentence_is_the_agreed_words_in_both_languages(api: TestClient) -> None:
    """The rule sentence moved from the web dictionary (`deals.why.rule`, since deleted) to the server: it is pinned here, word for word."""
    _, pic = _golden(api)
    assert pic["recommendation"]["rule_text"] == "FLOW recommends the first reply it may send within your mandate; it does not rank replies by cost."
    _, zh = _golden_zh(api)
    assert zh["recommendation"]["rule_text"] == "FLOW 建议的是在您的授权范围内它可以发送的第一个回复；它不按成本对回复排序。"


def _golden_zh(api: TestClient) -> tuple[str, dict[str, Any]]:
    api.post("/demo/reset")
    offer_id = _evaluate(api, EX01, "zh")
    return offer_id, _picture(api, offer_id, "zh")


def test_a_request_with_no_reply_has_no_recommendation_and_never_a_500(api: TestClient) -> None:
    _, pic = _busy_zhuhai(api)
    assert [p["kind"] for p in pic["paths"]] == ["asked"]
    rec = pic["recommendation"]
    assert rec["mandate_text"] == "FLOW has no reply it can send within your mandate for this offer."
    assert rec["alternative_text"] is None and rec["rule_text"] == GOLDEN_RULE
    asked = pic["paths"][0]
    assert asked["authority_short_text"] == "Needs your approval"
    assert asked["buyer_status_text"] == "Asked by Zhuhai"
    assert asked["reserve_state_text"] and asked["financing_needed_text"] == "None in this scenario"
    assert {t["scope"] for t in asked["terms"]} == {"future_invoices", "existing_invoice", "next_quarter"}


def test_the_status_of_a_reply_follows_the_log_and_the_get_changes_nothing(api: TestClient, rt: Runtime) -> None:
    offer_id, before = _golden(api)
    version, log_length = rt.store.get_state().state_version, len(rt.store.operations())
    assert _picture(api, offer_id) == before and rt.store.get_state().state_version == version and len(rt.store.operations()) == log_length
    assert api.post(f"/negotiate/{offer_id}", json={"buyer_profile": "hard_line"}).json()["outcome"] == "NO_DEAL"
    after = _by_label(_picture(api, offer_id))
    assert after["asked"]["buyer_status_text"] == "Asked by Foshan"
    assert {after["Option A"]["buyer_status_text"], after["Option B"]["buyer_status_text"]} <= {"Sent, no agreement reached", "Not yet sent"}
    assert "Sent, no agreement reached" in {p["buyer_status_text"] for p in after.values()}


def test_the_new_words_hold_no_id_no_day_number_and_not_best_or_safe(api: TestClient) -> None:
    for pic in (_golden(api)[1], _busy_zhuhai(api)[1]):
        for key, text in _texts({"paths": pic["paths"], "recommendation": pic["recommendation"]}):
            assert not BAD.search(text), (key, text)


def test_the_new_words_are_in_chinese_with_no_english_left(api: TestClient) -> None:
    _, pic = _golden_zh(api)
    fields = ["authority_short_text", "reserve_state_text", "headroom_short", "financing_needed_text", "buyer_status_text",
              "economic_headline_text", "economic_basis_text", "economic_sentence_text"]
    words = {"paths": [{**{k: p[k] for k in fields}, "terms": [{k: t[k] for k in ("scope_label", "cell_text")} for t in p["terms"]]} for p in pic["paths"]],
             "recommendation": pic["recommendation"]}
    assert english_leaks(words, NAMES) == []
    by = _by_label(pic)
    assert by["asked"]["authority_short_text"] == "超出授权"
    assert by["方案 A"]["authority_short_text"] == "在您的授权范围内" and by["方案 B"]["authority_short_text"] == "需要您批准"
    assert pic["recommendation"]["alternative_text"].startswith("方案 B 需要您批准 55 天账期。")


# ================================================================ task 3: the scenarios


def _scenario_list(api: TestClient, offer_id: str, lang: str = "en") -> list[dict[str, Any]]:
    r = api.get(f"/offers/{offer_id}/scenarios", params={"lang": lang})
    assert r.status_code == 200, r.text
    found: list[dict[str, Any]] = r.json()["scenarios"]
    return found


def _scenarios(pic: dict[str, Any], api: TestClient | None = None) -> dict[str, dict[str, Any]]:
    """The scenario cards: the route's, found from the picture's own `scenarios_href`."""
    assert pic["scenarios"] == [] and pic["scenarios_href"].startswith("/offers/")
    assert api is not None
    r = api.get(pic["scenarios_href"])
    assert r.status_code == 200
    return {s["key"]: s for s in r.json()["scenarios"]}


def test_golden_scenarios_are_composed_from_the_compare_and_exposure_reads(api: TestClient) -> None:
    offer_id, pic = _golden(api)
    sc = _scenarios(pic, api)
    assert list(sc) == ["no_new_agreement", "late_30", "customer_loss"]
    assert [s["label"] for s in sc.values()] == ["Continue current position", "Buyer pays 30 days late", "Buyer stops placing new orders"]
    compare = api.get(f"/offers/{offer_id}/compare").json()["rows"]
    current = next(r for r in compare if r["key"] == "current")
    assert sc["no_new_agreement"]["assumption_text"] == current["assumption_text"]
    assert sc["no_new_agreement"]["rows"][2]["text"] == current["funding_text"]
    # late_30: one row per response, each the exposure read's own stress words
    stress = api.get(f"/offers/{offer_id}/exposure", params={"spare": 1}).json()["stress"]["paths"]
    late = sc["late_30"]
    assert [r["key"] for r in late["rows"]] == [p["key"] for p in pic["paths"]]
    for r in late["rows"]:
        assert r["text"] == stress[r["key"]]["text"] and r["lowest_short"] == stress[r["key"]]["lowest_short"]
    assert late["assumption_text"].startswith("If Foshan Home Retail Co. paid every invoice 30 days late (a test, not a forecast)")
    loss = sc["customer_loss"]
    assert loss["lost_billings_text"] == "About ¥5,460,000 a year of billings (projected from your books)"
    assert loss["cash_effect_text"].startswith("¥1,260,000 of receipts removed within the next 120 days; ¥420,000 still arrives.")
    assert loss["invoice_remains_text"] == "The ¥420,000 already invoiced (due in 32 days) is still paid."
    assert loss["assumption_text"].endswith("This is not a prediction.")


def test_scenarios_leave_the_picture_and_the_books_as_they_were(api: TestClient, rt: Runtime) -> None:
    offer_id, pic = _golden(api)
    version, log_length = rt.store.get_state().state_version, len(rt.store.operations())
    again = _picture(api, offer_id)
    assert again == pic and rt.store.get_state().state_version == version and len(rt.store.operations()) == log_length


def test_zhuhai_has_scenarios_and_the_scenario_words_are_clean_in_both_languages(api: TestClient) -> None:
    z_offer, zhuhai = _busy_zhuhai(api)
    z_cards = _scenario_list(api, z_offer)
    assert {s["key"] for s in z_cards} <= {"no_new_agreement", "late_30", "customer_loss"} and z_cards
    g_offer, _ = (lambda: (_evaluate(api, EX01), None))()
    for cards in (_scenario_list(api, g_offer), z_cards):
        for key, text in _texts(cards):
            assert not BAD.search(text), (key, text)
    api.post("/demo/reset")
    zg_offer = _evaluate(api, EX01, "zh")
    zh_cards = _scenario_list(api, zg_offer, "zh")
    assert english_leaks(_scenarios_words(zh_cards), NAMES + ["Foshan Home Retail Co."]) == []
    assert {s["key"]: s for s in zh_cards}["customer_loss"]["lost_billings_text"] == "每年约 ¥5,460,000 的开票额（根据您的账目推算）"


def _scenarios_words(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    drop = {"assumption_text", "text"}  # the engine's long assumption sentences are checked by the compare and exposure tests
    return [{k: v for k, v in s.items() if k not in drop and k != "rows"} for s in cards]


# ================================================================ task 4: the chart's pairs


def _point(path: dict[str, Any], day: int) -> dict[str, Any]:
    return next(pt for pt in path["series"] if pt["day"] == day)


def test_each_point_carries_the_pair_words_for_every_reply_and_every_reply_pair(api: TestClient) -> None:
    _, pic = _golden(api)
    by = _by_label(pic)
    asked, a, b = by["asked"], by["Option A"], by["Option B"]
    for day in (0, 2, 30):
        for path in (asked, a, b):
            cmp = _point(path, day)["comparison"]
            assert set(cmp) >= {a["key"], b["key"]}
        cmp = _point(asked, day)["comparison"]
        for reply in (a, b):
            got = cmp[reply["key"]]
            assert set(got) == {"asked_display", "reply_display", "difference_display", "cause_text", "cause_lines"}
            assert got["asked_display"] == _point(asked, day)["closing_display"] and got["reply_display"] == _point(reply, day)["closing_display"]
            diff = _point(reply, day)["closing_fen"] - _point(asked, day)["closing_fen"]
            assert got["difference_display"].lstrip("+−-¥").replace(",", "").startswith(str(abs(diff) // 100)) or diff == 0
        pair = _point(asked, day)["comparison_pairs"][f"{a['key']}:{b['key']}"]
        assert pair["asked_display"] == _point(a, day)["closing_display"] and pair["reply_display"] == _point(b, day)["closing_display"]
    # the round-two strip is still beside the map for the recommended reply
    old = _point(asked, 2)["comparison"]
    assert old["asked_display"] == _point(asked, 2)["closing_display"] and old["recommended_display"] == _point(a, 2)["closing_display"]


def test_the_cause_names_what_one_line_has_and_the_other_does_not(api: TestClient) -> None:
    _, pic = _golden(api)
    by = _by_label(pic)
    asked, a = by["asked"], by["Option A"]
    cause = _point(asked, 2)["comparison"][a["key"]]["cause_text"]
    assert "Option A:" in cause and "Accept their request:" in cause and "today" in cause and "in 2 days" in cause
    asked_part, reply_part = cause.split("Accept their request:")[1].split("Option A:")[0], cause.split("Option A:")[1]
    assert "Early payment" in asked_part and "draw" in reply_part.lower()
    assert not BAD.search(cause), cause
    # on day 0 the request has nothing yet that the reply lacks except what the reply draws
    day0 = _point(asked, 0)["comparison"][a["key"]]["cause_text"]
    assert "Accept their request:" not in day0


def test_the_pair_words_are_in_chinese_with_no_english_left(api: TestClient) -> None:
    _, pic = _golden_zh(api)
    by = _by_label(pic)
    cmp = _point(by["asked"], 2)["comparison"]
    words = [{k: v for k, v in cmp[by["方案 A"]["key"]].items()}, _point(by["asked"], 2)["comparison_pairs"][f"{by['方案 A']['key']}:{by['方案 B']['key']}"]]
    assert english_leaks(words, NAMES) == []


# ================================================================ task 5: the whole life of a deal (the golden story walked to its end)

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def _agree(api: TestClient) -> tuple[str, str]:
    offer = api.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": EX01}).json()
    assert api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    return str(offer), str(v["decision_id"])


def _group_row(api: TestClient, did: str, lang: str = "en") -> dict[str, Any]:
    q = api.get("/deals", params={"lang": lang}).json()["queue"]
    [row] = [r for r in q["agreements"] if r["kind"] == "AGREEMENT" and r["decision_id"] == did]
    assert row["after_group_label"] and not BAD.search(row["after_group_label"])
    return row


def _stages_everywhere(api: TestClient, offer: str, did: str, lang: str = "en") -> list[dict[str, Any]]:
    """The strip from the tracker read, the decision read and the picture read: the same function, so the same stages."""
    tracker = api.get(f"/decisions/{did}/tracker", params={"lang": lang}).json()
    decision = api.get(f"/decisions/{did}", params={"lang": lang}).json()
    picture = _picture(api, offer, lang)
    assert tracker["lifecycle_stages"] == decision["lifecycle_stages"] == picture["lifecycle_stages"]
    assert not tracker["available"] or tracker["stages"] == tracker["lifecycle_stages"]
    stages: list[dict[str, Any]] = tracker["lifecycle_stages"]
    assert 0 < len(stages) <= 7
    for s in stages:
        assert set(s) == {"key", "label", "state", "state_text", "when_text"}
    return stages


def test_the_strip_is_one_function_at_every_moment_of_the_golden_story(api: TestClient, rt: Runtime) -> None:
    offer = api.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    did = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": EX01}).json()["decision_id"]
    before = _stages_everywhere(api, offer, did)  # before agreement: the offer's stages
    assert [s["key"] for s in before] == ["received", "analysed", "reply_ready", "sent", "agreed"]
    assert [s["state"] for s in before] == ["done", "done", "now", "todo", "todo"] and before[0]["when_text"] == "today"
    assert api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    agreed = _stages_everywhere(api, offer, did)  # after it: the contract stages of this deal
    first = _group_row(api, did)  # nothing is overdue yet: money is still to come
    assert (first["after_group"], first["after_group_label"], first["lifecycle"]) == ("awaiting_payment", "Awaiting payment", "agreed")
    assert _group_row(api, did, "zh")["after_group_label"] == "等待付款"
    assert [s["key"] for s in agreed][-1] == "fulfilled" and agreed[0]["state"] == "done" and agreed[0]["when_text"]
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    _stages_everywhere(api, offer, did)  # the part receipt
    for day in (30, 34):
        api.post("/clock/advance", json={"to_day": day})
    late = _stages_everywhere(api, offer, did)  # the late day
    assert any(s["state"] == "now" for s in late)
    assert _group_row(api, did)["after_group"] == "payment_late"
    action = api.get("/home").json()["next_action"]
    assert api.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]}).status_code == 200
    [row] = [a for a in api.get("/approvals/queue").json()["approvals"] if a["status"] == "PENDING"]
    assert api.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    _stages_everywhere(api, offer, did)  # the cure
    # after the cure the rest is still unpaid: the record says MISSED but money is owed, so the deal is payment late, not closed
    q = api.get("/deals").json()["queue"]
    row = _group_row(api, did)
    assert row["after_group"] == "payment_late" and row["after_group_label"] == "Payment late" and row["lifecycle"] == "agreed"
    assert row["status_text"] == "Payment late" and q["deals"]["closed"] == 0 and q["deals"]["payment_late"] == 1 and q["deals"]["agreements"] == 1
    rest = next(r for r in rt.store.get_state().receivables if r.id == "RCV-A")
    version = api.get("/mandate").json()["mandate"]["version"]
    paid = api.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "rc-rest", "idempotency_key": "rc-rest", "mandate_version": version, "requested_by": "SYSTEM",
        "receivable_id": "RCV-A", "amount_fen": rest.face_fen - rest.settled_fen, "bank_reference": "BANK-REST"})
    assert paid.json()["result"]["status"] == "EXECUTED", paid.text
    done = _stages_everywhere(api, offer, did)  # the rest paid
    assert done[-1]["state"] == "done"

    # the closed row: the tracker's state word and close-out, and the closed count in queue.deals
    for lang in ("en", "zh"):
        q = api.get("/deals", params={"lang": lang}).json()["queue"]
        tracker = api.get(f"/decisions/{did}/tracker", params={"lang": lang}).json()
        closed = [r for r in q["agreements"] if r.get("lifecycle") == "closed"]
        assert len(closed) == 1 and q["deals"]["closed"] == 1 and q["deals"]["agreements"] == 0 and q["deals"]["payment_late"] == 0
        assert closed[0]["after_group"] == "closed" and closed[0]["after_group_label"] == ("Closed" if lang == "en" else "已结束")
        assert not BAD.search(closed[0]["after_group_label"])
        assert closed[0]["status_text"] == tracker["state_word"] and closed[0]["consequence_text"] == tracker["closeout_text"]
        assert closed[0]["decision_id"] == did
        words = {k: closed[0][k] for k in ("status_text", "consequence_text", "subject_text")}
        assert not [t for t in words.values() if BAD.search(t)], words
        if lang == "zh":
            assert english_leaks(words, NAMES) == []
    # the customer's deals history and the entry points into Deals
    overview = api.get("/customers/BUYER-1/overview").json()
    [hist] = overview["deals_history"]
    assert hist["decision_id"] == did and hist["lifecycle"] == "closed" and hist["state_word"] == "Paid late"
    assert hist["summary_text"].startswith("This deal cost ¥4,809.96 against ¥3,027.77 expected")
    assert hist["href"] == f"/deals?customer=BUYER-1&decision={did}&from=customer"
    zh_hist = api.get("/customers/BUYER-1/overview", params={"lang": "zh"}).json()["deals_history"]
    for item, lang in ((hist, "en"), (zh_hist[0], "zh")):
        words = {k: item[k] for k in ("subject_text", "state_word", "summary_text")}
        assert not [t for t in words.values() if BAD.search(t)], words
        if lang == "zh":
            assert english_leaks(words, NAMES) == [] and zh_hist[0]["href"] == hist["href"]
    rows = [r for r in api.get("/activity").json()["rows"] if r.get("decision_id") == did]
    assert rows and all(r["href"] == f"/deals?customer=BUYER-1&decision={did}&from=activity" and r["record_href"] == f"/decisions/{did}" for r in rows)


    # a new Foshan request: the history line is present, in the tracker's words, and the verdict and the reply are what the picture alone says
    new = _evaluate(api, "EX03_AS_USUAL")
    pic = _picture(api, new)
    assert pic["buyer_history_text"].startswith("Last time Foshan agreed ") and "This deal cost ¥4,809.96 against ¥3,027.77 expected" in pic["buyer_history_text"]
    assert pic["buyer_history_title"] == "Context only: it changes no verdict, counter, plan or authority."
    assert not BAD.search(pic["buyer_history_text"]) and not BAD.search(pic["buyer_history_title"])
    with rt.lock:
        bare = offer_picture.cached_picture(rt, new, "en")
    assert "buyer_history_text" not in bare and bare["recommendation"] == pic["recommendation"]
    assert [p["authority"] for p in bare["paths"]] == [p["authority"] for p in pic["paths"]]
    zh = _picture(api, new, "zh")
    assert zh["buyer_history_text"].startswith("上一次，Foshan同意了") and english_leaks({"text": zh["buyer_history_text"], "title": zh["buyer_history_title"]}, NAMES) == []
    assert not BAD.search(zh["buyer_history_text"]) and not BAD.search(zh["buyer_history_title"])


def test_day_zero_has_no_history_and_the_busy_books_stage_strips_never_fail(api: TestClient) -> None:
    offer, pic = _golden(api)
    assert pic["buyer_history_text"] is None and pic["buyer_history_title"] is None
    assert [s["key"] for s in pic["lifecycle_stages"]] == ["received", "analysed", "reply_ready", "sent", "agreed"]
    _, zhuhai = _busy_zhuhai(api)
    assert [s["label"] for s in zhuhai["lifecycle_stages"]][2] == "Owner review needed" and zhuhai["buyer_history_text"] is None
    _, zh = _golden_zh(api)
    assert [s["label"] for s in zh["lifecycle_stages"]] == ["已收到", "已分析", "回复已就绪", "已发送", "已达成"]
    q = api.get("/deals").json()["queue"]
    assert q["deals"]["closed"] == 0 and not [r for r in q["agreements"] if r.get("lifecycle") == "closed"]


def test_the_demo_story_links_the_agreed_deal_to_deals(api: TestClient) -> None:
    offer = api.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": EX01}).json()
    sent = api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative", "verdict_id": v["id"], "counter_id": v["counters"][0]["id"],
                                                  "state_version": v["state_version"]})
    assert sent.json()["outcome"] == "DEAL"
    for lang, label in (("en", "Track the deal"), ("zh", "跟踪这笔交易")):
        story = api.get("/demo/story", params={"seen": "cash", "lang": lang}).json()
        scene = next(sc for sc in story["scenes"] if sc["id"] == "agreement")
        tracked = [lk for lk in scene["proof"] if "/deals?" in lk["href"]]
        assert [lk["href"] for lk in tracked] == [f"/deals?customer=BUYER-1&decision={v['decision_id']}&from=demo"] and tracked[0]["label"] == label


def test_a_deal_with_no_early_payment_promise_has_no_early_payment_stage(api: TestClient) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    offer = api.post("/offers", json={"fixture_id": ZHUHAI}).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{offer}/evaluate", json={"fixture_id": ZHUHAI}).json()
    r = api.post(f"/offers/{offer}/accept", json={"verdict_id": v["id"], "state_version": v["state_version"]})
    assert r.status_code == 200, r.text
    did = str(v["decision_id"])
    stages = _stages_everywhere(api, offer, did)
    keys = [s["key"] for s in stages]
    assert "early_payment" not in keys and keys[-1] == "fulfilled" and "collecting" in keys
    assert [s["key"] for s in _stages_everywhere(api, offer, did, "zh")] == keys


def test_the_late_payment_label_is_in_chinese_and_the_groups_are_ordered(api: TestClient) -> None:
    from app.api.lifecycle import GROUP_ORDER, after_group_label

    assert [after_group_label(g, "zh") for g in GROUP_ORDER] == ["付款逾期", "等待付款", "已结束"]
    assert [after_group_label(g, "en") for g in GROUP_ORDER] == ["Payment late", "Awaiting payment", "Closed"]


# ================================================================ the verifier's four defects


def test_a_revoked_agreement_with_money_owed_is_payment_late_never_closed(api: TestClient, rt: Runtime) -> None:
    offer, did = _agree(api)
    commitment = rt.store.commitments()[0].id
    assert api.post(f"/commitments/{commitment}/revoke").status_code == 200
    api.post("/clock/advance", json={"to_day": 40})
    for lang in ("en", "zh"):
        q = api.get("/deals", params={"lang": lang}).json()["queue"]
        [row] = [r for r in q["agreements"] if r["kind"] == "AGREEMENT" and r["decision_id"] == did]
        assert row["after_group"] == "payment_late" and row["lifecycle"] == "agreed"
        assert row["status_text"] == ("Agreement revoked" if lang == "en" else "协议已撤销")
        assert q["deals"]["closed"] == 0 and q["deals"]["payment_late"] == 1
        [hist] = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()["deals_history"]
        assert hist["lifecycle"] == "agreed"


def test_the_recommendation_is_null_once_the_negotiation_is_answered(api: TestClient) -> None:
    offer, pic = _golden(api)
    assert pic["recommendation"] is not None
    assert api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"}).json()["outcome"] == "DEAL"
    for lang, agreed, not_chosen in (("en", "Agreed by Foshan", "Sent, not chosen by the buyer"), ("zh", "Foshan 已同意", "已发送，买方未选择")):
        after = _picture(api, offer, lang)
        assert after["recommendation"] is None
        status = {p["label"]: p["buyer_status_text"] for p in after["paths"] if p["kind"] == "reply"}
        assert list(status.values()).count(agreed) == 1 and not_chosen in status.values()
        assert not [v for v in status.values() if "等待" in v or "awaiting" in v]


def test_the_recommendation_is_null_once_the_buyer_walks_away(api: TestClient) -> None:
    offer, pic = _golden(api)
    assert api.post(f"/negotiate/{offer}", json={"buyer_profile": "hard_line"}).json()["outcome"] == "NO_DEAL"
    assert _picture(api, offer)["recommendation"] is None


def test_the_way_back_from_the_demo_says_the_demo(api: TestClient) -> None:
    offer, _ = _golden(api)
    for lang, label in (("en", "Back to the Demo"), ("zh", "返回演示")):
        r = api.get(f"/offers/{offer}/picture", params={"lang": lang, "from": "demo", "customer": "BUYER-1"})
        assert r.json()["context"]["back"] == {"label": label, "href": "/demo"}
    activity = api.get(f"/offers/{offer}/picture", params={"from": "activity", "customer": "BUYER-1"}).json()["context"]["back"]
    assert activity == {"label": "Back to Activity", "href": "/activity"}


def test_the_cause_lines_list_the_same_events_as_the_cause_text(api: TestClient) -> None:
    for lang in ("en", "zh"):
        if lang == "zh":
            _, pic = _golden_zh(api)
        else:
            _, pic = _golden(api)
        by = _by_label(pic)
        a, b = by["asked"], next(p for p in pic["paths"] if p["kind"] == "reply")
        sep, end = ("; ", ".") if lang == "en" else ("；", "。")
        seen = 0
        for pt in a["series"]:
            for got in (*pt["comparison"].values(), *pt["comparison_pairs"].values()):
                if not isinstance(got, dict) or "cause_text" not in got:
                    continue
                joined = " ".join(f"{ln['label']}{': ' if lang == 'en' else '：'}{sep.join(ln['items'])}{end}" for ln in got["cause_lines"])
                assert joined == got["cause_text"] or (not got["cause_lines"] and got["cause_text"])
                assert all(ln["items"] and set(ln) == {"label", "items"} for ln in got["cause_lines"])
                seen += bool(got["cause_lines"])
                for ln in got["cause_lines"]:
                    for item in ln["items"]:
                        assert not BAD.search(item), item
        assert seen > 0 and b
        two = _point(a, 2)["comparison"][b["key"]]["cause_lines"]
        assert [ln["label"] for ln in two][0] == ("Accept their request" if lang == "en" else "接受对方的要求")
        if lang == "zh":
            assert english_leaks([ln for got in two for ln in [got["label"], *got["items"]]], NAMES) == []


# ================================================================ the web owner's three findings


def test_a_deal_whose_early_part_was_paid_still_owes_the_rest_so_it_is_an_open_agreement(api: TestClient) -> None:
    """The record calls the deal FULFILLED once the early payment is kept, but the rest of the invoice is still owed: it is awaiting payment and the
    worklist counts it as an open agreement (on dev it dropped out of the queue; under the owner's rule it stays until nothing is owed)."""
    offer, did = _agree(api)
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    counts = api.get("/worklist").json()["counts"]
    assert counts["agreements"] == 1
    row = _group_row(api, did)
    assert row["after_group"] == "awaiting_payment" and row["lifecycle"] == "agreed"
    q = api.get("/deals").json()["queue"]
    assert q["deals"]["awaiting_payment"] == 1 and q["deals"]["closed"] == 0
    for day in (30, 34):
        api.post("/clock/advance", json={"to_day": day})
    assert _group_row(api, did)["after_group"] == "payment_late" and api.get("/worklist").json()["counts"]["agreements"] == 1


def test_the_trackers_cost_tone_is_what_it_was_on_the_golden_walk(api: TestClient) -> None:
    offer, did = _agree(api)

    def tracker() -> dict[str, Any]:
        return api.get(f"/decisions/{did}/tracker").json()  # type: ignore[no-any-return]

    assert (tracker()["state_word"], tracker()["cost"]["actual"]["tone"]) == ("Waiting for the buyer", "neutral")
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    for day in (30, 34):
        api.post("/clock/advance", json={"to_day": day})
    assert (tracker()["state_key"], tracker()["cost"]["actual"]["tone"]) == ("late", "neutral")
    action = api.get("/home").json()["next_action"]
    api.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    [row] = [a for a in api.get("/approvals/queue").json()["approvals"] if a["status"] == "PENDING"]
    assert api.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    t = tracker()
    assert t["cost"]["actual"]["tone"] == "bad" and t["cost"]["difference_fen"] == 178219 and t["state_tone"] == "bad"


def test_a_cold_picture_read_builds_the_exposure_block_once(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    offer = _evaluate(api, EX01)
    calls: list[int] = []
    real = assembly._compute_base

    def counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(assembly, "_compute_base", counting)
    assembly.clear_cache()
    offer_picture._cache.clear()
    pic = _picture(api, offer)
    assert pic["scenarios"] == [] and calls == []  # the first read of the picture builds no exposure block at all
    assert _scenario_list(api, offer) and len(calls) == 1  # the scenarios route builds it once: the compare read builds it and the late-payment card reuses it


def test_the_scenarios_route_gives_what_the_picture_carried_before(api: TestClient, rt: Runtime) -> None:
    from app.api import picture_scenarios

    for lang in ("en", "zh"):
        for offer, _pic in (_golden(api, lang), _busy_zhuhai(api, lang)):
            with rt.lock:
                before = offer_picture.cached_picture(rt, offer, lang)
            assert _scenario_list(api, offer, lang) == picture_scenarios.scenarios(rt, offer, before, lang)
            pic = _picture(api, offer, lang)
            assert pic["scenarios"] == [] and pic["scenarios_href"] == f"/offers/{offer}/scenarios?lang={lang}"
        api.post("/demo/reset")


def test_the_scenarios_route_is_owner_only_and_an_unknown_offer_is_404(api: TestClient) -> None:
    offer, _ = _golden(api)
    from app.main import app

    anonymous = TestClient(app)
    assert anonymous.get(f"/offers/{offer}/scenarios").status_code == 401
    assert api.get("/offers/OFF-nope/scenarios").status_code == 404


def test_a_cold_picture_read_on_the_golden_books_is_small(api: TestClient) -> None:
    import time

    offer = _evaluate(api, EX01)
    offer_picture._cache.clear()
    assembly.clear_cache()
    started = time.perf_counter()
    pic = _picture(api, offer)
    elapsed = time.perf_counter() - started
    print(f"cold picture read: {elapsed:.2f}s")
    assert pic["paths"] and elapsed < 1.5


def test_a_revoked_agreement_is_grouped_by_money_alone(api: TestClient, rt: Runtime) -> None:
    offer, did = _agree(api)
    assert api.post(f"/commitments/{rt.store.commitments()[0].id}/revoke").status_code == 200
    # revoked at agreement: the invoice is open and not yet due, so the deal awaits payment and says the agreement was revoked
    for lang, word, label in (("en", "Agreement revoked", "Awaiting payment"), ("zh", "协议已撤销", "等待付款")):
        row = _group_row(api, did, lang)
        assert (row["after_group"], row["status_text"], row["after_group_label"], row["lifecycle"]) == ("awaiting_payment", word, label, "agreed")
        assert row["consequence_text"] == api.get(f"/decisions/{did}/tracker", params={"lang": lang}).json()["state_text"]
    q = api.get("/deals").json()["queue"]
    assert (q["deals"]["closed"], q["deals"]["awaiting_payment"], q["deals"]["payment_late"]) == (0, 1, 0)
    [hist] = api.get("/customers/BUYER-1/overview").json()["deals_history"]
    assert hist["lifecycle"] == "agreed" and hist["state_word"] == "Agreement revoked"
    # past the due day and unpaid: payment late, still saying the agreement was revoked
    api.post("/clock/advance", json={"to_day": 40})
    row = _group_row(api, did)
    assert (row["after_group"], row["status_text"]) == ("payment_late", "Agreement revoked")
    # paid: nothing is owed, so it is closed, with the tracker's own words
    rest = next(r for r in rt.store.get_state().receivables if r.id == "RCV-A")
    version = api.get("/mandate").json()["mandate"]["version"]
    paid = api.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "rc-revoked", "idempotency_key": "rc-revoked", "mandate_version": version, "requested_by": "SYSTEM",
        "receivable_id": "RCV-A", "amount_fen": rest.face_fen - rest.settled_fen, "bank_reference": "BANK-REVOKED"})
    assert paid.json()["result"]["status"] == "EXECUTED", paid.text
    row = _group_row(api, did)
    tracker = api.get(f"/decisions/{did}/tracker").json()
    assert (row["after_group"], row["lifecycle"], row["status_text"]) == ("closed", "closed", tracker["state_word"]) and tracker["ended"]


def test_customer_loss_cash_effect_leaves_out_the_gross_profit_clause_when_there_is_no_figure(api: TestClient) -> None:
    offer, _ = _golden(api)
    loss = {s["key"]: s for s in _scenario_list(api, offer)}["customer_loss"]
    assert loss["lost_contribution_text"] is None
    assert "gross-profit" not in loss["cash_effect_text"] and loss["cash_effect_text"].startswith("¥1,260,000 of receipts removed")
