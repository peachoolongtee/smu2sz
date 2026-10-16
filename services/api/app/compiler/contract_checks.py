"""Code-side checks on a grounded contract: derived performance dates and cross-checks between figures.

Nothing here reads a model's words. Every value comes from text quoted in the document and is parsed by code. A derived
date says so in `text`; a check that disagrees adds a note for the owner and changes no term.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.compiler.contract_parsing import CN_COUNT, COUNT_PAT, cn_int, parse_count, parse_date
from app.compiler.parsing import find_money
from app.domain.models import Abstention, ContractField, ContractTerm, PaymentBasis, SourceDocument, SourceSpan

F = ContractField

# "本合同签订之日起15日内交货", "自合同签订之日起45日内": a period counted from signing, in calendar days or in working days.
_FROM_SIGNING = re.compile(r"(?:自)?(?:本)?合同签订(?:生效)?之日起\s*(\d{1,4})\s*(个?工作日|日|天)内")
_PERFORMANCE = re.compile(r"交货|交付|供货|送至|送达|完成|提供|履行|竣工|验收合格后")
_PAYMENT = re.compile(r"付款|支付|预付|款|发票|汇票|转账")
_STATED_END = re.compile(r"[（(]?即(?:不迟于)?\s*([^，。；）)\n]{6,18}?)(?:前|完成|之前)"
                         r"|不迟于\s*([^，。；）)\n]{6,18}?)(?:前|之前)?完成")
# "签订之日起90日内运抵……，并在到货后20日内完成安装调试": a second period chained after the one counted from signing, so
# signing plus the first period is not the end of performance
_CHAINED = re.compile(r"(?:后|起)\s*\d{1,4}\s*(?:个?工作日|日|天)(?:内|之内|以内)")
DERIVED = "derived: "


def _bounds(text: str, pos: int) -> tuple[int, int]:
    start = max(text.rfind(c, 0, pos) for c in ("。", "；", "\n")) + 1
    ends = [i for i in (text.find(c, pos) for c in ("。", "；", "\n")) if i != -1]
    return start, (min(ends) if ends else len(text))


def derived_dates(doc: SourceDocument, terms: list[ContractTerm], abst: list[Abstention]) -> list[ContractTerm]:
    """START_DATE = the signed date and END_DATE = signed + N days, for a delivery or service period the contract counts
    from signing ("本合同签订之日起15日内交货"). Only calendar days, only from a quoted sentence about performance (not payment),
    only for a date the model did not read, and only when the contract does not state a different end date itself."""
    have = {t.field for t in terms}
    signed = next((t for t in terms if t.field == F.SIGNED_DATE and t.date), None)
    if signed is None or {F.START_DATE, F.END_DATE} <= have:
        return []
    found: dict[int, tuple[re.Match[str], str]] = {}
    for m in _FROM_SIGNING.finditer(doc.text):
        s, e = _bounds(doc.text, m.start())
        sentence = doc.text[s:e]
        if _PAYMENT.search(sentence) or not _PERFORMANCE.search(sentence):
            continue
        span = SourceSpan(doc_id=doc.doc_id, start=m.start(), end=m.end(), text=m.group(0))
        if "工作日" in m.group(2):
            abst.append(Abstention(field=F.END_DATE.value, spans=[span], reason=(
                "note: the period is counted in working days from signing, so no end date is derived")))
            continue
        found[int(m.group(1))] = (m, sentence)
    if len(found) != 1:
        if len(found) > 1:
            abst.append(Abstention(field=F.END_DATE.value, reason=(
                "note: the contract counts performance from signing in more than one way, so no end date is derived")))
        return []
    days, (m, sentence) = next(iter(found.items()))
    span = SourceSpan(doc_id=doc.doc_id, start=m.start(), end=m.end(), text=m.group(0))
    end = (date.fromisoformat(signed.date) + timedelta(days=days)).isoformat()  # type: ignore[arg-type]
    stated = _STATED_END.search(sentence)
    said = parse_date(stated.group(1) or stated.group(2)).value if stated else None
    how, end_span = f"the signing date plus {days} days", span
    if _CHAINED.search(sentence, sentence.find(m.group(0)) + len(m.group(0))):
        if said is None:
            abst.append(Abstention(field=F.END_DATE.value, spans=[span], reason=(
                "note: a second period follows the one counted from signing, so no end date is derived")))
            return []
        end, how = str(said), "the date by which the sentence says all the work is done"
        assert stated is not None  # a stated date was read from it
        at = _bounds(doc.text, m.start())[0] + stated.start()
        end_span = SourceSpan(doc_id=doc.doc_id, start=at, end=at + len(stated.group(0)), text=stated.group(0))
    elif said is not None:
        if said != end:
            abst.append(Abstention(field=F.END_DATE.value, spans=[span], reason=(
                f"note: {days} days from signing is {end}, but the contract also says {said}; no end date is read")))
            return []
    out = []
    if F.START_DATE not in have:
        out.append(ContractTerm(field=F.START_DATE, span=span, clause=None, value_text=m.group(0), date=signed.date,
                                text=DERIVED + "the signing date"))
    if F.END_DATE not in have:
        out.append(ContractTerm(field=F.END_DATE, span=end_span, value_text=end_span.text, date=end,
                                text=DERIVED + how))
    return out


# ---------------------------------------------------------------- per-stage payment schedule
#
# A milestone's quote states the stage's condition and its deadline ("交付成果经甲方验收合格并出具书面验收报告后15日内",
# "payable within 30 days after acceptance"). Code reads the days, their unit and the trigger from that quote alone.
# `PaymentBasis` has no value for signing, a quarter, an audit or the end of a warranty, and the engine's domain models
# are frozen, so the trigger is classified here, on demand, from the quote; only INVOICE, DELIVERY and ACCEPTANCE are
# also written to the term's `basis`.

TRIGGERS = ("sign", "delivery", "acceptance", "invoice", "quarter", "audit", "warranty_end", "milestone")
_BASIS_OF_TRIGGER = {"invoice": PaymentBasis.INVOICE, "delivery": PaymentBasis.DELIVERY,
                     "acceptance": PaymentBasis.ACCEPTANCE}

_ZH_DEADLINE = re.compile(
    rf"(?:(?:后|起|之日起)\s*(?P<a>\d{{1,4}}|{CN_COUNT})\s*(?P<ua>个?工作日|个?自然日|日|天)(?:内|之内|以内)?"
    rf"|(?P<b>\d{{1,4}}|{CN_COUNT})\s*(?P<ub>个?工作日|个?自然日|日|天)(?:内|之内|以内))")
_EN_DEADLINE = re.compile(
    rf"(?<![\w-])(?P<n>{COUNT_PAT})\s+(?P<w>(?:business|working|banking)\s+)?days?\b", re.IGNORECASE)
_CJK = re.compile(r"[一-鿿]")


def _squash(text: str) -> str:
    """Whitespace a PDF puts inside a Chinese phrase (a line break in the middle of 验收报告, or the spaces around a
    table bar) taken out; the spaces between two Latin words or figures stay."""
    return re.sub(r"(?<![A-Za-z0-9])\s+|\s+(?![A-Za-z0-9])", "", text)


@dataclass(frozen=True)
class StageDeadline:
    days: int | None  # None when the quote states no days, or two different ones
    working: bool = False  # counted in working days (个工作日 / business days)
    status: str = "ok"  # ok | none | conflict
    end: int = 0  # offset in the squashed quote where the (first) deadline begins


def _zh_deadlines(squashed: str) -> list[tuple[int, bool, int]]:
    found: list[tuple[int, bool, int]] = []
    for m in _ZH_DEADLINE.finditer(squashed):
        raw, unit = (m.group("a"), m.group("ua")) if m.group("a") else (m.group("b"), m.group("ub"))
        n = int(raw) if raw.isdigit() else cn_int(raw)
        if n is not None:
            found.append((n, "工作日" in unit, m.start()))
    return found


def _en_deadlines(text: str) -> list[tuple[int, bool, int]]:
    found: list[tuple[int, bool, int]] = []
    for m in _EN_DEADLINE.finditer(text):
        n = parse_count(m.group("n"))
        if n.ok and isinstance(n.value, int):
            found.append((n.value, m.group("w") is not None, m.start()))
    return found


def stage_deadline(quote: str) -> StageDeadline:
    """The payment deadline a stage's quote states: days and unit (日/天 calendar, 个工作日 working; days / business days).
    No days, or two different deadlines in one quote, is no value: the caller notes it and never guesses."""
    if _CJK.search(quote):
        squashed = _squash(quote)
        found = _zh_deadlines(squashed)
    else:
        squashed = re.sub(r"\s+", " ", quote)
        found = _en_deadlines(squashed)
    distinct = {(n, w) for n, w, _ in found}
    if not distinct:
        return StageDeadline(None, status="none")
    if len(distinct) > 1:
        return StageDeadline(None, status="conflict", end=min(p for _, _, p in found))
    (n, w), = distinct
    return StageDeadline(n, w, "ok", min(p for _, _, p in found))


_ZH_TRIGGERS: tuple[tuple[str, re.Pattern[str]], ...] = tuple((k, re.compile(p)) for k, p in (
    ("warranty_end", r"质保期(?:满|届满|结束|终止)|质量保证期(?:满|届满|结束)|缺陷责任期(?:满|届满)|保修期(?:满|届满|结束)|质保(?:期)?到期"),
    ("audit", r"审计|决算|结算审核|审减"),
    ("quarter", r"每季度|每个季度|按季|季度(?:服务)?考核|每季"),
    ("milestone", r"阶段(?:性)?成果|里程碑|节点"),
    ("acceptance", r"验收|终验|初验"),
    ("invoice", r"(?:收到|取得|接到|收讫|收妥|提交)[^，。；|]{0,14}发票|发票(?:收到|送达|无误)"),
    ("delivery", r"交付|交货|到货|送达|签收|收货|供货完成"),
    ("sign", r"签订|签署|签约|生效"),
))
_EN_TRIGGERS: tuple[tuple[str, re.Pattern[str]], ...] = tuple((k, re.compile(p, re.IGNORECASE)) for k, p in (
    ("warranty_end", r"warranty\s+(?:period\s+)?(?:ends?|expires?|expiry|has\s+expired)|(?:end|expiry|expiration)\s+of\s+"
                     r"(?:the\s+)?(?:warranty|defects?\s+liability)|defects?\s+liability\s+period"),
    ("audit", r"\baudit"),
    ("quarter", r"\bquarter(?:ly)?\b|\bper\s+quarter\b"),
    ("milestone", r"\bmilestones?\b"),
    ("acceptance", r"\baccept"),
    ("invoice", r"\binvoices?\b"),
    ("delivery", r"\bdeliver|\breceipt\s+of\s+(?:the\s+)?(?:goods|products)"),
    ("sign", r"\bsign(?:ing|ed|ature)\b|\bexecution\b|\beffective\s+date\b|\bcommencement\b"),
))


def _classify(text: str) -> str | None:
    table = _ZH_TRIGGERS if _CJK.search(text) else _EN_TRIGGERS
    return next((k for k, rx_ in table if rx_.search(text)), None)


def stage_trigger(quote: str, text: str | None = None) -> str | None:
    """What a stage's payment waits for, one of `TRIGGERS`, read from the words that lead to its deadline: the table cell
    or the clause before the days ("本合同签订生效后15日内" is sign; "经甲方验收合格后30日内" is acceptance). Falls back to the
    stage's whole quote, then to the trigger text the reading gave. None when the words name none of them."""
    deadline = stage_deadline(quote)
    squashed = _squash(quote) if _CJK.search(quote) else re.sub(r"\s+", " ", quote)
    # Chinese puts the condition before its days; English puts it after ("within 30 days after acceptance")
    head = squashed[:deadline.end] if deadline.status != "none" and _CJK.search(quote) else squashed
    clause = re.split(r"[|：:。；;]", head)[-1] if head else ""
    # a cell holding only the deadline ("30日内") has its condition in the cell before it
    cells = [c for c in re.split(r"[|：:。；;]", head) if c]
    for candidate in (clause, cells[-2] if len(cells) > 1 and len(clause) < 4 else "", head, squashed, text or ""):
        if candidate and (found := _classify(candidate)):
            return found
    return None


