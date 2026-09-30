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
WHAT_IF = _re(r"\bwhat if\b", r"\bwhat would happen\b", r"\bsuppose\b", r"\bhypothetical", r"如果", r"假如", r"假设",
              r"要是")
STATUS = _re(r"\bstatus\b", r"\bposition\b", r"\bhow are we\b", r"\bhow'?s (?:our |the )?cash\b", r"\bheadroom\b",
             r"\bdashboard\b", r"\boverview\b", r"\bcash balance\b", r"\bwhere do we stand\b", r"现状", r"状况", r"状态",
             r"现金(?:余额|情况)", r"余额", r"概况", r"情况怎么样")
REPAY = _re(r"\brepay", r"\bpay (?:back|down|off)\b", r"还款", r"偿还", r"还清", r"归还")
FUND = _re(r"\bfund (?:the |it\b|this\b|that\b|our )", r"\bfund it\b", r"\bcover (?:the |our )?(?:cash )?(?:gap|shortfall)",
           r"\bclose (?:the )?gap\b", r"\bfunding gap\b", r"\bcash gap\b", r"\bshortfall\b", r"\bbridge (?:the )?gap\b",
           r"\bdraw\b", r"补(?:足|上)?(?:资金)?缺口", r"资金缺口", r"填补", r"提款", r"支取", r"动用.{0,6}额度")
ACCELERATE = _re(r"\b(?:get|be|getting) paid (?:early|sooner|faster)\b", r"\bearly (?:payment|settlement)\b",
                 r"\bcollect (?:early|sooner)\b", r"\baccelerate\b", r"\bspeed up (?:the )?(?:payment|collection|receipt)",
                 r"提前(?:收款|回款|结算)", r"早点(?:收|回)款", r"加快回款", r"尽快收回")
NEGOTIATE = _re(r"\bnegotiat", r"\bsend (?:the |our |both )?counters?\b", r"\bcounter[- ]?offer", r"\bhaggle\b",
                r"\bbargain\b", r"谈判", r"还价", r"议价", r"反报价", r"发(?:送)?反要约")
EVALUATE = _re(r"\bevaluate\b", r"\bassess\b", r"\bcheck (?:this|the|that|offer)\b", r"\breview (?:this|the|that)\b",
               r"\banaly[sz]e\b", r"\bis (?:this|it) (?:a )?good\b", r"\bshould (?:we|i) accept\b", r"\bbuyer (?:says|wrote|sent)\b",
               r"评估", r"审核", r"分析", r"看看这", r"要不要接受", r"能不能接受", r"买家说")
AMBIGUOUS = _re(r"\b(?:help|sort out|do something about|handle|deal with|fix)\b.{0,30}\b(?:cash|money|finances?|liquidity)\b",
                r"处理一下(?:资金|现金|钱)", r"帮我(?:管|弄|搞)一下(?:钱|资金)", r"资金怎么办", r"钱的问题")
CAPEX = _re(r"\bmachine\b", r"\bequipment\b", r"\bcapex\b", r"设备", r"机器", r"购置")
ZERO_FORWARD = _re(r"without giving (?:anything|something) away", r"\bnothing away\b", r"\bno (?:forward )?concessions?\b",
                   r"\bzero (?:forward )?concessions?\b", r"不(?:做|给)(?:任何)?让步", r"不让利", r"不给任何(?:优惠|让利)")
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
BUYER_SAYS_RE = rx(r"(?:buyer (?:says|wrote|sent)|message)\s*[:：]\s*(.{8,})$|买家说\s*[:：]\s*(.{4,})$",
                           re.IGNORECASE | re.DOTALL)
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
