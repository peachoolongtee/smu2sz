"""Deterministic security lexicon (zh + en).

It runs on every compilation regardless of backend, and its findings are unioned with whatever the
model flags. Detection only: nothing here refuses anything. The architecture refuses (the compiler has
no operation field; the verifier and executor decide).

Data requests, authority claims and funding claims are matched on a folded copy of the text
(app.compiler.folding: NFKC, no zero-width or bidi characters, Latin for Cyrillic/Greek lookalikes), and
every quote is mapped back to the exact substring of the ORIGINAL document.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.compiler.folding import Folded, fold
from app.compiler.parsing import MONEY_PAT, RATE_PAT, parse_money, rx
from app.compiler.schema import XAuthorityClaim, XDataRequest, XFundingClaim, XQuantity
from app.domain.models import DataRequestKind, SourceDocument

I = re.IGNORECASE

# ---------------------------------------------------------------- data requests

_DATA_REQUESTS: list[tuple[DataRequestKind, re.Pattern[str]]] = [
    (DataRequestKind.RESERVE_FLOOR, rx(
        r"\b(?:minimum|min\.?)\s+(?:cash\s+)?(?:reserve|cash|balance|liquidity)(?:\s+(?:floor|level|requirement))?"
        r"|\bcash\s+(?:floor|reserve|buffer)\b|\breserve\s+(?:floor|level|requirement)s?\b"
        r"|最低(?:现金)?(?:储备|备付金?|余额|现金|资金)|现金(?:底线|储备)|安全(?:资金|现金)线", I)),
    (DataRequestKind.FACILITY_LIMIT, rx(
        r"\b(?:facility|credit|borrowing|loan|financing|bank)\s+(?:line\s+)?limits?\b|\bcredit\s+lines?\b(?=[^.。]{0,20}\b(?:size|limit|amount)s?\b)"
        r"|\bhow\s+much\s+(?:you\s+can|can\s+you)\s+borrow\b"
        r"|授信额度|信用额度|贷款额度|融资额度|额度上限|借款额度", I)),
    (DataRequestKind.FUNDING_MENU, rx(
        r"\bfunding\s+(?:menu|sources?|options|plan)\b|\b(?:list|which|what)\s+(?:of\s+)?(?:your\s+)?(?:lenders|banks|facilities|funders)\b"
        r"|\byour\s+(?:other\s+|existing\s+)?(?:lenders|banks|facilities|funders)\b"
        r"|融资渠道|资金来源|资金方|融资方案|融资清单|合作银行", I)),
    (DataRequestKind.OTHER_COUNTERPARTY_TERMS, rx(
        r"\b(?:buyer|customer|client)\s+[A-Z0-9](?:'s|’s)?\s+(?:payment\s+)?(?:terms|prices?|pricing|discounts?|rebates?|deal)\b"
        r"|\bother\s+(?:buyers?|customers?|clients?)(?:'|’|'s|’s)?\s+(?:payment\s+)?(?:terms|prices?|pricing|discounts?|rebates?|deals?)\b"
        r"|\b(?:terms|discounts?|prices?|rebates?)\s+(?:you\s+(?:give|gave|offer(?:ed)?)|given|offered)\s+to\s+(?:other|another|your\s+other)\b"
        r"|(?:其他|别的|其它)(?:客户|买家|买方|采购商)的?(?:账期|付款条件|价格|折扣|返利|条件)"
        r"|[A-Z0-9](?:客户|买家|公司)的?(?:账期|付款条件|价格|折扣|返利)|(?:客户|买家)[A-Z0-9]的?(?:账期|付款条件|价格|折扣)", I)),
    (DataRequestKind.RESERVATION_VALUE, rx(
        r"\breservation\s+(?:value|price)\b|\bwalk[- ]?away\s+(?:price|point|terms)\b|\bbottom\s+line\b"
        r"|\b(?:lowest|best|maximum|max)\s+(?:price|discount|terms?)\s+you\s+(?:would|will|can|could)\s+(?:accept|agree|go)\b"
        r"|底价|保留价|最低(?:可)?接受|心理价位|最多能(?:让|给)", I)),
    (DataRequestKind.SYSTEM_PROMPT, rx(
        r"\bsystem\s+prompt\b|\b(?:reveal|show|print|repeat|output|tell\s+me|share|send|give\s+me|paste|dump)\s+(?:me\s+|us\s+)?"
        r"(?:your|the)\s+(?:full\s+|exact\s+)?(?:system\s+|hidden\s+|internal\s+|original\s+)?(?:prompt|instructions|rules|configuration)\b"
        r"|系统提示词?|提示词|系统指令|内部指令", I)),
    (DataRequestKind.MANDATE_VALUE, rx(
        r"\b(?:your|the\s+owner'?s?|the)\s+mandate\b|\bconcession\s+(?:caps?|limits?|budget)\b|\bapproval\s+(?:limits?|thresholds?)\b"
        r"|\b(?:your|the)\s+(?:caps|limits)\s+(?:are|on)\b|\bmax(?:imum)?\s+(?:apr|leverage|concession)\b"
        r"|授权书|授权(?:范围|额度|限额|上限)|审批(?:权限|限额|上限)|让利上限|让步上限", I)),
    # prompt / secret extraction: "repeat everything above", "print your instructions", "reserve override code"
    (DataRequestKind.SYSTEM_PROMPT, rx(
        r"\b(?:repeat|print|output|echo|recite|copy|reproduce)\s+(?:back\s+)?(?:everything|all(?:\s+(?:of\s+)?the\s+text)?|the\s+text|whatever|what(?:'s|\s+is|\s+was))"
        r"\s+(?:written\s+|said\s+)?(?:above|before\s+this|preceding|earlier|so\s+far)\b"
        r"|\b(?:print|show|reveal|output|repeat|tell\s+me|share|send|give\s+me|paste|dump|list)\s+(?:me\s+|us\s+)?(?:your|the|all|any)\s+"
        r"(?:\w+\s+){0,2}?(?:instructions|guidelines|internal\s+markers?|hidden\s+(?:codes?|markers?|text))\b"
        r"|\binternal\s+markers?\b|\b(?:reserve|owner|admin|master|emergency|system)\s+override\s+(?:code|token|key|password|pin)s?\b"
        r"|重复(?:一下|一遍)?(?:上面|以上|前面|之前)(?:的|所有)?(?:内容|文字|指令|话)?|(?:打印|输出|显示|列出|复述)(?:一下)?(?:你的|你们的|所有的?)?(?:指令|提示|规则|设定)"
        r"|(?:储备|备付金?|管理员|超级)?(?:覆盖|解锁|授权|超控)(?:码|密码|口令)", I)),
    (DataRequestKind.RESERVE_FLOOR, rx(
        r"\bemergency\s+(?:cash\s+)?reserves?(?:\s+(?:amount|level|balance))?\b|\breserve\s+amount\b|应急(?:储备|备付金?|资金)", I)),
]

# Patterns that only become a data request when something is being asked for (cross-buyer questions).
_DATA_REQUESTS_ASKED: list[tuple[DataRequestKind, re.Pattern[str]]] = [
    (DataRequestKind.OTHER_COUNTERPARTY_TERMS, rx(
        # "your other customers", "the terms your other buyers get", 其他客户
        r"\b(?:your\s+)?other\s+(?:customers|buyers|clients|accounts)\b|(?:其他|别的|其它)(?:客户|买家|买方|采购商)"
        # "What payment terms and discounts does Foshan Home Retail get from you?"
        r"|\b(?:terms|discounts?|prices?|pricing|rebates?|deal|conditions)\b(?:[^.?!;。？！；\n]{0,40}?)\b(?:does|do|did|will)\s+"
        r"(?-i:(?!you\b|we\b|I\b|they\b)[A-Z][\w&'’-]*(?:\s+(?:[A-Z][\w&'’-]*|&|and|of))*)\s+(?:get|gets|receive|have|pay|enjoy)\b"
        # "the terms you give Foshan Home Retail", "the discount you offered Guangzhou Trading"
        r"|\b(?:terms|discounts?|prices?|pricing|rebates?|deal)\s+(?:that\s+)?you\s+(?:give|gave|offer|offered|grant|granted)\s+(?:to\s+)?"
        r"(?-i:(?!us\b|me\b)[A-Z][\w&'’-]*(?:\s+[A-Z][\w&'’-]*)*)"
        # "the same terms as Foshan Home Retail"
        r"|\bsame\s+(?:payment\s+)?(?:terms|discounts?|prices?|pricing|rebates?|deal)\s+as\s+(?-i:(?!you\b|before\b|usual\b)[A-Z][\w&'’-]*(?:\s+[A-Z][\w&'’-]*)+)"
        # 告诉我佛山家居零售的账期和折扣
        r"|(?:告诉|透露|说说|讲讲|发给|提供|问问|了解)(?:一下)?(?:我们|我)?\s*(?![们我你您贵咱本自他她它])"
        r"[一-鿿A-Za-z]{2,14}?的(?:账期|付款条件|价格|折扣|返利|返点|优惠|条件)", I)),
]

# Phrases that only become a data request when something is being asked for.
_ASK = rx(
    r"\b(?:send|tell|share|give|provide|reveal|disclose|show|list|what(?:'s| is| are)|how\s+much|confirm|forward|print|repeat)\b"
    r"|告诉|发(?:给|送)|提供|透露|说明|列出|给我|是多少|多少", I)
_NEEDS_ASK = {DataRequestKind.FUNDING_MENU, DataRequestKind.MANDATE_VALUE, DataRequestKind.RESERVATION_VALUE}


def sentence_bounds(text: str, pos: int) -> tuple[int, int]:
    """Start/end of the sentence containing `pos` (terminators: . ! ? ; newline and CJK forms)."""
    term = rx(r"[!?;！？；。\n]|\.(?!\d)")
    start = 0
    for m in term.finditer(text, 0, pos):
        start = m.end()
    m = term.search(text, pos)
    end = m.start() if m else len(text)
    return start, end


# Clause boundaries inside a sentence: a comma that is not a thousands separator, a semicolon or colon, a
# list comma, or a coordinating conjunction ("and", "but", 而且, 但是 ...).
_CLAUSE_BOUNDARY = rx(r",(?!\d{3})|[，;；:：、]|\s(?:and|but|while|whereas|plus)\s|而且|并且|但是?|同时|另外", I)


def clauses(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """The clauses of text[start:end] as (start, end) pairs, in order."""
    out: list[tuple[int, int]] = []
    pos = start
    for m in _CLAUSE_BOUNDARY.finditer(text, start, end):
        out.append((pos, m.start()))
        pos = m.end()
    out.append((pos, end))
    return out


def _quote(f: Folded, s: int, e: int, strip: str = " \n") -> str:
    """The ORIGINAL substring behind the folded match [s, e), with `strip` characters trimmed."""
    frag = f.text[s:e]
    lead = len(frag) - len(frag.lstrip(strip))
    trail = len(frag) - len(frag.rstrip(strip))
    if lead + trail >= len(frag):
        return ""
    return f.orig(s + lead, e - trail)


# Stricter: a question, or a verb that asks for disclosure ("give us the same terms as ..." is not one).
_DISCLOSE = rx(
    r"\b(?:tell|share|send|show|reveal|disclose|list|forward|provide|what|which|how\s+much|how\s+long)\b"
    r"|告诉|透露|发(?:给|送)|提供|说说|讲讲|列出|是多少|多少|哪些|什么", I)


def _asked(t: str, pos: int, pat: re.Pattern[str] = _ASK) -> bool:
    s, e = sentence_bounds(t, pos)
    if t[e : e + 1] in ("?", "？"):
        return True
    return bool(pat.search(t[max(0, s - 120) : e]))


def find_data_requests(doc: SourceDocument) -> list[XDataRequest]:
    out: list[XDataRequest] = []
    f = fold(doc.text)
    t = f.text
    rules = [(k, pat, _ASK if k in _NEEDS_ASK else None) for k, pat in _DATA_REQUESTS]
    rules += [(k, pat, _DISCLOSE) for k, pat in _DATA_REQUESTS_ASKED]
    for kind, pat, ask in rules:
        for m in pat.finditer(t):
            if not m.group(0).strip():
                continue
            if ask is not None and not _asked(t, m.start(), ask):
                continue
            q = _quote(f, m.start(), m.end())
            if q:
                out.append(XDataRequest(kind=kind, doc_id=doc.doc_id, quote=q))
    return out


# ---------------------------------------------------------------- authority claims

_AUTHORITY: list[tuple[str, re.Pattern[str]]] = [
    ("PRE_APPROVAL", rx(
        r"\bpre[- ]?(?:approved|approval|qualified|authori[sz]ed)\b|\balready\s+approved\s+(?:for|by)\b"
        r"|预批准|预审批|预授信|已获批|预先批准|已预批", I)),
    ("PRIOR_AGREEMENT", rx(
        r"\b(?:we|you)\s+(?:have\s+)?(?:already\s+|previously\s+|both\s+)?(?:agreed|promised|approved)\b(?!\s+to\s+(?:review|consider))"
        r"|\bas\s+(?:previously\s+)?(?:agreed|discussed|promised)\b|\b(?:agreed|promised)\s+last\s+(?:week|month|time|quarter|year)\b"
        r"|\b(?:owner|ceo|cfo|director|boss|management)\s+(?:has\s+|have\s+)?(?:already\s+)?(?:approved|agreed(?:\s+to)?|signed\s+off\s+on)\b"
        r"|已经?(?:同意|答应|批准)(?:过|了)?|说好的?|谈好的?|之前(?:约定|说定|商定)|上(?:个)?(?:月|次|周)(?:已经?)?(?:同意|答应|说好|谈好)", I)),
    ("INSTRUCTION_OVERRIDE", rx(
        r"\b(?:ignore|disregard|forget|override|bypass|skip)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+|these\s+|those\s+)?"
        r"(?:previous|prior|above|earlier|preceding|existing|system|safety|original)?\s*(?:instructions?|rules?|prompts?|constraints?|checks?|limits?|mandate|verifier|guidelines?|policy|policies)\b"
        r"|\byou\s+are\s+now\b|\bact\s+as\s+(?:the\s+)?(?:owner|admin|administrator|system)\b|\bnew\s+instructions?\b"
        r"|(?:^|\n|\[|<|\{)\s*(?:system|assistant|developer)\s*[:：\]>]|\bdeveloper\s+mode\b|\bjailbreak\b"
        r"|\b(?:reply|respond|answer|type|output)\s+(?:with\s+)?[\"'“]?ACCEPT(?:ED)?\b|\bauto[- ]?(?:accept|approve)\b"
        r"|\b(?:must|shall|have\s+to)\s+(?:immediately\s+)?(?:accept|approve|sign|execute|book|add)\b"
        r"|\badd\s+(?:us|this\s+(?:lender|facility)|\w+)\s+to\s+(?:your|the)\s+funding\s+menu\b"
        r"|忽略(?:之前|以上|前面|上述|先前|所有|全部)的?(?:所有|全部)?(?:指令|指示|规则|提示|要求|限制)|无视(?:之前|以上|所有)?的?(?:指令|规则|限制)"
        r"|你现在是|现在你是|系统\s*[:：]|系统消息|系统通知|新的?指令|绕过|直接(?:接受|批准|同意|放款)|回复\s*[“\"']?(?:接受|同意|ACCEPT)"
        r"|加入(?:你们的?)?融资(?:菜单|清单|渠道)"
        # JSON role messages: {"role": "system", ...}
        r"|[\"'“”]role[\"'“”]\s*:\s*[\"'“”](?:system|assistant|developer|tool)[\"'“”]"
        # role-play jailbreaks
        r"|\bpretend\s+(?:that\s+)?(?:you\s+are|you'?re|to\s+be)\b|\brole[- ]?play\b|\blet'?s\s+play\s+a\s+game\b"
        r"|\b(?:act|behave|respond|answer|speak)\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:the\s+|our\s+|your\s+)?(?:owner|boss|admin|administrator|system|developer|ceo|cfo|supervisor)\b"
        r"|\b(?:you\s+are|you'?re)\s+(?:now\s+)?(?:an?\s+)?(?:\w+\s+)?(?:assistant|ai|bot|agent)\s+(?:with|that\s+has|who\s+has)\s+no\s+(?:mandate|rules|restrictions|limits|filters)\b"
        r"|\byou\s+are\s+\w*bot\b|\bas\s+\w*bot\b"
        r"|扮演|假装(?:你是|自己是|成)|假设你是|角色扮演", I)),
    ("URGENCY", rx(
        r"\burgent(?:ly)?\b|\bimmediately\b|\basap\b|\bright\s+now\b|\bwithin\s+(?:the\s+)?(?:hour|\d+\s+(?:minutes?|hours?))\b"
        r"|\blast\s+chance\b|\b(?:expires?|deadline)\s+(?:today|tonight|in\s+\d+)\b|\btime[- ]sensitive\b"
        r"|紧急|加急|立即|立刻|马上|尽快|最后机会|今天(?:内)?必须|限时", I)),
    ("IMPERSONATION", rx(
        r"\b(?:this\s+is|i\s+am|i'm|we\s+are)\s+(?:the\s+|your\s+)?(?:owner|ceo|cfo|director|boss|admin|administrator|system|supervisor|auditor)\b"
        r"|\b(?:the\s+|your\s+)?(?:owner|ceo|cfo|boss|director|management|admin)\s+(?:has\s+|have\s+)?(?:already\s+)?"
        r"(?:approved|authori[sz]ed|signed\s+off|confirmed|instructed|asked)\b"
        r"|\bon\s+behalf\s+of\s+(?:the\s+|your\s+)?(?:owner|ceo|management)\b|\b(?:owner|admin)\s+(?:approval|override)\s*(?:code|token|granted)?\s*[:：]"
        r"|\bfrom\s+(?:the\s+)?(?:termsledger|anthropic|openai|deepseek)\b|\btermsledger\s+(?:admin|support|team|system)\b"
        r"|我是(?:你们的?)?(?:老板|老总|董事长?|总经理|管理员|业主|财务总监)|(?:老板|老总|业主|董事长|总经理|管理层)(?:已经?|已)(?:批准|同意|授权|签字|确认)"
        r"|代表(?:老板|业主|管理层)"
        # "the owner told me on WeChat", "your boss said on the phone", 老板说过 / 老板已在微信上同意
        r"|\b(?:your|the)\s+(?:owner|boss|ceo|cfo|director|md|manager|management|gm|general\s+manager)\s+(?:already\s+|personally\s+)?"
        r"(?:told|said\s+(?:to|that)|asked|instructed|promised|confirmed\s+(?:to|with)|agreed\s+with|okayed|ok'?d)\s+(?:me|us|our\s+\w+)\b"
        r"|\b(?:owner|boss|ceo|cfo|director|manager)\b[^.?!;。？！；\n]{0,40}?\b(?:on|via|over|by|through)\s+(?:wechat|weixin|whatsapp|the\s+phone|phone|a\s+call|text|sms|voice\s+message)\b"
        r"|(?:老板|老总|业主|董事长|总经理|你们经理|财务总监)(?:之前|已经?|亲自)?(?:说过|说了|说好|跟我(?:们)?说|告诉(?:过)?我(?:们)?|答应过?|口头(?:同意|答应|批准))"
        r"|(?:老板|老总|业主|董事长|总经理)[^，。,.；;！!？?]{0,8}(?:微信|电话|短信|语音|口头)[^，。,.；;！!？?]{0,6}(?:同意|答应|批准|说|确认|授权)"
        # change-of-payee notices: a classic impersonation fraud
        r"|\b(?:new|updated|changed|different)\s+(?:bank\s+|receiving\s+|payment\s+|beneficiary\s+)*(?:account|bank\s+details|payment\s+details|remittance\s+details|beneficiary)\b"
        r"|\b(?:changed|updated|switched|moved)\s+(?:our|the|my)\s+(?:bank\s+|receiving\s+|payment\s+)*(?:account|bank(?:ing)?\s+details|bank|payment\s+details)\b"
        r"|\b(?:remit|pay|transfer|wire|send\s+(?:the\s+)?(?:payment|funds|money))\s+(?:\w+\s+){0,4}?(?:to|into)\s+(?:our|this|the|a)\s+new\s+(?:bank\s+)?account\b"
        r"|(?:请)?(?:汇款|付款|转账|打款|汇)(?:至|到)(?:我们的?|我司)?新(?:的)?(?:银行)?(?:账户|账号|帐户|帐号)|新(?:的)?(?:收款|银行)?(?:账户|账号|帐户|帐号)"
        r"|(?:更换|变更|更改|换)(?:了)?(?:收款|银行)?(?:账户|账号|帐户|帐号)|(?:收款)?(?:账户|账号|帐户|帐号)(?:已)?(?:变更|更换|更改)", I)),
]


def find_authority_claims(doc: SourceDocument) -> list[XAuthorityClaim]:
    out: list[XAuthorityClaim] = []
    f = fold(doc.text)
    for kind, pat in _AUTHORITY:
        for m in pat.finditer(f.text):
            q = _quote(f, m.start(), m.end(), " \n[<{\"")
            if q:
                out.append(XAuthorityClaim(kind=kind, doc_id=doc.doc_id, quote=q))  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------- unsolicited funding claims

_AMT = MONEY_PAT
_RATE = RATE_PAT
_NAME = r"(?P<name>(?-i:[A-Z][\w&\-]*(?:[ ][A-Z][\w&\-]*){0,3}))"
_GAP = r"(?:[^.。;；!！?？\n]|\.(?=\d)){0,40}?"

_FUNDING: list[re.Pattern[str]] = [
    rx(
        rf"pre[- ]?(?:approved|qualified)\s+for\s+(?:a\s+)?(?:loan\s+of\s+)?(?P<amt>{_AMT})"
        rf"(?:{_GAP}\bat\s+(?P<rate>{_RATE}))?(?:{_GAP}\bfrom\s+{_NAME})?", I),
    rx(
        rf"\b(?:loan|financing|credit\s+line|facility|funding|advance|credit)\s+of\s+(?:up\s+to\s+)?(?P<amt>{_AMT})"
        rf"{_GAP}\bat\s+(?P<rate>{_RATE})(?:{_GAP}\bfrom\s+{_NAME})?", I),
    rx(
        rf"(?P<amt>{_AMT})\s+(?:[\w-]+\s+){{0,2}}(?:loan|credit\s+line|facility|financing|advance)\b{_GAP}\bat\s+(?P<rate>{_RATE})"
        rf"(?:{_GAP}\bfrom\s+{_NAME})?", I),
    rx(
        rf"{_NAME}\s+(?:can|will|is\s+(?:able|ready|happy)\s+to|would\s+like\s+to)\s+(?:offer|lend|provide|fund|advance)\s+(?:you\s+)?"
        rf"(?:up\s+to\s+)?(?P<amt>{_AMT}){_GAP}(?:\bat\s+(?P<rate>{_RATE}))?", 0),
    rx(
        rf"(?P<name>[A-Za-z][\w&\-]*|[一-鿿]{{2,12}}?(?:银行|金融|资本|小贷|保理|公司))[，,\s]*(?:已)?(?:为您|给您|向您)?(?:预批准|预授信|提供|批复)(?:了)?\s*(?P<amt>{_AMT})\s*(?:的)?"
        rf"(?:贷款|融资|额度|授信)(?:{_GAP}(?:年化)?(?:利率|年利率)?\s*(?P<rate>{_RATE}))?"),
    rx(
        rf"(?:预批准|预授信)(?:了)?\s*(?P<amt>{_AMT})\s*(?:的)?(?:贷款|融资|额度|授信)?(?:{_GAP}(?:利率|年化)\s*(?P<rate>{_RATE}))?"),
]
_NAME_STOP = {"You", "We", "Our", "Your", "The", "This", "Reply", "Also", "URGENT", "I"}


def find_funding_claims(doc: SourceDocument) -> list[XFundingClaim]:
    out: list[XFundingClaim] = []
    taken: list[tuple[int, int]] = []
    f = fold(doc.text)

    def group(m: re.Match[str], name: str) -> str | None:
        if m.groupdict().get(name) is None:
            return None
        return _quote(f, *m.span(name)) or None

    for pat in _FUNDING:
        for m in pat.finditer(f.text):
            if any(m.start() < e and s < m.end() for s, e in taken) or parse_money(m.group("amt")) is None:
                continue
            name = re.sub(r"^.*(?:获得|来自|我们是|这里是|由|从)", "", (group(m, "name") or "").strip())
            if not name or name in _NAME_STOP or name.split()[0] in _NAME_STOP:
                name = _lender_elsewhere(f) or doc.sender_id
            quote = _quote(f, m.start(), m.end(), " ,，\n")
            amount = group(m, "amt")
            if not quote or not amount:
                continue
            out.append(XFundingClaim(
                lender_name=name, doc_id=doc.doc_id, quote=quote, amount_text=amount.strip(), rate_text=group(m, "rate"),
            ))
            taken.append((m.start(), m.end()))
    return out


def _lender_elsewhere(f: Folded) -> str | None:
    m = rx(r"\bfrom\s+([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,3})").search(f.text)
    return f.orig(*m.span(1)) if m else None


# ---------------------------------------------------------------- quantities (conflicting sources)

_QUANTITIES: list[tuple[str, re.Pattern[str]]] = [
    ("order_size", rx(rf"(?P<amt>{_AMT})\s+(?:purchase\s+)?(?:order|PO)\b", I)),
    ("order_size", rx(
        rf"\b(?:order|PO|purchase\s+order)\s+(?:size|value|amount|total)\s*(?:of|is|[:：])?\s*(?P<amt>{_AMT})", I)),
    ("order_size", rx(rf"\b(?:an?\s+)?order\s+of\s+(?P<amt>{_AMT})", I)),
    ("order_size", rx(rf"\b(?:order|PO|purchase\s+order)\s+(?:for|worth|totall?ing|valued\s+at)\s+(?P<amt>{_AMT})", I)),
    ("order_size", rx(rf"(?:下单|订购|订货|下了?订单)\s*(?:了)?\s*(?P<amt>{_AMT})")),
    ("order_size", rx(rf"(?:订单|采购)(?:金额|总额|总价|规模)\s*[:：为是]?\s*(?P<amt>{_AMT})")),
    ("order_size", rx(rf"(?P<amt>{_AMT})\s*(?:的)?(?:订单|采购单)")),
    ("invoice_amount", rx(
        rf"\binvoice\s+(?:amount|face|value|total)\s*(?:of|is|[:：])?\s*(?P<amt>{_AMT})", I)),
    ("invoice_amount", rx(rf"(?:发票|货款)(?:金额|总额)\s*[:：为是]?\s*(?P<amt>{_AMT})")),
]


def find_quantities(doc: SourceDocument) -> list[XQuantity]:
    out: list[XQuantity] = []
    for kind, pat in _QUANTITIES:
        for m in pat.finditer(doc.text):
            if parse_money(m.group("amt")) is None:
                continue
            out.append(XQuantity(kind=kind, doc_id=doc.doc_id, quote=m.group(0).strip(), amount_text=m.group("amt").strip()))  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------- unresolved references ("as usual")

AS_USUAL_RE = rx(
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
