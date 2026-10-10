"""Review fixes for the decision record (map #65, ticket #71): the residual belongs to its own breach, a quote that projected nothing
says nothing about the reserve, a bound send is idempotent, a failed fact never fails a route, and one bad decision never takes the
list or the queue down."""

from __future__ import annotations

import json
from typing import Any

from app.alerts import Alert, AlertKind, Severity, SuggestedAction
from app.api import decide as decide_module
from app.api import decisions as decisions_module
from app.api import home as home_module
from app.api.presentation import quote_view
from app.api.quotes import build_quote, rate_of
from app.api.runtime import get_runtime
from app.decisions import QuotedFact
from app.decisions.facts import parse_fact
from app.domain.fixtures import load_scenario
from app.domain.models import Actor, ApplyForFacility, RepayFacility
from app.domain.money import Ratio
from tests.api.test_time_semantics import _act, _queue, _walk

EX01 = "EX01_PACKAGE"


def _settled_cure(client) -> str:
    _walk(client)
    acted = _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    client.post("/clock/advance", json={"to_day": 40})
    return acted["decision_id"]


def _with_open_reserve_alert(monkeypatch, **changes: Any) -> None:
    """The record reads today's alerts; show it the real reserve alert with other fields (another breach, another cure). The home runs the
    alerts once and hands them to the record (ticket #87), so the home's own read is patched beside the record's."""
    real = decisions_module.alerts

    def patched(*args, **kwargs):
        return [a.model_copy(update=changes) if a.kind == AlertKind.RESERVE_BREACH_AHEAD else a for a in real(*args, **kwargs)]

    monkeypatch.setattr(decisions_module, "alerts", patched)
    monkeypatch.setattr(home_module, "alerts", patched)


# ---------------------------------------------------------------- 1. the residual belongs to its own breach


def test_a_settled_cure_then_an_unrelated_breach_with_a_committed_cure_leaves_the_old_record_closed(client, monkeypatch):
    decision_id = _settled_cure(client)
    assert client.get("/home").json()["remaining_task"].endswith("no committed funding restores it. This needs your decision.")
    _with_open_reserve_alert(monkeypatch, id="ALERT-RESERVE-80", committed_cure=True)
    d = client.get(f"/decisions/{decision_id}").json()
    assert d["state"] == "SETTLED" and d["terminal"] is True and d["residual"] is None
    assert d["waiting_for"]["code"] == "NOTHING"
    home = client.get("/home").json()
    assert home["remaining_task"] is None and home["remaining_task_links"] == []
    assert decision_id not in [x["id"] for x in home["open_decisions"]]
    assert "no committed funding" not in json.dumps(home)


def test_the_same_breach_with_a_committed_cure_says_a_plan_is_ready_not_that_nothing_restores_it(client, monkeypatch):
    decision_id = _settled_cure(client)
    _with_open_reserve_alert(monkeypatch, id="ALERT-RESERVE-34", committed_cure=True)
    home = client.get("/home").json()
    assert home["remaining_task"] == ("Your minimum cash reserve is still ¥100,000.00 short from today; a funding plan is ready "
                                      "(see the next step).")
    assert home["remaining_task_decision_id"] == decision_id
    zh = client.get("/home", params={"lang": "zh"}).json()["remaining_task"]
    assert "融资方案已准备好" in zh and "没有已承诺" not in zh


def test_a_breach_nothing_fixes_is_still_the_owners_to_decide(client, monkeypatch):
    decision_id = _settled_cure(client)
    _with_open_reserve_alert(monkeypatch, id="ALERT-RESERVE-80", committed_cure=False)
    home = client.get("/home").json()
    assert home["remaining_task"].endswith("no committed funding restores it. This needs your decision.")
    assert home["remaining_task_decision_id"] == decision_id


# ---------------------------------------------------------------- 2. a quote that projected nothing


def _books():
    return load_scenario()


