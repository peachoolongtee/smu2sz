"""OUT-1: once the owner has sent the buyer a counter themself (an OFFERED fact), the chat does not answer the request either.

The routes refuse with 409 OFFER_SENT_OUTSIDE (app/api/accept.py, app/api/decide.py). The chat applies the same rule
(`app.api.decisions.sent_outside_conflict`) on every path that would accept, decline, send a counter or negotiate: it answers with that
refusal's own sentence, executes nothing, logs no operation and sends the buyer nothing. Reading the offer stays open.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.decisions import record_fact
from app.api.runtime import Runtime
from app.decisions.facts import OfferedFact
from app.decisions.identity import deal_id
from tests.nl.conftest import OWNER, Chat, ops

EX02 = "EX02_EARLY_1_5"
EARLY_ACCEPT = "Should we accept this from Foshan? “We can pay the ¥420,000 invoice early at 0.5%. Nothing else changes.”"
REFUSAL = {"en": "You sent the buyer a counter yourself; record their answer on the deal instead.",
           "zh": "您已亲自向买方发出还价；请改为在这笔交易上记录对方的答复。"}
OFFER_KINDS = ("ACCEPT_OFFER", "REJECT_OFFER", "COUNTER_OFFER")


def _mark_through_the_route(client: TestClient, fixture: str) -> str:
    """The owner copies Option A's message and marks it sent outside FLOW (POST .../offered), as tests/api/test_buyer_message.py does."""
    oid = client.post("/offers", json={"fixture_id": fixture}, headers=OWNER).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fixture}, headers=OWNER).json()
    cid = v["counters"][0]["id"]
    m = client.get(f"/offers/{oid}/counters/{cid}/message", params={"lang": "en"}, headers=OWNER).json()
    r = client.post(f"/offers/{oid}/counters/{cid}/offered", headers=OWNER,
                    json={"verdict_id": v["id"], "state_version": v["state_version"], "message_hash": m["message_hash"], "lang": "en"})
    assert r.status_code == 200, r.text
    return oid


def _mark_fact(rt: Runtime, offer_id: str, verdict_id: str) -> None:
    """The same OFFERED fact the route stores, for a request whose verdict has no counter of its own to mark through the route (its
    books moved since the owner sent theirs)."""
    offer = rt.store.get_offer(offer_id)
    assert offer is not None
    version = rt.store.get_state().state_version
    fact = OfferedFact(offer_id=offer_id, verdict_id=verdict_id, counter_id="C-OWN", counterparty_id=offer.counterparty_id,
                       state_version_shown=version, terms_hash="t" * 64, message_hash="m" * 64, template_version="v1", lang="en",
                       valid_until_day=rt.day + 2)
    assert record_fact(rt, deal_id(offer_id), f"{verdict_id}:C-OWN", fact, state_version=version, day=rt.day) is True


def _snapshot(rt: Runtime) -> tuple[int, int, list[Any]]:
    return len(rt.store.operations()), len(rt.store.commitments()), [d.fact_key for d in rt.store.decision_facts()]


