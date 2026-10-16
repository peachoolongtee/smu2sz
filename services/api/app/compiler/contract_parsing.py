"""Deterministic parsers for the number forms contracts use, on fragments that are exact substrings of a document.

Contracts state numbers twice, in words and in figures ("forty-five (45) days", "RMB 420,000 (four hundred and
twenty thousand yuan)"). Each parser returns `Parsed(value, conflict)`: when the words and the figures disagree,
the value is None and `conflict` is True, and grounding abstains with that reason instead of picking one. Money is
integer fen, rates integer bp, dates ISO strings; no float anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.compiler.parsing import en_number_words, find_money, find_rates
from app.domain.models import PaymentBasis, PriceUnit

I = re.IGNORECASE

_EN_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
             "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
             "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred")
_NUMW = "(?:" + "|".join(sorted(_EN_WORDS, key=len, reverse=True)) + ")"
EN_COUNT = rf"{_NUMW}(?:(?:-|\s+and\s+|\s+){_NUMW})*"
# A count as contracts write it: "forty-five (45)", "45", "forty-five". Use with re.IGNORECASE.
COUNT_PAT = rf"(?:(?:{EN_COUNT})\s*\(\s*\d{{1,4}}\s*\)|\(\s*\d{{1,4}}\s*\)|\d{{1,4}}(?![\d.,])|\b{EN_COUNT}\b)"
_EN_COUNT_RE = re.compile(rf"\b{EN_COUNT}\b", I)  # whole words only: "often" holds "ten" but states no number

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10,
    "nov": 11, "dec": 12,
}
_MONTH = "(?:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_ORD = r"(?:st|nd|rd|th)?"
# "1 September 2026", "1st day of September, 2026", "September 1, 2026", "2026-09-01", "2026年9月1日".
DATE_PAT = (rf"(?:\d{{1,2}}{_ORD}\s+(?:day\s+of\s+)?{_MONTH},?\s+\d{{4}}|{_MONTH}\s+\d{{1,2}}{_ORD},?\s+\d{{4}}"
            r"|\d{4}-\d{1,2}-\d{1,2}|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"
            r"|[〇零一二三四五六七八九]{4}年[一二三四五六七八九十]{1,3}月[一二三四五六七八九十]{1,3}日)")
_DATE_RE = re.compile(DATE_PAT, I)


@dataclass(frozen=True)
class Parsed:
    value: object = None
    conflict: bool = False  # the fragment states two different values (words against figures, or two figures)

    @property
    def ok(self) -> bool:
        return self.value is not None and not self.conflict


def parse_count(text: str | None) -> Parsed:
    """The count in "forty-five (45)", "(45)", "45" or "forty-five"."""
    if not text:
        return Parsed()
    paren = {int(x) for x in re.findall(r"\(\s*(\d{1,4})\s*\)", text)}
    bare = {int(x) for x in re.findall(r"(?<![\d.,(])(\d{1,4})(?![\d.,)])", text)}
    spoken = list(_EN_COUNT_RE.finditer(re.split(r"\(", text, maxsplit=1)[0]))
    words = en_number_words(spoken[-1].group(0)) if spoken else None  # the words next to the figures
    figures = paren | bare
    if len(figures) > 1 or (figures and words is not None and words not in figures):
        return Parsed(conflict=True)
    if figures:
        return Parsed(next(iter(figures)))
    return Parsed(words) if words is not None else Parsed()


_SAME_DAY = re.compile(r"\bsame\s+(?:business\s+|working\s+|banking\s+)?day\b|\bsame[- ]day\b|\bimmediately\b"
                       r"|\bno\s+lead\s+time\b|当天|当日|即时", I)
_BUSINESS = re.compile(r"\b(?:business|working|banking)\s+days?\b|工作日", I)


def parse_days(text: str | None) -> Parsed:
    """A day count: "forty-five (45) days", "45 days", "within three (3) Business Days", "30天"."""
    if not text:
        return Parsed()
    m = re.search(r"\d{1,4}\s*(?:个)?(?:工作日|天|日)", text)
    if m:
        return Parsed(int(re.match(r"\d+", m.group(0)).group(0)))  # type: ignore[union-attr]
    if not re.search(r"\bdays?\b", text, I):
        return Parsed()
    return parse_count(re.split(r"\bdays?\b", text, maxsplit=1, flags=I)[0])


def parse_lead_days(text: str | None) -> Parsed:
    """A lead time: "the same day" and "immediately" are 0; otherwise a day count."""
    if text and _SAME_DAY.search(text):
        return Parsed(0)
    return parse_days(text)


def business_days(text: str | None) -> bool:
    return bool(text and _BUSINESS.search(text))


def parse_months(text: str | None) -> Parsed:
    """A term in months: "twelve (12) months", "2 years" (24), "one year" (12)."""
    if not text:
        return Parsed()
    m = re.search(r"\b(months?|years?)\b|个月|年", text, I)
    if not m:
        return Parsed()
    unit = 12 if m.group(0).lower().startswith("year") or m.group(0) == "年" else 1
    head = text[:m.start()]
    if re.fullmatch(r"\s*(?:one|a)\s*", head, I):
        return Parsed(unit)
    n = parse_count(head)
    if not n.ok:
        return n
    return Parsed(int(n.value) * unit)  # type: ignore[call-overload]


def parse_date(text: str | None) -> Parsed:
    """The one calendar date in `text`, as an ISO string."""
    if not text:
        return Parsed()
    found: set[str] = set()
    for m in _DATE_RE.finditer(text):
        iso = _iso(m.group(0))
        if iso is None:
            return Parsed(conflict=True)  # "31 September 2026": not a date
        found.add(iso)
    if len(found) > 1:
        return Parsed(conflict=True)
    return Parsed(found.pop()) if found else Parsed()


_CN_DIGIT = {c: str(i) for i, c in enumerate("〇一二三四五六七八九")} | {"零": "0"}


def _cn_small(t: str) -> int:
    """一 .. 三十一 in Chinese numerals ("九", "十二", "二十", "二十五")."""
    if "十" not in t:
        return int(_CN_DIGIT[t])
    head, _, tail = t.partition("十")
    return (int(_CN_DIGIT[head]) if head else 1) * 10 + (int(_CN_DIGIT[tail]) if tail else 0)


def _iso(s: str) -> str | None:
    s = s.strip()
    try:
        if m := re.fullmatch(r"([〇零一二三四五六七八九]{4})年([一二三四五六七八九十]{1,3})月([一二三四五六七八九十]{1,3})日", s):
            y, mo, d = int("".join(_CN_DIGIT[c] for c in m.group(1))), _cn_small(m.group(2)), _cn_small(m.group(3))
        elif m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        elif m := re.fullmatch(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", s):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        elif m := re.fullmatch(rf"(\d{{1,2}}){_ORD}\s+(?:day\s+of\s+)?({_MONTH}),?\s+(\d{{4}})", s, I):
            d, mo, y = int(m.group(1)), _MONTHS[m.group(2).rstrip(".").lower()], int(m.group(3))
        elif m := re.fullmatch(rf"({_MONTH})\s+(\d{{1,2}}){_ORD},?\s+(\d{{4}})", s, I):
            mo, d, y = _MONTHS[m.group(1).rstrip(".").lower()], int(m.group(2)), int(m.group(3))
        else:
            return None
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_money(text: str | None) -> Parsed:
    """The amount in fen; an amount in words beside the figures must agree with them."""
    if not text:
        return Parsed()
    values = {f.value for f in find_money(text)}
    if len(values) > 1:
        return Parsed(conflict=True)
    return Parsed(values.pop()) if values else Parsed()


def parse_rate(text: str | None) -> Parsed:
    """The rate in bp ("1.2%", "one point two per cent (1.2%)", "千分之五")."""
    if not text:
        return Parsed()
    values = {f.value for f in find_rates(text)}
    if len(values) > 1:
        return Parsed(conflict=True)
    return Parsed(values.pop()) if values else Parsed()


def basis_of(text: str | None) -> PaymentBasis | None:
    """What payment terms count from, read from the fragment that states it."""
    if not text:
        return None
    if re.search(r"accept|验收", text, I):
        return PaymentBasis.ACCEPTANCE
    if re.search(r"end\s+of\s+(?:the\s+)?(?:calendar\s+)?month|month[- ]end|月结|月底|月末", text, I):
        return PaymentBasis.MONTH_END
    if re.search(r"deliver|receipt\s+of\s+(?:the\s+)?(?:goods|products|batch|consignment)|shipment|到货|交货|收货", text, I):
        return PaymentBasis.DELIVERY
    if re.search(r"invoice|发票|开票", text, I):
        return PaymentBasis.INVOICE
    return None


def unit_of(text: str | None) -> PriceUnit | None:
    """What a price is for, read from the fragment that states it."""
    if not text:
        return None
    if re.search(r"\b(?:batch(?:es)?|deliver(?:y|ies)|shipments?|consignments?|orders?)\b|每批|每次交货", text, I):
        return PriceUnit.PER_DELIVERY
    if re.search(r"\b(?:units?|pieces?|items?|sets?)\b|每件|每台|每套|单价", text, I):
        return PriceUnit.PER_UNIT
    if re.search(r"\bmonth(?:ly)?\b|每月", text, I):
        return PriceUnit.PER_MONTH
    if re.search(r"\b(?:contract|total)\s+(?:price|sum|value)\b|\blump\s+sum\b|合同总价|总价", text, I):
        return PriceUnit.LUMP_SUM
    return None


__all__ = [
    "COUNT_PAT",
    "DATE_PAT",
    "EN_COUNT",
    "Parsed",
    "basis_of",
    "business_days",
    "parse_count",
    "parse_date",
    "parse_days",
    "parse_lead_days",
    "parse_money",
    "parse_months",
    "parse_rate",
    "unit_of",
]
