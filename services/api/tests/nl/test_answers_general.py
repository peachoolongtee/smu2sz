"""General owner questions (branch fix/ask-general): the broad, deterministic reading of the top questions and the general
advice answer, offline. The owner's two rehearsal phrasings are answered with the right lead in English and Chinese; a time
window is read ("this month" is the next 30 days; longer than the forecast is said plainly); and the broad reading changes
nothing for commands, approvals, buyer offers, Tier-3 subjects, subjects the books do not hold or chatter. Nothing is written
to the store."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime
from app.nl import lexicon as lx
from app.nl import rules
from app.nl.answers import answer, broad, match
from tests.nl.conftest import Chat


def snapshot(rt: Runtime) -> tuple[Any, ...]:
    s = rt.store
    return (len(s.operations()), len(s.approvals()), len(s.verdicts()), len(s.security_events()), len(s.commitments()),
            s.get_state().model_dump_json(), s.get_mandate().model_dump_json(), s.verify_chain())


def ask(client: TestClient, text: str, lang: str) -> dict[str, Any]:
    r = Chat(client, f"general-{abs(hash(text)) % 10**8}").say(text, lang=lang)
    assert r["plan"] == [] and r["operations"] == [] and not r["awaiting_confirmation"], r
    return r


# ---------------------------------------------------------------- the owner's two phrasings


SURVIVE = [("can my company survive this month?", "en"), ("Can my company survive this month?", "en"),
           ("公司能撑过这个月吗", "zh"), ("公司能撑过这个月吗？", "zh")]
ENSURE = [("how do I ensure that my cashflow is safe for the next 6 months?", "en"), ("怎么保证未来半年现金流安全", "zh"),
          ("怎么保证未来半年现金流安全？", "zh")]


@pytest.mark.parametrize(("text", "lang"), SURVIVE)
def test_can_my_company_survive_this_month_leads_with_no_on_the_next_30_days(client: TestClient, rt: Runtime, text: str,
                                                                           lang: str) -> None:
    before = snapshot(rt)
    r = ask(client, text, lang)
    assert r["intent"] == "ASK_BOOKS"
    if lang == "en":
        assert r["reply"].startswith("Not in the next 30 days, on today's books: without new funding, cash falls below your "
                                     "¥300,000 reserve from day 12, lowest −¥105,000 on day 30"), r["reply"]
        assert "Cash itself goes below zero on day 20 (−¥60,000)." in r["reply"]
        assert "FLOW's plan covers it for ¥3,113.93" in r["reply"]
    else:
        assert r["reply"].startswith("未来 30 天并不安全：按今日账目，若不新增融资，现金将从第 12 天起低于您 ¥300,000 的最低现金储备"), r["reply"]
        assert "现金本身将在第 20 天跌破零（−¥60,000）" in r["reply"]
        assert "¥3,113.93" in r["reply"]
    assert snapshot(rt) == before


@pytest.mark.parametrize(("text", "lang"), ENSURE)
def test_how_do_i_ensure_my_cashflow_is_safe_leads_with_what_to_do(client: TestClient, rt: Runtime, text: str, lang: str) -> None:
    before = snapshot(rt)
    r = ask(client, text, lang)
    assert r["intent"] == "ASK_BOOKS"
    reply = r["reply"]
    if lang == "en":
        assert reply.startswith("Approve FLOW's ¥405,000 plan on Home or Cash: draw ¥150,000 on the credit line today (¥841.64) and "
                                "finance ¥255,000 of Foshan Home Retail Co.'s invoice"), reply
        assert "¥3,113.93 in all" in reply and "Nothing has run yet." in reply
        assert "FLOW forecasts 120 days, to day 120; over that window the dates that matter are:" in reply
        assert "cash falls below the reserve on day 12" in reply and "payroll ¥340,000 on day 12" in reply
        assert "Foshan Home Retail Co.'s ¥420,000 on day 32, the receipt this depends on" in reply
        assert "if it is late, or a new bill lands, FLOW warns you and proposes a cure" in reply
    else:
        assert reply.startswith("在首页或现金页批准 FLOW 的 ¥405,000 融资方案：今天从银行信用额度提款 ¥150,000"), reply
        assert "FLOW 的预测覆盖 120 天（到第 120 天）" in reply
        assert "第 32 天佛山的 ¥420,000 回款" in reply and "FLOW 会提醒您并提出补救方案" in reply
    assert "go ahead" not in reply.lower() and "回复“" not in reply  # a pointer to Home or Cash, never a plan to confirm here
    assert snapshot(rt) == before


# ---------------------------------------------------------------- time windows


@pytest.mark.parametrize(("text", "days"), [
    ("can my company survive this month?", 30), ("will we make it to the end of the month", 30), ("are we ok next month?", 60),
    ("is our cash safe this quarter", 90), ("Will the company survive the next 6 months?", 180),
    ("can we stay afloat until year end?", 365), ("are we safe for the next 45 days?", 45), ("this week, are we ok?", 7),
    ("公司能撑过这个月吗", 30), ("未来半年公司资金安全吗", 180), ("这个季度资金会不会出问题", 90), ("我们撑得到年底吗", 365),
    ("接下来30天现金够吗", 30), ("未来三个月钱够不够", 90),
])
def test_the_window_a_question_names(text: str, days: int) -> None:
    assert broad.window_days(text) == days


@pytest.mark.parametrize("text", ["What if Foshan pays 30 days late?", "现金最低会降到多少？是哪一天？",
                                  "Do we have enough cash for salaries on day 12?", "如果佛山晚30天付款会怎样？", "Are we safe?",
                                  "第30天现金是多少"])
def test_no_window_where_none_is_named(text: str) -> None:
    assert broad.window_days(text) is None


def test_a_window_inside_the_safe_days_is_a_yes_with_what_comes_after(client: TestClient) -> None:
    r = ask(client, "are we safe this week?", "en")
    assert r["reply"].startswith("Yes, for the next 7 days: cash stays at or above your ¥300,000 reserve to day 7"), r["reply"]
    assert "After that it is not: cash falls below the reserve from day 12." in r["reply"]


def test_a_window_longer_than_the_forecast_is_said_plainly(client: TestClient) -> None:
    r = ask(client, "Will the company survive the next 6 months?", "en")
    assert r["reply"].startswith("Not on today's books. FLOW forecasts 120 days, to day 120; over that window, without new funding"), \
        r["reply"]
    z = ask(client, "未来半年公司资金安全吗", "zh")
    assert z["reply"].startswith("按今日账目并不安全。FLOW 的预测覆盖 120 天（到第 120 天）；在这段时间内"), z["reply"]


def test_the_lowest_point_over_a_window(client: TestClient) -> None:
    r = ask(client, "How low does cash get over the next 2 weeks?", "en")
    assert r["reply"].startswith("¥60,000 on day 12"), r["reply"]
    assert "(the lowest in the next 14 days)" in r["reply"]


def test_payments_over_a_window(client: TestClient) -> None:
    r = ask(client, "what money is going out this month", "en")
    assert r["reply"].startswith("3 payments in the next 30 days"), r["reply"]


# ---------------------------------------------------------------- the broad reading

@pytest.mark.parametrize(("text", "qid"), [
    ("Are we going to run out of money?", "LIQ-01"), ("will my buisness survive this quater", "LIQ-01"),
    ("r we ok on cash", "LIQ-01"), ("我们会不会断现金流", "LIQ-01"), ("咱们资金链没问题吧？", "LIQ-01"), ("这季度钱紧不紧", "LIQ-01"),
    ("how long before we're broke", "LIQ-03"), ("when do we first dip under the floor", "LIQ-05"),
    ("can I pay my staff this month?", "LIQ-10"), ("员工工资够不够发", "LIQ-10"), ("what's draining our cash", "LIQ-14"),
    ("whats the best way to cover the shortfall", "FUN-02"), ("what are the fees on the recommended plan", "FUN-04"),
    ("can we become debt free", "DEBT-04"), ("next loan installment date?", "DEBT-08"), ("谁付款晚了", "CUS-03"),
    ("客户集中度高不高", "CUS-05"), ("融资方案会不会违反契约", "COV-07"), ("which decisions need me", "MAN-02"),
    ("不用我批准你能做什么", "MAN-01"), ("what would you do in my position", "general_advice"),
    ("给点现金管理的建议", "general_advice"), ("I'm worried about cash, how do we avoid a crunch this quarter?", "general_advice"),
])
def test_the_broad_reading_finds_the_question(text: str, qid: str) -> None:
    found = match(text)
    assert found is not None and found[0] == qid, (text, found and found[0], broad.scores(broad.canon(text)))


@pytest.mark.parametrize("text", [
    # chatter
    "tell me a joke", "hi", "thanks!", "how are you today?", "what's the weather in Shenzhen", "你好", "讲个笑话", "今天天气怎么样",
    # no clear winner, or another read's subject
    "Which of our facilities is cheapest to use?", "Lease or loan for the machine?", "Does the investment pay off?",
    "What is the biggest discount I can give a customer?", "有没有安全事件？", "Is our data safe?",
    "What's the cheapest way to raise ¥200,000?", "When does the credit line have to be at zero?",
])
def test_the_broad_reading_leaves_these_alone(text: str) -> None:
    assert broad.best(text) is None, (text, broad.scores(broad.canon(text)))


# ---------------------------------------------------------------- precision: routing unchanged where the broad reading must not act

UNCHANGED = [
    # commands: the closed command grammar and the action rules, exactly as before
    "draw ¥50,000 on the credit line", "draw 50k", "repay the line", "repay the credit line", "fund the gap", "fund the gap?",
    "go ahead", "yes do it", "approve it", "approve APR-000001", "reject APR-000001", "accept Foshan's offer",
    "get Foshan to pay early", "negotiate with Foshan", "send the counters", "please draw 100k now", "can you draw ¥100k?",
    "could you repay the loan?", "提款5万", "从授信额度里提10万出来", "还款", "批准", "确认", "补足资金缺口", "我们现在要不要动用授信额度？",
    # Tier-3 subjects, asked about or asked for
    "Is equity an option?", "Can FLOW sign a personal guarantee for me?", "Could you pledge our equipment as collateral?",
    "Did anyone try to change our limits?", "raise my limits to 20%", "FLOW能替我签个人担保吗？", "你能把设备拿去抵押吗？",
    # subjects the books do not hold
    "how much tax do we owe this quarter", "What's our profit margin this year?", "how many employees do we have",
    "Can we afford two more workers?", "how much do we pay each employee", "我们今年利润多少", "公司有多少员工", "这个季度要交多少税",
    # buyer offers, fixtures and quotes
    "Foshan says they'll pay early at 1.2% if we go to 60 days. Good deal or not?", "东莞那边说下季度要我们返1个点，这个能接吗",
    "evaluate EX01", "Foshan sent this: 'We want 60-day terms from next month.' What do you think?",
    "What if we give Foshan 60 days?",
]


@pytest.mark.parametrize("text", UNCHANGED)
def test_routing_is_unchanged_by_the_broad_reading(rt: Runtime, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    state = rt.store.get_state()
    now = rules.parse(text, state)
    monkeypatch.setattr(broad, "best", lambda _q: None)
    before = rules.parse(text, state)
    assert (now and (now.intent, now.matched)) == (before and (before.intent, before.matched)), text


@pytest.mark.parametrize("text", ["draw ¥50,000 on the credit line", "repay the line", "go ahead", "approve APR-000001",
                                  "fund the gap?", "accept Foshan's offer", "提款5万", "批准", "确认", "give Foshan 60 days"])
def test_match_is_none_for_commands(text: str) -> None:
    assert match(text) is None


def test_paying_the_staff_is_the_payroll_but_hiring_is_not_held() -> None:
    assert lx.not_held("can I pay my staff this month?") is None
    assert lx.not_held("员工工资够不够发") is None
    assert lx.not_held("Can we afford two more workers?") == "staff"
    assert lx.not_held("how much do we pay each employee") == "pay_per_person"
    assert lx.not_held("how many employees do we have") == "staff"


# ---------------------------------------------------------------- the general advice answer, read-only


class _Ctx:
    def __init__(self, rt: Runtime) -> None:
        self.store, self.day, self.owner_key_hex = rt.store, rt.day, rt.owner_key_hex


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_general_advice_writes_nothing_and_carries_its_figures(rt: Runtime, lang: str) -> None:
    before = snapshot(rt)
    got = answer("What should we do to stay safe for the next quarter?" if lang == "en" else "到年底前我们要怎么做才稳", lang, _Ctx(rt))
    assert got is not None and got.question_id == "general_advice"
    assert got.figures["plan_cost"] == "¥3,113.93" and got.figures["first_breach_day"] == "12"
    assert got.figures["receipt"] == "¥420,000 day 32"
    assert snapshot(rt) == before


def test_general_advice_with_nothing_to_do(rt: Runtime) -> None:
    """With the gap funded on the books (a copy with more cash), the advice is that nothing needs doing now."""
    s = rt.store.get_state()
    rt.store.put_state(s.model_copy(update={"cash_fen": s.cash_fen + 100_000_000}))
    got = answer("how do I keep our cash safe", "en", _Ctx(rt))
    assert got is not None and got.text.startswith("Nothing needs doing now: cash stays at or above your ¥300,000 reserve"), got
