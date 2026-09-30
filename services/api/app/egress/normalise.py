"""Text normalisation and numeric tokenisation for the egress guard.

Every surface form of a value is reduced to one canonical token before matching:

- NFKC folds full-width digits, currency signs and Latin letters; zero-width characters are removed
  and thin/narrow spaces between digits are treated as thousands separators.
- Chinese numerals become Arabic ("三十万" -> 300000, "六点四" -> 6.4), and "百分之N" becomes "N%".
- Thousands commas are removed; "bp"/"bps"/"basis points" become a percentage; "percent" becomes "%".
- Multipliers expand to plain yuan with a currency marker: "30万" / "300k" / "300 thousand" /
  "1.5 million" / "¥1.5m" -> "¥300000" etc.
- "×", "times", "倍" and a trailing "x" become the ratio suffix "x".

Canonical numbers carry no trailing zeros: "300,000.00" -> "300000", "6.40%" -> "6.4%".
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_ZERO_WIDTH = re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]")
_DIGIT_GAP = re.compile(r"(?<=\d)[\u00a0\u2007\u2008\u2009\u200a\u202f](?=\d)")

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}
_CN_RUN = re.compile(
    "[零〇一二两三四五六七八九十][零〇一二两三四五六七八九十百千万亿]*(?:点[零〇一二两三四五六七八九]+)?"
)

_NUM = r"(\d+(?:\.\d+)?)"
_PCT_OF = re.compile(r"百分之\s*" + _NUM)
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_PCT_WORD = re.compile(r"(?<=\d)\s*(?:percent|per cent|pct)(?![a-z])|(?<=\d)\s+%")
_BP = re.compile(_NUM + r"\s*(?:bps|bp|basis points?)(?![a-z])")
_WAN = re.compile(_NUM + "(万|亿)")
_K = re.compile(_NUM + r"k(?![a-z])")
_THOUSAND = re.compile(_NUM + r"\s*thousand")
_MILLION = re.compile(_NUM + r"\s*(?:million|mn)(?![a-z])")
_CUR_M = re.compile(r"(¥|\$|rmb|cny)(\s*)" + _NUM + r"m(?![a-z])")
_RATIO = re.compile(r"(?<=\d)(?:\s*×|\s*times(?![a-z])|\s*倍|\s*x(?![a-z]))")

_TOKEN = re.compile(r"(?<![\d.])" + _NUM + r"(?!\d)")
_PREFIX_MARKERS = ("¥", "$", "rmb", "cny", "人民币")
_SUFFIX_MARKERS = ("元", "yuan", "rmb", "cny", "块")


def canon(d: Decimal) -> str:
    """Plain decimal string without exponent or trailing zeros: Decimal('300000.00') -> '300000'."""
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    s = s.removeprefix("-")
    return s or "0"


def _cn_int(s: str) -> int:
    if not any(ch in _CN_UNITS or ch in "万亿" for ch in s):
        return int("".join(str(CN_DIGITS[ch]) for ch in s))
    total = section = num = 0
    for ch in s:
        if ch in CN_DIGITS:
            num = CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            section += (num or 1) * _CN_UNITS[ch]
            num = 0
        elif ch == "万":
            total += (section + num) * 10_000
            section = num = 0
        elif ch == "亿":
            total = (total + section + num) * 100_000_000
            section = num = 0
    return total + section + num


def _cn_number(m: re.Match[str]) -> str:
    run = m.group(0)
    whole, _, frac = run.partition("点")
    try:
        out = str(_cn_int(whole))
    except (KeyError, ValueError):
        return run
    if frac:
        out += "." + "".join(str(CN_DIGITS[ch]) for ch in frac)
    return out


def _dec(s: str) -> Decimal:
    try:
        return Decimal(s)
    except InvalidOperation:  # pragma: no cover - the regexes only capture valid numbers
        return Decimal(0)


def _scaled(factor: int) -> Callable[[re.Match[str]], str]:
    def repl(m: re.Match[str]) -> str:
        return "¥" + canon(_dec(m.group(1)) * factor)

    return repl


def _wan(m: re.Match[str]) -> str:
    return "¥" + canon(_dec(m.group(1)) * (10_000 if m.group(2) == "万" else 100_000_000))


def fold(text: str) -> str:
    """Light form for names and tokens: no zero-width characters, NFKC, lower case, single spaces.

    Numbers are left alone, so a name next to a number ("Bank-2 x") or a CJK name that contains
    a numeral character keeps its shape.
    """
    t = unicodedata.normalize("NFKC", _ZERO_WIDTH.sub("", text)).lower()
    return " ".join(t.split())


def normalise(text: str) -> str:
    """Canonical form of `text` for matching numbers (see module docstring)."""
    t = _ZERO_WIDTH.sub("", text)
    t = _DIGIT_GAP.sub("", t)
    t = unicodedata.normalize("NFKC", t).lower()
    t = _CN_RUN.sub(_cn_number, t)
    t = _PCT_OF.sub(r"\1%", t)
    t = _THOUSANDS.sub("", t)
    t = _PCT_WORD.sub("%", t)
    t = _BP.sub(lambda m: canon(_dec(m.group(1)) / 100) + "%", t)
    t = _WAN.sub(_wan, t)
    t = _CUR_M.sub(lambda m: m.group(1) + m.group(2) + canon(_dec(m.group(3)) * 1_000_000), t)
    t = _K.sub(_scaled(1_000), t)
    t = _THOUSAND.sub(_scaled(1_000), t)
    t = _MILLION.sub(_scaled(1_000_000), t)
    t = _RATIO.sub("x", t)
    return t


@dataclass(frozen=True, slots=True)
class NumToken:
    """One number in normalised text: canonical digits, its suffix and whether a currency marks it."""

    canon: str
    suffix: str  # "%", "x" or ""
    marked: bool  # a currency sign or word sits next to it
    identifier: bool  # part of an identifier such as "inv-300000" or "abc300000"


def _is_alnum_ascii(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch == "_")


def tokens(norm: str) -> list[NumToken]:
    """Every boundary-delimited number in already-normalised text."""
    out: list[NumToken] = []
    for m in _TOKEN.finditer(norm):
        start, end = m.span(1)
        nxt = norm[end : end + 1]
        suffix = nxt if nxt in ("%", "x") else ""
        before = norm[max(0, start - 8) : start].rstrip()
        after = norm[end : end + 6].lstrip()
        marked = before.endswith(_PREFIX_MARKERS) or after.startswith(_SUFFIX_MARKERS)
        prev = norm[start - 1 : start]
        glued_before = bool(prev) and _is_alnum_ascii(prev)  # "abc300000"
        hyphen_id = prev == "-" and start >= 2 and _is_alnum_ascii(norm[start - 2])  # "inv-300000"
        glued_after = not suffix and nxt.isascii() and nxt.isalpha()  # "300000abc"
        ident = not marked and (glued_before or hyphen_id or glued_after)
        out.append(NumToken(canon(_dec(m.group(1))), suffix, marked, ident))
    return out


_SENTENCE = re.compile(r"(?<!\d)\.|\.(?!\d)|[!?;。！？；\n]")
_DAYS = re.compile(
    r"(?<![\d.])(\d{1,4})\s*-?\s*(?:calendar\s+)?(?:days?|天|日)(?![a-z])"
    r"|net\s*-?\s*(\d{1,4})(?!\d)"
    r"|账期\s*(\d{1,4})(?!\d)"
)


def sentences(norm: str) -> list[str]:
    return [s for s in _SENTENCE.split(norm) if s.strip()]


def day_counts(sentence: str) -> set[int]:
    """Day counts stated in one normalised sentence ("60 days", "60-day", "60天", "net 60", "账期60")."""
    return {int(next(g for g in m.groups() if g)) for m in _DAYS.finditer(sentence)}


def squash(norm: str) -> str:
    """Only letters and digits: defeats spacing and punctuation tricks for long canary tokens."""
    return "".join(ch for ch in norm if ch.isalnum())
