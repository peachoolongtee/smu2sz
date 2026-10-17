"""Who the document is with (the owner's rule of 17 Oct, tightened by REG-2): the counterparty the owner chose against the
companies the reading found named in the document, each in the role its kind needs.

The owner says who a document is with; the reading finds the parties it names (a contract's PARTY_BUYER and PARTY_SUPPLIER
terms, a lender agreement's lender name). The chosen counterparty must be the party in its own role: the buyer of a buyer
contract, the vendor (the seller) of a capex contract, the lender of a lender agreement. A named party in that role that is
not the chosen counterparty gives a blocking PARTY_NOT_NAMED flag. When the reading found no party in that role (no parties
at all, the other party only, or a lender agreement whose lender was not found) the record carries a blocking
PARTY_UNCHECKED flag: a document whose parties could not be checked is not confirmed silently. Neither can be confirmed
(`ContractRecord.blocked`; the executor refuses a blocked record). Deterministic: no model call, no fuzzy score.

Matching is by company, not by words: a party is the chosen counterparty when `same_company_key` of the two names is equal
(full-width to half-width, case, punctuation and whitespace gone, the legal-form suffix Co., Ltd., Limited, 有限公司 dropped).
A first word ("Foshan"), a part of a name, or a longer name that contains it ("... Hong Kong Shell Ltd.") is another
company. The names a counterparty answers to are its registry name and any short name the owner gave it when adding it; the
owner's own short name may sit whole inside a longer party name, because the owner registered it for that.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence

from app.domain.models import (
    CONTRACT_READING_KINDS,
    ContractField,
    ContractRecord,
    Counterparty,
    DocumentFlag,
    DocumentKind,
    SourceSpan,
)
from app.operations.party_names import same_company_key

PARTY_NOT_NAMED = "PARTY_NOT_NAMED"  # blocking: the party in the document's role is not the chosen counterparty
PARTY_UNCHECKED = "PARTY_UNCHECKED"  # blocking: the reading found no party in that role, so the parties were not checked
PARTY_FLAG_KINDS = frozenset({PARTY_NOT_NAMED, PARTY_UNCHECKED})

_PARTY_FIELDS = (ContractField.PARTY_BUYER, ContractField.PARTY_SUPPLIER)
_PUNCT = re.compile(r"[\s,.;:()\[\]'\"“”‘’`·、，。；：（）【】「」]+")

# The role of the chosen counterparty in each kind of document: the party the reading must find, and must find to be it.
_KIND_ROLE = {DocumentKind.BUYER_CONTRACT: "BUYER", DocumentKind.CAPEX_CONTRACT: "SUPPLIER",
              DocumentKind.LENDER_AGREEMENT: "LENDER"}


def normalise(name: str) -> str:
    """A company name for comparison: NFKC (full-width letters, digits and brackets become half-width), case folded,
    punctuation and runs of whitespace as one space."""
    return _PUNCT.sub(" ", unicodedata.normalize("NFKC", name).casefold()).strip()


def names_match(party: str, chosen: str) -> bool:
    """One party name against one name of the chosen counterparty: the same company, by the same-company key used for the
    business's own names (operations.party_names). Never a first word, a part of the name or a longer name containing it."""
    p, c = same_company_key(party), same_company_key(chosen)
    return bool(p) and p == c


def short_name(name: str) -> str:
    """The registry name's short form, the one the pages use ("Foshan Home Retail Co." -> "Foshan"). The pages' own
    rule, imported here so that importing the contracts layer does not import the strategy package. It names a company
    on the pages only; the party check does not accept it (REG-2), and a new customer may not take it (`taken_names`)."""
    from app.strategy.words import buyer_short

    return buyer_short(name)


def registry_names(party: Counterparty, extra: Sequence[str] = ()) -> list[str]:
    """The names a counterparty answers to in the party check: its registry name, then any short name the owner gave it when
    adding it (`extra`, from the ADD_CUSTOMER entry; `app.api.customers.added_short_names`). Not the pages' first-word short
    form: that is not the owner's registration."""
    out = [party.name]
    for n in extra:
        if n and n.strip() and same_company_key(n) not in {same_company_key(x) for x in out}:
            out.append(n)
    return out


def taken_names(party: Counterparty, extra: Sequence[str] = ()) -> set[str]:
    """The normalised names a new customer may not take: a counterparty's name, its owner-given short names and the first-word
    short form the pages use for it."""
    return {normalise(n) for n in [*registry_names(party, extra), short_name(party.name)] if normalise(n)}


