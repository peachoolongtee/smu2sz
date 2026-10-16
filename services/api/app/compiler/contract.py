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
from app.compiler.contract_checks import (
    check_notes,
    cross_checks,
    derived_dates,
    payer_payee_check,
    stage_basis,
    stage_deadline,
    stage_trigger,
    widen_to_row,
)
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
from app.compiler.parsing import find_money, rx
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


# LATE_INTEREST is what the BUYER owes for paying late. A supplier's penalty for delivering late is not that: the
# model sometimes records it under the same field (both read "X per day"), so code drops it by the quote's words.
_LATE_DELIVERY = rx(
    r"(?:逾期|延期|延迟|迟延|拖延)\s*(?:交货|交付|供货|送货|发货|提供)"
    r"|(?:late|delayed?|overdue)\s+(?:delivery|deliveries|shipment|performance)"
    r"|(?:delay|delays|failure|fails?|late)\s+(?:in|to|with)\s+(?:(?:the|any)\s+)?(?:deliver(?:y|ing)?|ship(?:ping|ment)?|perform(?:ing)?)"
    r"|delivers?\s+(?:the\s+goods\s+)?(?:late|after\s+the\s+(?:delivery\s+)?date)", I)
_LATE_PAYMENT = rx(
    r"(?:逾期|延期|延迟|迟延|拖欠|拖延)\s*(?:付款|支付|结算|给付|付费)|未(?:按时|及时|按期|如期)\s*(?:付款|支付|结算)"
    r"|(?:late|overdue|delayed|delinquent|default(?:ed)?\s+in)\s+(?:payments?|paying|invoices?|amounts?|sums?)"
    r"|(?:payment|invoice|amount|sum)s?\s+(?:is|are|being|remains?)?\s*(?:late|overdue|past\s+due)"
    r"|(?:delay|delays|failure|fails?|late)\s+(?:in|to|with)\s+(?:(?:the|any)\s+)?(?:paying|payments?|pay)\b"
    r"|pays?\s+(?:\w+\s+){0,4}late|interest\s+on\s+(?:any\s+)?(?:overdue|late|unpaid)", I)


# "乙方逾期履行的，每逾期一日，按逾期部分价款的0.2%向甲方支付违约金": 乙方 performing late, a penalty (违约金), no late payment.
_SUPPLIER_LATE_PERFORMANCE = rx(r"乙方\s*(?:逾期|延期|延迟|迟延)\s*(?:履行|交付|交货|完成|履约)")


def supplier_late_delivery_penalty(quote: str) -> bool:
    """True when the quote is the supplier's penalty for late delivery (or 乙方's late performance with a 违约金) and says
    nothing of the buyer paying late."""
    late = _LATE_DELIVERY.search(quote) is not None or (
        _SUPPLIER_LATE_PERFORMANCE.search(quote) is not None and "违约金" in quote)
    return late and _LATE_PAYMENT.search(quote) is None


# RETENTION is money withheld from a payment. A performance bond or guarantee the supplier posts is a different thing
# (it is returned after acceptance, nothing is withheld), so a quote about a bond with no word of withholding is dropped.
_BOND = rx(r"履约保证金|履约保函|履约担保|保函|履约保证|performance\s+(?:bond|guarantee|security)|security\s+deposit"
           r"|(?:bank|bid|tender)\s+guarantee", I)
_WITHHELD = rx(r"质保金|质量保证金|保留金|尾款|扣留|扣除|暂扣|预留|retention|retain(?:s|ed|ing)?|withh[eo]ld(?:s|ing)?"
               r"|withheld|holdback|deduct(?:s|ed|ion)?", I)


def is_performance_bond(quote: str) -> bool:
    """True when the quote is about a performance bond or guarantee and says nothing of money withheld."""
    return _BOND.search(quote) is not None and _WITHHELD.search(quote) is None


_WITHHOLDING_MONEY = rx(r"质保金|质量保证金|保留金")
_PAYS = rx(r"支付|付款|付给|给付")


def _stage_or_retention(ctx: _Ctx, x: XContractTerm, span: SourceSpan) -> XContractTerm:
    """A Chinese payment row filed under the wrong one of RETENTION and MILESTONE is moved to the right one, by its words.
    The warranty money (质保金), paid when the warranty ends, is the retention; a payment that waits for an audit, an
    acceptance, a quarter or a delivery and holds back nothing is a stage, whatever the reading called it."""
    if not _has_cjk(span.text):
        return x
    if x.field == F.MILESTONE and _WITHHOLDING_MONEY.search(span.text) and stage_trigger(span.text) == "warranty_end":
        _drop(ctx, F.RETENTION, "note: a warranty-money row read as a stage is read as the retention", [span])
        return x.model_copy(update={"field": F.RETENTION})
    if (x.field == F.RETENTION and not _WITHHELD.search(span.text) and _PAYS.search(span.text)
            and stage_trigger(span.text) not in (None, "warranty_end")):
        _drop(ctx, F.MILESTONE, "note: a payment stage read as a retention is read as a stage", [span])
        return x.model_copy(update={"field": F.MILESTONE})
    return x


