"""ASK_BOOKS and the question gate (app/nl/ask.py, app/nl/rules.py): a question about the books is answered, never acted on.

The owner-question bank (evals/owner_questions, BASELINE.md section 3) found 35 replies that were wrong: questions read as
instructions (a repayment, a funding plan, a counter to send, a fact to record, an early-pay plan), Tier-3 words in a
question written to the hash-chained log as refused requests, broad Chinese status cues answering what the books do not
hold, and a late payment compiled as a change to the buyer's terms. Each one is pinned here in English and Chinese, with
the rule underneath it: a question proposes no plan, compiles no offer, queues or runs nothing and writes nothing to the
operations log or the security log. Requests phrased as questions keep their action reading, and the consent grammar
(app/nl/consent.py) is unchanged: test_consent.py still passes as it was.
"""

from __future__ import annotations

import re
import sys
import types
from dataclasses import dataclass, field

import pytest

from app.domain.fixtures import load_scenario
from app.nl import lexicon as lx
from app.nl.rules import parse
from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat, ops

STATE = load_scenario()[0]


def fingerprint(rt) -> dict:
    s = rt.store
    return {"operations": len(s.operations()), "approvals": len(s.approvals()), "commitments": len(s.commitments()),
            "security_events": len(s.security_events()), "state_version": s.get_state().state_version,
            "mandate_version": s.get_mandate().version}


def asked(client, rt, text: str, lang: str, session: str = "ask") -> dict:
    """One question in a fresh session: nothing may run, be queued, be proposed or be logged."""
    before = fingerprint(rt)
    r = Chat(client, f"{session}-{abs(hash(text)) % 10**8}").say(text, lang=lang)
    assert ops(r) == [], r["reply"]
    assert not r["awaiting_confirmation"], r["reply"]
    assert all(p["status"] not in ("PROPOSED", "PENDING_APPROVAL", "EXECUTED") for p in r["plan"]), r["plan"]
    assert fingerprint(rt) == before, r["reply"]
    assert SESSIONS.get(r["session_id"]).pending_plan is None
    return r


# ---------------------------------------------------------------- the 35 WRONG cases (BASELINE.md section 3)

# (question, lang, the intent it wrongly had, a pattern the new reply must carry)
WRONG_CASES = [
    # liquidity and debt
    ("What is causing the cash gap?", "en", "FUND_GAP", r"¥400,000\.00.*¥405,000\.00"),
    ("资金缺口是怎么造成的？", "zh", "FUND_GAP", r"¥400,000\.00.*¥405,000\.00"),
    ("Can we pay off all our loans?", "en", "REPAY_FACILITY", r"cannot answer that from the books"),
    ("我们能把债务还清吗？", "zh", "REPAY_FACILITY", r"暂时还不能"),
    ("我们能还清所有贷款吗？", "zh", "REPAY_FACILITY", r"暂时还不能"),
    ("下一笔贷款还款是什么时候？", "zh", "REPAY_FACILITY", r"暂时还不能"),
    ("我们现在要不要动用授信额度？", "zh", "FUND_GAP", r"需要融资的缺口：¥405,000\.00"),
    ("Does the investment pay off?", "en", "REPAY_FACILITY", r"NPV ¥380,885\.77.*payback in month 31"),
    # customers, deals and funding
    ("谁拖欠我们的款？", "zh", "RECORD_FACT", r"目前没有逾期款项"),
    ("我们的应收账款周转天数是多少？", "zh", "FUND_GAP", r"谁欠我们钱"),
    ("What if Foshan pays 30 days late?", "en", None, r"I have not re-run the forecast for a late payment"),
    ("如果佛山晚30天付款会怎样？", "zh", None, r"我没有针对延迟付款重新做预测"),
    ("Any open negotiations?", "en", "NEGOTIATE", r"Nothing is waiting on you or on anyone else"),
    ("给佛山60天账期要花我们多少钱？", "zh", "SHOW_STATUS", r"¥24,326\.92"),
    ("我们发过什么还价？", "zh", "NEGOTIATE", r"暂时还不能.*今天有什么变化"),
    ("FLOW的方案要花多少钱？", "zh", "SHOW_STATUS", r"总成本 .*¥3,113\.93"),
    ("我们的发票最多能融多少钱？", "zh", "SHOW_STATUS", r"需要融资的缺口"),
    ("What's the break-even discount for early payment?", "en", "ACCELERATE_RECEIPT", r"break-even early-payment discount is 0\.88%"),
    ("提前付款折扣的盈亏平衡点是多少？", "zh", "ACCELERATE_RECEIPT", r"盈亏平衡点是 0\.88%"),
    ("Above what discount is early payment too expensive?", "en", "ACCELERATE_RECEIPT", r"0\.88%"),
    # covenants, capex, activity and mandate
    ("Does the plan breach any covenant?", "en", "SHOW_STATUS", r"cannot answer that from the books.*covenant ratios"),
    ("Do we have any capex contracts?", "en", "CAPEX", r"cannot answer that from the books"),
    ("有哪些设备采购合同？", "zh", "CAPEX", r"暂时还不能"),
    ("How much money has FLOW moved?", "en", "SHOW_STATUS", r"cannot answer that from the books.*What changed today"),
    ("FLOW一共动了多少钱？", "zh", "SHOW_STATUS", r"暂时还不能.*今天有什么变化"),
    ("Did anyone try to change our limits?", "en", "OUT_OF_SCOPE", r"^No\. Nobody has tried to change your mandate"),
    ("有人试图修改我们的限额吗？", "zh", "OUT_OF_SCOPE", r"^没有。没有人尝试修改您的授权或限额"),
    ("授权什么时候到期？", "zh", "SHOW_STATUS", r"暂时还不能"),
    # not in the books
    ("What's our VAT position this quarter?", "en", "SHOW_STATUS", r"^FLOW's books do not hold VAT\."),
    ("本季度增值税情况怎么样？", "zh", "SHOW_STATUS", r"^FLOW 的账目中没有增值税数据。"),
    ("库存值多少钱？", "zh", "SHOW_STATUS", r"^FLOW 的账目中没有库存数据。"),
    ("每个银行账户里各有多少钱？", "zh", "SHOW_STATUS", r"^FLOW 的账目中没有各银行账户的余额。.*¥400,000\.00"),
    ("按账户列一下余额。", "zh", "SHOW_STATUS", r"^FLOW 的账目中没有各银行账户的余额。"),
    ("竞争对手情况怎么样？", "zh", "SHOW_STATUS", r"^FLOW 的账目中没有市场或竞争对手数据。"),
    ("公司值多少钱？", "zh", "SHOW_STATUS", r"^FLOW 的账目中没有公司估值。.*EBITDA"),
]