# The end of a table row in extracted text: a blank line before the next row ("2 进度款 ..."), a table header, the page footer,
# the paragraph that follows the table ("乙方应在每期付款前...") or the next clause.
_ROW_END = re.compile(
    r"\n[ \t]*\n(?=[ \t]*(?:\d{1,2}[ \t|]+[^\d\s]|期次|序号|合同编号|第\s*\d+\s*页|[甲乙]方(?:应|收款|指定|账户)|备注|[一二三四五六七八九十]+、"
    r"|第[一二三四五六七八九十]+条|\d+[.．]\s))")
_ROW_START = re.compile(r"\d{1,2}[ \t|]+\S")
MAX_ROW_REACH = 200


def widen_to_row(text: str, start: int, end: int) -> int:
    """The end of a payment-table row whose quote stops short of its deadline. PDF text breaks a table row across lines
    ("...验收报" / "告后20个工作日内 银行转账"), and a reading may quote only the first cell ("1 预付款 30%"). When the quote
    starts a row, states no deadline and the rest of the row (up to the next row, header, footer or paragraph) does,
    this is the row's end; otherwise `end` unchanged."""
    quote = text[start:end]
    at_line_start = start == 0 or text[start - 1] == "\n"
    if not _CJK.search(quote) or not at_line_start or not _ROW_START.match(quote) or stage_deadline(quote).status != "none":
        return end
    m = _ROW_END.search(text, end, min(len(text), end + MAX_ROW_REACH))
    row_end = m.start() if m else -1
    if row_end <= end or stage_deadline(text[start:row_end]).status != "ok":
        return end
    return row_end


