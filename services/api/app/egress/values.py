"""Protected and allowed values, their surface renderings and canonical match keys.

A `PrivateValue` is one value that must never leave in text to a counterparty unless the recipient
owns it. Its `repr` never shows the value or aliases, so it is safe in logs and assertion messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction

from app.domain.money import BP_DENOM, FEN_PER_YUAN, fmt_yuan, round_half_up
from app.egress.normalise import canon, fold, normalise, squash

OWNER_ID = "OWNER"  # the SME owner: entitled to every value marked `owner_visible`


class ValueKind(StrEnum):
    MONEY = "MONEY"  # integer fen
    RATE = "RATE"  # an annual or per-period rate: integer bp or an exact Fraction of 1
    RATIO = "RATIO"  # integer bp, 12500 = 1.25x
    TERMS = "TERMS"  # payment terms in days, matched only next to one of the owner's aliases
    TEXT = "TEXT"  # a name or token, matched as a phrase


class Category(StrEnum):
    MANDATE = "MANDATE"
    FACILITY = "FACILITY"
    BALANCE = "BALANCE"
    COUNTERPARTY_TERMS = "COUNTERPARTY_TERMS"
    CONCESSION = "CONCESSION"
    RESERVATION = "RESERVATION"
    NAME = "NAME"
    CANARY = "CANARY"
    OTHER = "OTHER"


def _as_rate(value: int | Fraction) -> Fraction:
    return Fraction(value, BP_DENOM) if isinstance(value, int) else Fraction(value)


@dataclass(frozen=True, slots=True)
class PrivateValue:
    """One protected value. `owner` is the one counterparty entitled to see it (None: nobody).

    `owner_visible` says whether the SME owner may see it: True for the supplier's own state and
    mandate, False for a buyer's hidden reservation and for canaries.
    """

    label: str
    kind: ValueKind
    value: int | Fraction | str = field(repr=False)
    owner: str | None = None
    category: Category = Category.OTHER
    owner_visible: bool = True
    aliases: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("a protected value needs a label")
        if self.kind in (ValueKind.MONEY, ValueKind.RATIO, ValueKind.TERMS):
            if not isinstance(self.value, int) or isinstance(self.value, bool) or self.value <= 0:
                raise ValueError(f"{self.label}: {self.kind} must be a positive int")
        elif self.kind is ValueKind.RATE:
            if isinstance(self.value, bool) or not isinstance(self.value, int | Fraction) or self.value <= 0:
                raise ValueError(f"{self.label}: RATE must be positive bp (int) or a Fraction")
        elif not isinstance(self.value, str) or len(self.value.strip()) < 3:
            raise ValueError(f"{self.label}: TEXT must be a string of at least 3 characters")
        if self.kind is ValueKind.TERMS and not self.aliases:
            raise ValueError(f"{self.label}: TERMS needs the owner's aliases")

    # constructors -------------------------------------------------------------------------

    @classmethod
    def money(cls, label: str, fen: int, *, owner: str | None = None, category: Category = Category.OTHER,
              owner_visible: bool = True) -> PrivateValue:
        return cls(label, ValueKind.MONEY, fen, owner, category, owner_visible)

    @classmethod
    def rate_bp(cls, label: str, bp: int, *, owner: str | None = None, category: Category = Category.OTHER,
                owner_visible: bool = True) -> PrivateValue:
        return cls(label, ValueKind.RATE, bp, owner, category, owner_visible)

    @classmethod
    def rate(cls, label: str, rate: Fraction, *, owner: str | None = None,
             category: Category = Category.OTHER, owner_visible: bool = True) -> PrivateValue:
        return cls(label, ValueKind.RATE, Fraction(rate), owner, category, owner_visible)

    @classmethod
    def ratio_bp(cls, label: str, bp: int, *, owner: str | None = None, category: Category = Category.OTHER,
                 owner_visible: bool = True) -> PrivateValue:
        return cls(label, ValueKind.RATIO, bp, owner, category, owner_visible)

    @classmethod
    def terms(cls, label: str, days: int, *, owner: str, aliases: tuple[str, ...],
              category: Category = Category.COUNTERPARTY_TERMS, owner_visible: bool = True) -> PrivateValue:
        return cls(label, ValueKind.TERMS, days, owner, category, owner_visible, tuple(aliases))

    @classmethod
    def text(cls, label: str, text: str, *, owner: str | None = None, aliases: tuple[str, ...] = (),
             category: Category = Category.OTHER, owner_visible: bool = True) -> PrivateValue:
        return cls(label, ValueKind.TEXT, text, owner, category, owner_visible, tuple(aliases))

    def entitled(self, recipient_id: str) -> bool:
        """May `recipient_id` see this value? Canaries are never entitled."""
        if self.category is Category.CANARY:
            return False
        if recipient_id == OWNER_ID:
            return self.owner_visible or self.owner == OWNER_ID
        return self.owner is not None and self.owner == recipient_id


@dataclass(frozen=True, slots=True)
class AllowedValue:
    """A value one outbound message is entitled to state (e.g. the counter's own rate and face)."""

    kind: ValueKind
    value: int | Fraction | str

    @classmethod
    def money(cls, fen: int) -> AllowedValue:
        return cls(ValueKind.MONEY, fen)

    @classmethod
    def rate_bp(cls, bp: int) -> AllowedValue:
        return cls(ValueKind.RATE, bp)

    @classmethod
    def rate(cls, rate: Fraction) -> AllowedValue:
        return cls(ValueKind.RATE, Fraction(rate))

    @classmethod
    def ratio_bp(cls, bp: int) -> AllowedValue:
        return cls(ValueKind.RATIO, bp)

    @classmethod
    def days(cls, days: int) -> AllowedValue:
        return cls(ValueKind.TERMS, days)

    @classmethod
    def text(cls, text: str) -> AllowedValue:
        return cls(ValueKind.TEXT, text)


# ---------------------------------------------------------------- canonical keys


def _yuan(fen: int) -> Decimal:
    return Decimal(fen) / FEN_PER_YUAN


def money_key(fen: int) -> str:
    return canon(_yuan(fen))


def money_bare_ok(fen: int) -> bool:
    """Small amounts (< ¥1,000) and year-like integers match only next to a currency marker."""
    y = _yuan(fen)
    if y < 1000:
        return False
    return not (y == y.to_integral_value() and 1900 <= y <= 2100)


def _terminating(x: Fraction, max_places: int) -> Decimal | None:
    scaled = x * 10**max_places
    if scaled.denominator != 1:
        return None
    return Decimal(scaled.numerator).scaleb(-max_places)


def rate_keys(value: int | Fraction) -> tuple[set[str], set[str]]:
    """(percent keys like '6.4%', fraction keys like '0.064')."""
    r = _as_rate(value)
    exact = _terminating(r * 100, 4)
    if exact is not None:
        pct = {canon(exact) + "%"}
        frac = canon(_terminating(r, 6) or Decimal(0))
        return pct, ({frac} if "." in frac and len(frac.split(".")[1]) >= 2 else set())
    pct = {canon(Decimal(round_half_up(r * 100 * 10**p)).scaleb(-p)) + "%" for p in (1, 2)}
    return pct, set()


def ratio_key(bp: int) -> str:
    return canon(Decimal(bp).scaleb(-4)) + "x"


def text_key(s: str) -> str:
    """Match key for a name or token (light folding; numbers untouched)."""
    return fold(s)


def terms_alias_key(s: str) -> str:
    """Match key for an alias inside a number-normalised sentence."""
    return " ".join(normalise(s).split())


def canary_squash(s: str) -> str:
    return squash(fold(s))


# ---------------------------------------------------------------- renderings (surface forms)

_FULLWIDTH = str.maketrans({**{chr(c): chr(c + 0xFEE0) for c in range(0x21, 0x7F)}, "¥": "￥"})
_CN = "零一二三四五六七八九"


def fullwidth(s: str) -> str:
    return s.translate(_FULLWIDTH)


def _cn_four(x: int) -> str:
    s, zero = "", False
    for unit_val, unit in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
        d = x // unit_val % 10
        if d:
            if zero:
                s += "零"
                zero = False
            s += _CN[d] + unit
        elif s:
            zero = True
    return s


def to_chinese(n: int) -> str:
    """Integer to Chinese numerals: 300000 -> '三十万', 105 -> '一百零五'."""
    if n == 0:
        return "零"
    yi, rem = divmod(n, 10**8)
    wan, low = divmod(rem, 10**4)
    s = ""
    if yi:
        s += to_chinese(yi) + "亿"
    if wan:
        if yi and wan < 1000:
            s += "零"
        s += _cn_four(wan) + "万"
    if low:
        if (yi or wan) and low < 1000:
            s += "零"
        s += _cn_four(low)
    return s[1:] if s.startswith("一十") else s


def chinese_decimal(d: Decimal) -> str:
    whole, _, frac = canon(d).partition(".")
    out = to_chinese(int(whole))
    return out + ("点" + "".join(_CN[int(c)] for c in frac) if frac else "")


def money_renderings(fen: int) -> list[str]:
    y = _yuan(fen)
    c = canon(y)
    whole = int(y)
    integral = y == whole
    grp = f"{whole:,}" + ("" if integral else f".{fen % FEN_PER_YUAN:02d}")
    marked = [fmt_yuan(fen), "¥" + grp, "¥" + c, f"RMB {grp}", f"CNY {grp}", f"RMB{c}", f"{grp}元", f"{c}元",
              f"人民币{grp}元", f"{grp} yuan", fullwidth(fmt_yuan(fen)), f"￥{fullwidth(c)}", f"{fullwidth(grp)}元"]
    bare = [grp, c, grp.replace(",", "\u2009"), grp.replace(",", "\u202f"), fullwidth(grp)]
    if integral:
        bare.append(f"{whole}.00")
        if whole >= 10_000 and whole % 100 == 0:
            w = canon(y / 10_000)
            marked += [f"{w}万", f"{w}万元", f"¥{w}万", f"{fullwidth(w)}万元"]
        if whole >= 1_000 and whole % 100 == 0:
            k = canon(y / 1_000)
            marked += [f"{k}k", f"¥{k}k", f"{k}K", f"RMB {k}k", f"{k} thousand"]
        if whole >= 1_000_000 and whole % 10_000 == 0:
            m = canon(y / 1_000_000)
            marked += [f"{m} million", f"¥{m}m", f"RMB {m}mn"]
        if whole < 10**12:
            marked += [f"{to_chinese(whole)}元", f"人民币{to_chinese(whole)}元"]
    return marked + (bare if money_bare_ok(fen) else [])


def rate_renderings(value: int | Fraction) -> list[str]:
    r = _as_rate(value)
    pct_keys, frac_keys = rate_keys(value)
    out: list[str] = []
    for key in sorted(pct_keys):
        p = key[:-1]
        d = Decimal(p)
        out += [key, f"{p} %", f"{p} percent", fullwidth(key), f"百分之{chinese_decimal(d)}"]
        if len(p.partition(".")[2]) < 2:
            out.append(f"{d:.2f}%")
    bp = r * BP_DENOM
    if bp.denominator == 1:
        out += [f"{bp.numerator}bp", f"{bp.numerator} bps", f"{bp.numerator} basis points"]
    out += sorted(frac_keys)
    return out


def ratio_renderings(bp: int) -> list[str]:
    c = ratio_key(bp)[:-1]
    d = Decimal(c)
    return [f"{c}x", f"{c}×", f"{c} times", f"{c}倍", f"{d:.2f}x", f"{c}X", f"{c} x", fullwidth(f"{c}x")]


def terms_renderings(days: int) -> list[str]:
    return [f"{days} days", f"{days}-day", f"{days}天", f"net {days}", f"账期{days}天", f"{days} calendar days"]


def text_renderings(s: str) -> list[str]:
    return [s, s.upper(), s.lower(), fullwidth(s)]


def renderings(pv: PrivateValue) -> list[str]:
    """Every common surface form of a protected value (TERMS forms need an alias nearby to match)."""
    if pv.kind is ValueKind.MONEY:
        return money_renderings(int(pv.value))  # type: ignore[arg-type]
    if pv.kind is ValueKind.RATE:
        return rate_renderings(pv.value)  # type: ignore[arg-type]
    if pv.kind is ValueKind.RATIO:
        return ratio_renderings(int(pv.value))  # type: ignore[arg-type]
    if pv.kind is ValueKind.TERMS:
        return terms_renderings(int(pv.value))  # type: ignore[arg-type]
    forms = text_renderings(str(pv.value))
    for a in pv.aliases:
        forms += text_renderings(a)
    return forms
