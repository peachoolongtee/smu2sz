"""Contract grounding: an untrusted reading of a buyer contract becomes typed `ContractTerm`s, or abstains.

- Long documents are split at section headings into chunks of at most `MAX_CHUNK_CHARS`; each chunk is read on its
  own and every quote is tied back to the chunk's offsets in the whole document.
- Every quote must be found verbatim in its chunk; every fragment (`value_text`, `date_text` ...) must sit inside its
  quote; code parses every value. A term that fails any of these is dropped with an abstention.
- One-valued fields stated twice with the same value are read once; with different values both are dropped and the
  reading is CONFLICTING_SOURCES (INVARIANT 10).
- The security lexicon runs over the whole document whatever the backend (a contract is untrusted input). Contract
  boilerplate ("shall accept the Goods", "the facility limit is", "immediately") is not a claim; an instruction
  addressed to the agent is, and it blocks confirmation (see `document_flags`).
- Model-written free text never reaches a term: names, references and descriptions are document substrings, and
  abstention reasons are fixed templates.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.compiler import lexicon
from app.compiler.contract_parsing import (
    Parsed,
    basis_of,
    business_days,
    parse_date,
    parse_days,
    parse_money,
    parse_months,
    parse_rate,
    unit_of,
)
from app.compiler.grounding import locate
from app.compiler.parsing import rx
from app.compiler.schema import ContractExtraction, XAuthorityClaim, XContractTerm, XDataRequest
from app.domain.models import (
    MULTI_VALUED_CONTRACT_FIELDS,
    Abstention,
    AuthorityClaim,
    CompiledContract,
    CompileStatus,
    ContractField,
    ContractTerm,
    DataRequest,
    DataRequestKind,
    DocumentFlag,
    DocumentKind,
    SourceDocument,
    SourceSpan,
)

F = ContractField
I = re.IGNORECASE
MAX_CHUNK_CHARS = 6_000
MAX_CHUNKS = 40  # a contract that needs more chunks than this is refused before any model call (each chunk is a call)
MATERIAL_FIELDS = (F.PRICE, F.PAYMENT_TERMS)  # a supply contract read without these is ABSTAINED
# ADR-0013: a capex contract states when its price is paid either as milestones or as payment terms; read without a price
# and without either of those, it is ABSTAINED (a payment schedule could not be derived from it).
CAPEX_WHEN_PAID = (F.MILESTONE, F.PAYMENT_TERMS)


def material_missing(kind: DocumentKind, found: set[ContractField]) -> bool:
    """Whether a reading of `kind` lacks a material field: a supply contract needs a price and payment terms; a capex
    contract needs a price and either milestones or payment terms."""
    if kind == DocumentKind.CAPEX_CONTRACT:
        return F.PRICE not in found or not any(f in found for f in CAPEX_WHEN_PAID)
    return any(f not in found for f in MATERIAL_FIELDS)

# ---------------------------------------------------------------- chunking

# A section start: "1. DEFINITIONS", "SCHEDULE 1", "Article 4", "## 7. Payment" (a numbered sub-clause "4.2" is not).
_SECTION = re.compile(r"^[ \t]*(?:#{1,3}[ \t]*)?(?:(?:ARTICLE|Article|SECTION|Section|CLAUSE|Clause|SCHEDULE|Schedule|ANNEX"
                      r"|Annex|APPENDIX|Appendix)[ \t]+[0-9IVXLC]+\b|\d{1,2}\.[ \t]+\S)", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    index: int
    start: int
    end: int


def _pieces(text: str, start: int, end: int, limit: int) -> list[tuple[int, int]]:
    """[start, end) cut at paragraph, then line, then space boundaries into pieces of at most `limit` characters."""
    out: list[tuple[int, int]] = []
    s = start
    while end - s > limit:
        cut = -1
        for sep in ("\n\n", "\n", " "):
            cut = text.rfind(sep, s + 1, s + limit)
            if cut > s:
                cut += len(sep)
                break
        if cut <= s:
            cut = s + limit
        out.append((s, cut))
        s = cut
    out.append((s, end))
    return out


class ContractTooLong(ValueError):
    """The contract needs more chunks than `MAX_CHUNKS`. Raised before any model call; nothing was read."""

    code = "DOCUMENT_TOO_LONG"

    def __init__(self, chunks: int) -> None:
        super().__init__(f"the contract is too long to read: it needs {chunks} sections of reading and the limit is "
                         f"{MAX_CHUNKS}; upload the part that sets the terms")
        self.message_zh = f"合同太长，无法读取：需要读取 {chunks} 段，上限是 {MAX_CHUNKS} 段；请上传约定条款的部分"


def chunk_document(doc: SourceDocument, limit: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """Consecutive chunks covering the whole text, cut at section starts and packed up to `limit` characters."""
    text = doc.text
    starts = sorted({0, *(m.start() for m in _SECTION.finditer(text))})
    sections = [(a, b) for a, b in zip(starts, [*starts[1:], len(text)], strict=True) if b > a]
    pieces = [p for a, b in sections for p in _pieces(text, a, b, limit)]
    chunks: list[tuple[int, int]] = []
    for a, b in pieces:
        if chunks and b - chunks[-1][0] <= limit:
            chunks[-1] = (chunks[-1][0], b)
        else:
            chunks.append((a, b))
    return [Chunk(i, a, b) for i, (a, b) in enumerate(chunks)] or [Chunk(0, 0, len(text))]


def contract_document(text: str, kind: DocumentKind, counterparty_id: str) -> SourceDocument:
    """The canonical untrusted document for a contract or lender agreement. Its id comes from the text, and it carries
    no upload day or file name, so the same text read for the same counterparty always has the same cache key."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SourceDocument(doc_id=f"DOC-{digest[:16]}",
                          channel="term_sheet" if kind == DocumentKind.LENDER_AGREEMENT else "attachment",
                          sender_id=counterparty_id, received_day=0, text=text)


