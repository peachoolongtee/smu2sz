"""The coverage proof (docs/adr/0005-autonomy-requires-proof.md): may this offer be accepted without the owner?

`prove()` returns (eligible, notes). Eligible is True only when every check below passes; each failed check adds
one short note (a fixed template: no amount, rate or text from the message is echoed). The default is False: a
false negative costs the owner one click, a false positive commits the business.

(a) Every numeric mention in every document is accounted for by an extracted obligation: its rate, its base or
    fixed amount, its terms or bound, a discount sum or net payment that equals rate x face, or an invoice
    reference the obligation binds. Dates and settlement windows are never read into a term, so any stated one
    fails the proof. Phone numbers, e-mail and web addresses, clock times and the lines of a header or signature
    are the only allow-list (`ALLOWED`).
(b) Figures agree: `settlement_conflicts()` marks a stated discount sum or net payment that is not rate x face
    within one fen; `build_offer` then returns CONFLICTING_SOURCES.
(c) No sentence holds a request, a condition, a question or another topic beyond the extracted obligations
    (request-verb and question cues, en + zh), once the obligations' own words, greetings, sign-offs and
    confirmation tags are set aside.
(d) No authority claim, data request or funding claim; nothing claimed as previously agreed.
(e) Every document of the offer (message and attachments) is scanned.
(f) Fail closed on unread words: the text left once the numbers and references the obligations explain,
    greetings, sign-offs and contact details are removed (the residue, source spans included) may hold only the closed list of filler
    words in `_FILLER_EN` / `_FILLER_ZH`. Any other word is unread text that might carry a term, so the proof
    fails and names up to five such words (single words only, never a phrase). No other currency than CNY, no
    rate per a period other than the invoice, and no reference to an attachment that was not supplied.
It also requires a clean compilation (COMPILED, no material abstention, nothing unresolved) and, for each
early-pay discount, a stated rate and a stated invoice amount.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.compiler import lexicon
from app.compiler.folding import fold
from app.compiler.parsing import find_money, find_rates, rx
from app.domain.models import (
    Abstention,
    AuthorityClaim,
    CompileStatus,
    DataRequest,
    Obligation,
    ObligationType,
    SourceDocument,
    SourceSpan,
    UnsolicitedFundingClaim,
)

I = re.IGNORECASE

# ---------------------------------------------------------------- vocabulary

# An invoice number the buyer quotes: "INV-2026-0871", "RCV-A", "invoice no. 5531", "发票号 12345".
INVOICE_REF_RE = rx(
    r"\b(?:INV|RCV|FP)[-‐_]?(?=[A-Z0-9-]*\d|[A-Z]\b)(?P<a>[A-Z0-9][A-Z0-9-]*)"
    r"|(?i:invoice|inv\.?)\s*(?:(?i:no)\.?|(?i:number)|#)\s*[:：]?\s*(?P<b>[A-Z0-9][A-Z0-9-]{2,})"
    r"|发票(?:号码?|编号)\s*[:：]?\s*(?P<c>[A-Z0-9][A-Z0-9-]{2,})")
# Any other quoted code: "PO-4471", "SO#221", "Q1", "DN 5520".
_CODE_RE = rx(r"\b[A-Z]{1,5}[-‐_#]?\s?\d[\w-]*|#\s?\d{2,}")

_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?"
          r"|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
DATE_RE = rx(
    rf"\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\b"
    r"|\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\bthe\s+\d{1,2}(?:st|nd|rd|th)\b"
    r"|(?:\d{2,4}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*[日号]?|\d{1,2}\s*[号日](?![元]|本)"
    r"|\b(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\b\.?|(?:周|星期|礼拜)[一二三四五六日天]"
    r"|\b(?:january|february|march|april|june|july|august|september|october|november|december|jan|feb|aug|sept?|oct|nov|dec)\b", I)
# A settlement time the verifier cannot assume: any stated time, "now / today / tomorrow" included (the binding
# assigns its own day, so a stated day it cannot prove equal is unread timing). No time at all is fine.
TIMING_RE = rx(
    r"\bnext\s+(?:week|month|quarter|mon\w*|tue\w*|wed\w*|thu\w*|fri\w*|sat\w*|sun\w*)\b|\bthis\s+(?:week|month|friday|weekend)\b"
    r"|\b(?:end|close)\s+of\s+(?:the\s+)?(?:week|month|quarter|year|day)\b|\b(?:month|quarter|year|week)[- ]end\b|\beo[mwdq]\b"
    r"|\bafter\s+(?:the\s+)?(?:holiday|holidays|golden\s+week|national\s+day|new\s+year|cny|chinese\s+new\s+year|spring\s+festival|payday)"
    r"|\bgolden\s+week\b|\bwithin\s+(?:a|the|one|two|three|four|five|a\s+few|a\s+couple\s+of|several)\s+(?:days?|weeks?)\b"
    r"|\bin\s+(?:a|one|two|three|a\s+few|a\s+couple\s+of)\s+(?:days?|weeks?)\b|\b(?:on\s+time|when\s+due|on\s+(?:the\s+)?due\s+date|at\s+maturity)\b"
    r"|\bearly\s+next\b|\blater\s+this\b|\bsoon\b"
    r"|\b(?:today|tomorrow|tmrw|tmr|tonight|now|immediately|right\s+away|straight\s+away|at\s+once)\b"
    r"|今天|明天|后天|今晚|现在|马上|立即|立刻|即刻|当天"
    r"|下(?:个)?(?:周|星期|礼拜|月)|这(?:个)?(?:周|星期|礼拜)|本(?:周|月)|月(?:底|初|中)|周末|节后|节前|年底|年前|国庆|春节|过几天|几天(?:内|后)|按时|到期"
    , I)

_DAYS_RE = rx(r"(?<![\d.])(?P<n>\d{1,3})\s*[-‑]?\s*(?:(?:business|working|calendar|banking)\s+)?(?:days?\b|个?工作日|天)", I)
_COUNT_RE = rx(r"\b(?P<n>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:open\s+|separate\s+)?"
               r"(?:invoices?|bills?|orders?|shipments?|deliveries|payments?|instal+ments?|tranches?)\b"
               r"|(?P<z>[一两二三四五六七八九十\d]+)\s*(?:张|笔|批|期|次)", I)
_WORD_NUMBER_RE = rx(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|forty-five"
                     r"|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million)\b(?=[\s-]+(?:days?|weeks?|months?|years?|percent"
                     r"|per\s?cent|points?|bps|basis|k\b|thousand|million|yuan|rmb|kuai))", I)
_DIGITS_RE = re.compile(r"\d+(?:[.,]\d+)*")
_ZH_NUMERAL_RE = re.compile(
    r"(?:百分之|千分之|万分之)?[零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟]+"
    r"(?=\s*(?:万|亿|千|百|元|块|个?点|个百分点|天|日|号|月|周|年|折|成|%|％|张|笔|单|期|次|倍|个))")
_ZH_CAPITAL_RE = re.compile(r"[壹贰叁肆伍陆柒捌玖拾佰仟]")
_ZH_HARMLESS = re.compile(r"一次性|一次付清|一次结清|一口气|一下|一起|一直|一定|一般|统一|一点(?![零一二三四五六七八九\d])|一些|星期|周末")

# Allow-list: numbers that are not terms.
ALLOWED = [
    rx(r"(?:\+?86[-\s]?)?\b1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}\b"),  # CN mobile
    rx(r"(?:\+\d{1,3}[-\s]?)?\(?\d{2,4}\)?[-\s]\d{3,4}[-\s]?\d{3,4}\b"),  # landline
    rx(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),  # e-mail
    rx(r"\bhttps?://\S+|\bwww\.\S+", I),  # web address
    rx(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b|(?:上午|下午|晚上|早上)?\d{1,2}\s*点(?:半|\d{1,2}分?)?(?=前|之前|以前|左右|$|[，。,.])", I),
    # header and signature lines: "Tel: ...", "Date: 2026-10-01", "Sent: ...", "电话：..."
    rx(r"^[ \t]*(?:tel|phone|mob(?:ile)?|fax|cell|e-?mail|date|sent|from|to|cc|subject|wechat|whatsapp|电话|手机|传真|邮箱|日期|发件人|收件人|主题|微信)"
       r"\s*[:：][^\n]*$", I | re.MULTILINE),
    rx(r"^[ \t]*(?:©|\(c\)|copyright)[^\n]*$", I | re.MULTILINE),
]

# ---------------------------------------------------------------- (c) requests and extra clauses

# Words the obligations' own framing and courtesy use; set aside before looking for requests.
_FRAMING = rx(
    r"\bif\s+(?:you|u)(?:'re|\s+are|\s+r)?\s+(?:(?:can|could|would|will)\s+)?(?:ok(?:ay)?\s+(?:with|to)|happy\s+to|able\s+to|agree(?:able)?\s+to"
    r"|give|allow|grant|offer|accept|take|knock|let\s+us\s+have)(?:\s+us)?"
    r"|\bif\s+(?:that'?s|this\s+is|it'?s)\s+(?:ok(?:ay)?|fine|acceptable|agreeable|alright)|\bif\s+ok\b|\bif\s+(?:that|this)\s+works\b"
    r"|\b(?:please|pls|plz|kindly)\s+(?:confirm|advise|let\s+(?:me|us)\s+know)\b|\b(?:can|could)\s+(?:you|u)\s+confirm\b"
    r"|\blet\s+(?:me|us)\s+know\b|\bconfirm\s+(?:when|if)\s+(?:you\s+can|ok|possible)\b"
    r"|\b(?:call|ring|contact|reach|text|message)\s+(?:me|us)\b[^.!?\n]{0,40}?(?:\bif\s+(?:needed|necessary|required|you\s+have\s+(?:any\s+)?questions?)\b|$|(?=[.!\n]))"
    r"|\bif\s+(?:needed|necessary|required|any\s+questions?|you\s+have\s+(?:any\s+)?questions?)\b|\bany\s+questions?\b"
    r"|^\s*(?:hi|hello|hey|dear|morning|good\s+(?:morning|afternoon|evening))\b[^,，.!！\n]{0,30}"
    r"|\bhope\s+(?:all\s+)?(?:is\s+)?(?:good|well|fine|you(?:'re|\s+are)\s+well|this\s+finds\s+you\s+well)\b"
    r"|\b(?:many\s+)?thanks?(?:\s+you)?(?:\s+(?:in\s+advance|so\s+much|a\s+lot))?\b|\bthx\b|\bcheers\b|\b(?:best|kind|warm)?\s*regards\b|\bbest\b|\bbr\b"
    r"|\bnothing\s+else\s+(?:changes|changing)\b|\beverything\s+else\s+(?:stays|remains)\s+(?:the\s+)?same\b|\ball\s+else\s+(?:unchanged|the\s+same)\b"
    r"|\b(?:ok(?:ay)?|deal|agreed|alright|sound\s+good|works\s+for\s+you|does\s+that\s+work(?:\s+for\s+you)?|is\s+that\s+(?:ok(?:ay)?|fine|alright|acceptable))\s*[?？]"
    r"|(?:你|您)好|[一-鿿]{1,4}(?:经理|总|小姐|先生|女士|老师)(?:你|您)?好|谢谢|多谢|感谢|辛苦了?|祝好|此致|敬礼"
    r"|请确认|麻烦确认|确认一下|没问题的话|可以的话|行的话|如果可以的话|如果没问题|行吗|可以吗|好吗|行不行|可以不|ok吗|同意吗|能接受吗|能接吗|就行|就可以|即可"
    r"|别的都不变|其他(?:都)?不变|其余(?:都)?不变|就这一张|麻烦|劳烦|请", I | re.MULTILINE)
# A request, condition, question or other topic in what is left of a sentence.
_REQUEST = [
    ("question", rx(r"(?:^|[,，:：;；—–-]\s*|\b(?:and|also|but|so)\s+)(?:can|could|would|will|may|shall|should|do|does|is|are)\s+"
                    r"(?=[A-Za-z])(?!we\b|i\b|it\s+be\b)", I | re.MULTILINE)),
    ("request", rx(r"\b(?:can|could|would|will)\s+(?:you|u|your\s+(?:team|side|company))\b"
                   r"|\b(?:please|pls|plz|kindly)\s+(?=[a-z])(?!confirm|advise|let\s+(?:me|us)\s+know)"
                   r"|\b(?:we|i)\s+(?:would\s+|'d\s+|also\s+|really\s+)?(?:need|want|require|ask|request|expect|propose|suggest|insist|like)\b"
                   r"|\bwe'?d\s+(?:like|want|need|ask|appreciate|prefer)\b|\b(?:need|want)\s+you\s+to\b|\bmake\s+sure\b"
                   r"|\bone\s+(?:more\s+)?(?:ask|request|thing|favou?r|condition|question|point)\b|\bin\s+return\b|\bin\s+exchange\b"
                   r"|(?:^\s*|[.!?\n]\s*)(?:send|provide|change|switch|move|deliver|ship|add|update|reissue|re-issue|issue|extend|waive|cover"
                   r"|include|reduce|increase|cut|lower|raise|hold|reserve|cancel|stop|start|allow|give|arrange|note\s+that)\b", I | re.MULTILINE)),
    ("condition", rx(r"\b(?:if|provided|providing|unless|as\s+long\s+as|so\s+long\s+as|on\s+condition|subject\s+to|assuming|only\s+when"
                     r"|contingent|conditional|depending)\b|如果|假如|要是|只要|前提|条件是|除非|的话", I)),
    ("other topic", rx(
        r"\b(?:also|additionally|in\s+addition|plus|besides|moreover|furthermore|separately|another|p\.?\s?s\.?|btw|by\s+the\s+way"
        r"|instead|rather\s+than|going\s+forward|from\s+now\s+on|in\s+(?:the\s+)?future|future|next\s+time|from\s+then\s+on"
        r"|deliver\w*|ship\w*|freight|warehouse|dc|depot|store|address|site|location|account|bank|beneficiary|entity"
        r"|terms?|net\s?\d+|rebate\w*|price\w*|pricing|volume|orders?|contract\w*|exclusiv\w*|quot\w*|credit\s+note|refund\w*|return\w*"
        r"|revis\w*|reissu\w*|re-issu\w*|new|change\w*|switch\w*|moved?|updat\w*|replac\w*|cancel\w*|penalt\w*|interest|fee\w*|charge\w*"
        r"|guarantee\w*|collateral|equity|loan|lend\w*|financ\w*|samples?|stock|inventory|quantity|quantities)\b"
        r"|另外|还有|顺便|此外|同时|以及|再(?:加|给|多|要)|以后|今后|往后|从下|下次|未来|送到|发到|寄到|配送|送货|发货|交货|仓|门店|地址|账户|账号|户名"
        r"|改(?:成|为|到|用)?|换|调整|账期|返利|返点|价格|单价|订单|合同|独家|重开|重新|开票|新的|新开|利息|手续费|费用|担保|抵押|贷款|借款|融资|样品|库存|数量|退货|罚", I)),
]
_QUESTION_MARK = re.compile(r"[?？]")
_WORDISH = re.compile(r"[A-Za-z]{2,}|[一-鿿]")
_PARTICLES = re.compile(r"^[\s吗呢吧哈啊呀哦嘛么\W]*$")

# ---------------------------------------------------------------- (b) settlement sums

# A sum stated as the discount or the net payment: "i.e. we transfer ¥402,000", "也就是扣2940元", "discount of ¥2,100".
_SUM_CUE = rx(
    r"(?:\b(?:discount|deduct\w*|less|minus|saving|savings|save|off|i\.?\s?e\.?|that'?s|that\s+is|which\s+is|equals?|net|transfer\w*"
    r"|wire|remit\w*|pay\w*|send|settle\w*|total|receive|get)\b|=|扣除?|减去?|贴息|贴现息?|折扣|优惠|少付|实付|也就是|即|相当于|等于|共计|合计"
    r"|付|打|转|汇|收到|到账)"
    r"(?:\s*(?:of|is|us|you|only|just|a|the|about|为|是|给你们|给您))*[\s:：,，]*(?:only\s+)?$", I)


# "the ¥150k invoice", "the ¥150k one": another invoice, named, not a sum paid
_NAMED_BILL = rx(r"\s*(?:one\b|invoices?\b|inv\b|bills?\b|(?:的)?(?:发票|货款|票)|那张|这张)", I)


@dataclass(frozen=True)
class Mention:
    doc_id: str
    start: int
    end: int
    kind: str  # money | rate | days | count | date | ref | number
    value: object


def _discount_sums(ob: Obligation) -> tuple[Fraction, Fraction] | None:
    """(discount sum, net payment) in fen for an early-pay discount with a stated rate and invoice amount."""
    if ob.type != ObligationType.IMMEDIATE_DISCOUNT or ob.rate_bp is None or ob.base.amount_fen is None:
        return None
    disc = Fraction(ob.rate_bp * ob.base.amount_fen, 10_000)
    return disc, ob.base.amount_fen - disc


def _within_fen(x: int, y: Fraction) -> bool:
    return abs(Fraction(x) - y) <= 1


def settlement_conflicts(docs: dict[str, SourceDocument], obs: Sequence[Obligation], skip_docs: set[str]) -> list[SourceSpan]:
    """(b): spans of discount sums or net payments that disagree with rate x face (within one fen).

    Only a sum introduced as a deduction or a payment ("i.e. we transfer ¥402,000", "扣2940元") is compared: an
    amount merely named ("the ¥150k one") is another invoice, which the coverage proof reports instead."""
    sums = [(ob, s) for ob in obs if (s := _discount_sums(ob)) is not None]
    if not sums:
        return []
    bases = {ob.base.amount_fen for ob, _ in sums} | {o.base.amount_fen for o in obs if o.base.amount_fen is not None}
    out: list[SourceSpan] = []
    for d in docs.values():
        if d.doc_id in skip_docs:
            continue
        for f in find_money(d.text):
            if f.value in bases:
                continue
            s0, _ = lexicon.sentence_bounds(d.text, f.start)
            if not _SUM_CUE.search(d.text[max(s0, f.start - 24):f.start]) or _NAMED_BILL.match(d.text, f.end):
                continue
            ok = False
            for ob, (disc, net) in sums:
                face = ob.base.amount_fen or 0
                if f.value * 2 > face:
                    ok |= _within_fen(f.value, net)
                else:
                    ok |= _within_fen(f.value, disc)
            if not ok:
                out.append(SourceSpan(doc_id=d.doc_id, start=f.start, end=f.end, text=d.text[f.start:f.end]))
    return out


# ---------------------------------------------------------------- invoice references


def invoice_refs(text: str, start: int = 0, end: int | None = None) -> list[tuple[int, int, str]]:
    end = len(text) if end is None else end
    out = []
    for m in INVOICE_REF_RE.finditer(text, start, end):
        gid = next(g for g in ("a", "b", "c") if m.group(g))
        ref = m.group(0) if gid == "a" else m.group(gid)
        out.append((m.start(), m.end(), ref.strip().upper()))
    return out


# ---------------------------------------------------------------- (a) numeric mentions


def _free(taken: list[tuple[int, int]], s: int, e: int) -> bool:
    return not any(s < te and ts < e for ts, te in taken)


def mentions(doc: SourceDocument) -> list[Mention]:
    """Every numeric mention in `doc`, classified; allow-listed numbers are left out."""
    f = fold(doc.text)
    t = f.text
    taken: list[tuple[int, int]] = []
    out: list[Mention] = []

    def add(s: int, e: int, kind: str, value: object) -> None:
        a, b = f.span(s, e)
        out.append(Mention(doc.doc_id, a, b, kind, value))
        taken.append((s, e))

    for pat in ALLOWED:
        for m in pat.finditer(t):
            if m.group(0).strip():
                taken.append((m.start(), m.end()))
    for m in INVOICE_REF_RE.finditer(t):
        if _free(taken, m.start(), m.end()):
            gid = next(g for g in ("a", "b", "c") if m.group(g))
            add(m.start(), m.end(), "ref", (m.group(0) if gid == "a" else m.group(gid)).strip().upper())
    for m in DATE_RE.finditer(t):
        if _free(taken, m.start(), m.end()):
            add(m.start(), m.end(), "date", m.group(0))
    for r in find_rates(t):
        if _free(taken, r.start, r.end):
            add(r.start, r.end, "rate", r.value)
    for mo in find_money(t):
        if _free(taken, mo.start, mo.end):
            add(mo.start, mo.end, "money", mo.value)
    for m in _DAYS_RE.finditer(t):
        if _free(taken, m.start(), m.end()):
            add(m.start(), m.end(), "days", int(m.group("n")))
    for m in _COUNT_RE.finditer(t):
        if _free(taken, m.start(), m.end()) and not _ZH_HARMLESS.match(t, m.start()):
            raw = m.group("n") or m.group("z") or ""
            add(m.start(), m.end(), "count", _count(raw))
    for m in _CODE_RE.finditer(t):
        if _free(taken, m.start(), m.end()):
            add(m.start(), m.end(), "ref", m.group(0).strip().upper())
    for m in _DIGITS_RE.finditer(t):
        if _free(taken, m.start(), m.end()):
            add(m.start(), m.end(), "number", m.group(0))
    for m in _ZH_NUMERAL_RE.finditer(t):
        if _free(taken, m.start(), m.end()) and not _ZH_HARMLESS.match(t, m.start()):
            add(m.start(), m.end(), "number", m.group(0))
    for m in _ZH_CAPITAL_RE.finditer(t):
        if _free(taken, m.start(), m.end()):
            add(m.start(), m.end(), "number", m.group(0))
    for m in _WORD_NUMBER_RE.finditer(t):
        if _free(taken, m.start(), m.end()):
            add(m.start(), m.end(), "number", m.group(0))
    return sorted(out, key=lambda x: x.start)


_WORD_COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_ZH_COUNTS = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _count(raw: str) -> int | None:
    r = raw.strip().lower()
    if r.isdigit():
        return int(r)
    return _WORD_COUNTS.get(r) or _ZH_COUNTS.get(r)


@dataclass
class _Known:
    money: set[int]
    rates: set[int]
    days: set[int]
    counts: set[int]
    refs: set[str]
    sums: list[tuple[int, Fraction, Fraction]]


def _known(obs: Sequence[Obligation], docs: Sequence[SourceDocument]) -> _Known:
    k = _Known(set(), set(), set(), set(), {d.doc_id.upper() for d in docs}, [])
    k.refs |= {d.filename.upper() for d in docs if d.filename}
    for ob in obs:
        for v in (ob.base.amount_fen, ob.amount_fen):
            if v is not None:
                k.money.add(v)
        if ob.rate_bp is not None:
            k.rates.add(abs(ob.rate_bp))
        for v in (ob.target_terms_days,):
            if v is not None:
                k.days.add(v)
        if ob.target_terms_days is not None and ob.days_delta is not None:
            k.days.add(ob.target_terms_days - ob.days_delta)
        if ob.duration.invoices is not None:
            k.counts.add(ob.duration.invoices)
        if ob.base.events_per_year is not None:
            k.counts.add(ob.base.events_per_year)
        if ob.base.receivable_id:
            k.refs.add(ob.base.receivable_id.upper())
        if ob.type == ObligationType.IMMEDIATE_DISCOUNT:
            k.counts.add(1)  # "this one", "一张": the single invoice it binds
        s = _discount_sums(ob)
        if s is not None:
            k.sums.append((ob.base.amount_fen or 0, *s))
    return k


def _explained(m: Mention, k: _Known) -> bool:
    match m.kind:
        case "money":
            v = int(m.value)  # type: ignore[call-overload]
            return v in k.money or any(_within_fen(v, net if v * 2 > face else disc) for face, disc, net in k.sums)
        case "rate":
            return m.value in k.rates
        case "days":
            return m.value in k.days
        case "count":
            return m.value in k.counts
        case "ref":
            return str(m.value) in k.refs
        case "number":
            raw = str(m.value).replace(",", "")
            if re.fullmatch(r"\d+", raw):
                n = int(raw)
                return n * 100 in k.money or n in k.days or n in k.counts
            if re.fullmatch(r"\d+\.\d{1,2}", raw):
                return int(Decimal(raw) * 100) in k.money  # a bare "420,000.00" (exact: no float on a money path)
            return False
    return False


_KIND_NOTE = {"money": "an amount", "rate": "a rate", "days": "a day count", "count": "a count", "date": "a date",
              "ref": "an invoice or document reference", "number": "a number"}


# ---------------------------------------------------------------- the proof


def _mask(doc: SourceDocument, spans: Sequence[SourceSpan]) -> str:
    chars = list(doc.text)
    for sp in spans:
        if sp.doc_id == doc.doc_id:
            for i in range(sp.start, min(sp.end, len(chars))):
                chars[i] = "\x00"
    text = "".join(chars)
    return _FRAMING.sub(lambda m: "\x00" * len(m.group(0)), text)


def _requests(doc: SourceDocument, spans: Sequence[SourceSpan]) -> list[str]:
    """Cue categories found in what the obligations, courtesy and framing leave of each sentence."""
    masked = _mask(doc, spans)
    found: list[str] = []
    s = 0
    while s < len(masked):
        s0, e0 = lexicon.sentence_bounds(doc.text, s)
        e0 = max(e0, s0)
        stop = e0 + 1 if e0 < len(doc.text) else len(doc.text)
        sentence = masked[s0:stop]
        for chunk in sentence.split("\x00"):
            if not chunk.strip() or _PARTICLES.match(chunk):
                continue
            for name, pat in _REQUEST:
                if pat.search(chunk) and name not in found:
                    found.append(name)
            if _QUESTION_MARK.search(chunk) and _WORDISH.search(chunk.split("?")[0].split("？")[0]) and "question" not in found:
                found.append("question")
        s = max(stop, s + 1)
    return found

# ---------------------------------------------------------------- (f) unread words (fail closed)

# The closed list of filler: function words, courtesy and the vocabulary of the single supported pattern (an early
# payment of a named invoice for a discount). It holds NO noun or verb that could carry a commercial term, and
# nothing that negates, quantifies, conditions beyond "if", or names a means, a period, a document or a party.
# Unsure: leave it out. A queued decision costs one click; a wrong autonomous accept commits the business.
_FILLER_EN = frozenset("""
hi hello hey thanks thank thx cheers regards sincerely please pls plz kindly ok okay advise confirm
i we us our ours you your yours u it its this that these those the a an
can could will would shall do am is are be
we'll we're we'd you'll you're you'd i'll i'd i'm it's that's
and or but so if then
for of on in at by with within from as to
pay payment invoice inv early discount disc off settle setle settel clear take give knock deduct less minus transfer remit agree
full whole open days day
happy glad able
cny rmb yuan
""".split())  # noqa: SIM905
_FILLER_ZH = sorted("""
您好 你好 谢谢 多谢 感谢 辛苦了 辛苦 祝好 此致 敬礼 请 麻烦 劳烦 确认
我方 我们 我司 我 贵方 贵司 您 你们 你
提前 付款 付清 结清 支付 付 结算 全额 整 发票 货款 折扣 贴息 扣除 扣 按 算 个 也就是 是 也 同意 给
这张 那张 这笔 那笔 一张
可以 愿意 想 能 如果 就 即可 就行 行吗 好吗 可以吗
天 元 人民币 的 了 吗 吧 呢 啊 嘛 呀 哦 这 那
""".split(), key=len, reverse=True)  # noqa: SIM905
_ZH_FILLER_RE = re.compile("|".join(map(re.escape, _FILLER_ZH)))

_WORD = re.compile(r"[一-鿿㐀-䶿]+|[^\W\d_一-鿿㐀-䶿]+(?:'[^\W\d_一-鿿㐀-䶿]+)?")
_HONORIFIC = r"(?:总|经理|小姐|先生|女士|老师|老板)"
# Fixed courtesy and framing phrases, set aside whole (their words are not on the list one by one).
_PHRASES = rx(
    r"\bnothing\s+else\s+(?:changes|changing)(?:\s+on\s+our\s+side)?\b|\beverything\s+else\s+(?:stays|remains)\s+(?:the\s+)?same\b"
    r"|\ball\s+else\s+(?:unchanged|the\s+same)\b|\b(?:rest|remainder)\s+of\s+the\s+(?:arrangement|terms|deal)\s+"
    r"(?:(?:is|are|stays|remains)\s+)?(?:unchanged|the\s+same)\b|\b(?:all\s+)?other\s+terms\s+(?:(?:are|remain)\s+)?(?:unchanged|the\s+same)\b"
    r"|\bhope\s+(?:all\s+is|you\s+are|you're)\s+well\b|\blet\s+(?:me|us)\s+know\b|\b(?:this|that|the)\s+one\b"
    r"|\bstraight\s+away\b|\bright\s+now\b|\bthank\s+you\b|\binvoice\s+amount\b|\bi\.\s?e\.|\b(?:call|ring|text|message|contact)\s+me(?:\s+(?:on|at))?\b"
    r"|\bif\s+(?:needed|necessary|you\s+have\s+(?:any\s+)?questions?)\b"
    r"|(?:其他|其它|其余|别的)(?:的)?(?:条款|条件)?(?:都)?不变|就这一?张", I)
# "Hi Chen," / "Dear Mr Wang," / "Hi 陈总" / "陈总好": a greeting and the name it addresses, at the start of a line.
_SALUTATION = rx(
    r"^[ \t]*(?:(?:hi|hello|hey|dear|good\s+(?:morning|afternoon|evening)|morning)\b"
    rf"(?:[ \t]+(?:(?-i:[A-Z][a-z]{{1,15}})(?:[ \t]+(?-i:[A-Z][a-z]{{1,15}})){{0,2}}(?=[ \t]*[,，:：!！\n-])|[一-鿿]{{1,3}}{_HONORIFIC}))?"
    rf"|[一-鿿]{{1,3}}{_HONORIFIC}(?:(?:你|您)?好|(?=[，,:：])))", I | re.MULTILINE)
# A sign-off at the end, with at most a three-word capitalised name on the next line.
_SIGNOFF = rx(
    r"(?:\b(?:best|kind|warm)\s+regards|\bregards|\bsincerely|\bcheers|\bthanks|\bthank\s+you|\bbest|\bbr)\b[ \t]*[,!.]?[ \t]*"
    r"(?:\n[ \t]*(?-i:[A-Z][A-Za-z.'-]{0,19})(?:[ \t]+(?-i:[A-Z][A-Za-z.'-]{0,19})){0,2})?\s*$", I)
# A signature: a name of up to three capitalised words alone on a line directly above contact details.
_SIGNATURE_NAME = rx(
    r"^[ \t]*(?-i:[A-Z][a-z.'-]{1,19})(?:[ \t]+(?-i:[A-Z][a-z.'-]{1,19})){0,2}[ \t]*\n"
    r"(?=[ \t]*(?:(?:tel|phone|mob(?:ile)?|fax|cell|e-?mail|wechat|whatsapp)[ \t]*[:：]|[\w.+-]+@))", I | re.MULTILINE)
# "before 3 pm" in Chinese: the clock time is allow-listed, its "前" / "左右" is the tail of the same phrase.
_TIME_TAIL = rx(r"(?:上午|下午|晚上|早上)?\d{1,2}\s*点(?:半|\d{1,2}分?)?(?:之前|以前|前|左右)", I)
# Contact details and the label of a contact line.
_CONTACT_LABEL = rx(r"^[ \t]*(?:subject|tel|phone|mob(?:ile)?|fax|cell|e-?mail|date|sent|wechat|whatsapp|电话|手机|传真|邮箱|日期|微信)[ \t]*[:：]",
                    I | re.MULTILINE)

_FOREIGN_CURRENCY = rx(
    r"\$|€|£|₩|₹|₽|(?<![A-Za-z])(?:usd|us\s?dollars?|dollars?|eur|euros?|gbp|pounds?|sterling|hkd|hk\s?dollars?|jpy|yen|sgd|aud|cad|chf"
    r"|krw|twd|inr|thb|myr|nzd|bucks)(?![A-Za-z])|美元|美金|美刀|港币|港元|欧元|英镑|日元|日圆|新币|新元|澳元|加元|韩元|台币|卢比|泰铢|林吉特", I)
_PERIOD = (r"(?:week|wk|fortnight|month|mo|day|quarter|year|yr|annum|diem)\b")
_RATE_PERIOD = rx(
    rf"\s*(?:(?:per|a|an|each|every|/)\s*{_PERIOD}|(?:weekly|monthly|daily|quarterly|annual(?:ly)?|yearly)\b)"
    r"|\s*(?:每|/)\s*(?:个)?(?:周|星期|礼拜|月|天|日|季度?|年)|\s*(?:周息|月息|日息|年息|年化)", I)
_ZH_PERIODIC = rx(r"每\s*(?:个)?(?:周|星期|礼拜|月|天|日|季度?|年)[^。.;；\n]{0,12}?(?:\d\s*[%％]|百分之|千分之|个点|折扣|贴息|返)"
                  r"|(?:周|月|日)(?:息|利率)", I)
_NOT_SUPPLIED = rx(
    r"\battach(?:ed|ment|ments)?\b|\benclos(?:ed|ure|ures)\b|\bas\s+per\b|\bper\s+the\b|\bsee\s+(?:the\s+)?(?:annex|appendix|schedule|exhibit|below|above)\b"
    r"|\b(?:annex|appendix|schedule|exhibit)\b|附件|附表|附录|附后|见附|详见|如附|所附|随附|另附|见下表|见上表", I)


def _residue(doc: SourceDocument, known: _Known) -> str:
    """The folded text of `doc` with the numbers and references the obligations explain, contact details,
    greetings, sign-offs and fixed courtesy phrases blanked out.

    The obligations' own source spans are deliberately NOT blanked: a span is the clause the compiler read, and it can
    swallow a rider ("pay invoice X tomorrow by bank draft if you take 0.5% off" is one clause). The words inside a
    span must be on the filler list too, which the vocabulary of the supported pattern is."""
    f = fold(doc.text)
    gone = bytearray(len(doc.text))
    for m in mentions(doc):
        if m.kind != "date" and _explained(m, known):
            for i in range(m.start, min(m.end, len(gone))):
                gone[i] = 1
    text = "".join(" " if gone[f.starts[i]] else ch for i, ch in enumerate(f.text))

    def blank(pat: re.Pattern[str], s: str) -> str:
        return pat.sub(lambda m: " " * len(m.group(0)), s)

    for pat in (_SIGNATURE_NAME, _TIME_TAIL, *ALLOWED[:5], _CONTACT_LABEL, _SALUTATION, _SIGNOFF, _PHRASES):
        text = blank(pat, text)
    return text


def _unread_tokens(residue: str) -> list[str]:
    """The words of `residue` that are not on the filler list (Latin words and runs of CJK), in order, once each."""
    out: list[str] = []
    for m in _WORD.finditer(residue):
        w = m.group(0)
        if re.match(r"[一-鿿㐀-䶿]", w):
            toks = [x for x in _ZH_FILLER_RE.sub(" ", w).split() if x]
        else:
            toks = [] if w.lower() in _FILLER_EN else [w.lower()]
        out.extend(x[:20] for x in toks if x not in out)
    return out


def _unread(docs: Sequence[SourceDocument], known: _Known, note: Callable[[str], None]) -> None:
    for d in docs:
        t = fold(d.text).text
        if _FOREIGN_CURRENCY.search(t):
            note("non-CNY currency stated")
        if any(_RATE_PERIOD.match(t, r.end) for r in find_rates(t)) or _ZH_PERIODIC.search(t):
            note("a rate is stated per a period other than the invoice")
        if len(docs) < 2 and _NOT_SUPPLIED.search(t):
            note("the message refers to a document that was not supplied")
    seen: list[str] = []
    for d in docs:
        seen.extend(x for x in _unread_tokens(_residue(d, known)) if x not in seen)
    if seen:
        note("text not read into the terms: " + ", ".join(f"'{x}'" for x in seen[:5]) + (", ..." if len(seen) > 5 else ""))


def prove(
    docs: Sequence[SourceDocument],
    obligations: Sequence[Obligation],
    *,
    status: CompileStatus,
    abstentions: Sequence[Abstention],
    data_requests: Sequence[DataRequest],
    authority_claims: Sequence[AuthorityClaim],
    funding_claims: Sequence[UnsolicitedFundingClaim],
) -> tuple[bool, list[str]]:
    notes: list[str] = []

    def note(msg: str) -> None:
        if msg not in notes:
            notes.append(msg)

    if status != CompileStatus.COMPILED:
        note(f"the compilation is {status.value}, not clean")
    material = [a for a in abstentions if not a.field.startswith("note:")]
    if material:
        note("a term was not read (" + ", ".join(dict.fromkeys(a.field for a in material)) + ")")
    for a in abstentions:
        if a.field.endswith(".rate_bp.derived"):
            note("a discount rate is derived from a net amount, not stated")
        if a.field.endswith(".base.approximate"):
            note("a base amount is stated only approximately")
    if not obligations:
        note("no term was read")
    # "pay it right now at 0.5%": an urgency word that is the discount's own settlement time is not a claim
    own = [sp for ob in obligations for sp in ob.spans]
    claims = [c for c in authority_claims
              if not (c.kind == "URGENCY" and any(sp.doc_id == c.span.doc_id and sp.start <= c.span.start and c.span.end <= sp.end
                                                  for sp in own))]
    if claims:
        note("the message asserts authority or a prior agreement (" + ", ".join(dict.fromkeys(c.kind for c in claims)) + ")")
    if data_requests:
        note("the message asks for protected data")
    if funding_claims:
        note("the message carries an unsolicited funding offer")
    for ob in obligations:
        if ob.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
            note("a concession is claimed as previously agreed")
        if ob.unresolved:
            note(f"{ob.type.value} leaves {', '.join(ob.unresolved)} unresolved")
        if ob.type == ObligationType.IMMEDIATE_DISCOUNT:
            if ob.rate_bp is None:
                note("a discount has no stated rate")
            if ob.base.amount_fen is None:
                note("a discount does not state its invoice amount")

    # (a) and (e): every numeric mention of every document
    known = _known(obligations, docs)
    for d in docs:
        for m in mentions(d):
            if m.kind == "date":
                note("a settlement date or window is stated but not read into the terms")
            elif not _explained(m, known):
                note(f"{_KIND_NOTE[m.kind]} in {d.doc_id} is not accounted for by the extracted terms")
        if TIMING_RE.search(fold(d.text).text):
            note("a settlement date or window is stated but not read into the terms")

    # (c): requests, conditions, questions and other topics
    spans = [sp for ob in obligations for sp in ob.spans]
    for d in docs:
        for cue in _requests(d, spans):
            note(f"{d.doc_id} holds a {cue} beyond the extracted terms")

    # (f): unread words, other currencies, per-period rates, references to what was not supplied
    _unread(docs, known, note)

    return (not notes), notes


__all__ = ["INVOICE_REF_RE", "Mention", "invoice_refs", "mentions", "prove", "settlement_conflicts"]
