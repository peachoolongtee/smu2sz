"""The boundary guard: readings the typed rows cannot carry are abstentions, never proposals.

The certification of the language boundary (`scripts/certify_language_boundary.py`) found a class of messages that
the grammar (or a model) reads into a typed discount that the buyer did not offer: a decimal comma ("0,5%" read as
5%), a rate per day early, "2/10 net 30", a dollar invoice, a hedged "maybe", a payment after the due date, a price
freeze, another party's invoice. None of them can be booked as written; each makes the offer abstain, so nothing is
countered, queued or committed until the buyer clarifies.

This module only narrows. It runs on the grounded obligations whatever backend produced them (rules, cache or a
model), looks at the message text only, and adds an abstention (a material one) per kind of unreadable reading.
A hit never creates or changes a term, it removes the reading or marks it unbookable.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.compiler import lexicon
from app.compiler.parsing import RATE_RE, rx
from app.domain.models import Abstention, Obligation, SourceDocument, SourceSpan

I = re.IGNORECASE

UNUSUAL_RATE_REASON = "rate written in an unusual form; please confirm the rate"
UNUSUAL_AMOUNT_REASON = "amount written in an unusual form; please confirm the amount"

# ---- number forms: ambiguous separators are not read ---------------------------------------------------------------
# "0,5%", "6,4%" (a decimal comma: a comma then one or two digits, then a percent sign), "0,5%" in a message that also
# writes "¥420,000" (the comma used both ways), "百分之0,5". A thousands comma is followed by exactly three digits.
_PCT = r"(?:%|％|percent\b|per\s?cent\b|个百分点|个点)"
RATE_UNUSUAL = rx(rf"(?<!\d)\d+,\d{{1,2}}(?!\d)\s?{_PCT}|(?:百分之|千分之|万分之)\s?\d+,\d{{1,2}}(?!\d)", I)
# "420.000,00", "1,234,56": dots or commas as thousands separators followed by a decimal comma
AMOUNT_UNUSUAL = rx(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3})+,\d{1,2}(?!\d)", I)

# ---- rate basis: the rate is not a flat rate on the invoice ---------------------------------------------------------
PER_DAY = rx(
    r"\b(?:per|each|every)\s+(?:(?:single|extra|additional|calendar|business|working)\s+)?day\b"
    r"|\bdaily\b|\bper\s+diem\b|/\s?day\b"
    r"|\bfor\s+(?:every|each)\s+(?:(?:extra|additional)\s+)?day\b"
    r"|每(?:提前|早|多提前|早付|多)?[一二两三四五六七八九十\d]*(?:天|日)|每天|每日|按天|按日|日息|日利率|天息", I)
# "2/10 net 30", "2%/10 net 30", "2% 10 days, net 30": a conditional discount with a payment-day schedule
TERMS_CODE = rx(
    r"\b\d{1,2}(?:\.\d+)?\s?%?\s?/\s?\d{1,3}\s*[,;]?\s*(?:net|n)\s?[/-]?\s?\d{1,3}\b"
    r"|\b\d{1,2}(?:\.\d+)?\s?%\s?\d{1,3}\s*(?:days?)?\s*[,;]?\s*(?:net|n)\s?[/-]?\s?\d{1,3}\b", I)

# ---- currency: only yuan is on the books ----------------------------------------------------------------------------
_FX = r"(?:US\s?\$|HK\s?\$|NT\s?\$|[SACT]\s?\$|\$|＄|€|£|USD|EUR|HKD|GBP|JPY|AUD|CAD|SGD|CHF|TWD|NTD|KRW)"
_FX_ZH = r"(?:美元|美金|欧元|港币|港元|英镑|日元|日圆|澳元|加元|新币|新加坡元|台币|韩元)"
FOREIGN_CURRENCY = rx(
    rf"{_FX}\s?\d|\d[\d,.]*\s?(?:[kKmM万千]|million|thousand)?\s?(?:{_FX}(?![A-Za-z])|dollars?\b|euros?\b|pounds?\b)|{_FX_ZH}"
    r"|\b(?:USD|EUR|HKD|GBP|JPY|AUD|CAD|SGD|CHF|TWD|NTD|KRW|dollars?|euros?)\b", I)

# ---- certainty and timing -------------------------------------------------------------------------------------------
HEDGE = rx(
    r"\b(?:might|maybe|perhaps|possibly|probably|potentially|tentatively|presumably|toying\s+with"
    r"|(?:we|i)\s+may|may\s+(?:well\s+)?(?:be\s+able\s+to|consider|pay|settle|possibly)"
    r"|(?:we|i)(?:'ll|\s+will|\s+would|\s+could)?\s+(?:consider|think\s+about|look\s+into)"
    r"|(?:thinking|thought)\s+(?:of|about)|not\s+(?:yet\s+)?(?:sure|certain|decided)"
    r"|at\s+some\s+point|sometime|some\s+day|someday|one\s+of\s+these\s+days)\b"
    r"|可能|也许|或许|说不定|不确定|看看|(?<!请)考虑|有可能|应该会|某个时候|找个时间|改天|以后再说|再看看", I)
AFTER_DUE = rx(
    r"\b(?:after|past|beyond|following)\s+(?:the\s+|its\s+|your\s+)?(?:original\s+|agreed\s+|stated\s+|invoice\s+)?due(?:\s+date)?\b"
    r"|\bpast[- ]due\b|\boverdue\b|\bdays?\s+late\b|\blater\s+than\s+(?:the\s+)?due\b|\bafter\s+maturity\b"
    r"|\b(?:pay|paying|settle|settling|settled|payment)\s+(?:it\s+|the\s+invoice\s+)?(?:a\s+(?:bit|little)\s+)?late\b"
    r"|\blate\s+(?:payment|settlement)\b|\bdelay(?:ed|ing)?\s+(?:the\s+)?(?:payment|settlement)\b|\bpay\s+later\b"
    r"|(?:到期|截止)(?:日|时间|期)?(?:之|以)?后|逾期|过期|超期|晚付|迟付|延(?:期|迟|后)(?:付|支付|结)|推迟(?:付|支付|结)|拖(?:欠|延|后)|宽限|晚于到期", I)

# ---- riders the typed rows cannot carry -----------------------------------------------------------------------------
PRICE_RIDER = rx(
    r"\b(?:keep|hold|freeze|lock|fix|maintain|leave|peg)\s+(?:all\s+)?(?:(?:our|the|your|current|existing|unit|today'?s)\s+)*prices?\b"
    r"|\bprices?\s+(?:freeze|lock|hold|guarantee|protection|ceiling|cap|stability)\b|\b(?:freeze|lock|cap)\s+(?:on\s+)?prices?\b"
    r"|\bprices?\s+(?:unchanged|frozen|fixed|flat|stable|stay(?:s)?\s+(?:the\s+same|flat|fixed|where)|remain(?:s)?"
    r"|(?:do|does|will|shall|must)\s*(?:not|n't)\s+(?:change|rise|go\s+up|increase))\b"
    r"|\bno\s+(?:further\s+|new\s+|more\s+)?price\s+(?:increases?|rises?|hikes?|changes?)\b"
    r"|\b(?:not|never|won'?t|will\s+not)\s+(?:raise|increase|hike|change)\s+(?:our\s+|the\s+|your\s+|any\s+)?prices?\b"
    r"|不涨价|不要涨价|别涨价|不调价|价格(?:保持)?(?:不变|稳定|冻结|锁定)|(?:保持|维持)(?:现有|目前|当前)?(?:的)?(?:价格|单价|报价)"
    r"|锁(?:定)?价|冻结(?:价格|单价)|价格冻结|稳价", I)

# ---- another party's invoice ------------------------------------------------------------------------------------------
_NOT_A_NAME = frozenset(
    ["your", "our", "my", "the", "this", "that", "these", "those", "their", "its", "his", "her", "we", "you", "i", "today", "yesterday", "tomorrow", "last", "next", "each", "every", "any", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])
_NAME = r"[A-Z][a-z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*){0,4}"
OTHER_PARTY_EN = [
    # "Dongguan Office Supplies' invoice", "Foshan's RCV-A invoice"
    re.compile(rf"(?<![\w'’])(?P<who>{_NAME})['’]s?\s+(?:[A-Za-z0-9#\-]+\s+){{0,2}}(?:invoices?|inv|bills?)\b"),
    # "the invoice of / for / from Dongguan Office Supplies"
    re.compile(rf"\b(?:invoices?|bills?)\s+(?:of|for|from|owed\s+by|issued\s+to)\s+(?:the\s+)?(?P<who>{_NAME})"),
]
OTHER_PARTY_ZH = re.compile(
    r"(?P<who>[^\s，。,；;！!？?的付我你贵们您把将要想愿给]{2,10}?)(?:公司|用品|贸易|商贸|商行|科技|集团|工厂|企业|超市|百货|批发|有限)"
    r"(?:的|那|这)?(?:张|笔|份)?(?:发票|货款|账单)")
_OWN_ZH = re.compile(r"^(?:我们|你们|咱们|我方|贵方|贵司|您|本|该|此|这|那)")

Scope = Literal["doc", "obligation_doc", "sentence"]


@dataclass(frozen=True, slots=True)
class _Check:
    field: str
    reason: str
    patterns: tuple[re.Pattern[str], ...]
    scope: Scope  # doc: fires on any offer text; obligation_doc: when the document carries a term; sentence: in a term's sentence
    drops_reading: bool = False  # the reading itself (its rate) is wrong, not only unbookable
    needs_rate: bool = False  # sentence scope: only when the sentence states a rate ("每天送货" alone is not a rate basis)


CHECKS: tuple[_Check, ...] = (
    _Check("offer.rate.unusual_form", UNUSUAL_RATE_REASON, (RATE_UNUSUAL,), "doc", drops_reading=True),
    _Check("offer.amount.unusual_form", UNUSUAL_AMOUNT_REASON, (AMOUNT_UNUSUAL,), "doc", drops_reading=True),
    _Check("offer.rate.per_day", "rate stated per day early: only a flat rate on the invoice can be "
           "booked; please confirm a single flat rate", (PER_DAY,), "sentence", drops_reading=True, needs_rate=True),
    _Check("offer.terms.discount_code", "terms of the 2/10 net 30 kind (a discount tied to a payment day) cannot be "
           "booked; please state a flat discount or a payment-terms length", (TERMS_CODE,), "doc", drops_reading=True),
    _Check("offer.currency", "amount in a currency other than yuan; please confirm the amount in yuan",
           (FOREIGN_CURRENCY,), "obligation_doc"),
    _Check("offer.hedged", "the offer is hedged (might, maybe, probably, 可能), not a firm offer; please confirm "
           "that you offer it", (HEDGE,), "sentence"),
    _Check("offer.payment_after_due_date", "payment after the due date with a discount is not an early payment; "
           "nothing booked, please confirm the payment date", (AFTER_DUE,), "obligation_doc"),
    _Check("offer.rider.price_freeze", "a price commitment (freeze, lock, no increase) cannot be recorded as a term; "
           "please confirm what is offered for the payment", (PRICE_RIDER,), "obligation_doc"),
)
OTHER_PARTY_FIELD = "offer.base.other_party_invoice"
OTHER_PARTY_REASON = ("the message names another party's invoice; please confirm which of your own invoices the "
                      "offer applies to")


def _other_party_hits(text: str) -> list[re.Match[str]]:
    out: list[re.Match[str]] = []
    for pat in OTHER_PARTY_EN:
        out += [m for m in pat.finditer(text) if m.group("who").split()[0].lower() not in _NOT_A_NAME]
    out += [m for m in OTHER_PARTY_ZH.finditer(text) if not _OWN_ZH.match(m.group("who"))]
    return sorted(out, key=lambda m: m.start())


def _overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def boundary_guard(
    docs: dict[str, SourceDocument], obs: Sequence[Obligation], abst: list[Abstention]
) -> tuple[list[Obligation], bool]:
    """(obligations, material abstention) after checking every document for readings the typed rows cannot carry."""
    spans_by_doc: dict[str, list[SourceSpan]] = {}
    for ob in obs:
        for sp in ob.spans:
            spans_by_doc.setdefault(sp.doc_id, []).append(sp)
    dropped: set[int] = set()
    material = False

    def sentence(doc_id: str, pos: int) -> tuple[int, int]:
        return lexicon.sentence_bounds(docs[doc_id].text, pos)

    def in_term_sentence(doc_id: str, s: int, e: int) -> bool:
        ss, se = sentence(doc_id, s)
        return any(_overlaps(ss, se, sp.start, sp.end) for sp in spans_by_doc.get(doc_id, ()))

    def states_rate(doc_id: str, pos: int) -> bool:
        ss, se = sentence(doc_id, pos)
        return RATE_RE.search(docs[doc_id].text, ss, se) is not None

    def hit(field: str, reason: str, doc_id: str, s: int, e: int, drops: bool) -> None:
        nonlocal material
        material = True
        text = docs[doc_id].text
        abst.append(Abstention(field=field, reason=reason,
                               spans=[SourceSpan(doc_id=doc_id, start=s, end=e, text=text[s:e])]))
        if drops:
            ss, se = sentence(doc_id, s)
            for n, ob in enumerate(obs):
                if any(sp.doc_id == doc_id and _overlaps(ss, se, sp.start, sp.end) for sp in ob.spans):
                    dropped.add(n)

    for doc_id, doc in docs.items():
        text = doc.text
        for chk in CHECKS:
            if chk.scope != "doc" and doc_id not in spans_by_doc:
                continue  # a document with no term in it has nothing here to mis-book
            first = next((m for pat in chk.patterns for m in pat.finditer(text)
                          if chk.scope != "sentence" or (in_term_sentence(doc_id, m.start(), m.end())
                                                         and (not chk.needs_rate or states_rate(doc_id, m.start())))), None)
            if first is not None:  # one abstention per kind and document
                hit(chk.field, chk.reason, doc_id, first.start(), first.end(), chk.drops_reading)
        if doc_id in spans_by_doc:
            for m in _other_party_hits(text)[:1]:
                hit(OTHER_PARTY_FIELD, OTHER_PARTY_REASON, doc_id, m.start(), m.end(), False)
    kept = [ob for n, ob in enumerate(obs) if n not in dropped]
    return kept, material
