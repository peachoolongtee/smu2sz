"""F13: an approval card keeps the economics the owner was shown. The quote is stored when the action is queued or run; a decided
row shows it (and the lot's actual result), and is never priced from today's open alerts or plan."""

from __future__ import annotations

from typing import Any, cast

import pytest

from app.api import operations as operations_module
from app.api.quotes import fen_of
from app.api.runtime import get_runtime
from app.decisions.facts import QuotedFact, parse_fact
from tests.api.test_time_semantics import _act, _queue, _walk


def facts_of(rt):
    return cast(Any, rt.store).decision_facts


def _home_action(client) -> dict:
    return client.get("/home").json()["next_action"]


def _quoted(client, decision_id: str) -> QuotedFact:
    row = next(r for r in facts_of(get_runtime())(decision_id) if r.fact == "QUOTED")
    fact = parse_fact(row)
    assert isinstance(fact, QuotedFact)
    return fact


def test_the_queued_cure_carries_a_quote_equal_to_the_home_next_action(client):
    _walk(client)
    action = _home_action(client)
    acted = _act(client)
    assert acted["decision_recorded"] is True and acted["decision_id"] == f"alert:{action['alert_id']}:v{action['state_version']}"
    row = _queue(client)[0]
    q = row["quote"]
    assert row["decision_id"] == acted["decision_id"] and row["decision_state"] == "AUTHORIZATION_REQUIRED"
    assert q["recorded"] is True
    assert q["total_display"] == action["cost_total_display"] == row["presentation"]["cost_display"]
    assert [x["rate_text"] for x in q["lines"]] == [action["rate_text"]]
    assert q["lines"][0]["cost_days"] == action["cost_days"] and q["lands_day"] == action["lands_day"]
    assert q["rate_basis"] == action["cost_basis"] and q["after"] and q["if_declined"] == row["presentation"]["if_decline"]
    assert row["execution"] == {"status": "PENDING", "summary_text": "Waiting for your approval. Nothing has run."}
    fact = _quoted(client, acted["decision_id"])
    assert fact.total_cost_fen == fen_of(action["cost_total_display"]) and fact.state_version_shown == action["state_version"]
    assert fact.legs[0].annual_rate is not None and fact.legs[0].above_ceiling is True and fact.needs_owner is True


def test_a_decided_row_keeps_the_quoted_cost_and_rate_of_the_home_at_the_same_state_version(client):
    _walk(client)
    action = _home_action(client)
    _act(client)
    row = _queue(client)[0]
    assert client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    decided = _queue(client)[0]
    p = decided["presentation"]
    assert p["cost_display"] == action["cost_total_display"] and p["rate_text"] == action["rate_text"]
    assert decided["quote"]["total_display"] == action["cost_total_display"]
    assert decided["decision_state"] == "SETTLEMENT_PENDING"
    assert decided["execution"]["status"] == "EXECUTED" and "was requested" in decided["execution"]["summary_text"]
    assert decided["quote"]["actual"][0]["arrival_day"] == decided["quote"]["lines"][0]["lands_day"]
    assert decided["quote"]["difference_text"] is None


def test_a_decided_row_is_never_priced_from_todays_alerts_or_plan(client, monkeypatch):
    _walk(client)
    action = _home_action(client)
    _act(client)
    row = _queue(client)[0]
    client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"})
    client.post("/clock/advance", json={"to_day": 40})  # a new alert is open today, with another price and another id

    def forbidden(*args, **kwargs):
        raise AssertionError("a decided row must not read today's alerts or plan")

    monkeypatch.setattr(operations_module, "alerts", forbidden)
    monkeypatch.setattr(operations_module, "runnable_plan", forbidden)
    monkeypatch.setattr(operations_module, "cure_after", forbidden)
    decided = _queue(client)[0]
    assert decided["presentation"]["cost_display"] == action["cost_total_display"]
    assert decided["quote"]["total_display"] == action["cost_total_display"]