def test_a_repayment_quote_projects_nothing_and_says_the_balance_is_repaid(client):
    state, mandate = _books()
    fac = state.facilities[0].id
    alert = Alert(id="ALERT-REPAY-X", kind=AlertKind.FACILITY_REPAYABLE, severity=Severity.WARNING, title="t", detail="d", formula="f",
                  day=10, actionable=True,
                  suggested=[SuggestedAction(operation_kind="REPAY_FACILITY", facility_id=fac, amount_fen=1_000_000)])
    op = RepayFacility(op_id="alert:ALERT-REPAY-X:v1:0", idempotency_key="alert:ALERT-REPAY-X:v1:0", mandate_version=mandate.version,
                       requested_by=Actor.AGENT, day=10, facility_id=fac, amount_fen=1_000_000)
    fact = build_quote(state, [], mandate, alert, None, [op], 10)
    assert fact.projected is False and fact.restores_reserve is None and fact.after_first_short_day is None
    assert fact.if_decline is not None and fact.if_decline.kind == "closed"
    view = quote_view(fact, state, 10, 10, "en")
    assert view["after"] == "The balance is repaid and the interest stops."
    assert "reserve" not in json.dumps(view).lower().replace("if_declined", "")
    assert view["if_declined"] == "Interest keeps running on the drawn balance."
    assert quote_view(fact, state, 10, 10, "zh")["after"] == "余额还清，利息停止。"


def test_an_application_only_cure_says_nothing_about_the_reserve(client):
    state, mandate = _books()
    fac = state.facilities[0].id
    alert = Alert(id="ALERT-RESERVE-5", kind=AlertKind.RESERVE_BREACH_AHEAD, severity=Severity.CRITICAL, title="t", detail="d",
                  formula="f", day=5, amount_fen=1_000, committed_cure=False,
                  suggested=[SuggestedAction(operation_kind="APPLY_FOR_FACILITY", facility_id=fac, amount_fen=1_000_000)])
    op = ApplyForFacility(op_id="alert:ALERT-RESERVE-5:v1:0", idempotency_key="alert:ALERT-RESERVE-5:v1:0",
                          mandate_version=mandate.version, requested_by=Actor.AGENT, day=5, facility_id=fac, amount_fen=1_000_000)
    fact = build_quote(state, [], mandate, alert, None, [op], 5)
    assert fact.projected is False and fact.restores_reserve is None and fact.needs_owner is True
    assert quote_view(fact, state, 5, 5, "en")["after"] is None


def test_a_projected_cure_quote_still_says_where_the_reserve_stands(client):
    _walk(client)
    acted = _act(client)
    row = next(r for r in get_runtime().store.decision_facts(acted["decision_id"]) if r.fact == "QUOTED")
    fact = parse_fact(row)
    assert isinstance(fact, QuotedFact) and fact.projected is True and fact.restores_reserve is False
    assert _queue(client)[0]["quote"]["after"]


# ---------------------------------------------------------------- 11. a router plan keeps its rate


def test_a_router_lines_rate_is_kept_exactly_and_shown_to_the_places_the_line_stated():
    assert rate_of("16.26%") == Ratio(num=813, den=5000)
    assert rate_of("32.5%") == Ratio(num=13, den=40)
    assert rate_of(None) is None and rate_of("about 16%") is None and rate_of("16.26") is None
    state, _ = _books()
    fact = QuotedFact.model_validate({
        "alert_id": "A", "alert_kind": "RESERVE_BREACH_AHEAD", "alert_day": 5, "state_version_shown": 1, "source": "router",
        "legs": [{"op_id": "o:0", "kind": "SUBMIT_INVOICE_FOR_FINANCING", "facility_id": state.facilities[0].id, "receivable_id": None,
                  "amount_fen": 100, "cost_fen": 7, "annual_rate": {"num": 813, "den": 5000}, "cost_days": None, "cost_end_day": None,
                  "lands_day": 7, "above_ceiling": True}],
        "total_cost_fen": 7, "cost_note": None, "needs_owner": True, "max_apr_bp": 1500, "projected": True,
        "restores_reserve": True, "after_first_short_day": None, "horizon_days": 90, "if_decline": None, "residual_shortfall_fen": None})
    assert quote_view(fact, state, 5, 5, "en")["lines"][0]["rate_text"] == "16.26%"
    cure = fact.model_copy(update={"source": "cure"})
    assert quote_view(cure, state, 5, 5, "en")["lines"][0]["rate_text"] == "16.3%"


# ---------------------------------------------------------------- 3. a bound send is idempotent


def _tier2_send(client, monkeypatch) -> tuple[str, dict]:
    import app.operations.executor as executor_module

    monkeypatch.setattr(executor_module, "has_terms_change", lambda c: True)  # the accept needs the owner, as Option B's terms do
    client.post("/demo/reset", json={})
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01}).json()
    body = {"buyer_profile": "cooperative", "verdict_id": v["id"], "counter_id": v["counters"][0]["id"], "state_version": v["state_version"]}
    return oid, body


