"""Audit finding A10 (S-05): "go ahead" authorises the operations that were shown, not a goal that is planned again.

A pending plan stores the exact typed operations, the quoted cost and the books (state version, mandate version, day)
it was built on. Every test asserts the stored economic state: cash, each facility's drawn balance, the executed
operations in the log and the approval queue, not only the reply.
"""

from __future__ import annotations

import json

import pytest

from app.domain.models import ApplyForFacility, DrawFacility, SubmitInvoiceForFinancing
from app.nl.plans import signature
from app.nl.sessions import SESSIONS
from tests.nl.conftest import OWNER, Chat, ops
from tests.nl.test_alerts_opener import _day34, _opener

LINE_DRAW = ("DRAW_FACILITY", "FAC-LINE", None, 15_000_000)
# the day-0 plan's advance: the ¥405,000 gap (it includes the existing loan's ¥45,000 day-30 payment) less the line
ADVANCE_PLAN = ("SUBMIT_INVOICE_FOR_FINANCING", "FAC-IF", "RCV-A", 25_500_000)
# after the books lose ¥100,000 the gap is ¥505,000: the line, an advance of 266,080 on RCV-A and an early payment of
# 90,000 face on RI:BUYER-1:2 at 1.2% (1,080.00, netting 88,920) that is shown but is not an operation of this plan
ADVANCE_MOVED = ("SUBMIT_INVOICE_FOR_FINANCING", "FAC-IF", "RCV-A", 26_608_000)
GOAL = "Find me the cheapest way to fund the cash gap"


def books(rt) -> dict:
    s = rt.store.get_state()
    return {
        "cash_fen": s.cash_fen, "state_version": s.state_version,
        "drawn": {f.id: f.drawn_fen for f in s.facilities},
        "executed": [(o.kind, json.loads(o.payload_json).get("amount_fen") or json.loads(o.payload_json).get("advance_fen"))
                     for o in rt.store.operations() if json.loads(o.result_json)["status"] == "EXECUTED"],
        "approvals": [(a.id, str(getattr(a.status, "value", a.status))) for a in rt.store.approvals()],
    }


def move_books(rt, cash_fen: int) -> None:
    """The books change after the proposal: cash moves and the state version goes up by one."""
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"cash_fen": s.cash_fen + cash_fen, "state_version": s.state_version + 1}))


def pending(session_id: str):
    plan = SESSIONS.get(session_id).pending_plan
    assert plan is not None, "no plan is pending"
    return plan


# ---------------------------------------------------------------- S-05 and the stored plan


def test_a_proposal_stores_the_operations_the_cost_and_the_books(client, rt):
    c = Chat(client, "pb-store")
    r = c.say(GOAL)
    assert r["awaiting_confirmation"] and ops(r) == [] and "¥3,113.93" in r["reply"]
    plan = pending("pb-store")
    assert signature(plan.ops) == [LINE_DRAW, ADVANCE_PLAN]
    assert plan.quoted_cost_fen == 311_393
    s, m = rt.store.get_state(), rt.store.get_mandate()
    assert (plan.state_version, plan.mandate_version, plan.day) == (s.state_version, m.version, rt.day)
    assert all(isinstance(o, DrawFacility | SubmitInvoiceForFinancing) and o.day == rt.day for o in plan.ops)


