"""Slice B patch (second verifier pass), the server half: the What-if sandbox says what it simulates and its reserve word follows its own lowest cash (P4);
a lapsed offer is not revivable (P5); the words of a lapsed decision, the customer overview, the agreement's history row, the Home customer row's waiting
count, the unresolved-reference abstention and the send receipt (P6). On the busy books, in both languages. (P1 to P3 are in test_chat_scope.py.)"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.api import customer_overview, offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.api.whatif import _cash_text
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import agree_on_rcv_a, english_leaks

pytestmark = pytest.mark.usefixtures("fast_busy")  # the busy seed is replayed once per process (tests/api/busy_snapshot.py)

OWNER = {"X-Owner-Token": "demo-owner-token"}
ACTUAL = {"terms_days": 60, "discount_bp": 120, "rebate_bp": 100}
NAMES = ["Foshan Home Retail Co.", "Foshan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai", "Dongguan Office Supplies Ltd.", "Dongguan"]
LAPSED_TEXT = {"en": "Nothing to do: this offer lapsed.", "zh": "无需处理：该报价已失效。"}


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset()
    set_runtime(runtime)
    reset_sessions()
    for clear in (worklist.clear_cache, customer_overview.clear_cache, offer_picture._cache.clear):
        clear()
    yield runtime
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app, headers=OWNER)


@pytest.fixture
def busy(api: TestClient) -> dict[str, str]:
    """The busy books and the offer ids of Foshan (EX01), Dongguan (EX08B) and Zhuhai (EX09)."""
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    ids: dict[str, str] = {}
    for key, fixture in (("foshan", "EX01_PACKAGE"), ("dongguan", "EX08B_JOINT_BUYER2"), ("zhuhai", "EX09_TERMS_BUYER3")):
        ids[key] = str(api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"])
    return ids


def _whatif(api: TestClient, lang: str = "en", **address: Any) -> dict[str, Any]:
    r = api.post("/whatif", params={"lang": lang}, json={**ACTUAL, **address})
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


# ---------------------------------------------------------------- P4: the sandbox says what it simulates, and names the negotiation's own figure


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_sandbox_says_it_simulates_every_invoice_and_names_the_negotiations_own_figure(api: TestClient, busy: dict[str, str], lang: str) -> None:
    zhuhai = _whatif(api, lang, offer_id=busy["zhuhai"])
    assert zhuhai["scope_text"] == {
        "en": "The sandbox applies the terms to every Zhuhai invoice for the next 12 months, not only the next one; the negotiation itself asks for one invoice.",
        "zh": "沙盘把这些条款应用于Zhuhai未来 12 个月内的每一张发票，而不只是下一张；这项谈判本身只涉及一张发票。"}[lang]
    assert zhuhai["compare_text"] == {"en": "The negotiation if you accept their request: ¥668.32 over 12 months, within your limit.",
                                      "zh": "如果接受对方的要求，谈判成本：¥668.32（12 个月内），在您的限额内。"}[lang]
    asked = next(p for p in api.get(f"/offers/{busy['zhuhai']}/picture", params={"lang": lang}).json()["paths"] if p["key"] == "asked")
    assert asked["cost_total_display"] in zhuhai["compare_text"]  # the picture's own figure for the ask, not a second computation
    assert zhuhai["invoice_text"].count("RCV-") == 0 and "RCV-" not in zhuhai["scope_text"] + zhuhai["compare_text"]
    foshan = _whatif(api, lang, offer_id=busy["foshan"])
    assert "Foshan" in foshan["scope_text"] and "Zhuhai" not in foshan["scope_text"]
    asked_f = next(p for p in api.get(f"/offers/{busy['foshan']}/picture", params={"lang": lang}).json()["paths"] if p["key"] == "asked")
    assert asked_f["cost_once_display"] in foshan["compare_text"] and asked_f["cost_forward_display"] in foshan["compare_text"]
    assert ("over your limit" if lang == "en" else "超出您的限额") in foshan["compare_text"]  # Foshan's ask breaks the concession cap, and it says so
    if lang == "zh":
        assert not english_leaks({"a": zhuhai["scope_text"], "b": zhuhai["compare_text"], "c": foshan["compare_text"]}, NAMES)


def test_the_sandboxs_maths_does_not_change(api: TestClient, busy: dict[str, str]) -> None:
    named = _whatif(api, offer_id=busy["zhuhai"])
    bare = _whatif(api, buyer_id="BUYER-3")
    assert {k: named[k] for k in ("outcome", "codes", "forward", "trajectory")} == {k: bare[k] for k in ("outcome", "codes", "forward", "trajectory")}


def test_without_an_offer_the_sandbox_says_what_it_simulates_and_has_no_negotiation_figure(api: TestClient, busy: dict[str, str]) -> None:
    by_buyer = _whatif(api, buyer_id="BUYER-3")
    assert by_buyer["scope_text"] == "The sandbox applies the terms to every Zhuhai invoice for the next 12 months, not only the next one."
    assert by_buyer["compare_text"] is None
    presets = api.get("/whatif/presets", params={"offer_id": busy["zhuhai"]}).json()
    assert presets["scope_text"].endswith("the negotiation itself asks for one invoice.") and presets["compare_text"].startswith("The negotiation if you accept their request: ¥668.32")
    unavailable = api.get("/whatif/presets", params={"offer_id": busy["dongguan"]}).json()
    assert unavailable["available"] is False and unavailable["compare_text"] is None  # the reason it cannot run is the scope text, unchanged


@pytest.mark.parametrize("lang", ["en", "zh"])
@pytest.mark.parametrize("who", ["zhuhai", "foshan"])
def test_the_reserve_word_follows_the_lowest_cash_against_the_minimum(api: TestClient, busy: dict[str, str], lang: str, who: str) -> None:
    for position in ({"terms_days": 45, "discount_bp": 0, "rebate_bp": 0}, ACTUAL, {"terms_days": 60, "discount_bp": 0, "rebate_bp": 0}):
        r = api.post("/whatif", params={"lang": lang}, json={**position, "offer_id": busy[who]}).json()
        traj, reserve = r["trajectory"], r["reserve"]
        below = [d for d in traj["days"] if d["closing"]["fen"] < traj["floor"]["fen"]]
        assert reserve["below_days"] == len(below) == sum(1 for d in traj["days"] if d["below_floor"])
        assert reserve["stays_above"] is (traj["min_cash"]["fen"] >= traj["floor"]["fen"])
        if traj["min_cash"]["fen"] < traj["floor"]["fen"]:  # the cash dips under the minimum: never "Stays above it", whatever the verifier's delta says
            assert reserve["cash_text"] == {"en": f"Below it for {len(below)} days", "zh": f"有 {len(below)} 天低于储备"}[lang]
        else:
            assert reserve["cash_text"] == {"en": "Stays above it", "zh": "始终高于储备"}[lang]
    # the contradiction the owner read: the books are under the minimum with or without the terms, so the verifier names no breach of its own
    same = api.post("/whatif", params={"lang": lang}, json={"terms_days": 45, "discount_bp": 0, "rebate_bp": 0, "offer_id": busy[who]}).json()
    assert same["trajectory"]["min_cash"]["fen"] < same["trajectory"]["floor"]["fen"]
    assert same["reserve"]["breach_day"] is None and same["reserve"]["cash_text"] and "Stays" not in same["reserve"]["cash_text"]


def test_the_cash_word_without_a_cash_line_is_null_and_one_day_is_singular() -> None:
    assert _cash_text({"below_days": None}, "en") is None
    assert _cash_text({"below_days": 1}, "en") == "Below it for 1 day" and _cash_text({"below_days": 0}, "en") == "Stays above it"
    assert _cash_text({"below_days": 1}, "zh") == "有 1 天低于储备" and _cash_text({"below_days": 0}, "zh") == "始终高于储备"


# ---------------------------------------------------------------- P5: a lapsed offer is not revivable


def _lapsed_ids(api: TestClient) -> list[str]:
    return [d["id"].split(":", 1)[1] for d in api.get("/decisions").json()["decisions"] if d["state"] == "LAPSED"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_lapsed_offer_is_neither_evaluated_nor_negotiated_again(api: TestClient, busy: dict[str, str], lang: str) -> None:
    agree_on_rcv_a(api)
    lapsed = _lapsed_ids(api)
    assert len(lapsed) == 2
    expected = {"en": "This offer has lapsed: the invoice it was about has since been settled under another agreement, so there is nothing to reply to.",
                "zh": "该报价已失效：它所针对的发票此后已按另一份协议结算，无需再答复。"}[lang]
    before = api.get("/deals", params={"lang": lang}).json()["queue"]
    for oid in lapsed:
        evaluate = api.post(f"/offers/{oid}/evaluate", params={"lang": lang}, json={})
        negotiate = api.post(f"/negotiate/{oid}", params={"lang": lang}, json={"buyer_profile": "cooperative"})
        for r in (evaluate, negotiate):
            assert r.status_code == 409, r.text
            assert r.json()["detail"] == {"code": "OFFER_LAPSED", "message": expected, "message_when": expected}
    assert sorted(_lapsed_ids(api)) == sorted(lapsed)  # still lapsed: not NEEDS_CLARIFICATION, not Waiting, not FAILED
    assert api.get("/deals", params={"lang": lang}).json()["queue"] == before
    assert all(d["state"] != "FAILED" for d in api.get("/decisions").json()["decisions"])


def test_a_bound_send_on_a_lapsed_offer_is_lapsed_too_and_a_live_offer_still_evaluates(api: TestClient, busy: dict[str, str]) -> None:
    agree_on_rcv_a(api)
    oid = _lapsed_ids(api)[0]
    verdict = api.get(f"/offers/{oid}").json()
    sent = api.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative", "counter_id": "x", "verdict_id": "y"})
    assert sent.status_code == 409 and sent.json()["detail"]["code"] in ("OFFER_LAPSED", "COUNTER_CHANGED"), (sent.text, verdict)
    live = api.post(f"/offers/{busy['zhuhai']}/evaluate", json={})  # an offer on an invoice nobody agreed on is read as before
    assert live.status_code == 200, live.text


# ---------------------------------------------------------------- P6 (a): a lapsed decision's waiting and remaining-task words


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_lapsed_decision_says_nothing_to_do_and_never_that_the_action_is_complete(api: TestClient, busy: dict[str, str], lang: str) -> None:
    agree_on_rcv_a(api)
    rows = [d for d in api.get("/decisions", params={"lang": lang}).json()["decisions"] if d["state"] == "LAPSED"]
    assert len(rows) == 2
    for row in rows:
        assert row["waiting_for"]["text"] == LAPSED_TEXT[lang]
        detail = api.get(f"/decisions/{quote(row['id'], safe='')}", params={"lang": lang}).json()
        assert detail["waiting_for"]["text"] == detail["remaining_task"]["text"] == LAPSED_TEXT[lang]
        assert "action is complete" not in str(detail) and "操作已完成" not in str(detail)
    agreed = next(d for d in api.get("/decisions", params={"lang": lang}).json()["decisions"] if d["state"] == "AGREED")
    assert agreed["waiting_for"]["text"] != LAPSED_TEXT[lang]  # an agreement keeps its own words


# ---------------------------------------------------------------- P6 (b): the overview counts the customer's decisions


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_overview_counts_the_customers_open_decisions(api: TestClient, busy: dict[str, str], lang: str) -> None:
    eyebrow = {b: api.get(f"/customers/{b}/overview", params={"lang": lang}).json()["decision"]["eyebrow"] for b in ("BUYER-1", "BUYER-2", "BUYER-3")}
    assert eyebrow["BUYER-1"] == {"en": "Three commercial decisions wait for you", "zh": "有 3 项商务决定等待您处理"}[lang]
    assert eyebrow["BUYER-2"] == eyebrow["BUYER-3"] == {"en": "One commercial decision waits for you", "zh": "有一项商务决定等待您处理"}[lang]
    queue = api.get("/deals", params={"lang": lang}).json()["queue"]
    assert sum(1 for r in queue["needs_you"] if r["kind"] == "DECISION" and r["customer_id"] == "BUYER-1") == 3  # the queue's own count
    agree_on_rcv_a(api)  # two of the three lapse with the agreement: the count follows
    after = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()["decision"]
    assert "Three" not in after["eyebrow"] and "3" not in after["eyebrow"]


# ---------------------------------------------------------------- P6 (c): after an agreement the page reflects it


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_after_an_agreement_the_history_row_and_the_outstanding_say_what_is_promised(api: TestClient, busy: dict[str, str], lang: str) -> None:
    agree_on_rcv_a(api)
    page = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()
    row = next(h for h in page["history"] if h["when_text"] in ("In force", "现行"))
    assert "No confirmed agreement on file" not in row["text"] and "尚无已确认的协议" not in row["text"]
    assert ("Agreed:" in row["text"] and "0.85% off" in row["text"] and "may be paid early" in row["text"]) if lang == "en" else \
        ("已约定：" in row["text"] and "折扣 0.85%" in row["text"] and "可提前付款" in row["text"])
    outstanding = next(f for f in page["figures"] if f["key"] == "outstanding")
    assert outstanding["value_display"] == "¥420,000"  # what is owed is unchanged
    assert outstanding["note"] == {"en": "¥416,430 promised in 2 days; otherwise due in 32 days",
                                   "zh": "已承诺 2 天后支付 ¥416,430；否则 32 天后到期"}[lang]
    assert ("nothing overdue" not in outstanding["note"]) and "没有逾期" not in outstanding["note"]
    if lang == "zh":
        assert not english_leaks({"a": row["text"], "b": outstanding["note"]}, NAMES)


def test_before_an_agreement_the_history_row_and_the_outstanding_are_as_they_were(api: TestClient, busy: dict[str, str]) -> None:
    page = api.get("/customers/BUYER-1/overview").json()
    row = next(h for h in page["history"] if h["when_text"] == "In force")
    assert row["text"].startswith("No confirmed agreement on file; payment is due 45 days") and "none agreed on this invoice" in row["text"]
    assert next(f for f in page["figures"] if f["key"] == "outstanding")["note"] == "due in 32 days, nothing overdue"


# ---------------------------------------------------------------- P6 (d): the Home customer row counts waiting as the queue does


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_home_customer_rows_waiting_count_leaves_out_the_promise(api: TestClient, busy: dict[str, str], lang: str) -> None:
    agree_on_rcv_a(api)
    queue = api.get("/deals", params={"lang": lang}).json()["queue"]
    assert queue["counts"]["waiting"] == 1 and queue["counts"]["agreements"] == 1  # one reply awaited; the agreement, which carries its promise
    assert not any(r["kind"] == "PROMISE" for r in queue["agreements"])
    assert any(r["kind"] == "AGREEMENT" and r["customer_id"] == "BUYER-1" and ("has promised" if lang == "en" else "买方承诺") in r["consequence_text"] for r in queue["agreements"])
    foshan = next(c for c in api.get("/customers", params={"lang": lang}).json()["customers"] if c["customer_id"] == "BUYER-1")
    waiting_for_foshan = sum(1 for r in queue["waiting"] if r["customer_id"] == "BUYER-1")
    assert waiting_for_foshan == 1
    assert foshan["status_text"].endswith({"en": "1 waiting", "zh": "1 项在等待"}[lang]) and "2" not in foshan["status_text"].split("·")[-1]
    assert "promised" not in foshan["status_text"] and "承诺" not in foshan["status_text"]  # a customer with something waiting says only that
    worklist_waiting = api.get("/worklist", params={"lang": lang}).json()["waiting"]
    assert any(w["kind"] == "PROMISE" for w in worklist_waiting)  # the promise stays a row of the worklist, only the count leaves it out


# ---------------------------------------------------------------- P6 (e): the unresolved-reference abstention in words


@pytest.mark.parametrize("lang,expected", [
    ("en", "The buyer refers to an earlier arrangement that is not in your books."),
    ("zh", "买方提到了一项此前的约定，但您的账目中没有这项记录。")])
def test_an_unresolved_reference_is_explained_not_quoted(api: TestClient, lang: str, expected: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    offer = api.post("/offers", params={"lang": lang}, json={"fixture_id": "EX03_AS_USUAL"}).json()["offer"]
    ref = [a for a in offer["abstentions"] if a["field"] == "unresolved_reference"]
    assert ref and all(a["reason_when"] == expected for a in ref)
    assert all("unresolved reference" not in a["reason_when"] for a in ref)
    shown = api.get(f"/offers/{offer['offer_id']}", params={"lang": lang}).json()
    assert all(a["reason_when"] == expected for a in shown["offer"]["abstentions"] if a["field"] == "unresolved_reference")


# ---------------------------------------------------------------- P6 (f): the send receipt says when nothing is funded, and what ran after


@pytest.mark.parametrize("lang,expected", [
    ("en", "No funding runs when you send: today's plan cannot run; the gap stays open."),
    ("zh", "发送时不会办理融资：今天的方案无法执行；缺口仍未补上。")])
def test_a_send_that_will_not_fund_says_so_before_the_send(api: TestClient, busy: dict[str, str], lang: str, expected: str) -> None:
    ev = api.post(f"/offers/{busy['foshan']}/evaluate", params={"lang": lang}, json={"fixture_id": "EX01_PACKAGE"}).json()
    [reply] = ev["workspace"]["priced_responses"]
    assert reply["receipt"]["executes_now_text"] == expected


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_after_the_send_the_receipt_says_what_ran_not_the_state_word(api: TestClient, busy: dict[str, str], lang: str) -> None:
    agree_on_rcv_a(api)
    agreed = next(d for d in api.get("/decisions").json()["decisions"] if d["state"] == "AGREED")
    detail = api.get(f"/decisions/{quote(agreed['id'], safe='')}", params={"lang": lang}).json()
    said = detail["agreement"]["receipt"]["executes_now_text"]
    assert said == detail["execution"]["summary_text"] and said != detail["agreement"]["status_text"]
    assert said.endswith({"en": "The gap was not funded: today's funding plan could not run.", "zh": "缺口未获融资：今天的融资方案无法执行。"}[lang])
