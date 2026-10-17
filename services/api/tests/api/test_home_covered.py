"""The Home says the cash is covered only when it is (17 Oct, day 77 of a take: "You're covered!" and "All clear" beside "Cash available
today ¥155,000, ¥145k below your ¥300k minimum").

The projection closes each day after the money due that day: at day 77 of the golden story the ¥420k Foshan owes is due today, so no day
of the forecast is under the reserve while the bank holds ¥155k. The one rule (`cash.covered`, `home_v2.action.covered`): nothing to fund,
the cash in the bank today at or above the minimum, and no day ahead under it. The headline, the status badge, the hybrid's position and
the Home V2 card follow it, in English and in Chinese; the words are the server's.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
EX01 = {"fixture_id": "EX01_PACKAGE"}
COVERED_WORDS = ("You're covered", "covered on", "All clear", "您的现金是安全的", "您的现金很安全", "一切正常")
HAN = re.compile(r"[一-鿿]")


@pytest.fixture
def api() -> Iterator[TestClient]:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset_demo("golden_sme")
    set_runtime(rt)
    from app.main import app

    yield TestClient(app, headers=OWNER)
    set_runtime(None)


def _home(api: TestClient, lang: str = "en") -> dict[str, Any]:
    r = api.get(f"/home?lang={lang}")
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def _says_covered(h: dict[str, Any]) -> bool:
    c, a = h["cash"], h["home_v2"]["action"]
    said = " ".join(str(x) for x in (h["headline"], h["status_text"], c.get("status_word"), c.get("headline_conditional"), a["title"],
                                     a.get("covered_pill_text"), a.get("covered_title_text")) if x)
    return any(w in said for w in COVERED_WORDS)


def _consistent(h: dict[str, Any]) -> None:
    """The one rule, and every word on the page agreeing with the figures beside it."""
    c, a = h["cash"], h["home_v2"]["action"]
    under_today = c["cash_fen"] < c["floor_fen"]
    under_ahead = c["lowest_fen"] < c["floor_fen"] or c["first_breach_day"] is not None
    expected = not under_today and not under_ahead and h["next_action"] is None
    assert c["covered"] is expected and a["covered"] is expected
    assert _says_covered(h) is expected, (h["headline"], a["title"])
    assert c["below_reserve_today"] is (under_today or c["first_breach_day"] == h["day"])
    if expected:
        assert a["variant"] == "QUIET" and a["covered_pill_text"] and a["covered_title_text"]
    else:
        assert a["variant"] == "ACTION" and h["status"] not in ("SAFE", "WATCH")


def _plan(api: TestClient) -> None:
    h = _home(api)
    n = h["next_action"]
    r = api.post(f"/alerts/{n['alert_id']}/act", json={"state_version": h["state_version"], "suggestions": n["suggestions"]})
    assert r.status_code == 200, r.text


def _story_to_day_34(api: TestClient) -> None:
    offer = api.post("/offers", json=EX01).json()["offer"]["offer_id"]
    v = api.post(f"/offers/{offer}/evaluate", json=EX01).json()
    sent = api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative", "verdict_id": v["id"], "counter_id": v["counters"][0]["id"],
                                                 "state_version": v["state_version"]})
    assert sent.json()["outcome"] == "DEAL"
    assert api.post("/clock/advance", json={"to_day": 2}).status_code == 200
    assert api.post("/demo/bank-receipt").status_code == 200
    assert api.post("/clock/advance", json={"to_day": 34}).status_code == 200


def _cure_and_approve(api: TestClient) -> None:
    _plan(api)
    from app.api.runtime import get_runtime

    for a in get_runtime().store.approvals():
        if a.status.value == "PENDING":
            assert api.post(f"/approvals/{a.id}", json={"decision": "APPROVE"}).status_code == 200


def test_day_zero_is_not_covered(api: TestClient) -> None:
    h = _home(api)
    _consistent(h)
    assert h["cash"]["covered"] is False and h["next_action"] is not None


def test_after_the_plan_runs_the_cash_is_covered_in_the_servers_words(api: TestClient) -> None:
    _plan(api)
    h = _home(api)
    _consistent(h)
    a = h["home_v2"]["action"]
    assert h["cash"]["covered"] is True and a["covered"] is True
    assert (a["covered_pill_text"], a["covered_title_text"]) == ("All clear", "You're covered!")
    zh = _home(api, "zh")["home_v2"]["action"]
    assert zh["covered"] is True and HAN.search(zh["covered_pill_text"]) and HAN.search(zh["covered_title_text"])


def test_day_34_the_late_receipt_is_not_covered_and_the_cure_covers_it(api: TestClient) -> None:
    _story_to_day_34(api)
    h = _home(api)
    _consistent(h)
    assert h["cash"]["covered"] is False and h["cash"]["first_breach_day"] is not None
    _cure_and_approve(api)
    h = _home(api)
    _consistent(h)
    assert h["cash"]["covered"] is True  # cash sits exactly on the minimum: "at or above" is covered


def test_day_77_cash_under_the_minimum_today_is_never_covered(api: TestClient) -> None:
    """The take's state: the forecast never closes a day under the reserve (the ¥420k due today counts), the bank holds less than it."""
    _story_to_day_34(api)
    _cure_and_approve(api)
    for day in (38, 48, 77):
        assert api.post("/clock/advance", json={"to_day": day}).status_code == 200
        _consistent(_home(api))
    for lang in ("en", "zh"):
        h = _home(api, lang)
        c, a = h["cash"], h["home_v2"]["action"]
        assert c["cash_fen"] < c["floor_fen"] and c["first_breach_day"] is None and c["lowest_fen"] >= c["floor_fen"]  # the take's state
        _consistent(h)
        assert c["covered"] is False and a["covered"] is False and c["below_reserve_today"] is True
        assert h["status"] == "ACTION_NEEDED" and a["variant"] == "ACTION" and a["tone"] == "bad"
        assert a["primary"]["href"] == "/cash#cash-options"
        if lang == "en":
            assert h["headline"] == "Below reserve today." and c["headline_conditional"] == "Below reserve today."
            assert h["note"].startswith(f"Cash is {c['headroom_short'].lstrip('-−')} below your {c['floor_short']} minimum cash reserve right now.")
            assert a["title"] == h["headline"] and a["text"] == h["note"]
        else:
            for said in (h["headline"], h["note"], a["eyebrow"], a["title"], a["primary"]["label"]):
                assert HAN.search(said), said