def test_s05_go_ahead_after_the_books_moved_runs_nothing_and_shows_the_new_plan(client, rt):
    c = Chat(client, "s05")
    c.say(GOAL)
    move_books(rt, -10_000_000)  # cash down by ¥100,000, state_version + 1
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before  # no operation, no change of cash, no drawn balance moved
    # 841.64 + 266,080 × 7.8% × 30/365 = 1,705.83 + fee 665.20 (2,371.03) + 1,080.00 = 4,292.67
    assert r["awaiting_confirmation"] and "I did not run it" in r["reply"] and "¥4,292.67" in r["reply"]
    assert "Raised" not in r["reply"] and "funded" not in r["reply"].lower()
    new = pending("s05")
    assert signature(new.ops) == [LINE_DRAW, ADVANCE_MOVED] and new.quoted_cost_fen == 429_267
    # the new plan needs its own go-ahead, and then runs exactly its own operations
    r = c.say("go ahead")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    after = books(rt)
    assert after["executed"] == [("DRAW_FACILITY", 15_000_000), ("SUBMIT_INVOICE_FOR_FINANCING", 26_608_000)]
    assert after["drawn"]["FAC-LINE"] == 15_000_000 and after["drawn"]["FAC-IF"] == 26_608_000
    assert SESSIONS.get("s05").pending_plan is None


def test_the_same_operations_still_feasible_at_no_higher_cost_run_as_shown(client, rt):
    c = Chat(client, "pb-same")
    shown = c.say(GOAL)
    stored = signature(pending("pb-same").ops)
    move_books(rt, +100)  # cash up by ¥1, state_version + 1: the stored operations are still feasible, same cost
    cash = rt.store.get_state().cash_fen
    r = c.say("go ahead")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    after = books(rt)
    assert after["executed"] == [("DRAW_FACILITY", 15_000_000), ("SUBMIT_INVOICE_FOR_FINANCING", 25_500_000)]
    assert stored == [LINE_DRAW, ADVANCE_PLAN] and after["drawn"]["FAC-LINE"] == 15_000_000
    assert after["drawn"]["FAC-IF"] == 25_500_000 and after["cash_fen"] > cash
    assert "Cost as quoted: ¥3,113.93" in r["reply"] and shown["awaiting_confirmation"]


def test_an_unchanged_state_sends_the_stored_operations_untouched(client, rt):
    c = Chat(client, "pb-plain")
    c.say(GOAL)
    stored = [(o.op_id, o.idempotency_key) for o in pending("pb-plain").ops]
    r = c.say("go ahead")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert [(o.op_id, o.idempotency_key) for o in rt.store.operations()] == stored


def test_a_new_day_voids_the_plan(client, rt):
    c = Chat(client, "pb-day")
    c.say(GOAL)
    assert client.post("/clock/advance", json={"to_day": 1}, headers=OWNER).status_code == 200
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before
    assert "I did not run it" in r["reply"] and "it is day 1" in r["reply"] and r["awaiting_confirmation"]
    assert pending("pb-day").day == 1  # the fresh proposal is built on the new day and waits for its own go-ahead


def test_a_changed_mandate_voids_the_plan(client, rt):
    c = Chat(client, "pb-mandate")
    c.say(GOAL)
    m = rt.store.get_mandate()
    rt.store.put_mandate(m.model_copy(update={"version": m.version + 1}))
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before
    assert "your mandate changed after I proposed it" in r["reply"] and "I did not run it" in r["reply"]
    # the re-signed-by-nobody mandate admits no plan, so there is nothing to confirm: the old plan is gone, not pending
    assert SESSIONS.get("pb-mandate").pending_plan is None or pending("pb-mandate").mandate_version == m.version + 1


def test_a_cheaper_world_does_not_let_a_dearer_plan_through(client, rt):
    # the stored operations must cost no more than the quote: raise the stored cost ceiling's counterpart by moving
    # the books so that the same legs would cost more (the interest on a larger need is not the same legs, so use the
    # quote itself: halve it and the unchanged operations are dearer than quoted)
    c = Chat(client, "pb-dear")
    c.say(GOAL)
    plan = pending("pb-dear")
    plan.quoted_cost_fen = plan.quoted_cost_fen // 2
    move_books(rt, +100)
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before
    assert "more than the ¥1,556.96 I quoted" in r["reply"]  # half of ¥3,113.93, rounded down to the fen


# ---------------------------------------------------------------- the alert cure