def stage_basis(trigger: str | None) -> PaymentBasis | None:
    """The `PaymentBasis` a trigger corresponds to; None for the triggers PaymentBasis has no value for."""
    return _BASIS_OF_TRIGGER.get(trigger or "")


@dataclass(frozen=True)
class Check:
    kind: str  # STAGES_SUM_100 | STAGE_AMOUNT | WRITTEN_TOTAL
    ok: bool
    note: str
    spans: tuple[SourceSpan, ...] = ()


_TOTAL_LINE = re.compile(r"合同(?:总价|金额|总金额|价款)|合计|总价")
_WRITTEN = re.compile(r"大写(?:金额)?\s*[：:|]?\s*(人民币\s*[零壹贰叁肆伍陆柒捌玖拾佰仟万亿元圆角分整正]+)")


def cross_checks(doc: SourceDocument, terms: list[ContractTerm]) -> list[Check]:
    checks: list[Check] = []
    stages = [t for t in terms if t.field == F.MILESTONE and t.rate_bp is not None]
    prices = [t for t in terms if t.field == F.PRICE and t.amount_fen is not None]
    total = max(prices, key=lambda t: t.amount_fen or 0) if prices else None
    if len(stages) >= 2:
        held = sum(t.rate_bp or 0 for t in terms if t.field == F.RETENTION)  # the last stage, withheld as retention
        pct = sum(t.rate_bp or 0 for t in stages) + held
        checks.append(Check("STAGES_SUM_100", pct == 10_000,
                            f"the stage percentages add up to {pct / 100:g}%, not 100%", tuple(t.span for t in stages)))
    if total is not None:
        for t in stages:
            amounts = {f.value for f in find_money(t.span.text)} - {total.amount_fen}
            if not amounts:
                continue
            want = round(total.amount_fen * t.rate_bp / 10_000)  # type: ignore[operator]
            ok = any(abs(a - want) <= 1 for a in amounts)
            checks.append(Check("STAGE_AMOUNT", ok, (
                f"a stage of {t.rate_bp / 10_000:.0%} of the total should be {want / 100:,.2f}, "  # type: ignore[operator]
                f"but its clause states {', '.join(f'{a / 100:,.2f}' for a in sorted(amounts))}"), (t.span,)))
        for w in _WRITTEN.finditer(doc.text):
            line = doc.text[slice(*_bounds(doc.text, w.start()))]
            if "%" in line or not _TOTAL_LINE.search(line):  # the words beside a stage amount are not the total
                continue
            values = {f.value for f in find_money(w.group(1))}
            if len(values) == 1:
                v = values.pop()
                span = SourceSpan(doc_id=doc.doc_id, start=w.start(1), end=w.end(1), text=w.group(1))
                if v == total.amount_fen or v in {t.amount_fen for t in prices}:
                    checks.append(Check("WRITTEN_TOTAL", True, "the amount in words equals the amount in figures", (span,)))
                else:
                    checks.append(Check("WRITTEN_TOTAL", False, (
                        f"the amount in words ({v / 100:,.2f}) differs from the total read ({total.amount_fen / 100:,.2f})"),  # type: ignore[operator]
                        (span,)))
                break
    return checks


