"""Company names compared as a person reads them, for the registry's write path (`POST /customers`, REG-3).

A name the owner types is data, and a second customer that reads as the first (or as a lender, or as the business itself) is
a way to make one party stand in for another: a contract filed under the lookalike passes the party check and is
read as the other company's. This module gives the comparison a name goes through:

- `skeleton`: a small UTS #39 style confusables skeleton. Format characters are dropped, full-width and compatibility forms are
  made plain (NFKC), the Cyrillic and Greek letters that render as Latin ones are their Latin letters (the compiler lexicon's
  `HOMOGLYPHS`, reused), accents and other Mn/Me marks are dropped, and the Latin shapes that read alike are one letter
  (i, l, 1 and | are l; 0 is o; rn is m; vv is w).
- `name_key`: the skeleton passed through the engine's `same_company_key` (punctuation, spaces and the legal-form suffix gone),
  so "Foshan Home Retail Company Limited" and "Ｆоshan Home Retail Co." are one key.
- `keys_clash`: two keys are equal, or one contains the other and is long enough to identify a company.
- `has_letter_or_digit` and `looks_like_id`: a name must name something, and must not read as an identifier (BUYER-7).

Pure functions, no I/O. Imports the compiler's folding table and the operations package's name key; modifies neither.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from app.compiler.folding import fold
from app.operations.party_names import same_company_key

# Lookalikes the compiler's table does not hold (dotless i and j, the Latin letter iota, the Cyrillic and Greek ones it misses).
_EXTRA: dict[str, str] = {"ı": "i", "ȷ": "j", "ɩ": "i", "ӏ": "l", "ѵ": "v", "ѡ": "w", "ԍ": "g", "ᴏ": "o", "ᴄ": "c",
                          "ᴠ": "v", "ᴡ": "w", "ᴢ": "z", "ꜱ": "s", "Ɩ": "l", "ǀ": "l", "Ο": "O", "Ѡ": "W", "Ꮯ": "C"}
_SHAPES = str.maketrans({"i": "l", "1": "l", "|": "l", "0": "o"})  # applied to the case-folded text: I, l and 1 are one shape
_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_ID_PREFIXES = frozenset({"BUYER", "SUPPLIER", "VENDOR", "LENDER", "BANK", "OWNER", "AGENT", "DOC", "CAPEX", "CUSTOMER", "OWN",
                          "PLATFORM", "LESSOR", "FAC", "FACILITY", "INV", "REC", "OP", "APR", "ID", "NO"})
_MIN_CONTAINED = 4  # latin characters; 2 for Chinese: enough of a name to identify a company (the party check's rule)


def _bare(text: str) -> str:
    """The text without its Mn/Me marks (accents, combining and enclosing marks), recomposed."""
    kept = "".join(c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) not in ("Mn", "Me"))
    return unicodedata.normalize("NFKC", kept)


def _plain(text: object) -> str:
    """The text with its lookalike letters, width forms, format characters, marks and case made plain, letter shapes kept."""
    folded = fold(str(text or "")).text  # no format characters, NFKC, Cyrillic and Greek lookalikes as Latin
    folded = "".join(_EXTRA.get(c, c) for c in folded)
    return _bare(_bare(folded).casefold())  # case folding can add a mark (İ): drop it too


def _shapes(text: str) -> str:
    return text.translate(_SHAPES).replace("rn", "m").replace("vv", "w")


def skeleton(text: object) -> str:
    """The name with its lookalikes made one: what a reader cannot tell apart is equal."""
    return _shapes(_plain(text))


def name_key(text: object) -> str:
    """The company a name stands for: the engine's same-company key (punctuation, spaces and the legal-form suffix gone) of
    its plain form, then the letter shapes made one. The suffix goes before the shapes, while "limited" still reads so."""
    return _shapes(same_company_key(_plain(text)))


def _identifies(key: str) -> bool:
    return len(_CJK.findall(key)) >= 2 or len(key) >= _MIN_CONTAINED


def keys_clash(a: str, b: str) -> bool:
    """Whether two company keys read as one company: equal, or one holds the other and the held one is long enough to
    identify a company (a two-letter key does not make every name that contains it a lookalike)."""
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return _identifies(short) and short in long


def has_letter_or_digit(text: str) -> bool:
    """A letter or digit once the Mn/Me marks (accents, combining marks, enclosing marks) are removed."""
    return any(unicodedata.category(c)[0] in ("L", "N") for c in text if unicodedata.category(c) not in ("Mn", "Me"))


def looks_like_id(text: str, known_ids: Iterable[str] = ()) -> bool:
    """Whether a name reads as an identifier ("BUYER-7", "buyer 7", "ＢＵＹＥＲ－７", BANK_2): a known prefix and a number, or a
    short word, a hyphen or underscore and a number, or any id the books and the channel keys already hold."""
    plain = re.sub(r"\s+", " ", fold(text).text.strip()).upper()
    prefixes = _ID_PREFIXES | {m.group(0) for i in known_ids if (m := re.match(r"[A-Za-z]+", i))}
    alternatives = "|".join(sorted(map(re.escape, prefixes), key=len, reverse=True))
    if re.fullmatch(rf"(?:{alternatives})[-_ ]*\d+", plain):
        return True
    if re.fullmatch(r"[A-Z]{2,12}[-_]\d+", plain):
        return True
    return plain in {i.upper() for i in known_ids}


__all__ = ["has_letter_or_digit", "keys_clash", "looks_like_id", "name_key", "skeleton"]
