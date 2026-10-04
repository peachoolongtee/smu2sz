"""The contract grammar: a deterministic reading of the common shapes of supply-contract clauses (English, with a few
Chinese forms). It is the offline fallback of `extract_contract` and the source of the recorded demo cache, as
`rules.py` is for offers.

It reads one chunk at a time and quotes whole sentences (or list items) without their clause number, so a quote is a
substring of the chunk by construction; grounding still re-checks every quote and every fragment. It reports no
security flags of its own: grounding runs the lexicon over the whole document whatever the backend. An unknown
clause shape is simply not read, and the term shows as "not found": the grammar never guesses.
"""

from __future__ import annotations

import re

from app.compiler.contract_parsing import COUNT_PAT, DATE_PAT
from app.compiler.lexicon import sentence_spans
from app.compiler.parsing import MONEY_PAT, RATE_PAT, rx
from app.compiler.schema import ContractExtraction, XContractTerm
from app.domain.models import ContractField, SourceDocument

RULES_CONTRACT_MODEL_ID = "rules-v1"

I = re.IGNORECASE
F = ContractField


def _gap(n: int) -> str:
    """Up to n characters inside one sentence (a '.' only inside a number)."""
    return rf"(?:[^.。;；!！?？\n]|\.(?=\d)){{0,{n}}}?"


_MONEY_WORDS = rf"{MONEY_PAT}(?:\s*[(（][^)）\n]{{1,80}}[)）])?"  # "RMB 420,000 (four hundred and twenty thousand yuan)"
_DAYS = rf"{COUNT_PAT}\s*(?:calendar\s+|business\s+|working\s+|banking\s+)?days?"
_TERM_CUE = rx(r"\b(?:Agreement|Contract)\b|合同|协议", I)
_TERM_LENGTH_CUE = rx(r"\b(?:term|continues?|remains?\s+in\s+(?:force|effect)|expires?|until|valid|period)\b|有效期|期限",
                      I)

# ---------------------------------------------------------------- patterns

REFERENCE = rx(r"\b(?:Agreement|Contract)\s+(?:No\.?|Number|Ref(?:erence)?\.?|#)\s*[:：]?\s*"
               r"(?P<v>(?-i:[A-Z0-9][A-Z0-9/_.-]*\d[A-Z0-9/_-]*))"
               r"|(?:合同编号|合同号|协议编号)\s*[:：]?\s*(?P<vz>[A-Za-z0-9][A-Za-z0-9/_.-]*\d[A-Za-z0-9/_-]*)", I)
SIGNED = rx(rf"\b(?:is\s+|was\s+)?(?:made|dated|signed|entered\s+into|executed|concluded)\s+(?:on|as\s+of|this)\s+"
            rf"(?:the\s+)?(?P<d>{DATE_PAT})"
            rf"|\bDate\s+of\s+(?:this\s+)?(?:Agreement|Contract)\s*[:：]?\s*(?P<d2>{DATE_PAT})"
            rf"|(?:签订日期|签署日期|签约日期)\s*[:：]?\s*(?P<dz>{DATE_PAT})", I)
START = rx(rf"\b(?:takes?\s+effect|comes?\s+into\s+(?:force|effect)|commences?|is\s+effective|becomes?\s+effective"
           rf"|starts?|begins?)\s+(?:on|from|as\s+of)\s+(?:the\s+)?(?P<d>{DATE_PAT})"
           rf"|\bEffective\s+Date\s*[:：]?\s*(?P<d2>{DATE_PAT})|(?:生效日期|起始日期)\s*[:：]?\s*(?P<dz>{DATE_PAT})", I)
END = rx(rf"\b(?:until|up\s+to\s+and\s+including|expires?\s+on|ends?\s+on|ending\s+on|terminates?\s+on|through)\s+"
         rf"(?:the\s+)?(?P<d>{DATE_PAT})"
         rf"|\b(?:Expiry|End)\s+Date\s*[:：]?\s*(?P<d2>{DATE_PAT})|(?:到期日期?|终止日期)\s*[:：]?\s*(?P<dz>{DATE_PAT})", I)
DURATION = rx(rf"\b(?:term|period|duration)\s+of\s+(?P<p>{COUNT_PAT}\s*(?:months?|years?))\b"
              rf"|\bfor\s+(?P<p2>{COUNT_PAT}\s*(?:months?|years?))\b|(?:有效期|期限)\s*(?:为)?\s*(?P<pz>\d{{1,3}}\s*(?:个月|年))",
              I)
