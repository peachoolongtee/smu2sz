"""Privacy before the model: identifiers FLOW never reads are replaced before text reaches a model provider.

Live mode sends a document to Claude or DeepSeek only when no recorded reading exists (`compiler.service`). Before it
goes, `redact` replaces the identifiers FLOW never extracts with stable placeholders (one per distinct value per call):
- ACCOUNT: bank account and card numbers (labelled by 账号/账户/卡号/Account No., or 16 to 19 bare digits);
- PHONE: mobile and landline numbers (labelled by 电话/手机/Tel/Phone, or a Chinese mobile, a 0755- style landline, a
  +country number);
- EMAIL: email addresses;
- USCC: the 18-character unified social credit code (统一社会信用代码);
- NATIONAL_ID: national ID and passport numbers (labelled, or an 18-character 身份证 number with a valid birth date);
- ADDRESS: a street address, only where a label says so (住所/地址/Address:).
Party names, amounts, dates, percentages, rates, contract and invoice numbers and the clauses are kept: FLOW reads them.
A bare number in an invoice, contract or amount context is never taken for an account or a phone.

The redaction is reversible with an offset map (`Redaction.to_original`): the model quotes the redacted text, and
`RedactingBackend` maps every quote back to the original document's own substring before grounding, so the stored spans
and offsets refer to the original. A placeholder inside a quote maps back to the original identifier; a quote that cuts
a placeholder widens to the whole identifier. Recorded readings, the rules grammar and the cross-check never see
redacted text: the redaction wraps the model backends only, so cache keys are unchanged.

Only counts per kind are logged, never the values.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

from app.compiler.base import BackendError, ContractResult, LLMBackend, OfferResult, TermSheetResult
from app.domain.models import SourceDocument

log = structlog.get_logger("termsledger.compiler")

OPEN, CLOSE = "⟦", "⟧"  # ⟦ ⟧
KINDS = ("ACCOUNT", "PHONE", "EMAIL", "USCC", "NATIONAL_ID", "ADDRESS")
PLACEHOLDER_RE = re.compile(f"{OPEN}([A-Z_]+)_([0-9]+){CLOSE}")

_B = r"(?<![A-Za-z0-9_\-/.])"  # no letter, digit or reference joiner before
_E = r"(?![A-Za-z0-9_\-/]|[.,][0-9])"  # nor after (a trailing full stop is fine, a decimal is not)
_SEP = r"[ \t]*[:：]?[ \t]*"
_USCC_CH = "0-9A-HJ-NP-RT-UW-Y"  # GB 32100-2015: no I, O, S, V, Z
_NUM_END = r"(?![0-9A-Za-z年月日元万%])"  # a labelled number ends where a date, an amount or a word would go on
_MIN_DIGITS = {"ACCOUNT": 8, "PHONE": 7}

# (kind, priority, pattern). A pattern with a group `v` replaces only that group (its label stays). Higher priority wins
# an overlap; labelled patterns outrank bare ones, so 账号 + 18 digits is an ACCOUNT, not a USCC.
_LABELLED: list[tuple[str, int, re.Pattern[str]]] = [
    ("USCC", 9, re.compile(
        r"(?<![A-Za-z])(?:统一社会信用代码|社会信用代码|信用代码|纳税人识别号|税号|Unified Social Credit Code|USCC|Tax ID(?: No\.?)?)"
        rf"(?:[ \t]*[(（][^)）\n]{{0,30}}[)）])?{_SEP}(?P<v>[{_USCC_CH}]{{15,20}})(?![A-Za-z0-9])", re.IGNORECASE)),
    ("NATIONAL_ID", 9, re.compile(
        r"(?<![A-Za-z])(?:身份证(?:号码|号)?|证件号(?:码)?|护照号(?:码)?|ID (?:Card )?No\.?|Passport No\.?|National ID(?: No\.?)?)"
        rf"{_SEP}(?P<v>[A-Z0-9]{{6,20}})(?![A-Za-z0-9])", re.IGNORECASE)),
    ("ACCOUNT", 9, re.compile(
        r"(?<![A-Za-z])(?:账号|帐号|账户号码|账户号|账户|帐户|银行卡号|卡号|Account (?:No\.?|Number)|A/C(?: No\.?)?|IBAN|Card (?:No\.?|Number))"
        rf"(?:[ \t]*[(（][^)）\n]{{0,30}}[)）])?{_SEP}(?P<v>[0-9]{{2,}}(?:[ \-][0-9]{{2,}}){{0,8}}){_NUM_END}", re.IGNORECASE)),
    ("PHONE", 9, re.compile(
        r"(?<![A-Za-z])(?:联系电话|电话号码|电话|手机号码|手机号|手机|传真|座机|Tel(?:ephone)?|Phone|Mobile|Fax|Cell)\.?(?:[ 	]*(?:number|No\.?))?"
        rf"(?:[ \t]*[(（][^)）\n]{{0,20}}[)）])?{_SEP}(?P<v>\+?(?:\([0-9]{{1,4}}\)[ \-]?)?[0-9]{{2,}}(?:[ \-][0-9]{{2,}}){{0,4}}){_NUM_END}", re.IGNORECASE)),
    ("EMAIL", 8, re.compile(r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")),
    ("ADDRESS", 7, re.compile(
        r"(?<![A-Za-z])(?:住所地|住所|注册地址|通讯地址|联系地址|办公地址|收货地址|地址|(?:Registered |Business |Mailing |Office )?Address)"
        r"[ \t]*[:：][ \t]*(?P<v>[^\n；;]{2,160}?)"
        r"(?=[ \t]*(?:$|\n|[；;。]|[ \t，,]+(?:法定代表人|负责人|联系人|电话|手机|传真|邮编|邮箱|电子邮箱|统一社会信用代码|开户|账号|"
        r"Tel|Phone|Fax|Email|Legal Representative|Contact)))", re.IGNORECASE | re.MULTILINE)),
    ("ADDRESS", 6, re.compile(
        r"(?:registered (?:address|office)|principal place of business|address) at[ \t]+(?P<v>[^\n;；(（\"“]{4,160}?)"
        r"(?=[ \t]*(?:$|\n|[;；(（\"“]|,?[ \t]+and\b|,[ \t]*(?:hereinafter|represented)))", re.IGNORECASE | re.MULTILINE)),
]

_BARE: list[tuple[str, int, re.Pattern[str]]] = [
    ("NATIONAL_ID", 5, re.compile(
        rf"{_B}(?P<v>[1-9][0-9]{{5}}(?:19|20)[0-9]{{2}}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])[0-9]{{3}}[0-9Xx]){_E}")),
    ("USCC", 5, re.compile(rf"{_B}(?P<v>[1-9ANY][1-9][0-9]{{6}}[{_USCC_CH}]{{9}}[{_USCC_CH}]){_E}")),
    ("ACCOUNT", 4, re.compile(rf"{_B}(?P<v>[0-9]{{4}}(?:[ \-]?[0-9]{{4}}){{2}}[ \-]?[0-9]{{4,7}}){_E}")),
    ("PHONE", 4, re.compile(rf"{_B}(?P<v>(?:\+?86[ \-]?)?1[3-9][0-9](?:[ \-]?[0-9]{{4}}){{2}}){_E}")),
    ("PHONE", 4, re.compile(rf"{_B}(?P<v>(?:\(0[1-9][0-9]{{1,2}}\)|0[1-9][0-9]{{1,2}})[ \-]?[2-9][0-9]{{2,3}}[ \-]?[0-9]{{4}}(?:-[0-9]{{1,5}})?){_E}")),
    ("PHONE", 4, re.compile(rf"(?<![A-Za-z0-9_\-/.])(?P<v>\+[1-9][0-9]{{0,2}}[ \-]?(?:\([0-9]{{1,4}}\)[ \-]?)?[0-9]{{2,4}}(?:[ \-]?[0-9]{{3,4}}){{1,3}}){_E}")),
]

# A bare number with one of these just before it is a reference or an amount FLOW reads, never an identifier.
_KEEP_BEFORE = re.compile(
    r"(?:发票|合同|协议|编号|单号|订单|批次|号码|代码|invoice|contract|agreement|order|ref(?:erence)?|no\.?|number|#|"
    r"[¥￥$€£]|rmb|cny|usd|hkd|人民币|金额|价款|总价)[\s:：()（）]*$", re.IGNORECASE)
_KEEP_AFTER = re.compile(r"^\s*(?:元|万|亿|角|分|yuan|fen|rmb|cny|usd|%|percent|天|日|days?)", re.IGNORECASE)


@dataclass(frozen=True)
class Segment:
    r_start: int  # in the redacted text
    r_end: int
    o_start: int  # in the original text
    o_end: int
    kind: str
    placeholder: str


@dataclass
class Redactor:
    """One per model call: the same value gets the same placeholder in every document of the call."""

    table: dict[tuple[str, str], str] = field(default_factory=dict)  # (kind, value) -> placeholder
    values: dict[str, str] = field(default_factory=dict)  # placeholder -> value
    counts: Counter[str] = field(default_factory=Counter)

    def _placeholder(self, kind: str, value: str) -> str:
        key = (kind, value)
        if key not in self.table:
            n = sum(1 for k, _ in self.table if k == kind) + 1
            ph = f"{OPEN}{kind}_{n}{CLOSE}"
            self.table[key] = ph
            self.values[ph] = value
        return self.table[key]

    def redact(self, text: str) -> Redaction:
        found = sorted(_matches(text), key=lambda m: (-m[2], m[0], -(m[1] - m[0])))
        taken: list[tuple[int, int, str]] = []
        for s, e, _prio, kind in found:
            if not any(s < te and ts < e for ts, te, _ in taken):
                taken.append((s, e, kind))
        taken.sort()
        out: list[str] = []
        segs: list[Segment] = []
        pos = 0
        rlen = 0
        for s, e, kind in taken:
            out.append(text[pos:s])
            rlen += s - pos
            ph = self._placeholder(kind, text[s:e])
            segs.append(Segment(rlen, rlen + len(ph), s, e, kind, ph))
            out.append(ph)
            rlen += len(ph)
            pos = e
            self.counts[kind] += 1
        out.append(text[pos:])
        return Redaction(original=text, redacted="".join(out), segments=tuple(segs))

    def substitute(self, s: str, escape: Callable[[str], str] = lambda v: v) -> str:
        """Every whole placeholder in `s` replaced by its original value."""
        return PLACEHOLDER_RE.sub(lambda m: escape(self.values.get(m.group(0), m.group(0))), s)


def _matches(text: str) -> Iterable[tuple[int, int, int, str]]:
    for kind, prio, rx in _LABELLED:
        for m in rx.finditer(text):
            s, e = m.span("v") if "v" in rx.groupindex else m.span()
            v = text[s:e].rstrip(" \t,，.")
            if v.strip():
                yield s, s + len(v), prio, kind
    for kind, prio, rx in _BARE:
        for m in rx.finditer(text):
            s, e = m.span("v")
            if _KEEP_BEFORE.search(text[max(0, s - 24):s]) or _KEEP_AFTER.match(text[e:e + 8]):
                continue
            yield s, e, prio, kind


@dataclass(frozen=True)
class Redaction:
    original: str
    redacted: str
    segments: tuple[Segment, ...]

    def _map(self, p: int, *, end: bool, forward: bool) -> int:
        """An offset in one text as the offset in the other; inside an identifier or a placeholder it widens to the whole."""
        shift = 0
        for sg in self.segments:
            a0, a1, b0, b1 = ((sg.o_start, sg.o_end, sg.r_start, sg.r_end) if forward
                              else (sg.r_start, sg.r_end, sg.o_start, sg.o_end))
            if p <= a0:  # before this segment (or at its start)
                break
            if p < a1:  # inside it
                return b1 if end else b0
            shift = b1 - a1
        return p + shift

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """A span of the redacted text as the span of the original it stands for."""
        return self._map(start, end=False, forward=False), self._map(end, end=True, forward=False)

    def to_redacted(self, start: int, end: int) -> tuple[int, int]:
        """A span of the original as the span of the redacted text that stands for it."""
        return self._map(start, end=False, forward=True), self._map(end, end=True, forward=True)

    def find(self, quote: str) -> tuple[int, int] | None:
        """A quote's span in the redacted text: exact, then whitespace-insensitive (as `grounding.locate` reads)."""
        q = quote.strip()
        if not q:
            return None
        i = self.redacted.find(q)
        if i >= 0:
            return i, i + len(q)
        tokens = q.split()
        if len(tokens) > 1:
            m = re.search(r"\s+".join(re.escape(t) for t in tokens), self.redacted)
            if m:
                return m.span()
        return None


