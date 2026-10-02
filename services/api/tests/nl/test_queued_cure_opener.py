"""The opener after a cure above the ceiling was queued: it says the cure waits for the owner's approval, names the
approval, and offers nothing to go ahead with (no pending plan, no second approval)."""

from __future__ import annotations

from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat, ops
from tests.nl.test_alerts_opener import _day34, _opener


def _queue_the_cure(client, rt) -> str:
    """Day 34, the over-the-ceiling cure queued by the owner's go-ahead: the approval id."""
    _day34(client, rt)
    assert _opener(client).json()["awaiting_confirmation"] is True
    done = Chat(client, "op-1").say("go ahead")
    assert ops(done) == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    return done["operations"][0]["approval_id"]


def test_the_opener_says_a_queued_cure_waits_instead_of_offering_it_again(client, rt):
    aid = _queue_the_cure(client, rt)
    logged = len(rt.store.operations())
    body = _opener(client, "op-2").json()
    reply = body["reply"]
    assert body["has_news"] is True and body["awaiting_confirmation"] is False and body["operations"] == []
    assert SESSIONS.get("op-2").pending_plan is None
    assert f"waiting for your approval ({aid})" in reply and f'"approve {aid}"' in reply and "approval card" in reply
    assert "It costs" in reply and "32.5% a year for those 10 days" in reply and "above your 15.00% ceiling" in reply
    assert "if you say go ahead" not in reply and "Go ahead?" not in reply
    # there is no plan to run, so a go-ahead never queues a second approval: the one queue item it can decide is the
    # approval the opener just named (the owner's yes to what they were shown)
    again = Chat(client, "op-2").say("go ahead")
    assert [a.id for a in rt.store.approvals()] == [aid]
    assert not [a for a in rt.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING" and a.id != aid]
    assert len(rt.store.operations()) <= logged + 1 and again["intent"] != "SHOW_ALERTS"


def test_the_opener_says_a_queued_cure_waits_in_chinese(client, rt):
    aid = _queue_the_cure(client, rt)
    body = _opener(client, "op-3", lang="zh").json()
    reply = body["reply"]
    assert body["awaiting_confirmation"] is False and SESSIONS.get("op-3").pending_plan is None
    assert f"等待您批准（{aid}）" in reply and f"批准 {aid}" in reply and "审批卡" in reply
    assert "32.5%" in reply and "15.00%" in reply and "要执行吗" not in reply


def test_once_the_cure_is_approved_the_opener_no_longer_mentions_it(client, rt):
    aid = _queue_the_cure(client, rt)
    r = Chat(client, "owner-ap").say(f"approve {aid}")
    assert ops(r) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    reply = _opener(client, "op-4").json()["reply"]
    assert aid not in reply and "waiting for your approval" not in reply