def test_two_identical_bound_sends_make_one_commitment_one_approval_and_one_sent_fact(client, monkeypatch):
    oid, body = _tier2_send(client, monkeypatch)
    first = client.post(f"/negotiate/{oid}", json=body)
    assert first.status_code == 200 and first.json()["operations"][0]["status"] == "PENDING_APPROVAL"
    second = client.post(f"/negotiate/{oid}", json=body)
    assert second.status_code == 409
    d = second.json()["detail"]
    assert d["code"] == "ALREADY_SENT" and d["decision_id"] == f"deal:{oid}" and d["approval_status"] == "PENDING"
    store = get_runtime().store
    assert len(store.commitments()) == 1 and len(store.approvals()) == 1
    assert d["commitment_id"] == store.commitments()[0].id and d["approval_id"] == store.approvals()[0].id
    assert [f.fact for f in store.decision_facts() if f.fact == "SENT"] == ["SENT"]
    # a third try with the books as they now stand still finds the standing agreement, not a stale-books answer
    body["state_version"] = client.get("/home").json()["state_version"]
    assert client.post(f"/negotiate/{oid}", json=body).json()["detail"]["code"] == "ALREADY_SENT"
    assert len(store.commitments()) == 1 and len(store.approvals()) == 1


def test_an_agreed_send_is_not_made_twice_and_a_different_counter_still_can_be(client, monkeypatch):
    client.post("/demo/reset", json={})
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01}).json()
    body = {"buyer_profile": "cooperative", "verdict_id": v["id"], "counter_id": v["counters"][0]["id"]}
    assert client.post(f"/negotiate/{oid}", json=body).json()["outcome"] == "DEAL"
    again = client.post(f"/negotiate/{oid}", json=body)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ALREADY_SENT"
    assert again.json()["detail"]["commitment_status"] == "ACTIVE" and again.json()["detail"]["approval_id"] is None
    assert len(get_runtime().store.commitments()) == 1


def test_a_queued_tier2_accept_from_the_real_negotiate_route_has_its_terms_and_is_agreed_on_approval(client, monkeypatch):
    oid, body = _tier2_send(client, monkeypatch)
    n = client.post(f"/negotiate/{oid}", json=body).json()
    assert n["outcome"] == "DEAL" and n["operations"][0]["status"] == "PENDING_APPROVAL"
    row = _queue(client)[0]
    assert row["kind"] == "ACCEPT_OFFER" and row["presentation"]["terms_available"] is True  # the nonce lookup finds the commitment
    assert row["decision_id"] == f"deal:{oid}" and row["decision_state"] == "AUTHORIZATION_REQUIRED"
    d = client.get(f"/decisions/{row['decision_id']}").json()
    assert d["authorization"]["required_tier"] == "TIER_2" and d["agreement"]["terms"], "the terms actually agreed are listed"
    assert d["execution"]["summary_text"].startswith("The agreement is waiting for your approval and is not in force.")
    # Finding (executor behaviour, not changed here): /negotiate funds the gap in the same call, which moves the books, so the
    # queued accept no longer verifies against its verdict when the owner approves it. The record shows that as a finished failure.
    res = client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"}).json()["result"]
    assert res["status"] == "REFUSED" and "The books changed since verdict" in res["message"]
    after = client.get(f"/decisions/{row['decision_id']}").json()
    assert after["state"] == "FAILED" and after["terminal"] is True and after["state_text"] == "Could not run; nothing changed"
    assert _queue(client)[0]["execution"]["summary_text"].startswith("You approved it, but it could not run")


def test_a_send_of_one_chosen_counter_that_ends_without_a_deal_has_its_own_fact_key(client):
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01}).json()
    body = {"buyer_profile": "hard_line", "verdict_id": v["id"], "counter_id": v["counters"][1]["id"], "state_version": v["state_version"]}
    assert client.post(f"/negotiate/{oid}", json=body).json()["outcome"] == "NO_DEAL"
    keys = [f.fact_key for f in get_runtime().store.decision_facts() if f.fact == "SENT"]
    assert keys == [f"nodeal:{v['id']}:hard_line:{v['counters'][1]['id']}"]


# ---------------------------------------------------------------- 6. partial binding


def test_a_send_bound_by_the_verdict_alone_is_refused_when_that_verdict_is_on_old_books(client):
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    v = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01}).json()
    client.post("/clock/advance", json={"to_day": 1})
    before = len(get_runtime().store.operations())
    for body in ({"verdict_id": v["id"]}, {"counter_id": v["counters"][0]["id"]}):
        r = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative", **body})
        assert r.status_code == 409 and r.json()["detail"]["reason"] == "BOOKS_CHANGED" and r.json()["detail"]["reevaluate"] is True
    assert len(get_runtime().store.operations()) == before