def _has_mark(s: str) -> bool:
    return OPEN in s or CLOSE in s


@dataclass
class RedactedCall:
    """The redacted documents of one call, and how to map the model's strings back to the original text."""

    redactor: Redactor
    docs: list[SourceDocument]
    by_id: dict[str, Redaction]

    def restore(self, s: str, doc_id: str | None = None) -> str:
        """A string the model returned, in the original's words. A quote of a redacted document maps through the offset
        map to the original's own substring; anything else has its whole placeholders substituted."""
        if not _has_mark(s):
            return s
        order = [self.by_id[doc_id]] if doc_id in self.by_id else []
        order += [r for k, r in self.by_id.items() if k != doc_id]
        for r in order:
            span = r.find(s)
            if span is not None:
                lead = len(s) - len(s.lstrip())
                trail = len(s) - len(s.rstrip())
                os_, oe = r.to_original(*span)
                return s[:lead] + r.original[os_:oe] + (s[len(s) - trail:] if trail else "")
        return self.redactor.substitute(s)

    def restore_model(self, model: BaseModel) -> Any:
        return type(model).model_validate(self._walk(model.model_dump(), None))

    def _walk(self, v: Any, doc_id: str | None) -> Any:
        if isinstance(v, dict):
            did = v.get("doc_id") if isinstance(v.get("doc_id"), str) else doc_id
            return {k: self._walk(x, did) for k, x in v.items()}
        if isinstance(v, list):
            return [self._walk(x, doc_id) for x in v]
        if isinstance(v, str):
            return self.restore(v, doc_id)
        return v


