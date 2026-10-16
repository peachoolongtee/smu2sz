"""Code-side checks on a grounded contract: derived performance dates and cross-checks between figures.

Nothing here reads a model's words. Every value comes from text quoted in the document and is parsed by code. A derived
date says so in `text`; a check that disagrees adds a note for the owner and changes no term.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.compiler.contract_parsing import parse_date
from app.compiler.parsing import find_money
from app.domain.models import Abstention, ContractField, ContractTerm, SourceDocument, SourceSpan

F = ContractField

# "本合同签订之日起15日内交货", "自合同签订之日起45日内": a period counted from signing, in calendar days or in working days.
_FROM_SIGNING = re.compile(r"(?:自)?(?:本)?合同签订(?:生效)?之日起\s*(\d{1,4})\s*(个?工作日|日|天)内")
_PERFORMANCE = re.compile(r"交货|交付|供货|送至|送达|完成|提供|履行|竣工|验收合格后")
_PAYMENT = re.compile(r"付款|支付|预付|款|发票|汇票|转账")
_STATED_END = re.compile(r"[（(]?即(?:不迟于)?\s*([^，。；）)\n]{6,18}?)(?:前|完成|之前)")
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
    if stated := _STATED_END.search(sentence):
        said = parse_date(stated.group(1)).value
        if said is not None and said != end:
            abst.append(Abstention(field=F.END_DATE.value, spans=[span], reason=(
                f"note: {days} days from signing is {end}, but the contract also says {said}; no end date is read")))
            return []
    out = []
    if F.START_DATE not in have:
        out.append(ContractTerm(field=F.START_DATE, span=span, clause=None, value_text=m.group(0), date=signed.date,
                                text=DERIVED + "the signing date"))
    if F.END_DATE not in have:
        out.append(ContractTerm(field=F.END_DATE, span=span, value_text=m.group(0), date=end,
                                text=DERIVED + f"the signing date plus {days} days"))
    return out


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


def check_notes(checks: list[Check]) -> list[Abstention]:
    return [Abstention(field=f"note:{c.kind}", spans=list(c.spans), reason=f"check failed: {c.note}")
            for c in checks if not c.ok]
