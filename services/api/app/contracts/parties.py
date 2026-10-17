"""Who the document is with (the owner's rule of 17 Oct): the counterparty the owner chose against the companies the
reading found named in the document.

The owner says who a document is with; the reading finds the parties it names (a contract's PARTY_BUYER and PARTY_SUPPLIER
terms, a lender agreement's lender name). When neither named party is the chosen counterparty, the record carries a
blocking PARTY_NOT_NAMED flag and cannot be confirmed; when a contract reading found no party names at all, a non-blocking
PARTY_UNCHECKED warning says the parties could not be checked. A lender agreement whose reading names no lender is not
checked. Deterministic: no model call, no fuzzy score.

Matching: both sides are normalised (full-width to half-width, case, punctuation and whitespace); a name matches when the two
are equal or one contains the other on word boundaries, and the registry name's short form ("Foshan") counts when it sits
inside a party name. A contained name must be long enough to identify a company once its legal-form words (Co., Ltd.,
有限公司) are set aside: 4 characters, or 2 Chinese characters.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence

from app.domain.models import (
    CONTRACT_READING_KINDS,
    ContractField,
    ContractRecord,
    Counterparty,
    DocumentFlag,
    DocumentKind,
    SourceSpan,
)

PARTY_NOT_NAMED = "PARTY_NOT_NAMED"  # blocking: no party the document names is the chosen counterparty
PARTY_UNCHECKED = "PARTY_UNCHECKED"  # warning: the reading found no party names, so the parties were not checked
PARTY_FLAG_KINDS = frozenset({PARTY_NOT_NAMED, PARTY_UNCHECKED})

_PARTY_FIELDS = (ContractField.PARTY_BUYER, ContractField.PARTY_SUPPLIER)
_PUNCT = re.compile(r"[\s,.;:()\[\]'\"“”‘’`·、，。；：（）【】「」]+")
_CJK = re.compile(r"[㐀-鿿豈-﫿]")


def normalise(name: str) -> str:
    """A company name for comparison: NFKC (full-width letters, digits and brackets become half-width), case folded,
    punctuation and runs of whitespace as one space."""
    return _PUNCT.sub(" ", unicodedata.normalize("NFKC", name).casefold()).strip()


# Words every company name may carry: a contained name made of them alone ("Co., Ltd.") names no one.
_GENERIC = re.compile(r"(?<![a-z0-9])(?:co|company|ltd|limited|inc|corp|corporation|llc|plc|group|the|and|of)(?![a-z0-9])"
                      r"|股份有限公司|有限责任公司|有限公司|公司|集团")


def _long_enough(n: str) -> bool:
    """Enough of a name to identify a company once its legal-form words are set aside: 4 characters, or 2 Chinese."""
    core = _GENERIC.sub(" ", n)
    return len(_CJK.findall(core)) >= 2 or len(core.replace(" ", "")) >= 4


def _inside(short: str, long: str) -> bool:
    """`short` sits in `long` as whole words (a Latin name does not match half a word; Chinese has no word gaps)."""
    if not short or not _long_enough(short):
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(short)}(?![a-z0-9])", long) is not None


def names_match(party: str, chosen: str) -> bool:
    """One party name against one name of the chosen counterparty: equal, or one inside the other."""
    p, c = normalise(party), normalise(chosen)
    if not p or not c:
        return False
    return p == c or _inside(c, p) or _inside(p, c)


def short_name(name: str) -> str:
    """The registry name's short form, the one the pages use ("Foshan Home Retail Co." -> "Foshan"). The pages' own
    rule, imported here so that importing the contracts layer does not import the strategy package."""
    from app.strategy.words import buyer_short

    return buyer_short(name)


def registry_names(party: Counterparty) -> list[str]:
    """The names the registry holds for a counterparty: its name and its short form."""
    short = short_name(party.name)
    return [party.name, *([short] if short and short != party.name else [])]


def party_matches(found: Iterable[str], names: Sequence[str]) -> bool:
    """Whether any name the document gives is one of the chosen counterparty's `names` (its registry name first, then the
    short or Chinese forms). A short form counts only inside a party name, never the other way round."""
    found = [f for f in found if f.strip()]
    full, *others = names
    return any(names_match(f, full) or any(_inside(normalise(o), normalise(f)) for o in others) for f in found)


def _found(record: ContractRecord) -> list[tuple[str, SourceSpan]]:
    """The party names the reading found, each with the span it was read from, in document order, distinct."""
    out: list[tuple[str, SourceSpan]] = []
    if record.contract is not None:
        for term in record.contract.terms:
            name = (term.text or term.value_text or "").strip()
            if term.field in _PARTY_FIELDS and name:
                out.append((name, term.span))
    elif record.term_sheet is not None:
        name = record.term_sheet.lender_name.strip()
        # The term-sheet reader falls back to the sender (the counterparty id) when it found no lender name in the text.
        at = record.document.text.find(name) if name and name not in (record.document.sender_id, record.counterparty_id) else -1
        if at >= 0:
            out.append((name, SourceSpan(doc_id=record.document.doc_id, start=at, end=at + len(name), text=name)))
    seen: set[str] = set()
    distinct: list[tuple[str, SourceSpan]] = []
    for name, span in sorted(out, key=lambda x: x[1].start):
        if normalise(name) not in seen:
            seen.add(normalise(name))
            distinct.append((name, span))
    return distinct


def found_names(record: ContractRecord) -> list[str]:
    return [n for n, _ in _found(record)]


def _joined(names: Sequence[str], lang: str) -> str:
    if lang == "zh":
        return "和".join(names) if len(names) <= 2 else "、".join(names[:-1]) + "和" + names[-1]
    return " and ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + " and " + names[-1]


def _doc_word(kind: DocumentKind, lang: str) -> str:
    if lang == "zh":
        return "这份协议" if kind == DocumentKind.LENDER_AGREEMENT else "这份合同"
    return "This agreement" if kind == DocumentKind.LENDER_AGREEMENT else "This contract"


def not_named_note(kind: DocumentKind, found: Sequence[str], chosen: str, lang: str) -> str:
    if lang == "zh":
        return f"{_doc_word(kind, lang)}列明的是{_joined(found, lang)}，而不是{chosen}。确认前请核实它的对方是谁。"
    end = "" if chosen.endswith(".") else "."
    return f"{_doc_word(kind, lang)} names {_joined(found, lang)}, not {chosen}{end} Check who it is with before confirming."


def unchecked_note(chosen: str, lang: str) -> str:
    if lang == "zh":
        return f"代理没有在文件中读到各方的名称，因此无法核实它是否与{chosen}签订。确认前请核实它的对方是谁。"
    end = "" if chosen.endswith(".") else "."
    return (f"The agent found no party names in this document, so it could not check that it is with {chosen}{end} "
            f"Check who it is with before confirming.")


def party_flags(record: ContractRecord, names: Sequence[str]) -> list[DocumentFlag]:
    """The party check's flags for a record read for the counterparty whose registry names are `names` (empty: no
    registry entry to compare with, nothing is checked)."""
    if not names:
        return []
    found = _found(record)
    if not found:
        if record.kind not in CONTRACT_READING_KINDS:
            return []  # a lender agreement whose reading names no lender is not checked
        return [DocumentFlag(kind=PARTY_UNCHECKED, blocking=False, note=unchecked_note(names[0], "en"),
                             span=SourceSpan(doc_id=record.document.doc_id, start=0, end=0, text=""))]
    if party_matches([n for n, _ in found], names):
        return []
    return [DocumentFlag(kind=PARTY_NOT_NAMED, blocking=True,
                         note=not_named_note(record.kind, [n for n, _ in found], names[0], "en"), span=found[0][1])]


def with_party_check(record: ContractRecord, party: Counterparty | None) -> ContractRecord:
    """The record with the party check's flags added after the reading's own. `party` is the registry entry the owner
    chose; a vendor not yet on the registry has none, and is not checked."""
    flags = party_flags(record, registry_names(party)) if party is not None else []
    return record.model_copy(update={"flags": [*record.flags, *flags]}) if flags else record


def party_note(flag: DocumentFlag, record: ContractRecord, chosen: str | None, lang: str) -> str:
    """A party flag's note in the page's language, rebuilt from the record and the chosen counterparty's registry name so
    the English and the Chinese say the same; the note as stored when the registry no longer holds the name."""
    if chosen is None:
        return flag.note
    if flag.kind == PARTY_UNCHECKED:
        return unchecked_note(chosen, lang)
    return not_named_note(record.kind, found_names(record), chosen, lang)


__all__ = ["PARTY_FLAG_KINDS", "PARTY_NOT_NAMED", "PARTY_UNCHECKED", "found_names", "names_match", "normalise",
           "party_flags", "party_matches", "party_note", "registry_names", "with_party_check"]
