"""N01/N02/N03: chat says when funding cash lands (ADR-0010), a negotiation sends the follow-up legs it showed, and a
bare constraint is not a refusal.

Every test asserts the stored state (cash, lots, drawn balances, the operations log) as well as the reply."""

from __future__ import annotations

import json

import pytest

from app.nl import consent, offers
from app.nl.plans import signature
from app.nl.sessions import SESSIONS
from tests.nl.conftest import OWNER, Chat, ops
from tests.nl.test_alerts_opener import _day34, _opener
from tests.nl.test_plan_binding import GOAL, LINE_DRAW, books, move_books, pending

# the day-0 plan's advance: the ¥405,000 gap (it includes the existing loan's ¥45,000 day-30 payment) less the line
ADVANCE = ("SUBMIT_INVOICE_FOR_FINANCING", "FAC-IF", "RCV-A", 25_500_000)
SESSIONS_NEG = "Negotiate EX01 with the buyer"


def pending_of(session_id: str):
    """The session's pending plan, or None."""
    return SESSIONS.get(session_id).pending_plan


def lots(rt) -> list[tuple[str, int, int, bool]]:
    return [(x.facility_id, x.request_day, x.arrival_day, x.settled) for x in rt.store.get_state().lots]


# ---------------------------------------------------------------- N01a: fund the gap


def test_the_gap_proposal_names_the_landing_day_and_does_not_count_the_advance_as_cash(client, rt):
    cash = rt.store.get_state().cash_fen
    r = Chat(client, "ld-prop").say(GOAL)
    assert r["awaiting_confirmation"] and ops(r) == []
    reply = r["reply"]
    assert "Cash today: ¥150,000.00." in reply
    assert "Cash later: ¥255,000.00 on FAC-IF, requested today, lands on day 3." in reply
    assert "405,000" in reply.split("Cash today")[0]  # the need is named; it is never called cash in hand
    assert "Raised" not in reply and "in total" not in reply
    advance = next(s for s in r["plan"] if s["kind"] == "SUBMIT_INVOICE_FOR_FINANCING")
    assert "requested today, cash lands on day 3" in advance["description"]
    assert rt.store.get_state().cash_fen == cash and rt.store.get_state().lots == []  # nothing is booked


def test_the_gap_result_separates_cash_in_from_cash_landing_later(client, rt):
    c = Chat(client, "ld-run")
    before = rt.store.get_state()
    c.say(GOAL)
    r = c.say("go ahead")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    reply = r["reply"]
    assert "Submit RCV-A to FAC-IF for a ¥255,000.00 advance: done; requested today, cash lands on day 3." in reply
    assert "Cash in now: ¥150,000.00. Still to land: ¥255,000.00 on FAC-IF, requested today, lands on day 3." in reply
    assert "Raised" not in reply and "funded" not in reply.lower() and "Cost as quoted: ¥3,113.93" in reply
    after = rt.store.get_state()
    assert after.cash_fen == before.cash_fen + 15_000_000  # the draw only: the advance is not in cash
    assert lots(rt) == [("FAC-LINE", 0, 0, True), ("FAC-IF", 0, 3, False)]
    # the clock credits the advance only when it closes the landing day
    client.post("/clock/advance", json={"to_day": 2}, headers=OWNER)
    assert ("FAC-IF", 0, 3, False) in lots(rt)
    client.post("/clock/advance", json={"to_day": 4}, headers=OWNER)
    assert ("FAC-IF", 0, 3, True) in lots(rt)


def test_the_chinese_gap_replies_carry_the_landing_day(client, rt):
    c = Chat(client, "ld-zh")
    r = c.say("帮我补足资金缺口")
    assert r["lang"] == "zh" and r["awaiting_confirmation"]
    assert "今日到账：¥150,000.00。稍后到账：FAC-IF ¥255,000.00，今日申请，第 3 天到账。" in r["reply"]
    assert "第 3 天到账" in next(s for s in r["plan"] if s["kind"] == "SUBMIT_INVOICE_FOR_FINANCING")["description"]
    r = c.say("执行")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert "今日申请，第 3 天到账" in r["reply"] and "已到账：¥150,000.00。待到账：FAC-IF ¥255,000.00" in r["reply"]
    assert "合计融得" not in r["reply"] and ("FAC-IF", 0, 3, False) in lots(rt)