def _nothing_happened(rt: Runtime, r: dict, before: tuple[int, int, list[Any]], lang: str) -> None:
    assert r["reply"] == REFUSAL[lang]
    assert ops(r) == [] and r["negotiation"] is None  # nothing executed, nothing went to the buyer
    assert _snapshot(rt) == before  # no operation appended, no commitment proposed, no fact recorded
    assert not [o for o in rt.store.operations() if o.kind in OFFER_KINDS]
    assert rt.store.verify_chain()


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_go_ahead_on_the_counters_sends_nothing_once_the_owner_sent_their_own(client: TestClient, rt: Runtime, lang: str) -> None:
    """negotiate_intent (go-ahead on the proposed send) and run_negotiation / send_counters behind it."""
    oid = _mark_through_the_route(client, EX02)
    c = Chat(client, f"out1-neg-{lang}")
    shown = c.say("Evaluate EX02", lang=lang)  # reading the offer stays open
    assert shown["verdict"]["offer_id"] == oid and shown["awaiting_confirmation"]
    before = _snapshot(rt)
    _nothing_happened(rt, c.say("go ahead", lang=lang), before, lang)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_send_the_counters_is_refused_once_the_owner_sent_their_own(client: TestClient, rt: Runtime, lang: str) -> None:
    """negotiate_intent asked to send: no proposal to send is offered either."""
    _mark_through_the_route(client, EX02)
    c = Chat(client, f"out1-send-{lang}")
    c.say("Evaluate EX02", lang=lang)
    before = _snapshot(rt)
    r = c.say("Send the counters", lang=lang)
    assert r["intent"] == "NEGOTIATE" and not r["awaiting_confirmation"]
    _nothing_happened(rt, r, before, lang)
    after = c.say("go ahead", lang=lang)  # the refusal left nothing waiting for a yes
    assert ops(after) == [] and _snapshot(rt) == before and rt.store.verify_chain()


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_go_ahead_on_an_accept_accepts_nothing_once_the_owner_sent_their_own(client: TestClient, rt: Runtime, lang: str) -> None:
    """execute_decision (the go-ahead on a proposed ACCEPT) and decide / accept behind it."""
    c = Chat(client, f"out1-acc-{lang}")
    shown = c.say(EARLY_ACCEPT, lang=lang)
    assert shown["verdict"]["outcome"] == "ACCEPT" and shown["awaiting_confirmation"]
    _mark_fact(rt, shown["verdict"]["offer_id"], shown["verdict"]["id"])
    before = _snapshot(rt)
    _nothing_happened(rt, c.say("go ahead", lang=lang), before, lang)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_go_ahead_on_a_decline_declines_nothing_once_the_owner_sent_their_own(client: TestClient, rt: Runtime, lang: str) -> None:
    """execute_decision (the go-ahead on a proposed REJECT) and decide / reject behind it."""
    c = Chat(client, f"out1-rej-{lang}")
    shown = c.say("Evaluate EX06", lang=lang)
    assert shown["verdict"]["outcome"] == "REJECT" and [s["kind"] for s in shown["plan"]] == ["VERIFY", "REJECT_OFFER"]
    _mark_fact(rt, shown["verdict"]["offer_id"], shown["verdict"]["id"])
    before = _snapshot(rt)
    _nothing_happened(rt, c.say("go ahead", lang=lang), before, lang)


def test_the_same_send_still_acts_on_an_offer_not_sent_outside(client: TestClient, rt: Runtime) -> None:
    c = Chat(client, "out1-open")
    c.say("Evaluate EX02")
    r = c.say("go ahead")
    assert r["reply"] != REFUSAL["en"] and ("COUNTER_OFFER", "EXECUTED") in ops(r) and r["negotiation"] is not None
    assert rt.store.verify_chain()


def test_the_same_accept_still_acts_on_an_offer_not_sent_outside(client: TestClient, rt: Runtime) -> None:
    c = Chat(client, "out1-open-acc")
    assert c.say(EARLY_ACCEPT)["awaiting_confirmation"]
    r = c.say("go ahead")
    assert r["reply"] != REFUSAL["en"] and ops(r) == [("ACCEPT_OFFER", "EXECUTED")]
    assert rt.store.verify_chain()


def test_the_pipeline_builders_refuse_on_their_own(client: TestClient, rt: Runtime) -> None:
    """The last line: accept, reject, send_counters and run_negotiation each check the rule, whichever handler calls them."""
    from app.nl import pipeline
    from app.nl.context import NlContext
    from app.nl.sessions import Session

    oid = _mark_through_the_route(client, EX02)
    verdict = next(v for v in reversed(rt.store.verdicts()) if v.offer_id == oid)
    ctx = NlContext(store=rt.store, executor=rt.executor, day=rt.day, owner_key_hex=rt.owner_key_hex, owner_authenticated=True,
                    session=Session(id="out1-unit", actor="OWNER", owner_auth=True), lang="zh", trace_id="out1")
    before = _snapshot(rt)
    steps = pipeline.Steps()
    assert pipeline.accept(ctx, steps, verdict, verdict.counters[0]) is None
    assert pipeline.reject(ctx, steps, verdict) is None
    assert pipeline.send_counters(ctx, steps, verdict, verdict.counters, "BUYER-1") == []
    assert pipeline.run_negotiation(ctx, steps, verdict, verdict.counters, "cooperative").outcome == "NOT_STARTED"
    assert [(s.status, s.description) for s in steps.items] == [("SKIPPED", REFUSAL["zh"])] * 4
    assert _snapshot(rt) == before and ctx.results == [] and rt.store.verify_chain()
