"""Ticket #84 (map #65): the decisions that start from a chat "go ahead" or a direct POST /operations keep a stored quote.

A decided card used to say "The quoted cost was not recorded." for them. The plan shown in the earlier chat turn (kept in the session),
or the direct operation's own figures, is now stored as the decision's QUOTED fact by the API layer, after the executor returned."""

from __future__ import annotations

from typing import Any, cast

from app.api.runtime import get_runtime
from app.decisions.facts import QuotedFact, parse_fact
from app.nl import reset_sessions
from tests.nl.conftest import AGENT, OWNER
from tests.nl.test_alerts_opener import _day34


def _walk(client, rt) -> None:
    reset_sessions()
    _day34(client, rt)


def _queue(client) -> list[dict]:
    return client.get("/approvals/queue", headers=OWNER).json()["approvals"]


def approve(client, approval_id: str) -> dict:
    return client.post(f"/approvals/{approval_id}", headers=OWNER, json={"decision": "APPROVE"}).json()


def detail(client, decision_id: str) -> dict:
    return client.get(f"/decisions/{decision_id}", headers=OWNER).json()


def say(client, text: str, sid: str, mode: str | None = None) -> dict:
    r = client.post("/nl", params={"mode": mode} if mode else {}, json={"session_id": sid, "actor": "OWNER", "text": text}, headers=OWNER)
    assert r.status_code == 200, r.text
    return r.json()


def quoted(decision_id: str) -> QuotedFact:
    store = cast(Any, get_runtime().store)
    row = next(r for r in store.decision_facts(decision_id) if r.fact == "QUOTED")
    fact = parse_fact(row)
    assert isinstance(fact, QuotedFact)
    return fact


def facts():
    return cast(Any, get_runtime().store).decision_facts()


def test_the_chat_fund_the_gap_plan_is_stored_as_the_quote_and_a_later_approval_shows_it(client, rt):
    _walk(client, rt)
    plan = say(client, "fund the gap", "q1")
    assert plan["awaiting_confirmation"] is True and "decision_id" not in plan  # proposing records nothing
    before = facts()
    done = say(client, "go ahead", "q1")
    assert [(o["kind"], o["status"]) for o in done["operations"]] == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    did = done["decision_id"]
    assert did.startswith("nl:q1:") and done["decision_recorded"] is True
    assert len(facts()) == len(before) + 1

    fact = quoted(did)
    assert [(leg.amount_fen, leg.cost_fen, leg.lands_day, leg.above_ceiling) for leg in fact.legs] == [
        (8_000_000, 142_575, 37, True), (12_000_000, 106_932, 37, True)]
    assert fact.total_cost_fen == 170_610 and fact.needs_owner is True and fact.alert_id == did
    assert fact.restores_reserve is True and fact.alert_kind == "OPERATION"

    row = _queue(client)[0]
    assert row["decision_id"] == did and row["decision_state"] == "AUTHORIZATION_REQUIRED"
    assert row["quote"]["recorded"] is True and row["quote"]["total_display"] == "¥1,706.10"
    assert [x["rate_text"] for x in row["quote"]["lines"]] == ["16.26%", "32.53%"]
    assert row["quote"]["after"] == "Cash stays above your minimum cash reserve for the next 120 days."

    approved = approve(client, row["id"])
    assert approved["result"]["status"] == "EXECUTED"
    decided = _queue(client)[0]
    assert decided["quote"]["recorded"] is True and decided["quote"]["text"] is None
    assert decided["quote"]["text"] != "The quoted cost was not recorded."
    assert decided["presentation"]["cost_display"] == "¥1,425.75" and decided["presentation"]["rate_text"] == "16.26%"
    assert decided["quote"]["total_display"] == "¥1,706.10"
    record = detail(client, did)
    assert record["recorded"]["quoted"] is True and record["source"] == {"kind": "OPERATION"}
    assert record["quote"]["recorded"] is True


def test_a_repeat_of_the_confirmation_changes_nothing_in_the_record(client, rt):
    _walk(client, rt)
    say(client, "fund the gap", "q2")
    first = say(client, "go ahead", "q2")
    stored = facts()
    again = say(client, "go ahead", "q2")  # nothing is waiting any more: no second quote
    assert "decision_id" not in again and facts() == stored
    assert quoted(first["decision_id"]).total_cost_fen == 170_610


def test_a_chat_alert_cure_is_stored_with_the_alerts_own_figures(client, rt):
    _walk(client, rt)
    proposed = say(client, "what needs me today?", "q3")
    assert proposed["awaiting_confirmation"] is True
    done = say(client, "go ahead", "q3")
    assert [(o["kind"], o["status"]) for o in done["operations"]] == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    did = done["decision_id"]
    assert did.startswith("alert:ALERT-RESERVE-") and done["decision_recorded"] is True
    fact = quoted(did)
    assert fact.alert_kind == "RESERVE_BREACH_AHEAD" and fact.alert_id.startswith("ALERT-RESERVE-")
    assert fact.total_cost_fen == 178_219 and fact.legs[0].cost_days == 10 and fact.legs[0].cost_end_day == 47
    row = _queue(client)[0]
    assert row["decision_id"] == did and row["quote"]["total_display"] == "¥1,782.19"
    approve(client, row["id"])
    decided = _queue(client)[0]
    assert decided["quote"]["recorded"] is True and decided["presentation"]["cost_display"] == "¥1,782.19"
    assert detail(client, did)["source"]["kind"] == "ALERT"