# ---------------------------------------------------------------- who pays whom
#
# PARTY_BUYER is the party that pays, PARTY_SUPPLIER the party that is paid, whatever the role labels (承包人/分包人,
# 定作方/承揽方, 承租方/出租方). A reading sometimes files them the other way round. The contract says who is paid in two
# ways code can read: the receiving account ("乙方收款账户：户名 某某公司") and the direction of a payment of the price
# ("甲方以银行转账方式向乙方支付合同价款的10%"). A penalty, a deposit, a refund or interest runs the other way or says
# nothing of the price, so a sentence about one of them is not evidence.

_ROLE = re.compile(r"^\s*(甲方|乙方)")
_RECEIVING = re.compile(r"(甲方|乙方)?\s*(?:指定的?)?收款(?:账户|帐户|账号|帐号|单位|人)")
_PAYS_TO = re.compile(r"(甲方|乙方)(?:(?!甲方|乙方)[^。；;\n向]){0,40}向(甲方|乙方)(?:支付|付清|付款|结清)")
_NOT_PRICE = re.compile(r"违约|赔偿|罚|保证金|保函|担保|押金|定金|退还|返还|退回|垫付|代付|工资|利息|损失")


def _sentence_after(text: str, pos: int, reach: int = 100) -> str:
    ends = [i for i in (text.find(c, pos) for c in ("。", "；", ";")) if i != -1]
    return text[pos:min([*ends, pos + reach])]


