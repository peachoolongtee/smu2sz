"""The consent grammar: what free text may execute, and what may only be proposed, answered or clarified.

Free text never grants execution by containing a keyword. A financial instruction runs only when the WHOLE
normalised message full-matches the small closed affirmative grammar below: optional politeness, one imperative
verb, exactly one RMB amount (at most two decimals) and the facility. Negation, a question, a condition, a time
other than now/today, a foreign currency, sub-fen precision, a second amount or any rider is simply not in the
grammar, so it cannot execute. The same holds for an approval id (decided only by a full-match approve/reject
sentence) and for the confirmation of a pending plan (a short affirmative, nothing else).

Everything here is deterministic. The optional LLM classifier never reaches this module's "execute" answers: only
`parse_command`, `approval_verdict`, `bare_verdict` and `confirmation` grant anything, and they read the owner's
own words only.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.domain.models import FinancialState
from app.nl import lexicon as lx

MAX_COMMAND_CHARS = 160


def normalise(text: str) -> str:
    """NFKC (full-width digits, ￥ and ？ become ASCII), lower case, curly apostrophes straightened."""
    return unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("‘", "'").strip()


def _core(text: str) -> str | None:
    """The one-line message with its trailing punctuation removed, or None when it is not a single short line
    (a longer or multi-line message may hold someone else's words, so it grants nothing)."""
    n = normalise(text)
    if "\n" in n or len(n) > MAX_COMMAND_CHARS:
        return None
    n = re.sub(r"\s+", " ", n)
    n = re.sub(r"[\s.!;,。！；，、~～]+$", "", n)
    return re.sub(r"^[\s,，]+", "", n)


# ---------------------------------------------------------------- money

_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_RMB_PRE = ("¥", "rmb", "cny")
_RMB_POST = ("元", "块", "yuan", "rmb", "cny")
_FOREIGN_PRE = r"us\$|\$|€|£|usd|eur|gbp|jpy|hkd|aud|cad|sgd|chf"
_FOREIGN_POST = (r"usd|eur|gbp|jpy|hkd|aud|cad|sgd|dollars?|bucks|euros?|pounds?|quid|美元|美金|欧元|英镑|港币|港元|"
                 r"日元|刀")
_UNITS = {"万": 10_000, "千": 1_000, "k": 1_000, "million": 1_000_000, "billion": 1_000_000_000, "bn": 1_000_000_000}

# One amount as an instruction may state it: ¥100,000 / 100,000元 / 10万元 / RMB 50k. `rmb_fen` validates it.
AMOUNT = rf"(?:(?:¥|rmb|cny)\s?{_NUM}\s?(?:万|千|k|million)?\s?(?:元|块|yuan|rmb|cny)?|{_NUM}\s?(?:万|千)?\s?(?:元|块|yuan|rmb|cny)|{_NUM}\s?万)"
_RMB_ONE = re.compile(
    rf"(?P<pre>¥|rmb|cny)?\s?(?P<num>{_NUM})\s?(?P<mult>万|千|k|million)?\s?(?P<post>元|块|yuan|rmb|cny)?")
_SCAN = re.compile(
    rf"(?<![a-z0-9_-])(?P<pre>{_FOREIGN_PRE}|¥|rmb|cny)?\s?(?P<num>{_NUM})\s?(?P<mult>万|千|k\b|million|billion|bn)?"
    rf"\s?(?P<post>{_FOREIGN_POST}|元|块|yuan|rmb|cny)?")
_NOT_MONEY_NEXT = re.compile(
    r"\s?(?:%|percent|bps?\b|个点|折|st\b|nd\b|rd\b|th\b|days?\b|weeks?\b|months?\b|years?\b|hours?\b|天|日|号|月|周|年|"
    r"小时|点|个|张|笔|次|am\b|pm\b|[-/:]\d)")
_WORD_AMOUNT = re.compile(r"\b(?:hundred|thousand|million|billion|grand)\b|[一二两三四五六七八九十百零]+(?:万|千)|"
                          r"[一二两三四五六七八九十百零]+(?=元|块)")


def rmb_fen(token: str) -> int | None:
    """One RMB amount as integer fen: needs a marker (¥ / RMB / CNY before, 元 / yuan / 块 after, or 万), at most two
    decimals in yuan (a sub-fen amount is not an amount), strictly positive."""
    m = _RMB_ONE.fullmatch(token.strip())
    if not m:
        return None
    mult = m.group("mult")
    if not (m.group("pre") or m.group("post") or mult == "万"):
        return None
    try:
        d = Decimal(m.group("num").replace(",", "")) * _UNITS.get(mult or "", 1) * 100
    except InvalidOperation:
        return None
    if d != d.to_integral_value() or d <= 0:
        return None
    return int(d)


def scan_amounts(text: str) -> list[int | None]:
    """Every explicit amount in the message: integer fen when it reads as RMB with at most two decimals, None when it
    cannot (a foreign currency, an unmarked number, a number word, sub-fen precision, a unit with no currency).
    Rates, days, dates, ordinals and identifiers (APR-000001, EX01) are not amounts."""
    n = normalise(text)
    out: list[int | None] = []
    for m in _SCAN.finditer(n):
        pre, mult, post = m.group("pre"), m.group("mult"), m.group("post")
        if not pre and not post and not mult and _NOT_MONEY_NEXT.match(n[m.end():]):
            continue
        foreign = bool((pre and pre not in _RMB_PRE) or (post and post not in _RMB_POST))
        if foreign:
            out.append(None)
            continue
        if not pre and not post and not mult:
            num = m.group("num")
            if len(num) >= 3 or "," in num or "." in num:
                out.append(None)  # an unmarked number: not readable as RMB
            continue
        out.append(rmb_fen(m.group(0)))
    for _ in _WORD_AMOUNT.finditer(n):
        out.append(None)
    return out


# ---------------------------------------------------------------- the affirmative command grammar

_FAC_EN = (r"(?P<fac>fac-[a-z0-9-]+|credit line|line of credit|credit facility|bank line|revolving (?:credit )?line|"
           r"revolver|invoice financing|invoice finance|factoring|line|facility)")
_FAC_ZH = r"(?P<fac>授信额度|信用额度|贷款额度|银行额度|发票融资|保理|授信|额度)"
_THE = r"(?:the |our |my )?"
_EN_NOW = r"(?:(?:right )?now|today|immediately|right away)"
_EN_PRE = rf"(?:(?:please|pls|kindly)[ ,]+)?(?:{_EN_NOW}[ ,]+)?"
_EN_POST = rf"(?:[ ,]+(?:please|pls|thanks|thank you|{_EN_NOW}))*"
_ZH_PRE = r"(?:(?:请你?|麻烦你?|劳驾|请帮我|帮我)[ ,]*)?(?:(?:现在|马上|立即|立刻|今天)[ ,]*)?(?:请[ ,]*)?"
_ZH_POST = r"(?:[ ,]*(?:现在|马上|立即|立刻|今天|谢谢|多谢|谢了|吧|啊|呀|哦))*"
_ZH_FROM = r"(?:从|在|用|动用|向)?(?:我们的|咱们的|我的)?"
_DRAW_VERB = r"(?:draw(?: ?down)?|withdraw|take out|pull)"
_REPAY_VERB = r"(?:repay|pay back|pay down|pay off)"
_ZH_DRAW = r"(?:提款|提取|提现|支取|提用|支用|提|取|借)"
_ZH_REPAY = r"(?:偿还|归还|还款|还)"

_DRAW = [
    re.compile(rf"{_EN_PRE}{_DRAW_VERB} (?P<amt>{AMOUNT}) (?:on|from|against|off|out of|under) {_THE}{_FAC_EN}{_EN_POST}"),
    re.compile(rf"{_EN_PRE}draw(?: ?down)? (?:on )?{_THE}{_FAC_EN} (?:by |for |of )?(?P<amt>{AMOUNT}){_EN_POST}"),
    re.compile(rf"{_ZH_PRE}{_ZH_FROM}{_FAC_ZH}(?:里|中|上)?{_ZH_DRAW}(?:出)? ?(?P<amt>{AMOUNT})(?:出来)?{_ZH_POST}"),
    re.compile(rf"{_ZH_PRE}{_ZH_DRAW} ?(?P<amt>{AMOUNT}) ?(?:从|在|用|向){_FAC_ZH}(?:里|中|上)?{_ZH_POST}"),
]
_REPAY = [
    re.compile(rf"{_EN_PRE}{_REPAY_VERB} (?P<amt>{AMOUNT}) (?:on|of|to|towards?|from) {_THE}{_FAC_EN}{_EN_POST}"),
    re.compile(rf"{_EN_PRE}{_REPAY_VERB} {_THE}{_FAC_EN} (?:by |with |for |of )?(?P<amt>{AMOUNT}){_EN_POST}"),
    re.compile(rf"{_ZH_PRE}{_ZH_REPAY}(?:了)?{_FAC_ZH}(?:里|中|上)? ?(?P<amt>{AMOUNT}){_ZH_POST}"),
    re.compile(rf"{_ZH_PRE}(?:向|给|对)?{_FAC_ZH}(?:里|中|上)?{_ZH_REPAY} ?(?P<amt>{AMOUNT}){_ZH_POST}"),
    re.compile(rf"{_ZH_PRE}{_ZH_REPAY} ?(?P<amt>{AMOUNT}) ?(?:到|给|向|至|回)?{_FAC_ZH}{_ZH_POST}"),
]


@dataclass(frozen=True)
class Command:
    kind: Literal["DRAW", "REPAY"]
    amount_fen: int
    facility_id: str


def _facility_id(word: str, state: FinancialState) -> str | None:
    if word.startswith("fac-"):
        return next((f.id for f in state.facilities if f.id.lower() == word), None)
    kind = "INVOICE_FINANCING" if re.search(r"invoice|factoring|发票融资|保理", word) else "CREDIT_LINE"
    found = [f.id for f in state.facilities if f.kind.value == kind]
    return found[0] if len(found) == 1 else None


def parse_command(text: str, state: FinancialState) -> Command | None:
    """The one place a free-text financial instruction becomes executable: the whole message is the command."""
    core = _core(text)
    if core is None:
        return None
    for kind, patterns in (("DRAW", _DRAW), ("REPAY", _REPAY)):
        for p in patterns:
            m = p.fullmatch(core)
            if not m:
                continue
            fen = rmb_fen(m.group("amt"))
            fac = _facility_id(m.group("fac"), state)
            if fen is not None and fac is not None:
                return Command(kind, fen, fac)  # type: ignore[arg-type]
    return None


# ---------------------------------------------------------------- everything else with a financial intent

_NEG_EN = (r"(?<![a-z])(?:do not|don't|dont|does not|doesn't|did not|didn't|never|not|no|nor|cannot|can't|cant|won't|"
           r"wouldn't|shouldn't|should not|stop|cancel|refrain|avoid|skip|hold off|forget (?:about |it)|n't)(?![a-z])")
_NEG_ZH = (r"不要|(?<![特区分告辞离个])别|不用|不必|无需|勿|不想|不许|不准|不能|不可|不该|不应|没让|没叫|暂不|先不|不是让|并非|"
           r"取消|停止|算了|禁止|切勿|请勿|不得|不(?=提|借|支|取|还|动|补|垫|付|用)")
NEGATION = re.compile(f"{_NEG_EN}|{_NEG_ZH}")
CONDITION = re.compile(
    r"(?<![a-z])(?:if|only if|unless|when|whenever|once|provided|providing|assuming|supposing|in case|as long as|"
    r"so long as|depending|contingent|subject to)(?![a-z])|如果|假如|假设|要是|倘若|若|除非|万一|一旦|的话|只有|只要|等到|当.{0,10}时")
FUTURE = re.compile(
    r"(?<![a-z])(?:tomorrow|tmrw|tmr|tonight|later|next|soon|eventually|upcoming|following|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|weekend|after|before|until|from now|"
    r"(?:in|within|after|by|before|until) (?:\d+|a|an|one|two|three|four|five|six|seven|ten|several|few) "
    r"(?:day|days|week|weeks|month|months|hour|hours|year|years|minutes?)|"
    r"end of (?:the )?(?:day|week|month|quarter|year)|eod|eow|eom|"
    r"this (?:week|month|quarter|year|afternoon|evening|morning)|on (?:the )?\d|at \d|\d ?(?:am|pm)|"
    r"(?:jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d+|\d{4}-\d{2}-\d{2}|day \d+)(?![a-z])"
    r"|明天|明日|后天|今晚|稍后|晚点|晚些|之后|以后|随后|下周|下个?月|下个?季度|下午|下礼拜|本周|这周|本月|这个月|"
    r"周[一二三四五六日天]|星期[一二三四五六日天]|礼拜[一二三四五六日天]|月底|周末|年底|改天|回头|到时候|过几天|"
    r"\d+ ?(?:天|日|周|个月|小时)(?:后|内|以后|之后)|\d+月\d*[日号]|\d+[号]|(?:过|等)[一二两三四五六七八九十\d]+(?:天|周|个月)")
_QUESTION = re.compile(
    r"^(?:(?:please|pls|hey|hi|ok|okay|so|and)[ ,]+)?(?:is|are|am|was|were|can|could|should|would|will|shall|do|does|did|"
    r"may|might|what|how|whether|why|which|who|where|any chance)(?![a-z])|"
    r"(?<![a-z])(?:wondering|do you think|let me know (?:if|whether)|tell me (?:if|whether))(?![a-z])|"
    r"吗|嘛|(?<!什)么|是否|能不能|可不可以|要不要|会不会|行不行|好不好|对不对|有没有|是不是|请问|呢")


def is_question(text: str) -> bool:
    n = normalise(text)
    return "?" in n or bool(_QUESTION.search(n))


def money_gate(text: str) -> Literal["negated", "bad_amount", "deferred", "question", "propose"]:
    """How a financial instruction that is NOT the executable grammar is treated. Nothing here executes:
    negated -> nothing is done and the plan is cleared; bad_amount -> a clarification (never the default funding
    bundle); deferred (a condition or a time other than now) -> an answer, nothing proposed; question and
    propose -> a proposal that waits for the owner's confirmation."""
    n = normalise(text)
    if NEGATION.search(n):
        return "negated"
    if CONDITION.search(n) or FUTURE.search(n):
        return "deferred"
    amounts = scan_amounts(n)
    if len(amounts) > 1 or any(a is None for a in amounts):
        return "bad_amount"
    return "question" if is_question(n) else "propose"


# ---------------------------------------------------------------- negating an action (negotiate, get paid early)

# "Do not negotiate with Foshan", "don't send the counters", 不要谈判, "do not get paid early on the Foshan invoice",
# 不要让佛山提前付款: a negation that governs the ACTION. A phrase that constrains it ("don't give anything away",
# "without conceding the rebate", 不要给任何让步) negates the concession, not the action, so it is not matched here.
_NEG_LEAD = (r"(?<![a-z])(?:do not|don't|dont|never|stop|cancel|no need to|avoid|skip|hold off(?: on)?|refrain from|not)"
             r"\s+(?:(?:try(?:ing)? to|bother(?:ing)? to|want to|need to|go and|start)\s+)?")
_NEG_NEGOTIATE = re.compile(
    _NEG_LEAD + r"(?:negotiat\w*|send(?:\s+(?:out|over|them|the|our|both|any|those|these|a|my))*\s+counter\w*|"
                r"counter[- ]?offer\w*|counter(?=\s+(?:them|him|her|the buyer|it)\b)|haggl\w*|push\s*back|bargain\w*)"
    r"|(?<![a-z])no\s+(?:more\s+)?(?:negotiat\w*|counter[- ]?offers?)"
    r"|(?:不要|(?<![特区分告辞离个])别|不用|不必|取消|先不|暂不|停止|勿|不再|不)"
    r"(?:再|去|要|(?:跟|和|与|向|对)[^，,。；;！!？?]{1,10})?"
    r"(?:谈判|谈一下|谈谈|谈|发送|发|还价|议价|砍价|反报价|反要约)(?!\s*(?:任何|让步|让利|返点|返利|优惠))")
_NEG_ACCELERATE = re.compile(
    _NEG_LEAD + r"(?:get(?:ting)?|have|be|being|ask(?:ing)?|collect(?:ing)?|settle|settling|pay(?:ing)?|accelerat\w*|"
                r"speed up|chase)\b(?:\s+\w+){0,3}?\s+(?:paid|pay|early|sooner|earlier|faster|quicker|accelerat\w*)"
    r"|(?<![a-z])no\s+early[- ]?(?:pay\w*|settle\w*)"
    r"|(?:不要|(?<![特区分告辞离个])别|不用|不必|取消|先不|暂不|停止|勿|不再|不)"
    r"(?:再|去|要|让|叫|请|帮我|给我|(?:跟|和|与|向)[^，,。；;！!？?]{0,8})*"
    r"[^，,。；;！!？?]{0,6}?(?:提前|早点|早付|提早|尽快)")


# "without conceding the rebate", "don't concede anything": a constraint on a negotiation (no forward concessions).
NO_CONCEDE = re.compile(r"(?<![a-z])(?:without|not)\s+conced\w+|(?<![a-z])(?:don't|dont|do not|never)\s+(?:concede|give in)(?![a-z])|"
                        r"不要?(?:做出?)?让步|别让步")


def action_negated(kind: Literal["NEGOTIATE", "ACCELERATE"], text: str) -> bool:
    """The owner says NOT to do the action: nothing is done and no plan stays pending (the caller answers)."""
    pattern = _NEG_NEGOTIATE if kind == "NEGOTIATE" else _NEG_ACCELERATE
    return bool(pattern.search(normalise(text)))


# ---------------------------------------------------------------- approvals

_ID = r"aprid"
_APPROVE_VERB = r"(?:approve|批准|同意|审批通过)"
_REJECT_VERB = (r"(?:reject|decline|deny|do not approve|don't approve|dont approve|do not authori[sz]e|"
                r"don't authori[sz]e|拒绝|驳回|不批准|不同意|不要批准|别批准|否决)")
_ITEM = r"(?:(?:the |this |that )?(?:approval |request |operation |item )?)"
_ZH_ITEM = r"(?:这个|这笔|这项|它|该)?"
_YES = r"(?:(?:yes|yep|yeah|ok|okay|sure|好的?|是的?|对|嗯|可以)[ ,，]*)?"
_NO = r"(?:(?:no|nope|不)[ ,，]*)?"
_PLEASE = r"(?:(?:please|pls|kindly|请)[ ,，]*)?"
_THANKS = r"(?:[ ,，]*(?:please|pls|thanks|thank you|吧|谢谢|啊))*"

_ID_RE = re.compile(r"(?<![a-z0-9-])apr-\d{6}(?!\d)")
_APPROVE_ID = re.compile(rf"{_YES}{_PLEASE}{_APPROVE_VERB} ?{_ITEM}{_ID}{_THANKS}")
_REJECT_ID = re.compile(rf"{_NO}{_PLEASE}{_REJECT_VERB} ?{_ITEM}{_ID}{_THANKS}")
_APPROVE_BARE = re.compile(
    rf"{_YES}{_PLEASE}{_APPROVE_VERB}(?: it| that| this| the (?:pending |queued |waiting )?(?:one|operation|approval|request|item)"
    rf"|{_ZH_ITEM}(?:待审批的?(?:那个|那笔|操作|事项)?|待批的?)?){_THANKS}")
_REJECT_BARE = re.compile(
    rf"{_NO}{_PLEASE}{_REJECT_VERB}(?: it| that| this| the (?:pending |queued |waiting )?(?:one|operation|approval|request|item)"
    rf"|{_ZH_ITEM}(?:待审批的?(?:那个|那笔|操作|事项)?|待批的?)?){_THANKS}")
_APPROVE_ZH_BARE = re.compile(rf"{_PLEASE}{_APPROVE_VERB}{_ZH_ITEM}{_THANKS}")
_REJECT_ZH_BARE = re.compile(rf"{_PLEASE}{_REJECT_VERB}{_ZH_ITEM}{_THANKS}")


def approval_ids(text: str) -> list[str]:
    return list(dict.fromkeys(m.upper() for m in _ID_RE.findall(normalise(text))))


def approval_verdict(text: str) -> Literal["approve", "reject"] | None:
    """The decision on a message that names ONE approval id: approve only on a full-match affirmative
    (`approve APR-000001`, `yes, approve APR-000001`, `批准 APR-000001`), reject only on a full-match rejection
    (`reject APR-…`, `do not approve APR-…`, `拒绝 APR-…`, `不批准 APR-…`). Everything else (a bare id, a question,
    a mixed approve and reject cue, a second id, a rider) is None: the caller clarifies and mutates nothing."""
    core = _core(text)
    if core is None or len(_ID_RE.findall(core)) != 1:
        return None
    masked = re.sub(r"\s+", " ", _ID_RE.sub(f" {_ID} ", core)).strip()
    masked = re.sub(rf"(?<={_ID}) (?=[一-鿿])", "", masked)
    if _APPROVE_ID.fullmatch(masked) and not _REJECT_ID.fullmatch(masked):
        return "approve"
    if _REJECT_ID.fullmatch(masked):
        return "reject"
    return None


def bare_verdict(text: str) -> Literal["approve", "reject"] | None:
    """The same, for a decision that names no id ("approve it", "reject the pending one", 批准这个): it may
    only bind to the item this session just showed, which the service checks."""
    core = _core(text)
    if core is None or _ID_RE.search(core):
        return None
    if _REJECT_BARE.fullmatch(core) or _REJECT_ZH_BARE.fullmatch(core):
        return "reject"
    if _APPROVE_BARE.fullmatch(core) or _APPROVE_ZH_BARE.fullmatch(core):
        return "approve"
    return None


# ---------------------------------------------------------------- confirming or cancelling a pending plan

_YES_EN = (r"go ahead|go for it|proceed|confirm(?:ed)?|do it|execute(?: it)?|run it|approve(?:d)?(?: it| that| this)?|"
           r"lgtm|send it|make it so|sounds good|that'?s fine|that works|yes|yep|yeah|ya|yup|ok(?:ay)?|sure|alright|"
           r"fine|great|perfect")
_YES_ZH = (r"好的?|行|可以|同意|确认|确定|执行|是的?|对|没问题|就这么办|照办|办吧|去办|做吧|弄吧|继续|开始|批准|按这个来|办")
_FILLER = (r"please|pls|kindly|and|then|now|thanks|thank you|请|麻烦|谢谢|多谢|吧|啊|呀|的|了|现在|马上|立即|立刻")
_YES_PLAN = re.compile(rf"(?:(?:{_FILLER}|{_YES_EN}|{_YES_ZH})[ ,，]*)+")
_YES_CORE = re.compile(rf"(?<![a-z])(?:{_YES_EN})(?![a-z])|{_YES_ZH}")
_NO_EN = (r"no|nope|nah|cancel|stop|abort|don't|dont|do not|never ?mind|forget it|scrap it|hold off|not now|"
          r"that|it|this|just|anything|nothing|go ahead|proceed|do it|execute|run it|confirm")
_NO_ZH = r"不要|别|不用|不必|取消|算了|不行|不|先不|停止|停下|撤销|作罢|不执行|不办|执行|办|做|了|吧|啊"
_NO_PLAN = re.compile(rf"(?:(?:{_FILLER}|{_NO_EN}|{_NO_ZH})[ ,，]*)+")
_NO_CORE = re.compile(r"(?<![a-z])(?:no|nope|nah|cancel|stop|abort|don't|dont|do not|never ?mind|forget it|scrap it|"
                      r"hold off|not now)(?![a-z])|不要|别|不用|不必|取消|算了|不行|先不|停止|停下|撤销|作罢|不执行|不办|不")


def confirmation(text: str) -> Literal["yes", "no"] | None:
    """The reply to a pending plan: "yes" only when the whole message is a short affirmative ("go ahead", "yes",
    "confirm", "好的", "确认" ...), "no" for a short cancellation or any plain refusal that is not a question, and None
    for everything else ("should I go ahead?", "go ahead if cash is low", a longer sentence): it decides nothing."""
    core = _core(text)
    if core is None or "?" in core:
        return None
    if _YES_PLAN.fullmatch(core) and _YES_CORE.search(core) and not _NO_CORE.search(core):
        return "yes"
    if _NO_PLAN.fullmatch(core) and _NO_CORE.search(core):
        return "no"
    if lx.DECLINE.search(core) and not is_question(core):
        return "no"
    return None