def test_the_alert_cure_runs_as_shown_when_nothing_moved(client, rt):
    _day34(client, rt)
    _opener(client, "ac-ok")
    plan = pending("ac-ok")
    shown = signature(plan.ops)
    assert shown
    r = Chat(client, "ac-ok").say("go ahead")
    done = [k for k, _ in ops(r)]
    assert done and [o["kind"] for o in r["operations"]] == [k for k, *_ in shown][:len(done)]


def test_the_alert_cure_is_not_rederived_when_the_cure_would_be_larger(client, rt):
    _day34(client, rt)
    _opener(client, "ac-big")
    shown = signature(pending("ac-big").ops)
    move_books(rt, -100)  # ¥1 less cash: the cure would now be larger (a line draw on top of the financing)
    before = books(rt)
    logged = len(rt.store.operations())
    r = Chat(client, "ac-big").say("go ahead")
    assert ops(r) == [] and books(rt) == before and len(rt.store.operations()) == logged
    assert "I did not run it" in r["reply"]
    assert r["awaiting_confirmation"]
    new = signature(pending("ac-big").ops)
    assert new != shown and len(new) > len(shown)  # a new proposal, which needs its own go-ahead
    r = Chat(client, "ac-big").say("go ahead")
    logged_ops = [json.loads(e.payload_json) for e in rt.store.operations()[logged:]]
    assert [(o["kind"], o.get("facility_id")) for o in logged_ops] == [(k, f) for k, f, *_ in new][:len(logged_ops)]
    assert [o.get("amount_fen") or o.get("advance_fen") for o in logged_ops] == [a for *_, a in new][:len(logged_ops)]
    assert logged_ops


def test_a_new_day_voids_the_alert_cure(client, rt):
    _day34(client, rt)
    _opener(client, "ac-day")
    client.post("/clock/advance", json={"to_day": 35}, headers=OWNER)
    before = books(rt)
    r = Chat(client, "ac-day").say("go ahead")
    assert ops(r) == [] and books(rt) == before and "it is day 35" in r["reply"]


# ---------------------------------------------------------------- legs the executor does not execute


def _tamper(plan, index: int, advance_fen: int) -> None:
    op = plan.ops[index]
    plan.ops[index] = op.model_copy(update={"advance_fen": advance_fen})


def test_a_refused_second_leg_is_reported_and_nothing_says_funded(client, rt):
    c = Chat(client, "pb-refuse")
    c.say(GOAL)
    _tamper(pending("pb-refuse"), 1, 99_900_000)  # an advance far above the invoice: the executor refuses it
    r = c.say("go ahead")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "REFUSED")]
    after = books(rt)
    assert after["drawn"]["FAC-LINE"] == 15_000_000 and after["drawn"]["FAC-IF"] == 0
    reply = r["reply"].lower()
    assert "done" in reply and "refused" in reply and "funded" not in reply and "raised" not in reply
    assert [s["status"] for s in r["plan"]] == ["EXECUTED", "REFUSED"]


def test_a_refused_first_leg_stops_the_run_and_the_reply_names_what_was_not_sent(client, rt):
    c = Chat(client, "pb-first")
    c.say(GOAL)
    plan = pending("pb-first")
    plan.ops[:] = [plan.ops[1].model_copy(update={"advance_fen": 99_900_000}), plan.ops[0]]
    r = c.say("go ahead")
    assert ops(r) == [("SUBMIT_INVOICE_FOR_FINANCING", "REFUSED")]
    after = books(rt)
    assert after["drawn"] == {f: 0 for f in after["drawn"]} and after["executed"] == []
    assert "Not sent: Draw ¥150,000.00 on FAC-LINE" in r["reply"] and "stopped after step 1 of 2" in r["reply"]
    assert [s["status"] for s in r["plan"]] == ["REFUSED", "SKIPPED"]


# ---------------------------------------------------------------- repay and the borrower file