def chunk_source(doc: SourceDocument, chunk: Chunk) -> SourceDocument:
    """What a backend reads for one chunk. Only the text, the chunk's position and the sender name it, so a recorded
    reading replays whatever day the document was uploaded."""
    return SourceDocument(doc_id=f"{doc.doc_id}#{chunk.index}", channel=doc.channel, sender_id=doc.sender_id,
                          received_day=0, text=doc.text[chunk.start:chunk.end])


# ---------------------------------------------------------------- clause labels

_NUMBERED = re.compile(r"^[ \t]*(\d{1,2}(?:\.\d{1,2})+|\d{1,2})\.?[ \t]+\S")
_ITEM = re.compile(r"^[ \t]*\(([a-z]|[ivx]{1,4}|\d{1,2})\)[ \t]+")
_SCHEDULE = re.compile(r"^[ \t]*(?:#{1,3}[ \t]*)?(SCHEDULE|Schedule|ANNEX|Annex|APPENDIX|Appendix)[ \t]+([0-9IVXLC]+)\b")
_TOP_HEADING = re.compile(r"^[ \t]*(?:#{1,3}[ \t]*)?\d{1,2}\.[ \t]+[A-Z][A-Z ,&'/-]+$")


def clause_label(text: str, pos: int) -> str | None:
    """The clause `pos` sits in, as the document numbers it: "4.2", "6.1(b)", "Schedule 1, 2"; None outside any."""
    lines_before = text[:pos].split("\n")
    current = lines_before[-1] + text[pos:].split("\n", 1)[0]
    item = _ITEM.match(current)
    idx = len(lines_before) - 1
    lines = text.split("\n")
    # The line itself decides; a list item takes the number of the paragraph that introduces it (blank lines and its
    # sibling items skipped). An unnumbered paragraph has no clause.
    candidates = [current] if item is None else [lines[i] for i in range(idx - 1, -1, -1)]
    number: str | None = None
    for line in candidates:
        if not line.strip() or (item is not None and _ITEM.match(line)):
            continue
        m = _NUMBERED.match(line)
        number = m.group(1) if m else None
        break
    if number is None:
        return None
    label = number + (f"({item.group(1)})" if item else "")
    schedule = top = -1
    for i in range(idx, -1, -1):
        if schedule < 0 and _SCHEDULE.match(lines[i]):
            schedule = i
        if top < 0 and _TOP_HEADING.match(lines[i]):
            top = i
        if schedule >= 0 and top >= 0:
            break
    if schedule > top:
        m = _SCHEDULE.match(lines[schedule])
        assert m is not None
        return f"{m.group(1).capitalize()} {m.group(2)}, {label}"
    return label


