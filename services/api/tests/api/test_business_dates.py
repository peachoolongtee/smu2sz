"""Wave 4 (wayfinder #33): the Business pages never read "day N". The server adds a `*_when` twin beside every sentence
that can carry a day number (the ledger's messages, the act results, the counters' text and rationale, the violations and
the plan in the verdict view) and says the rate ceiling in the owner's words; the raw sentences stay for the audit level
and the Demo views."""

from __future__ import annotations

import re

from app.api.presentation import business_text, owner_words, relative_days
from app.api.runtime import get_runtime
from app.domain.money import bp, post

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
DAY_N = re.compile(r"\bday \d", re.IGNORECASE)

QUEUED = ("Queued for owner approval (APR-000001): effective annual cost 32.52% is above the mandate's 15.00% ceiling for what "
          "the agent may borrow alone (all charges on ¥200,000.00 held 10 days (day 37 to day 47), annualised = 32.52%)")


def test_relative_days_covers_the_holding_period_and_the_settlement_promise():
    assert relative_days("held 10 days (day 37 to day 47), annualised", 34, "en") == "held 10 days (from in 3 days to in 13 days), annualised"
    assert relative_days("at 0.85%, paid on or before day 2.", 0, "en") == "at 0.85%, paid within 2 days."
    assert relative_days("paid on or before day 34.", 34, "en") == "paid by today."
    assert relative_days("Clock moved from day 0 to day 32: 0 flow(s)", 34, "en") == "Clock moved from 34 days ago to 2 days ago: 0 flow(s)"
    assert relative_days("draw ¥255,000.00 (arrives day 21)", 0, "en") == "draw ¥255,000.00 (arrives in 21 days)"
    assert relative_days("a shortfall of ¥85,000.00 on day 47, funded by the plan", 0, "en") == "a shortfall of ¥85,000.00 in 47 days, funded by the plan"


def test_owner_words_say_the_ceiling_as_the_signed_limit_and_keep_the_figures():
    out = owner_words(QUEUED)
    assert out == ("Queued for owner approval (APR-000001): the yearly cost of 32.52% is above the 15.00% limit you signed for "
                   "funding without your approval (all charges on ¥200,000.00 held 10 days (day 37 to day 47), annualised = 32.52%)")
    assert owner_words("that is above the 15.00% ceiling for what the agent may borrow alone, so it needs the owner's approval before it runs") == (
        "that is above the 15.00% limit you signed for funding without your approval, so it needs your approval before it runs")
    assert owner_words("effective annual cost 10.84% is within the ceiling") == "effective annual cost 10.84% is within the ceiling"


def test_business_text_is_the_whole_pass_and_keeps_none(client):
    state = get_runtime().store.get_state()
    out = business_text(state, QUEUED, 34, "en")
    assert "limit you signed for funding without your approval" in out and "(from in 3 days to in 13 days)" in out
    assert not DAY_N.search(out) and "32.52%" in out and "¥200,000.00" in out
    assert business_text(state, None, 34, "en") is None


def _eval(client, fx="EX01_PACKAGE"):
    oid = client.post("/offers", json={"fixture_id": fx}).json()["offer"]["offer_id"]
    return oid, client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fx}).json()


def test_the_verdict_view_carries_business_twins_for_counters_violations_and_the_plan(client):
    _, v = _eval(client)
    a = next(c for c in v["counters"] if "on or before day" in c["text"])
    assert a["text_when"] == a["text"].replace("paid on or before day 2", "paid within 2 days")
    assert not DAY_N.search(a["text_when"]) and "on or before day 2" in a["text"]  # the buyer's words are untouched
    b = next(c for c in v["counters"] if "on day 47" in c["rationale"])
    assert "in 47 days" in b["rationale_when"] and not DAY_N.search(b["rationale_when"])
    breach = next(x for x in v["violations"] if x["code"] == "RESERVE_BREACH")
    assert breach["message"].endswith("on day 47") and breach["message_when"].endswith("in 47 days")
    assert breach["cure_note_when"] is not None and "closing_cash(day 47)" in breach["formula"]  # the formula is the audit level
    plan = v["plan"]
    assert "day 32" in plan["not_executable_reason"] and "in 32 days" in plan["not_executable_reason_when"]
    assert not DAY_N.search(plan["not_executable_reason_when"])
    for line in plan["costs"]:
        assert line["label_when"] is not None and not DAY_N.search(line["label_when"])
        if line.get("not_executable_reason"):
            assert not DAY_N.search(line["not_executable_reason_when"])
    for r in plan["rejected"]:
        assert not DAY_N.search(r["note_when"])
    assert "RESERVE_BREACH@47" in v["summary"] and not DAY_N.search(v["summary_when"])
    assert all(not DAY_N.search(n["message_when"]) for n in v["notes"])
    for row in v["comparison"]:
        assert row["note_when"] is None or not DAY_N.search(row["note_when"])
        assert not any(DAY_N.search(c) for c in row["components_when"])
        assert len(row["components_when"]) == len(row["components"])


def test_the_ledger_and_the_act_results_carry_message_when_and_the_queue_the_request_day(client):
    rt = get_runtime()
    oid, _ = _eval(client)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    ob = rt.store.get_commitment(n["commitment"]["id"]).obligations[0]
    agreed = ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
    client.post("/clock/advance", json={"to_day": ob.effective_day})
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "t-receipt-1", "idempotency_key": "t-receipt-1",
        "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
        "receivable_id": ob.base.receivable_id, "amount_fen": agreed}).json()
    assert r["result"]["status"] == "EXECUTED"
    client.post("/clock/advance", json={"to_day": 30})
    client.post("/clock/advance", json={"to_day": 34})
    breach = next(a for a in client.get("/alerts").json()["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")

    [res] = client.post(f"/alerts/{breach['id']}/act").json()["results"]
    assert res["status"] == "PENDING_APPROVAL"
    assert "what the agent may borrow alone" in res["message"] and "(day 37 to day 47)" in res["message"]
    assert "limit you signed for funding without your approval" in res["message_when"]
    assert "(from in 3 days to in 13 days)" in res["message_when"] and not DAY_N.search(res["message_when"])

    [queued] = client.get("/approvals/queue").json()["approvals"]
    assert queued["presentation"]["created_when"] == "today"
    assert "limit you signed for funding without your approval" in queued["presentation"]["reason"]
    assert not DAY_N.search(queued["presentation"]["reason"]) and "what the agent may borrow alone" in queued["reason"]

    ledger = client.get("/ledger").json()
    for op in ledger["operations"]:
        assert op["message_when"] is not None and not DAY_N.search(op["message_when"]), op["message_when"]
    tail = ledger["operations"][-1]
    assert tail["summary"] == res["message"] and tail["message_when"] == res["message_when"]
    assert ledger["chain_valid"] is True  # a presentation field, not a change to the chained entry
