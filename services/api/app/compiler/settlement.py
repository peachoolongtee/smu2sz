"""Read a closed settlement grammar from a single whole-invoice discount clause.

Independent of model prompts/cache schema. Only one supported expression in one
payment clause is consumed. Unknown wording remains visible to the coverage proof.
The parser deliberately does not swallow a rider, holiday, time zone or business day.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from app.compiler.folding import fold
from app.domain.models import Obligation, ObligationType, PaymentTiming, SourceDocument, SourceSpan

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_NUMBER = r"(?:[1-9]\d?|one|two|three|four|five|six|seven|一|两|二|三|四|五|六|七|八|九|十)"
_EXPR = re.compile(
    r"(?<![A-Za-z])(?:by\s+(?:the\s+)?end\s+of\s+this\s+week|"
    r"(?:on\s+|by\s+)?\d{4}-\d{2}-\d{2}|"
    r"(?:within|in)\s+" + _NUMBER + r"\s+(?:calendar\s+)?days?|"
    r"(?:on\s+|by\s+)?this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"(?:by\s+)?(?:today|tomorrow|tmrw|tmr|tonight)|right\s+now|straight\s+away|right\s+away|now|immediately)(?![A-Za-z])"
    r"|\d{4}年\d{1,2}月\d{1,2}[日号](?:之前|以前|前)?"
    r"|本周内|(?:本|这)周[一二三四五六日天](?:之前|以前|前)?"
    r"|" + _NUMBER + r"天(?:内|后)|今天|明天|后天|今晚|现在|马上|立即|立刻|即刻",
    re.IGNORECASE,
)
_PAY = re.compile(r"\b(?:pay|settle|transfer|remit|wire|payment)\b|付|结清|结算|支付|转款|打款|汇款", re.IGNORECASE)
_UNSAFE = re.compile(
    r"\b(?:due|issued?|dated?|after|before|until|not|never|next|last|yesterday|business|working|banking|holiday|"
    r"utc|gmt|pst|est|cst|cet|timezone|time\s+zone)\b|"
    r"\b(?:am|pm)\b|\d{1,2}:\d{2}|到期|开票|工作日|节后|节前|下周|不付|未付|北京时间|时区|(?<![.\d])\d{1,2}\s*点",
    re.IGNORECASE,
)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _parse(span: SourceSpan, reference: int) -> PaymentTiming:
    text = span.text.lower()
    relation = "by" if text.startswith(("by ", "within ")) or text.endswith(("内", "前")) else "on"
    values: dict = {"expression": span, "reference_day": reference, "relation": relation}
    if re.search(r"\d{4}(?:-|年)", text):
        y, m, d = map(int, re.findall(r"\d+", text))
        return PaymentTiming(**values, basis="calendar_date", calendar_date=f"{y:04}-{m:02}-{d:02}")
    if text in {"本周内", "by end of this week", "by the end of this week"}:
        return PaymentTiming(**values, basis="week_end")
    for day, name in enumerate(_WEEKDAYS):
        if name in text:
            return PaymentTiming(**values, basis="this_weekday", weekday=day)
    zh = re.search(r"周([一二三四五六日天])", text)
    if zh:
        return PaymentTiming(**values, basis="this_weekday", weekday=min("一二三四五六日天".index(zh[1]), 6))
    if any(word in text for word in ("tomorrow", "tmrw", "tmr", "明天")):
        offset = 1
    elif text == "后天":
        offset = 2
    elif re.search(r"\bdays?\b|天(?:内|后)", text):
        raw = re.search(_NUMBER, text)
        assert raw is not None
        offset = int(raw[0]) if raw[0].isdigit() else _WORDS[raw[0]]
    else:
        offset = 0
    return PaymentTiming(**values, basis="relative_days", offset_days=offset)


def attach_payment_timing(docs: dict[str, SourceDocument], obligations: Sequence[Obligation]) -> list[Obligation]:
    result = list(obligations)
    discounts = [o for o in result if o.type == ObligationType.IMMEDIATE_DISCOUNT]
    # No heuristic attribution across several payments/discounts or documents.
    if len(discounts) != 1 or len(docs) != 1:
        return result
    ob = discounts[0]
    if ob.base.amount_fen is None or "base_amount" in ob.unresolved:
        return result
    doc = next(iter(docs.values()))
    if doc.received_day < 0:
        return result
    matches = list(_EXPR.finditer(doc.text))
    if len(matches) != 1 or _UNSAFE.search(doc.text):
        return result
    match = matches[0]
    # A bare Chinese "before" suffix does not prove an inclusive day deadline.
    # Ask rather than silently shift the discount entitlement by a calendar day.
    if match[0].endswith("前"):
        return result
    # Semicolons/newlines separate commercial clauses; decimal dots do not.
    left = max((m.end() for m in re.finditer(r"[;；。!?！\n]|\.(?!\d)", doc.text[:match.start()])), default=0)
    tail = re.search(r"[;；。!?！\n]|\.(?!\d)", doc.text[match.end():])
    right = match.end() + tail.start() if tail else len(doc.text)
    if not _PAY.search(doc.text[left:right]):
        return result
    # The date must belong to the extracted payment clause, not a signature or an attachment.
    if not any(s.doc_id == doc.doc_id and s.start < right and left < s.end for s in ob.spans):
        return result
    span = SourceSpan(doc_id=doc.doc_id, start=match.start(), end=match.end(), text=match[0])
    timing = _parse(span, doc.received_day)
    return [o.model_copy(update={"payment_timing": timing}) if o is ob else o for o in result]


def has_unread_timing(doc: SourceDocument, spans: Sequence[SourceSpan]) -> bool:
    """Unconsumed timing in a single-discount message, excluding metadata headers.

    Multi-term packages retain their existing owner-reviewed semantics; assigning a
    period across several commercial clauses requires the later clarification build.
    """
    from app.compiler.coverage import ALLOWED, TIMING_RE, mentions
    from app.compiler.lexicon import sentence_bounds

    regions = [(sentence_bounds(doc.text, sp.start)[0], sentence_bounds(doc.text, max(sp.start, sp.end - 1))[1])
               for sp in spans if sp.doc_id == doc.doc_id]

    def in_payment(start: int, end: int) -> bool:
        return any(lo <= start and end <= hi for lo, hi in regions)

    if any(m.kind in {"date", "days"} and in_payment(m.start, m.end) for m in mentions(doc)):
        return True
    folded = fold(doc.text)
    text = folded.text
    allowed = [(m.start(), m.end()) for pat in ALLOWED for m in pat.finditer(text)]
    return any(in_payment(*folded.span(m.start(), m.end()))
               and not any(start <= m.start() and m.end() <= end for start, end in allowed)
               for m in TIMING_RE.finditer(text))