@pytest.mark.parametrize("recorded", [True, False])
def test_a_decided_row_beside_a_pending_one_is_unchanged_while_the_alert_is_still_open(client, monkeypatch, recorded):
    """The alert is still open after the first cure, so a read of today's alerts could re-price the decided row. It must not:
    with the quote stored it keeps the quote, without it the row has no price at all (never today's)."""
    _walk(client)
    with monkeypatch.context() as m:
        if not recorded:
            m.setattr(get_runtime().store, "add_decision_fact", lambda record: (_ for _ in ()).throw(RuntimeError("x")))
        _act(client)
    first = _queue(client)[0]
    client.post(f"/approvals/{first['id']}", json={"decision": "APPROVE"})
    decided = _queue(client)[0]
    open_ids = [a["id"] for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD"]
    assert open_ids == ["ALERT-RESERVE-34"], "the first cure's alert is still open"
    # a second approval waits (an agreement), so the queue reads today's alerts again
    rt = get_runtime()
    verdict = rt.store.get_verdict(next(iter(rt.latest_verdict.values())))
    commitment = rt.executor.propose_commitment(verdict.id, expires_day=60, counter_id=verdict.counters[1].id)
    queued = client.post("/operations", headers={"X-Agent-Key": "demo-agent-key"}, json={
        "kind": "RECORD_COMMITMENT", "op_id": "rec-2", "idempotency_key": "rec-2", "mandate_version": verdict.mandate_version,
        "requested_by": "AGENT", "commitment_id": commitment.id, "nonce": commitment.nonce})
    assert queued.json()["result"]["status"] == "PENDING_APPROVAL", queued.text
    rows = _queue(client)
    again = next(r for r in rows if r["id"] == first["id"])
    assert any(r["status"] == "PENDING" for r in rows), "a second approval is waiting and the alerts were read for it"
    keys = ("cost_display", "rate_text", "cost_due_day", "protects", "residual", "if_decline", "lands_day", "headline")
    assert {k: again["presentation"][k] for k in keys} == {k: decided["presentation"][k] for k in keys}
    assert again["quote"] == decided["quote"] and again["decision_id"] == decided["decision_id"]
    if not recorded:
        assert again["presentation"]["cost_display"] is None and again["quote"]["recorded"] is False


def test_a_decided_row_says_when_the_cash_landed_differently_than_quoted(client):
    _walk(client)
    _act(client)
    row = _queue(client)[0]
    client.post("/clock/advance", json={"to_day": 36})  # the owner approves two days after the quote
    assert client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    q = _queue(client)[0]["quote"]
    assert q["lines"][0]["lands_day"] == 37 and q["actual"][0]["arrival_day"] == 39
    assert q["difference_text"] == "Approved later than quoted, so the cash lands in 3 days instead of tomorrow."


def test_without_a_stored_quote_a_decided_row_says_so_and_takes_no_cost_from_todays_alert(client, monkeypatch):
    _walk(client)
    store = get_runtime().store

    def boom(record):
        raise RuntimeError("disk full")

    monkeypatch.setattr(store, "add_decision_fact", boom)
    acted = _act(client)  # the executor still queues the cure; the response says the fact was not recorded
    assert acted["decision_recorded"] is False and acted["pending_approval"] == 1
    row = _queue(client)[0]
    assert row["quote"] == {**row["quote"], "recorded": False, "text": "Price today."} and row["presentation"]["cost_display"]
    client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"})
    decided = _queue(client)[0]
    assert decided["quote"]["recorded"] is False and decided["quote"]["text"] == "The quoted cost was not recorded."
    assert decided["presentation"]["cost_display"] is None and decided["presentation"]["rate_text"] is None
    assert decided["execution"]["status"] == "EXECUTED"


def test_the_act_route_is_still_200_when_the_fact_cannot_be_stored(client, monkeypatch):
    _walk(client)
    monkeypatch.setattr(get_runtime().store, "add_decision_fact", lambda record: (_ for _ in ()).throw(RuntimeError("x")))
    action = _home_action(client)
    r = client.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
    assert r.status_code == 200 and r.json()["decision_recorded"] is False
    assert client.get("/ledger").json()["chain_valid"] is True


def test_a_repeat_of_the_act_changes_nothing_in_the_record(client):
    _walk(client)
    action = _home_action(client)
    body = {"state_version": action["state_version"], "suggestions": action["suggestions"]}
    first = client.post(f"/alerts/{action['alert_id']}/act", json=body).json()
    facts = facts_of(get_runtime())()
    again = client.post(f"/alerts/{action['alert_id']}/act", json=body).json()
    assert again["decision_id"] == first["decision_id"] and again["decision_recorded"] is True
    assert facts_of(get_runtime())() == facts


def test_a_declined_row_keeps_its_quote_and_says_declined(client):
    _walk(client)
    action = _home_action(client)
    _act(client)
    row = _queue(client)[0]
    client.post(f"/approvals/{row['id']}", json={"decision": "REJECT"})
    declined = _queue(client)[0]
    assert declined["decision_state"] == "DECLINED" and declined["execution"]["status"] == "DECLINED"
    assert declined["quote"]["total_display"] == action["cost_total_display"] and "actual" in declined["quote"]
    assert declined["quote"]["actual"] == [] and declined["presentation"]["if_decline"] is None
    d = client.get(f"/decisions/{declined['decision_id']}").json()
    assert d["state"] == "DECLINED" and d["terminal"] is True and d["waiting_for"]["code"] == "NOTHING"


def test_one_bad_row_cannot_fail_the_queue(client, monkeypatch):
    _walk(client)
    _act(client)

    def boom(*args, **kwargs):
        raise ValueError("a row that cannot be presented")

    monkeypatch.setattr(operations_module, "approval_words", boom)
    r = client.get("/approvals/queue")
    assert r.status_code == 200 and len(r.json()["approvals"]) == 1
    assert r.json()["approvals"][0]["status"] == "PENDING"


def test_a_failing_decision_record_does_not_fail_the_queue(client, monkeypatch):
    _walk(client)
    _act(client)

    def boom(rt):
        raise RuntimeError("the record is unreadable")

    monkeypatch.setattr(operations_module, "load_context", boom)
    rows = client.get("/approvals/queue").json()["approvals"]
    assert len(rows) == 1 and rows[0]["decision_id"] is None and rows[0]["quote"] is None
    assert rows[0]["presentation"]["cost_display"]


@pytest.mark.parametrize(("text", "expected"), [("¥1,234.56", 123456), ("¥0.05", 5), ("¥1,000,000.00", 100000000), ("−¥1.50", -150),
                                                 ("-¥2.00", -200), (None, None), ("", None), ("1,234.56", None), ("¥1,234.5", None)])
def test_fen_of_is_the_exact_inverse_of_the_yuan_text(text, expected):
    assert fen_of(text) == expected