def test_the_list_is_the_baselines_35():
    assert len(WRONG_CASES) == 35
    assert sum(1 for _, lang, _, _ in WRONG_CASES if lang == "zh") == 23


@pytest.mark.parametrize(("text", "lang", "was", "pattern"), WRONG_CASES)
def test_a_wrong_case_is_answered_and_nothing_happens(client, rt, text, lang, was, pattern):
    r = asked(client, rt, text, lang)
    if was is not None:
        assert r["intent"] != was, r["reply"]
    assert re.search(pattern, r["reply"], re.DOTALL), r["reply"]
    assert "Reply \"Yes, run it\"" not in r["reply"] and "回复“好，执行”" not in r["reply"]  # no plan offered for a go-ahead


def test_a_late_payment_is_never_compiled_as_a_change_to_the_terms(client, rt):
    """offers.py: "pays 30 days late" carried a day count, so it was compiled as 30-day terms and got a verdict."""
    before = len(rt.store.verdicts())
    for text, lang in (("What if Foshan pays 30 days late?", "en"), ("如果佛山晚30天付款会怎样？", "zh"),
                       ("What happens if the Foshan invoice slips a month?", "en"), ("佛山的款晚一个月到会怎么样？", "zh")):
        r = asked(client, rt, text, lang)
        assert r["intent"] == "WHAT_IF" and r["verdict"] is None, r["reply"]
        assert "needs your approval" not in r["reply"] and "需要您批准" not in r["reply"]
    assert len(rt.store.verdicts()) == before  # nothing was evaluated as an offer


def test_yao_bu_yao_is_a_question_not_a_negation(client, rt):
    """要不要 ("whether to") was read as 不要 ("do not"): "Understood, I have not done anything"."""
    for text in ("我们现在要不要动用授信额度？", "要不要跟佛山谈判？", "要不要让佛山提前付款？"):
        r = asked(client, rt, text, "zh")
        assert r["intent"] not in ("FUND_GAP", "NEGOTIATE", "ACCELERATE_RECEIPT"), r["reply"]
        assert "明白，我没有执行任何操作" not in r["reply"]


# ---------------------------------------------------------------- the question gate, for every action intent

