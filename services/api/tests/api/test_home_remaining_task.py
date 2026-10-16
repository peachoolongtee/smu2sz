"""F17: after a partial rescue the home says what is left to decide, in words, with the supported routes as links and no invented
cure. Also the home's open decisions (up to three non-terminal records)."""

from __future__ import annotations

from app.api import home as home_module
from tests.api.test_time_semantics import _act, _queue, _walk


def _settled_zero_floor_cure(client) -> str:
    _walk(client)
    acted = _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    client.post("/clock/advance", json={"to_day": 40})  # the funding has landed (day 37)
    return acted["decision_id"]


def test_the_zero_floor_cure_approved_and_settled_leaves_a_remaining_task_with_links(client):
    decision_id = _settled_zero_floor_cure(client)
    home = client.get("/home").json()
    assert home["remaining_task"] == ("Your minimum cash reserve is still ¥100,000.00 short from today; no committed funding "
                                      "restores it. This needs your decision.")
    assert home["remaining_task_decision_id"] == decision_id
    links = home["remaining_task_links"]
    assert links[0]["href"] == "/cash#cash-options" and links[-1]["href"] == "/limits"
    assert any(x["href"].startswith("/receivables#") for x in links)
    assert all(x["label"] for x in links)
    d = client.get(f"/decisions/{decision_id}").json()
    assert d["state"] == "SETTLED" and d["terminal"] is False and d["residual"]["shortfall_display"] == "¥100,000.00"
    assert d["waiting_for"]["code"] == "OWNER_DECISION" and d["remaining_task"]["text"] == home["remaining_task"]
    assert decision_id in [x["id"] for x in home["open_decisions"]]
    # no invented cure: nothing in the links applies for a facility or asks the agent to run anything
    assert not any("apply" in x["label"].lower() for x in links)


def test_the_remaining_task_is_chinese_on_a_chinese_home(client):
    _settled_zero_floor_cure(client)
    home = client.get("/home", params={"lang": "zh"}).json()
    assert "这需要您决定" in home["remaining_task"] and "¥100,000.00" in home["remaining_task"]
    assert home["remaining_task_links"][0]["label"] == "比较您的融资方案"


def test_while_the_cash_is_on_its_way_the_home_waits_for_the_lender_not_the_owner(client):
    _walk(client)
    acted = _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    home = client.get("/home").json()
    assert home["remaining_task"] is None and home["remaining_task_links"] == []
    row = next(x for x in home["open_decisions"] if x["id"] == acted["decision_id"])
    assert row["state"] == "SETTLEMENT_PENDING" and row["waiting_for"]["code"] == "FUNDING_SETTLEMENT"
    assert row["waiting_for"]["party"] == "lender" and row["residual"]["shortfall_display"] == "¥257,790.00"


def test_healthy_books_have_no_remaining_task_and_no_open_decisions(client):
    home = client.get("/home").json()
    assert home["remaining_task"] is None and home["remaining_task_links"] == [] and home["open_decisions"] == []
    assert home["remaining_task_decision_id"] is None


def test_the_home_lists_at_most_three_open_decisions_newest_first(client):
    for n in range(5):
        oid = client.post("/offers", json={"documents": [{"doc_id": f"t{n}", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0,
                                                           "text": f"Deduct 0.{n + 1}% and we'll settle the open ¥420,000 invoice early."}],
                                           "counterparty_id": "BUYER-1"}).json()["offer"]["offer_id"]
        client.post(f"/offers/{oid}/evaluate", json={})
    rows = client.get("/home").json()["open_decisions"]
    assert len(rows) == 3 and all(r["terminal"] is False for r in rows)


def test_a_failure_in_the_record_never_takes_the_home_down(client, monkeypatch):
    _walk(client)
    _act(client)

    def boom(rt):
        raise RuntimeError("unreadable")

    monkeypatch.setattr(home_module, "load_context", boom)
    r = client.get("/home")
    assert r.status_code == 200
    body = r.json()
    assert body["open_decisions"] == [] and body["remaining_task"] is None and body["next_action"] is not None
