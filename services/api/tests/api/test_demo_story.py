"""GET /demo/story and POST /demo/restore (Slice D, ticket #145): where the story stands is derived from the books; one next control;
the owner's step is never pressed; the alternate scenario shows what it would lose and the restore brings the day-0 books back."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app.api import offer_picture, worklist
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
ID_PATTERN = re.compile(r"\b(?:APR|DOC|RCV|COM|FAC|BUYER|OFF|CTR|VER|SEC|ALERT)-[\w-]+|\bdeal:|\b[A-Z]{2,}_[A-Z_]+\b|\b[a-z]+:[A-Z0-9]{3,}")
DAY_N = re.compile(r"\bday\s*\d+", re.IGNORECASE)


@pytest.fixture
def rt() -> Iterator[Runtime]:
    runtime = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    runtime.reset_demo("golden_sme")
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


def _story(api: TestClient, **params: str) -> dict[str, Any]:
    r = api.get("/demo/story", params=params)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def _current(body: dict[str, Any]) -> str:
    assert body["current"] is not None
    return str(body["current"]["step_id"])


def _one_next(body: dict[str, Any]) -> None:
    assert isinstance(body["next"], dict) and body["next"]["label"]
    assert sum(1 for s in body["scenes"] for st in s["steps"] if st["state"] == "current") == (0 if body["current"] is None else 1)
    assert sum(1 for s in body["scenes"] if s["state"] == "current") == (0 if body["current"] is None else 1)


# the story's steps, driven through the routes the web calls (apps/web/lib/demo.ts)
def _ask(api: TestClient, rt: Runtime) -> str:
    return str(api.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"])


def _decide(api: TestClient, offer: str) -> dict[str, Any]:
    return api.post(f"/offers/{offer}/evaluate", json={"fixture_id": "EX01_PACKAGE"}).json()  # type: ignore[no-any-return]


def _agree(api: TestClient, offer: str, v: dict[str, Any]) -> None:
    sent = api.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative", "verdict_id": v["id"], "counter_id": v["counters"][0]["id"],
                                                  "state_version": v["state_version"]})
    assert sent.json()["outcome"] == "DEAL"


def _queue(api: TestClient) -> None:
    h = api.get("/home").json()
    n = h["next_action"]
    assert api.post(f"/alerts/{n['alert_id']}/act", json={"state_version": h["state_version"], "suggestions": n["suggestions"]}).status_code == 200


def _all_hrefs(body: dict[str, Any]) -> list[str]:
    return [link["href"] for s in body["scenes"] for link in s["proof"]]


def _check_href(api: TestClient, rt: Runtime, href: str) -> None:
    """A proof link lands on a record that exists."""
    if href.startswith("/trust?view=evidence&entry="):
        assert int(re.search(r"entry=(\d+)", href).group(1)) in {o.seq for o in rt.store.operations()}  # type: ignore[union-attr]
    elif href.startswith("/decisions/"):
        assert api.get(f"/decisions/{unquote(href[len('/decisions/'):])}").status_code == 200
    elif href.startswith("/approvals#approval-"):
        assert rt.store.get_approval(href.split("approval-", 1)[1]) is not None
    else:
        assert href.startswith("/trust?view=")


def _words(body: dict[str, Any], lang: str) -> None:
    texts: list[str] = [body["title_text"], body["subtitle_text"], body["progress_text"], body["simulation_text"], body["next"]["label"],
                        body["next"]["hint_text"], body["proof"]["title_text"], body["proof"]["text"]]
    for s in body["scenes"]:
        texts += [s["label"], s["state_text"], *(st["label"] for st in s["steps"]), *(p["label"] for p in s["proof"])]
        texts += [s["result_text"]] if s["result_text"] else []
    alt = body["alternate"]
    texts += [alt[k] for k in alt if k.endswith("_text") and alt[k]] + [alt["label"], alt["confirm_label"], alt["restore_label"], *alt["loss_items"]]
    texts += [h["text"] for h in alt["history"]]
    if body["current"]:
        texts += [body["current"]["title_text"], body["current"]["text"], *([body["current"]["owner_text"]] if body["current"]["owner_text"] else [])]
    for s in texts:
        assert not ID_PATTERN.search(s), s
        assert not DAY_N.search(s), s
        assert "None" not in s and "{" not in s, s
        if lang == "zh":
            assert re.search(r"[一-鿿]", s) or not re.search(r"[A-Za-z]{4,}", s), s


def test_fresh_golden_books(api: TestClient) -> None:
    body = _story(api)
    assert body["main"] and body["story_available"] and not body["complete"] and body["scenario"] == "golden_sme"
    assert body["progress_text"] == "Scene 1 of 6" and _current(body) == "ask"
    assert [s["state"] for s in body["scenes"]] == ["current", "next", "locked", "locked", "locked", "locked"]
    assert [s["state_text"] for s in body["scenes"]][:3] == ["Now", "Next", "Later"]
    _one_next(body)
    assert body["next"]["action"] == "ask" and body["next"]["href"] is None and body["next"]["owner"] is False
    assert all(s["proof"] == [] and s["result_text"] is None for s in body["scenes"])
    alt = body["alternate"]
    assert alt["loaded"] is False and alt["loaded_text"] is None and alt["scenario"] == "busy" and alt["label"] == "Load alternate scenario"
    assert alt["loss_items"] == ["Nothing has been done yet, so nothing is lost."]
    assert [g["key"] for g in body["operator_tools"]["groups"]] == ["clock", "books", "engine"]
    assert body["proof"]["chain"]["chain_text"] and body["proof"]["links"][2]["href"] == "/ledger"
    _words(body, "en")
    _words(_story(api, lang="zh"), "zh")


def test_each_book_changing_step_moves_the_story_on(api: TestClient, rt: Runtime) -> None:
    offer = _ask(api, rt)
    body = _story(api)
    assert _current(body) == "decide" and body["scenes"][0]["state"] == "done" and body["progress_text"] == "Scene 2 of 6"
    _one_next(body)
    v = _decide(api, offer)
    assert _current(_story(api)) == "agree"
    _agree(api, offer, v)
    body = _story(api)
    assert _current(body) == "cash" and body["next"]["action"] == "cash" and body["scenes"][2]["state"] == "current"
    assert body["scenes"][2]["steps"][0]["state"] == "done"
    # the cash step changes nothing: it cannot be derived, so only the browser's `seen` advances it
    assert _current(_story(api, seen="cash")) == "bank"
    assert api.post("/clock/advance", json={"to_day": 2}).status_code == 200
    assert _current(_story(api, seen="cash")) == "bank"  # the clock alone records no receipt
    assert api.post("/demo/bank-receipt").status_code == 200
    body = _story(api, seen="cash")
    assert _current(body) == "time" and body["scenes"][3]["state"] == "current"
    api.post("/clock/advance", json={"to_day": 34})
    body = _story(api, seen="cash")
    assert _current(body) == "queue" and body["scenes"][3]["state"] == "done" and "Time then passed" in body["scenes"][3]["result_text"]
    _one_next(body)
    _queue(api)
    body = _story(api, seen="cash")
    assert _current(body) == "approve" and body["current"]["owner"] is True
    # the owner's step: no action, a link to the approval, and the words that the story never presses it
    nxt = body["next"]
    assert nxt["action"] is None and nxt["owner"] is True and nxt["href"].startswith("/approvals#approval-APR-")
    assert "never presses it" in body["current"]["owner_text"]
    approve_step = next(st for s in body["scenes"] for st in s["steps"] if st["id"] == "approve")
    assert approve_step["owner"] is True and approve_step["state"] == "current"
    assert _story(api, seen="cash")["next"]["action"] is None  # asking again does not approve anything
    assert [a.status.value for a in rt.store.approvals()] == ["PENDING"]
    _check_proof(api, rt, _story(api, seen="cash"))
    # the owner's own click
    approval = rt.store.approvals()[0].id
    assert api.post(f"/approvals/{approval}", json={"decision": "APPROVE"}).status_code == 200
    assert _current(_story(api, seen="cash")) == "settle"
    api.post("/clock/advance", json={"to_day": 39})
    body = _story(api, seen="cash")
    assert _current(body) == "outcome" and body["scenes"][4]["state"] == "done"
    assert _current(_story(api, seen="outcome")) == "proof" and _story(api, seen="outcome")["complete"] is False
    done = _story(api, seen="proof")
    assert done["complete"] is True and done["current"] is None and done["progress_text"] == "All 6 scenes are done"
    assert done["next"]["action"] == "restart" and all(s["state"] == "done" for s in done["scenes"])
    _one_next(done)
    _check_proof(api, rt, done)
    for lang in ("en", "zh"):
        _words(_story(api, seen="proof", lang=lang), lang)
    # loss preview on the played books names what exists
    alt = done["alternate"]
    text = " ".join(alt["loss_items"])
    assert "6 of 6 scenes" in text and "1 offer" in text and "1 agreement" in text and "approvals" not in text and "1 approval" in text
    assert "entries in the record" in text and "The clock goes back to the start" in text


def _check_proof(api: TestClient, rt: Runtime, body: dict[str, Any]) -> None:
    hrefs = _all_hrefs(body)
    assert hrefs
    for h in hrefs:
        _check_href(api, rt, h)
    for s in body["scenes"]:
        assert bool(s["proof"]) == (s["state"] == "done") or s["id"] in ("buyer", "decision")  # proof only for done scenes
        assert s["state"] == "done" or s["proof"] == []
        assert (s["result_text"] is not None) == (s["state"] == "done")


def test_seen_advances_only_a_view_step_and_is_ignored_when_unsupported(api: TestClient, rt: Runtime) -> None:
    # nothing done: a seen the books do not support is ignored, never an error
    for seen in ("cash", "outcome", "proof", "decide", "approve", "nonsense", ""):
        body = _story(api, seen=seen)
        assert _current(body) == "ask", seen
    offer = _ask(api, rt)
    assert _current(_story(api, seen="proof")) == "decide"
    _agree(api, offer, _decide(api, offer))
    # a book-changing step id is never accepted as "seen"
    assert _current(_story(api, seen="bank")) == "cash"
    assert _current(_story(api, seen="outcome")) == "cash"  # the steps before it do not all hold
    assert _current(_story(api, seen="cash")) == "bank"
    assert api.get("/demo/story", params={"seen": "cash"}).status_code == 200
    assert len(rt.store.operations()) == 5  # three documents, the agreement, its funding: reading changed nothing


def test_the_busy_books_are_loaded_without_a_story(api: TestClient, rt: Runtime) -> None:
    from app.api import receivables as receivables_mod

    assert api.post("/demo/reset", params={"scenario": "busy"}).json() == {"ok": True, "scenario": "busy", "day": 0}
    body = _story(api)
    assert body["main"] is False and body["story_available"] is False and body["scenario"] == "busy" and body["complete"] is False
    assert all(s["state"] == "locked" and s["state_text"] == "Later" and s["proof"] == [] for s in body["scenes"])
    assert body["current"] is None
    assert body["next"] == {"label": "Open Home on these books", "action": None, "href": "/", "hint_text": body["next"]["hint_text"], "owner": False}
    alt = body["alternate"]
    assert alt["loaded"] is True and alt["loaded_text"].startswith("You are on the alternate books (Busy company)")
    # the scope is the books' own counts: the worklist, the Deals queue and the Receivables read
    queue = api.get("/deals").json()["queue"]
    overdue = receivables_mod.read_rows(rt, "en")[2]["summary"]["overdue_count"]
    scope = alt["scope_text"]
    assert f"{queue['counts']['customers']} customers" in scope
    assert f"{sum(1 for r in queue['needs_you'] if r['kind'] == 'DECISION')} negotiations waiting for your decision" in scope
    assert f"{queue['counts']['agreements']} agreements in force" in scope or f"{queue['counts']['agreements']} agreement in force" in scope
    assert f"{overdue} overdue invoice" in scope
    assert f"{sum(1 for a in rt.store.approvals() if a.status.value == 'PENDING')} approval waiting for you" in scope
    assert alt["history"][0]["text"] == "The main books were replaced by the busy company." and alt["history"][0]["when"] == "just now"
    _words(body, "en")
    zh = _story(api, lang="zh")
    assert zh["alternate"]["loaded"] and zh["next"]["label"] == "在这些账目上打开首页"
    _words(zh, "zh")


def test_the_loss_preview_names_what_exists(api: TestClient, rt: Runtime) -> None:
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    api.post("/clock/advance", json={"to_day": 2})
    alt = _story(api)["alternate"]
    assert alt["loss_items"] == ["Your place in the story: 3 of 6 scenes have run.", "1 offer FLOW has read and priced.", "1 agreement on the books.",
                                 "3 entries in the record.", "The clock goes back to the start: 2 days of simulated time are undone."]
    assert alt["loss_preview_text"].startswith("Loading it replaces the main books. You would lose:")
    assert alt["confirm_title_text"] == "Load the busy company?" and alt["cancel_label"] == "Keep the main books"
    assert alt["restore_label"] == "Restore the main books" and alt["keeps_text"] and alt["restore_text"]
    # nothing was replaced by reading it
    assert rt.scenario == "golden_sme" and len(rt.store.commitments()) == 1


def _day_zero(api: TestClient, rt: Runtime) -> dict[str, Any]:
    home = api.get("/home").json()
    return {"ops": [o.kind for o in rt.store.operations()], "commitments": len(rt.store.commitments()), "approvals": len(rt.store.approvals()),
            "security": len(rt.store.security_events()), "day": rt.day, "scenario": rt.scenario, "cash": home["cash"]["cash_short"]}


def test_restore_brings_back_the_day_zero_books(api: TestClient, rt: Runtime) -> None:
    fresh = _day_zero(api, rt)
    assert fresh["ops"] == ["CONFIRM_DOCUMENT"] * 3 and fresh["day"] == 0
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    api.post("/clock/advance", json={"to_day": 34})
    assert _day_zero(api, rt) != fresh
    api.post("/demo/reset", params={"scenario": "busy"})
    assert _day_zero(api, rt)["scenario"] == "busy"
    r = api.post("/demo/restore", params={"lang": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["scenario"] == "golden_sme" and body["day"] == 0
    assert body["restored_text"] == "The main books are back at the start of the story."
    assert _day_zero(api, rt) == fresh
    story = body["story"]
    assert story["main"] and _current(story) == "ask" and story["alternate"]["loaded"] is False
    assert [h["text"] for h in story["alternate"]["history"]] == ["The main books were restored.", "The main books were replaced by the busy company."]
    # the same counts as a fresh reset_demo("golden_sme")
    api.post("/demo/reset", params={"scenario": "golden_sme"})
    assert _day_zero(api, rt) == fresh
    zh = api.post("/demo/restore", params={"lang": "zh"}).json()
    assert zh["restored_text"] == "主账目已回到故事的起点。"
    _words(zh["story"], "zh")


def test_replaying_the_story_on_the_main_books_is_not_a_swap(api: TestClient, rt: Runtime) -> None:
    api.post("/demo/reset", params={"scenario": "golden_sme"})
    assert rt.demo_history == []


def test_unknown_scenario_and_credentials(api: TestClient, rt: Runtime) -> None:
    from app.main import app

    assert TestClient(app).get("/demo/story").status_code == 401
    assert TestClient(app).post("/demo/restore").status_code == 401
    assert api.post("/demo/reset", params={"scenario": "nope"}).status_code == 422
    assert rt.demo_history == []


def test_each_step_has_its_own_hint_and_the_owner_step_says_the_plan_waits(api: TestClient, rt: Runtime) -> None:
    from app.api import demo_story

    for lang in ("en", "zh"):
        for sid, scene, _, owner in demo_story.STEPS:
            books = demo_story._Books("OFF-x", {}, type("A", (), {"id": "APR-1"})() if owner else None, [])
            cur = [s[0] for s in demo_story.STEPS].index(sid)
            nxt = demo_story._next(lang, True, cur, books, False)
            text = demo_story.t(lang, demo_story._STEP[sid][2], demo_story._STEP[sid][3])
            assert nxt["hint_text"] != text and "this button" not in (nxt["hint_text"] + text).lower() and "这个按钮" not in nxt["hint_text"] + text
    for sid in ("approve",):
        en = demo_story.t("en", demo_story._STEP[sid][2], demo_story._STEP[sid][3])
        assert "outside what FLOW may run alone" in en and "approval card" in en


# ---------------------------------------------------------------- the verifier's attack on "the main books cannot be silently replaced"


def _counts(rt: Runtime) -> tuple[int, int, int, int, str]:
    return len(rt.store.operations()), len(rt.store.approvals()), len(rt.store.commitments()), len(rt.store.security_events()), rt.scenario


def _wrong_token(n: int) -> None:
    from app.main import app

    for _ in range(n):
        assert TestClient(app, headers={"X-Owner-Token": "wrong"}).get("/home").status_code == 401


def test_security_events_are_part_of_what_a_reset_loses(api: TestClient, rt: Runtime) -> None:
    api.post("/demo/reset")
    assert _story(api)["alternate"]["nothing_to_lose"] is True
    _wrong_token(3)
    assert len(rt.store.security_events()) == 3
    body = _story(api)
    assert body["alternate"]["nothing_to_lose"] is False and body["books"]["nothing_to_lose"] is False
    assert "3 security events in the record." in body["alternate"]["loss_items"] and "nothing is lost" not in " ".join(body["alternate"]["loss_items"])
    assert "3 条安全事件" in " ".join(_story(api, lang="zh")["books"]["loss_items"])
    # the attack-message scene: the offer and the events it recorded are both named
    sec = api.post("/offers", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}).json()["offer"]["offer_id"]
    api.post(f"/offers/{sec}/evaluate", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"})
    items = " ".join(_story(api)["books"]["loss_items"])
    assert f"{len(rt.store.security_events())} security events" in items
    api.post("/demo/restore")
    assert len(rt.store.security_events()) == 0 and _story(api)["books"]["nothing_to_lose"] is True


def test_the_books_block_on_main_and_busy(api: TestClient, rt: Runtime) -> None:
    fresh = _story(api)["books"]
    assert fresh["scenario"] == "golden_sme" and fresh["main"] is True and fresh["nothing_to_lose"] is True
    assert fresh["reset_confirm_title_text"] == "Reset the books?" and fresh["reset_confirm_label"] == "Reset the books"
    assert fresh["loss_title_text"] == "What the main books lose" and fresh["reset_cancel_label"] and fresh["reset_keeps_text"]
    reset = next(i for g in _story(api)["operator_tools"]["groups"] for i in g["items"] if i.get("action") == "reset")
    assert reset["replaces_books"] is True
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    played = _story(api)
    assert played["books"]["nothing_to_lose"] is False and played["books"]["loss_items"] == played["alternate"]["loss_items"]
    assert "1 agreement on the books." in played["books"]["loss_items"]
    api.post("/demo/reset", params={"scenario": "busy"})
    busy = _story(api)
    # a freshly loaded busy company has nothing beyond what its own seed wrote
    assert busy["books"]["scenario"] == "busy" and busy["books"]["main"] is False and busy["books"]["nothing_to_lose"] is True
    assert busy["books"]["reset_confirm_title_text"] == "Reset these books?" and busy["alternate"]["nothing_to_lose"] is True
    _wrong_token(1)
    after = _story(api)
    assert after["books"]["nothing_to_lose"] is False and "1 security event in the record." in after["books"]["loss_items"]
    zh = _story(api, lang="zh")
    assert zh["books"]["reset_confirm_title_text"] == "重置这些账目？"
    _words(zh, "zh")


def test_a_stale_page_cannot_swap_the_books(api: TestClient, rt: Runtime) -> None:
    # a page was read on the busy books; meanwhile the books were restored and the story walked
    api.post("/demo/reset", params={"scenario": "busy"})
    api.post("/demo/restore")
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    before = _counts(rt)
    r = api.post("/demo/reset", params={"scenario": "busy", "from_scenario": "busy", "confirm_loss": "1", "lang": "en"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "BOOKS_CHANGED"
    assert r.json()["detail"]["message_when"] == "The books changed since this page was read; nothing was reset."
    zh = api.post("/demo/reset", params={"scenario": "busy", "from_scenario": "busy", "lang": "zh"}).json()["detail"]
    assert zh["code"] == "BOOKS_CHANGED" and "账目已发生变化" in zh["message_when"] and zh["message"].endswith("nothing was reset.")
    restore = api.post("/demo/restore", params={"from_scenario": "busy", "confirm_loss": "1"})
    assert restore.status_code == 409 and restore.json()["detail"]["code"] == "BOOKS_CHANGED"
    assert _counts(rt) == before
    # the right scenario, but the loss is not confirmed
    for call in (lambda **k: api.post("/demo/reset", params={"scenario": "busy", "from_scenario": "golden_sme", **k}),
                 lambda **k: api.post("/demo/restore", params={"from_scenario": "golden_sme", **k})):
        r = call()
        assert r.status_code == 409 and r.json()["detail"]["code"] == "LOSS_NOT_CONFIRMED"
        assert "1 agreement on the books." in r.json()["detail"]["loss_items"] and r.json()["detail"]["message_when"].endswith("nothing was reset.")
        assert call(confirm_loss="0").status_code == 409
        assert _counts(rt) == before
    ok = api.post("/demo/reset", params={"scenario": "busy", "from_scenario": "golden_sme", "confirm_loss": _story(api)["books"]["loss_token"]})
    assert ok.status_code == 200 and rt.scenario == "busy"
    ok = api.post("/demo/restore", params={"from_scenario": "busy", "confirm_loss": "1"})
    assert ok.status_code == 200 and rt.scenario == "golden_sme" and ok.json()["story"]["main"] is True


def test_nothing_to_lose_needs_no_confirmation_and_old_callers_are_unchanged(api: TestClient, rt: Runtime) -> None:
    assert api.post("/demo/reset", params={"scenario": "busy", "from_scenario": "golden_sme"}).status_code == 200  # fresh books
    assert api.post("/demo/restore", params={"from_scenario": "busy"}).status_code == 200  # a fresh busy company loses nothing
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    assert api.post("/demo/reset", params={"scenario": "golden_sme"}).status_code == 200  # no parameters: as it always was
    assert len(rt.store.commitments()) == 0
    assert api.post("/demo/restore").status_code == 200


def test_the_history_notes_only_a_real_change(api: TestClient, rt: Runtime) -> None:
    api.post("/demo/restore")  # untouched main books: nothing to note
    assert rt.demo_history == []
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    api.post("/demo/restore")  # the reset discarded an agreement: that is worth saying
    assert [h["kind"] for h in rt.demo_history] == ["restore"]
    api.post("/demo/reset", params={"scenario": "busy"})
    api.post("/demo/restore")
    assert [h["kind"] for h in rt.demo_history] == ["restore", "swap", "restore"]


def test_a_declined_cure_has_its_own_words(api: TestClient, rt: Runtime) -> None:
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    api.post("/clock/advance", json={"to_day": 2})
    api.post("/demo/bank-receipt")
    api.post("/clock/advance", json={"to_day": 34})
    _queue(api)
    waiting = _story(api, seen="cash")
    assert "waits for the owner" in waiting["current"]["text"] and waiting["current"]["owner_text"]
    assert api.post(f"/approvals/{rt.store.approvals()[0].id}", json={"decision": "REJECT"}).status_code == 200
    for lang, word in (("en", "declined"), ("zh", "拒绝")):
        body = _story(api, seen="cash", lang=lang)
        cur = body["current"]
        assert word in cur["title_text"] and word in cur["text"] and cur["owner"] is False and cur["owner_text"] is None
        assert "waits" not in cur["text"] and "open the approval" not in cur["text"].lower()
        assert body["next"]["action"] == "restart"
        _words(body, lang)


# ---------------------------------------------------------------- the confirmation is bound to the loss it was shown; owner work counts


def _token(api: TestClient) -> str:
    body = _story(api)
    assert body["books"]["loss_token"] == body["alternate"]["loss_token"]
    return str(body["books"]["loss_token"])


def _upload_contract(api: TestClient) -> dict[str, Any]:
    r = api.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"})
    assert r.status_code == 200, r.text
    return r.json()["document"]  # type: ignore[no-any-return]


def _input(api: TestClient) -> None:
    body = {"field": "typical_delay_days", "value": 15, "provenance": "OWNER_ENTERED", "source_ref": "the owner's call"}
    assert api.post("/buyers/BUYER-1/inputs", json=body).status_code == 200


def _detail(r: Any) -> dict[str, Any]:
    return r.json()["detail"]  # type: ignore[no-any-return]


def test_a_confirmation_given_for_one_loss_does_not_cover_another(api: TestClient, rt: Runtime) -> None:
    # the page was opened on fresh books: its dialog said nothing is lost, so it holds no token (or the fresh one)
    old = _token(api)
    assert _story(api)["books"]["nothing_to_lose"] is True
    offer = _ask(api, rt)
    _agree(api, offer, _decide(api, offer))
    before = _counts(rt)
    new = _token(api)
    assert new != old
    params = {"scenario": "busy", "from_scenario": "golden_sme"}
    stale = api.post("/demo/reset", params={**params, "confirm_loss": old})
    assert stale.status_code == 409 and _detail(stale)["code"] == "LOSS_CHANGED" and _detail(stale)["loss_token"] == new
    assert "1 agreement on the books." in _detail(stale)["loss_items"]
    assert _detail(stale)["message"] == "The books changed since this list was shown; nothing was reset."
    assert "清单" in _detail(api.post("/demo/reset", params={**params, "confirm_loss": old, "lang": "zh"}))["message_when"]
    assert _counts(rt) == before
    # the old literal is no confirmation, and a missing value is a different refusal
    assert _detail(api.post("/demo/reset", params={**params, "confirm_loss": "1"}))["code"] == "LOSS_CHANGED"
    assert _detail(api.post("/demo/restore", params={"from_scenario": "golden_sme", "confirm_loss": "1"}))["code"] == "LOSS_CHANGED"
    missing = api.post("/demo/reset", params=params)
    assert _detail(missing)["code"] == "LOSS_NOT_CONFIRMED" and _detail(missing)["loss_token"] == new
    assert _counts(rt) == before
    ok = api.post("/demo/reset", params={**params, "confirm_loss": new})
    assert ok.status_code == 200 and rt.scenario == "busy"


def test_owner_work_counts_as_something_to_lose(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    def check(label: str, expect_line: str | None) -> None:
        body = _story(api)
        assert body["books"]["nothing_to_lose"] is False and body["alternate"]["nothing_to_lose"] is False, label
        items = body["books"]["loss_items"]
        assert items and "nothing is lost" not in " ".join(items), label
        if expect_line:
            assert any(expect_line in i for i in items), (label, items)
        before = _counts(rt)
        r = api.post("/demo/reset", params={"scenario": "busy", "from_scenario": "golden_sme"})
        assert r.status_code == 409 and _detail(r)["code"] == "LOSS_NOT_CONFIRMED" and _detail(r)["loss_items"], label
        assert _counts(rt) == before, label
        assert _words_ok(body)

    def _words_ok(body: dict[str, Any]) -> bool:
        return all(not ID_PATTERN.search(i) and "None" not in i for i in body["books"]["loss_items"])

    # a document read (and not decided)
    api.post("/demo/reset")
    d = _upload_contract(api)
    check("a document read", "1 document read.")
    # the same document confirmed: 4 record entries
    assert api.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}).status_code == 200
    check("a document confirmed", "1 document confirmed.")
    assert len(rt.store.operations()) == 4
    # a document rejected
    api.post("/demo/reset")
    d = _upload_contract(api)
    assert api.post(f"/documents/{d['id']}/reject", json={"doc_hash": d["doc_hash"]}).status_code == 200
    check("a document rejected", "1 document rejected.")
    # a customer input
    api.post("/demo/reset")
    _input(api)
    check("a customer input", "1 customer input entered.")
    zh = _story(api, lang="zh")["books"]["loss_items"]
    assert zh and any("客户信息" in i for i in zh)


def test_the_list_is_never_empty_while_something_would_be_lost(api: TestClient, rt: Runtime) -> None:
    # a change no named line accounts for: the books moved without a count changing
    api.post("/demo/reset")
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"cash_fen": state.cash_fen + 1}), expected_version=state.state_version)
    body = _story(api)
    assert body["books"]["nothing_to_lose"] is False and body["books"]["loss_items"] == ["Other changes made to these books since they were reset."]
    # a record entry no named line accounts for (a document decision with no document behind it) is said as "other entries"
    rt.store.append_operation("x-op", "CONFIRM_DOCUMENT", "x-key", "{}", "{}")
    items = _story(api)["books"]["loss_items"]
    assert "1 other entry in the record." in items


def test_fresh_books_have_nothing_to_lose_and_reset_without_a_token(api: TestClient, rt: Runtime) -> None:
    for scenario in ("golden_sme", "busy"):
        api.post("/demo/reset", params={"scenario": scenario})
        books = _story(api)["books"]
        assert books["nothing_to_lose"] is True and books["scenario"] == scenario
        r = api.post("/demo/reset", params={"scenario": scenario, "from_scenario": scenario})
        assert r.status_code == 200, r.text
    assert api.post("/demo/restore", params={"from_scenario": "busy"}).status_code == 200
    assert _story(api)["books"]["nothing_to_lose"] is True


def test_the_token_is_stable_until_something_changes(api: TestClient, rt: Runtime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_EXPOSURE", "1")
    api.post("/demo/reset")
    base = _token(api)
    assert _token(api) == base and _token(api) == base
    assert api.get("/activity").status_code == 200 and api.get("/home").status_code == 200
    assert _token(api) == base  # reads change nothing
    seen = {base}

    def changed(label: str) -> None:
        tok = _token(api)
        assert tok not in seen, label
        seen.add(tok)

    api.post("/offers", json={"fixture_id": "EX01_PACKAGE"})
    changed("an offer")
    _upload_contract(api)
    changed("a document")
    _input(api)
    changed("a customer input")
    _wrong_token(1)
    changed("a wrong-token request")
    api.post("/clock/advance", json={"to_day": 1})
    changed("a clock move")
