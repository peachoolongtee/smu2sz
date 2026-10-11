"""Wave 3 (wayfinder #65, ticket #72, F26, F27, audit section 11): Activity says what changed, why it matters and what remains.
`why_it_matters` of an executed event is the forecast as of now, read once per request and labelled "now" (never a per-event replay);
an approval request reads its cost and landing, a refusal says no money moved; `what_remains` is the decision record's."""

from __future__ import annotations

from tests.alerts.test_repay_alert import OWNER, approve_cure, to_day34
from tests.api.test_ledger_events import BANK
from tests.nl import conftest as nl_conftest

rt = nl_conftest.rt
client = nl_conftest.client


def _ledger(client, lang: str = "en") -> dict:
    return client.get("/ledger", params={"lang": lang}, headers=OWNER).json()


def _refuse(client) -> None:
    mv = client.get("/mandate", headers=OWNER).json()["mandate"]["version"]
    res = client.post("/operations", headers=BANK, json={
        "kind": "DRAW_FACILITY", "op_id": "t-big", "idempotency_key": "t-big", "mandate_version": mv,
        "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 99_000_000_000, "day": 0}).json()["result"]
    assert res["status"] == "REFUSED"


def test_an_executed_event_says_the_forecast_now_matching_the_homes_first_breach(client, rt):
    to_day34(client, rt)
    home = client.get("/home", headers=OWNER).json()
    cash = home["cash"]
    gap = f"¥{(cash['floor_fen'] - cash['first_breach_cash_fen']) / 100:,.2f}"
    want = f"Cash forecast is now {gap} below your minimum {cash['first_breach_when']}."
    receipt = next(o for o in _ledger(client)["operations"] if o["kind"] == "RECEIVE_PAYMENT")
    assert receipt["what_changed"] == receipt["event_text"] == "Received ¥255,013.80 from Foshan Home Retail Co."
    assert receipt["why_it_matters"] == want and receipt["why_it_matters_as_of"] == "now"
    clock = next(o for o in _ledger(client)["operations"] if o["kind"] == "ADVANCE_CLOCK")
    assert clock["why_it_matters"] == want
    # the home's recent changes say the same, from the same single reading
    late = next(c for c in home["changes"] if c["kind"] == "LATE")
    assert late["what_changed"] == late["event_text"] and late["why_it_matters"] == want


def test_when_the_forecast_stays_above_the_minimum_the_sentence_says_so(client, rt):
    a = client.get("/home", headers=OWNER).json()["next_action"]
    client.post(f"/alerts/{a['alert_id']}/act", headers=OWNER, json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    ops = _ledger(client)["operations"]
    assert ops and all(o["why_it_matters"] == "The forecast stays at or above your minimum." for o in ops if o["status"] == "EXECUTED")


def test_the_forecast_sentence_is_in_chinese_and_the_ledger_reads_the_forecast_once(client, rt, monkeypatch):
    to_day34(client, rt)
    from app.api import read

    calls: list[int] = []
    real = read.project
    monkeypatch.setattr(read, "project", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    rows = _ledger(client, "zh")["operations"]
    assert len(rows) > 3 and len(calls) == 1  # one reading for every row, never one per event
    assert all(r["why_it_matters"].startswith("截至现在，现金预测显示") for r in rows if r["status"] == "EXECUTED")


def test_a_refusal_says_no_money_moved(client, rt):
    _refuse(client)
    refused = next(o for o in _ledger(client)["operations"] if o["op_id"] == "t-big")
    assert refused["why_it_matters"] == "No money moved." and refused["why_it_matters_as_of"] is None
    assert _ledger(client, "zh")["operations"][-1]["why_it_matters"] == "资金未动。"


def test_an_approval_request_reads_cost_and_landing_and_a_decided_one_is_a_past_request_with_its_current_state(client, rt):
    to_day34(client, rt)
    alert = next(a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")
    r = client.post(f"/alerts/{alert['id']}/act", headers=OWNER)
    [res] = r.json()["results"]
    waiting = next(o for o in _ledger(client)["operations"] if o["status"] == "PENDING_APPROVAL")
    assert waiting["approval_label"] == "Approval requested" and waiting["event_text"].startswith("Waiting for your approval: ")
    assert waiting["why_it_matters"].startswith("Quoted cost ¥") and "the cash would land" in waiting["why_it_matters"]
    assert waiting["current_decision_state"] == "Waiting for your approval"
    assert waiting["decision_link"]["href"] == f"/decisions/{waiting['decision_id']}"
    assert waiting["what_remains"] and waiting["what_remains"].startswith("Waiting for your approval")
    client.post(f"/approvals/{res['approval_id']}", headers=OWNER, json={"decision": "APPROVE"})
    past = next(o for o in _ledger(client)["operations"] if o["status"] == "PENDING_APPROVAL")
    assert past["event_text"].startswith("Approval requested: ") and past["approval_label"] == "Approval requested"
    assert past["current_decision_state"] != "Waiting for your approval"  # it has been answered since
    assert past["decision_link"]["decision_id"] == waiting["decision_id"]


def test_what_remains_comes_from_the_decision_record_and_is_null_when_nothing_waits(client, rt):
    to_day34(client, rt)
    alert = next(a for a in client.get("/alerts", headers=OWNER).json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")
    approve_cure(client, rt, alert["id"])
    rows = _ledger(client)["operations"]
    record = {d["id"]: d for d in client.get("/decisions", headers=OWNER).json()["decisions"]}
    assert any(row["decision_id"] in record for row in rows)  # the check below is not vacuous
    for row in rows:
        if row["decision_id"] in record:
            summary = record[row["decision_id"]]
            assert row["current_decision_state"] == summary["state_text"]
            waits = summary["waiting_for"]["code"] != "NOTHING"
            assert (row["what_remains"] is not None) == waits, row["decision_id"]
        else:
            assert row["what_remains"] is None and row["current_decision_state"] is None
    # an entry that belongs to no decision (a clock move) has nothing remaining
    assert next(o for o in rows if o["kind"] == "ADVANCE_CLOCK")["what_remains"] is None


def test_the_record_chain_badge_says_exactly_what_it_checks(client, rt):
    empty = _ledger(client)
    assert empty["chain_text"] is None  # nothing in the log to check
    _refuse(client)
    ok = _ledger(client)
    assert ok["chain_text"] == "Record chain checks passed" and ok["chain_valid"] is True
    assert ok["chain_scope_text"] == ("Every entry's hash matches the entry before it. This checks the log's own integrity; it does "
                                      "not confirm bank facts or buyer promises.")
    zh = _ledger(client, "zh")
    assert zh["chain_text"] == "记录链检查通过" and "银行事实" in zh["chain_scope_text"]


def test_a_failed_chain_reads_failed(client, rt, monkeypatch):
    _refuse(client)
    monkeypatch.setattr(rt.store, "verify_chain", lambda: False)
    bad = _ledger(client)
    assert bad["chain_valid"] is False and bad["chain_text"] == "Record chain checks failed"
    assert _ledger(client, "zh")["chain_text"] == "记录链检查未通过"


def test_the_refused_section_has_a_stable_anchor_and_the_set_aside_count_is_the_recorded_refusals(client, rt):
    none = _ledger(client)["refusals"]
    assert none["anchor_id"] == "activity-refused" and none["href"] == "/activity#activity-refused"
    assert none["count"] == 0 and none["set_aside_text"] is None and none["is_fixture_example"] is False
    assert none["example"]["is_fixture_example"] is True  # an example is labelled as one
    _refuse(client)
    one = _ledger(client)["refusals"]
    assert (one["count"], one["refused_operations"], one["security_events"]) == (1, 1, 0)
    assert one["set_aside_text"] == "One message was set aside." and one["example"] is None and one["is_fixture_example"] is False
    # a message from an unknown sender is set aside when it is checked: its security events are recorded refusal events
    oid = client.post("/offers", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}, headers=OWNER).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}, headers=OWNER)
    audit = client.get("/audit", headers=OWNER).json()
    events = len(audit["events"])
    assert events > 0
    after = _ledger(client)["refusals"]
    assert after["security_events"] == events and after["count"] == 1 + events
    assert audit["refusal_summary"] == after  # the audit and the ledger count the same refusals
    assert _ledger(client, "zh")["refusals"]["set_aside_text"] == f"已搁置 {1 + events} 条消息。"