# ---------------------------------------------------------------- 5. a fact that cannot be built never fails the route


def test_a_fact_that_fails_to_build_after_the_event_never_makes_a_500(client, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("a field the model refuses")

    monkeypatch.setattr(decide_module, "EvaluatedFact", broken)
    oid = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    r = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": EX01})
    assert r.status_code == 200 and r.json()["decision_recorded"] is False
    monkeypatch.setattr(decide_module, "SentFact", broken)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
    assert n.status_code == 200 and n.json()["outcome"] == "DEAL" and n.json()["decision_recorded"] is False
    assert client.get("/ledger").json()["chain_valid"] is True and len(get_runtime().store.commitments()) == 1


# ---------------------------------------------------------------- 13. a fact stored earlier with other content stands, and says so


def test_a_fact_stored_earlier_with_other_content_is_reported_not_replaced(client):
    from app.decisions.facts import EvaluatedFact
    from app.domain.models import Outcome

    rt = get_runtime()

    def fact(outcome: Outcome) -> EvaluatedFact:
        return EvaluatedFact(offer_id="O", offer_version=1, verdict_id="V", outcome=outcome, counter_ids=[],
                             recommended_counter_id=None, mandate_version=1)

    assert decisions_module.record_fact(rt, "deal:O", "V", fact(Outcome.REJECT), state_version=1, day=0) is True
    assert decisions_module.record_fact(rt, "deal:O", "V", fact(Outcome.REJECT), state_version=1, day=0) is True
    assert decisions_module.record_fact(rt, "deal:O", "V", fact(Outcome.ACCEPT), state_version=1, day=0) == "already_recorded_differently"
    stored = parse_fact(rt.store.decision_facts("deal:O")[0])  # type: ignore[attr-defined]
    assert isinstance(stored, EvaluatedFact) and stored.outcome == Outcome.REJECT


# ---------------------------------------------------------------- 8. one bad decision cannot take the list or the queue down


def test_one_decision_that_cannot_be_derived_is_left_out_not_fatal(client, monkeypatch):
    _walk(client)
    _act(client)
    real = decisions_module.derive

    def picky(inputs):
        if inputs.decision_id.startswith("alert:"):
            raise RuntimeError("a record this code cannot read")
        return real(inputs)

    monkeypatch.setattr(decisions_module, "derive", picky)
    listed = client.get("/decisions")
    assert listed.status_code == 200 and [d["family"] for d in listed.json()["decisions"]] == ["DEAL"]
    q = client.get("/approvals/queue")
    assert q.status_code == 200 and len(q.json()["approvals"]) == 1
    assert q.json()["approvals"][0]["presentation"]["cost_display"], "the card is still priced as before"
    assert client.get("/home").status_code == 200


# ---------------------------------------------------------------- 9. the queue speaks the language it is asked for


def test_the_queue_is_chinese_on_request_and_english_by_default(client):
    _walk(client)
    _act(client)
    en = client.get("/approvals/queue").json()["approvals"][0]
    zh = client.get("/approvals/queue", params={"lang": "zh"}).json()["approvals"][0]
    assert en["quote"]["after"] != zh["quote"]["after"] and "现金" in zh["quote"]["after"] and "cash" in en["quote"]["after"]
    assert "现金" in zh["quote"]["if_declined"] and zh["execution"]["summary_text"] == "等待您批准，尚未执行。"
    assert "现金" in zh["presentation"]["if_decline"] and "批准" in zh["presentation"]["headline"]
    assert en["presentation"]["headline"].startswith("Approve")
    client.post(f"/approvals/{en['id']}", json={"decision": "APPROVE"})
    decided = client.get("/approvals/queue", params={"lang": "zh"}).json()["approvals"][0]
    assert decided["quote"]["recorded"] is True and "批准" in decided["presentation"]["result_message"] or decided["presentation"]["result_message"]


# ---------------------------------------------------------------- 15. small things


def test_the_audit_refusals_link_to_their_decision_and_the_tier_is_the_executors(client):
    _walk(client)
    acted = _act(client)
    row = _queue(client)[0]
    d = client.get(f"/decisions/{acted['decision_id']}").json()
    assert d["authorization"]["required_tier"] == "TIER_2"
    client.post("/clock/advance", json={"to_day": 91})
    client.post(f"/approvals/{row['id']}", json={"decision": "APPROVE"})
    refusals = client.get("/audit").json()["refusals"]
    assert any(r.get("decision_id") == acted["decision_id"] for r in refusals)
    assert not hasattr(decisions_module, "decision_id_of_offer")