# Each action intent's trigger words inside a question (en and zh): no plan, no offer, no operation, no log entry.
GATE = [
    ("Should we fund the gap?", "en"), ("要不要补上资金缺口？", "zh"),
    ("How big is the cash gap?", "en"), ("资金缺口有多大？", "zh"),
    ("Should we draw on the credit line now?", "en"), ("现在该提款了吗？", "zh"),
    ("Should we repay the credit line?", "en"), ("要不要还授信额度？", "zh"),
    ("Is there anything we could repay right now?", "en"), ("下次还贷是哪天？", "zh"),
    ("Should we negotiate with Foshan?", "en"), ("我们要不要和佛山谈判？", "zh"),
    ("What counter did we send?", "en"), ("我们给佛山还价了吗？", "zh"),
    ("Should we get Foshan to pay early?", "en"), ("佛山提前付款划算吗？", "zh"),
    ("Is the early-pay discount worth it?", "en"), ("佛山1.2%的提前付款折扣划算吗？", "zh"),
    ("Did we record a late payment for the supplier?", "en"), ("谁拖欠我们的款？", "zh"),
    ("What is our DSO?", "en"), ("客户平均多久付款？", "zh"),
]


@pytest.mark.parametrize(("text", "lang"), GATE)
def test_an_action_word_in_a_question_runs_and_proposes_nothing(client, rt, text, lang):
    r = asked(client, rt, text, lang)
    assert r["intent"] not in ("FUND_GAP", "REPAY_FACILITY", "NEGOTIATE", "ACCELERATE_RECEIPT", "RECORD_FACT"), r["reply"]
    assert r["verdict"] is None


@pytest.mark.parametrize(("text", "lang"), GATE)
def test_the_gate_reads_each_question_as_a_question(text, lang):
    p = parse(text, STATE)
    assert p is not None and p.intent.value not in ("FUND_GAP", "REPAY_FACILITY", "NEGOTIATE", "ACCELERATE_RECEIPT",
                                                    "RECORD_FACT"), p
    assert not p.tentative and not p.slots.execute_now and p.slots.tier3 is None


@pytest.mark.parametrize(("text", "intent"), [
    # requests phrased as questions keep their action reading (a proposal at most; consent.py decides what runs)
    ("can we pull the Foshan receivable forward? 0.5% max", "ACCELERATE_RECEIPT"),
    ("东莞那笔货款能不能让他们早点打款？折扣最多0.6%", "ACCELERATE_RECEIPT"),
    ("Dongguan 那张 invoice 可以 early pay 吗", "ACCELERATE_RECEIPT"),
    ("Can you draw ¥100,000 on the credit line?", "FUND_GAP"),
    ("能不能从授信额度提款10万元？", "FUND_GAP"),
    ("Could you arrange some bridging money for the payroll crunch?", None),  # no rule: the classifier's turn
    # commands are untouched
    ("draw ¥100,000 on the credit line", "FUND_GAP"), ("fund the gap", "FUND_GAP"), ("repay the credit line", "REPAY_FACILITY"),
    ("Negotiate EX01 with the buyer", "NEGOTIATE"), ("Do not negotiate with Foshan", "NEGOTIATE"), ("不要谈判", "NEGOTIATE"),
    # buyer offers the owner asks about still get their verdict
    ("Foshan wants 60-day terms. Can we accept?", "EVALUATE_OFFER"), ("Is this a good offer? “We can pay early at 1.5%.”", "EVALUATE_OFFER"),
    ("What if we give Foshan 60-day terms?", "WHAT_IF"), ("如果给佛山60天账期呢？", "WHAT_IF"),
])
def test_requests_commands_and_offers_keep_their_reading(text, intent):
    p = parse(text, STATE)
    assert (p.intent.value if p is not None else None) == intent, p


def test_a_command_still_executes_and_its_question_form_does_not(client, rt):
    c = Chat(client, "ask-cmd")
    q = c.say("Should we draw ¥100,000 on the credit line?")
    assert ops(q) == [] and not q["awaiting_confirmation"] and q["intent"] == "ASK_BOOKS"
    assert ops(c.say("go ahead")) == []  # the question left nothing to confirm
    assert ops(c.say("draw ¥100,000 on the credit line")) == [("DRAW_FACILITY", "EXECUTED")]


def test_a_question_does_not_cancel_or_confirm_a_waiting_plan(client, rt):
    c = Chat(client, "ask-pending")
    assert c.say("fund the gap")["awaiting_confirmation"]
    r = c.say("How much would FLOW's plan cost?")
    assert ops(r) == [] and SESSIONS.get("ask-pending").pending_plan is not None
    assert len(ops(c.say("go ahead"))) == 2  # the plan shown before the question is the one that runs