def test_a_repayment_is_sent_as_shown_and_not_when_the_books_moved(client, rt):
    c = Chat(client, "pb-repay")
    move_books(rt, 100_000_000)  # ¥1,000,000 more cash: repaying is affordable when it is proposed
    assert c.say("draw ¥100,000 on the credit line")["operations"][0]["status"] == "EXECUTED"
    r = c.say("Is it OK to repay ¥50,000 on the credit line?")
    assert r["awaiting_confirmation"] and ops(r) == []
    assert signature(pending("pb-repay").ops) == [("REPAY_FACILITY", "FAC-LINE", None, 5_000_000)]
    move_books(rt, -95_000_000)  # cash down, so that repaying would now break the reserve
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before and "I did not run it" in r["reply"]


def test_a_repayment_runs_exactly_the_stored_amount(client, rt):
    c = Chat(client, "pb-repay2")
    move_books(rt, 100_000_000)
    c.say("draw ¥100,000 on the credit line")
    c.say("Is it OK to repay ¥50,000 on the credit line?")
    drawn = rt.store.get_state().facilities
    r = c.say("go ahead")
    assert ops(r) == [("REPAY_FACILITY", "EXECUTED")]
    line = next(f for f in rt.store.get_state().facilities if f.id == "FAC-LINE")
    assert line.drawn_fen == next(f for f in drawn if f.id == "FAC-LINE").drawn_fen - 5_000_000


# ---------------------------------------------------------------- negotiation from free text


NEGOTIATE = "Negotiate EX01 with the buyer"


def test_negotiating_from_free_text_proposes_and_sends_nothing(client, rt):
    c = Chat(client, "ng-1")
    r = c.say(NEGOTIATE)
    assert r["intent"] == "NEGOTIATE" and r["awaiting_confirmation"] and ops(r) == []
    assert "I would send 2 counter(s)" in r["reply"] and "Nothing has been sent" in r["reply"]
    assert rt.store.commitments() == [] and books(rt)["executed"] == []
    assert pending("ng-1").data["verdict_id"]


def test_a_confirmation_sends_the_counters(client, rt):
    c = Chat(client, "ng-2")
    c.say(NEGOTIATE)
    r = c.say("go ahead")
    assert r["negotiation"]["outcome"] == "ACCEPT"
    assert ops(r)[:2] == [("COUNTER_OFFER", "EXECUTED"), ("COUNTER_OFFER", "EXECUTED")]
    assert len(rt.store.commitments()) == 1 and SESSIONS.get("ng-2").pending_plan is None


@pytest.mark.parametrize("text", [
    "Do not negotiate with Foshan", "Do not negotiate EX01", "Don't send the counters", "please don't negotiate this one",
    "stop negotiating", "no need to send counters", "never send a counter-offer", "不要谈判", "不要发送反报价",
    "别跟佛山谈判", "不要发送",
])
def test_a_negation_sends_nothing_and_clears_the_pending_plan(client, rt, text):
    c = Chat(client, "ng-neg")
    c.say(NEGOTIATE)
    assert SESSIONS.get("ng-neg").pending_plan is not None
    before = books(rt)
    r = c.say(text)
    assert ops(r) == [] and books(rt) == before and rt.store.commitments() == []
    assert not r["awaiting_confirmation"] and SESSIONS.get("ng-neg").pending_plan is None


@pytest.mark.parametrize("text", [
    "Do not negotiate with Foshan", "Don't send the counters", "不要谈判", "不要发送反报价", "不要和佛山谈判",
])
def test_a_negation_with_nothing_pending_does_nothing(client, rt, text):
    c = Chat(client, "ng-neg0")
    before = books(rt)
    r = c.say(text)
    assert ops(r) == [] and books(rt) == before and not r["awaiting_confirmation"]
    assert SESSIONS.get("ng-neg0").pending_plan is None
    assert "not done anything" in r["reply"] or "没有执行" in r["reply"]


