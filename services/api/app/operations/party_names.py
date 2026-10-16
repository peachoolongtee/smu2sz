"""Company names compared as a company is: CAPEX-4, the vendor of a purchase is never the business itself.

`same_company_key` makes two spellings of one name equal: NFKC (full-width forms), casefolded, punctuation (Latin and
CJK) and whitespace gone, and the legal-form suffix (Co., Ltd, Limited, Company, 有限公司, 公司 ...) dropped, so the
suffix spelling is not a way round the check. `own_business_keys` is every name the books give the business itself.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# The demo scenarios' business (the golden fixtures carry no org name field; its contracts and the egress tests name it).
DEMO_BUSINESS_NAME = "Lingnan Homeware Manufacturing Co., Ltd."

_LATIN_SUFFIX_WORDS = frozenset({"co", "ltd", "limited", "company", "corp", "corporation", "inc", "incorporated", "llc",
                                 "plc", "pte", "pvt", "gmbh"})
_CJK_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "股份公司", "公司")


def _is_mark(ch: str) -> bool:
    return unicodedata.category(ch)[0] in ("P", "S", "Z", "C", "M")


def same_company_key(name: object) -> str:
    text = unicodedata.normalize("NFKC", str(name or "")).casefold()
    words = [w for w in re.split(r"[^\w]+", text, flags=re.UNICODE) if w]
    while len(words) > 1 and words[-1] in _LATIN_SUFFIX_WORDS:
        words.pop()
    key = "".join(ch for ch in "".join(words) if not _is_mark(ch) and ch != "_")
    changed = True
    while changed:
        changed = False
        for suffix in _CJK_SUFFIXES:
            if key.endswith(suffix) and len(key) > len(suffix):
                key, changed = key[: -len(suffix)], True
                break
    return key


def own_business_keys(*, contract_buyer_names: Iterable[object], opened_names: Iterable[object],
                      confirmed_records: Iterable[object], scenario: str | None) -> set[str]:
    """The business's own names, as keys: the contract's buyer, the name the owner registered at OPEN_BOOKS, the own
    side of every other owner-confirmed contract (supplier of a buyer contract, buyer of a capex contract), and the
    demo business when the books are a demo scenario's."""
    names: list[object] = [*contract_buyer_names, *opened_names]
    for rec in confirmed_records:
        contract = getattr(rec, "contract", None)
        if contract is None:
            continue
        own = "PARTY_BUYER" if getattr(rec, "kind", None) == "CAPEX_CONTRACT" else "PARTY_SUPPLIER"
        names.extend(t.text for t in contract.terms if t.field.value == own and t.text)
    if scenario not in (None, "blank"):
        names.append(DEMO_BUSINESS_NAME)
    return {k for k in (same_company_key(n) for n in names) if k}