def test_a_direct_draw_on_a_facility_with_a_lead_time_says_when_it_lands(client, rt):
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"facilities": [
        f.model_copy(update={"lead_time_days": 2}) if f.id == "FAC-LINE" else f for f in s.facilities]}))
    c = Chat(client, "ld-direct")
    r = c.say("draw ¥100,000 on the credit line")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED")] and "lands on day 2" in r["reply"]
    assert lots(rt) == [("FAC-LINE", 0, 2, False)] and rt.store.get_state().cash_fen == s.cash_fen


def test_a_chinese_direct_draw_says_when_it_lands(client, rt):
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"facilities": [
        f.model_copy(update={"lead_time_days": 2}) if f.id == "FAC-LINE" else f for f in s.facilities]}))
    r = Chat(client, "ld-direct-zh").say("从授信额度提款¥50,000")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED")] and "第 2 天到账" in r["reply"]
    assert lots(rt) == [("FAC-LINE", 0, 2, False)] and rt.store.get_state().cash_fen == s.cash_fen


# ---------------------------------------------------------------- N01a: the alert cure on day 34


def test_the_day_34_opener_and_its_result_name_day_37(client, rt):
    _day34(client, rt)
    body = _opener(client, "ld-34").json()
    assert "requested today, cash lands on day 37" in body["reply"] and body["awaiting_confirmation"]
    cash = rt.store.get_state().cash_fen
    r = Chat(client, "ld-34").say("go ahead")
    assert ops(r) == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]  # above the rate ceiling: queued, not run
    assert "day 37" in r["reply"] and "I have not run it" in r["reply"]
    assert rt.store.get_state().cash_fen == cash and not [x for x in rt.store.get_state().lots if not x.settled]


def test_the_day_34_cure_once_approved_reports_day_37_and_leaves_the_cash_unchanged(client, rt):
    _day34(client, rt)
    _opener(client, "ld-34r")
    c = Chat(client, "ld-34r")
    queued = c.say("go ahead")
    cash = rt.store.get_state().cash_fen
    aid = queued["operations"][0]["approval_id"]
    r = c.say(f"approve {aid}")
    assert [o["status"] for o in r["operations"]] == ["EXECUTED"] and "lands on day 37" in r["reply"]
    assert rt.store.get_state().cash_fen == cash  # the advance is not cash until the clock closes day 37
    assert [(x.request_day, x.arrival_day) for x in rt.store.get_state().lots if not x.settled] == [(34, 37)]


def test_the_chinese_opener_and_result_carry_day_37(client, rt):
    _day34(client, rt)
    body = _opener(client, "ld-34zh", lang="zh").json()
    assert "今日申请，第 37 天到账" in body["reply"]
    r = Chat(client, "ld-34zh").say("执行")
    assert "第 37 天" in r["reply"] and ops(r) == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]


# ---------------------------------------------------------------- N01b: repay only what has landed


def _line_with_a_part_in_transit(client, rt) -> None:
    move_books(rt, 100_000_000)
    Chat(client, "ld-rp-setup").say("draw ¥100,000 on the credit line")  # lead time 0: landed
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"facilities": [
        f.model_copy(update={"lead_time_days": 2}) if f.id == "FAC-LINE" else f for f in s.facilities]}))
    assert ops(Chat(client, "ld-rp-setup2").say("draw ¥50,000 on the credit line")) == [("DRAW_FACILITY", "EXECUTED")]


def test_repay_defaults_to_the_landed_balance_and_names_when_the_rest_lands(client, rt):
    _line_with_a_part_in_transit(client, rt)
    line = next(f for f in rt.store.get_state().facilities if f.id == "FAC-LINE")
    assert line.drawn_fen == 15_000_000 and lots(rt) == [("FAC-LINE", 0, 0, True), ("FAC-LINE", 0, 2, False)]
    c = Chat(client, "ld-rp")
    asked = c.say("Is it OK to repay the credit line?")  # a question is answered, never proposed (app/nl/ask.py)
    assert asked["intent"] == "ASK_BOOKS" and not asked["awaiting_confirmation"] and ops(asked) == []
    assert SESSIONS.get("ld-rp").pending_plan is None
    r = c.say("I'd like to repay the credit line")
    assert r["awaiting_confirmation"] and ops(r) == []
    assert signature(pending("ld-rp").ops) == [("REPAY_FACILITY", "FAC-LINE", None, 10_000_000)]  # landed, not drawn
    assert "Repay ¥100,000.00 on FAC-LINE" in r["reply"]
    assert ("A further ¥50,000.00 on FAC-LINE, requested on day 0, lands on day 2 and cannot be repaid before then."
            in r["reply"])
    r = c.say("go ahead")
    assert ops(r) == [("REPAY_FACILITY", "EXECUTED")] and "lands on day 2" in r["reply"]
    after = next(f for f in rt.store.get_state().facilities if f.id == "FAC-LINE")
    assert after.drawn_fen == 5_000_000 and lots(rt) == [("FAC-LINE", 0, 2, False)]  # the part in transit is untouched