def payee_roles(text: str, names: dict[str, str]) -> set[str]:
    """The role labels (甲方/乙方) the contract says are paid. `names` maps each party's name to its role, so an account
    held in a party's name counts as that party's even when the account line names no role."""
    paid: set[str] = set()
    for m in _RECEIVING.finditer(text):
        if m.group(1):
            paid.add(m.group(1))
            continue
        after = re.sub(r"\s+", "", _sentence_after(text, m.end()))
        held = {role for name, role in names.items() if name and name in after}
        if len(held) == 1:
            paid |= held
    for m in _PAYS_TO.finditer(text):
        s, e = _bounds(text, m.start())
        if m.group(1) != m.group(2) and not _NOT_PRICE.search(text[s:e]):
            paid.add(m.group(2))
    return paid


def payer_payee_check(doc: SourceDocument, terms: list[ContractTerm], abst: list[Abstention]) -> list[ContractTerm]:
    """PARTY_BUYER and PARTY_SUPPLIER swapped when the contract clearly says the reading's buyer is the one paid: every
    piece of evidence names the same role, and each party's quote carries a different role label. Anything less clear
    (no evidence, evidence both ways, a party without a label) leaves the reading as it is."""
    buyers = [t for t in terms if t.field == F.PARTY_BUYER]
    suppliers = [t for t in terms if t.field == F.PARTY_SUPPLIER]
    if len(buyers) != 1 or len(suppliers) != 1:
        return terms
    (b,), (s,) = buyers, suppliers
    rb, rs = _ROLE.match(b.span.text), _ROLE.match(s.span.text)
    if rb is None or rs is None or rb.group(1) == rs.group(1):
        return terms
    names = {re.sub(r"\s+", "", b.text or ""): rb.group(1), re.sub(r"\s+", "", s.text or ""): rs.group(1)}
    paid = payee_roles(doc.text, names)
    if paid != {rb.group(1)}:
        return terms
    abst.append(Abstention(field=f"note:{F.PARTY_SUPPLIER.value}", spans=[b.span, s.span], reason=(
        f"note: the contract pays {rb.group(1)} (its receiving account, or a payment made to it), so {rb.group(1)} is "
        "the supplier and the other party the buyer")))
    return [b.model_copy(update={"field": F.PARTY_SUPPLIER}) if t is b
            else s.model_copy(update={"field": F.PARTY_BUYER}) if t is s else t for t in terms]


def check_notes(checks: list[Check]) -> list[Abstention]:
    return [Abstention(field=f"note:{c.kind}", spans=list(c.spans), reason=f"check failed: {c.note}")
            for c in checks if not c.ok]
