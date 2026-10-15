"""The Deals redesign's server words (feat/slice-b-r3-api): the buyer's path named once, why a deal has one reply, what happens if the buyer
refuses, and the audit's four server bugs (no promise counted before it is due, one row per agreed deal, the headline agreeing with the page, the
record's sent cost). Golden books and the busy books' Foshan deal, in both languages."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.api.withheld_words import withheld
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.strategy import exposure as assembly
from tests.api.conftest import english_leaks

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = "EX01_PACKAGE"
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai",
         "Bank credit line", "Invoice financing (onboarded platform)", "Government-guaranteed working-capital loan", "FLOW"]
# an id, a day number, a raw enum or the word None in a sentence; "best", "safe" and "cheaper" are never said
BAD = re.compile(r"\b(?:RCV|BUYER|FAC|LOT|CMT|OFF|CTR|VER|OP|APR|DOC)-[A-Za-z0-9]|RI:|\bday -?\d|\bNone\b|\bnull\b|\b(?:flow_may|needs_owner|over_limit)\b"
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


# ---------------------------------------------------------------- S1: the buyer's path, named once


@pytest.mark.parametrize("lang,label", [("en", "Accept their request"), ("zh", "接受对方的要求")])
def test_the_buyers_path_has_one_name_in_the_picture_and_its_pair_words(api: TestClient, lang: str, label: str) -> None:
    offer_id = _evaluate(api, EX01, lang)
    pic = _picture(api, offer_id, lang)
    assert pic["paths"][0]["kind"] == "asked" and pic["paths"][0]["label"] == label and pic["asked"]["label"] == label
    seen = [ln["label"] for p in pic["paths"] for pt in p["series"] or [] for c in (pt["comparison"] or {}).values() if isinstance(c, dict)
            for ln in c.get("cause_lines", [])]
    assert label in seen
    words = [p["label"] for p in pic["paths"]] + [p["band_text"] or "" for p in pic["paths"]] + [m["text"] for m in pic["moments"]]
    words += [m["word"] for m in pic["moments"]] + [pic["recommendation"]["mandate_text"], pic["asked"]["label"]]
    words += [ln["label"] for p in pic["paths"] for pt in p["series"] or [] for c in (pt["comparison"] or {}).values() if isinstance(c, dict)
              for ln in c.get("cause_lines", [])]
    old = ("As they asked", "As asked", "as asked", "按对方要求")
    assert [w for w in words if any(o in w for o in old)] == []  # a short list on failure, never a diff of the whole picture


# ---------------------------------------------------------------- S2: why there is only one reply


def test_the_golden_books_offer_two_replies_and_withhold_nothing(api: TestClient) -> None:
    pic = _picture(api, _evaluate(api, EX01))
    assert len(pic["replies"]) == 2 and pic["withheld"] == []


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_busy_foshan_deal_says_why_it_has_one_reply(api: TestClient, lang: str) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    pic = _picture(api, _evaluate(api, EX01, lang), lang)
    assert [p["kind"] for p in pic["paths"]] == ["asked", "reply"]
    [w] = pic["withheld"]
    assert w["kind"] == "price_adjustment"
    if lang == "en":
        assert w["text"] == ("FLOW has no second reply: terms of 60, 55 or 50 days would leave cash ¥385,000 short of your minimum in 47 days, "
                             "and your committed funding cannot cover it.")
    else:
        assert w["text"] == ("FLOW 没有第二个回复：60、55 或 50 天的账期会使现金低于您的最低现金储备 ¥385,000（47 天后），"
                             "而您已承诺的融资无法覆盖。")
        assert not english_leaks({"withheld_text": w["text"]}, NAMES)
    assert not BAD.search(w["text"]), w["text"]


class _V:
    def __init__(self, summary: str, counters: int = 1) -> None:
        self.summary, self.counters = summary, [object()] * counters


def test_each_reason_the_engine_writes_is_said_and_one_it_does_not_know_is_left_out() -> None:
    cases = {
        "No early-pay counter (early settlement of ¥420,000.00 at 1.50%): it cannot be funded from committed sources: the shortfall of "
        "¥12,000.00 on day 10 has no cure": ("early_pay", "an early-payment reply would leave cash ¥12,000 short of your minimum in 8 days"),
        "No rebate counter (a 2.00% rebate): it cannot be funded in time: the shortfall of ¥9,000.00 on day 5 is cured only by an advance that "
        "cannot run by then (RCV-A is issued on day 9)": ("rebate", "the funding that would cover it cannot arrive in time"),
        "No bounded-extension counter (+10 days on 3 invoices): it would breach a covenant: DSCR 1.18 against 1.25":
            ("bounded_extension", "would breach a lender covenant: debt-service cover 1.18 against 1.25"),
        "No early-pay counter (early settlement of ¥1.00 at 1.50%): it is above the mandate's rate ceiling: 18.5279% against 15.00%":
            ("early_pay", "would cost 18.5279% a year against your 15.00% rate ceiling"),
        "No price-adjustment counter: 60-day terms with a 0.25% price adjustment exceed the forward-concession budget":
            ("price_adjustment", "even with a 0.25% price adjustment to offset them, would exceed your budget"),
        "No price-adjustment counter: 60-day terms cannot be funded from committed sources: no committed plan keeps cash at the reserve":
            ("price_adjustment", "no committed funding plan can keep it at the minimum"),
    }
    for summary, (kind, fragment) in cases.items():
        [w] = withheld(_V(f"REJECT: X. {summary}. Counters: Option A."), 2, "en")
        assert w["kind"] == kind and fragment in w["text"] and w["text"].startswith("FLOW has no second reply: "), w
        assert not BAD.search(w["text"]), w["text"]
        [z] = withheld(_V(f"REJECT: X. {summary}. Counters: Option A."), 2, "zh")
        assert z["kind"] == kind and z["text"].startswith("FLOW 没有第二个回复：") and z["text"].endswith("。")
    unknown = "No rebate counter (a 2.00% rebate): it fails its own re-check (REJECT: SOMETHING_ODD)"
    assert withheld(_V(f"REJECT: X. {unknown}. Counters: Option A."), 2, "en") == []
    assert withheld(_V("COUNTER: X. Counters: Option A, Option B."), 2, "en") == []
    assert withheld(_V(f"REJECT. {unknown}.", counters=0), 2, "en") == []
    [w] = withheld(_V("REJECT. No rebate counter (a 2.00% rebate): it would breach a covenant: leverage 1.9 against 1.8.", counters=0), 2, "en")
    assert w["text"].startswith("FLOW has no reply to offer: ")


# ---------------------------------------------------------------- S3: what happens if the buyer refuses


def _money(fen: int) -> str:
    return f"¥{fen // 100:,}"


def _refused_send(api: TestClient, rt: Runtime, offer_id: str, verdict: dict[str, Any], counter_id: str) -> dict[str, Any]:
    r = api.post(f"/negotiate/{offer_id}", json={"buyer_profile": "cooperative", "verdict_id": verdict["id"], "counter_id": counter_id,
                                                 "state_version": rt.store.get_state().state_version})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    assert body["outcome"] == "NO_DEAL"
    return body


def test_a_picture_read_says_what_a_refusal_runs_and_changes_nothing(api: TestClient, rt: Runtime) -> None:
    offer_id = _evaluate(api, EX01)
    before = (rt.store.get_state().state_version, len(rt.store.operations()), len(rt.store.commitments()),
              {f.id: f.drawn_fen for f in rt.store.get_state().facilities})
    en, zh = _picture(api, offer_id, "en"), _picture(api, offer_id, "zh")
    assert before == (rt.store.get_state().state_version, len(rt.store.operations()), len(rt.store.commitments()),
                      {f.id: f.drawn_fen for f in rt.store.get_state().facilities})
    assert [p["if_refused_text"] for p in en["paths"] if p["kind"] == "asked"] == [None]
    texts = [p["if_refused_text"] for p in en["paths"] if p["kind"] == "reply"]
    assert len(texts) == 2 and len(set(texts)) == 1
    assert texts[0] == ("If Foshan refuses, FLOW will fund the gap on its own: a ¥150,000 credit-line draw today and ¥255,000 of invoice financing "
                        "in 3 days. The funding costs ¥3,113.93.")
    [zh_text] = {p["if_refused_text"] for p in zh["paths"] if p["kind"] == "reply"}
    assert zh_text == "如果Foshan拒绝，FLOW 将自行为缺口融资：信用额度提款 ¥150,000（今天）、发票融资 ¥255,000（3 天后）。融资成本为 ¥3,113.93。"
    assert not english_leaks({"if_refused_text": zh_text}, NAMES)
    assert not BAD.search(texts[0]) and not BAD.search(zh_text)


@pytest.mark.parametrize("pick", [1])  # the cooperative buyer agrees to Option A and refuses Option B
def test_the_amounts_in_the_text_are_what_a_refused_send_then_draws(api: TestClient, rt: Runtime, pick: int) -> None:
    offer_id = _evaluate(api, EX01)
    view = api.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": EX01}).json()
    text = next(p["if_refused_text"] for p in _picture(api, offer_id)["paths"] if p["key"] == view["counters"][pick]["id"])
    drawn_before = {f.id: f.drawn_fen for f in rt.store.get_state().facilities}
    sent = _refused_send(api, rt, offer_id, view, view["counters"][pick]["id"])
    drawn = {f.id: f.drawn_fen - drawn_before[f.id] for f in rt.store.get_state().facilities if f.drawn_fen != drawn_before[f.id]}
    assert drawn == {"FAC-LINE": 15_000_000, "FAC-IF": 25_500_000}
    assert [a["amount_fen"] for a in sent["plan"]["actions"]] == [15_000_000, 25_500_000]
    for fen in drawn.values():
        assert _money(fen) in text
    assert "The funding costs ¥3,113.93." in text and [o["status"] for o in sent["operations"]] == ["EXECUTED", "EXECUTED"]
    assert len(re.findall(r"¥[\d,]+", text)) == 3  # the two legs and the funding cost; no figure the plan does not carry


def test_a_refusal_that_would_run_nothing_says_nothing(api: TestClient, rt: Runtime) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    pic = _picture(api, _evaluate(api, EX01))
    texts = {p["if_refused_text"] for p in pic["paths"] if p["kind"] == "reply"}
    # on the busy books the gap's plan cannot run today: the refused send executes nothing, so there is nothing to say
    assert texts == {None}


def test_extracting_the_no_deal_plan_left_the_refused_send_as_it_was(api: TestClient, rt: Runtime) -> None:
    """`decide._negotiate_locked` now reads its no-deal funding from `refusal.refusal_plan`. The plan is the old inline computation's, and the send's
    outcome, message, plan and draws are those of the route before the extraction (a refused Option B on the golden books)."""
    from app.books import current_books
    from app.funding import plan

    offer_id = _evaluate(api, EX01)
    view = api.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": EX01}).json()
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    from app.api.refusal import refusal_plan

    assert refusal_plan(state, rt.store.commitments(), mandate).model_dump() == plan(books.state, books.with_([]), mandate).model_dump()
    drawn_before = {f.id: f.drawn_fen for f in state.facilities}
    sent = _refused_send(api, rt, offer_id, view, view["counters"][1]["id"])
    assert sent["message"] == "NO DEAL after bounded rounds; the Debt Desk funds the near-term gap."
    assert sent["message_when"] == "No deal after the buyer's replies; the near-term gap is funded another way."
    assert sent["plan"]["need_fen"] == 40_500_000 and [(a["kind"], a["facility_id"], a["amount_fen"]) for a in sent["plan"]["actions"]] == [
        ("DRAW", "FAC-LINE", 15_000_000), ("FINANCE_INVOICE", "FAC-IF", 25_500_000)]
    assert [o["kind"] for o in sent["operations"]] == ["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]
    assert {f.id: f.drawn_fen - drawn_before[f.id] for f in rt.store.get_state().facilities if f.drawn_fen != drawn_before[f.id]} == {
        "FAC-LINE": 15_000_000, "FAC-IF": 25_500_000}