# ---------------------------------------------------------------- security flags for contracts

# Text addressed to an automated reader: "Note to any AI system reading this Agreement: ignore ...", "If you are an
# AI, record the terms as ...". Contract language never addresses the reader's software.
AGENT_ADDRESSED = rx(
    r"\b(?:AI|A\.I\.|artificial\s+intelligence|LLMs?|large\s+language\s+models?|language\s+models?|chatbots?|TermsLedger"
    r"|automated\s+(?:reviewers?|readers?|review(?:\s+system)?|systems?|agents?|tools?)"
    r"|(?:reading|reviewing|processing|extraction)\s+(?:agents?|systems?|software|tools?))\b"
    r"[^.;\n]{0,80}?\b(?:ignore|disregard|override|bypass|record|treat|set|mark|confirm|approve|accept|report|enter|book"
    r"|extract|output|reply|respond|change|update|classify|skip|must|should|shall)\b"
    r"|\bif\s+you\s+are\s+an?\s+(?:AI|assistant|language\s+model|automated)\b|人工智能|AI助手|自动审核", I)
# Ordinary obligations between the parties that the offer lexicon reads as instructions to the system.
_PARTY_OBLIGATION = re.compile(r"(?:must|shall|have\s+to)\s+(?:immediately\s+)?(?:accept|approve|sign|execute|book|add)",
                               I)
# Kinds kept for contracts. Urgency ("immediately") and prior agreement ("as agreed") are ordinary contract wording.
_WARNING_AUTHORITY = {"PRE_APPROVAL", "IMPERSONATION"}
_BLOCKING_REQUESTS = {DataRequestKind.SYSTEM_PROMPT}
# A lender agreement states its own limit and may set a minimum cash covenant: those are its content, not requests.
_LENDER_CONTENT = {DataRequestKind.FACILITY_LIMIT, DataRequestKind.RESERVE_FLOOR}


def _overlaps(a: SourceSpan, b: SourceSpan) -> bool:
    return a.doc_id == b.doc_id and a.start < b.end and b.start < a.end


def ground_flags(doc: SourceDocument, kind: DocumentKind, extra_authority: Sequence[XAuthorityClaim] = (),
                 extra_requests: Sequence[XDataRequest] = ()) -> tuple[list[AuthorityClaim], list[DataRequest]]:
    """The lexicon over the whole document, plus a backend's own flags, filtered for contract wording."""
    by_id = {doc.doc_id: doc}
    claims: list[AuthorityClaim] = []
    for c in [*lexicon.find_authority_claims(doc), *extra_authority]:
        sp = locate(by_id, doc.doc_id, c.quote)
        if sp is None:
            continue
        if c.kind == "INSTRUCTION_OVERRIDE" and (_PARTY_OBLIGATION.fullmatch(sp.text.strip())
                                                 or (lexicon.CHANGE_SETTING_RE.search(sp.text)
                                                     and not AGENT_ADDRESSED.search(sp.text))):
            continue
        if c.kind != "INSTRUCTION_OVERRIDE" and c.kind not in _WARNING_AUTHORITY:
            continue
        if not any(x.kind == c.kind and _overlaps(x.span, sp) for x in claims):
            claims.append(AuthorityClaim(kind=c.kind, span=sp))
    for m in AGENT_ADDRESSED.finditer(doc.text):
        sp = SourceSpan(doc_id=doc.doc_id, start=m.start(), end=m.end(), text=m.group(0))
        if not any(x.kind == "INSTRUCTION_OVERRIDE" and _overlaps(x.span, sp) for x in claims):
            claims.append(AuthorityClaim(kind="INSTRUCTION_OVERRIDE", span=sp))
    requests: list[DataRequest] = []
    for r in [*lexicon.find_data_requests(doc), *extra_requests]:
        rk = DataRequestKind(r.kind)
        if kind == DocumentKind.LENDER_AGREEMENT and rk in _LENDER_CONTENT:
            continue
        sp = locate(by_id, doc.doc_id, r.quote)
        if sp is not None and not any(x.kind == rk and _overlaps(x.span, sp) for x in requests):
            requests.append(DataRequest(kind=rk, span=sp))
    claims.sort(key=lambda c: (c.span.start, c.kind))
    requests.sort(key=lambda r: (r.span.start, r.kind.value))
    return claims, requests