_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_GENERIC = re.compile(r"(?<![a-z0-9])(?:co|company|ltd|limited|inc|corp|corporation|llc|plc|group|the|and|of)(?![a-z0-9])"
                      r"|股份有限公司|有限责任公司|有限公司|公司|集团")


def _registered_inside(short: str, party: str) -> bool:
    """A short name the owner registered, whole words inside a party name ("澄昱智能" inside 深圳市澄昱智能制造股份有限公司). Only
    the owner's own registration counts this way, and only a name that identifies a company once its legal-form words are set
    aside (4 characters, or 2 Chinese); the pages' first-word short form never does."""
    s, p = normalise(short), normalise(party)
    core = _GENERIC.sub(" ", s)
    if not s or not (len(_CJK.findall(core)) >= 2 or len(core.replace(" ", "")) >= 4):
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])", p) is not None


def party_matches(found: Iterable[str], names: Sequence[str]) -> bool:
    """Whether any name the document gives is the chosen counterparty: the same company as its registry name (`names[0]`),
    or the same company as, or a party name containing, a short name the owner registered for it (`names[1:]`)."""
    full, *registered = names
    return any(names_match(f, full) or any(names_match(f, r) or _registered_inside(r, f) for r in registered)
               for f in found if f.strip())


_FIELD_ROLE = {ContractField.PARTY_BUYER: "BUYER", ContractField.PARTY_SUPPLIER: "SUPPLIER"}


def _found_roles(record: ContractRecord) -> list[tuple[str, SourceSpan, str]]:
    """The party names the reading found, each with the span it was read from and the role the document gives it (BUYER,
    SUPPLIER or LENDER), in document order, distinct."""
    out: list[tuple[str, SourceSpan, str]] = []
    if record.contract is not None:
        for term in record.contract.terms:
            name = (term.text or term.value_text or "").strip()
            if term.field in _PARTY_FIELDS and name:
                out.append((name, term.span, _FIELD_ROLE[term.field]))
    elif record.term_sheet is not None:
        name = record.term_sheet.lender_name.strip()
        # The term-sheet reader falls back to the sender (the counterparty id) when it found no lender name in the text.
        at = record.document.text.find(name) if name and name not in (record.document.sender_id, record.counterparty_id) else -1
        if at >= 0:
            out.append((name, SourceSpan(doc_id=record.document.doc_id, start=at, end=at + len(name), text=name), "LENDER"))
    seen: set[tuple[str, str]] = set()
    distinct: list[tuple[str, SourceSpan, str]] = []
    for name, span, role in sorted(out, key=lambda x: x[1].start):
        if (same_company_key(name), role) not in seen:
            seen.add((same_company_key(name), role))
            distinct.append((name, span, role))
    return distinct


def _found(record: ContractRecord) -> list[tuple[str, SourceSpan]]:
    """The party names the reading found, each with the span it was read from, in document order, distinct."""
    return [(n, s) for n, s, _ in _found_roles(record)]


def found_names(record: ContractRecord) -> list[str]:
    return [n for n, _ in _found(record)]


def on_books(name: str, role: str, registry: Sequence[Counterparty],
             extra: Mapping[str, Sequence[str]] | None = None) -> str | None:
    """The registry counterparty a party name the document gives is, by the same matcher as the party check: one of the
    document's role first, then any; None when no registry name matches."""
    matched = [c for c in registry if party_matches([name], registry_names(c, (extra or {}).get(c.id, ())))]
    same = [c for c in matched if c.role == role]
    return (same or matched)[0].id if matched else None


def named_parties(record: ContractRecord, registry: Sequence[Counterparty],
                  extra: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, str | None]]:
    """The parties the reading found (a contract's PARTY_BUYER and PARTY_SUPPLIER terms, a lender agreement's lender name
    when it is not the reader's fallback), each with the registry counterparty it is, or None when it is not on the books."""
    return [{"name": n, "role": role, "on_books_id": on_books(n, role, registry, extra)}
            for n, _, role in _found_roles(record)]


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


# A party the document defines: it opens the party ("between <name>", "and <name>", "(1) <name>", "甲方：<name>"), and its name is
# followed, after any legal-form words, by the bracket that names its role in the document ((the "Bank"), （以下简称“乙方”）).
# A name the document only mentions, a part of a longer name, or a party defined as the borrower's side is not the lender.
_OPENS_PARTY = r"(?:^|\n|[:：;；)）\]]|(?<![a-z0-9])(?:between|and|by|with|among)(?![a-z0-9])|[&与和及])\s*"
_LEGAL_FORM = r"(?:[\s,.]*(?:co|ltd|limited|company|corp|corporation|inc|llc|plc))*"
_DEFINED_AS = r"[\s,.]*[(（]\s*(?:the\s+|以下简称\s*)?[\"“「'‘]\s*([^\"”」'’]{1,40})"
_BORROWER_SIDE = frozenset({"borrower", "client", "customer", "buyer", "company", "business", "debtor", "lessee", "借款人", "借款方",
                            "客户", "买方", "承租人"})