_COMPANY = (r"[A-Z][A-Za-z0-9&'’.-]*(?:[ ,]+[A-Za-z0-9&'’.-]+)*?\s(?:Co\.,?\s*Ltd\.?|Co\.|Ltd\.?|Limited|Inc\.?|LLC"
            r"|Corporation|Corp\.|Company|GmbH|PLC|Pte\.?\s+Ltd\.?)")
PARTY = rx(rf"(?P<v>{_COMPANY})(?:,[^()\n;]{{0,120}}?)?\s*\(\s*(?:the\s+|hereinafter\s+(?:called\s+|referred\s+to\s+as\s+)?)?"
           r"[\"“'‘]?(?P<role>Supplier|Seller|Vendor|Manufacturer|Buyer|Purchaser|Customer)[\"”'’]?\s*\)")
_SUPPLIER_ROLES = {"supplier", "seller", "vendor", "manufacturer"}

PRICE = [
    rx(rf"\b(?:shall\s+pay|will\s+pay|agrees?\s+to\s+pay|pays?|price\s+(?:is|of|shall\s+be|will\s+be)|priced\s+at"
       rf"|at\s+a\s+price\s+of|consideration\s+of)\b{_gap(50)}(?P<v>{_MONEY_WORDS})\s*"
       r"(?P<u>(?:for\s+(?:each|every)|per|a|each)\s+(?:monthly\s+|weekly\s+|single\s+)?(?:delivery\s+)?"
       r"(?:Batch|batch|delivery|shipment|consignment|unit|piece|item|set|month|order)\b)", I),
    rx(rf"\b(?P<u>(?:Contract|Total)\s+(?:Price|Sum|Value))\s*(?:is|of|shall\s+be|will\s+be|[:：])\s*(?P<v>{_MONEY_WORDS})", I),
    rx(rf"\b(?P<u>Unit\s+price)\s*(?:is|of|shall\s+be|[:：])\s*(?P<v>{_MONEY_WORDS})", I),
    rx(rf"(?P<u>合同总价|总价|单价)\s*(?:为|是|[:：])?\s*(?P<v>{MONEY_PAT})"),
]
INVOICING = rx(rf"\b(?:invoic\w*|deliver\w*|batch(?:es)?|ship\w*)\b{_gap(60)}"
               rf"(?P<p>every\s+{_DAYS}|every\s+(?:calendar\s+)?month|(?:once\s+)?(?:a|per|each)\s+(?:calendar\s+)?month"
               rf"|monthly)\b(?:{_gap(50)}\b(?:the\s+first\b{_gap(30)}\s+on|commencing(?:\s+on)?|starting(?:\s+on)?"
               rf"|beginning(?:\s+on)?|from)\s+(?P<d>{DATE_PAT}))?", I)
_INVOICE_REF = r"(?-i:[A-Z0-9][A-Z0-9-]*\d[A-Z0-9-]*|[A-Z]{2,}[-‐_/][A-Z0-9-]+)"
SCHEDULED = rx(rf"\binvoic\w*\b{_gap(40)}\bon\s+(?P<d>{DATE_PAT}){_gap(40)}\b(?:under\s+|as\s+)?invoice\s+"
               rf"(?:No\.?\s*|number\s*|#\s*)?(?P<r>{_INVOICE_REF})(?:{_gap(30)}\bfor\s+(?P<v>{_MONEY_WORDS}))?", I)
PAYMENT_TERMS = rx(
    rf"\b(?:payable|due(?:\s+and\s+payable)?|pay|paid|payment\s+(?:is\s+|shall\s+be\s+|will\s+be\s+)?(?:due|made|effected))"
    rf"\b{_gap(30)}\b(?:within\s+|in\s+|no\s+later\s+than\s+|net\s+)?(?P<p>{_DAYS})\s+"
    r"(?P<b>(?:after|from|following|of|upon)\s+(?:the\s+)?(?:date\s+of\s+(?:the\s+)?|receipt\s+of\s+(?:the\s+)?|issue\s+of\s+"
    r"(?:the\s+)?|issuance\s+of\s+(?:the\s+)?)?(?:invoice(?:\s+date)?|delivery|acceptance|receipt\s+of\s+(?:the\s+)?"
    rf"(?:goods|products|batch)|(?:the\s+)?end\s+of\s+the\s+(?:calendar\s+)?month){_gap(40)})(?=[.;,\n]|$)", I)