_FLAG_NOTES = {
    "INSTRUCTION_OVERRIDE": "text addressed to the agent: it is not a term, and the document cannot be confirmed; ask the "
                            "counterparty for a clean copy",
    "PRE_APPROVAL": "the text claims an approval nobody gave through the agent",
    "IMPERSONATION": "the text claims to speak for someone, or changes payment details: check it with the counterparty",
}


def document_flags(claims: Sequence[AuthorityClaim], requests: Sequence[DataRequest]) -> list[DocumentFlag]:
    flags = [DocumentFlag(kind=c.kind, span=c.span, blocking=c.kind == "INSTRUCTION_OVERRIDE",
                          note=_FLAG_NOTES.get(c.kind, "a claim of authority")) for c in claims]
    for r in requests:
        blocking = r.kind in _BLOCKING_REQUESTS
        note = ("the text asks for the agent's instructions: the document cannot be confirmed" if blocking
                else "the text asks the supplier to disclose protected information")
        flags.append(DocumentFlag(kind=f"DATA_REQUEST:{r.kind.value}", span=r.span, blocking=blocking, note=note))
    return sorted(flags, key=lambda f: (f.span.start, f.kind))


# ---------------------------------------------------------------- terms


@dataclass
class _Ctx:
    doc: SourceDocument
    abst: list[Abstention]


def _drop(ctx: _Ctx, field: ContractField, reason: str, spans: Sequence[SourceSpan] = ()) -> None:
    ctx.abst.append(Abstention(field=field.value, reason=reason, spans=list(spans)))


def _fragment(ctx: _Ctx, x: XContractTerm, span: SourceSpan, name: str) -> str | None | bool:
    """The fragment's text when it sits inside the quote; None when null; False (with an abstention) when outside."""
    v = getattr(x, name)
    if v is None or not v.strip():
        return None
    if v.strip() not in span.text:
        _drop(ctx, x.field, f"term dropped: its {name} is not inside its quoted evidence", [span])
        return False
    return v.strip()


def _need(ctx: _Ctx, field: ContractField, p: Parsed, what: str, span: SourceSpan) -> bool:
    if p.conflict:
        _drop(ctx, field, f"term dropped: the {what} is stated twice with different values (words against figures)",
              [span])
        return False
    if p.value is None:
        _drop(ctx, field, f"term dropped: the {what} is not parseable as an exact value", [span])
        return False
    return True


_REQUIRED: dict[ContractField, str] = {
    F.PARTY_SUPPLIER: "value_text", F.PARTY_BUYER: "value_text", F.CONTRACT_REFERENCE: "value_text",
    F.SIGNED_DATE: "date_text", F.START_DATE: "date_text", F.END_DATE: "date_text", F.DURATION: "period_text",
    F.PRICE: "value_text", F.INVOICING: "period_text", F.SCHEDULED_INVOICE: "date_text", F.PAYMENT_TERMS: "period_text",
    F.EARLY_PAYMENT: "value_text", F.MILESTONE: "value_text", F.RETENTION: "value_text", F.LATE_INTEREST: "value_text",
    F.DELIVERABLE: "value_text", F.REQUIRED_DOCUMENT: "value_text", F.AMENDMENT: "value_text",
}