@pytest.mark.parametrize("text", [
    "Negotiate EX01 but don't give anything away", "Negotiate EX01 without conceding the rebate",
    "Negotiate EX01 and don't concede anything", "Negotiate EX01, no concessions",
])
def test_a_constraint_is_not_a_negation_and_shapes_the_proposal(client, rt, text):
    c = Chat(client, "ng-con")
    r = c.say(text)
    assert r["intent"] == "NEGOTIATE" and r["awaiting_confirmation"] and ops(r) == []
    assert "I would send 1 counter(s)" in r["reply"] and "Option A" in r["reply"] and "Option B" not in r["reply"]
    assert [x["label"] for x in r["verdict"]["counters"]] == ["Option A"]
    assert all(cv["forward_value_fen"] == 0 for cv in r["verdict"]["counters"])
    # and the confirmation sends the constrained counter only
    r = c.say("go ahead")
    assert [k for k, _ in ops(r)].count("COUNTER_OFFER") == 1


def test_a_negotiation_is_not_sent_when_the_books_moved_and_the_counters_changed(client, rt):
    c = Chat(client, "ng-moved")
    c.say(NEGOTIATE)
    move_books(rt, +100_000_000)  # cash up by ¥1,000,000: the offer no longer draws the same counters
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before and rt.store.commitments() == []
    assert "I did not run it" in r["reply"] and "I would send" in r["reply"] and r["awaiting_confirmation"]


def test_a_negotiation_whose_counters_and_follow_up_are_unchanged_is_sent_as_shown(client, rt):
    c = Chat(client, "ng-same")
    c.say(NEGOTIATE)
    move_books(rt, 0)  # the state version moved, but the same counters and the same follow-up funding come out
    r = c.say("go ahead")
    assert ops(r)[:2] == [("COUNTER_OFFER", "EXECUTED"), ("COUNTER_OFFER", "EXECUTED")]
    assert "I did not run it" not in r["reply"] and len(rt.store.commitments()) == 1


def test_a_new_day_voids_a_pending_negotiation(client, rt):
    c = Chat(client, "ng-day")
    c.say(NEGOTIATE)
    client.post("/clock/advance", json={"to_day": 1}, headers=OWNER)
    r = c.say("go ahead")
    assert ops(r) == [] and rt.store.commitments() == [] and "it is day 1" in r["reply"]


# ---------------------------------------------------------------- early payment


ACCEL = "Get paid early on the Foshan invoice without giving anything away next quarter."


@pytest.mark.parametrize("text", [
    "do not get paid early on the Foshan invoice", "Don't ask Foshan to pay early", "never get the Foshan invoice paid early",
    "不要让佛山提前付款", "别提前收款", "不用提前收佛山的款",
])
def test_an_early_pay_negation_does_nothing_and_proposes_nothing(client, rt, text):
    c = Chat(client, "ac-neg")
    before = books(rt)
    r = c.say(text)
    assert ops(r) == [] and books(rt) == before and rt.store.commitments() == []
    assert not r["awaiting_confirmation"] and SESSIONS.get("ac-neg").pending_plan is None


def test_an_early_pay_negation_clears_a_pending_early_pay_plan(client, rt):
    c = Chat(client, "ac-neg2")
    assert c.say(ACCEL)["awaiting_confirmation"]
    r = c.say("do not get paid early on the Foshan invoice")
    assert ops(r) == [] and not r["awaiting_confirmation"] and SESSIONS.get("ac-neg2").pending_plan is None
    assert c.say(ACCEL)["awaiting_confirmation"]
    r = c.say("不要让佛山提前付款")  # a decline that names the buyer still clears the plan
    assert ops(r) == [] and not r["awaiting_confirmation"] and SESSIONS.get("ac-neg2").pending_plan is None
    assert c.say("go ahead")["operations"] == [] and books(rt)["executed"] == []