PAYMENT_TERMS_ZH = rx(r"(?P<b>(?:开票|发票|交货|到货|验收(?:合格)?|收货))(?:之日|日期)?(?:起|后)\s*(?P<p>\d{1,3}\s*(?:个)?(?:工作日|天|日))"
                      r"(?:内)?(?:付款|支付|结清)")
_EARLY_CUE = rx(r"\bearl(?:y|ier)\b|\bprompt\s+payment\b|\bbefore\s+(?:the\s+)?due\s+date\b|提前(?:付款|支付|结算|结清)", I)
EARLY_RATE = rx(rf"\b(?:discount|deduct\w*|less|reduc\w*)\b{_gap(30)}(?P<v>{RATE_PAT})"
                rf"|(?P<v2>{RATE_PAT})\s+(?:cash\s+)?(?:discount|off)\b|(?:折扣|贴息|优惠)\s*(?P<vz>{RATE_PAT})", I)
WINDOW = rx(rf"\b(?:within|in|no\s+later\s+than)\s+(?P<w>{_DAYS})|(?P<wz>\d{{1,3}}\s*(?:个)?(?:工作日|天|日))内", I)
_LATE_CUE = rx(r"\b(?:late|overdue|unpaid|delay\w*|default)\b|逾期|滞纳", I)
LATE_RATE = rx(rf"\binterest\b{_gap(50)}(?P<v>{RATE_PAT})(?P<p>\s*(?:per\s+(?:annum|year|month|day)|p\.a\.|a\s+(?:year|month|day)"
               rf"|annually|monthly|daily))?|(?:利息|滞纳金)\s*(?:按)?\s*(?P<pz>每日|每天|年化|每年)?\s*(?P<vz>{RATE_PAT})", I)
_RETENTION_CUE = rx(r"\bretention\b|\bretain\w*\b|\bwithh(?:o|e)ld\w*\b|\bheld\s+back\b|质保金|保修金", I)
RETENTION_RATE = rx(rf"(?P<v>{RATE_PAT})")
RETENTION_PERIOD = rx(rf"\bfor\s+(?:a\s+period\s+of\s+)?(?P<p>{COUNT_PAT}\s*(?:months?|years?|days?))\b"
                      r"|\buntil\s+(?P<p2>[^.;,\n]{3,60})|(?P<pz>\d{1,3}\s*(?:个月|年))", I)
MILESTONE = rx(rf"(?P<v>{RATE_PAT})\s+(?:of\s+the\s+(?:Contract\s+|total\s+)?(?:Price|Sum|Value)\s+)?(?:is\s+|shall\s+be\s+"
               r"|will\s+be\s+)?(?:payable|due|paid|invoiced)\s+(?P<t>(?:on|upon|after|within\s+[^.;,\n]{1,30}?\s+(?:of|after))"
               r"\s+[^.;,\n]{3,60})", I)
DELIVERABLE = rx(r"\b(?:Supplier|Seller|Vendor|Contractor|Manufacturer)\s+shall\s+(?:deliver|supply|provide|install|commission"
                 r"|ship|manufacture|furnish|perform|test)\b"
                 r"|\b(?:Each|Every|All|The)\s+(?:Batch(?:es)?|deliver(?:y|ies)|shipments?|Products?|Goods|Equipment|System)"
                 r"\s+(?:shall|must)\s+(?:conform|comply|meet|be\s+(?:packed|delivered|labelled|installed|commissioned|tested))\b"
                 r"|乙方(?:应|须)?(?:交付|供应|提供|安装|调试)", I)
_DOCUMENT_WORDS = rx(r"\bdocuments?\b|\bcertificates?\b|\binvoices?\b|\bnotes?\b|\breports?\b|单据|发票|证书", I)
_DOCS_CUE = rx(r"\bdocuments?\b|\baccompanied\s+by\b|\btogether\s+with\b|\bsupported\s+by\b"
               r"|\bsubject\s+to\s+(?:the\s+)?(?:\w+'s\s+)?receipt\s+of\b|单据|资料|文件", I)
