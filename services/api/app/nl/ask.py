"""ASK_BOOKS: an owner's question about the books, answered read-only (the question gate in app/nl/rules.py routes it here).

Nothing here proposes a plan, compiles an offer, queues or executes an operation, or writes to the operations log or the
security log: every branch reads the store and the books and writes words. The one exception is a Tier-3 request put as a
question ("sign a personal guarantee?", "should we pledge the equipment?"): it goes to the executor like the same words
without the mark, so it is refused, logged and raises its security event, for every caller (ASK-1;
lexicon.tier3_is_information). The server writes all of them, in English and
Chinese. Owner only: with the agent key a question gets the sign-in reply (and a question the old rules did not read at
all gets exactly the reply it got before).

The order of the answer:
  1. A Tier-3 subject asked about ("Is equity an option?", "Did anyone try to change our limits?"): what FLOW may never
     do, as information; an attempt is read from the operations log and the security log. Nothing is requested. This is
     for the owner and for a question that only asks for information; a request put as a question, or any question from
     another caller, is refused by the executor and logged (see `tier3_request`).
  2. A subject the books do not hold (tax, VAT, profit, staff, inventory, competitors, a valuation ...): "FLOW's books do
     not hold {thing}." and the nearest thing FLOW can show, chosen by the subject.
  3. The read-only answer layer, `app.nl.answers.answer(question, lang, ctx)`, when it is installed and answers.
  4. Otherwise the existing read that answers the topic right (the financing comparison for the gap and the plan's cost,
     the cash status for why cash is short, the late-payment read, what is waiting), or the nearest-capability reply.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.models import FlowKind
from app.domain.money import fmt_yuan
from app.financial import EngineError
from app.nl import lexicon as lx
from app.nl.context import NlContext
from app.nl.models import Intent, Parsed, Slots
from app.nl.pipeline import t
from app.nl.turn import Turn

AnswerFn = Callable[[str, str, Any], Any]


# ---------------------------------------------------------------- the answer layer (app.nl.answers, another branch)


def answer_layer() -> AnswerFn | None:
    """`app.nl.answers.answer`, or None while that package is not installed (this branch then runs on its own)."""
    try:
        from app.nl.answers import answer  # type: ignore[import-not-found,unused-ignore]
    except ModuleNotFoundError as e:
        if e.name and (e.name == "app.nl.answers" or "app.nl.answers".startswith(e.name)):
            return None
        raise  # the package is there but broken: say so, never answer around it
    return answer  # type: ignore[no-any-return,unused-ignore]


def _reply_text(reply: Any, lang: str) -> str | None:
    """The reply's text in the requested language: `text_<lang>`, else `text` (an object or a mapping)."""
    for key in (f"text_{lang}", "text"):
        v = reply.get(key) if isinstance(reply, dict) else getattr(reply, key, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _metric_ids(reply: Any) -> list[str]:
    v = reply.get("metric_ids") if isinstance(reply, dict) else getattr(reply, "metric_ids", None)
    return [str(x) for x in v] if isinstance(v, list | tuple) else []


# ---------------------------------------------------------------- the nearest thing FLOW can show


@dataclass(frozen=True)
class Nearest:
    en: str
    zh: str
    example_en: str
    example_zh: str


def _nearest(ctx: NlContext, key: str) -> Nearest:
    """A read FLOW answers today that is close to what was asked, with a question that reaches it."""
    state = ctx.state()
    if key == "ebitda":
        e = fmt_yuan(state.monthly_ebitda_fen)
        return Nearest(f"your monthly EBITDA ({e}) and the covenant ratios built on it", f"您的月度 EBITDA（{e}）及据此计算的契约指标",
                       "What is our DSCR?", "偿债覆盖率是多少？")
    if key == "payroll":
        nxt = min((f for f in state.flows if f.kind == FlowKind.PAYROLL and f.day >= ctx.day), key=lambda f: f.day, default=None)
        if nxt is not None:
            n = nxt.day - ctx.day
            en_when = "today" if n == 0 else f"in {n} day{'' if n == 1 else 's'}"
            zh_when = "今天" if n == 0 else f"{n} 天后"
            amt = fmt_yuan(abs(nxt.amount_fen))
            return Nearest(f"the payroll total (next: {amt}, due {en_when})", f"工资总额（下一笔 {amt}，{zh_when}支付）",
                           "How are we doing?", "现金状况怎么样？")
        return Nearest("the payroll total in your forecast", "预测中的工资总额", "How are we doing?", "现金状况怎么样？")
    if key == "cash":
        c = fmt_yuan(state.cash_fen)
        return Nearest(f"one cash total ({c} today)", f"一个现金总额（今天 {c}）", "How are we doing?", "现金状况怎么样？")
    if key == "scheduled":
        return Nearest("the payments already scheduled in your forecast", "预测中已排定的付款", "How are we doing?", "现金状况怎么样？")
    if key == "receivables":
        return Nearest("what each customer owes you and when it is due", "每位客户欠您多少、何时到期", "Who owes us money?", "谁欠我们钱？")
    if key == "orders":
        return Nearest("what each customer owes you and the invoicing ahead", "每位客户的欠款和今后的开票",
                       "Who owes us money?", "谁欠我们钱？")
    if key == "lender":
        return Nearest("the covenant ratios a lender reads (DSCR and leverage)", "贷款方查看的契约指标（DSCR 和杠杆）",
                       "What is our DSCR?", "偿债覆盖率是多少？")
    if key == "ratios":
        return Nearest("the covenant ratios on today's books", "按今天账目计算的契约指标", "Are we inside our covenants?", "我们满足契约吗？")
    if key == "financing":
        return Nearest("the financing FLOW may use, priced for the gap", "FLOW 可用的融资来源及其针对缺口的成本",
                       "Which financing option is cheapest?", "哪种融资最便宜？")
    if key == "changes":
        return Nearest("what changed today in the operations log", "今天操作日志中的变化", "What changed today?", "今天有什么变化？")
    if key == "alerts":
        return Nearest("what needs you (the alerts, a mandate about to expire included)", "需要您处理的事项（提醒，包括即将到期的授权）",
                       "Any alerts?", "有什么提醒？")
    if key == "capex":
        return Nearest("the equipment purchase case FLOW holds", "FLOW 持有的设备购置方案", "Should I buy the machine?", "买这台设备划算吗？")
    if key == "repay_plan":
        return Nearest("a repayment plan for the drawn line, which runs only on your go-ahead", "针对已提款额度的还款方案（需您确认后才执行）",
                       "repay the credit line", "偿还授信额度")
    if key == "waiting":
        return Nearest("what is waiting on you or on a buyer", "正在等您或等买家处理的事项", "What are we waiting for?", "我们在等什么？")
    return Nearest("your cash position and forecast", "您的现金状况和预测", "How are we doing?", "现金状况怎么样？")


def _nearest_line(ctx: NlContext, n: Nearest) -> str:
    return t(ctx, f"The nearest I can show is {n.en}: ask \"{n.example_en}\".",
             f"我能提供的最接近的是{n.zh}，您可以问：“{n.example_zh}”。")


# ---------------------------------------------------------------- 2. what the books do not hold

# key -> (the thing in English, in Chinese, the nearest read, a hint or "")
NOT_HELD_WORDS: dict[str, tuple[str, str, str, tuple[str, str]]] = {
    "vat": ("VAT", "增值税数据", "scheduled", ("", "")),
    "tax": ("tax", "税务数据", "scheduled", (" To have a tax payment counted, enter it as a bill.", "若要计入一笔税款，请把它作为账单录入。")),
    "customer_profit": ("profit by customer", "各客户的利润", "receivables", ("", "")),
    "margin": ("margins", "毛利数据", "ebitda", ("", "")),
    "profit": ("a profit and loss account", "利润表", "ebitda", ("", "")),
    "revenue": ("revenue or sales history", "营收或销售历史", "orders", ("", "")),
    "inventory": ("inventory", "库存数据", "cash_forecast", ("", "")),
    "pay_per_person": ("pay per employee", "每位员工的工资", "payroll", ("", "")),
    "staff": ("staff or headcount", "员工或人数数据", "payroll", ("", "")),
    "accounts": ("balances per bank account", "各银行账户的余额", "cash", ("", "")),
    "payables": ("a payables ledger", "应付账款明细", "scheduled", ("", "")),
    "credit_rating": ("a credit rating", "信用评级", "lender", ("", "")),
    "market": ("market or competitor data", "市场或竞争对手数据", "cash_forecast", ("", "")),
    "fx": ("exchange rates or foreign-currency positions", "汇率或外币头寸", "cash_forecast", ("", "")),
    "valuation": ("a company valuation", "公司估值", "ebitda", ("", "")),
    "past_spend": ("spending before today", "今天之前的支出记录", "scheduled", ("", "")),
    "social_insurance": ("social insurance or benefit records", "社保或福利记录", "payroll", ("", "")),
    "products": ("sales or orders by product", "按产品划分的销售或订单", "orders", ("", "")),
}


def not_held(ctx: NlContext, key: str) -> Turn:
    thing_en, thing_zh, near, (hint_en, hint_zh) = NOT_HELD_WORDS[key]
    reply = (t(ctx, f"FLOW's books do not hold {thing_en}.", f"FLOW 的账目中没有{thing_zh}。")
             + ("" if ctx.lang == "zh" else " ") + _nearest_line(ctx, _nearest(ctx, near)) + t(ctx, hint_en, hint_zh))
    return Turn(intent=Intent.ASK_BOOKS, reply=reply, facts={"ask": {"not_held": key}})


# ---------------------------------------------------------------- 1. a Tier-3 subject asked about

_TIER3_WORDS = {
    "SIGN_PERSONAL_GUARANTEE": ("signing a personal guarantee", "签署个人担保", "to have FLOW sign a personal guarantee", "让 FLOW 签署个人担保"),
    "PLEDGE_COLLATERAL": ("pledging collateral", "抵押或质押资产", "to have FLOW pledge collateral", "让 FLOW 抵押或质押资产"),
    "ISSUE_EQUITY": ("issuing equity", "发行股权", "to have FLOW issue equity", "让 FLOW 发行股权"),
    "CHANGE_MANDATE": ("changing your mandate or its limits", "修改您的授权或限额", "to change your mandate or its limits",
                       "修改您的授权或限额"),
}


def tier3_info(ctx: NlContext, kind: str, text: str) -> Turn:
    """A question that only names a Tier-3 subject. Nothing is sent to the executor, so nothing is refused or logged: it
    is answered from the rules and, for an attempt, from the operations log and the security log."""
    what_en, what_zh, tried_en, tried_zh = _TIER3_WORDS[kind]
    if lx.ASK_ATTEMPT.search(text):
        tries = [e for e in ctx.store.operations() if e.kind == kind]
        events = len(ctx.store.security_events())
        ev_en = ("there is no security event on record" if events == 0
                 else f"{events} security event{'' if events == 1 else 's'} {'is' if events == 1 else 'are'} on record")
        ev_zh = "也没有安全事件记录" if events == 0 else f"安全日志中有 {events} 条安全事件"
        if not tries:
            reply = t(ctx, f"No. Nobody has tried {tried_en}: the operations log holds no such request, and {ev_en}.",
                      f"没有。没有人尝试{tried_zh}：操作日志中没有这类请求，{ev_zh}。")
        else:
            n = len(tries)
            reply = t(ctx, f"Yes: {n} request{'' if n == 1 else 's'} {tried_en} {'was' if n == 1 else 'were'} refused and logged, "
                           f"and nothing changed; {ev_en}.",
                      f"有：{n} 次{tried_zh}的请求已被拒绝并记录，没有任何改变；{ev_zh}。")
        return Turn(intent=Intent.ASK_BOOKS, reply=reply, facts={"ask": {"tier3": kind, "attempts": len(tries)}})
    lines = [t(ctx, f"{what_en[:1].upper()}{what_en[1:]} is outside what FLOW may do: it is a Tier-3 action, which FLOW never "
                    f"takes, whoever asks. Only you can decide it, outside FLOW. Nothing was requested or logged.",
               f"{what_zh}不在 FLOW 的权限之内：这是三级操作，无论谁提出，FLOW 都不会执行，只能由您在 FLOW 之外自行决定。"
               f"本次没有提交任何请求，也没有记录。")]
    lines += _tier3_guidance(ctx, kind)
    return Turn(intent=Intent.ASK_BOOKS, reply=("" if ctx.lang == "zh" else " ").join(lines), facts={"ask": {"tier3": kind}})


def _tier3_guidance(ctx: NlContext, kind: str) -> list[str]:
    """What the owner can look at instead of the Tier-3 action (the funding menu's equity row, the nearest financing read)."""
    lines: list[str] = []
    if kind == "ISSUE_EQUITY":
        ref = next((f for f in ctx.state().facilities if f.kind.value == "EQUITY"), None)
        if ref is not None:
            lines.append(t(ctx, f"{ref.name} is on the funding menu for comparison only ({ref.lead_time_days} days to cash).",
                           f"“{ref.name}”仅作为参考列在融资菜单中（约 {ref.lead_time_days} 天到账）。"))
    if kind != "CHANGE_MANDATE":
        lines.append(_nearest_line(ctx, _nearest(ctx, "financing")))
    return lines


def tier3_request(ctx: NlContext, kind: str, slots: Slots) -> Turn:
    """A Tier-3 subject in a question that is not plainly information: a request put as a question ("sign a personal
    guarantee?", "should we pledge the equipment?", 要不要签个人担保？), or any question from a caller who is not the owner.
    It is sent to the executor exactly as the imperative is (service.refuse_tier3), so it is REFUSED, written to the operations
    log and raises its TIER3 security event. The owner's reply then also says what to look at instead (the question part);
    any other caller gets the plain refusal."""
    from app.nl.service import refuse_tier3

    typed = slots.model_copy(update={"tier3": kind, "execute_now": False})
    tail: tuple[str, str] | None = None
    if ctx.owner_authenticated:
        extra = _tier3_guidance(ctx, kind)
        tail = (" ".join(["Only you can decide it, outside FLOW.", *extra]), "只能由您在 FLOW 之外自行决定。" + "".join(extra))
    return refuse_tier3(ctx, typed, tail)


# ---------------------------------------------------------------- 4. the fallback, by topic

_NEAREST_FOR = {"debt": "lender", "plan_covenants": "ratios", "money_moved": "changes", "mandate": "alerts",
                "capex_contracts": "capex", "receivable_days": "receivables", "deals_sent": "changes", "break_even": "financing",
                "accelerate": "financing", "negotiate": "waiting", "deals": "waiting", "record": "cash_forecast",
                "repay": "repay_plan", "fund": "financing", "plan_cost": "financing", "capacity": "financing",
                "late_payment": "cash_forecast", "why_short": "cash_forecast"}


def cannot_yet(ctx: NlContext, topic: str) -> Turn:
    """An answerable question that no read in chat answers yet: said plainly, with the nearest read. Nothing changes."""
    near = _nearest(ctx, _NEAREST_FOR.get(topic, "cash_forecast"))
    reply = t(ctx, "I cannot answer that from the books in chat yet, and I have not changed anything. ",
              "我暂时还不能在对话中根据账目回答这个问题，也没有做任何更改。") + _nearest_line(ctx, near)
    return Turn(intent=Intent.ASK_BOOKS, reply=reply, facts={"ask": {"topic": topic, "answered": False}})


def break_even(ctx: NlContext, slots: Slots) -> Turn | None:
    """The early-payment break-even the early-pay plan is priced on (`funding.break_even_discount`), as an answer: with a
    rate asked about, whether it is above it. None when no committed source can price early payment."""
    from fractions import Fraction

    from app.domain.money import BP_DENOM, fmt_pct
    from app.funding import NoPermanentSourceError, break_even_discount

    try:
        be, _ = break_even_discount(ctx.state(), ctx.mandate())
    except NoPermanentSourceError:
        return None
    be_s = fmt_pct(be.value)
    if slots.rate_bp is None:
        reply = t(ctx, f"The break-even early-payment discount is {be_s}: below it, being paid early costs less than "
                       f"invoice financing; above it, it costs more. Nothing was proposed or sent.",
                  f"提前付款折扣的盈亏平衡点是 {be_s}：低于它，提前收款比发票融资便宜；高于它则更贵。没有提出或发送任何内容。")
        return Turn(intent=Intent.ASK_BOOKS, reply=reply, facts={"ask": {"topic": "break_even"}})
    r = fmt_pct(Fraction(slots.rate_bp, BP_DENOM))
    cap = ctx.mandate().max_immediate_discount_bp
    if Fraction(slots.rate_bp, BP_DENOM) > be.value:
        reply = t(ctx, f"No: {r} is above the {be_s} break-even, so early payment at that discount costs more than invoice "
                       f"financing. Nothing was proposed or sent.",
                  f"不划算：{r} 高于 {be_s} 的盈亏平衡点，按这个折扣提前收款比发票融资更贵。没有提出或发送任何内容。")
    elif cap is not None and slots.rate_bp > cap:
        c = fmt_pct(Fraction(cap, BP_DENOM))
        reply = t(ctx, f"{r} is below the {be_s} break-even, but above your {c} discount limit, so it needs your approval. "
                       f"Nothing was proposed or sent.",
                  f"{r} 低于 {be_s} 的盈亏平衡点，但高于您 {c} 的折扣上限，因此需要您批准。没有提出或发送任何内容。")
    else:
        reply = t(ctx, f"Yes on cost: {r} is below the {be_s} break-even, so early payment at that discount costs less than "
                       f"invoice financing. Nothing was proposed or sent.",
                  f"从成本看划算：{r} 低于 {be_s} 的盈亏平衡点，按这个折扣提前收款比发票融资便宜。没有提出或发送任何内容。")
    return Turn(intent=Intent.ASK_BOOKS, reply=reply, facts={"ask": {"topic": "break_even", "rate_bp": slots.rate_bp}})


def _fallback(ctx: NlContext, topic: str, slots: Slots, text: str) -> Turn:
    """The existing read that answers the topic right, else the plain 'cannot yet' with the nearest read."""
    from app.nl import capabilities as cap
    from app.nl import reads
    from app.nl.funding import repay, status

    try:
        if topic in ("fund", "plan_cost", "capacity") and slots.amount_fen is None:
            return cap.compare_financing(ctx)  # the gap, the committed plan and its cost; it runs nothing
        if topic in ("break_even", "accelerate") and (be := break_even(ctx, slots)) is not None:
            return be  # the break-even itself, or whether the rate asked about is above it
        if topic == "why_short":
            ctx.scope_read = "company"
            return status(ctx)  # where cash falls short and by how much
        if topic == "late_payment" and ctx.reads is not None:
            return reads.late_payment(ctx)  # what the payment means for the forecast; nothing is compiled
        if topic in ("deals", "negotiate") and ctx.reads is not None:
            return reads.waiting(ctx)  # what is open, with the buyer or with you
        if topic == "repay" and not any(f.drawn_fen > 0 for f in ctx.state().facilities):
            said = repay(ctx, slots, execute=False)  # nothing is drawn: its read-only sentence, never a plan
            said.intent = Intent.ASK_BOOKS  # a question's answer is never labelled as the action it asked about
            return said
    except EngineError:
        pass
    if topic == "books":
        return _old_reply(ctx, slots, text)
    return cannot_yet(ctx, topic)


def _old_reply(ctx: NlContext, slots: Slots, text: str) -> Turn:
    """The reply the question got before it was routed here: the out-of-scope reply (one way forward, or the closest
    capability)."""
    from app.nl import capabilities as cap
    from app.nl import reads
    from app.nl.service import CAPABILITIES_EN, CAPABILITIES_ZH

    if ctx.owner_authenticated and lx.READ_QUESTION.search(text.strip()) and cap.closest_capability(text) is None:
        return reads.recovery(ctx)
    return cap.nearest_reply(ctx, text, CAPABILITIES_EN, CAPABILITIES_ZH)


# ---------------------------------------------------------------- the handler


def layer_reply(ctx: NlContext, question: str) -> tuple[str, list[str]] | None:
    """The answer layer's reply (its text in the turn's language, its metric ids), or None when it is not installed or
    has no answer."""
    fn = answer_layer()
    if fn is None:
        return None
    try:
        got = fn(question, ctx.lang, ctx)
    except EngineError:
        return None
    text = _reply_text(got, ctx.lang) if got is not None else None
    return (text, _metric_ids(got)) if text else None


def topic_of(p: Parsed) -> str:
    return next((m.split(":", 1)[1] for m in p.matched if m.startswith("ask:")), "books")


# The topics that are about doing something (a draw, a repayment, early payment, a counter); an amount in the question counts too.
ACTION_TOPICS = frozenset({"fund", "repay", "accelerate", "negotiate", "debt", "record"})


def pending_reminder(ctx: NlContext, p: Parsed) -> tuple[str, str] | None:
    """ASK-2. A question about an action asked while a plan waits for "go ahead": the reply must say that the earlier plan is
    still waiting, what it does and what it costs, and that "go ahead" runs that plan and nothing the question named.
    Chosen: the plan is KEPT (a question never cancels anything, so the owner can still go on with it) and the reply says
    so; clearing it would be a change the owner did not ask for."""
    pending = ctx.session.pending_plan
    if pending is None or not ctx.owner_authenticated:
        return None
    if topic_of(p) not in ACTION_TOPICS and p.slots.amount_fen is None:
        return None
    steps = [s.description for s in pending.steps if s.status == "PROPOSED"] or [s.description for s in pending.steps]
    what = "; ".join(d.rstrip(".") for d in steps) or pending.intent.value
    cost_en = f" (cost {fmt_yuan(pending.quoted_cost_fen)})" if pending.quoted_cost_fen is not None else ""
    cost_zh = f"（成本 {fmt_yuan(pending.quoted_cost_fen)}）" if pending.quoted_cost_fen is not None else ""
    amount = p.slots.amount_fen
    asked_en = f"the {fmt_yuan(amount)} you just asked about" if amount is not None else "what you just asked about"
    asked_zh = f"您刚才询问的 {fmt_yuan(amount)}" if amount is not None else "您刚才询问的内容"
    return (("Your earlier plan is still waiting and nothing has changed: "
             f"{what}{cost_en}. Reply 'go ahead' and that plan runs, not {asked_en}; reply 'cancel' to drop it."),
            f"您之前的方案仍在等待，没有任何变化：{what}{cost_zh}。回复“执行”将运行该方案，而不是{asked_zh}；回复“取消”可放弃。")


def ask_books(ctx: NlContext, p: Parsed, text: str) -> Turn:
    turn = _ask_books(ctx, p, text)
    if turn.intent == Intent.ASK_BOOKS and (note := pending_reminder(ctx, p)) is not None:
        turn.reply = f"{turn.reply}{'' if ctx.lang == 'zh' else ' '}{t(ctx, *note)}"
        turn.awaiting = True  # the earlier plan is still waiting for its go-ahead
    return turn


def _ask_books(ctx: NlContext, p: Parsed, text: str) -> Turn:
    topic = topic_of(p)
    slots = p.slots
    question = slots.question or text
    if topic.startswith("tier3:"):
        kind = topic.split(":", 1)[1]
        if not ctx.owner_authenticated or not lx.tier3_is_information(question):
            return tier3_request(ctx, kind, slots)
    if not ctx.owner_authenticated:
        if topic == "books":
            return _old_reply(ctx, slots, text)  # the agent key gets exactly what it got before
        from app.nl import capabilities as cap

        return cap.needs_sign_in(ctx, Intent.ASK_BOOKS)  # nothing is read, disclosed or logged
    if topic.startswith("tier3:"):
        return tier3_info(ctx, topic.split(":", 1)[1], question)
    if topic.startswith("not_held:"):
        return not_held(ctx, topic.split(":", 1)[1])
    if (got := layer_reply(ctx, question)) is not None:
        return Turn(intent=Intent.ASK_BOOKS, reply=got[0], facts={"ask": {"topic": topic, "metric_ids": got[1]}})
    return _fallback(ctx, topic, slots, text)
