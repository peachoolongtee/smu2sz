"""Deterministic parsers for money, rates, days and counts in English and Chinese.

Every number that reaches a contract is parsed here from text that is itself an exact substring of a
source document. The model never supplies a number directly. Money is integer fen; rates are integer
bp. No float is used anywhere on these paths.

Numbers may be written in digits ("1.5%", "¥420k", "42万"), in English words ("one and a half percent",
"four hundred and twenty thousand yuan") or in Chinese numerals ("百分之一点五", "四十二万"). A form that is
colloquial and ambiguous ("四万二", "一千二") parses to None: the compiler then abstains instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------- CJK-safe word boundaries

# Python's `\b` treats CJK characters as word characters, so "批准APR-000003" or "评估一下EX05" has no
# boundary before the id. ASCII_B is a word boundary on ASCII word characters only.
_W_ASCII = "[A-Za-z0-9_]"
ASCII_B = rf"(?:(?<={_W_ASCII})(?!{_W_ASCII})|(?<!{_W_ASCII})(?={_W_ASCII}))"
_BACKSLASH_B = re.compile(r"(?<!\\)\\b")


def cjk_safe(pattern: str) -> str:
    r"""`pattern` with every `\b` replaced by ASCII_B (lookarounds on ASCII word characters)."""
    return _BACKSLASH_B.sub(lambda _m: ASCII_B, pattern)


def rx(pattern: str, flags: int | re.RegexFlag = 0) -> re.Pattern[str]:
    """re.compile with CJK-safe word boundaries."""
    return re.compile(cjk_safe(pattern), flags)


# ---------------------------------------------------------------- money

_CUR = r"(?:¥|￥|RMB\s?|CNY\s?|人民币\s?)"
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_UNIT = r"(?:[kK](?![a-zA-Z])|mn\b|million\b|thousand\b|m(?![a-zA-Z])|M(?![a-zA-Z])|万|亿|千)"
_SUFFIX = r"(?:元|\s?yuan\b|\s?RMB\b|\s?CNY\b)"

# A number with no currency marker is money only when the word right after it names a bill: "the 420k inv",
# "the 420,000 invoice". `ctx` is an empty group that records that lookahead.
_BILL_CTX = r"(?:(?P<ctx>)(?=\s?(?:的|那张|这张|那笔|这笔)?\s?(?:inv(?:oice)?s?\b|inv\.|bills?\b|发票|货款|张票)))"

# A 万/亿 count of things is not money: "一万步", "3万人参加", "五万公里" (人 is a measure word, but not in 人民币).
_ZH_MEASURE = r"(?:人(?!民币)|步|公里|公斤|里|米|斤|吨|亩|平方|字|次|个|只|台|套|件|辆|名|户|股|册|份)"
_ZH_MEASURE_RE = re.compile(_ZH_MEASURE)
_ARABIC_TO_ZH = str.maketrans("123456789", "一二三四五六七八九")
# Arabic numeral and Chinese tail in one amount: "3万5千元" = 35,000, "1亿2千万" = 120,000,000, "2万3千5百元".
# The tail needs a 千/百 digit (a bare "3万5" stays ambiguous and is not read).
_MIXED_TAIL = r"(?:[1-9一二两三四五六七八九][千百]){1,2}(?:[1-9一二三四五六七八九]十)?"
MIXED_ZH_RE = re.compile(
    rf"(?P<num>\d+(?:\.\d+)?)(?P<unit>[万亿])\s?(?P<tail>{_MIXED_TAIL}[万]?)(?P<zs>元整?|块钱?)?")

MONEY_RE = re.compile(
    rf"(?P<cur>{_CUR})?(?P<num>{_NUM})(?:\s?(?P<unit>{_UNIT}))?(?P<suffix>{_SUFFIX})?{_BILL_CTX}?",
)

_UNIT_MULT = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "m": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "千": Decimal(1_000),
    "万": Decimal(10_000),
    "亿": Decimal(100_000_000),
}

# English number words: "four hundred and twenty thousand yuan" (a currency word is required).
_EN_SMALL = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_EN_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_EN_SCALE = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}
_EN_W = "(?:" + "|".join(sorted([*_EN_SMALL, *_EN_TENS, *_EN_SCALE], key=len, reverse=True)) + ")"
EN_WORD_MONEY_RE = re.compile(
    rf"(?i:(?<![A-Za-z-])(?P<w>{_EN_W}(?:(?:\s+and\s+|[\s-]+){_EN_W})*)\s+(?:yuan|rmb|renminbi|cny)(?![A-Za-z]))")
# Chinese numerals: "四十二万", "三十万元", "五千元". A 万/亿 unit or a 元/块 suffix is required.
# Financial (大写) numerals are the same numbers written fraud-proof: 肆拾贰万元整 = 四十二万元.
_ZH_CAPITAL = str.maketrans("壹贰叁肆伍陆柒捌玖拾佰仟〇", "一二三四五六七八九十百千零")
_ZH_N = "零〇一二两三四五六七八九十百千壹贰叁肆伍陆柒捌玖拾佰仟"
ZH_WORD_MONEY_RE = re.compile(
    rf"(?:人民币\s?)?(?<![{_ZH_N}万亿])(?P<z>[{_ZH_N}]+(?:(?:万|亿)[{_ZH_N}万亿]*)?)(?P<zs>元整?|块钱?)?")
_ZH_DIGIT_VALUES = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_ZH_UNIT_VALUES = {"十": 10, "百": 100, "千": 1_000}


@dataclass(frozen=True)
class Found:
    start: int
    end: int
    value: int  # fen, bp, days or a count
    text: str


def _strip_names(p: str) -> str:
    return re.sub(r"\?P<\w+>", "?:", p)


# Same grammar, no named groups: digits (with ¥/k/万), English number words, Chinese numerals.
MONEY_PAT = (
    f"(?:(?:{_strip_names(MIXED_ZH_RE.pattern)}|{_strip_names(MONEY_RE.pattern)}|{_strip_names(EN_WORD_MONEY_RE.pattern)}"
    rf"|(?:人民币\s?)?(?<![{_ZH_N}万亿])[{_ZH_N}]+(?:(?:万|亿)[{_ZH_N}万亿]*(?:元整?|块钱?)?|元整?|块钱?))"
    rf"(?:(?<![万亿])|(?!{_ZH_MEASURE})))"
)


def _money_value(m: re.Match[str]) -> int | None:
    cur, unit, suffix = m.group("cur"), m.group("unit"), m.group("suffix")
    unit_key = unit.lower() if unit and unit not in "千万亿" else unit
    # A bare number is not money. Chinese 万/亿 are unambiguous; k/m need a currency marker, or a bill noun
    # right after a k/m amount or a comma-grouped one ("420k inv", "the 420,000 invoice").
    bill = m.group("ctx") is not None and (unit_key in {"k", "m", "mn", "million", "thousand"} or "," in m.group("num")
                                           or (not unit_key and re.fullmatch(r"\d{5,}", m.group("num")) is not None))
    if not (cur or suffix or unit_key in {"万", "亿"} or bill):
        return None
    if unit_key in {"万", "亿"} and not (cur or suffix) and _ZH_MEASURE_RE.match(m.string, m.end()):
        return None  # "3万人", "一万步": a count, not money
    if unit_key in {"万", "亿"} and re.match(r"[1-9一二两三四五六七八九]", m.string[m.end():m.end() + 1]) and not suffix:
        return None  # "3万5" (35,000 colloquially): do not guess, as "四万二"
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


def en_number_words(text: str) -> int | None:
    """'four hundred and twenty thousand' -> 420000. None if the words do not form one number."""
    toks = re.findall(_EN_W, text.lower())
    if not toks:
        return None
    total = cur = 0
    prev: str | None = None
    for tok in toks:
        if tok in _EN_SMALL or tok in _EN_TENS:
            # "two three", "twenty thirty", "twenty twelve": not one number
            if prev in _EN_SMALL or (prev in _EN_TENS and _EN_SMALL.get(tok, 10) >= 10):
                return None
            cur += _EN_SMALL.get(tok, _EN_TENS.get(tok, 0))
        elif tok == "hundred":
            if prev is None or prev in _EN_SCALE:
                return None
            cur *= 100
        else:
            if prev is None or (prev in _EN_SCALE and prev != "hundred"):
                return None
            total += cur * _EN_SCALE[tok]
            cur = 0
        prev = tok
    return total + cur


def _zh_section(s: str) -> int | None:
    """A Chinese numeral below 10,000: '四千二百', '三十', '十二'. Colloquial '一千二' is refused (ambiguous)."""
    n = cur = 0
    last_unit = 0
    zero_seen = False
    for ch in s:
        if ch in _ZH_DIGIT_VALUES:
            if ch == "零":
                zero_seen = True
                continue
            cur = _ZH_DIGIT_VALUES[ch]
        elif ch in _ZH_UNIT_VALUES:
            unit = _ZH_UNIT_VALUES[ch]
            n += (cur or 1) * unit
            cur = 0
            last_unit = unit
        else:
            return None
    if cur and last_unit >= 100 and not zero_seen:
        return None  # "一千二" (1,200 colloquially): do not guess
    return n + cur


def zh_number(s: str) -> int | None:
    """'四十二万' -> 420000, '一亿二千万' -> 120000000, '十二' -> 12, '肆拾贰万' -> 420000. None when not one
    exact number."""
    total = 0
    rest = s.translate(_ZH_CAPITAL)
    for big, mult in (("亿", 100_000_000), ("万", 10_000)):
        if big in rest:
            head, rest = rest.split(big, 1)
            v = zh_number(head) if big == "亿" and "万" in head else _zh_section(head)
            if not v:
                return None
            total += v * mult
            # "四万二" (42,000 colloquially): a bare digit after the unit is ambiguous
            if len(rest) == 1 and rest in _ZH_DIGIT_VALUES and rest != "零":
                return None
    if rest:
        v = _zh_section(rest)
        if v is None:
            return None
        total += v
    return total


def _word_money(text: str) -> list[Found]:
    out: list[Found] = []
    for m in EN_WORD_MONEY_RE.finditer(text):
        n = en_number_words(m.group("w"))
        if n:
            out.append(Found(m.start(), m.end(), n * 100, m.group(0)))
    for m in ZH_WORD_MONEY_RE.finditer(text):
        z = m.group("z")
        if not (m.group("zs") or "万" in z or "亿" in z):
            continue
        if not m.group("zs") and m.group(0)[:3] != "人民币" and _ZH_MEASURE_RE.match(text, m.end()):
            continue  # "一万步", "五万公里": a count, not money
        if not re.search("[一二两三四五六七八九十]", z.translate(_ZH_CAPITAL)):
            continue  # "千万" (by all means), not an amount
        n = zh_number(z)
        if n:
            out.append(Found(m.start(), m.end(), n * 100, m.group(0)))
    return out


def find_money(text: str) -> list[Found]:
    out: list[Found] = []
    for m in MIXED_ZH_RE.finditer(text):
        tail = zh_number(m.group("tail").translate(_ARABIC_TO_ZH))
        if not tail:
            continue
        d = Decimal(m.group("num")) * _UNIT_MULT[m.group("unit")] + tail
        if d * 100 == (d * 100).to_integral_value():
            out.append(Found(m.start(), m.end(), int(d * 100), m.group(0)))
    for m in MONEY_RE.finditer(text):
        v = _money_value(m)
        if v is None:
            continue
        s, e = m.start(), m.end()
        if any(s < o.end and o.start < e for o in out):
            continue
        raw = text[s:e]
        stripped = raw.rstrip()
        out.append(Found(s, s + len(stripped), v, stripped))
    for f in _word_money(text):
        if not any(f.start < o.end and o.start < f.end for o in out):
            out.append(f)
    return sorted(out, key=lambda f: f.start)


def parse_money(text: str | None) -> int | None:
    """The single money amount in `text`, in fen; None if there is none or more than one value."""
    if not text:
        return None
    vals = {f.value for f in find_money(text)}
    return vals.pop() if len(vals) == 1 else None


# ---------------------------------------------------------------- rates

_EN_DIGIT_WORD = "(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
_EN_RATE_WORDS = (
    r"(?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten)"
    rf"(?:\s+point(?:\s+{_EN_DIGIT_WORD})+|\s+and\s+(?:a\s+)?(?:half|quarter|three[\s-]quarters))?"
    rf"|point(?:\s+{_EN_DIGIT_WORD})+|half\s+(?:a|of\s+a|of\s+one)|a\s+half|a\s+quarter\s+of\s+a|a\s+quarter"
    r"|three[\s-]quarters\s+of\s+a)"
)
_ZH_DEC = "[零一二两三四五六七八九十]+(?:点[零一二三四五六七八九]+)?"
# Discounts are also quoted per mille (千分之六 = 0.6%), per ten-thousand (万分之五 = 5 bp), in basis points
# ("30bps"), and as the share of the price still paid (99.3折 = pay 99.3% = 0.7% off; 九五折 = 5% off).
_ZH_DIGIT_RUN = "[零一二两三四五六七八九]"
RATE_RE = re.compile(
    rf"(?:百分之\s?(?P<zh>\d+(?:\.\d+)?|{_ZH_DEC}))"
    rf"|(?:千分之\s?(?P<pm>\d+(?:\.\d+)?|{_ZH_DEC}))"
    rf"|(?:万分之\s?(?P<pt>\d+(?:\.\d+)?|{_ZH_DEC}))"
    r"|(?:(?<![\d.])(?P<bps>\d+(?:\.\d+)?)\s?(?:bps|bp|basis\s+points?|个基点)(?![A-Za-z]))"
    rf"|(?:(?<![\d.])(?P<zhe>\d{{1,2}}(?:\.\d{{1,2}})?|{_ZH_DIGIT_RUN}{{1,3}})\s?折(?!扣|算|合|叠|旧|返|现|让))"
    r"|(?:(?<!\d,)(?P<num>\d+(?:\.\d+)?)\s?(?:%|％|\s?percent\b|\s?per\s?cent\b|\s?percentage\s+points?\b|个百分点|个点))"
    rf"|(?:(?P<zhp>{_ZH_DEC}|半)个点)|(?:(?P<zhh>[一二两三四五六七八九十]+)个半点)"
    rf"|(?i:(?<![A-Za-z-])(?P<en>{_EN_RATE_WORDS})\s+(?:percent|per\s?cent|percentage\s+points?)(?![A-Za-z]))"
)


RATE_PAT = _strip_names(RATE_RE.pattern)
_EN_DIGITS = {"zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
              "eight": 8, "nine": 9, "ten": 10}
_EN_FIXED = {"half a": "0.5", "half of a": "0.5", "half of one": "0.5", "a half": "0.5", "a quarter of a": "0.25",
             "a quarter": "0.25", "three quarters of a": "0.75"}
_EN_FRACTION = {"half": Decimal("0.5"), "quarter": Decimal("0.25"), "three quarters": Decimal("0.75")}


def _zh_decimal(s: str) -> Decimal | None:
    whole, _, frac = s.partition("点")
    w = zh_number(whole) if whole else 0
    if w is None:
        return None
    if not frac:
        return Decimal(w)
    return Decimal(f"{w}." + "".join(str(_ZH_DIGIT_VALUES[c]) for c in frac))


def _en_rate_value(s: str) -> Decimal | None:
    t = re.sub(r"[\s-]+", " ", s.lower()).strip()
    if t in _EN_FIXED:
        return Decimal(_EN_FIXED[t])
    m = re.fullmatch(r"(?:(\w+) )?point((?: \w+)+)", t)
    if m:
        whole = _EN_DIGITS.get(m.group(1) or "zero")
        digits = [_EN_DIGITS.get(w) for w in m.group(2).split()]
        if whole is None or any(d is None or d > 9 for d in digits):
            return None
        return Decimal(f"{whole}." + "".join(str(d) for d in digits))
    m = re.fullmatch(r"(\w+)(?: and (?:a )?(half|quarter|three quarters))?", t)
    if m and m.group(1) in _EN_DIGITS:
        return Decimal(_EN_DIGITS[m.group(1)]) + (_EN_FRACTION[m.group(2)] if m.group(2) else 0)
    return None


def _zhe_discount(raw: str) -> Decimal | None:
    """'99.3' -> 0.7, '95' -> 5, '9.5' -> 5, '九五' -> 5, '九' -> 10: the percentage taken off by an N折 price."""
    if raw[0].isdigit():
        pay = Decimal(raw)
        pay = pay * 10 if pay < 10 else pay
    else:
        digits = "".join(str(_ZH_DIGIT_VALUES[c]) for c in raw)
        pay = Decimal(digits) * 10 if len(digits) == 1 else Decimal(digits[:2] + ("." + digits[2:] if digits[2:] else ""))
    if not Decimal(50) <= pay < Decimal(100):
        return None
    return Decimal(100) - pay


def _rate_value(m: re.Match[str]) -> Decimal | None:
    try:
        if m.group("num"):
            return Decimal(m.group("num"))
        if m.group("pm"):
            z = m.group("pm")
            v = Decimal(z) if z[0].isdigit() else _zh_decimal(z)
            return None if v is None else v / 10
        if m.group("pt"):
            z = m.group("pt")
            v = Decimal(z) if z[0].isdigit() else _zh_decimal(z)
            return None if v is None else v / 100
        if m.group("bps"):
            return Decimal(m.group("bps")) / 100
        if m.group("zhe"):
            return _zhe_discount(m.group("zhe"))
        if m.group("zh"):
            z = m.group("zh")
            return Decimal(z) if z[0].isdigit() else _zh_decimal(z)
        if m.group("zhp"):
            return Decimal("0.5") if m.group("zhp") == "半" else _zh_decimal(m.group("zhp"))
        if m.group("zhh"):
            w = zh_number(m.group("zhh"))
            return None if w is None else Decimal(w) + Decimal("0.5")
        if m.group("en"):
            return _en_rate_value(m.group("en"))
    except (InvalidOperation, KeyError):
        return None
    return None


def find_rates(text: str) -> list[Found]:
    out: list[Found] = []
    for m in RATE_RE.finditer(text):
        v = _rate_value(m)
        if v is None:
            continue
        bp = v * 100
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

DAYS_RE = re.compile(r"(?P<n>\d+)\s?[-‑]?\s?(?:(?:business|working|calendar)\s+)?(?:days?\b|个?工作日|天|日)")
MONTHS_RE = re.compile(r"(?P<n>\d+)\s?[-‑]?\s?(?:months?\b|mos?\b|个月|月期)")
YEARS_RE = re.compile(r"(?P<n>\d+)\s?[-‑]?\s?(?:years?\b|yrs?\b|年期|年)")

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "a couple of": 2, "couple of": 2,
}
_ZH_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

NUMBER_WORD = r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[一二两三四五六七八九十]+"
# "the next invoice", "下一张发票": a bound of exactly one invoice.
SINGLE_NEXT_RE = re.compile(
    r"(?i:(?<![A-Za-z])(?:next|following|coming)\s+(?:invoice|order|bill|shipment|delivery)(?![A-Za-z]))"
    r"|下一?(?:张|笔|批)(?:发票|订单|单|货)")


def parse_count(text: str | None) -> int | None:
    """'3', 'three', '三', '十二', 'next invoice' -> int. The first count found, or None."""
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
    if SINGLE_NEXT_RE.search(text):
        return 1
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