def test_asking_to_repay_more_than_has_landed_repays_the_landed_balance_and_says_so(client, rt):
    _line_with_a_part_in_transit(client, rt)
    r = Chat(client, "ld-rp2").say("I'd like to repay ¥150,000 on the credit line")
    assert signature(pending("ld-rp2").ops) == [("REPAY_FACILITY", "FAC-LINE", None, 10_000_000)]
    assert "lands on day 2" in r["reply"] and "cannot be repaid before then" in r["reply"]


def test_nothing_landed_means_nothing_to_repay(client, rt):
    s = rt.store.get_state()
    move_books(rt, 100_000_000)
    rt.store.put_state(rt.store.get_state().model_copy(update={"facilities": [
        f.model_copy(update={"lead_time_days": 2}) if f.id == "FAC-LINE" else f for f in s.facilities]}))
    Chat(client, "ld-rp3a").say("draw ¥100,000 on the credit line")
    logged = len(rt.store.operations())
    r = Chat(client, "ld-rp3").say("repay the credit line")
    assert ops(r) == [] and len(rt.store.operations()) == logged and not r["awaiting_confirmation"]
    assert "Nothing has landed" in r["reply"] and "lands on day 2" in r["reply"]


# ---------------------------------------------------------------- N02: a negotiation sends the legs it showed


def _hardline(client, session: str) -> Chat:
    c = Chat(client, session, buyer_profile="BUYER-1-HARDLINE")
    r = c.say("Evaluate EX01")
    assert r["awaiting_confirmation"]
    return c


