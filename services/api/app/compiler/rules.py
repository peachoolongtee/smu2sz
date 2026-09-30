"""RulesBackend: a deterministic zh + en grammar that fills the same extraction schema as the model.

It is the offline fallback and the source of the recorded demo cache. Every quote it emits is a regex
match over the document text, so it is an exact substring by construction; grounding still re-checks.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.compiler.base import OfferResult, TermSheetResult
from app.compiler.lexicon import (
    AS_USUAL_RE,
    clauses,
    find_authority_claims,
    find_data_requests,
    find_funding_claims,
    find_quantities,
    sentence_bounds,
)
from app.compiler.parsing import MONEY_PAT, NUMBER_WORD, RATE_PAT, find_money, parse_money, rx
from app.compiler.schema import (
    ClauseField,
    OfferExtraction,
    Quote,
    TermSheetExtraction,
    UnresolvedKey,
    XClause,
    XMissing,
    XObligation,
)
from app.domain.models import (
    BaseKind,
    Contingency,
    DurationKind,
    FacilityKind,
    ObligationType,
    SourceDocument,
)

RULES_MODEL_ID = "rules-v1"

I = re.IGNORECASE
AMT = MONEY_PAT
RATE = RATE_PAT
# An intra-sentence gap: anything but a sentence terminator (a '.' inside a number is allowed).
_G = r"(?:[^.。;；!！?？\n]|\.(?=\d))"


def G(n: int) -> str:
    return rf"{_G}{{0,{n}}}?"


# ---------------------------------------------------------------- phrase grammar

# Settling verbs, with the common typos of a hurried message ("setle", "settel", "pymt").
_SETTLE = r"(?:settle|settling|settled|settlement|setle|setl(?:e|ing)|settel|settl|sttle)"
_EARLY_VERB = rf"(?:{_SETTLE}|pay|paying|payment|pymt|pay\s+off|clear|release|releasing|remit|remitting|transfer|wire)"
# A short, stated settlement window: "within 2 working days", "in 3 business days", "T+2".
_WINDOW = (r"(?:within|in)\s+(?:the\s+next\s+)?(?:[1-9]|1[0-4]|one|two|three|four|five|six|seven|a\s+couple\s+of|a\s+few)"
           r"\s+(?:working\s+|business\s+|banking\s+|calendar\s+)?days?|T\s?\+\s?[0-9]")
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?"
          r"|nov(?:ember)?|dec(?:ember)?)\.?")
_WEEKDAY = r"(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day)?\.?"
# A stated calendar day: "Oct 8", "8 October", "the 8th", "Monday", "10/8".
DATE_EN = (rf"(?:{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}|the\s+\d{{1,2}}(?:st|nd|rd|th)"
           rf"|(?:next\s+|this\s+|coming\s+)?{_WEEKDAY}|\d{{1,2}}/\d{{1,2}})")
# "early" in "due early Nov" names the due date, not an early payment.
_EARLY_WORD = (rf"(?:(?<!due\s)early|ahead\s+of\s+(?:time|schedule|the\s+due\s+date)|before\s+(?:the\s+)?due(?:\s+date)?|now|today"
               rf"|tomorrow|tmrw|tmr|immediately|upfront|up\s+front|in\s+advance|right\s+away|straight\s+away|at\s+once|this\s+week"
               rf"|{_WINDOW}|(?:on|by)\s+{DATE_EN})")
# What links the settlement to its price: "at 1%", "for 1% off", "if you give us 0.8%", "less 1.2%".
_PRICE_LINK = (r"(?:at|for|with|against|in\s+exchange\s+for|less|minus|net\s+of"
               r"|(?:if|provided(?:\s+that)?|as\s+long\s+as)\s+(?:you|u)\s+(?:can\s+|could\s+)?(?:give|allow|grant|offer|knock|take)(?:\s+us)?)")
# The Chinese verbs of paying an invoice ahead of time: 提前付 / 付款 / 付清 / 支付 / 结清 / 还 ...
_EARLY_ZH = r"提前(?:付(?:款|清|掉)?|支付|结清|结算|结账|回款|还款|还清|还|打款|转账)"

DISCOUNT = [
    # "settle the ¥420k early at 1.2%", "pay this one early at 1.5%", "pay early for a 1.2% discount"
    rx(rf"\b{_EARLY_VERB}\b{G(60)}\b{_EARLY_WORD}\b{G(40)}\b{_PRICE_LINK}\s+(?:a\s+|an\s+)?(?P<rate>{RATE})(?:\s+(?:discount|disc\b\.?|off))?", I),
    # "Early pay at 1.5%", "early-payment discount of 2%", "early settlement at 1.2%", "rate for early settlement is 0.8%"
    rx(rf"\bearly[- ]?(?:pay(?:ment)?|settlement|{_SETTLE})\b(?:\s+discount)?{G(40)}(?:\b(?:at|of|for|with|taken|applied|deducted|claimed|discount|less|minus|is|would\s+be|will\s+be)\b\s*[:：]?|[:：=])\s*(?P<rate>{RATE})", I),
    # "…, early at 0.5%": the settling verb is implied by the invoice around it
    rx(rf"(?<!due\s)\bearly\s+(?:at|for|with|less|minus)\s+(?:a\s+|an\s+)?(?P<rate>{RATE})(?:\s+(?:discount|off))?", I),
    # "1.2% for early settlement", "a 2% discount for paying early", "1.5% early-payment discount"
    rx(rf"(?P<rate>{RATE})\s+(?:discount\s+|off\s+)?(?:for|on|in\s+exchange\s+for|if\s+we)\s+(?:an?\s+)?(?:early|prompt|immediate)\s*(?:settlement|payment|pay)?", I),
    rx(rf"(?P<rate>{RATE})\s+(?:discount\s+|off\s+)?for\s+(?:paying|settling)\s+(?:\w+\s+){{0,3}}?{_EARLY_WORD}", I),
    rx(rf"(?P<rate>{RATE})\s+early[- ]?(?:pay(?:ment)?|settlement|{_SETTLE})(?:\s+discount)?", I),
    # zh: "提前付款，折扣1.2%", "提前结清42万货款，折扣1.2%", "提前付，扣1.2%", "按1.5%提前付款"
    rx(rf"{_EARLY_ZH}{G(25)}(?P<rate>{RATE})"),
    rx(rf"(?P<rate>{RATE}){G(8)}(?:的)?(?:折扣|贴息)?{G(4)}{_EARLY_ZH}"),
]

# A discount rate with no early-payment wording of its own ("knock 1% off", "折扣1%"). It is an immediate
# discount only when its sentence has an early-payment cue and its clause names no future period.
DISCOUNT_RATE = [
    rx(rf"\b(?:take|knock|shave|deduct|trim|lop|cut|strip)\s+(?:off\s+)?(?:a\s+|an\s+|another\s+|just\s+|only\s+)?(?P<rate>{RATE})(?:\s+off)?", I),
    rx(rf"(?:\b(?:a|an)\s+)?(?P<rate>{RATE})\s+(?:cash\s+)?(?:discount\b|disc\b\.?|off\b|reduction\b|deduction\b)", I),
    rx(rf"\b(?:discount|reduction|deduction)\s*(?:of|at|is|[:：=])?\s*(?P<rate>{RATE})", I),
    # "less 1.2%", "minus 0.8%", "net of 1%"
    rx(rf"\b(?:less|minus|net\s+of)\s+(?:a\s+)?(?P<rate>{RATE})", I),
    rx(rf"(?:折扣|扣|减|优惠|少收|让|给)\s*(?:我们|给我们|个|我们个)?\s*(?P<rate>{RATE})"),
    rx(rf"(?P<rate>{RATE})\s*(?:的)?(?:现金)?(?:折扣|优惠|扣减|贴息|贴现息?)"),
    # 贴息 / 贴现息 is the discount taken for paying early: "贴息0.5%", "按千分之八扣贴现息", "按99.3折付"
    rx(rf"(?:贴息|贴现息?|贴现率)\s*(?:按|是|为|[:：])?\s*(?P<rate>{RATE})"),
    rx(rf"按\s*(?P<rate>{RATE})\s*(?:扣|收|算|付|支付|结算|结清)"),
]
# An early-payment cue anywhere in the sentence: "pay it today", "settle straight away", "马上付".
EARLY_CUE = rx(
    rf"\b(?:pay|paying|paid|pymt|{_SETTLE}|clear|clearing|wire|wiring|remit|remitting|transfer|release|releasing)\b"
    rf"{G(50)}\b(?:(?<!due\s)early|(?<!from\s)now(?!\s+on)|today|tonight|tomorrow|tmrw|tmr|immediately|straight\s+away|right\s+away|at\s+once|this\s+week"
    r"|upfront|up\s+front|in\s+advance|ahead\s+of\s+(?:time|schedule|the\s+due\s+date)|before\s+(?:the\s+|its\s+)?due(?:\s+date)?"
    rf"|on\s+receipt|{_WINDOW})\b"
    r"|\b(?:today|immediately|straight\s+away|right\s+away)\b[\s,]+(?:we'?ll|we\s+will|we\s+can|we)\s+(?:pay|settle|clear|wire)\b"
    rf"|\b(?:early|immediate|prompt)[- ]?(?:payment|settlement|pay|{_SETTLE})\b"
    rf"|{_EARLY_ZH}|(?:马上|立即|立刻|今天|明天|现在|即刻|当天|尽快|早点|提早)就?(?:付|支付|结清|结算|打款|转账|付清)"
    r"|(?:[一二两三四五\d]|几)\s*(?:个)?(?:工作日|天)内(?:就)?(?:付|支付|结清|打款|转账|付清)"
    # a stated day or week, then paying: "下周一全款打过去", "这周全部付清", "10月8号可以全额付"
    r"|(?:这周|本周|这个星期|下周[一二三四五六日天]?|周[一二三四五六日天]|星期[一二三四五六日天]|礼拜[一二三四五六日天]|\d{1,2}\s*[号日]"
    r"|明天|今天|后天|今晚)[^，。；;！!？?\n]{0,8}?(?:付|支付|结清|结算|打款|转账|付清|打过去|转过去|汇过去|汇款)", I)
# The invoice a discount applies to, with its stated amount: "the ¥420,000 invoice", "42万的发票", "invoice for ¥420k".
# An invoice number the buyer quotes: "INV-2026-0871", "RCV-A", "invoice no. 5531", "发票号 12345".
INVOICE_REF_ID = (r"(?:\b(?:INV|RCV|FP)[-‐_]?(?=[A-Z0-9-]*\d|[A-Z]\b)[A-Z0-9][A-Z0-9-]*"
                  r"|(?<=(?i:invoice)\s)(?:(?i:no)\.?\s*|(?i:number)\s*|#\s*)[A-Z0-9][A-Z0-9-]{2,}"
                  r"|(?<=发票号)\s*[:：]?\s*[A-Z0-9][A-Z0-9-]{2,})")
INVOICE_AMOUNT = [
    rx(rf"(?P<amt>{AMT})\s*(?:的)?\s*(?:(?:那|这|该)?(?:张|笔)?\s*(?:open\s+|outstanding\s+|unpaid\s+)?(?:invoice|inv\b|bill|发票|货款)"
       rf"|(?:那|这|该)?张票|票(?![据号])|(?:那|这)张)", I),
    rx(rf"\b(?:invoice|bill)\s+(?:of|for|worth)\s+(?P<amt>{AMT})", I),
    rx(rf"(?:发票|货款)\s*(?P<amt>{AMT})"),
    # "the full ¥420,000 on your inv", "¥420,000 for your invoice"
    rx(rf"(?P<amt>{AMT})\s+(?:on|for|of)\s+(?:your|the|our|this|that)\s+(?:invoice|inv\b|bill)", I),
    # "invoice RCV-A (¥420,000)", "Re INV-2026-0871 (RMB 86,500.00)", "invoice (¥420,000)"
    rx(rf"(?:\b(?i:invoice|inv\.?|bill)\s+(?:(?i:no\.?|number)\s*|#\s*)?(?:[A-Z0-9][A-Z0-9-]*\s*)?|{INVOICE_REF_ID}\s*)[(（:：]\s*(?P<amt>{AMT})"),
]
INVOICE_WORD = rx(r"\binvoices?\b|\binv\b|\bbills?\b|发票|货款|这笔款|这张|那张|张票|的票", I)

_TERMS_WORD = r"(?:(?:standard\s+|payment\s+|credit\s+)*terms)"
# zh verbs of changing the payment terms: 延长到 / 缩到 / 缩短为 / 改成 / 调整至 / 减到 ...
_ZH_TERMS_VERB = r"(?:延长|延|拉长|放宽|增加|加|改|调整|调|缩短|缩|减少|减|降低|降|压缩|压|提前|变|定|统一)了?(?:为|到|至|成)"
# "instead of 45", "instead of the usual 45", "rather than our current 45"
_FROM_WORDS = r"(?:instead\s+of|rather\s+than|up\s+from|down\s+from|from)\s+(?:(?:the|our|your|my)\s+)?(?:(?:usual|current|normal|standard|existing|present|agreed)\s+)?"
_ASK_DAYS = r"(?:take|give\s+us|allow\s+us|grant\s+us|we\s+need|we\s+want|we'?d\s+like|let\s+us\s+have|can\s+we\s+(?:have|get)|could\s+we\s+(?:have|get)|we'?d\s+need)"
TERMS = [
    # "Take 45 days on the next three invoices instead of 30"
    # "we'll pay you in 30 days instead of 45", "move to paying you on 30 days rather than 45"
    (rx(rf"\b(?:{_ASK_DAYS}|pay(?:ing)?\s+(?:you\s+|us\s+|the\s+invoices?\s+)?(?:in|at|on|within|after))\s+(?P<to>\d+)\s*[-‑]?\s*days?\b{G(45)}\b{_FROM_WORDS}(?P<from>\d+)(?:\s*[-‑]?\s*days?)?", I), 0.9),
    # "extend our standard terms from 45 to 60 days"
    (rx(rf"\b(?:extend|move|change|switch|lengthen|increase|shorten|reduce|cut|bring|adjust)\w*\b{G(30)}\b{_TERMS_WORD}{G(10)}\bfrom\s+(?P<from>\d+)(?:\s*[-‑]?\s*days?)?\s+to\s+(?P<to>\d+)\s*[-‑]?\s*days?", I), 0.95),
    # "extend our standard terms to 60 days"
    (rx(rf"\b(?:extend|move|change|switch|set|lengthen|increase|shorten|reduce|cut|bring|adjust|push)\w*\b{G(30)}\b{_TERMS_WORD}{G(12)}\bto\s+(?P<to>\d+)\s*[-‑]?\s*days?", I), 0.95),
    # "move you to 30-day terms", "switch us to Net 60"
    (rx(r"\b(?:move|put|switch|change|shift|go|take|pay)\w*\s+(?:(?:you|us)\s+)?(?:to|onto|on)\s+(?:(?P<to>\d+)\s*[-‑]?\s*days?\s+(?:payment\s+)?terms|net\s?(?P<to2>\d+))", I), 0.9),
    # "Standard terms going forward: 60 days", "payment terms: 60 days"
    (rx(rf"\b{_TERMS_WORD}{G(25)}[:：]\s*(?P<to>\d+)\s*[-‑]?\s*days?", I), 0.9),
    # "terms of 60 days", "60-day terms", "Net 60"
    (rx(rf"\b{_TERMS_WORD}\s+of\s+(?P<to>\d+)\s*[-‑]?\s*days?", I), 0.8),
    (rx(r"\b(?P<to>\d+)\s*[-‑]?\s*days?\s+(?:payment\s+|credit\s+)?terms\b", I), 0.75),
    (rx(r"\bnet\s?(?P<to>\d+)\b", I), 0.75),
    # "give us 60 days", "we'd like 55 days on the next invoice" (the ask itself, no "instead of")
    (rx(rf"\b{_ASK_DAYS}\s+(?P<to>\d+)\s*[-‑]?\s*days?\b(?!\s+(?:early|earlier|sooner|ahead|before))", I), 0.8),
    # "we'll pay at 60 days", "we pay on 45-day terms" ("pay within 10 days" is early payment, not terms)
    (rx(r"\b(?:we'?ll\s+|we\s+will\s+|we\s+)?pay\s+(?:at|on)\s+(?P<to>\d+)\s*[-‑]?\s*days?\b", I), 0.8),
    # "we'll pay you in 35 days from now on": a length of 15 days or more is a payment term, not an early payment
    (rx(r"\b(?:we'?ll|we\s+will|we\s+can|we'?d|we)\s+(?:be\s+)?pay(?:ing)?\s+(?:you\s+)?(?:in|at|on|within|after)\s+(?P<to>1[5-9]|[2-9]\d|1\d\d)\s*[-‑]?\s*days?\b", I), 0.75),
    # zh: "账期从30天延长到45天", "账期延长到60天", "以后账期改为60天"
    (rx(rf"账期{G(12)}从\s*(?P<from>\d+)\s*天?{G(6)}{_ZH_TERMS_VERB}\s*(?P<to>\d+)\s*天"), 0.95),
    (rx(rf"账期{G(12)}{_ZH_TERMS_VERB}\s*(?P<to>\d+)\s*天"), 0.95),
    (rx(rf"账期{G(12)}(?:改|调|延长?|缩短?|变|放到|拉到)\s*(?P<to>\d+)\s*天"), 0.9),
    # "从45天缩到30天付款", "我们以后30天付款，不再是45天"
    (rx(rf"从\s*(?P<from>\d+)\s*天{G(4)}{_ZH_TERMS_VERB}\s*(?P<to>\d+)\s*天(?:付款|结算|回款|账期)"), 0.9),
    (rx(r"账期(?:都|一律|统一|全部)(?:按|是)?\s*(?P<to>\d+)\s*天"), 0.9),
    (rx(r"(?P<to>\d+)\s*天(?:的)?账期"), 0.8),
    (rx(r"账期\s*[:：为是]?\s*(?P<to>\d+)\s*天"), 0.8),
]

_PERIOD = r"(?:next|following|coming)\s+(?:quarter|month|year|season|half)(?:'s|’s)?"
_PERIOD_ZH = r"(?:下(?:个)?季度|下个?月|明年|下半年|下一季度?)"
_CAP = rf"(?:,?\s+(?:purchases|orders|volume|spend|buying)?\s*(?:of|on)?\s*(?:up\s+to|a\s+maximum\s+of|capped\s+at|at\s+most|no\s+more\s+than)\s+(?P<cap>{AMT})(?:\s+(?:of|in)\s+(?:orders|purchases|volume|spend))?)"

# Rebate rates. The base and the duration are read from the rate's clause (see _rebates), not from the
# pattern: a named period ("next quarter", 下季度) binds one period's purchases; an unbounded promise
# ("going forward", "everything we buy", 以后所有) is perpetual; no stated base is unresolved scope.
REBATE = [
    # "1% off next quarter", "1% on next quarter" (EX01B), "0.75% off next quarter's purchases of up to ¥400,000"
    rx(rf"(?P<rate>{RATE})\s+(?:rebate\s+|discount\s+|off\s+|reduction\s+|back\s+)?(?:off\s+|on\s+|for\s+|from\s+|across\s+)?(?:the\s+|our\s+)?{_PERIOD}", I),
    # "rebate of 1%", "a volume rebate of 2%"
    rx(rf"\b(?:volume\s+|loyalty\s+)?(?:rebate|discount|reduction|cashback|cash\s+back)\s+of\s+(?P<rate>{RATE})", I),
    # "1% off for the volume", "1% off this order"
    rx(rf"(?P<rate>{RATE})\s+(?:off|discount|rebate)\s+(?:for|on)\s+(?:the\s+|this\s+|that\s+)?(?:volume|order|purchase|PO)\b", I),
    # "a 2% rebate", "2% off", "0.5% back", "half a percent back"
    rx(rf"(?P<rate>{RATE})\s+(?:volume\s+|loyalty\s+|annual\s+|year-end\s+|cash\s*)?(?:rebate|off|discount|back|cashback|reduction)\b(?!\s+for\s+(?:early|prompt|paying|settling))", I),
    rx(rf"\b(?:give|pay|send|hand)\s+(?:us\s+)?back\s+(?P<rate>{RATE})", I),
    # zh: "1%的返利", "返0.8%", "再返1%", "给我们返点0.5%"
    rx(rf"(?P<rate>{RATE})\s*(?:的)?(?:返利|返点|回扣|让利|返现|折扣|优惠)"),
    rx(rf"(?:返利|返点|返还|返现|回扣|让利|返|折扣|优惠)\s*(?:给)?(?:我们|我方)?\s*(?P<rate>{RATE})"),
]
PERIOD_RE = rx(rf"{_PERIOD}|\bthis\s+(?:quarter|month|season)\b|{_PERIOD_ZH}|本季度|这个季度", I)
CAP_RE = rx(
    rf"\b(?:up\s+to|a\s+maximum\s+of|capped\s+at|at\s+most|no\s+more\s+than|maximum\s+of|max\.?)\s+(?P<cap>{AMT})"
    rf"|(?:最多|不超过|上限|封顶|最高)\s*(?:为|是)?\s*(?P<capz>{AMT})", I)
# A stated base for a period rebate: "next quarter's ¥300,000 order", "orders worth ¥300k", "30万的采购"
REBATE_BASE_RE = rx(
    rf"(?P<b1>{AMT})\s+(?:of\s+)?(?:(?:purchase|order)\s+)?(?:orders?|purchases?|volume|spend|PO)\b"
    rf"|\b(?:orders?|purchases?|volume|spend)\s+(?:of|worth|totall?ing)\s+(?P<b2>{AMT})"
    rf"|(?P<b3>{AMT})\s*(?:左右|上下)?\s*(?:的)?(?:采购|订单|货款|货(?!款))"
    # a hedged base, bound at the stated figure (grounding notes it): "order (approx. ¥400,000)", "~¥400k of orders"
    rf"|\b(?:orders?|purchases?|PO)\b{G(25)}[(（]?\s*(?:approx\.?|approximately|about|around|roughly|circa|est\.?|estimated|~|≈|c\.)\s*(?P<b4>{AMT})"
    rf"|(?:approx\.?|approximately|about|around|roughly|~|≈)\s*(?P<b5>{AMT})\s+(?:of\s+|in\s+)?(?:orders?|purchases?|volume|spend)\b"
    rf"|(?:那|这|该)单\s*(?:大约|大概|约)?\s*(?P<b6>{AMT})", I)

CLAIMED = [
    # "the 2% rebate we agreed last month", "the 60-day terms you already agreed", "the 60-day terms you agreed with us"
    rx(
        rf"(?:the\s+|that\s+|our\s+)?(?:(?P<rate>{RATE})\s+|(?P<days>\d+)\s*[-‑]?\s*days?\s+)?(?:(?:payment|credit)\s+)?"
        rf"(?:rebate|discount|terms|credit|price\s+cut|price|arrangement|deal|concession|extension)\s+(?:that\s+)?(?:we|you)\s+"
        rf"(?:have\s+)?(?:already\s+|previously\s+|both\s+)?(?:agreed|promised|approved|offered|gave\s+us)"
        rf"(?:\s+(?:to|on|with\s+us|with\s+you|last\s+(?:week|month|time|quarter|year)|earlier|before|previously))*", I),
    # "you already agreed to 60-day terms", "you promised us a 2% rebate"
    rx(
        rf"\b(?:we|you)\s+(?:have\s+)?(?:already\s+|previously\s+)?(?:agreed\s+to|promised(?:\s+us)?|approved)\s+(?:a\s+|an\s+|the\s+)?"
        rf"(?:(?P<rate>{RATE})\s+(?:rebate|discount|credit|price\s+cut)|(?P<days>\d+)\s*[-‑]?\s*days?(?:\s+(?:payment\s+)?terms)?)", I),
    # zh: "上个月你们已经同意的2%返利", "之前说好的60天账期"
    rx(
        rf"(?:上(?:个)?(?:月|次|周|季度)|之前|以前|早先|已经?){G(10)}(?:说好|谈好|同意|答应|批准|约定|商定)(?:过|了)?的?{G(6)}"
        rf"(?:(?P<rate>{RATE})\s*(?:的)?(?:返利|返点|折扣|优惠)|(?P<days>\d+)\s*天(?:的)?账期)"),
]

PRICE_ADJ = [
    # "we'll add a 0.5% loyalty credit", "we'll pay you a 0.5% premium"
    (rx(rf"\b(?:we'?ll|we\s+will|we\s+can|we\s+could)\s+(?:add|give\s+you|pay(?:\s+you)?|offer(?:\s+you)?|throw\s+in|include)\s+(?:a\s+|an\s+)?(?P<rate>{RATE})\s+(?:loyalty\s+|volume\s+|bonus\s+|goodwill\s+|price\s+)?(?:credit|bonus|premium|uplift|price\s+increase|top[- ]?up)", I), Contingency.CONTINGENT),
    # "a 0.45% price adjustment on future invoices"
    (rx(rf"(?:a\s+)?(?P<rate>{RATE})\s+(?:price\s+(?:adjustment|increase|uplift|rise)|(?:higher|more)\s+(?:prices?|per\s+unit|on\s+(?:the\s+)?price))", I), Contingency.FIRM),
    # "our price goes up 0.5%", "prices will go up by 0.5%", "raise the unit price by 0.5%", "we'll pay 0.3% more"
    (rx(rf"\bprices?\s+(?:will\s+|would\s+|can\s+)?(?:go(?:es)?|going|move[sd]?|rise[sd]?|increase[sd]?)(?:\s+up)?\s+(?:by\s+)?(?P<rate>{RATE})", I), Contingency.FIRM),
    (rx(rf"\b(?:raise|raising|increase|increasing|lift|lifting|put\s+up|bump\s+up|mark\s+up)\s+(?:our|the|your|its|unit|all)?\s*(?:unit\s+)?prices?\s+(?:by\s+)?(?P<rate>{RATE})", I), Contingency.FIRM),
    (rx(rf"\b(?:we'?ll|we\s+will|we\s+can|we\s+could|we'?d)\s+(?:happily\s+|gladly\s+)?pay\s+(?:you\s+)?(?P<rate>{RATE})\s+(?:more|extra|higher)", I), Contingency.FIRM),
    (rx(rf"(?:价格|单价|货价)(?:上调|提高|上浮|上涨|涨|提升)了?\s*(?P<rate>{RATE})"), Contingency.FIRM),
    (rx(rf"(?:涨价|加价|多付)\s*(?P<rate>{RATE})"), Contingency.FIRM),
    # price cuts: grounding books these with a negative rate (a cost to the supplier)
    (rx(rf"(?:a\s+)?(?P<rate>{RATE})\s+(?:price\s+(?:reduction|cut|decrease|drop)|(?:lower|cheaper)\s+(?:unit\s+)?prices?|cut\s+(?:in|to|on)\s+(?:the\s+|your\s+|our\s+)?(?:unit\s+)?prices?)", I), Contingency.FIRM),
    (rx(rf"\b(?:reduce|reducing|cut|cutting|lower|lowering|decrease|decreasing|drop|dropping)\s+(?:our|the|your|its|unit|all)?\s*(?:unit\s+)?prices?\s+(?:by\s+)?(?P<rate>{RATE})", I), Contingency.FIRM),
    (rx(rf"\bprices?\s+(?:will\s+|would\s+|need\s+to\s+|must\s+|should\s+|to\s+)?(?:go(?:es)?\s+down|drop|fall|decrease|come\s+down|be\s+(?:cut|reduced|lowered))\s+(?:by\s+)?(?P<rate>{RATE})", I), Contingency.FIRM),
    (rx(rf"(?:价格|单价|货价)(?:需要|要|必须|得)?(?:下调|降低|下降|降|减少|下浮)了?\s*(?P<rate>{RATE})"), Contingency.FIRM),
    (rx(rf"(?:降价|减价|让价)\s*(?P<rate>{RATE})"), Contingency.FIRM),
]

OPERATIONAL = [
    rx(rf"\b(?:consolidate|combine|merge|batch|split|reroute|redirect)\s+(?:all\s+|our\s+|your\s+)?(?:deliveries|shipments|orders|delivery|shipping|drops)\b{_G}{{0,40}}", I),
    rx(r"\b(?:deliver|ship)\s+(?:everything\s+|all\s+orders\s+|all\s+deliveries\s+)?(?:directly\s+)?to\s+our\s+[\w\s-]{0,30}?(?:DC|warehouse|distribution\s+cent(?:er|re)|depot|hub|stores?)\b", I),
    rx(r"\b(?:you\s+)?(?:cover|pay\s+for|absorb)\s+(?:the\s+|all\s+)?(?:shipping|freight|delivery)(?:\s+costs?)?\b", I),
    # delivery schedule changes the supplier absorbs: "switch to a weekly delivery run", "deliver twice a week"
    rx(r"\b(?:switch|move|change|go)\s+(?:us\s+|you\s+)?(?:over\s+)?to\s+(?:a\s+)?(?:weekly|daily|twice[- ]weekly|fortnightly|bi-?weekly)\s+(?:delivery\s+|shipping\s+)?(?:runs?|deliver(?:y|ies)|schedule|shipments?|drops?)\b", I),
    rx(r"\b(?:weekly|daily|twice[- ]weekly|fortnightly|bi-?weekly)\s+(?:delivery\s+)?(?:runs?|deliver(?:y|ies)|drops?|shipments?)\s+(?:to|into)\s+(?:our|the)\s+[\w\s-]{0,30}?(?:DC|warehouse|distribution\s+cent(?:er|re)|depot|hub|stores?|site)\b", I),
    rx(r"\b(?:deliver|ship)\s+(?:to\s+us\s+)?(?:every\s+(?:week|day|monday|tuesday|wednesday|thursday|friday)|twice\s+a\s+week|weekly|daily)\b", I),
    rx(rf"(?:合并|集中|统一)(?:送货|发货|配送|交付|出货){_G}{{0,20}}"),
    rx(rf"(?:送到|配送到|发到)我们的?{G(12)}(?:仓库?|配送中心|门店)"),
    rx(r"(?:每周|每天|每日|每周两次)(?:送货|配送|发货|送一次货)"),
]
_OP_CUT = rx(r"\s+(?:and|but|if|so|then)\s+(?:we|you|I)\b|\s*,\s*(?:and\s+)?(?:we|you)\b|[，,]\s*(?:我们|你们)", I)

VOLUME = [
    rx(rf"\b(?:we'?ll|we\s+will|we\s+can)\s+(?:commit|guarantee|lock\s+in)\s+(?:to\s+)?(?:the\s+|this\s+|an?\s+)?(?:order|orders|volume|purchase|purchases)(?:\s+of\s+(?P<amt>{AMT}))?", I),
    rx(rf"\bcommit\s+to\s+(?:buying\s+|purchasing\s+|ordering\s+)?(?P<amt>{AMT})", I),
    rx(rf"承诺(?:采购|下单|订购|订单){G(10)}(?P<amt>{AMT})?"),
]

# Mentions of a material concession with no value: the compiler abstains on these.
MATERIAL_TRIGGERS = [
    (ObligationType.IMMEDIATE_DISCOUNT, rx(rf"\b(?:{_EARLY_VERB})\b{G(30)}\bearly\b|\bearly[- ]?(?:pay(?:ment)?|settlement)\b|提前(?:付款|支付|结清|结算)", I)),
    (ObligationType.CONTINGENT_REBATE, rx(r"\b(?:rebate|discount|off\s+next|price\s+cut)\b|返利|返点|折扣|优惠|让利", I)),
]
_NO_VALUE_CONTEXT = rx(
    r"\bno\s+(?:discount|rebate)|without\s+(?:a\s+|any\s+)?(?:discount|rebate)|nothing\s+else|不要(?:折扣|返利)|无(?:折扣|返利)", I)

# Duration markers, searched within the obligation's sentence.
BOUNDED_RE = rx(
    rf"\b(?:next|following|coming)\s+(?P<n>{NUMBER_WORD})\s+(?:invoices|orders|shipments|deliveries|bills)\b"
    rf"|(?:接下来|之后|后面?|未来|下)的?\s*(?P<nz>{NUMBER_WORD})\s*(?:张|笔|个|批)?(?:发票|订单|单|批货)"
    r"|\b(?:the\s+)?(?P<one>(?:next|following|coming)\s+(?:invoice|order|bill|shipment|delivery))\b"
    r"|(?P<onez>下一?(?:张|笔|批)(?:发票|订单|单|货))", I)
PERPETUAL_RE = rx(
    r"\bgoing\s+forward\b|\bfrom\s+now\s+on\b|\bpermanently\b|\bin\s+(?:the\s+)?future\b|\bongoing\b|\bfrom\s+here\s+on\b"
    r"|\bfor\s+all\s+(?:future\s+)?(?:invoices|orders)\b|\bon\s+all\s+future\s+invoices\b|\bstanding\b|\bevery\s+(?:invoice|order)\b"
    r"|以后|今后|从现在起|从今往后|长期|往后|此后|今后所有|所有(?:后续|以后)的?(?:发票|订单)", I)
# Unbounded forward promises on a rebate or price: always perpetual, whatever else the clause says.
STRONG_PERPETUAL_RE = rx(
    r"\bgoing\s+forward\b|\bfrom\s+(?:now|here|then)\s+on(?:wards?)?\b|\bpermanently\b|\bforever\b|\bfor\s+good\b"
    r"|\bin\s+(?:the\s+)?future\b|\bongoing\b|\bindefinitely\b|\bfuture\s+(?:purchases|orders|invoices|business|buying|deliveries)\b"
    r"|\b(?:every|each|per)\s+(?:quarter|month|year|order|invoice|purchase|shipment|delivery)\b|\bquarterly\b|\bannual(?:ly)?\b"
    r"|\bsubsequent\s+(?:invoices|orders|purchases)\b"
    r"|以后|今后|往后|此后|从现在起|从今往后|从此|长期|永久|每(?:个)?(?:季度|月|年|单|笔|张|次)|所有(?:后续|以后|未来)", I)
# Unbounded unless a period is named: "everything we buy", "all our orders", 所有采购
WEAK_UNBOUNDED_RE = rx(
    r"\b(?:everything|anything|whatever|all)\s+(?:that\s+)?(?:we|you)\s+(?:buy|order|purchase|take)\b"
    r"|\ball\s+(?:of\s+)?(?:our|your|the|their)?\s*(?:purchases|orders|business|buying|invoices|volume|spend)\b"
    r"|所有(?:的)?(?:采购|订单|货|发票|进货)|全部(?:的)?(?:采购|订单)|一切采购", I)
# A starting point, not a bound: "starting with the next invoice", "effective from the next order", 从下一张发票开始.
START_RE = rx(
    r"\b(?:starting|beginning|commencing|effective|applying)\s+(?:with|from|on|as\s+of)?\s*(?:the\s+)?(?:very\s+)?"
    r"(?:next|following|coming)\s+(?:invoice|order|bill|shipment|delivery)\b"
    r"|\bfrom\s+(?:the\s+)?(?:next|following)\s+(?:invoice|order|bill)\s+(?:on(?:wards?)?|forward|and\s+after)\b"
    r"|从\s*下一?(?:张|笔|批)(?:发票|订单|单|货)(?:开始|起)", I)
RECURRING_REBATE_RE = rx(r"\bevery\s+(?:quarter|month|year|order)\b|\beach\s+(?:quarter|month|year|order)\b|\bper\s+(?:quarter|order)\b|每(?:个)?(?:季度|月|年|单)", I)
CURRENT_TERMS_RE = rx(
    r"\b(?:instead\s+of|rather\s+than)\s+(?:(?:the|our|your|my)\s+)?(?:(?:usual|current|normal|standard|existing|present|agreed)\s+)?(?P<a>\d+)"
    r"|\b(?:up|down)\s+from\s+(?P<b>\d+)|\bcurrent(?:ly)?\s+(?:terms\s+(?:are|of)\s+)?(?P<c>\d+)\s*[-‑]?\s*days?"
    r"|\bfrom\s+(?P<d>\d+)\s*[-‑]?\s*days?\s+to\b|(?:现在|目前|原来)(?:的)?(?:账期)?(?:是)?\s*(?P<e>\d+)\s*天", I)
INVOICE_REF_RE = rx(r"\bthis\s+(?:one|invoice|bill)\b|\bthe\s+invoice\b|\bthat\s+invoice\b|本张|这张|这笔|该发票|货款", I)
_VALUE_RE = rx(rf"\d|{RATE}|{AMT}", I)


# ---------------------------------------------------------------- helpers


@dataclass
class _Doc:
    doc: SourceDocument
    taken: list[tuple[int, int]] = field(default_factory=list)

    def free(self, s: int, e: int) -> bool:
        return not any(s < te and ts < e for ts, te in self.taken)


def _sub(m: re.Match[str], name: str) -> str | None:
    gd = m.groupdict()
    v = gd.get(name)
    return v.strip() if v else None


def _quote(d: SourceDocument, s: int, e: int) -> Quote:
    txt = d.text[s:e]
    stripped = txt.rstrip(" ,，、")
    return Quote(doc_id=d.doc_id, text=stripped.lstrip())


def _extend_to_marker(text: str, m_end: int, sent_end: int, pat: re.Pattern[str]) -> re.Match[str] | None:
    mk = pat.search(text, m_end, sent_end)
    return mk


def _obligation(**kw: object) -> XObligation:
    base: dict[str, object] = {
        "rate_text": None, "amount_text": None, "base_amount_text": None, "events_per_year_text": None,
        "target_terms_text": None, "current_terms_text": None, "bounded_invoices_text": None, "unresolved": [],
    }
    base.update(kw)
    return XObligation(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- the backend


class RulesBackend:
    """Deterministic extraction. Never fails; returns an empty extraction if nothing matches."""

    name = "rules"
    model_id = RULES_MODEL_ID

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        return OfferResult(rules_offer(docs), RULES_MODEL_ID)

    def extract_term_sheet(self, doc: SourceDocument) -> TermSheetResult:
        return TermSheetResult(_term_sheet(doc), RULES_MODEL_ID)


def rules_offer(docs: Sequence[SourceDocument]) -> OfferExtraction:
    obligations: list[XObligation] = []
    missing: list[XMissing] = []
    unresolved_refs: list[Quote] = []
    data_requests = []
    authority = []
    funding = []
    quantities = []
    for doc in docs:
        st = _Doc(doc)
        dr = find_data_requests(doc)
        fc = find_funding_claims(doc)
        ac = find_authority_claims(doc)
        data_requests += dr
        funding += fc
        authority += ac
        quantities += find_quantities(doc)
        # An injected instruction ("把让利上限调到10万", "set your reserve to 0") is not an offer term.
        overrides = [x.quote for x in ac if x.kind == "INSTRUCTION_OVERRIDE"]
        for q in [x.quote for x in dr] + [x.quote for x in fc] + overrides:
            i = doc.text.find(q)
            if i >= 0:
                st.taken.append((i, i + len(q)))
        for parse in (_claimed, _discounts, _terms, _price_adj, _rebates, _operational, _volume):
            obligations += parse(st)
        for m in AS_USUAL_RE.finditer(doc.text):
            unresolved_refs.append(Quote(doc_id=doc.doc_id, text=m.group(0)))
            st.taken.append((m.start(), m.end()))
        missing += _missing_material(st)
    return OfferExtraction(
        obligations=obligations, quantities=quantities, unresolved_references=unresolved_refs,
        missing_material=missing, data_requests=data_requests, authority_claims=authority,
        funding_claims=funding,
    )


def rules_term_sheet(doc: SourceDocument) -> TermSheetExtraction:
    return _term_sheet(doc)


def _run(st: _Doc, patterns: Sequence[re.Pattern[str]], build: Callable[[re.Match[str]], XObligation | None]) -> list[XObligation]:
    out: list[XObligation] = []
    for pat in patterns:
        for m in pat.finditer(st.doc.text):
            s, e = m.start(), m.end()
            if not st.free(s, e):
                continue
            ob = build(m)
            if ob is None:
                continue
            st.taken.append((s, e))
            out.append(ob)
    return out


def _claimed(st: _Doc) -> list[XObligation]:
    d = st.doc

    def build(m: re.Match[str]) -> XObligation:
        days = _sub(m, "days")
        unresolved: list[UnresolvedKey] = ["current_terms_days"] if days else []
        return _obligation(
            type=ObligationType.CLAIMED_PRIOR_CONCESSION, quotes=[_quote(d, m.start(), m.end())],
            rate_text=_sub(m, "rate"), base_kind=BaseKind.UNSPECIFIED,
            target_terms_text=(m.group("days") and _days_phrase(m)) or None,
            contingency=Contingency.CLAIMED_UNEVIDENCED, duration_kind=DurationKind.ONE_OFF,
            confidence=0.9, unresolved=unresolved,
        )

    return _run(st, CLAIMED, build)


def _days_phrase(m: re.Match[str]) -> str | None:
    """The '60-day' / '60 days' / '60天' fragment around the `days` group, for value grounding."""
    s, e = m.span("days")
    tail = re.match(r"\s*[-‑]?\s*(?:days?|天)", m.string[e:])
    return m.string[s : e + (tail.end() if tail else 0)]


_CAP_START = rx(r"\s*(?:(?:but\s+|and\s+)?(?:up\s+to|a\s+maximum\s+of|capped\s+at|at\s+most|no\s+more\s+than|maximum|max\.?)\b|最多|不超过|上限|封顶|最高)", I)
_DISCOUNT_TAIL = rx(r"\s*(?:的)?(?:现金)?(?:折扣|优惠|贴息)|\s+(?:cash\s+)?discount\b", I)
_REBATE_GAP = rx(rf"返|{_PERIOD_ZH}|{_PERIOD}|以后|今后|每(?:个)?(?:季度|月|年)", I)


def _has_value(text: str, s: int, e: int) -> bool:
    return _VALUE_RE.search(text, s, e) is not None


def clause_scope(text: str, s: int, e: int) -> tuple[int, int]:
    """The clause around [s, e), widened over neighbouring clauses of the same sentence that state no value
    of their own ("Going forward, 0.5% back on everything" / "1% back, every quarter"). A neighbour with a
    number belongs to another term and stops the widening."""
    parts = clauses(text, *sentence_bounds(text, s))
    idx = [i for i, (cs, ce) in enumerate(parts) if cs < e and s < ce] or [0]
    lo, hi = idx[0], idx[-1]
    while lo > 0 and not _has_value(text, *parts[lo - 1]):
        lo -= 1
    while hi < len(parts) - 1 and (not _has_value(text, *parts[hi + 1]) or _CAP_START.match(text, *parts[hi + 1])):
        hi += 1  # a trailing cap ("…, capped at ¥300,000", "，最多40万") qualifies the term before it
    return parts[lo][0], parts[hi][1]


def _widen(qs: int, qe: int, m: re.Match[str] | None) -> tuple[int, int]:
    return (min(qs, m.start()), max(qe, m.end())) if m else (qs, qe)


def _money_text(amt: str | None, whole: str) -> str | None:
    """The amount fragment to ground: the amount itself, or with its bill noun when only that makes it money
    ("420k inv")."""
    if amt and parse_money(amt) is not None:
        return amt.strip()
    return whole.strip() if parse_money(whole) is not None else None


def _invoice_amount(t: str, ss: int, se: int) -> re.Match[str] | None:
    """The first stated invoice amount in t[ss:se]: "the ¥420,000 invoice", "42万货款", "invoice for ¥420k"."""
    hits = [m for m in (p.search(t, ss, se) for p in INVOICE_AMOUNT) if m and _money_text(m.group("amt"), m.group(0))]
    return min(hits, key=lambda m: m.start()) if hits else None


def _only_invoice_amount(t: str) -> re.Match[str] | None:
    """The invoice amount of a message that names exactly one amount of money ("We'll pay the ¥420k invoice by
    Monday. Our rate for early settlement is 0.8%."): the discount in the other sentence is on that invoice.
    None when the message states no amount, or more than one."""
    hits = [m for p in INVOICE_AMOUNT for m in p.finditer(t) if _money_text(m.group("amt"), m.group(0))]
    if not hits or len({f.value for f in find_money(t)}) > 1:
        return None
    values = {parse_money(_money_text(m.group("amt"), m.group(0))) for m in hits}
    return min(hits, key=lambda m: m.start()) if len(values) == 1 else None


def _base_amount(d: SourceDocument, s: int, e: int, quotes: list[Quote]) -> str | None:
    """The invoice amount a discount phrase t[s:e] applies to: in the phrase, else in its sentence, else the
    single amount of the whole message. Adds the amount's own quote when it lies outside the phrase."""
    t = d.text
    inv = _invoice_amount(t, s, e)
    if inv is not None:
        return _money_text(inv.group("amt"), inv.group(0))
    money = re.search(AMT, t[s:e])
    if money and parse_money(money.group(0)) is not None:
        return money.group(0).strip()
    ss, se = sentence_bounds(t, s)
    inv = _invoice_amount(t, ss, se) or _only_invoice_amount(t)
    if inv is not None:
        quotes.append(_quote(d, inv.start(), inv.end()))
        return _money_text(inv.group("amt"), inv.group(0))
    return None


def _discounts(st: _Doc) -> list[XObligation]:
    d = st.doc
    t = d.text

    def build(m: re.Match[str]) -> XObligation | None:
        s, e = m.start(), m.end()
        # "提前付款，下季度返1%": the rate after the early-pay phrase belongs to a rebate, not to this discount
        if _REBATE_GAP.search(t, s, m.start("rate")):
            return None
        tail = _DISCOUNT_TAIL.match(t, e)
        if tail:
            e = tail.end()
        quotes = [_quote(d, s, e)]
        # "42万货款我们提前付，扣0.8%": the invoice amount may sit in the same sentence, outside the phrase
        amount_text = _base_amount(d, s, e, quotes)
        return _obligation(
            type=ObligationType.IMMEDIATE_DISCOUNT, quotes=quotes, rate_text=_sub(m, "rate"),
            base_kind=BaseKind.INVOICE, base_amount_text=amount_text, contingency=Contingency.FIRM,
            duration_kind=DurationKind.ONE_OFF, confidence=0.9,
        )

    return _run(st, DISCOUNT, build) + _cued_discounts(st) + _net_settlements(st)


# Paying on the due date is not an early payment: a "discount" for it is a price cut, never the Tier-1 path.
ON_TIME_RE = rx(r"\bon\s+time\b|\bon\s+(?:the\s+)?due\s+date\b|\bwhen\s+(?:it'?s\s+)?due\b|\bat\s+maturity\b|\bas\s+(?:normal|usual)\b"
                r"|按时|准时|到期(?:时|日|当天)?(?:再)?(?:付|支付|结)", I)
PAY_VERB_RE = rx(rf"\b(?:{_SETTLE}|pay|paying|release|releasing|remit|remitting|transfer|wire|wiring|clear|close\s+out)\b"
                 r"|付款|支付|打款|转账|结清|付清|打过去|转过去|汇款", I)

# A discount stated only as the net sum paid: "we'd transfer ¥417,480 tomorrow as full and final settlement of the
# ¥420,000 invoice". The rate is derived in grounding, exactly, from (face - net) / face.
NET_SETTLEMENT = [
    rx(rf"\b(?:transfer|wire|remit|pay|send|settle\s+(?:it\s+|this\s+)?(?:for|with|at)|close\s+(?:it\s+|this\s+)?out\s+(?:for|with|at))"
       rf"\s+(?:you\s+)?(?:only\s+|just\s+)?(?P<net>{AMT}){G(40)}\b(?:as|in)\s+(?:full(?:\s+and\s+final)?|final|complete)\s+"
       r"(?:settlement|payment)", I),
    rx(rf"(?:实付|只付|付|打|转|汇)(?:给(?:你们|贵司|您))?\s*(?P<net>{AMT})\s*(?:作为|当作|算作|就)?(?:全款|结清|了结|全部结清|一次结清|一次性结清)"),
]


def _net_settlements(st: _Doc) -> list[XObligation]:
    """The net sum and the invoice amount it settles, quoted together; no rate is claimed here."""
    d = st.doc
    t = d.text
    out: list[XObligation] = []
    for pat in NET_SETTLEMENT:
        for m in pat.finditer(t):
            s, e = m.start(), m.end()
            ss, se = sentence_bounds(t, s)
            net = parse_money(m.group("net"))
            if net is None or not st.free(ss, se):
                continue  # a rate is already read in this sentence: grounding checks the sum against it instead
            bases = [f for f in find_money(t) if f.value > net and not (s <= f.start < e)]
            if len({f.value for f in bases}) != 1:
                continue
            f0 = bases[0]
            st.taken.append((s, e))
            out.append(_obligation(
                type=ObligationType.IMMEDIATE_DISCOUNT, quotes=[_quote(d, s, e), _quote(d, f0.start, f0.end)],
                base_kind=BaseKind.INVOICE, base_amount_text=f0.text, contingency=Contingency.FIRM,
                duration_kind=DurationKind.ONE_OFF, confidence=0.7,
            ))
    return out


# A named FUTURE period ("next quarter's orders", 下季度): the rate is a rebate on purchases, not an early-pay
# discount. "this month" / 本月 is not one: "0.8% off the invoices this month and we pay right away" is an
# early payment (on several invoices, so it abstains on scope).
_FUTURE_PERIOD_RE = rx(rf"{_PERIOD}|{_PERIOD_ZH}", I)


def _cued_discounts(st: _Doc) -> list[XObligation]:
    """"Knock 1% off the ¥420,000 invoice and we'll pay it today": a discount rate whose sentence has an
    early-payment cue, and whose own clause names no future period or unbounded scope, is an immediate
    discount on the invoice. Without a cue it is left to the rebate grammar, which abstains when no base is
    stated."""
    d = st.doc
    t = d.text
    out: list[XObligation] = []
    for pat in DISCOUNT_RATE:
        for m in pat.finditer(t):
            s, e = m.start(), m.end()
            if not st.free(s, e):
                continue
            ss, se = sentence_bounds(t, s)
            own = next(((a, b) for a, b in clauses(t, ss, se) if a <= s < b), (ss, se))
            if (_FUTURE_PERIOD_RE.search(t, *own) or STRONG_PERPETUAL_RE.search(t, *own)
                    or WEAK_UNBOUNDED_RE.search(t, *own)):
                continue
            cs, ce = clause_scope(t, s, e)
            cues = [c for c in EARLY_CUE.finditer(t, ss, se) if st.free(*c.span()) and not (c.start() < e and s < c.end())]
            if not cues and INVOICE_WORD.search(t, cs, ce):
                # "Take 1% off the invoice. We'll pay it today." — an explicit invoice base, the cue next door
                cues = [c for c in EARLY_CUE.finditer(t) if st.free(*c.span())]
            if not cues and not ON_TIME_RE.search(t, ss, se) and _invoice_amount(t, ss, se) is not None:
                # "We can release the full ¥420,000 on your inv next week if you're ok to take 0.6% off": a rate
                # taken off a stated invoice that the sentence pays is a discount on that invoice, not a rebate.
                cues = [c for c in PAY_VERB_RE.finditer(t, ss, se) if st.free(*c.span()) and not (c.start() < e and s < c.end())]
            if not cues:
                continue
            cue = cues[0]
            quotes = [_quote(d, s, e), _quote(d, *cue.span())]
            unresolved: list[UnresolvedKey] = []
            amount_text = None
            inv = _invoice_amount(t, ss, se)
            if inv is not None:
                amount_text = _money_text(inv.group("amt"), inv.group(0))
                quotes.append(_quote(d, inv.start(), inv.end()))
            else:
                free_money = {f.value: f for f in find_money(t[ss:se])
                              if st.free(ss + f.start, ss + f.end) and not (ss + f.start < e and s < ss + f.end)}
                if len(free_money) == 1:
                    f = next(iter(free_money.values()))
                    amount_text = f.text
                    quotes.append(_quote(d, ss + f.start, ss + f.end))
                elif len(free_money) > 1:
                    unresolved.append("base_amount")  # several amounts: which one is the invoice?
                elif (only := _only_invoice_amount(t)) is not None:
                    amount_text = _money_text(only.group("amt"), only.group(0))
                    quotes.append(_quote(d, only.start(), only.end()))
            st.taken += [(s, e), cue.span()]
            out.append(_obligation(
                type=ObligationType.IMMEDIATE_DISCOUNT, quotes=quotes, rate_text=_sub(m, "rate"),
                base_kind=BaseKind.INVOICE, base_amount_text=amount_text, contingency=Contingency.FIRM,
                duration_kind=DurationKind.ONE_OFF, confidence=0.8, unresolved=unresolved,
            ))
    return out


def _terms(st: _Doc) -> list[XObligation]:
    d = st.doc
    out: list[XObligation] = []
    for pat, conf in TERMS:
        for m in pat.finditer(d.text):
            s, e = m.start(), m.end()
            if not st.free(s, e):
                continue
            to = _sub(m, "to") or _sub(m, "to2")
            if not to:
                continue
            to_span = m.span("to") if m.groupdict().get("to") else m.span("to2")
            sent_s, sent_e = sentence_bounds(d.text, s)
            quotes = [_quote(d, s, e)]
            current = _sub(m, "from")
            if current is None:
                cm = CURRENT_TERMS_RE.search(d.text, sent_s, sent_e)
                if cm and st.free(cm.start(), cm.end()):
                    current = next(v for v in cm.groups() if v)
                    quotes.append(_quote(d, cm.start(), cm.end()))
            duration = DurationKind.RECURRING_PERPETUAL
            bounded_text = None
            bm = BOUNDED_RE.search(d.text, sent_s, sent_e)
            if bm and any(sm.start() <= bm.start() and bm.end() <= sm.end() for sm in START_RE.finditer(d.text, sent_s, sent_e)):
                bm = None  # "starting with the next invoice": where it starts, not how long it lasts
            if bm:
                duration = DurationKind.RECURRING_BOUNDED
                bounded_text = next(v for v in (bm.group("n"), bm.group("nz"), bm.group("one"), bm.group("onez")) if v).strip()
                if not (s <= bm.start() and bm.end() <= e):
                    quotes.append(_quote(d, bm.start(), bm.end()))
            else:
                pm = PERPETUAL_RE.search(d.text, sent_s, sent_e)
                if pm and not (s <= pm.start() and pm.end() <= e):
                    between = d.text[e : pm.start()]
                    if pm.start() >= e and re.fullmatch(r"[\s,，]*", between):
                        quotes[0] = _quote(d, s, pm.end())  # "... to 60 days going forward"
                    else:
                        quotes.append(_quote(d, pm.start(), pm.end()))
            tail = re.match(r"\s*[-‑]?\s*(?:days?|天)", d.text[to_span[1] :])
            target_text = d.text[to_span[0] : to_span[1] + (tail.end() if tail else 0)] if tail else d.text[s:e]
            unresolved: list[UnresolvedKey] = [] if current else ["current_terms_days"]
            out.append(_obligation(
                type=ObligationType.TERMS_EXTENSION, quotes=quotes, base_kind=BaseKind.FUTURE_INVOICES,
                target_terms_text=target_text.strip(), current_terms_text=current,
                contingency=Contingency.FIRM, duration_kind=duration, bounded_invoices_text=bounded_text,
                confidence=conf, unresolved=unresolved,
            ))
            st.taken.append((s, e))
    return out


def _rebates(st: _Doc) -> list[XObligation]:
    """A rebate's base and duration come from its clause (INVARIANT 10):
    - an unbounded forward promise ("going forward", "every quarter", 以后, or "everything we buy" with no
      named period) is RECURRING_PERPETUAL with unresolved scope: its base cannot be bounded, so it abstains;
    - a named period ("next quarter", 下季度) is one period's purchases, capped or based when the text says so;
    - a stated amount with no period ("1% off our ¥300,000 order") is that base;
    - otherwise ("Give us 1% off.") the scope is unresolved and nothing is bound or booked."""
    d = st.doc
    t = d.text
    out: list[XObligation] = []
    for pat in REBATE:
        for m in pat.finditer(t):
            s, e = m.start(), m.end()
            if not st.free(s, e):
                continue
            cs, ce = clause_scope(t, s, e)
            period = PERIOD_RE.search(t, cs, ce)
            strong = STRONG_PERPETUAL_RE.search(t, cs, ce)
            weak = WEAK_UNBOUNDED_RE.search(t, cs, ce)
            base_hit = CAP_RE.search(t, cs, ce) or REBATE_BASE_RE.search(t, cs, ce)
            base_text = next((g for g in base_hit.groups() if g), None) if base_hit else None
            qs, qe = s, e
            unresolved: list[UnresolvedKey] = []
            duration = DurationKind.ONE_OFF
            base = BaseKind.PERIOD_PURCHASES
            if strong or (weak and not period):
                duration = DurationKind.RECURRING_PERPETUAL
                unresolved.append("scope")
                for marker in (strong, weak, period):
                    qs, qe = _widen(qs, qe, marker)
                base_text = None
            elif period:
                qs, qe = _widen(qs, qe, period)
                qs, qe = _widen(qs, qe, base_hit)
            elif base_text:
                qs, qe = _widen(qs, qe, base_hit)
            elif (ante := _antecedent(t, s, e)) is not None:
                # "Next quarter we plan about ¥400k of orders (max ¥400k). Give us a 0.5% rebate on those":
                # "those" points at the period and cap of the sentence before it.
                a_period, a_base = ante
                extra = [x for x in (a_period, a_base) if x is not None]
                base_text = next((g for g in a_base.groups() if g), None) if a_base else None
                if base_text and parse_money(base_text) is None:
                    base_text = None
                out.append(_obligation(
                    type=ObligationType.CONTINGENT_REBATE,
                    quotes=[_quote(d, qs, qe), *(_quote(d, x.start(), x.end()) for x in extra)],
                    rate_text=_sub(m, "rate"), base_kind=BaseKind.PERIOD_PURCHASES, base_amount_text=base_text,
                    contingency=Contingency.CONTINGENT, duration_kind=DurationKind.ONE_OFF, confidence=0.75,
                    unresolved=[],
                ))
                st.taken.append((qs, qe))
                continue
            else:
                base = BaseKind.UNSPECIFIED
                unresolved.append("scope")
            if base_text and parse_money(base_text) is None:
                base_text = None
            out.append(_obligation(
                type=ObligationType.CONTINGENT_REBATE, quotes=[_quote(d, qs, qe)], rate_text=_sub(m, "rate"),
                base_kind=base, base_amount_text=base_text, contingency=Contingency.CONTINGENT,
                duration_kind=duration, confidence=0.9 if not unresolved else 0.6, unresolved=unresolved,
            ))
            st.taken.append((qs, qe))
    return out


_ANAPHOR = rx(r"\b(?:on|for|against|of|across)\s+(?:all\s+)?(?:those|these|them|that|it)\b|\bthat\s+(?:volume|order)\b|也返|同样返"
             r"|(?:那些|这些|上述|这批|那批)(?:的)?(?:采购|订单|货)?", I)


_INVOICE_NOUN = rx(r"\binvoices?\b|\binv\b|\bbills?\b|发票|货款|票", I)


def _antecedent(t: str, s: int, e: int) -> tuple[re.Match[str] | None, re.Match[str] | None] | None:
    """(named period, cap or base) of the sentence before a rebate whose own clause points back at it
    ("… on those"), or None when there is no such pointer or the previous sentence names no period."""
    cs, ce = clause_scope(t, s, e)
    ss, se = sentence_bounds(t, s)
    # "if our Q1 order (~¥400k) happens, 0.5% rebate on that too", "那批40万的货如果下单，希望给1个点的返利": the one
    # order the sentence names before the rebate (never an invoice being paid)
    same = [b for b in REBATE_BASE_RE.finditer(t, ss, cs) if not _INVOICE_NOUN.search(b.group(0))]
    if (len(same) == 1 and len({f.value for f in find_money(t[ss:se])}) == 1
            and not (STRONG_PERPETUAL_RE.search(t, ss, se) or WEAK_UNBOUNDED_RE.search(t, ss, se))):
        return PERIOD_RE.search(t, ss, se), same[0]
    if not _ANAPHOR.search(t, cs, ce):
        return None
    if ss == 0:
        return None
    ps, pe = sentence_bounds(t, max(0, ss - 2))
    period = PERIOD_RE.search(t, ps, pe)
    if period is None or STRONG_PERPETUAL_RE.search(t, ps, pe) or WEAK_UNBOUNDED_RE.search(t, ps, pe):
        return None
    base = CAP_RE.search(t, ps, pe) or REBATE_BASE_RE.search(t, ps, pe)
    return period, base


def _price_adj(st: _Doc) -> list[XObligation]:
    d = st.doc
    t = d.text
    out: list[XObligation] = []
    for pat, contingency in PRICE_ADJ:
        for m in pat.finditer(t):
            s, e = m.start(), m.end()
            if not st.free(s, e):
                continue
            cs, ce = clause_scope(t, s, e)
            marker = (STRONG_PERPETUAL_RE.search(t, cs, ce) or PERPETUAL_RE.search(t, cs, ce)
                      or WEAK_UNBOUNDED_RE.search(t, cs, ce))
            future = marker is not None
            qs, qe = _widen(s, e, marker)
            out.append(_obligation(
                type=ObligationType.PRICE_ADJUSTMENT, quotes=[_quote(d, qs, qe)], rate_text=_sub(m, "rate"),
                base_kind=BaseKind.FUTURE_INVOICES if future else BaseKind.UNSPECIFIED,
                contingency=contingency,
                duration_kind=DurationKind.RECURRING_PERPETUAL if future else DurationKind.ONE_OFF,
                confidence=0.8, unresolved=[] if future else ["base"],
            ))
            st.taken.append((qs, qe))
    return out



def _operational(st: _Doc) -> list[XObligation]:
    d = st.doc

    def span(m: re.Match[str]) -> tuple[int, int]:
        s, e = m.start(), m.end()
        # Stop the quote before a following clause ("... and we'll move you to 30-day terms").
        cut = _OP_CUT.search(d.text[s:e])
        if cut:
            e = s + cut.start()
        for ts, te in st.taken:  # never run into an already-quoted obligation
            if s < ts < e:
                e = ts
        return s, len(d.text[:e].rstrip(" ,，"))

    def build(s: int, e: int) -> XObligation:
        return _obligation(
            type=ObligationType.OPERATIONAL_CONCESSION, quotes=[_quote(d, s, e)], base_kind=BaseKind.PER_EVENT,
            contingency=Contingency.FIRM, duration_kind=DurationKind.RECURRING_PERPETUAL, confidence=0.8,
            unresolved=["per_event_cost_fen", "events_per_year"],
        )

    out: list[XObligation] = []
    for pat in OPERATIONAL:
        for m in pat.finditer(d.text):
            s, e = span(m)
            if e <= s or not st.free(s, e):
                continue
            st.taken.append((s, e))
            out.append(build(s, e))
    return out


def _volume(st: _Doc) -> list[XObligation]:
    d = st.doc

    def build(m: re.Match[str]) -> XObligation:
        return _obligation(
            type=ObligationType.VOLUME_COMMITMENT, quotes=[_quote(d, m.start(), m.end())],
            base_kind=BaseKind.PERIOD_PURCHASES, base_amount_text=_sub(m, "amt"),
            contingency=Contingency.FIRM, duration_kind=DurationKind.ONE_OFF, confidence=0.7,
        )

    return _run(st, VOLUME, build)


def _missing_material(st: _Doc) -> list[XMissing]:
    d = st.doc
    out: list[XMissing] = []
    for ob_type, pat in MATERIAL_TRIGGERS:
        for m in pat.finditer(d.text):
            if not st.free(m.start(), m.end()):
                continue
            sent_s, sent_e = sentence_bounds(d.text, m.start())
            # "we'd want 1.5% back as a rebate": the word names the term already read in its own clause
            own = next(((a, b) for a, b in clauses(d.text, sent_s, sent_e) if a <= m.start() < b), (m.start(), m.end()))
            if any(ts < own[1] and own[0] < te for ts, te in st.taken):
                continue
            if _NO_VALUE_CONTEXT.search(d.text, sent_s, sent_e):
                continue
            out.append(XMissing(obligation_type=ob_type, missing_field="rate_bp", doc_id=d.doc_id, quote=m.group(0)))
            st.taken.append((m.start(), m.end()))
    return out


# ---------------------------------------------------------------- term sheets

_TS_FEE = rx(
    rf"\b(?:arrangement|upfront|up-front|origination|facility|processing|commitment|management|service|handling)\s+fees?\b"
    rf"(?:\s+(?:of|is|at))?\s*[:：]?\s*(?:{G(10)})(?P<v>{RATE}|{AMT})(?:\s+(?:per|every)\s+(?:\d+\s+days?|month|advance|period))?"
    rf"|(?:手续费|服务费|安排费|承诺费|管理费)\s*[:：为]?\s*(?P<vz>{RATE}|{AMT})", I)
_TS_RATE = rx(
    rf"(?:\bat\s+|\b(?:interest\s+)?rate\s*(?:of\s+|is\s+)?[:：]?\s*|\binterest\s+(?:of\s+|at\s+)?|(?:年化)?(?:年)?利率\s*[:：为]?\s*|年化\s*)"
    rf"(?P<v>{RATE})(?:\s*(?:p\.?a\.?|per\s+annum|a\s+year|annual(?:ly)?|APR))?", I)
_TS_PRINCIPAL = [
    rx(rf"\b(?:[\w-]+\s+){{0,3}}(?:loan|facility|line|credit|financing|advance)\s+(?:of\s+|for\s+|amount\s+)?(?:up\s+to\s+)?[:：]?\s*(?P<v>{AMT})", I),
    rx(rf"(?P<v>{AMT})\s+(?:[\w-]+\s+){{0,3}}(?:loan|facility|credit\s+line|line|financing)", I),
    rx(rf"(?:贷款|额度|授信|融资)(?:金额)?\s*[:：为]?\s*(?P<v>{AMT})|(?P<vz>{AMT})\s*(?:的)?(?:贷款|额度|授信|融资)"),
]
_TS_TENOR = rx(
    r"\b(?:tenor|term|maturity|duration|for|over|repayable\s+(?:over|within|in))\s*(?:of\s+)?[:：]?\s*(?P<v>\d+\s*[-‑]?\s*(?:months?|years?|yrs?|mos?)\b|(?:one|a)\s+year)"
    r"|(?P<v2>\d+\s*[-‑]?\s*(?:months?|years?))\s+(?:tenor|term|loan)"
    r"|(?:期限|贷款期限)\s*[:：为]?\s*(?P<vz>\d+\s*(?:个月|年))|(?P<vz2>\d+\s*(?:个月|年))期", I)
_TS_LEAD = rx(
    r"\b(?:disburse(?:ment|d)?|funds?\s+(?:available|released)|drawdown|funding)\s*(?:within|in|after)\s+(?P<v>\d+\s*(?:business\s+|working\s+)?days?)"
    r"|(?P<vz>\d+\s*(?:个)?(?:工作日|天))(?:内)?放款", I)
_TS_GUARANTEE = rx(r"\bpersonal(?:ly)?\s+guarant\w*|\bguarantor\b|\bjoint\s+and\s+several\b|个人(?:连带)?(?:担保|保证)|连带责任保证|实际控制人.{0,6}担保", I)
_TS_COLLATERAL = rx(r"\bcollateral\b|\bpledg\w*|\bmortgag\w*|\bsecured\s+(?:on|against|by)\b|\bcharge\s+over\b|抵押|质押", I)
_TS_EQUITY = rx(r"\bequity\b|\bwarrants?\b|\bshares\s+(?:in|of)\b|\bconvertible\b|股权|入股|认股|对赌", I)
_TS_COVENANT = rx(r"\bDSCR\b|\bdebt\s+service\s+coverage\b|\bleverage\b|\bclean[- ]?down\b|\bcovenant\w*|资产负债率|偿债覆盖|清零", I)
_TS_KIND: list[tuple[FacilityKind, re.Pattern[str]]] = [
    (FacilityKind.INVOICE_FINANCING, rx(r"invoice\s+(?:financ|discount)|factoring|receivables?\s+financ|保理|应收账款融资|发票贷", I)),
    (FacilityKind.EQUIPMENT_LEASE, rx(r"\blease\b|leasing|融资租赁|租赁", I)),
    (FacilityKind.EQUIPMENT_TERM_LOAN, rx(r"equipment\s+(?:term\s+)?loan|设备贷", I)),
    (FacilityKind.GOV_GUARANTEED_LOAN, rx(r"(?:government|gov\.?|state)[- ]guaranteed|担保贷|政策性", I)),
    (FacilityKind.BANK_ACCEPTANCE_BILL, rx(r"acceptance\s+bill|banker'?s\s+acceptance|银票|承兑汇票", I)),
    (FacilityKind.BUYER_EARLY_PAY, rx(r"early[- ]pay(?:ment)?\s+programme|supply\s+chain\s+finance|供应链金融", I)),
    (FacilityKind.EQUITY, rx(r"equity\s+(?:investment|round|financing)|股权融资", I)),
    (FacilityKind.CREDIT_LINE, rx(r"credit\s+line|revolv|overdraft|working[- ]capital|流动资金|循环", I)),
]


_NEG = rx(r"\b(?:no|not|without|unsecured|waived?|none)\b|无需|不需要|无须|免", I)


def _sentence_quote(d: SourceDocument, pos: int) -> tuple[int, int]:
    s, e = sentence_bounds(d.text, pos)
    seg = d.text[s:e]
    lead = len(seg) - len(seg.lstrip())
    return s + lead, s + len(seg.rstrip())


def _term_sheet(d: SourceDocument) -> TermSheetExtraction:
    t = d.text
    clauses: list[XClause] = []
    taken: list[tuple[int, int]] = []

    def add(fld: ClauseField, s: int, e: int, v: str) -> None:
        clauses.append(XClause(field=fld, quote=t[s:e].strip(), value_text=v.strip()))
        taken.append((s, e))

    def free(s: int, e: int) -> bool:
        return not any(s < te and ts < e for ts, te in taken)

    for m in _TS_FEE.finditer(t):
        add("fee", m.start(), m.end(), m.group("v") or m.group("vz"))
    for m in _TS_LEAD.finditer(t):
        add("lead_time", m.start(), m.end(), m.group("v") or m.group("vz"))
    for m in _TS_TENOR.finditer(t):
        if free(m.start(), m.end()):
            add("tenor", m.start(), m.end(), next(v for v in (m.group("v"), m.group("v2"), m.group("vz"), m.group("vz2")) if v))
    for pat in _TS_PRINCIPAL:
        hit = next(
            (m for m in pat.finditer(t)
             if free(m.start(), m.end()) and parse_money(m.groupdict().get("v") or m.groupdict().get("vz")) is not None),
            None,
        )
        if hit:
            add("principal", hit.start(), hit.end(), hit.groupdict().get("v") or hit.group("vz"))
            break
    for m in _TS_RATE.finditer(t):
        if free(m.start(), m.end()):
            add("rate", m.start(), m.end(), m.group("v"))
    for fld, pat in (("guarantee", _TS_GUARANTEE), ("collateral", _TS_COLLATERAL), ("equity", _TS_EQUITY), ("covenant", _TS_COVENANT)):
        seen: set[tuple[int, int]] = set()
        for m in pat.finditer(t):
            s, e = _sentence_quote(d, m.start())
            if (s, e) in seen or (fld != "covenant" and _NEG.search(t[s:e])):
                continue
            seen.add((s, e))
            clauses.append(XClause(field=fld, quote=t[s:e], value_text=m.group(0)))  # type: ignore[arg-type]

    kind = FacilityKind.CREDIT_LINE
    for k, pat in _TS_KIND:
        if pat.search(t):
            kind = k
            break
    repayment = None
    if re.search(r"amortis|amortiz|equal\s+(?:monthly\s+)?instal|等额", t, I):
        repayment = "AMORTISING"
    elif re.search(r"repaid\s+(?:from|on)\s+(?:receipt|collection)|回款还款", t, I) or kind == FacilityKind.INVOICE_FINANCING:
        repayment = "ON_RECEIPT"
    elif rx(r"\bbullet\b|at\s+maturity|到期一次", I).search(t):
        repayment = "BULLET"
    name = None
    nm = rx(r"\bfrom\s+([A-Z][\w&\-]*(?:[ ][A-Z][\w&\-]*){0,3})").search(t)
    if nm:
        name = nm.group(1)
    return TermSheetExtraction(
        lender_name=name, facility_kind=kind, repayment=repayment,  # type: ignore[arg-type]
        clauses=clauses, authority_claims=find_authority_claims(d),
    )
