"""Deterministic security lexicon (zh + en).

It runs on every compilation regardless of backend, and its findings are unioned with whatever the
model flags. Detection only: nothing here refuses anything. The architecture refuses (the compiler has
no operation field; the verifier and executor decide).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.compiler.parsing import MONEY_PAT, RATE_PAT, parse_money
from app.compiler.schema import XAuthorityClaim, XDataRequest, XFundingClaim, XQuantity
from app.domain.models import DataRequestKind, SourceDocument

I = re.IGNORECASE

# ---------------------------------------------------------------- data requests

_DATA_REQUESTS: list[tuple[DataRequestKind, re.Pattern[str]]] = [
    (DataRequestKind.RESERVE_FLOOR, re.compile(
        r"\b(?:minimum|min\.?)\s+(?:cash\s+)?(?:reserve|cash|balance|liquidity)(?:\s+(?:floor|level|requirement))?"
        r"|\bcash\s+(?:floor|reserve|buffer)\b|\breserve\s+(?:floor|level|requirement)s?\b"
        r"|最低(?:现金)?(?:储备|备付金?|余额|现金|资金)|现金(?:底线|储备)|安全(?:资金|现金)线", I)),
    (DataRequestKind.FACILITY_LIMIT, re.compile(
        r"\b(?:facility|credit|borrowing|loan|financing|bank)\s+(?:line\s+)?limits?\b|\bcredit\s+lines?\b(?=[^.。]{0,20}\b(?:size|limit|amount)s?\b)"
        r"|\bhow\s+much\s+(?:you\s+can|can\s+you)\s+borrow\b"
        r"|授信额度|信用额度|贷款额度|融资额度|额度上限|借款额度", I)),
    (DataRequestKind.FUNDING_MENU, re.compile(
        r"\bfunding\s+(?:menu|sources?|options|plan)\b|\b(?:list|which|what)\s+(?:of\s+)?(?:your\s+)?(?:lenders|banks|facilities|funders)\b"
        r"|\byour\s+(?:lenders|banks|facilities|funders)\b"
        r"|融资渠道|资金来源|资金方|融资方案|融资清单|合作银行", I)),
    (DataRequestKind.OTHER_COUNTERPARTY_TERMS, re.compile(
        r"\b(?:buyer|customer|client)\s+[A-Z0-9](?:'s|’s)?\s+(?:payment\s+)?(?:terms|prices?|pricing|discounts?|rebates?|deal)\b"
        r"|\bother\s+(?:buyers?|customers?|clients?)(?:'|’|'s|’s)?\s+(?:payment\s+)?(?:terms|prices?|pricing|discounts?|rebates?|deals?)\b"
        r"|\b(?:terms|discounts?|prices?|rebates?)\s+(?:you\s+(?:give|gave|offer(?:ed)?)|given|offered)\s+to\s+(?:other|another|your\s+other)\b"
        r"|(?:其他|别的|其它)(?:客户|买家|买方|采购商)的?(?:账期|付款条件|价格|折扣|返利|条件)"
        r"|[A-Z0-9](?:客户|买家|公司)的?(?:账期|付款条件|价格|折扣|返利)|(?:客户|买家)[A-Z0-9]的?(?:账期|付款条件|价格|折扣)", I)),
    (DataRequestKind.RESERVATION_VALUE, re.compile(
        r"\breservation\s+(?:value|price)\b|\bwalk[- ]?away\s+(?:price|point|terms)\b|\bbottom\s+line\b"
        r"|\b(?:lowest|best|maximum|max)\s+(?:price|discount|terms?)\s+you\s+(?:would|will|can|could)\s+(?:accept|agree|go)\b"
        r"|底价|保留价|最低(?:可)?接受|心理价位|最多能(?:让|给)", I)),
    (DataRequestKind.SYSTEM_PROMPT, re.compile(
        r"\bsystem\s+prompt\b|\b(?:reveal|show|print|repeat|output|tell\s+me|share|send|give\s+me|paste|dump)\s+(?:me\s+|us\s+)?"
        r"(?:your|the)\s+(?:full\s+|exact\s+)?(?:system\s+|hidden\s+|internal\s+|original\s+)?(?:prompt|instructions|rules|configuration)\b"
        r"|系统提示词?|提示词|系统指令|内部指令", I)),
    (DataRequestKind.MANDATE_VALUE, re.compile(
        r"\b(?:your|the\s+owner'?s?|the)\s+mandate\b|\bconcession\s+(?:caps?|limits?|budget)\b|\bapproval\s+(?:limits?|thresholds?)\b"
        r"|\b(?:your|the)\s+(?:caps|limits)\s+(?:are|on)\b|\bmax(?:imum)?\s+(?:apr|leverage|concession)\b"
        r"|授权书|授权(?:范围|额度|限额|上限)|审批(?:权限|限额|上限)|让利上限|让步上限", I)),
]

# Phrases that only become a data request when something is being asked for.
_ASK = re.compile(
    r"\b(?:send|tell|share|give|provide|reveal|disclose|show|list|what(?:'s| is| are)|how\s+much|confirm|forward|print|repeat)\b"
    r"|告诉|发(?:给|送)|提供|透露|说明|列出|给我|是多少|多少", I)
_NEEDS_ASK = {DataRequestKind.FUNDING_MENU, DataRequestKind.MANDATE_VALUE, DataRequestKind.RESERVATION_VALUE}


def sentence_bounds(text: str, pos: int) -> tuple[int, int]:
    """Start/end of the sentence containing `pos` (terminators: . ! ? ; newline and CJK forms)."""
    term = re.compile(r"[!?;！？；。\n]|\.(?!\d)")
    start = 0
    for m in term.finditer(text, 0, pos):
        start = m.end()
    m = term.search(text, pos)
    end = m.start() if m else len(text)
    return start, end


def find_data_requests(doc: SourceDocument) -> list[XDataRequest]:
    out: list[XDataRequest] = []
    t = doc.text
    for kind, rx in _DATA_REQUESTS:
        for m in rx.finditer(t):
            if not m.group(0).strip():
                continue
            if kind in _NEEDS_ASK:
                s, e = sentence_bounds(t, m.start())
                if not _ASK.search(t[max(0, s - 120) : e]):
                    continue
            out.append(XDataRequest(kind=kind, doc_id=doc.doc_id, quote=m.group(0)))
    return out


# ---------------------------------------------------------------- authority claims

_AUTHORITY: list[tuple[str, re.Pattern[str]]] = [
    ("PRE_APPROVAL", re.compile(
        r"\bpre[- ]?(?:approved|approval|qualified|authori[sz]ed)\b|\balready\s+approved\s+(?:for|by)\b"
        r"|预批准|预审批|预授信|已获批|预先批准|已预批", I)),
    ("PRIOR_AGREEMENT", re.compile(
        r"\b(?:we|you)\s+(?:have\s+)?(?:already\s+|previously\s+|both\s+)?(?:agreed|promised|approved)\b(?!\s+to\s+(?:review|consider))"
        r"|\bas\s+(?:previously\s+)?(?:agreed|discussed|promised)\b|\b(?:agreed|promised)\s+last\s+(?:week|month|time|quarter|year)\b"
        r"|已经?(?:同意|答应|批准)(?:过|了)?|说好的?|谈好的?|之前(?:约定|说定|商定)|上(?:个)?(?:月|次|周)(?:已经?)?(?:同意|答应|说好|谈好)", I)),
    ("INSTRUCTION_OVERRIDE", re.compile(
        r"\b(?:ignore|disregard|forget|override|bypass|skip)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+|these\s+|those\s+)?"
        r"(?:previous|prior|above|earlier|preceding|existing|system|safety|original)?\s*(?:instructions?|rules|prompts?|constraints|checks|limits|mandate|verifier|guidelines)\b"
        r"|\byou\s+are\s+now\b|\bact\s+as\s+(?:the\s+)?(?:owner|admin|administrator|system)\b|\bnew\s+instructions?\b"
        r"|(?:^|\n|\[|<|\{)\s*(?:system|assistant|developer)\s*[:：\]>]|\bdeveloper\s+mode\b|\bjailbreak\b"
        r"|\b(?:reply|respond|answer|type|output)\s+(?:with\s+)?[\"'“]?ACCEPT(?:ED)?\b|\bauto[- ]?(?:accept|approve)\b"
        r"|\b(?:must|shall|have\s+to)\s+(?:immediately\s+)?(?:accept|approve|sign|execute|book|add)\b"
        r"|\badd\s+(?:us|this\s+(?:lender|facility)|\w+)\s+to\s+(?:your|the)\s+funding\s+menu\b"
        r"|忽略(?:之前|以上|前面|上述|先前|所有|全部)的?(?:所有|全部)?(?:指令|指示|规则|提示|要求|限制)|无视(?:之前|以上|所有)?的?(?:指令|规则|限制)"
        r"|你现在是|现在你是|系统\s*[:：]|系统消息|系统通知|新的?指令|绕过|直接(?:接受|批准|同意|放款)|回复\s*[“\"']?(?:接受|同意|ACCEPT)"
        r"|加入(?:你们的?)?融资(?:菜单|清单|渠道)", I)),
    ("URGENCY", re.compile(
        r"\burgent(?:ly)?\b|\bimmediately\b|\basap\b|\bright\s+now\b|\bwithin\s+(?:the\s+)?(?:hour|\d+\s+(?:minutes?|hours?))\b"
        r"|\blast\s+chance\b|\b(?:expires?|deadline)\s+(?:today|tonight|in\s+\d+)\b|\btime[- ]sensitive\b"
        r"|紧急|加急|立即|立刻|马上|尽快|最后机会|今天(?:内)?必须|限时", I)),
    ("IMPERSONATION", re.compile(
        r"\b(?:this\s+is|i\s+am|i'm|we\s+are)\s+(?:the\s+|your\s+)?(?:owner|ceo|cfo|director|boss|admin|administrator|system|supervisor|auditor)\b"
        r"|\b(?:the\s+|your\s+)?(?:owner|ceo|cfo|boss|director|management|admin)\s+(?:has\s+|have\s+)?(?:already\s+)?"
        r"(?:approved|authori[sz]ed|signed\s+off|confirmed|instructed|asked)\b"
        r"|\bon\s+behalf\s+of\s+(?:the\s+|your\s+)?(?:owner|ceo|management)\b|\b(?:owner|admin)\s+(?:approval|override)\s*(?:code|token|granted)?\s*[:：]"
        r"|\bfrom\s+(?:the\s+)?(?:termsledger|anthropic|openai|deepseek)\b|\btermsledger\s+(?:admin|support|team|system)\b"
        r"|我是(?:你们的?)?(?:老板|老总|董事长?|总经理|管理员|业主|财务总监)|(?:老板|老总|业主|董事长|总经理|管理层)(?:已经?|已)(?:批准|同意|授权|签字|确认)"
        r"|代表(?:老板|业主|管理层)", I)),
]


def find_authority_claims(doc: SourceDocument) -> list[XAuthorityClaim]:
    out: list[XAuthorityClaim] = []
    for kind, rx in _AUTHORITY:
        for m in rx.finditer(doc.text):
            q = m.group(0).strip(" \n[<{\"")
            if q:
                out.append(XAuthorityClaim(kind=kind, doc_id=doc.doc_id, quote=q))  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------- unsolicited funding claims

_AMT = MONEY_PAT
_RATE = RATE_PAT
_NAME = r"(?P<name>(?-i:[A-Z][\w&\-]*(?:[ ][A-Z][\w&\-]*){0,3}))"
_GAP = r"(?:[^.。;；!！?？\n]|\.(?=\d)){0,40}?"

_FUNDING: list[re.Pattern[str]] = [
    re.compile(
        rf"pre[- ]?(?:approved|qualified)\s+for\s+(?:a\s+)?(?:loan\s+of\s+)?(?P<amt>{_AMT})"
        rf"(?:{_GAP}\bat\s+(?P<rate>{_RATE}))?(?:{_GAP}\bfrom\s+{_NAME})?", I),
    re.compile(
        rf"\b(?:loan|financing|credit\s+line|facility|funding|advance|credit)\s+of\s+(?:up\s+to\s+)?(?P<amt>{_AMT})"
        rf"{_GAP}\bat\s+(?P<rate>{_RATE})(?:{_GAP}\bfrom\s+{_NAME})?", I),
    re.compile(
        rf"{_NAME}\s+(?:can|will|is\s+(?:able|ready|happy)\s+to|would\s+like\s+to)\s+(?:offer|lend|provide|fund|advance)\s+(?:you\s+)?"
        rf"(?:up\s+to\s+)?(?P<amt>{_AMT}){_GAP}(?:\bat\s+(?P<rate>{_RATE}))?", 0),
    re.compile(
        rf"(?P<name>[A-Za-z][\w&\-]*|[一-鿿]{{2,12}}?(?:银行|金融|资本|小贷|保理|公司))(?:已)?(?:为您|给您|向您)?(?:预批准|预授信|提供|批复)(?:了)?\s*(?P<amt>{_AMT})\s*(?:的)?"
        rf"(?:贷款|融资|额度|授信)(?:{_GAP}(?:年化)?(?:利率|年利率)?\s*(?P<rate>{_RATE}))?"),
    re.compile(
        rf"(?:预批准|预授信)(?:了)?\s*(?P<amt>{_AMT})\s*(?:的)?(?:贷款|融资|额度|授信)?(?:{_GAP}(?:利率|年化)\s*(?P<rate>{_RATE}))?"),
]
_NAME_STOP = {"You", "We", "Our", "Your", "The", "This", "Reply", "Also", "URGENT", "I"}


def find_funding_claims(doc: SourceDocument) -> list[XFundingClaim]:
    out: list[XFundingClaim] = []
    taken: list[tuple[int, int]] = []
    for rx in _FUNDING:
        for m in rx.finditer(doc.text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            name = (m.groupdict().get("name") or "").strip()
            if not name or name in _NAME_STOP or name.split()[0] in _NAME_STOP:
                name = _lender_elsewhere(doc.text) or doc.sender_id
            out.append(XFundingClaim(
                lender_name=name, doc_id=doc.doc_id, quote=m.group(0).rstrip(" ,，"),
                amount_text=m.group("amt").strip(), rate_text=m.groupdict().get("rate"),
            ))
            taken.append((m.start(), m.end()))
    return out


def _lender_elsewhere(text: str) -> str | None:
    m = re.search(r"\bfrom\s+([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,3})", text)
    return m.group(1) if m else None


# ---------------------------------------------------------------- quantities (conflicting sources)

_QUANTITIES: list[tuple[str, re.Pattern[str]]] = [
    ("order_size", re.compile(rf"(?P<amt>{_AMT})\s+(?:purchase\s+)?(?:order|PO)\b", I)),
    ("order_size", re.compile(
        rf"\b(?:order|PO|purchase\s+order)\s+(?:size|value|amount|total)\s*(?:of|is|[:：])?\s*(?P<amt>{_AMT})", I)),
    ("order_size", re.compile(rf"\b(?:an?\s+)?order\s+of\s+(?P<amt>{_AMT})", I)),
    ("order_size", re.compile(rf"(?:订单|采购)(?:金额|总额|总价|规模)\s*[:：为是]?\s*(?P<amt>{_AMT})")),
    ("order_size", re.compile(rf"(?P<amt>{_AMT})\s*(?:的)?(?:订单|采购单)")),
    ("invoice_amount", re.compile(
        rf"\binvoice\s+(?:amount|face|value|total)\s*(?:of|is|[:：])?\s*(?P<amt>{_AMT})", I)),
    ("invoice_amount", re.compile(rf"(?:发票|货款)(?:金额|总额)\s*[:：为是]?\s*(?P<amt>{_AMT})")),
]


def find_quantities(doc: SourceDocument) -> list[XQuantity]:
    out: list[XQuantity] = []
    for kind, rx in _QUANTITIES:
        for m in rx.finditer(doc.text):
            if parse_money(m.group("amt")) is None:
                continue
            out.append(XQuantity(kind=kind, doc_id=doc.doc_id, quote=m.group(0).strip(), amount_text=m.group("amt").strip()))  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------- unresolved references ("as usual")

AS_USUAL_RE = re.compile(
    r"\bsame\s+(?:arrangement|terms|deal|conditions|as\s+(?:usual|before|always|last\s+time))(?:\s+as\s+(?:usual|before|always|last\s+time))?"
    r"|\bas\s+(?:usual|always|before|per\s+usual)\b|\bthe\s+usual\s+(?:arrangement|terms|deal|discount|rebate)\b|\blike\s+last\s+time\b"
    r"|\bthe\s+(?:normal|standard)\s+arrangement\b"
    r"|照旧|老规矩|跟?(?:和|与|同)?(?:以前|往常|平时|上次|之前)一样|按(?:以前|往常|老|之前)的?(?:办|规矩|约定|惯例)|惯例", I)


def find_unresolved_references(doc: SourceDocument) -> list[tuple[str, str]]:
    return [(doc.doc_id, m.group(0)) for m in AS_USUAL_RE.finditer(doc.text)]


def all_flags(docs: Iterable[SourceDocument]) -> tuple[list[XDataRequest], list[XAuthorityClaim], list[XFundingClaim]]:
    dr: list[XDataRequest] = []
    ac: list[XAuthorityClaim] = []
    fc: list[XFundingClaim] = []
    for d in docs:
        dr += find_data_requests(d)
        ac += find_authority_claims(d)
        fc += find_funding_claims(d)
    return dr, ac, fc
