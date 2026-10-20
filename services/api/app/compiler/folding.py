"""Evasion-resistant folding for the security lexicon, with an offset map back to the original text.

The lexicon matches on a folded copy of each document: format characters (zero-width, soft hyphen,
bidi controls) are removed, each character is NFKC-normalised (full-width Latin and digits become
ASCII) and common Cyrillic and Greek lookalikes become their Latin letters. Every folded character
remembers the original character it came from, so a match on the folded text maps back to an exact
substring of the ORIGINAL document: spans keep pointing at what the counterparty actually sent.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Cyrillic and Greek letters that render like Latin ones.
HOMOGLYPHS: dict[str, str] = {
    # Cyrillic lower
    "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c",
    "т": "t", "у": "y", "х": "x", "і": "i", "ї": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    "һ": "h", "ӏ": "l", "ɡ": "g",
    # Cyrillic upper
    "А": "A", "В": "B", "Е": "E", "Ё": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ї": "I", "Ј": "J", "Ѕ": "S", "Ԁ": "D", "Ԛ": "Q", "Ԝ": "W",
    "Һ": "H", "Ӏ": "I",
    # Greek
    "α": "a", "β": "b", "γ": "y", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
    "υ": "u", "χ": "x", "ω": "w", "ϲ": "c", "ϳ": "j",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "Ϲ": "C",
}


@dataclass(frozen=True)
class Folded:
    """`text` is the folded form of `original`; folded char i came from original[starts[i]:ends[i]]."""

    original: str
    text: str
    starts: tuple[int, ...]
    ends: tuple[int, ...]

    def span(self, s: int, e: int) -> tuple[int, int]:
        """Original (start, end) of the folded range [s, e)."""
        if e <= s:
            pos = self.starts[s] if s < len(self.starts) else len(self.original)
            return pos, pos
        return self.starts[s], self.ends[e - 1]

    def orig(self, s: int, e: int) -> str:
        a, b = self.span(s, e)
        return self.original[a:b]


def _strip(ch: str) -> bool:
    """Format characters: zero-width spaces and joiners, soft hyphen, word joiner, BOM, bidi controls."""
    return unicodedata.category(ch) == "Cf"


def fold(text: str) -> Folded:
    out: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for i, ch in enumerate(text):
        if _strip(ch):
            continue
        n = unicodedata.normalize("NFKC", ch) if not ch.isascii() else ch
        for c in n:
            if _strip(c):
                continue
            out.append(HOMOGLYPHS.get(c, c))
            starts.append(i)
            ends.append(i + 1)
    return Folded(text, "".join(out), tuple(starts), tuple(ends))


def has_format_characters(text: str) -> bool:
    """True when `text` holds a format character (zero-width, soft hyphen, word joiner, BOM, bidi control): the folded copy
    drops them silently, so a reader of the folded text cannot tell they were there (LIVE-1)."""
    return any(_strip(ch) for ch in text)


__all__ = ["HOMOGLYPHS", "Folded", "fold", "has_format_characters"]