def defines_party(text: str, names: Sequence[str]) -> bool:
    """Whether the document text defines one of `names` as a party that is not the borrower's side ("between <name> (the
    "Bank")"). A lender agreement whose reading found no lender is checked this way: the chosen lender must be a party the
    document itself introduces, whole, in a role other than the borrower's."""
    flat = unicodedata.normalize("NFKC", text).casefold()
    for name in names:
        n = unicodedata.normalize("NFKC", name).casefold().strip()
        if not n or not _long_enough(n):
            continue
        body = r"\s+".join(re.escape(w) for w in n.split())
        for m in re.finditer(_OPENS_PARTY + body + _LEGAL_FORM + _DEFINED_AS, flat):
            if m.group(1).strip().removeprefix("the ").strip() not in _BORROWER_SIDE:
                return True
    return False


def _long_enough(n: str) -> bool:
    """A name worth looking for: not only legal-form words ("Co., Ltd.")."""
    core = re.sub(r"(?<![a-z0-9])(?:co|company|ltd|limited|inc|corp|corporation|llc|plc|the|and|of)(?![a-z0-9])", " ", n)
    return len(re.findall(r"[\w]", core)) >= 2


def _no_party_flag(record: ContractRecord, names: Sequence[str]) -> DocumentFlag:
    return DocumentFlag(kind=PARTY_UNCHECKED, blocking=True, note=unchecked_note(names[0], "en"),
                        span=SourceSpan(doc_id=record.document.doc_id, start=0, end=0, text=""))


def party_flags(record: ContractRecord, names: Sequence[str]) -> list[DocumentFlag]:
    """The party check's flags for a record read for the counterparty whose registry names are `names` (empty: no
    registry entry to compare with, nothing is checked). Only the party in the document kind's own role counts: the buyer
    of a buyer contract, the vendor of a capex contract, the lender of a lender agreement. Both flags block."""
    if not names:
        return []
    role = _KIND_ROLE[record.kind]
    found = _found_roles(record)
    in_role = [n for n, _, r in found if r == role]
    if in_role:
        if party_matches(in_role, names):
            return []
        return [DocumentFlag(kind=PARTY_NOT_NAMED, blocking=True,
                             note=not_named_note(record.kind, [n for n, _, _ in found], names[0], "en"), span=found[0][1])]
    if record.kind not in CONTRACT_READING_KINDS and defines_party(record.document.text, names):
        return []  # the reading found no lender, but the agreement itself introduces the chosen lender as a party
    return [_no_party_flag(record, names)]


def with_party_check(record: ContractRecord, party: Counterparty | None, extra: Sequence[str] = ()) -> ContractRecord:
    """The record with the party check's flags added after the reading's own. `party` is the registry entry the owner
    chose (`extra`: the short names the owner gave it); a vendor not yet on the registry has none, and is not checked."""
    flags = party_flags(record, registry_names(party, extra)) if party is not None else []
    return record.model_copy(update={"flags": [*record.flags, *flags]}) if flags else record


def without_party_check(record: ContractRecord) -> ContractRecord:
    """The record with the party check's flags taken off (the reading's own flags kept), to check it again for another
    counterparty."""
    return record.model_copy(update={"flags": [f for f in record.flags if f.kind not in PARTY_FLAG_KINDS]})


def party_note(flag: DocumentFlag, record: ContractRecord, chosen: str | None, lang: str) -> str:
    """A party flag's note in the page's language, rebuilt from the record and the chosen counterparty's registry name so
    the English and the Chinese say the same; the note as stored when the registry no longer holds the name."""
    if chosen is None:
        return flag.note
    if flag.kind == PARTY_UNCHECKED:
        return unchecked_note(chosen, lang)
    return not_named_note(record.kind, found_names(record), chosen, lang)


__all__ = ["PARTY_FLAG_KINDS", "PARTY_NOT_NAMED", "PARTY_UNCHECKED", "found_names", "named_parties", "names_match",
           "normalise", "on_books", "party_flags", "party_matches", "party_note", "registry_names", "taken_names",
           "with_party_check", "without_party_check"]