@pytest.mark.parametrize("text", [
    "Get the Foshan invoice paid sooner, but don't give anything away",
    "Get paid early on the Foshan invoice, don't give anything away",
    "Get paid early on the Foshan invoice without conceding the rebate",
    "让佛山提前付款，不要给任何让利",
])
def test_an_early_pay_constraint_is_not_a_negation(client, rt, text):
    r = Chat(client, "ac-con").say(text)
    assert r["intent"] == "ACCELERATE_RECEIPT" and r["awaiting_confirmation"] and ops(r) == []


def test_an_early_pay_plan_runs_the_stored_legs_and_not_a_replan(client, rt):
    c = Chat(client, "ac-run")
    c.say(ACCEL)
    plan = pending("ac-run")
    legs = signature(plan.ops)
    r = c.say("go ahead")
    assert ops(r)[0] == ("COUNTER_OFFER", "EXECUTED") and r["negotiation"]["outcome"] == "ACCEPT"
    sent = [(o["kind"]) for o in r["operations"]]
    assert sent[1:] == ["ACCEPT_OFFER"] + [k for k, *_ in legs if k in sent][: len(sent) - 2]


def test_an_early_pay_plan_whose_books_moved_is_proposed_again(client, rt):
    c = Chat(client, "ac-moved")
    c.say(ACCEL)
    # cash down by ¥300,000: the ¥705,000 gap is more than the line and the whole invoice at 0.85% can carry
    # (150,000 + 416,430)
    move_books(rt, -30_000_000)
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before  # the plan no longer comes out the same: nothing runs
    assert "I did not run it" in r["reply"] and "no longer comes out the same" in r["reply"]
    assert SESSIONS.get("ac-moved").pending_plan is None  # no early-pay counter fits any more: nothing to confirm


# ---------------------------------------------------------------- the borrower file, an offer decision, Chinese


def test_accepting_an_offer_is_not_run_when_its_verdict_changed(client, rt):
    c = Chat(client, "pb-eval")
    r = c.say("Evaluate EX02")
    assert r["awaiting_confirmation"] and ops(r) == []
    client.post("/clock/advance", json={"to_day": 1}, headers=OWNER)
    r = c.say("go ahead")
    assert ops(r) == [] and rt.store.commitments() == [] and "it is day 1" in r["reply"]


def test_the_chinese_confirmation_sends_the_stored_operations(client, rt):
    c = Chat(client, "pb-zh")
    r = c.say("帮我补足资金缺口")
    assert r["awaiting_confirmation"] and ops(r) == []
    stored = signature(pending("pb-zh").ops)
    move_books(rt, -10_000_000)
    before = books(rt)
    r = c.say("执行")
    assert ops(r) == [] and books(rt) == before and "没有执行" in r["reply"] and r["awaiting_confirmation"]
    assert signature(pending("pb-zh").ops) != stored
    r = c.say("执行")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_a_leg_queued_for_the_owner_ends_the_run(client, rt):
    """A leg that is Tier 2 comes back PENDING_APPROVAL: it is reported as waiting, and the next leg is not sent."""
    c = Chat(client, "pb-queue")
    c.say(GOAL)
    plan = pending("pb-queue")
    common = {k: getattr(plan.ops[0], k) for k in ("mandate_version", "requested_by", "day")}
    apply_op = ApplyForFacility(op_id="pb-queue-apply", idempotency_key="pb-queue-apply", facility_id="FAC-GGL",
                                amount_fen=20_000_000, **common)
    plan.ops[:] = [apply_op, plan.ops[0]]
    r = c.say("go ahead")
    assert ops(r) == [("APPLY_FOR_FACILITY", "PENDING_APPROVAL")]
    assert "Not sent: Draw ¥150,000.00 on FAC-LINE" in r["reply"] and "needs your approval" in r["reply"]
    assert books(rt)["drawn"]["FAC-LINE"] == 0 and books(rt)["executed"] == []
    assert "funded" not in r["reply"].lower() and "raised" not in r["reply"].lower()
    assert [x["status"] for x in r["plan"]] == ["PENDING_APPROVAL", "SKIPPED"]