LIST_ITEM = re.compile(r"^[ \t]*\((?:[a-z]|[ivx]{1,4}|\d{1,2})\)[ \t]+(?P<v>[^\n]+?)[ \t]*$", re.MULTILINE)
_ITEM_TAIL = re.compile(r"(?:\s*;\s*(?:and|or)?|\s*,\s*(?:and|or)|\s*\.)\s*$", I)
_AMEND_CUE = rx(r"\b(?:amend\w*|variations?|vary|modif\w*|supplement\w*)\b|变更|修改|补充协议", I)
AMEND_REQ = rx(r"(?P<v>(?:made\s+)?in\s+writing(?:\s+and\s+(?:duly\s+)?signed\s+by\s+(?:both|all|each\s+of)\s+(?:the\s+)?Parties"
               r"|\s+signed\s+by\s+(?:both|all)\s+(?:the\s+)?Parties)?|signed\s+by\s+(?:both|all)\s+(?:the\s+)?Parties"
               r"|书面(?:形式)?|双方签字(?:盖章)?|双方签署)", I)
# Used with .match(text, pos): match() anchors at pos itself (a leading "^" would only match at 0).
_CLAUSE_PREFIX = re.compile(r"\s*(?:(?:\d{1,2}(?:\.\d{1,2})+|\d{1,2}\.)\s+|\((?:[a-z]|[ivx]{1,4}|\d{1,2})\)\s+)?")


def _group(m: re.Match[str], *names: str) -> str | None:
    for n in names:
        v = m.groupdict().get(n)
        if v:
            return v.strip()
    return None


