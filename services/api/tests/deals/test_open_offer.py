"""The Deals read's open offer: the offer a buyer has waiting for a reply, FLOW's read of it and what in the deal needs the owner."""

from __future__ import annotations

import re

import pytest

CODES = re.compile(r"DOC-|RCV-|RI:|APR-|COM-|FAC-|BUYER-|OFF-|CTR-|VER-|DEC-")
SENTENCES = ("asks_text", "read_text", "headline_short", "headline_note", "action_text", "cost_window_text", "needs_you_text")
BUYER = "BUYER-1"


def _deal(client, lang="en"):
    deals = client.get("/deals", params={"lang": lang}).json()["deals"]
    return next(d for d in deals if d["counterparty_id"] == BUYER)


def _flags(client, lang="en"):
    d = _deal(client, lang)
    return d["open_offer"], d["needs_you"], d["needs_you_text"]


def _walk_to(client, step):
    client.post("/demo/reset", json={})
    if step == "before":
        return None
    offer = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
    if step == "submitted":
        return offer
    client.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    if step == "evaluated":
        return offer
    client.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative" if step == "agreed" else "hard_line"})
    return offer


def test_a_quiet_deal_has_no_open_offer_and_needs_nothing(client):
    _walk_to(client, "before")
    assert _flags(client) == (None, False, None)


def test_a_submitted_offer_is_received_and_waiting_for_the_owner(client):
    offer = _walk_to(client, "submitted")
    o, needs, text = _flags(client)
    assert o["offer_id"] == offer["offer_id"] and o["verdict_id"] is None and o["read_text"] is None
    assert [(x["key"], x["state"]) for x in o["stages"]] == [
        ("received", "now"), ("analysed", "todo"), ("reply_ready", "todo"), ("sent", "todo"), ("agreed", "todo")]
    assert o["asks_text"].startswith("early settlement of ")
    assert needs is True and text == "An offer is waiting for your reply"


def test_an_evaluated_offer_carries_flows_read_of_it(client):
    offer = _walk_to(client, "evaluated")
    o, needs, _ = _flags(client)
    assert o["offer_id"] == offer["offer_id"] and o["verdict_id"].startswith("VER-")
    assert o["read_text"] == "Don't accept as asked: it would cost ¥28,326.92 over 12 months, above your ¥5,000.00 limit."
    assert o["headline_short"] == "Counter instead of accepting as asked"
    assert o["headline_note"] == "As asked costs ¥28,326.92 over 12 months, above your ¥5,000.00 limit. Two replies are ready to send."
    assert o["action_text"] == "Two replies are ready to send." and o["replies_ready"] == 2
    assert (o["cost_display"], o["cost_window_text"], o["limit_display"], o["over_limit"]) == (
        "¥28,326.92", "over 12 months", "¥5,000.00", True)
    assert [(x["key"], x["state"]) for x in o["stages"]] == [
        ("received", "done"), ("analysed", "done"), ("reply_ready", "now"), ("sent", "todo"), ("agreed", "todo")]
    assert o["tone"] == "warn" and needs is True
    # the stage is the decision record's own state
    decision = client.get(f"/decisions/{client.get(f'/offers/{offer['offer_id']}').json()['decision_id']}").json()
    assert decision["state"] == "RESPONSE_READY"


def test_the_chinese_heading_is_split_into_a_short_verdict_and_a_note_of_figures(client):
    _walk_to(client, "evaluated")
    zh = _flags(client, "zh")[0]
    assert zh["headline_short"] == "还价，不按对方要求接受"
    assert zh["headline_note"] == "按对方要求，成本将为¥28,326.92（12 个月内），高于您 ¥5,000.00 的上限。两份回复已可发送。"
    assert "28,326.92" not in zh["headline_short"] and not re.search(r"[A-Za-z]", zh["headline_short"] + zh["headline_note"])


def test_the_short_verdict_and_note_follow_each_outcome():
    from app.api.deal_offers import _headline_note, _headline_short
    from app.decisions.state import DealState

    window = ("over 12 months", "12 个月内")
    ready = DealState.RESPONSE_READY
    assert _headline_short(ready, "accept", "en") == "Accept as asked"
    assert _headline_short(ready, "needs_owner", "en") == "Accept, with your approval"
    assert _headline_short(ready, "decline", "en") == "No deal" and _headline_short(ready, "cannot", "en") == "Not safe to act on"
    assert _headline_short(DealState.NEEDS_CLARIFICATION, "counter", "en") == "Clarify before deciding"
    assert _headline_note("accept", "¥1.00", window, "¥5.00", False, 0, "en") == "As asked costs ¥1.00 over 12 months, within your ¥5.00 limit."
    assert _headline_note("accept", "¥1.00", window, "¥5.00", False, 0, "zh") == "按对方要求，成本将为¥1.00（12 个月内），在您 ¥5.00 的上限内。"
    assert _headline_note("cannot", "¥1.00", window, "¥5.00", False, 0, "en") is None
    assert _headline_note("counter", "¥9.00", window, "¥5.00", True, 1, "en").endswith("One reply is ready to send.")


@pytest.mark.parametrize("step", ["agreed", "no_deal"])
def test_after_the_counter_is_sent_the_offer_is_no_longer_open(client, step):
    _walk_to(client, step)
    assert _flags(client)[0] is None


@pytest.mark.parametrize("step", ["submitted", "evaluated"])
def test_the_chinese_read_has_the_same_figures_and_no_id_in_a_sentence(client, step):
    _walk_to(client, step)
    en, zh = _flags(client, "en")[0], _flags(client, "zh")[0]
    for k in ("offer_id", "verdict_id", "cost_display", "limit_display", "over_limit", "replies_ready", "tone"):
        assert en[k] == zh[k]
    assert [x["state"] for x in en["stages"]] == [x["state"] for x in zh["stages"]]
    for o in (en, zh):
        for k in SENTENCES:
            assert not o.get(k) or not CODES.search(o[k]), (k, o[k])
    assert zh["action_text"] != en["action_text"] and not re.search(r"[A-Za-z]{3,}", (zh["action_text"] + (zh["read_text"] or "")).replace("FLOW", ""))


def test_a_late_invoice_a_document_or_an_approval_needs_the_owner(client):
    from tests.api.test_time_semantics import _walk

    _walk(client, receipt="half")
    d = _deal(client)
    assert d["needs_you"] is True and d["needs_you_text"] == "An invoice is late and needs chasing"
    assert _deal(client, "zh")["needs_you_text"] == "有一张发票已逾期，需要催收"
    client.post("/demo/reset", json={})
    up = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"})
    assert up.status_code == 200
    assert _flags(client)[1:] == (True, "A document is waiting for your review")