# ---------------------------------------------------------------- Tier-3 words in a question write nothing to the log

TIER3_QUESTIONS = [
    ("Did anyone try to change our limits?", "en", "CHANGE_MANDATE"),
    ("有人试图修改我们的限额吗？", "zh", "CHANGE_MANDATE"),
    ("Has someone tried to lower the reserve?", "en", "CHANGE_MANDATE"),
    ("Is equity an option?", "en", "ISSUE_EQUITY"),
    ("增发股权是一个选项吗？", "zh", "ISSUE_EQUITY"),
    ("Is a personal guarantee ever needed?", "en", "SIGN_PERSONAL_GUARANTEE"),
    ("个人担保是什么意思？", "zh", "SIGN_PERSONAL_GUARANTEE"),
    ("Does the bank want collateral?", "en", "PLEDGE_COLLATERAL"),
    ("要不要抵押设备？", "zh", "PLEDGE_COLLATERAL"),
]


@pytest.mark.parametrize(("text", "lang", "kind"), TIER3_QUESTIONS)
def test_a_tier3_question_appends_nothing_to_the_log(client, rt, text, lang, kind):
    r = asked(client, rt, text, lang)
    assert r["intent"] in ("ASK_BOOKS", "EXPLAIN"), r["reply"]
    assert r["security_events"] == []
    assert "refused by the executor and logged" not in r["reply"] and "执行器已拒绝并记录" not in r["reply"]
    assert kind not in r["reply"]  # never the code


def test_equity_is_answered_as_information(client, rt):
    r = asked(client, rt, "Is equity an option?", "en")
    assert r["reply"].startswith("Issuing equity is outside what FLOW may do: it is a Tier-3 action")
    assert "Owner equity or outside investor is on the funding menu for comparison only (60 days to cash)" in r["reply"]
    zh = asked(client, rt, "增发股权是一个选项吗？", "zh")
    assert zh["reply"].startswith("发行股权不在 FLOW 的权限之内：这是三级操作")


def test_an_attempt_is_read_from_the_log(client, rt):
    """After a real Tier-3 request (refused and logged), the question about attempts says so; asking adds nothing."""
    assert ops(Chat(client, "t3-req").say("Change the mandate floor to ¥100,000")) == [("CHANGE_MANDATE", "REFUSED")]
    logged = fingerprint(rt)
    r = Chat(client, "t3-ask").say("Did anyone try to change our limits?")
    assert r["reply"].startswith("Yes: 1 request to change your mandate or its limits was refused and logged")
    assert fingerprint(rt) == logged


@pytest.mark.parametrize(("text", "kind"), [("Can FLOW sign a personal guarantee for me?", "SIGN_PERSONAL_GUARANTEE"),
                                            ("Could you pledge our equipment as collateral?", "PLEDGE_COLLATERAL"),
                                            ("Sign the personal guarantee for the credit line", "SIGN_PERSONAL_GUARANTEE"),
                                            ("你能把设备拿去抵押吗？", "PLEDGE_COLLATERAL")])
def test_a_tier3_request_is_still_refused_by_the_executor_and_logged(client, rt, text, kind):
    r = Chat(client, "t3-cmd").say(text)
    assert ops(r) == [(kind, "REFUSED")]


# ---------------------------------------------------------------- what the books do not hold

NOT_HELD = [
    ("How much tax do we owe?", "en", r"^FLOW's books do not hold tax\..*payments already scheduled", r"reconcile"),
    ("我们要交多少税？", "zh", r"^FLOW 的账目中没有税务数据。.*已排定的付款", r"对账"),
    ("What was our profit this year?", "en", r"^FLOW's books do not hold a profit and loss account\..*EBITDA \(¥90,000\.00\)", None),
    ("哪个客户最赚钱？", "zh", r"^FLOW 的账目中没有各客户的利润。.*谁欠我们钱", r"提前付款"),
    ("How much is each employee paid?", "en", r"^FLOW's books do not hold pay per employee\..*payroll total \(next: ¥340,000\.00, due in 12 days\)",
     r"fund the gap"),
    ("每个员工的工资是多少？", "zh", r"^FLOW 的账目中没有每位员工的工资。.*工资总额（下一笔 ¥340,000\.00，12 天后支付）", None),
    ("How many staff do we have?", "en", r"^FLOW's books do not hold staff or headcount\.", None),
    ("Balance by account, please.", "en", r"^FLOW's books do not hold balances per bank account\..*¥400,000\.00", None),
    ("What's our credit rating?", "en", r"^FLOW's books do not hold a credit rating\..*DSCR", None),
    ("Where is the exchange rate going?", "en", r"^FLOW's books do not hold exchange rates", None),
    ("What is the company worth?", "en", r"^FLOW's books do not hold a company valuation\.", None),
    ("社保都按时交了吗？", "zh", r"^FLOW 的账目中没有社保或福利记录。", None),
    ("按产品看在手订单有多少？", "zh", r"^FLOW 的账目中没有按产品划分的销售或订单。", None),
]


