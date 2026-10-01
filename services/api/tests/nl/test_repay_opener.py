"""The opener proposes repaying a drawn credit line the books can afford to repay (tracker row C5)."""

from __future__ import annotations

from app.domain.money import fmt_yuan
from app.nl.sessions import SESSIONS
from tests.alerts.test_repay_alert import deal, line, repay_alerts, to_day34, to_day47
from tests.nl.conftest import AGENT, OWNER, Chat, ops


def _opener(client, session_id="rp-1", lang="en", headers=OWNER):
    return client.post("/nl/opener", json={"session_id": session_id, "lang": lang}, headers=headers)


def test_the_opener_proposes_the_repayment_and_go_ahead_executes_it(client, rt):
    to_day47(client, rt)
    drawn, cash = line(rt).drawn_fen, rt.store.get_state().cash_fen
    [alert] = repay_alerts(client)
    logged = len(rt.store.operations())
    body = _opener(client).json()
    assert body["has_news"] is True and body["awaiting_confirmation"] is True and body["intent"] == "SHOW_ALERTS"
    reply = body["reply"]
    assert f"The {fmt_yuan(drawn)} drawn on {line(rt).name} can be repaid today: cash stays above your floor" in reply
    assert f"(lowest {alert['inputs']['lowest_closing']} on day {alert['inputs']['lowest_day']})" in reply
    assert f"Interest to date {alert['inputs']['interest_due']}." in reply
    assert reply.rstrip().endswith("I can repay it now. Go ahead?")
    assert len(rt.store.operations()) == logged and body["operations"] == []  # the opener executes nothing
    assert [s["kind"] for s in body["plan"]] == ["REPAY_FACILITY"]
    assert SESSIONS.get("rp-1").pending_plan.data == {"alert_id": alert["id"]}

    done = Chat(client, "rp-1").say("go ahead")
    assert ops(done) == [("REPAY_FACILITY", "EXECUTED")]
    assert "repayment alert is now cleared" in done["reply"]
    assert line(rt).drawn_fen == 0 and rt.store.get_state().cash_fen < cash and repay_alerts(client) == []
    assert SESSIONS.get("rp-1").pending_plan is None
    assert "can be repaid" not in _opener(client).json()["reply"]


def test_the_opener_in_chinese(client, rt):
    to_day47(client, rt)
    body = _opener(client, lang="zh").json()
    assert body["awaiting_confirmation"] is True
    assert "今天可以还清" in body["reply"] and "要执行吗？" in body["reply"]
    assert ops(Chat(client, "rp-1").say("go ahead")) == [("REPAY_FACILITY", "EXECUTED")]


def test_a_reserve_breach_is_proposed_as_before_and_no_repayment(client, rt):
    to_day34(client, rt)
    body = _opener(client).json()
    assert "below your" in body["reply"] and "can be repaid" not in body["reply"]
    assert [s["kind"] for s in body["plan"]] == ["SUBMIT_INVOICE_FOR_FINANCING"]


def test_nothing_is_proposed_straight_after_the_deal(client, rt):
    deal(client, rt)
    body = _opener(client).json()
    assert "can be repaid" not in body["reply"] and "repay it" not in body["reply"]
    assert all(s["kind"] != "REPAY_FACILITY" for s in body["plan"])


def test_a_counterparty_asking_for_alerts_gets_nothing_of_this(client, rt):
    to_day47(client, rt)
    chat = Chat(client, "cp-1", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1")
    r = chat.say("any alerts?")
    assert r["operations"] == [] and r["awaiting_confirmation"] is False
    assert "can be repaid" not in r["reply"] and "repay" not in r["reply"].lower()
    assert line(rt).drawn_fen > 0
    assert chat.say("go ahead")["operations"] == []
    assert _opener(client, "cp-2", headers=AGENT).status_code in (401, 403)