# A price per kilogram, per trip, per mould shot, per piece, per placement or per thousand sheets is a rate in a rate card
# or a unit-price row, never the contract total: it is not read as a PRICE, so it cannot stand against the total.
_RATE_UNIT = re.compile(r"\s*(?:每\s*)?(?:公斤|车次|模次|件|点|千张)\s*")
_TOTAL_WORDS = re.compile(r"合计|总价|总额|总金额|预估金额")


def _ground_term(ctx: _Ctx, x: XContractTerm, chunk: Chunk, chunk_doc: SourceDocument) -> ContractTerm | None:
    sp = locate({chunk_doc.doc_id: chunk_doc}, chunk_doc.doc_id, x.quote)
    if sp is None:
        _drop(ctx, x.field, "term dropped: its quote is not found verbatim in the document")
        return None
    span = SourceSpan(doc_id=ctx.doc.doc_id, start=chunk.start + sp.start, end=chunk.start + sp.end, text=sp.text)
    if x.field in (F.MILESTONE, F.RETENTION):  # a payment-table row quoted short of its deadline is read to the row's end
        end = widen_to_row(ctx.doc.text, span.start, span.end)
        if end != span.end:
            span = SourceSpan(doc_id=ctx.doc.doc_id, start=span.start, end=end, text=ctx.doc.text[span.start:end])
    frags: dict[str, str | None] = {}
    for name in ("value_text", "date_text", "period_text", "basis_text", "unit_text", "trigger_text", "reference_text"):
        if name == "trigger_text" and x.field == F.MILESTONE and (x.trigger_text or "").strip() not in span.text:
            # the label of a stage is not one of its values (the share and the days come from the quote): a label the
            # reading wrote in its own words is left out, the stage is kept
            _drop(ctx, x.field, "note: the stage's trigger wording is not inside its quote and is not shown", [span])
            frags[name] = None
            continue
        v = _fragment(ctx, x, span, name)
        if v is False:
            return None
        frags[name] = v  # type: ignore[assignment]
    if x.field == F.LATE_INTEREST and supplier_late_delivery_penalty(span.text):
        _drop(ctx, x.field, "term dropped: the clause is the supplier's penalty, not interest owed by the buyer", [span])
        return None
    if x.field == F.RETENTION and is_performance_bond(span.text):
        _drop(ctx, x.field, "term dropped: the clause is a performance bond the supplier posts, not money withheld "
              "from payments", [span])
        return None
    x = _stage_or_retention(ctx, x, span)
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
        if _RATE_UNIT.fullmatch(frags["unit_text"] or "") and not _TOTAL_WORDS.search(frags["value_text"] or ""):
            ctx.abst.append(Abstention(field=f"note:{F.PRICE.value}", spans=[span], reason=(
                f"note: a price per {frags['unit_text']} is a unit rate, not a candidate contract total")))
            return None
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
            _stage_schedule(ctx, out, span)
    if f == F.RETENTION and _has_cjk(span.text) and out.get("months") is None:
        d = stage_deadline(span.text)  # "质保期满且无质量问题后30个工作日内": the days of its release, working or calendar
        if d.status == "ok" and out.get("days") in (None, d.days):
            out["days"], out["business_days"] = d.days, d.working
    return ContractTerm.model_validate(out)


def _stage_schedule(ctx: _Ctx, out: dict[str, object], span: SourceSpan) -> None:
    """A milestone's own payment deadline, read by code from its quote: the days, working or calendar, and the PaymentBasis
    where the trigger is one it has (invoice, delivery, acceptance). A quote with no days, or two different ones, leaves
    the stage without a deadline and says so."""
    d = stage_deadline(span.text)
    if d.status == "conflict":
        _drop(ctx, F.MILESTONE, "note: the stage's quote states more than one payment deadline, so none is read", [span])
    elif d.status == "none":
        _drop(ctx, F.MILESTONE, "note: the stage's quote states no number of days for its payment", [span])
    else:
        out["days"], out["business_days"] = d.days, d.working
        out["basis"] = stage_basis(stage_trigger(span.text, out.get("text") if isinstance(out.get("text"), str) else None))


def _has_cjk(text: str) -> bool:
    return re.search(r"[一-鿿]", text) is not None