def _ground_term(ctx: _Ctx, x: XContractTerm, chunk: Chunk, chunk_doc: SourceDocument) -> ContractTerm | None:
    sp = locate({chunk_doc.doc_id: chunk_doc}, chunk_doc.doc_id, x.quote)
    if sp is None:
        _drop(ctx, x.field, "term dropped: its quote is not found verbatim in the document")
        return None
    span = SourceSpan(doc_id=ctx.doc.doc_id, start=chunk.start + sp.start, end=chunk.start + sp.end, text=sp.text)
    frags: dict[str, str | None] = {}
    for name in ("value_text", "date_text", "period_text", "basis_text", "unit_text", "trigger_text", "reference_text"):
        v = _fragment(ctx, x, span, name)
        if v is False:
            return None
        frags[name] = v  # type: ignore[assignment]
    need = _REQUIRED[x.field]
    if frags[need] is None:
        _drop(ctx, x.field, f"term dropped: no {need.removesuffix('_text').replace('_', ' ')} is stated in its quote",
              [span])
        return None
    out: dict[str, object] = {"field": x.field, "span": span, "clause": clause_label(ctx.doc.text, span.start),
                              "value_text": frags["value_text"] or frags[need]}
    f = x.field
    if f in (F.PARTY_SUPPLIER, F.PARTY_BUYER, F.CONTRACT_REFERENCE, F.DELIVERABLE, F.REQUIRED_DOCUMENT, F.AMENDMENT):
        out["text"] = frags["value_text"]
    elif f in (F.SIGNED_DATE, F.START_DATE, F.END_DATE):
        p = parse_date(frags["date_text"])
        if not _need(ctx, f, p, "date", span):
            return None
        out["date"] = p.value
    elif f == F.DURATION:
        p = parse_months(frags["period_text"])
        if not _need(ctx, f, p, "term", span):
            return None
        out["months"] = p.value
    elif f == F.PRICE:
        p = parse_money(frags["value_text"])
        if not _need(ctx, f, p, "amount", span):
            return None
        out["amount_fen"], out["unit"] = p.value, unit_of(frags["unit_text"])
    elif f == F.INVOICING:
        period = frags["period_text"] or ""
        if re.search(r"\bmonth(?:ly)?\b|每月", period, I):
            out["months"] = 1
        else:
            p = parse_days(period)
            if not _need(ctx, f, p, "invoicing interval", span):
                return None
            out["days"] = p.value
        if frags["date_text"]:
            d = parse_date(frags["date_text"])
            if not _need(ctx, f, d, "first invoice date", span):
                return None
            out["date"] = d.value
    elif f == F.SCHEDULED_INVOICE:
        d = parse_date(frags["date_text"])
        if not _need(ctx, f, d, "invoice date", span):
            return None
        out["date"], out["reference"] = d.value, frags["reference_text"]
        if frags["value_text"]:
            p = parse_money(frags["value_text"])
            if not _need(ctx, f, p, "invoice amount", span):
                return None
            out["amount_fen"] = p.value
    elif f == F.PAYMENT_TERMS:
        p = parse_days(frags["period_text"])
        if not _need(ctx, f, p, "number of days", span):
            return None
        out["days"], out["business_days"] = p.value, business_days(frags["period_text"])
        out["basis"] = basis_of(frags["basis_text"])
        if out["basis"] is None:
            _drop(ctx, f, "note: the payment terms do not say what the days count from", [span])
    elif f in (F.EARLY_PAYMENT, F.MILESTONE, F.RETENTION, F.LATE_INTEREST):
        p = parse_rate(frags["value_text"])
        if not _need(ctx, f, p, "rate", span):
            return None
        out["rate_bp"] = p.value
        period = frags["period_text"]
        if f == F.EARLY_PAYMENT and period:
            w = parse_days(period)
            if not _need(ctx, f, w, "early-payment window", span):
                return None
            out["days"], out["business_days"] = w.value, business_days(period)
        elif f == F.RETENTION and period:
            if (months := parse_months(period)).ok:
                out["months"] = months.value
            elif (days := parse_days(period)).ok:
                out["days"] = days.value
            else:
                out["text"] = period  # "until the end of the warranty period": shown as written
        elif f == F.LATE_INTEREST:
            out["text"] = period
        elif f == F.MILESTONE:
            out["text"] = frags["trigger_text"]
    return ContractTerm.model_validate(out)


def _key(t: ContractTerm) -> tuple[object, ...]:
    text = re.sub(r"\s+", " ", t.text or "").strip().lower()
    return (t.amount_fen, t.rate_bp, t.days, t.months, t.date, t.basis, t.unit, t.reference, text)