def test_the_no_deal_legs_shown_with_the_proposal_are_the_legs_that_run(client, rt, monkeypatch):
    c = _hardline(client, "ng-run")
    plan = pending("ng-run")
    assert signature(plan.data["refuse_ops"]) == [LINE_DRAW, ADVANCE]
    assert "If the buyer refuses" in " ".join(s.description for s in plan.steps) or any(
        s.condition and "refuses" in s.condition for s in plan.steps)
    stored = [(o.op_id, o.idempotency_key) for o in plan.data["refuse_ops"]]
    cash = rt.store.get_state().cash_fen
    def never(*_a, **_k):
        raise AssertionError("a funding plan was built after the owner's confirmation")

    for name in ("committed_plan", "runnable_legs", "followups", "status_quo_offer"):
        monkeypatch.setattr(offers, name, never)
    r = c.say("go ahead")
    assert r["negotiation"]["outcome"] == "NO_DEAL"
    assert ops(r) == [("COUNTER_OFFER", "EXECUTED"), ("COUNTER_OFFER", "EXECUTED"), ("DRAW_FACILITY", "EXECUTED"),
                      ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    logged = [json.loads(e.payload_json) for e in rt.store.operations()][-2:]
    assert [(e["op_id"], e["idempotency_key"]) for e in logged] == stored
    assert [e.get("amount_fen") or e.get("advance_fen") for e in logged] == [15_000_000, 25_500_000]
    assert rt.store.get_state().cash_fen == cash + 15_000_000 and lots(rt)[-1] == ("FAC-IF", 0, 3, False)
    assert "lands on day 3" in r["reply"] and "Raised" not in r["reply"]
    assert [s["status"] for s in r["plan"]][-2:] == ["EXECUTED", "EXECUTED"]


def test_the_proposal_names_the_landing_day_of_the_follow_up_funding(client, rt):
    c = Chat(client, "ng-prop")
    r = c.say(SESSIONS_NEG)
    assert r["awaiting_confirmation"] and ops(r) == []
    assert "If the buyer refuses:" in r["reply"] and "requested today, lands on day 3" in r["reply"]
    assert "If the buyer accepts Option A, the rest of the gap:" in r["reply"] and "Nothing has been sent" in r["reply"]
    assert rt.store.get_state().cash_fen == 40_000_000 and rt.store.get_state().lots == []


def said(reply: str) -> str:
    """What the reply says about the run, lower-cased: without the verdict line, whose summary may say which plan
    funds a counter's own shortfall (the counter property), which is not a claim that the gap was funded."""
    return "\n".join(line for line in reply.splitlines() if not line.startswith("Verdict ")).lower()


def test_a_refused_second_follow_up_leg_is_reported_and_the_gap_is_not_called_funded(client, rt):
    c = _hardline(client, "ng-refuse")
    plan = pending("ng-refuse")
    # the books changed after the proposal so that the executor refuses the second leg: an advance above its invoice
    plan.data["refuse_ops"][1] = plan.data["refuse_ops"][1].model_copy(update={"advance_fen": 99_900_000})
    r = c.say("go ahead")
    assert ops(r) == [("COUNTER_OFFER", "EXECUTED"), ("COUNTER_OFFER", "EXECUTED"), ("DRAW_FACILITY", "EXECUTED"),
                      ("SUBMIT_INVOICE_FOR_FINANCING", "REFUSED")]
    after = books(rt)
    assert after["drawn"]["FAC-LINE"] == 15_000_000 and after["drawn"]["FAC-IF"] == 0
    assert lots(rt) == [("FAC-LINE", 0, 0, True)]  # no advance, so no cash in transit
    reply = r["reply"].lower()
    assert "draw ¥150,000.00 on fac-line: done" in reply and "refused" in reply
    for word in ("funded", "raised", "covered", "cash in now"):
        assert word not in said(r["reply"])
    assert [s["status"] for s in r["plan"]][-2:] == ["EXECUTED", "REFUSED"]
    assert pending_of("ng-refuse") is None


def test_a_refused_first_follow_up_leg_stops_the_run_and_names_the_legs_not_sent(client, rt):
    c = _hardline(client, "ng-first")
    plan = pending("ng-first")
    plan.data["refuse_ops"][:] = [plan.data["refuse_ops"][1].model_copy(update={"advance_fen": 99_900_000}),
                                  plan.data["refuse_ops"][0]]
    r = c.say("go ahead")
    assert ops(r)[-1] == ("SUBMIT_INVOICE_FOR_FINANCING", "REFUSED") and ("DRAW_FACILITY", "EXECUTED") not in ops(r)
    assert books(rt)["drawn"]["FAC-LINE"] == 0 and "Not sent: Draw ¥150,000.00 on FAC-LINE" in r["reply"]
    assert "stopped after step 1 of 2" in r["reply"] and "funded" not in said(r["reply"])
    assert [s["status"] for s in r["plan"]][-2:] == ["REFUSED", "SKIPPED"]


def test_the_remaining_gap_legs_after_an_accepted_counter_run_as_shown(client, rt):
    c = Chat(client, "ng-acc")
    c.say(SESSIONS_NEG)
    legs = pending("ng-acc").data["accept_ops"]["Option A"]
    shown = signature(legs)
    r = c.say("go ahead")
    assert r["negotiation"]["accepted_counter"] == "Option A"
    assert ("ACCEPT_OFFER", "EXECUTED") in ops(r) and ops(r)[-1] == ("DRAW_FACILITY", "EXECUTED")
    logged = json.loads(rt.store.operations()[-1].payload_json)
    assert [(logged["kind"], logged["facility_id"], None, logged["amount_fen"])] == [
        (k, f, None, a) for k, f, _r, a in shown]
    assert logged["op_id"] == legs[0].op_id


def test_a_refused_remaining_gap_leg_is_reported_and_not_called_funded(client, rt):
    c = Chat(client, "ng-acc2")
    c.say(SESSIONS_NEG)
    legs = pending("ng-acc2").data["accept_ops"]["Option A"]
    legs[0] = legs[0].model_copy(update={"amount_fen": 900_000_000})  # above the line's limit: refused
    r = c.say("go ahead")
    assert ops(r)[-1] == ("DRAW_FACILITY", "REFUSED") and ("ACCEPT_OFFER", "EXECUTED") in ops(r)
    assert books(rt)["drawn"]["FAC-LINE"] == 0 and "refused" in r["reply"].lower()
    for word in ("funded", "raised", "covered"):
        assert word not in said(r["reply"])


def test_a_negotiation_gone_stale_runs_nothing_and_proposes_the_follow_up_again(client, rt):
    c = _hardline(client, "ng-stale")
    move_books(rt, -10_000_000)  # the books moved: what would follow the counters is no longer what was shown
    before = books(rt)
    r = c.say("go ahead")
    assert ops(r) == [] and books(rt) == before and "I did not run it" in r["reply"]


# ---------------------------------------------------------------- N03: a constraint is not a refusal


@pytest.mark.parametrize("text", ["don't give anything away", "Don't give anything away.", "不要给任何让步"])
def test_a_bare_constraint_with_a_negotiation_pending_proposes_again_and_sends_nothing(client, rt, text):
    c = Chat(client, "n3-neg")
    first = c.say(SESSIONS_NEG)
    assert "I would send 2 counter(s)" in first["reply"] or "2 条反报价" in first["reply"]
    before = books(rt)
    r = c.say(text)
    assert ops(r) == [] and books(rt) == before and rt.store.commitments() == []
    assert r["awaiting_confirmation"] and r["intent"] == "NEGOTIATE" and r["amended"]
    assert [x["label"] for x in r["verdict"]["counters"]] == ["Option A"]  # only the counter that concedes nothing
    assert all(cv["forward_value_fen"] == 0 for cv in r["verdict"]["counters"])
    plan = pending("n3-neg")
    assert plan.data["zero_forward"] is True
    sent = c.say("go ahead")
    assert [k for k, _ in ops(sent)].count("COUNTER_OFFER") == 1 and len(rt.store.commitments()) == 1


@pytest.mark.parametrize(("setup", "intent"), [
    (GOAL, "FUND_GAP"), ("Get paid early on the Foshan invoice without giving anything away next quarter.",
                         "ACCELERATE_RECEIPT")])
def test_a_bare_constraint_keeps_any_other_plan_pending_and_sends_nothing(client, rt, setup, intent):
    c = Chat(client, "n3-other")
    c.say(setup)
    stored = signature(pending("n3-other").ops)
    before = books(rt)
    r = c.say("don't give anything away")
    assert ops(r) == [] and books(rt) == before and r["awaiting_confirmation"] and r["intent"] == intent
    assert signature(pending("n3-other").ops) == stored


@pytest.mark.parametrize("setup", [SESSIONS_NEG, GOAL, "帮我补足资金缺口"])
@pytest.mark.parametrize("text", ["先不要发送", "先别发送", "先不要执行"])
def test_a_chinese_refusal_with_a_plan_pending_declines_it(client, rt, setup, text):
    c = Chat(client, "n3-zh")
    c.say(setup)
    assert pending_of("n3-zh") is not None
    before = books(rt)
    r = c.say(text)
    assert ops(r) == [] and books(rt) == before and rt.store.commitments() == []
    assert r["intent"] == "REJECT" and not r["awaiting_confirmation"] and "已取消" in r["reply"]
    assert pending_of("n3-zh") is None
    assert c.say("go ahead")["operations"] == [] and books(rt) == before  # and a later go-ahead runs nothing


def test_the_grammar_reads_a_constraint_and_a_chinese_refusal(client, rt):
    assert consent.confirmation("先不要发送") == "no" and consent.confirmation("先别发送") == "no"
    for text in ("don't give anything away", "without conceding the rebate", "不要给任何让步", "no concessions"):
        assert consent.is_constraint(text) and consent.confirmation(text) is None
    for text in ("don't", "no", "cancel", "不要", "取消", "do not go ahead"):
        assert consent.confirmation(text) == "no" and not consent.is_constraint(text)


# ---------------------------------------------------------------- accelerate: the fallback and the financing plan


ACCEL = "Get paid early on the Foshan invoice without giving anything away next quarter."


def test_the_early_pay_proposal_names_the_landing_day_of_the_fallback(client, rt):
    c = Chat(client, "ac-ld")
    r = c.say(ACCEL)
    assert r["awaiting_confirmation"] and ops(r) == []
    assert "If BUYER-1 refuses:" in r["reply"] and "requested today, lands on day 3" in r["reply"]
    assert "Raised" not in r["reply"]
    assert rt.store.get_state().lots == [] and rt.store.get_state().cash_fen == 40_000_000


def test_the_early_pay_fallback_result_names_the_landing_day(client, rt):
    c = Chat(client, "ac-ld2", buyer_profile="BUYER-1-HARDLINE")
    c.say(ACCEL)
    r = c.say("go ahead")
    assert ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED") in ops(r)
    assert "refused" in r["reply"] and "requested today, cash lands on day 3" in r["reply"]
    assert "Still to land: ¥255,000.00 on FAC-IF" in r["reply"] and "Raised" not in r["reply"]
    assert ("FAC-IF", 0, 3, False) in lots(rt)


def test_the_financing_plan_for_an_invoice_names_the_landing_day_in_chinese(client, rt):
    c = Chat(client, "ac-ld3")
    c.say(ACCEL)
    r = c.say("改用发票融资")
    assert r["awaiting_confirmation"] and "第 3 天到账" in r["reply"]
    r = c.say("执行")
    assert ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED") in ops(r) and "第 3 天到账" in r["reply"]
    assert ("FAC-IF", 0, 3, False) in lots(rt)