def _direct_op(rt, **over) -> dict:
    return {"kind": "SUBMIT_INVOICE_FOR_FINANCING", "op_id": "direct-1", "idempotency_key": "direct-1",
            "mandate_version": rt.store.get_mandate().version, "requested_by": "AGENT", "facility_id": "FAC-IF",
            "receivable_id": "RI:BUYER-1:2", "advance_fen": 20_000_000, **over}


def test_a_direct_tier_2_operation_is_stored_with_its_own_figures_and_the_approval_shows_them(client, rt):
    _walk(client, rt)
    r = client.post("/operations", headers=AGENT, json=_direct_op(rt))
    body = r.json()
    assert r.status_code == 200 and body["result"]["status"] == "PENDING_APPROVAL"
    aid = body["result"]["approval_id"]
    did = f"approval:{aid}"
    assert body["decision_id"] == did and body["decision_recorded"] is True

    fact = quoted(did)
    [leg] = fact.legs
    assert (leg.kind, leg.facility_id, leg.receivable_id, leg.amount_fen, leg.lands_day, leg.above_ceiling) == (
        "SUBMIT_INVOICE_FOR_FINANCING", "FAC-IF", "RI:BUYER-1:2", 20_000_000, 37, True)
    assert leg.annual_rate is not None and (leg.annual_rate.num, leg.annual_rate.den) == (813, 2500)  # 32.52%: the executor's own cost line
    assert fact.alert_id == did and fact.total_cost_fen is None and fact.needs_owner is True and fact.projected is False

    row = next(x for x in _queue(client) if x["id"] == aid)
    assert row["decision_id"] == did and row["quote"]["recorded"] is True
    assert [x["rate_text"] for x in row["quote"]["lines"]] == ["32.5%"] and row["quote"]["lines"][0]["lands_day"] == 37
    assert approve(client, aid)["result"]["status"] == "EXECUTED"
    decided = next(x for x in _queue(client) if x["id"] == aid)
    assert decided["quote"]["recorded"] is True and decided["quote"]["text"] != "The quoted cost was not recorded."
    assert decided["presentation"]["rate_text"] == "32.5%" and decided["decision_state"] in ("SETTLEMENT_PENDING", "SETTLED")
    assert detail(client, did)["source"] == {"kind": "OPERATION"}


def test_an_operation_that_runs_at_once_or_belongs_to_an_alert_records_no_quote(client, rt):
    _walk(client, rt)
    direct = client.post("/operations", headers=AGENT, json={
        "kind": "REPAY_FACILITY", "op_id": "direct-2", "idempotency_key": "direct-2", "mandate_version": rt.store.get_mandate().version,
        "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 1_000_000}).json()
    assert "decision_id" not in direct  # Tier 1 and run at once: Activity, not a decision
    keyed = client.post("/operations", headers=AGENT, json=_direct_op(rt, op_id="alert:ALERT-RESERVE-42:v1:0",
                                                                      idempotency_key="alert:ALERT-RESERVE-42:v1:0")).json()
    assert keyed["result"]["status"] == "PENDING_APPROVAL" and "decision_id" not in keyed  # the act route owns that decision's quote


def test_a_failing_write_leaves_every_route_200_and_the_decision_unquoted(client, rt, monkeypatch):
    _walk(client, rt)

    def boom(record):
        raise RuntimeError("disk full")

    monkeypatch.setattr(rt.store, "add_decision_fact", boom)
    say(client, "fund the gap", "q4")
    done = say(client, "go ahead", "q4")  # the route answers 200 (say asserts it) and the executor still queued the leg
    assert done["operations"][0]["status"] == "PENDING_APPROVAL" and done["decision_recorded"] is False
    direct = client.post("/operations", headers=AGENT, json=_direct_op(rt))
    assert direct.status_code == 200 and direct.json()["result"]["status"] == "PENDING_APPROVAL"
    assert direct.json()["decision_recorded"] is False
    assert [f for f in facts() if f.fact == "QUOTED"] == []
    rows = _queue(client)
    assert len(rows) == 2 and all(r["quote"]["recorded"] is False and r["quote"]["text"] == "Price today." for r in rows)
    for r in rows:
        approve(client, r["id"])
    assert all(r["quote"]["text"] == "The quoted cost was not recorded." for r in _queue(client))
    assert client.get("/ledger", headers=OWNER).json()["chain_valid"] is True


def test_a_plan_whose_quote_could_not_be_built_still_runs(client, rt, monkeypatch):
    _walk(client, rt)
    from app.nl import quoting

    def boom(*args, **kwargs):
        raise RuntimeError("no quote today")

    monkeypatch.setattr(quoting.quotes, "build_shown_quote", boom)
    plan = say(client, "fund the gap", "q5")
    assert plan["awaiting_confirmation"] is True
    done = say(client, "go ahead", "q5")
    assert done["operations"][0]["status"] == "PENDING_APPROVAL" and "decision_id" not in done
    assert [f for f in facts() if f.fact == "QUOTED"] == []