def _merge(terms: list[ContractTerm], abst: list[Abstention]) -> tuple[list[ContractTerm], bool]:
    """Read a term stated twice once; drop a one-valued field stated with different values (CONFLICTING_SOURCES)."""
    kept: list[ContractTerm] = []
    conflict = False
    by_field: dict[ContractField, list[ContractTerm]] = {}
    for t in terms:
        by_field.setdefault(t.field, []).append(t)
    for field, group in by_field.items():
        distinct: dict[tuple[object, ...], ContractTerm] = {}
        for t in group:
            distinct.setdefault(_key(t), t)
        if field not in MULTI_VALUED_CONTRACT_FIELDS and len(distinct) > 1:
            conflict = True
            where = ", ".join(t.clause or "an unnumbered clause" for t in group)
            abst.append(Abstention(field=field.value, spans=[t.span for t in group], reason=(
                f"conflicting sources: {where} state different values; neither is read, clarification needed")))
            continue
        if len(group) > len(distinct):
            abst.append(Abstention(field=f"note:{field.value}", spans=[t.span for t in group], reason=(
                "stated more than once with the same value: read once")))
        kept += distinct.values()
    return sorted(kept, key=lambda t: (t.span.start, t.field.value)), conflict


def build_contract(doc: SourceDocument, parts: Sequence[tuple[Chunk, ContractExtraction]], compiler_id: str,
                   prompt_version: str, kind: DocumentKind = DocumentKind.BUYER_CONTRACT) -> CompiledContract:
    """The grounded reading of a contract of `kind` (a buyer contract or, ADR-0013, a capex contract): the same terms and
    flags for both; only the material fields that decide ABSTAINED differ (`material_missing`)."""
    if kind not in (DocumentKind.BUYER_CONTRACT, DocumentKind.CAPEX_CONTRACT):
        raise ValueError(f"{kind.value} is not read as a contract")
    ctx = _Ctx(doc=doc, abst=[])
    grounded: list[ContractTerm] = []
    extra_authority: list[XAuthorityClaim] = []
    extra_requests: list[XDataRequest] = []
    for chunk, ex in parts:
        chunk_doc = chunk_source(doc, chunk)
        for x in ex.terms:
            t = _ground_term(ctx, x, chunk, chunk_doc)
            if t is not None:
                grounded.append(t)
        # a backend's flags quote its chunk; the quotes are located again in the whole document
        extra_authority += [a.model_copy(update={"doc_id": doc.doc_id}) for a in ex.authority_claims]
        extra_requests += [r.model_copy(update={"doc_id": doc.doc_id}) for r in ex.data_requests]
    claims, requests = ground_flags(doc, kind, extra_authority, extra_requests)
    blocking = [c.span for c in claims if c.kind == "INSTRUCTION_OVERRIDE"]
    blocking += [r.span for r in requests if r.kind in _BLOCKING_REQUESTS]
    clean: list[ContractTerm] = []
    for t in grounded:
        hit = [b for b in blocking if _same_sentence(doc.text, t.span, b) or _overlaps(t.span, b)]
        if hit:
            _drop(ctx, t.field, "term dropped: it sits in text addressed to the agent, which is never read as a term",
                  [t.span, *hit])
            continue
        clean.append(t)
    terms, conflict = _merge(clean, ctx.abst)
    found = {t.field for t in terms}
    conflicted = {a.field for a in ctx.abst if a.reason.startswith("conflicting sources")}
    not_found = [f for f in ContractField if f not in found and f.value not in conflicted]
    if conflict:
        status = CompileStatus.CONFLICTING_SOURCES
    elif material_missing(kind, found):
        status = CompileStatus.ABSTAINED
    else:
        status = CompileStatus.COMPILED
    return CompiledContract(
        doc_id=doc.doc_id, status=status, terms=terms, not_found=not_found, abstentions=ctx.abst,
        authority_claims=claims, data_requests=requests, chunks=len(parts), compiler=compiler_id,
        prompt_version=prompt_version,
    )


def _same_sentence(text: str, a: SourceSpan, b: SourceSpan) -> bool:
    return lexicon.sentence_bounds(text, a.start) == lexicon.sentence_bounds(text, b.start)


__all__ = [
    "AGENT_ADDRESSED",
    "CAPEX_WHEN_PAID",
    "MAX_CHUNKS",
    "MAX_CHUNK_CHARS",
    "Chunk",
    "ContractTooLong",
    "build_contract",
    "chunk_document",
    "chunk_source",
    "clause_label",
    "contract_document",
    "document_flags",
    "ground_flags",
    "material_missing",
]