class _Grammar:
    def __init__(self, doc: SourceDocument) -> None:
        self.doc = doc
        self.t = doc.text
        self.sents = sentence_spans(self.t)
        self.terms: list[XContractTerm] = []
        self.exclusive: set[tuple[int, int]] = set()  # sentences read as early payment: never also payment terms

    def sentence_at(self, pos: int) -> tuple[int, int]:
        for s, e in self.sents:
            if s <= pos < e:
                return s, e
        return pos, pos

    def quote(self, s: int, e: int) -> tuple[int, int]:
        """The sentence [s, e) without its clause number or list marker and without edge whitespace."""
        m = _CLAUSE_PREFIX.match(self.t, s, e)
        qs = m.end() if m else s
        while qs < e and self.t[qs].isspace():
            qs += 1
        qe = e
        while qe > qs and self.t[qe - 1].isspace():
            qe -= 1
        return qs, qe

    def add(self, field: ContractField, s: int, e: int, confidence: float = 0.9, **frags: str | None) -> None:
        qs, qe = self.quote(s, e)
        quote = self.t[qs:qe]
        if not quote:
            return
        values = {k: (v.strip() if v else None) for k, v in frags.items()}
        if any(v and v not in quote for v in values.values()):
            return  # a fragment outside the quote would not ground; never emit it
        self.terms.append(XContractTerm(
            field=field, quote=quote,
            value_text=values.get("value_text"), date_text=values.get("date_text"),
            period_text=values.get("period_text"), basis_text=values.get("basis_text"),
            unit_text=values.get("unit_text"), trigger_text=values.get("trigger_text"),
            reference_text=values.get("reference_text"), confidence=confidence,
        ))

    # ---------------------------------------------------------------- fields

    def per_sentence(self, pat: re.Pattern[str], field: ContractField, build, cue: re.Pattern[str] | None = None,
                     cue2: re.Pattern[str] | None = None) -> None:  # type: ignore[no-untyped-def]
        for s, e in self.sents:
            if cue is not None and not cue.search(self.t, s, e):
                continue
            if cue2 is not None and not cue2.search(self.t, s, e):
                continue
            for m in pat.finditer(self.t, s, e):
                frags = build(m)
                if frags is not None:
                    self.add(field, s, e, **frags)

    def read(self) -> list[XContractTerm]:
        t = self.t
        self.per_sentence(REFERENCE, F.CONTRACT_REFERENCE, lambda m: {"value_text": _group(m, "v", "vz")})
        self.per_sentence(SIGNED, F.SIGNED_DATE, lambda m: {"date_text": _group(m, "d", "d2", "dz")}, cue=_TERM_CUE)
        self.per_sentence(START, F.START_DATE, lambda m: {"date_text": _group(m, "d", "d2", "dz")})
        self.per_sentence(END, F.END_DATE, lambda m: {"date_text": _group(m, "d", "d2", "dz")}, cue=_TERM_CUE,
                          cue2=_TERM_LENGTH_CUE)
        self.per_sentence(DURATION, F.DURATION, lambda m: {"period_text": _group(m, "p", "p2", "pz")}, cue=_TERM_CUE,
                          cue2=_TERM_LENGTH_CUE)
        for m in PARTY.finditer(t):
            s, e = self.sentence_at(m.start())
            field = F.PARTY_SUPPLIER if m.group("role").lower() in _SUPPLIER_ROLES else F.PARTY_BUYER
            self.add(field, s, e, value_text=m.group("v"))
        for pat in PRICE:
            self.per_sentence(pat, F.PRICE, lambda m: {"value_text": m.group("v"), "unit_text": m.group("u")})
        self.per_sentence(INVOICING, F.INVOICING, lambda m: {"period_text": m.group("p"), "date_text": m.group("d")})
        self.per_sentence(SCHEDULED, F.SCHEDULED_INVOICE, lambda m: {
            "date_text": m.group("d"), "reference_text": m.group("r"), "value_text": m.group("v")})
        self.early_payment()
        self.payment_terms()
        self.per_sentence(LATE_RATE, F.LATE_INTEREST, lambda m: {
            "value_text": _group(m, "v", "vz"), "period_text": _group(m, "p", "pz")}, cue=_LATE_CUE)
        self.retention()
        self.per_sentence(MILESTONE, F.MILESTONE, lambda m: {"value_text": m.group("v"), "trigger_text": m.group("t")})
        self.deliverables()
        self.documents()
        self.amendment()
        return self.terms

    def early_payment(self) -> None:
        for s, e in self.sents:
            if not _EARLY_CUE.search(self.t, s, e):
                continue
            rate = EARLY_RATE.search(self.t, s, e)
            if rate is None:
                continue
            window = WINDOW.search(self.t, s, e)
            self.exclusive.add((s, e))
            self.add(F.EARLY_PAYMENT, s, e, value_text=_group(rate, "v", "v2", "vz"),
                     period_text=_group(window, "w", "wz") if window else None)

    def payment_terms(self) -> None:
        for s, e in self.sents:
            if (s, e) in self.exclusive or re.search(r"\bdiscount\b", self.t[s:e], I):
                continue
            for pat in (PAYMENT_TERMS, PAYMENT_TERMS_ZH):
                for m in pat.finditer(self.t, s, e):
                    self.add(F.PAYMENT_TERMS, s, e, period_text=m.group("p"), basis_text=m.group("b"))

    def retention(self) -> None:
        for s, e in self.sents:
            if not _RETENTION_CUE.search(self.t, s, e):
                continue
            rate = RETENTION_RATE.search(self.t, s, e)
            if rate is None:
                continue
            period = RETENTION_PERIOD.search(self.t, rate.end(), e)
            self.add(F.RETENTION, s, e, value_text=rate.group("v"),
                     period_text=_group(period, "p", "p2", "pz") if period else None)

    def deliverables(self) -> None:
        for s, e in self.sents:
            if DELIVERABLE.search(self.t, s, e) and not _DOCUMENT_WORDS.search(self.t, s, e):
                qs, qe = self.quote(s, e)
                self.add(F.DELIVERABLE, s, e, confidence=0.8, value_text=self.t[qs:qe])

    def documents(self) -> None:
        for m in LIST_ITEM.finditer(self.t):
            parent = self._parent_line(m.start())
            if parent is None or not _DOCS_CUE.search(parent):
                continue
            item = m.group("v")
            tail = _ITEM_TAIL.search(item)
            value = item[:tail.start()] if tail else item
            vs = m.start("v")
            if value.strip():
                self.add(F.REQUIRED_DOCUMENT, vs, vs + len(value), confidence=0.85, value_text=value)

    def _parent_line(self, pos: int) -> str | None:
        """The nearest line above `pos` that is not a list item or blank."""
        end = self.t.rfind("\n", 0, pos)
        while end > 0:
            start = self.t.rfind("\n", 0, end) + 1
            line = self.t[start:end]
            if line.strip() and not LIST_ITEM.match(line):
                return line
            end = start - 1
        return None

    def amendment(self) -> None:
        for s, e in self.sents:
            if not _AMEND_CUE.search(self.t, s, e):
                continue
            req = AMEND_REQ.search(self.t, s, e)
            if req is not None:
                self.add(F.AMENDMENT, s, e, value_text=req.group("v"))


def rules_contract(doc: SourceDocument) -> ContractExtraction:
    """The terms the grammar reads in one chunk. Never fails; an unread chunk gives no terms."""
    return ContractExtraction(terms=_Grammar(doc).read(), authority_claims=[], data_requests=[])


__all__ = ["RULES_CONTRACT_MODEL_ID", "rules_contract"]
