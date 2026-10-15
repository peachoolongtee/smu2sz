"""A lapsed offer is never "ready to send" (Slice B fix S2). An agreement on invoice RCV-A settles that invoice, so every other reply about it can no
longer be drawn on today's books (the offer picture says so). The decision record gives such a negotiation one state word, LAPSED, derived by the
same rule (`app.api.decisions.offer_as_asked`): the queue lists it in no tier, the customer overview says Lapsed and shows no reply and no figure,
and the exposure routes say there is nothing to read because the offer lapsed, not that the read failed."""

from __future__ import annotations

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
LAPSED_EN = "Lapsed · the invoice it was about has since been settled under another agreement"
LAPSED_ZH = "已失效 · 它所针对的发票此后已按另一份协议结算"
NAMES = ["Foshan Home Retail Co.", "Foshan", "Dongguan Office Supplies Ltd.", "Dongguan", "Zhuhai Kitchenware Wholesale Co.", "Zhuhai"]
# the busy seed before the Slice B fix: EX03 negotiated to an agreement on RCV-A at day 0
OLD_SEED = {"offers": ["EX01_PACKAGE", "EX02_EARLY_1_5", "EX03_AS_USUAL", "EX07_CONFLICT", "EX08B_JOINT_BUYER2", "EX09_TERMS_BUYER3"],
            "negotiate": [{"offer": "EX03_AS_USUAL", "mode": "cooperative"}],
            "operations": [{"kind": "APPLY_FOR_FACILITY", "facility": "FAC-GGL", "amount_fen": 20000000}]}


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


def _decisions(api: TestClient, lang: str = "en") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = api.get("/decisions", params={"lang": lang}).json()["decisions"]
    return rows


def _lapsed(api: TestClient, lang: str = "en") -> list[dict[str, Any]]:
    return [d for d in _decisions(api, lang) if d["state"] == "LAPSED"]


def _foshan_live(api: TestClient) -> list[dict[str, Any]]:
    return [d for d in _decisions(api) if d["counterparty_name"] == "Foshan Home Retail Co." and d["state"] == "RESPONSE_READY"]


def test_on_the_busy_books_every_foshan_reply_is_live_until_one_is_sent(api: TestClient) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    assert len(_foshan_live(api)) == 3 and _lapsed(api) == []
    q = api.get("/deals").json()["queue"]
    assert sum(1 for r in q["needs_you"] if r["kind"] == "DECISION" and r["customer_id"] == "BUYER-1") == 3


@pytest.mark.parametrize("lang,word", [("en", LAPSED_EN), ("zh", LAPSED_ZH)])
def test_after_a_send_on_rcv_a_the_other_foshan_replies_are_lapsed_and_in_no_tier(api: TestClient, lang: str, word: str) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    agreed = agree_on_rcv_a(api)
    lapsed = _lapsed(api, lang)
    assert len(lapsed) == 2 and {d["id"] for d in lapsed}.isdisjoint({f"deal:{agreed}"})
    for d in lapsed:
        assert d["state_text"] == word and d["state_tone"] == "neutral" and d["terminal"] is True
        assert d["waiting_for"]["code"] == "NOTHING" and d["waiting_for"]["party"] == "none"
    q = api.get("/deals", params={"lang": lang}).json()["queue"]
    listed = {r["decision_id"] for tier in ("needs_you", "waiting", "agreements") for r in q[tier]}
    assert not listed & {d["id"] for d in lapsed}  # nothing to do and nothing to wait for
    assert not any(r["customer_id"] == "BUYER-1" and r["kind"] == "DECISION" for r in q["needs_you"])
    assert q["counts"] == {"needs_you": 4, "waiting": 1, "agreements": 1, "customers": 3}  # one row per agreed deal: the promise is folded into it (S5)
    foshan = next(c for c in api.get("/customers", params={"lang": lang}).json()["customers"] if c["customer_id"] == "BUYER-1")
    # a lapsed offer is not an open negotiation: what is left is the buyer's clarification (EX07), which waits on the buyer
    assert foshan["negotiations_count"] == 1 and foshan["needs_you_count"] == 0
    detail = api.get(f"/decisions/{lapsed[0]['id']}", params={"lang": lang}).json()
    assert detail["state"] == "LAPSED" and detail["state_text"] == word and detail["remaining_task"]["code"] == "NOTHING"


def test_the_decision_record_and_the_picture_use_the_same_rule(api: TestClient) -> None:
    api.post("/demo/reset", params={"scenario": "busy"})
    live = _foshan_live(api)
    agree_on_rcv_a(api)
    lapsed = _lapsed(api)
    assert {d["id"] for d in lapsed} <= {d["id"] for d in live}
    for d in lapsed:
        picture = api.get(f"/offers/{d['id'].split(':', 1)[1]}/picture").json()
        assert picture["available"] is False and "can no longer be drawn" in picture["unavailable_text"]
    for d in _decisions(api):
        if d["state"] == "RESPONSE_READY":  # a live reply is drawn
            assert api.get(f"/offers/{d['id'].split(':', 1)[1]}/picture").json()["available"] is True