def redact_documents(docs: Sequence[SourceDocument], redactor: Redactor | None = None) -> RedactedCall:
    r = redactor or Redactor()
    by_id: dict[str, Redaction] = {}
    out: list[SourceDocument] = []
    for d in docs:
        red = r.redact(d.text)
        by_id[d.doc_id] = red
        out.append(d if red.redacted == d.text else d.model_copy(update={"text": red.redacted}))
    return RedactedCall(r, out, by_id)


def log_counts(backend: str, purpose: str, counts: Counter[str]) -> None:
    """Counts per kind only; never a value."""
    log.info("model.redaction", backend=backend, purpose=purpose, total=sum(counts.values()),
             **{k.lower(): counts.get(k, 0) for k in KINDS})


R = TypeVar("R", OfferResult, TermSheetResult, ContractResult)


class RedactingBackend:
    """A model backend behind the redaction: it receives redacted documents, and its extraction comes back with every
    quote and fragment in the original's words, ready for the same grounding as any other backend's."""

    def __init__(self, inner: LLMBackend) -> None:
        self.inner = inner
        self.name = inner.name

    def _call(self, purpose: str, docs: Sequence[SourceDocument], call: Callable[[list[SourceDocument]], R]) -> R:
        rc = redact_documents(docs)
        log_counts(self.name, purpose, rc.redactor.counts)
        res = call(rc.docs)
        if not rc.redactor.counts:
            return res
        return type(res)(rc.restore_model(res.extraction), res.model_id)

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        return self._call("offer", docs, lambda d: self.inner.extract_offer(d))

    def extract_term_sheet(self, doc: SourceDocument) -> TermSheetResult:
        return self._call("term_sheet", [doc], lambda d: self.inner.extract_term_sheet(d[0]))

    def extract_contract(self, chunk: SourceDocument) -> ContractResult:
        fn = getattr(self.inner, "extract_contract", None)
        if fn is None:
            raise BackendError(f"{self.name} cannot read contracts")
        return self._call("contract", [chunk], lambda d: fn(d[0]))


def redacting(backends: Iterable[LLMBackend], enabled: bool) -> list[LLMBackend]:
    return [RedactingBackend(b) if enabled else b for b in backends]


def redact_text(text: str) -> tuple[str, Redactor]:
    """One free text (the NL classifier's message): the redacted text and the redactor that can restore it."""
    r = Redactor()
    return r.redact(text).redacted, r


def json_escape(v: str) -> str:
    return json.dumps(v, ensure_ascii=False)[1:-1]
