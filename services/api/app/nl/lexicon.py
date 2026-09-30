"""Deterministic lexicon (en + zh) for owner intents, and exact parsers for money, rates and days.

Amounts come out as integer fen and rates as integer bp, parsed with Decimal; anything with sub-fen
or sub-bp precision is ignored rather than rounded (INVARIANT 9).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.compiler.parsing import rx
from app.domain.models import FinancialState


def norm(text: str) -> str:
    """NFKC (full-width digits and ％ become ASCII) and lower case."""
    return unicodedata.normalize("NFKC", text).lower()


def detect_lang(text: str) -> str:
    cjk = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "zh" if cjk > 0 and cjk * 2 >= latin else "en"


def _re(*parts: str) -> re.Pattern[str]:
    """Alternatives, case-insensitive, with CJK-safe word boundaries (EV-08: "批准APR-000003")."""
    return rx("|".join(parts), re.IGNORECASE)


# ---------------------------------------------------------------- intent cues

CORRECTION = _re(r"\bactually\b", r"\binstead\b", r"\bmake (?:it|that)\b", r"\bchange (?:it|that|the rate) to\b",
                 r"\bswitch to\b", r"\brather\b", r"改成", r"改为", r"换成", r"其实", r"改用", r"不如用")
CONFIRM = _re(r"^\s*(?:yes|yep|yeah|ok(?:ay)?|sure|go ahead|proceed|confirm(?:ed)?|do it|lgtm|execute|run it)\b",
              r"\bgo ahead\b", r"\bapprove[ds]?\b", r"\bconfirm\b", r"批准", r"同意", r"确认", r"^\s*执行", r"^\s*好的?",
              r"就这么办", r"可以执行")
DECLINE = _re(r"^\s*(?:no|nope|cancel|stop|abort|don'?t|do not)\b", r"\breject\b", r"\bdecline\b", r"\bdeny\b",
              r"\bcancel\b", r"驳回", r"拒绝", r"取消", r"^\s*不要", r"算了")
EXECUTE_NOW = _re(r"\bnow\b", r"\bright away\b", r"\bimmediately\b", r"\bgo ahead and\b", r"\band do it\b",
                  r"立即", r"马上", r"现在就", r"立刻")
EXPLAIN = _re(r"\bwhy\b", r"\bexplain\b", r"\bhow come\b", r"\breasons?\b", r"为什么", r"为何", r"解释", r"原因", r"依据")
WHAT_IF = _re(r"\bwhat if\b", r"\bwhat would happen\b", r"\bwhat happens\b", r"\bsuppose\b", r"\bhypothetical",
              r"\bwhat (?:would|will|does) (?:it|that) (?:do|mean|look like|cost)\b",
              r"\bhow (?:would|will|does)\b.{0,50}\b(?:affect|change|impact|hit)\b", r"\bimpact of\b",
              r"如果", r"假如", r"假设", r"要是", r"会怎样", r"会怎么样", r"会如何", r"有什么影响", r"影响多大")
STATUS = _re(r"\bstatus\b", r"\bposition\b", r"\bhow are we\b", r"\bhow'?s (?:our |the )?cash\b", r"\bheadroom\b",
             r"\bdashboard\b", r"\boverview\b", r"\bcash balance\b", r"\bwhere do we stand\b", r"现状", r"状况", r"状态",
             r"现金(?:余额|情况)", r"余额", r"概况", r"情况怎么样",
             r"\bhow much (?:cash|money)\b", r"\bcash (?:on hand|do we have|position)\b", r"\bbank balance\b",
             r"\bcovenants?\b.{0,30}\b(?:look|looking|status|headroom|ok|okay|safe|risk)\b",
             r"账上", r"多少(?:钱|现金)", r"还有多少", r"(?:契约|财务指标).{0,10}(?:怎么样|情况|风险)",
             # forecasts and receivables: "show me the 13 week forecast", "list the open receivables", 现金流预测
             r"\bforecast\b", r"\b\d{1,2}[- ]?week\b", r"\bcash ?flows?\b", r"\breceivables?\b", r"\bopen invoices\b",
             r"\baging\b", r"\bageing\b", r"\bwho owes us\b", r"\bprojection\b",
             r"现金流", r"预测", r"应收(?:账款)?", r"未(?:收|回)(?:款|回)", r"谁欠(?:我们)?钱", r"账龄")
# A question about the position ("are we close to breaching a covenant?", "会不会跌破储备线？"): it asks, so
# it is SHOW_STATUS even when it names the reserve or a shortfall (checked before FUND).
STATUS_QUESTION = _re(
    r"^\s*(?:are|is|will|would|could|do|does|am)\s+(?:we|there|it|our|the)\b.{0,60}"
    r"\b(?:breach\w*|break\w*|below|under|short|enough|dip\w*|fall\w*|drop\w*|covenants?|reserve|floor|minimum|gap)\b",
    r"\b(?:any|close to|near|at risk of)\s+(?:a\s+|any\s+)?(?:covenant|breach)",
    r"会不会.{0,12}(?:跌破|低于|违反|突破|违约|缺钱|不够)", r"(?:有没有|是否).{0,10}(?:违约|违反|跌破|缺口)")
REPAY = _re(r"\brepay", r"\bpay (?:back|down|off)\b", r"\bpay (?:the |our )?(?:credit |bank )?line (?:back|down|off)\b",
            r"\bclear (?:the |our )?(?:balance on the |outstanding balance on the |outstanding )?(?:credit |bank )?line\b",
            r"\bsettle (?:the |our )?(?:credit |bank )?line\b", r"还款", r"偿还", r"还清", r"归还",
            r"(?:授信|信用|银行|额度).{0,8}还(?:掉|了|上|回去)", r"把.{0,12}还(?:掉|了|上|回去)")
FUND = _re(r"\bfund (?:the |it\b|this\b|that\b|our )", r"\bfund it\b", r"\bcover (?:the |our )?(?:cash )?(?:gap|shortfall)",
           r"\bclose (?:the )?gap\b", r"\bfunding gap\b", r"\bcash gap\b", r"\bshortfall\b", r"\bbridge (?:the )?gap\b",
           r"\bdraw\b", r"补(?:足|上)?(?:资金)?缺口", r"资金缺口", r"填补", r"提款", r"支取", r"动用.{0,6}额度",
           r"\bcover (?:the |our |this |that )?\w+ (?:gap|shortfall)\b",
           r"缺口(?:给)?补(?:上|足|齐|平)", r"补(?:上|足|齐|平)?.{0,6}缺口",
           # "从授信额度里提10万出来", "在额度上借20万"
           r"(?:额度|授信|信用额度|贷款额度)(?:里|中|上)?.{0,4}(?:提|借|拿|取|支)(?:款|现|用|出)?.{0,3}(?:\d|[一二两三四五六七八九十])",
           r"(?:提|借|拿|取)(?:款|现)?\s*(?:\d[\d,.]*|[一二两三四五六七八九十]+)\s*(?:万|千|元|块).{0,6}(?:出来|用|周转)")
# A request to look for options rather than to act ("find me the cheapest way to cover the gap",
# 帮我找最便宜的方式补上): FUND_GAP proposes the plan and waits for "go ahead", in either language.
FUND_EXPLORE = _re(
    r"\b(?:find|look for|figure out|work out|suggest|recommend|propose|show me|what(?:'s| is| are)|which is)\b.{0,40}"
    r"\b(?:way|ways|option|options|cheapest|best|plan|route)\b",
    r"\bhow (?:can|could|should|do|would) we\b", r"\bany (?:way|option)s?\b",
    r"(?:找|想|看看|推荐|建议|有没有|有什么|怎么|如何|哪种|哪个).{0,12}(?:办法|方式|方法|方案|途径|最便宜|最划算|最省)",
    r"怎么补|如何补|怎么解决|如何解决")
# Needs described, not the funding asked for ("payroll is due and we are short", 工资不够): FUND_GAP, but the plan is
# proposed and waits for "go ahead" instead of executing on a reading this loose.
FUND_SOFT = _re(
           r"\b(?:payroll|wages|salaries|rent|suppliers?|bills)\b.{0,50}\b(?:short|can'?t cover|cannot cover|not enough|tight|cover (?:it|them))\b",
           r"\bcover (?:the )?(?:payroll|wages|salaries|rent|bills)\b", r"\b(?:we'?re|we are|running)\s+(?:a bit\s+)?(?:short|low|tight)\b",
           r"\bshort (?:of|on) (?:cash|money|funds)\b", r"\btop (?:up|off) (?:the )?(?:cash|account|balance|bank)\b",
           r"\b(?:don'?t|doesn'?t|do not|never|won'?t)\s+(?:let\s+(?:cash|us|the balance)\s+)?(?:dip|fall|drop|go)\w*\s+(?:below|under)\b",
           r"\bstay (?:above|over) (?:the )?(?:reserve|floor|minimum)\b", r"\baccount is (?:thin|low|tight)\b",
           r"(?:工资|薪水|房租|货款|账单).{0,12}(?:不够|缺|付不起|发不出)", r"(?:钱|资金|现金)不够", r"缺钱", r"安排(?:一下)?融资",
           r"找(?:点)?钱", r"借(?:点)?钱", r"周转", r"(?:别|不要|不能)(?:让)?.{0,6}(?:跌破|低于)(?:储备|底线|最低)")
ACCELERATE = _re(r"\b(?:get|be|getting) paid (?:early|sooner|faster)\b", r"\b(?:get|have)\b.{0,40}\bpaid (?:early|sooner|faster)\b",
                 r"\bcollect\b.{0,50}\b(?:sooner|earlier|early|faster|quicker)\b", r"\bearly[- ]pay\b",
                 r"\b(?:pay|paid|settle|settled|clear|cleared)\b(?!.{0,50}\b(?:line|loan|facility|debt|bank|back|off)\b)"
                 r".{0,40}\b(?:sooner|earlier|faster|quicker)\b",
                 r"\b(?:get|ask|make)\b.{0,30}\bto pay (?:early|sooner|earlier)\b",
                 r"早点(?:付|给钱|打款)", r"提前(?:付|打款|给钱)", r"早付", r"尽快(?:付|打款|收)",
                 r"\b(?:money|cash|payment|invoice)\b.{0,20}\bin (?:sooner|earlier|faster)\b", r"\bearly (?:payment|settlement)\b",
                 r"\bcollect (?:early|sooner)\b", r"\baccelerate\b", r"\bspeed up (?:the )?(?:payment|collection|receipt)",
                 r"提前(?:收款|回款|结算)", r"早点(?:收|回)款", r"加快回款", r"尽快收回")
NEGOTIATE = _re(r"\bnegotiat", r"\bsend (?:the |our |both )?counters?\b", r"\bcounter[- ]?offer", r"\bhaggle\b",
                r"\bbargain\b", r"谈判", r"还价", r"议价", r"反报价", r"发(?:送)?反要约",
                r"^\s*counter\b", r"\bcounter (?:them|him|her|the buyer|it|at|with)\b",
                r"谈一下", r"谈谈", r"去谈", r"跟.{1,10}谈", r"砍价")
# An explicit negotiating verb outranks an early-payment cue: "跟佛山谈一下，提前付款最多给0.7%" negotiates.
NEGOTIATE_VERB = _re(r"\bnegotiat", r"^\s*counter\b", r"\bcounter (?:them|him|her|the buyer|it|at|with)\b",
                     r"谈判", r"谈一下", r"谈谈", r"去谈", r"跟.{1,10}谈", r"还价", r"议价", r"砍价")
EVALUATE = _re(r"\bevaluate\b", r"\bassess\b", r"\bcheck (?:this|the|that|offer)\b", r"\breview (?:this|the|that)\b",
               r"\banaly[sz]e\b", r"\bis (?:this|it) (?:a )?good\b", r"\bshould (?:we|i) accept\b", r"\bbuyer (?:says|wrote|sent)\b",
               r"评估", r"审核", r"分析", r"看看这", r"要不要接受", r"能不能接受", r"买家说")
AMBIGUOUS = _re(r"\b(?:help|sort out|do something about|handle|deal with|fix)\b.{0,30}\b(?:cash|money|finances?|liquidity)\b",
                r"处理一下(?:资金|现金|钱)", r"帮我(?:管|弄|搞)一下(?:钱|资金)", r"资金怎么办", r"钱的问题",
                # vague delegation with no task named: one clarifying question, not the capability list (EV-09)
                r"^\s*(?:can|could|would|will) you\s+(?:please\s+|just\s+)?(?:handle|sort|deal with|take care of|fix|manage|look after|do)"
                r"\s+(?:it|this|that|things|everything|something)\b",
                r"^\s*(?:please\s+|just\s+)?(?:handle|sort|sort out|deal with|take care of|fix|manage)\s+(?:it|this|that|things|everything)\b",
                r"\b(?:do|does) (?:the |what(?:ever)? (?:is|'s) )?(?:usual|normal|same as (?:always|usual|before))\b",
                r"\bthe (?:usual|normal thing|normal stuff)\b", r"\byou decide\b", r"\byour call\b", r"\bup to you\b",
                r"\bwhatever you think\b", r"看着办", r"你(?:来)?决定", r"你看着", r"帮我处理", r"处理一下", r"帮我搞定", r"^\s*搞定",
                r"老样子", r"照旧", r"老规矩", r"你来定", r"你定吧",
                # a task named only by a pointer: "do the thing with Foshan", "make it cheaper", 那个单子怎么说
                r"\bdo the (?:thing|needful|stuff)\b", r"\bmake (?:it|this|that) (?:cheaper|better|work|happen|right)\b",
                r"\b(?:sort|figure) (?:it|this|that) out\b", r"那个(?:单子|事情?|东西)", r"那件事", r"那笔(?:单|生意)?怎么")
CAPEX = _re(r"\bmachine\b", r"\bequipment\b", r"\bcapex\b", r"设备", r"机器", r"购置")
ZERO_FORWARD = _re(r"without giving (?:anything|something) away", r"\bnothing away\b", r"\bno (?:forward )?concessions?\b",
                   r"\b(?:don'?t|do not|never|without)\s+giv(?:e|ing)\s+(?:\w+\s+){0,2}?away\b",
                   r"\bnothing (?:in return|forward|else)\b", r"不要?(?:给|做)(?:任何)?(?:让步|让利|优惠)", r"别(?:给|让)(?:任何)?(?:让步|让利|优惠)",
                   r"\bzero (?:forward )?concessions?\b", r"不(?:做|给)(?:任何)?让步", r"不让利", r"不给任何(?:优惠|让利)")
REBATE_WORD = _re(r"\brebates?\b", r"\bback\b", r"\bcashback\b", r"返利", r"返点", r"返现", r"返")
USE_FINANCING = _re(r"invoice financing", r"\bfactoring\b", r"\bfinance the invoice\b", r"发票融资", r"保理")
HARDLINE = _re(r"\bhard[- ]?line\b", r"\btough\b", r"\bwalks?\b", r"\brefuses?\b", r"强硬")
APPROVAL_REF = _re(r"\bapproval\b", r"\bpending\b", r"\bqueue", r"审批", r"待批")

TIER3: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SIGN_PERSONAL_GUARANTEE", _re(r"personal(?:ly)? guarant", r"\bguarantor\b", r"个人担保", r"个人连带", r"连带担保")),
    ("PLEDGE_COLLATERAL", _re(r"\bpledge\b", r"\bcollateral\b", r"\bmortgage\b", r"抵押", r"质押")),
    ("ISSUE_EQUITY", _re(r"\bissue (?:new )?(?:equity|shares)\b", r"\bsell (?:a )?stake\b", r"\bequity\b", r"股权", r"增发",
                         r"出让股份")),
    ("CHANGE_MANDATE", _re(r"\b(?:change|raise|lower|increase|decrease|edit|modify|update|override|bypass|ignore)\b.{0,20}"
                           r"\b(?:mandate|floor|reserve|cap|limits?)\b",
                           r"修改.{0,4}(?:授权|限额|底线|上限)", r"(?:降低|取消|提高).{0,6}(?:储备|底线|上限|限额)")),
)

FIXTURE_RE = rx(r"\b(EX\s?\d{2}[A-Z]?|SEC[_ ]DEMO)(?:_[A-Z0-9_]+)?\b", re.IGNORECASE)
QUOTED_RE = re.compile(r"[\"“「『](.{8,}?)[\"”」』]", re.DOTALL)
BUYER_SAYS_RE = rx(
    r"(?:buyer (?:says|wrote|sent)|message)\s*[:：]\s*(.{8,})$|买家说\s*[:：]\s*(.{4,})$"
    # "Foshan just sent this: 'We'll pay …'", "the customer wrote:", 东莞那边发来：, 佛山客户说：
    r"|\b(?:buyer|customer|client|they|he|she|[a-z][a-z]+(?: [a-z][a-z&]+){0,3})\s+(?:just\s+)?(?:says|said|wrote|sent(?: (?:this|us|me|over))?"
    r"|messaged|emailed|texted|replied|offered|proposed)\s*[:：]\s*(.{8,})$"
    r"|(?:客户|买家|买方|对方|那边|他们)(?:刚才?|刚刚)?(?:说|发来|来信|回复|提出|发消息说|发了)(?:了)?\s*[:：]\s*(.{4,})$",
    re.IGNORECASE | re.DOTALL)
# The owner's own question after a pasted offer: dropped before the offer is compiled.
OWNER_TAIL = _re(r"\bwhat do you think\b", r"\bthoughts\b", r"\bshould (?:we|i) (?:accept|take|agree)",
                 r"\bcan we (?:accept|take|agree|do)\b", r"\bis (?:this|it|that) (?:ok|okay|good|acceptable|fine)\b",
                 r"帮我看看", r"能不能接", r"能接吗", r"能答应吗", r"可以接受吗", r"能接受吗", r"怎么看", r"要不要接",
                 r"行不行", r"可以吗")
APPROVAL_ID_RE = rx(r"\bAPR-\d{6}\b", re.IGNORECASE)

ORDINALS = {"1": 1, "one": 1, "first": 1, "1st": 1, "第一": 1, "一": 1,
            "2": 2, "two": 2, "second": 2, "2nd": 2, "第二": 2, "二": 2,
            "3": 3, "three": 3, "third": 3, "3rd": 3, "第三": 3, "三": 3,
            "both": 99, "all": 99, "全部": 99, "都": 99, "两个都": 99}

# ---------------------------------------------------------------- values

_MONEY_RE = rx(
    r"(?P<pre>¥|￥|rmb\s*|cny\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>million|k\b|千|万|元|yuan\b|块)?",
    re.IGNORECASE)
_RATE_RE = rx(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>%|percent\b|bps?\b|个基点)", re.IGNORECASE)
_DAYS_RE = rx(r"(?P<num>\d{1,3})\s*(?:-\s*)?(?:days?\b|天|日)", re.IGNORECASE)
_INVOICES_RE = rx(r"(?:next|following)\s+(?P<n>\d+|two|three|four|five|six)\s+invoices|(?:接下来|后续)(?P<zh>\d+)张",
                          re.IGNORECASE)
_WORD_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
_UNIT = {"k": 1_000, "千": 1_000, "万": 10_000, "million": 1_000_000}


@dataclass(frozen=True)
class Found:
    value: int
    start: int
    end: int


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", ""))
    except InvalidOperation:
        return None


def amounts(text: str) -> list[Found]:
    """Money amounts with a currency marker or a unit (¥420k, 50万元, 500,000 yuan) as integer fen."""
    t = unicodedata.normalize("NFKC", text)
    out: list[Found] = []
    for m in _MONEY_RE.finditer(t):
        pre, unit = m.group("pre"), (m.group("unit") or "").lower()
        if not pre and not unit:
            continue
        tail = t[m.end():m.end() + 2]
        if tail.strip().startswith("%"):
            continue
        d = _dec(m.group("num"))
        if d is None:
            continue
        fen = d * _UNIT.get(unit, 1) * 100
        if fen != fen.to_integral_value() or fen <= 0:
            continue
        out.append(Found(int(fen), m.start(), m.end()))
    return out


def rates(text: str) -> list[Found]:
    """Rates as integer bp: 0.85% -> 85, 80bp -> 80."""
    t = unicodedata.normalize("NFKC", text)
    out: list[Found] = []
    for m in _RATE_RE.finditer(t):
        d = _dec(m.group("num"))
        if d is None:
            continue
        unit = m.group("unit").lower()
        bp = d * 100 if unit in ("%", "percent") else d
        if bp != bp.to_integral_value() or bp < 0 or bp > 10_000:
            continue
        out.append(Found(int(bp), m.start(), m.end()))
    return out


def days(text: str) -> list[Found]:
    t = unicodedata.normalize("NFKC", text)
    return [Found(int(m.group("num")), m.start(), m.end()) for m in _DAYS_RE.finditer(t) if 0 < int(m.group("num")) <= 365]


def invoices(text: str) -> int | None:
    m = _INVOICES_RE.search(unicodedata.normalize("NFKC", text))
    if not m:
        return None
    raw = m.group("n") or m.group("zh")
    return int(raw) if raw.isdigit() else _WORD_NUM.get(raw.lower())


def ordinal(text: str) -> int | None:
    t = norm(text).strip(" .!?。！？")
    for word, n in sorted(ORDINALS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", t) if word.isascii() else word in t:
            return n
    return None


# ---------------------------------------------------------------- names

_ZH_ALIASES = {"foshan": ("佛山",), "dongguan": ("东莞",)}


def counterparty_aliases(state: FinancialState) -> dict[str, tuple[str, ...]]:
    """Registry id -> lower-case aliases: the id, the full name, its first word and a zh city name."""
    out: dict[str, tuple[str, ...]] = {}
    for cp in state.counterparties:
        if cp.role not in ("BUYER", "LENDER"):
            continue
        first = cp.name.split()[0].lower().strip(".,")
        names = [cp.id.lower(), cp.id.lower().replace("-", " "), cp.name.lower(), first]
        names += list(_ZH_ALIASES.get(first, ()))
        out[cp.id] = tuple(dict.fromkeys(n for n in names if len(n) >= 2))
    return out


def find_counterparty(text: str, state: FinancialState, role: str | None = "BUYER") -> list[str]:
    t = norm(text)
    roles = {c.id: c.role for c in state.counterparties}
    hits = []
    for cp_id, names in counterparty_aliases(state).items():
        if role and roles.get(cp_id) != role:
            continue
        if any((re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", t) if n.isascii() else n in t) for n in names):
            hits.append(cp_id)
    return hits


FACILITY_WORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("CREDIT_LINE", _re(r"\bcredit line\b", r"\bthe line\b", r"\bline\b", r"\brevolver\b", r"授信", r"信用额度", r"额度")),
    ("INVOICE_FINANCING", _re(r"invoice financing", r"\bfactoring\b", r"发票融资", r"保理")),
)