@pytest.mark.parametrize(("text", "lang", "pattern", "not_pointed_at"), NOT_HELD)
def test_a_subject_the_books_do_not_hold_is_refused_with_a_relevant_nearest_read(client, rt, text, lang, pattern, not_pointed_at):
    r = asked(client, rt, text, lang)
    assert r["intent"] == "ASK_BOOKS"
    assert re.search(pattern, r["reply"], re.DOTALL), r["reply"]
    if not_pointed_at:
        assert not re.search(not_pointed_at, r["reply"]), r["reply"]
    if lang == "zh":
        assert not re.search(r"[A-Za-z]{4,}", r["reply"].replace("FLOW", "").replace("EBITDA", "").replace("DSCR", "")), r["reply"]


@pytest.mark.parametrize("text", ["What's our monthly operating profit?", "每月息税折旧前利润是多少？", "Is the machine profitable?",
                                  "What's in the sales pipeline?", "What are the benefits of invoice financing?",
                                  "Is hire purchase cheaper than a lease?"])
def test_what_the_books_do_hold_is_never_refused_as_not_held(text):
    assert lx.not_held(text) is None or not lx.is_question(text)


def test_every_nearest_read_suggested_is_one_the_rules_answer():
    """The example question each refusal or 'cannot yet' reply suggests is read by the rules as the read it names."""
    from app.nl import ask

    class Ctx:
        lang, day = "en", 0

        def state(self):
            return STATE

    for key in ("ebitda", "payroll", "cash", "scheduled", "receivables", "orders", "lender", "ratios", "financing",
                "changes", "alerts", "capex", "waiting", "repay_plan", "cash_forecast"):
        n = ask._nearest(Ctx(), key)  # type: ignore[arg-type]
        for example in (n.example_en, n.example_zh):
            p = parse(example, STATE)
            assert p is not None and p.intent.value in (
                "SHOW_STATUS", "SHOW_RATIOS", "COMPARE_FINANCING", "CHANGES", "SHOW_ALERTS", "CAPEX", "REPAY_FACILITY"), (key, example, p)


# ---------------------------------------------------------------- the narrowed Chinese status cues

@pytest.mark.parametrize(("text", "intent"), [
    ("我们今天账上有多少钱？", "SHOW_STATUS"), ("现在现金余额是多少？", "SHOW_STATUS"), ("现金情况怎么样？", "SHOW_STATUS"),
    ("公司情况怎么样？", "SHOW_STATUS"), ("Is our cash position safe?", "SHOW_STATUS"), ("How much cash do we have today?", "SHOW_STATUS"),
    ("今天我最多能花多少钱而不跌破储备？", "SHOW_STATUS"), ("东莞欠我们多少钱？", "SHOW_STATUS"),
])
def test_the_status_cues_still_read_cash(text, intent):
    p = parse(text, STATE)
    assert p is not None and p.intent.value == intent


@pytest.mark.parametrize("text", ["FLOW的方案要花多少钱？", "我们的发票最多能融多少钱？", "给佛山60天账期要花我们多少钱？", "FLOW一共动了多少钱？",
                                  "本季度增值税情况怎么样？", "库存值多少钱？", "每个银行账户里各有多少钱？", "按账户列一下余额。", "竞争对手情况怎么样？",
                                  "公司值多少钱？", "What's our VAT position this quarter?", "How much money has FLOW moved?"])
def test_the_status_cues_no_longer_catch_other_money_questions(text):
    p = parse(text, STATE)
    assert p is not None and p.intent.value != "SHOW_STATUS", p


# ---------------------------------------------------------------- the answer layer (app.nl.answers, another branch)


@dataclass
class _Reply:
    text_en: str
    text_zh: str
    metric_ids: list[str] = field(default_factory=list)