def test_on_the_current_seed_the_two_foshan_negotiations_are_lapsed_not_ready(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The seed as it was before the Slice B fix (EX03 agreed at day 0): the queue no longer tiers EX01 and EX02 as Needs you."""
    monkeypatch.setattr("app.api.demo_seed.scenario_seed", lambda name: OLD_SEED)
    assert api.post("/demo/reset", params={"scenario": "busy"}).status_code == 200
    assert len(_lapsed(api)) == 2 and _foshan_live(api) == []
    q = api.get("/deals").json()["queue"]
    assert q["counts"] == {"needs_you": 4, "waiting": 1, "agreements": 1, "customers": 3}  # one row per agreed deal: the promise is folded into it (S5)
    assert api.get("/worklist").json()["counts"] == q["counts"]


@pytest.mark.parametrize("lang,eyebrow", [("en", "Lapsed"), ("zh", "已失效")])
def test_the_customer_overview_says_lapsed_and_shows_no_reply_and_no_figure(api: TestClient, lang: str, eyebrow: str) -> None:
    for fixture in ("EX01_PACKAGE", "EX02_EARLY_1_5"):
        offer_id = api.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
        api.post(f"/offers/{offer_id}/evaluate", json={"fixture_id": fixture})
    before = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()["decision"]
    assert before["kind"] in ("counter", "request")  # both are live: one reply is ready
    agree_on_rcv_a(api)
    body = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()
    decision = body["decision"]
    assert decision["kind"] == "lapsed" and decision["eyebrow"] == eyebrow and decision["authority_text"] is None
    text = decision["text"]
    assert "ready to send" not in text and "可发送" not in text and "建议" not in text and "recommends" not in text
    assert "28,3" not in text and "concession" not in text and "让步" not in text  # no concession figure (the ask's own amount is the buyer's)
    assert ("lapsed" in text) if lang == "en" else ("已失效" in text)
    assert decision["primary"]["label"] != "Review the counter" and decision["primary"]["href"].startswith("/deals?decision=deal%3A")
    assert body["none_text"] is None
    if lang == "zh":
        assert not english_leaks([{k: decision[k] for k in ("eyebrow", "text")}], NAMES)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_exposure_of_a_lapsed_offer_says_there_is_nothing_to_read_not_a_transient_error(
        api: TestClient, lang: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    api.post("/demo/reset", params={"scenario": "busy"})
    agree_on_rcv_a(api)
    [first, _second] = _lapsed(api)
    offer_id = first["id"].split(":", 1)[1]
    for path in (f"/offers/{offer_id}/exposure", f"/decisions/{first['id']}/exposure"):
        r = api.get(path, params={"lang": lang})
        assert r.status_code == 409, (path, r.text)
        detail = r.json()["detail"]
        assert detail["code"] == "OFFER_LAPSED"
        said = detail["message"]
        assert (("has lapsed" in said and "nothing to reply to" in said) if lang == "en" else ("已失效" in said)), said
        assert "try again" not in said.lower() and "cannot project" not in said and "重试" not in said
    # a live offer of the same books still reads
    [live] = [d for d in _decisions(api) if d["counterparty_name"] == "Dongguan Office Supplies Ltd." and d["state"] == "RESPONSE_READY"]
    assert api.get(f"/decisions/{live['id']}/exposure", params={"lang": lang}).status_code == 200


@pytest.mark.parametrize("lang,word", [
    ("en", "Lapsed · the invoice or the dates it was about have since changed"),
    ("zh", "已失效 · 它所针对的发票或日期此后已有变动")])
def test_a_lapse_that_no_agreement_caused_does_not_say_one_did(api: TestClient, lang: str, word: str) -> None:
    """Once the days the Foshan offer named have passed it can no longer be drawn: it is Lapsed, but no agreement settled it."""
    ex = {"fixture_id": "EX01_PACKAGE"}
    offer_id = api.post("/offers", json=ex).json()["offer"]["offer_id"]
    api.post(f"/offers/{offer_id}/evaluate", json=ex)
    assert _lapsed(api) == []
    action = api.get("/home").json()["next_action"]
    done = api.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]}).json()
    assert done["executed"] == 2
    assert _lapsed(api) == []  # the plan has run and the offer is still live
    assert api.post("/clock/advance", json={"to_day": 10}).status_code == 200
    [lapsed] = _lapsed(api, lang)
    assert lapsed["state_text"] == word and lapsed["terminal"] is True
    overview = api.get("/customers/BUYER-1/overview", params={"lang": lang}).json()["decision"]
    assert overview["kind"] == "lapsed" and "another agreement" not in overview["text"] and "另一份协议" not in overview["text"]
    assert api.get("/deals", params={"lang": lang}).json()["queue"]["needs_you"] == []
