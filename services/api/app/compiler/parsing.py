"""Deterministic parsers for money, rates, days and counts in English and Chinese.

Every number that reaches a contract is parsed here from text that is itself an exact substring of a
source document. The model never supplies a number directly. Money is integer fen; rates are integer
bp. No float is used anywhere on these paths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------- money

_CUR = r"(?:¥|￥|RMB\s?|CNY\s?|人民币\s?)"
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_UNIT = r"(?:[kK](?![a-zA-Z])|mn\b|million\b|m(?![a-zA-Z])|M(?![a-zA-Z])|万|亿|千)"
_SUFFIX = r"(?:元|\s?yuan\b|\s?RMB\b|\s?CNY\b)"

MONEY_RE = re.compile(
    rf"(?P<cur>{_CUR})?(?P<num>{_NUM})(?:\s?(?P<unit>{_UNIT}))?(?P<suffix>{_SUFFIX})?",
)

_UNIT_MULT = {
    "k": Decimal(1_000),
    "m": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "千": Decimal(1_000),
    "万": Decimal(10_000),
    "亿": Decimal(100_000_000),
}


@dataclass(frozen=True)
class Found:
    start: int
    end: int
    value: int  # fen, bp, days or a count
    text: str


MONEY_PAT = re.sub(r"\?P<\w+>", "?:", MONEY_RE.pattern)  # same grammar, no named groups


def _money_value(m: re.Match[str]) -> int | None:
    cur, unit, suffix = m.group("cur"), m.group("unit"), m.group("suffix")
    unit_key = unit.lower() if unit and unit not in "千万亿" else unit
    # A bare number is not money. Chinese 万/亿 are unambiguous; k/m need a currency marker.
    if not (cur or suffix or unit_key in {"万", "亿"}):
        return None
    try:
        d = Decimal(m.group("num").replace(",", ""))
    except InvalidOperation:
        return None
    if unit_key:
        d *= _UNIT_MULT[unit_key]
    fen = d * 100
    if fen != fen.to_integral_value():
        return None
    return int(fen)


def find_money(text: str) -> list[Found]:
    out: list[Found] = []
    for m in MONEY_RE.finditer(text):
        v = _money_value(m)
        if v is None:
            continue
        s, e = m.start(), m.end()
        raw = text[s:e]
        stripped = raw.rstrip()
        out.append(Found(s, s + len(stripped), v, stripped))
    return out


def parse_money(text: str | None) -> int | None:
    """The single money amount in `text`, in fen; None if there is none or more than one value."""
    if not text:
        return None
    vals = {f.value for f in find_money(text)}
    return vals.pop() if len(vals) == 1 else None


# ---------------------------------------------------------------- rates

RATE_RE = re.compile(
    r"(?:百分之\s?(?P<zh>\d+(?:\.\d+)?))|(?:(?P<num>\d+(?:\.\d+)?)\s?(?:%|％|\s?percent\b|\s?per\s?cent\b|个点))"
)


RATE_PAT = re.sub(r"\?P<\w+>", "?:", RATE_RE.pattern)


def find_rates(text: str) -> list[Found]:
    out: list[Found] = []
    for m in RATE_RE.finditer(text):
        raw = m.group("zh") or m.group("num")
        try:
            bp = Decimal(raw) * 100
        except InvalidOperation:
            continue
        if bp != bp.to_integral_value():
            continue
        out.append(Found(m.start(), m.end(), int(bp), m.group(0)))
    return out


def parse_rate_bp(text: str | None) -> int | None:
    """The single percentage in `text`, in integer bp; None if absent, ambiguous or sub-bp."""
    if not text:
        return None
    vals = {f.value for f in find_rates(text)}
    return vals.pop() if len(vals) == 1 else None


# ---------------------------------------------------------------- days, months, counts

DAYS_RE = re.compile(r"(?P<n>\d+)\s?[-‑]?\s?(?:days?\b|天|日)")
MONTHS_RE = re.compile(r"(?P<n>\d+)\s?[-‑]?\s?(?:months?\b|mos?\b|个月|月期)")
YEARS_RE = re.compile(r"(?P<n>\d+)\s?[-‑]?\s?(?:years?\b|yrs?\b|年期|年)")

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "a couple of": 2, "couple of": 2,
}
_ZH_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

NUMBER_WORD = r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[一二两三四五六七八九十]+"


def parse_count(text: str | None) -> int | None:
    """'3', 'three', '三', '十二' -> int. The first count found, or None."""
    if not text:
        return None
    t = text.strip().lower()
    m = re.search(r"\d+", t)
    if m:
        return int(m.group(0))
    for w, n in sorted(_WORDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{w}\b", t):
            return n
    m = re.search(r"[一二两三四五六七八九十]+", text)
    if m:
        return _zh_number(m.group(0))
    return None


def _zh_number(s: str) -> int | None:
    if s == "十":
        return 10
    if "十" in s:
        tens, _, units = s.partition("十")
        t = _ZH_DIGITS.get(tens, 1) if tens else 1
        u = _ZH_DIGITS.get(units, 0) if units else 0
        return t * 10 + u
    if len(s) == 1:
        return _ZH_DIGITS.get(s)
    return None


def parse_days(text: str | None) -> int | None:
    """A payment-terms length in days: '60 days', '60-day', '60天', 'Net 60', or a bare '30'."""
    if not text:
        return None
    m = DAYS_RE.search(text)
    if m:
        return int(m.group("n"))
    m = re.search(r"(?i)\bnet\s?(\d+)\b", text)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"\s*(\d+)\s*", text)
    return int(m.group(1)) if m else None


def parse_tenor_months(text: str | None) -> int | None:
    if not text:
        return None
    m = MONTHS_RE.search(text)
    if m:
        return int(m.group("n"))
    m = YEARS_RE.search(text)
    if m:
        return int(m.group("n")) * 12
    if re.search(r"(?i)\b(?:one|a)[- ]year\b|一年", text):
        return 12
    return None
