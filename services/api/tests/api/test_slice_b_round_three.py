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
    assert [p["authority_short_text"] for p in (asked, a, b)] == ["Outside mandate", "FLOW can send", "Needs your approval"]
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
        "mandate_text": "Option A is the reply FLOW can send within your mandate.",
        "alternative_text": "Option B needs your approval for 55-day terms. Its net economic cost over 12 months is stated as about ¥0 under the model's assumptions.",
        "rule_text": GOLDEN_RULE}


def test_the_rule_sentence_is_the_dictionary_word_for_word(api: TestClient) -> None:
    import pathlib

    _, pic = _golden(api)
    dictionary = (pathlib.Path(__file__).parents[4] / "apps" / "web" / "lib" / "dictionary.ts")
    if dictionary.exists():  # the web owns the key until it deletes it; the words are the same
        text = dictionary.read_text(encoding="utf-8")
        assert pic["recommendation"]["rule_text"] in text
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
    assert by["方案 A"]["authority_short_text"] == "FLOW 可以发送" and by["方案 B"]["authority_short_text"] == "需要您批准"
    assert pic["recommendation"]["alternative_text"].startswith("方案 B 需要您批准 55 天账期。")


# ================================================================ task 3: the scenarios


def _scenarios(pic: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in pic["scenarios"]}


def test_golden_scenarios_are_composed_from_the_compare_and_exposure_reads(api: TestClient) -> None:
    offer_id, pic = _golden(api)
    sc = _scenarios(pic)
    assert list(sc) == ["no_new_agreement", "late_30", "customer_loss"]
    assert [s["label"] for s in pic["scenarios"]] == ["Continue current position", "Buyer pays 30 days late", "Buyer stops placing new orders"]
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
    assert loss["lost_billings_text"] == "About ¥5,460,000 a year of billings"
    assert loss["cash_effect_text"].startswith("¥1,260,000 of receipts removed within the next 120 days; ¥420,000 still arrives.")
    assert loss["invoice_remains_text"] == "The ¥420,000 already invoiced (due in 32 days) is still paid."
    assert loss["assumption_text"].endswith("This is not a prediction.")


def test_scenarios_leave_the_picture_and_the_books_as_they_were(api: TestClient, rt: Runtime) -> None:
    offer_id, pic = _golden(api)
    version, log_length = rt.store.get_state().state_version, len(rt.store.operations())
    again = _picture(api, offer_id)
    assert again == pic and rt.store.get_state().state_version == version and len(rt.store.operations()) == log_length


def test_zhuhai_has_scenarios_and_the_scenario_words_are_clean_in_both_languages(api: TestClient) -> None:
    _, zhuhai = _busy_zhuhai(api)
    assert {s["key"] for s in zhuhai["scenarios"]} <= {"no_new_agreement", "late_30", "customer_loss"} and zhuhai["scenarios"]
    for pic in (_golden(api)[1], zhuhai):
        for key, text in _texts(pic["scenarios"]):
            assert not BAD.search(text), (key, text)
    _, zh = _golden_zh(api)
    assert english_leaks(_scenarios_words(zh), NAMES + ["Foshan Home Retail Co."]) == []
    assert _scenarios(zh)["customer_loss"]["lost_billings_text"] == "每年约 ¥5,460,000 的开票额"


def _scenarios_words(pic: dict[str, Any]) -> list[dict[str, Any]]:
    drop = {"assumption_text", "text"}  # the engine's long assumption sentences are checked by the compare and exposure tests
    return [{k: v for k, v in s.items() if k not in drop and k != "rows"} for s in pic["scenarios"]]


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
            assert set(got) == {"asked_display", "reply_display", "difference_display", "cause_text"}
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
    assert "Option A:" in cause and "As asked:" in cause and "today" in cause and "in 2 days" in cause
    asked_part, reply_part = cause.split("As asked:")[1].split("Option A:")[0], cause.split("Option A:")[1]
    assert "Early payment" in asked_part and "draw" in reply_part.lower()
    assert not BAD.search(cause), cause
    # on day 0 the request has nothing yet that the reply lacks except what the reply draws
    day0 = _point(asked, 0)["comparison"][a["key"]]["cause_text"]
    assert "As asked:" not in day0


def test_the_pair_words_are_in_chinese_with_no_english_left(api: TestClient) -> None:
    _, pic = _golden_zh(api)
    by = _by_label(pic)
    cmp = _point(by["asked"], 2)["comparison"]
    words = [{k: v for k, v in cmp[by["方案 A"]["key"]].items()}, _point(by["asked"], 2)["comparison_pairs"][f"{by['方案 A']['key']}:{by['方案 B']['key']}"]]
    assert english_leaks(words, NAMES) == []
