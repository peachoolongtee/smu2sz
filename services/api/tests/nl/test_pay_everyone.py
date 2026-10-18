""""Can I pay everyone / all my bills / everything this month?" (en and zh) is answered from the whole 30-day horizon on the demo books:
every obligation against the reserve and against zero, on the conservative forecast Home draws. On the golden books the answer is no
(cash reaches -¥105,000 on day 30), it names the first day below the reserve, offers FLOW's plan with its cost, and saves that plan
exactly as "fund the cash gap" does, so a following "go ahead" runs it (or queues it for approval) down the existing path."""

from __future__ import annotations

import re

import pytest

from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat, ops
from tests.nl.test_alerts_opener import _day34

EN = ["Can I pay everyone?", "Can I pay all my bills this month?", "Can I pay everything this month?",
      "Can I pay all my obligations?", "Can we cover all our obligations this month?", "Will I be able to pay everyone this month?"]
ZH = ["我能付清所有账单吗", "这个月所有款项都付得起吗", "能付清所有人吗", "所有账单都能付清吗"]


@pytest.mark.parametrize("text", EN)
def test_the_answer_is_no_over_the_whole_horizon_in_english(client, rt, text) -> None:
    r = Chat(client, "pe-en").say(text)
    assert r["intent"] == "ASK_BOOKS" and not r["reply"].startswith("I can answer questions")
    reply = r["reply"]
    assert reply.startswith("No:"), reply
    assert "day 12" in reply and "−¥105,000 on day 30" in reply and "below zero from day 20" in reply  # first breach, zero, lowest
    assert "¥3,113.93" in reply and "go ahead" in reply
    assert r["awaiting_confirmation"] is True and SESSIONS.get("pe-en").pending_plan is not None
    assert r["operations"] == []  # nothing ran


@pytest.mark.parametrize("text", ZH)
def test_the_answer_is_no_over_the_whole_horizon_in_chinese(client, rt, text) -> None:
    r = Chat(client, "pe-zh").say(text, lang="zh")
    reply = r["reply"]
    assert r["intent"] == "ASK_BOOKS" and reply.startswith("不能："), reply
    assert "第 12 天" in reply and "−¥105,000" in reply and "第 30 天" in reply and "第 20 天起跌破零" in reply
    assert "¥3,113.93" in reply and "执行" in reply
    assert r["awaiting_confirmation"] is True and SESSIONS.get("pe-zh").pending_plan is not None
    assert r["operations"] == []


def test_the_figures_come_from_the_engine_not_the_text(client, rt) -> None:
    """The sums and the cost are the books': the payments added up, the lowest point Home shows, the plan the fund-gap flow proposes."""
    home = client.get("/home?lang=en", headers={"X-Owner-Token": "demo-owner-token"}).json()
    assert home["cash"]["lowest_display"] == "−¥105,000.00" and home["cash"]["lowest_day"] == 30
    chat = Chat(client, "pe-eng")
    reply = chat.say("Can I pay everyone?")["reply"]
    plan = SESSIONS.get("pe-eng").pending_plan
    assert plan is not None and plan.quoted_cost_fen == 311_393
    assert "¥505,000 in all" in reply and "payroll ¥340,000" in reply and "loan payments ¥45,000" in reply
    fund = Chat(client, "pe-fund").say("fund the cash gap")
    other = SESSIONS.get("pe-fund").pending_plan
    assert other is not None and [s.description for s in other.steps] == [s.description for s in plan.steps]
    assert other.quoted_cost_fen == plan.quoted_cost_fen and fund["awaiting_confirmation"] is True


def test_go_ahead_runs_the_saved_plan_through_the_existing_path(client, rt) -> None:
    chat = Chat(client, "pe-go")
    chat.say("Can I pay all my bills this month?")
    cash = rt.store.get_state().cash_fen
    done = chat.say("go ahead")
    assert ops(done) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert rt.store.get_state().cash_fen > cash and done["awaiting_confirmation"] is False
    assert SESSIONS.get("pe-go").pending_plan is None
    again = chat.say("Can I pay everyone?")  # the plan has run: the same question is now a yes
    assert again["reply"].startswith("Yes") and again["awaiting_confirmation"] is False


def test_the_chinese_go_ahead_runs_it(client, rt) -> None:
    chat = Chat(client, "pe-zh-go")
    chat.say("我能付清所有账单吗", lang="zh")
    done = chat.say("好的执行", lang="zh")
    assert ops(done) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_go_ahead_without_the_question_does_nothing(client, rt) -> None:
    done = Chat(client, "pe-none").say("go ahead")
    assert done["operations"] == [] and len(rt.store.operations()) == 0


def test_a_plan_over_the_limits_is_queued_for_approval_not_run(client, rt) -> None:
    """On day 34 the saved plan has a leg above the rate ceiling: its go-ahead queues that leg for approval, exactly as it does after
    "fund the cash gap"."""
    _day34(client, rt)
    chat = Chat(client, "pe-34")
    r = chat.say("Can I pay everyone this month?")
    assert r["awaiting_confirmation"] is True and SESSIONS.get("pe-34").pending_plan is not None
    done = chat.say("go ahead")
    ask_ops = ops(done)
    assert ("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL") in ask_ops and len(rt.store.approvals()) == 1


def test_a_yes_says_yes_and_the_lowest_point_and_saves_nothing(client, rt) -> None:
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"cash_fen": state.cash_fen + 100_000_000_00}))
    en = Chat(client, "pe-yes").say("Can I pay everyone this month?")
    assert en["reply"].startswith("Yes: you can pay all 3 payments due in the next 30 days")
    assert re.search(r"the lowest point is ¥[\d,]+ on day \d+", en["reply"]) and "FLOW's plan" not in en["reply"]
    assert en["awaiting_confirmation"] is False and SESSIONS.get("pe-yes").pending_plan is None
    zh = Chat(client, "pe-yes-zh").say("这个月所有款项都付得起吗", lang="zh")
    assert zh["reply"].startswith("可以：") and re.search(r"最低点是第 \d+ 天的 ¥[\d,]+", zh["reply"])
    assert zh["awaiting_confirmation"] is False and SESSIONS.get("pe-yes-zh").pending_plan is None


@pytest.mark.parametrize("text", ["Can I pay my staff this month?", "Is payroll covered?"])
def test_the_payroll_question_is_still_the_payroll_answer(client, rt, text) -> None:
    reply = Chat(client, "pe-pay").say(text)["reply"]
    assert "payroll on day 12" in reply and "3 payments" not in reply


def test_a_how_to_and_a_request_to_flow_are_not_this_answer(client, rt) -> None:
    how = Chat(client, "pe-how").say("how do i make sure i can pay the bills until year end")["reply"]
    assert not how.startswith(("No:", "Yes:"))
    cmd = Chat(client, "pe-cmd").say("Can you pay all my bills?")
    assert cmd["operations"] == [] and not cmd["reply"].startswith("No: paying all")


def test_asking_while_the_gap_plan_waits_keeps_one_plan_and_go_ahead_runs_it(client, rt) -> None:
    chat = Chat(client, "pe-wait")
    chat.say("fund the cash gap")
    r = chat.say("Can I pay everyone?")
    assert r["awaiting_confirmation"] is True and r["reply"].startswith("No:")
    done = chat.say("go ahead")
    assert ops(done) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