@pytest.fixture
def answers(monkeypatch):
    """A stand-in `app.nl.answers` that records what it was asked and answers from a table."""
    calls: list[tuple[str, str, object]] = []
    table: dict[str, _Reply | None] = {}

    def answer(question: str, lang: str, ctx: object):
        calls.append((question, lang, ctx))
        return table.get(question)

    mod = types.ModuleType("app.nl.answers")
    mod.answer = answer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.nl.answers", mod)
    return calls, table


def test_the_answer_layer_answers_a_routed_question_in_the_requested_language(client, rt, answers):
    calls, table = answers
    q_en, q_zh = "When is our next loan payment?", "下一笔贷款还款是什么时候？"
    table[q_en] = _Reply("¥45,000.00 on the equipment loan in 30 days.", "设备贷款 ¥45,000.00，30 天后。", ["next_debt_payment"])
    table[q_zh] = _Reply("¥45,000.00 on the equipment loan in 30 days.", "设备贷款 ¥45,000.00，30 天后。", ["next_debt_payment"])
    r = asked(client, rt, q_en, "en")
    assert r["intent"] == "ASK_BOOKS" and r["reply"] == "¥45,000.00 on the equipment loan in 30 days."
    zh = asked(client, rt, q_zh, "zh")
    assert zh["reply"] == "设备贷款 ¥45,000.00，30 天后。"
    assert [(q, lang) for q, lang, _ in calls] == [(q_en, "en"), (q_zh, "zh")]
    ctx = calls[0][2]
    assert hasattr(ctx, "store") and hasattr(ctx, "state") and hasattr(ctx, "day")  # what the read handlers receive


def test_no_answer_falls_back_to_the_honest_reply(client, rt, answers):
    calls, _table = answers
    r = asked(client, rt, "Does the plan breach any covenant?", "en")
    assert calls and r["intent"] == "ASK_BOOKS" and "cannot answer that from the books" in r["reply"]


def test_tier3_and_not_held_never_reach_the_answer_layer(client, rt, answers):
    calls, _ = answers
    asked(client, rt, "Is equity an option?", "en")
    asked(client, rt, "How much tax do we owe?", "en")
    assert calls == []


def test_a_late_payment_question_asks_the_answer_layer_first(client, rt, answers):
    _calls, table = answers
    q = "What if Foshan pays 30 days late?"
    table[q] = _Reply("Your lowest point moves to −¥525,000.00 on day 47.", "最低点变为第 47 天的 −¥525,000.00。")
    r = asked(client, rt, q, "en")
    assert r["intent"] == "WHAT_IF" and r["reply"] == "Your lowest point moves to −¥525,000.00 on day 47."


def test_without_the_answer_layer_the_branch_runs_on_its_own():
    from app.nl import ask

    assert ask.answer_layer() is None or callable(ask.answer_layer())


# ---------------------------------------------------------------- owner only


def test_with_the_agent_key_a_routed_question_reads_nothing(client, rt):
    before = fingerprint(rt)
    r = Chat(client, "ask-agent", owner=False).say("Is equity an option?")
    assert r["operations"] == [] and fingerprint(rt) == before
    assert "sign-in" in r["reply"] or r["intent"] == "ASK_BOOKS"


# ---------------------------------------------------------------- the small fixes


def test_the_chinese_capex_reply_has_no_english_module_sentences(client, rt):
    r = asked(client, rt, "这台设备值得买吗？", "zh")
    assert r["intent"] == "CAPEX"
    body = r["reply"].replace("¥600k die-cutting line", "").replace("DSCR", "")
    assert not re.search(r"[A-Za-z]{3,}", body), r["reply"]
    assert "现金加信用额度：不通过：在 ¥300,000.00 的最低现金储备之上只有 ¥250,000.00 可用" in r["reply"]
    assert "按业主的估计值得投资：按 10.00% 折现，净现值 ¥380,885.77，第 31 个月回本。" in r["reply"]
    assert "建议采用48 个月租赁，7.20%（每月 ¥14,423.49）" in r["reply"]
    en = asked(client, rt, "Is the machine worth buying?", "en")
    assert "Worth doing on the owner's estimate" in en["reply"]  # English unchanged


def test_the_chinese_early_pay_plan_names_the_fallback_in_chinese(client, rt):
    r = Chat(client, "ask-accel-zh").say("让佛山提前付款", lang="zh")
    assert r["intent"] == "ACCELERATE_RECEIPT"
    assert "committed plan" not in r["reply"] and "已承诺方案" in r["reply"], r["reply"]