def _key(t: ContractTerm) -> tuple[object, ...]:
    text = re.sub(r"\s+", " ", t.text or "").strip().lower()
    return (t.amount_fen, t.rate_bp, t.days, t.months, t.date, t.basis, t.unit, t.reference, text)


def _without_line_items(group: list[ContractTerm], abst: list[Abstention]) -> list[ContractTerm]:
    """A price that is a line of the contract total is read inside it, not against it: the row that states the total
    (quantity, unit price, total), or lines that add up to it. A different amount stays a conflict."""
    amounts = [t.amount_fen for t in group if t.amount_fen is not None]
    if len(set(amounts)) < 2:
        return group
    total = max(group, key=lambda t: t.amount_fen or 0)
    lines = [t for t in group if t.amount_fen != total.amount_fen]
    stated = [t for t in lines if total.amount_fen in {f.value for f in find_money(t.span.text)}]
    rest = [t for t in lines if t not in stated]
    summed = bool(rest) and sum(t.amount_fen or 0 for t in rest) == total.amount_fen
    if not stated and not summed:
        return group
    gone = stated + (rest if summed else [])
    if len(gone) != len(lines):
        return group
    abst.append(Abstention(field=F.PRICE.value, spans=[t.span for t in gone], reason=(
        "note: this amount is a line of the contract total and is read inside it")))
    return [t for t in group if t not in gone]


def _per_stage_payment_terms(terms: list[ContractTerm], abst: list[Abstention]) -> tuple[list[ContractTerm], bool]:
    """A contract that pays in stages states each stage's days in the stage itself (on its MILESTONE term). A PAYMENT_TERMS
    read from the same clause is that stage's deadline, not a rule for every payment, so it is not held against the others
    as a conflict. A PAYMENT_TERMS from a clause no stage covers is the contract-wide rule and stays. Returns the terms and
    whether payment terms were moved onto the stages (they then still count as stated)."""
    stages = [t for t in terms if t.field == F.MILESTONE and t.days is not None]
    if len(stages) < 2:
        return terms, False
    covered = [t for t in terms if t.field == F.PAYMENT_TERMS and any(_overlaps(t.span, s.span) for s in stages)]
    if covered:
        abst.append(Abstention(field=f"note:{F.PAYMENT_TERMS.value}", spans=[t.span for t in covered], reason=(
            "note: the payment days are stated per stage, not once for the contract")))
    return [t for t in terms if t not in covered], bool(covered)


def _retention_stated_twice(group: list[ContractTerm], abst: list[Abstention]) -> list[ContractTerm]:
    """A retention stated in the payment table ("4 质量保证金 3%") and again in a clause that adds when it is released
    ("按结算价的3%预留……缺陷责任期满后14日内返还") is one term: the one with the deadline is read. Only when every
    statement has the same rate and exactly one states a deadline; different rates, or two deadlines, stay a conflict."""
    rates = {t.rate_bp for t in group}
    if len(group) < 2 or len(rates) != 1 or None in rates:
        return group
    timed = [t for t in group if t.days is not None or t.months is not None]
    if len(timed) != 1 or any(t.text for t in group if t is not timed[0]):
        return group
    abst.append(Abstention(field=f"note:{F.RETENTION.value}", spans=[t.span for t in group], reason=(
        "note: the same retention is stated twice and only one statement says when it is released: read once")))
    return timed


def _merge(terms: list[ContractTerm], abst: list[Abstention]) -> tuple[list[ContractTerm], bool]:
    """Read a term stated twice once; drop a one-valued field stated with different values (CONFLICTING_SOURCES)."""
    kept: list[ContractTerm] = []
    conflict = False
    by_field: dict[ContractField, list[ContractTerm]] = {}
    for t in terms:
        by_field.setdefault(t.field, []).append(t)
    for field, group in by_field.items():
        if field == F.PRICE:
            group = _without_line_items(group, abst)
            by_field[field] = group
        if field == F.RETENTION:
            group = _retention_stated_twice(group, abst)
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
    clean, per_stage = _per_stage_payment_terms(clean, ctx.abst)
    terms, conflict = _merge(clean, ctx.abst)
    terms = payer_payee_check(doc, terms, ctx.abst)
    terms = sorted([*terms, *derived_dates(doc, terms, ctx.abst)], key=lambda t: (t.span.start, t.field.value))
    ctx.abst += check_notes(cross_checks(doc, terms))
    found = {t.field for t in terms}
    conflicted = {a.field for a in ctx.abst if a.reason.startswith("conflicting sources")}
    not_found = [f for f in ContractField if f not in found and f.value not in conflicted]
    if conflict:
        status = CompileStatus.CONFLICTING_SOURCES
    elif material_missing(kind, found | ({F.PAYMENT_TERMS} if per_stage else set())):
        # (a contract whose stages each state their own days has stated its payment terms)
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
