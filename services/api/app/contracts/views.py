"""Server-formatted views of a contract record (INVARIANT 13: the UI never formats money or rates).

`record_view` is the review screen: the document text, every term beside its quote and span, the fields left blank
and why, the flags, and for a lender agreement the agreement against the facility on the books. `record_summary` is
the row the documents list shows. Every reading is labelled "AI-generated, for reference" until the owner confirms it.

Every sentence is written by the server in the page's language (`lang`, "en" or "zh") and the figures are the same in both.
A day is said as a distance from `today` ("3 days ago"), never as "day N", when `today` is given.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.api.engine_zh import translate
from app.api.presentation import Lang, t, when_text
from app.contracts.derive import date_display, day_of
from app.contracts.parties import PARTY_FLAG_KINDS, PARTY_NOT_NAMED, named_parties, party_note
from app.domain.models import (
    CONTRACT_READING_KINDS,
    MULTI_VALUED_CONTRACT_FIELDS,
    ContractField,
    ContractRecord,
    ContractTerm,
    DocumentKind,
    DocumentStatus,
    Facility,
    FinancialState,
    PaymentBasis,
    PriceUnit,
)
from app.domain.money import Ratio, bp, fmt_pct, fmt_yuan
from app.domain.ports import ContractGuardRow

F = ContractField
AI_LABEL = "AI-generated, for reference"
AI_LABEL_ZH = "由 AI 生成，仅供参考"

FIELD_LABELS: dict[ContractField, str] = {
    F.PARTY_SUPPLIER: "Supplier", F.PARTY_BUYER: "Buyer", F.CONTRACT_REFERENCE: "Agreement number",
    F.SIGNED_DATE: "Signed", F.START_DATE: "Starts", F.END_DATE: "Ends", F.DURATION: "Term", F.PRICE: "Price",
    F.INVOICING: "Invoicing", F.SCHEDULED_INVOICE: "Scheduled invoice", F.PAYMENT_TERMS: "Payment terms",
    F.EARLY_PAYMENT: "Early payment", F.MILESTONE: "Milestone payment", F.RETENTION: "Retention",
    F.LATE_INTEREST: "Late-payment interest", F.DELIVERABLE: "Deliverable", F.REQUIRED_DOCUMENT: "Document for payment",
    F.AMENDMENT: "Amendments",
}
FIELD_LABELS_ZH: dict[ContractField, str] = {
    F.PARTY_SUPPLIER: "供应方", F.PARTY_BUYER: "买方", F.CONTRACT_REFERENCE: "合同编号", F.SIGNED_DATE: "签署日",
    F.START_DATE: "开始日", F.END_DATE: "结束日", F.DURATION: "期限", F.PRICE: "价格", F.INVOICING: "开票",
    F.SCHEDULED_INVOICE: "约定发票", F.PAYMENT_TERMS: "账期", F.EARLY_PAYMENT: "提前付款", F.MILESTONE: "阶段付款",
    F.RETENTION: "质保金", F.LATE_INTEREST: "逾期利息", F.DELIVERABLE: "交付物", F.REQUIRED_DOCUMENT: "付款所需文件",
    F.AMENDMENT: "修订",
}
BASIS_TEXT = {PaymentBasis.INVOICE: "the invoice date", PaymentBasis.DELIVERY: "delivery",
              PaymentBasis.ACCEPTANCE: "acceptance", PaymentBasis.MONTH_END: "the end of the invoice month"}
BASIS_TEXT_ZH = {PaymentBasis.INVOICE: "发票日", PaymentBasis.DELIVERY: "交货", PaymentBasis.ACCEPTANCE: "验收",
                 PaymentBasis.MONTH_END: "开票当月月末"}
UNIT_TEXT_ZH = {PriceUnit.PER_DELIVERY: "每批交货", PriceUnit.PER_UNIT: "每单位", PriceUnit.PER_MONTH: "每月",
                PriceUnit.LUMP_SUM: "总价"}
UNIT_TEXT = {PriceUnit.PER_DELIVERY: "per delivery batch", PriceUnit.PER_UNIT: "per unit",
             PriceUnit.PER_MONTH: "per month", PriceUnit.LUMP_SUM: "in total"}
NOT_FOUND_REASON = "The agent found no clause for this and left it blank."
NOT_FOUND_REASON_ZH = "代理没有找到相关条款，已留空。"


def _days(n: int, business: bool, lang: Lang = "en") -> str:
    if lang == "zh":
        return f"{n} 个工作日" if business else f"{n} 天"
    return f"{n} {'business ' if business else ''}day{'' if n == 1 else 's'}"


def _date(iso: str | None, anchor: str | None, lang: Lang = "en", today: int | None = None) -> str:
    """A calendar date, and when it is as a distance from today when the books' anchor and today are known."""
    if iso is None:
        return ""
    when = when_text(day_of(iso, anchor), today, lang) if anchor and today is not None else ""
    return date_display(iso, lang) + ((f"（{when}）" if lang == "zh" else f" ({when})") if when else "")


def term_display(term: ContractTerm, anchor: str | None = None, lang: Lang = "en", today: int | None = None) -> str:
    """One plain line for a term, from its typed fields only."""
    f = term.field
    if f == F.PRICE and term.amount_fen is not None:
        unit = (UNIT_TEXT_ZH if lang == "zh" else UNIT_TEXT).get(term.unit, "") if term.unit else ""
        return f"{fmt_yuan(term.amount_fen)} {unit}".strip()
    if f == F.INVOICING:
        if lang == "zh":
            return (f"每 {term.days} 天开票一次" if term.days else "每月开票") + (
                f"，首张为 {_date(term.date, anchor, lang, today)}" if term.date else "")
        head = f"Every {_days(term.days, False)}" if term.days else "Monthly"
        return head + (f", the first on {_date(term.date, anchor, lang, today)}" if term.date else "")
    if f == F.SCHEDULED_INVOICE:
        amount = f"{fmt_yuan(term.amount_fen)} " if term.amount_fen is not None else ""
        if lang == "zh":  # the contract's name for the invoice stays in `reference`, never in the sentence
            return f"一张发票：{amount}于 {_date(term.date, anchor, lang, today)} 开具"
        return f"An invoice: {amount}issued {_date(term.date, anchor, lang, today)}"
    if f == F.PAYMENT_TERMS and term.days is not None:
        if lang == "zh":
            basis = BASIS_TEXT_ZH[term.basis] if term.basis else "合同未注明的日期"
            return f"自{basis}起 {_days(term.days, term.business_days, lang)}"
        return (f"{_days(term.days, term.business_days)} from "
                f"{BASIS_TEXT[term.basis] if term.basis else 'a date the clause does not state'}")
    if f == F.EARLY_PAYMENT and term.rate_bp is not None:
        if lang == "zh":
            window = f"，须在 {_days(term.days, term.business_days, lang)}内" if term.days is not None else ""
            return f"买方可提前付款，折扣 {fmt_pct(bp(term.rate_bp))}{window}"
        window = f", within {_days(term.days, term.business_days)}" if term.days is not None else ""
        return f"The buyer may settle early at {fmt_pct(bp(term.rate_bp))} off{window}"
    if f == F.MILESTONE and term.rate_bp is not None:
        return t(lang, f"{fmt_pct(bp(term.rate_bp))} of the price {term.text or ''}",
                 f"价格的 {fmt_pct(bp(term.rate_bp))} {term.text or ''}").strip()
    if f == F.RETENTION and term.rate_bp is not None:
        if lang == "zh":
            period = (f"，保留 {term.months} 个月" if term.months else f"，保留 {_days(term.days, False, lang)}" if term.days
                      else f"，{term.text}" if term.text else "")
            return f"质保金 {fmt_pct(bp(term.rate_bp))}{period}"
        period = (f" for {term.months} months" if term.months else f" for {_days(term.days, False)}" if term.days
                  else f" {term.text}" if term.text else "")
        return f"{fmt_pct(bp(term.rate_bp))} retained{period}"
    if f == F.LATE_INTEREST and term.rate_bp is not None:
        return f"{fmt_pct(bp(term.rate_bp))}{' ' + term.text if term.text else ''}"
    if f in (F.SIGNED_DATE, F.START_DATE, F.END_DATE):
        return _date(term.date, anchor, lang, today)
    if f == F.DURATION and term.months is not None:
        return t(lang, f"{term.months} months", f"{term.months} 个月")
    return term.text or term.value_text or ""


def term_view(term: ContractTerm, anchor: str | None, lang: Lang = "en", today: int | None = None) -> dict[str, Any]:
    return {
        "field": term.field.value, "label": (FIELD_LABELS_ZH if lang == "zh" else FIELD_LABELS)[term.field],
        "value_display": term_display(term, anchor, lang, today),
        "clause": term.clause, "quote": term.span.text, "span": {"start": term.span.start, "end": term.span.end},
        "amount_fen": term.amount_fen,
        "amount_display": fmt_yuan(term.amount_fen) if term.amount_fen is not None else None,
        "rate_bp": term.rate_bp, "rate_display": fmt_pct(bp(term.rate_bp)) if term.rate_bp is not None else None,
        "days": term.days, "months": term.months, "date": term.date,
        "date_display": date_display(term.date, lang) if term.date else None,
        "day": day_of(term.date, anchor) if term.date and anchor else None,
        "basis": term.basis.value if term.basis else None, "unit": term.unit.value if term.unit else None,
        "reference": term.reference, "text": term.text, "business_days": term.business_days,
    }


# What the reading says about itself, in the owner's words. The compiler writes English reasons (the audit level, kept as
# `reason_raw`); the ones the contract reader writes are a closed set, said here in Chinese. Any other reason goes through the
# engine-sentence templates and, if none knows it, is said generally rather than left in English.
_REASONS_ZH: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(p), z) for p, z in (
    (r"term dropped: its \w+ is not inside its quoted evidence", "该条款已舍弃：其中的某个数值不在所引原文之内。"),
    (r"term dropped: the .+ is stated twice with different values.*", "该条款已舍弃：同一数值的文字写法与数字写法不一致。"),
    (r"term dropped: the .+ is not parseable as an exact value", "该条款已舍弃：无法读出确切数值。"),
    (r"term dropped: its quote is not found verbatim in the document", "该条款已舍弃：引文在文件中找不到原句。"),
    (r"term dropped: no .+ is stated in its quote", "该条款已舍弃：所引原文中没有写明所需内容。"),
    (r"term dropped: it sits in text addressed to the agent.*", "该条款已舍弃：它位于写给代理的文字中，这类文字从不当作条款读取。"),
    (r"note: the payment terms do not say what the days count from", "账期没有写明这些天数从何时起算。"),
    (r"stated more than once with the same value: read once", "同一数值写了多次：只读取一次。"),
    (r"clause dropped: quote not found verbatim in the term sheet", "该条款已舍弃：引文在文件中找不到原句。"),
    (r"flag dropped: quote not found verbatim in the document", "该提示已舍弃：引文在文件中找不到原句。"),
))
_CONFLICT = re.compile(r"conflicting sources: (.+) state different values; neither is read, clarification needed")
_UNREADABLE_ZH = "代理在读取时留下一条说明（英文原文见技术详情）。"


def reason_words(reason: str, lang: Lang, state: FinancialState | None = None) -> str:
    """A reason the reading gave for leaving something blank or noting something, in the page's language."""
    if lang != "zh":
        return reason
    if reason == NOT_FOUND_REASON:
        return NOT_FOUND_REASON_ZH
    for pattern, zh in _REASONS_ZH:
        if pattern.fullmatch(reason):
            return zh
    m = _CONFLICT.fullmatch(reason)
    if m:
        where = m.group(1).replace("an unnumbered clause", "未编号的条款")
        return f"来源冲突：{where} 写了不同的数值，两处都不采用，需要向对方确认。"
    said = translate(reason, [])
    return said if said is not None and not re.search(r"[A-Za-z]{3,}", said) else _UNREADABLE_ZH


_FLAG_WORDS = {
    "INSTRUCTION_OVERRIDE": ("an instruction addressed to the agent", "写给代理的指令"),
    "PRE_APPROVAL": ("a claimed approval", "声称已获批准"),
    "PRIOR_AGREEMENT": ("a claimed earlier agreement", "声称已有约定"),
    "URGENCY": ("pressure to hurry", "催促施压"),
    "IMPERSONATION": ("a claim to speak for someone", "冒用他人身份"),
    "PARTY_NOT_NAMED": ("not the counterparty you chose", "不是您选择的对方"),
    "PARTY_UNCHECKED": ("parties not checked", "未能核对合同各方"),
}
_FLAG_NOTES_ZH = {
    "INSTRUCTION_OVERRIDE": "这是写给代理的文字，不是条款，该文件无法确认；请让对方提供干净的版本。",
    "PRE_APPROVAL": "文字声称某项批准已经取得，但没有人通过代理给出过批准。",
    "IMPERSONATION": "文字声称代表某人，或更改了付款信息：请与对方核实。",
}


def flag_kind_text(kind: str, lang: Lang) -> str:
    """A flag's kind in words ("an instruction addressed to the agent"); a data request is one whatever it asks for."""
    if kind.startswith("DATA_REQUEST"):
        return t(lang, "a request for protected information", "索取受保护信息")
    en, zh = _FLAG_WORDS.get(kind, ("a claim of authority", "声称拥有权限"))
    return t(lang, en, zh)


def flag_note(kind: str, blocking: bool, note: str, lang: Lang) -> str:
    """The flag's note in the page's language; English is the note as the reader wrote it."""
    if lang != "zh":
        return note
    if kind.startswith("DATA_REQUEST"):
        return "文字要求提供代理的指令：该文件无法确认。" if blocking else "文字要求供应方披露受保护的信息。"
    return _FLAG_NOTES_ZH.get(kind, "文字声称拥有权限。")


def blanks(record: ContractRecord, lang: Lang = "en") -> list[dict[str, Any]]:
    """The fields the reading left blank, each with why: a dropped term's reason, a conflict, or not found."""
    c = record.contract
    if c is None:
        return []
    out = []
    for f in [*c.not_found, *(F(a.field) for a in c.abstentions if a.reason.startswith("conflicting sources"))]:
        why = next((a.reason for a in c.abstentions if a.field == f.value and not a.field.startswith("note:")), None)
        out.append({"field": f.value, "label": (FIELD_LABELS_ZH if lang == "zh" else FIELD_LABELS)[f],
                    "reason": reason_words(why or NOT_FOUND_REASON, lang), "reason_raw": why or NOT_FOUND_REASON,
                    "multi": f in MULTI_VALUED_CONTRACT_FIELDS})
    return out


def _facility_rows(agreed: Facility, books: Facility | None, lang: Lang = "en") -> list[dict[str, Any]]:
    none = t(lang, "none", "无")

    def pct(v: int | None) -> str:
        return fmt_pct(bp(v)) if v else none

    def cov(f: Facility, kind: str) -> str:
        c = next((c for c in f.covenants if c.kind.value == kind), None)
        if c is None:
            return none
        if c.clean_down_days is not None:
            return t(lang, f"zero for {c.clean_down_days} consecutive days a year",
                     f"每年须有连续 {c.clean_down_days} 天额度为零")
        return f"{Ratio.of(bp(c.threshold_bp or 0)).text}×"

    def fee(f: Facility) -> str:
        return t(lang, f"{pct(f.fee_bp_per_advance)} per {f.fee_period_days} days",
                 f"每 {f.fee_period_days} 天 {pct(f.fee_bp_per_advance)}") if f.fee_bp_per_advance else none

    rows = [(t(lang, "Limit", "额度"), fmt_yuan(agreed.limit_fen), books and fmt_yuan(books.limit_fen)),
            (t(lang, "Interest rate", "利率"), pct(agreed.rate_bp), books and pct(books.rate_bp)),
            (t(lang, "Periodic fee", "周期费用"), fee(agreed), books and fee(books)),
            (t(lang, "Upfront fee", "前端费用"), pct(agreed.upfront_fee_bp), books and pct(books.upfront_fee_bp)),
            (t(lang, "Lead time", "放款提前期"), _days(agreed.lead_time_days, False, lang),
             books and _days(books.lead_time_days, False, lang)),
            (t(lang, "Advance rate", "垫款比例"), pct(agreed.advance_rate_bp), books and pct(books.advance_rate_bp)),
            (t(lang, "Minimum DSCR", "最低偿债覆盖率"), cov(agreed, "DSCR_MIN"), books and cov(books, "DSCR_MIN")),
            (t(lang, "Maximum leverage", "最高杠杆"), cov(agreed, "LEVERAGE_MAX"), books and cov(books, "LEVERAGE_MAX")),
            (t(lang, "Clean-down", "额度清零期"), cov(agreed, "CLEAN_DOWN"), books and cov(books, "CLEAN_DOWN"))]
    return [{"label": label, "agreement_display": a, "books_display": b, "same": b is not None and a == b}
            for label, a, b in rows]


def facility_summary(f: Facility, lang: Lang = "en") -> str:
    """"¥350,000.00 at 7.80% · 80% advance · 0.25% per 30 days · 3-day lead time"."""
    parts = [t(lang, f"{fmt_yuan(f.limit_fen)} at {fmt_pct(bp(f.rate_bp))}", f"{fmt_yuan(f.limit_fen)}，利率 {fmt_pct(bp(f.rate_bp))}")]
    if f.advance_rate_bp:
        parts.append(t(lang, f"{fmt_pct(bp(f.advance_rate_bp))} advance", f"垫款 {fmt_pct(bp(f.advance_rate_bp))}"))
    if f.fee_bp_per_advance:
        parts.append(t(lang, f"{fmt_pct(bp(f.fee_bp_per_advance))} per {f.fee_period_days} days",
                       f"每 {f.fee_period_days} 天 {fmt_pct(bp(f.fee_bp_per_advance))}"))
    parts.append(t(lang, "same-day funding" if f.lead_time_days == 0 else f"{f.lead_time_days}-day lead time",
                   "当日放款" if f.lead_time_days == 0 else f"提前 {f.lead_time_days} 天放款"))
    cd = next((c.clean_down_days for c in f.covenants if c.clean_down_days), None)
    if cd:
        parts.append(t(lang, f"line at zero {cd} days a year", f"每年有 {cd} 天额度清零"))
    return " · ".join(parts)


def _registry_name(state: FinancialState | None, counterparty_id: str) -> str | None:
    cp = next((c for c in (state.counterparties if state else []) if c.id == counterparty_id), None)
    return cp.name if cp else None


def _name(state: FinancialState | None, counterparty_id: str) -> str:
    cp = next((c for c in (state.counterparties if state else []) if c.id == counterparty_id), None)
    return cp.name if cp else counterparty_id


_KIND_TEXT = {DocumentKind.BUYER_CONTRACT: ("Buyer contract", "买方合同"),
              DocumentKind.LENDER_AGREEMENT: ("Lender agreement", "贷款方协议"),
              DocumentKind.CAPEX_CONTRACT: ("Capex contract", "设备采购合同")}


def _kind_text(kind: DocumentKind, lang: Lang) -> str:
    en, zh = _KIND_TEXT[kind]
    return t(lang, en, zh)


def refiled(record: ContractRecord | ContractGuardRow) -> bool:
    """A record the owner filed again under another counterparty (`POST /documents/{id}/refile`): closed without a
    decision on its text, and superseded by the new record. A confirmed contract superseded by a later one stays CONFIRMED."""
    return record.superseded_by is not None and record.status == DocumentStatus.REJECTED


def _status_text(record: ContractRecord, lang: Lang, today: int | None, state: FinancialState | None = None,
                 records: Sequence[ContractRecord | ContractGuardRow] = ()) -> str:
    """Where the document stands, in the owner's words, with when it was decided as a distance from today."""
    when = when_text(record.decided_day, today, lang) if today is not None and record.decided_day is not None else ""
    if refiled(record):
        to = next((r for r in records if r.id == record.superseded_by), None)
        later = _registry_name(state, to.counterparty_id) if to is not None else None
        return t(lang, f"Filed again under {later}" if later else "Filed again under another counterparty",
                 f"已改为归入{later}" if later else "已改为归入其他对方")
    if record.status == DocumentStatus.CONFIRMED:
        return t(lang, f"Confirmed by you {when}".strip(), f"{when}经您确认".strip())
    if record.status == DocumentStatus.REJECTED:
        return t(lang, f"Rejected by you {when}".strip(), f"{when}被您拒绝".strip())
    if record.blocked and all(f.kind == PARTY_NOT_NAMED for f in record.flags if f.blocking):
        return t(lang, "Cannot be confirmed: it does not name the counterparty you chose", "无法确认：文件没有列明您选择的对方")
    if record.blocked:
        return t(lang, "Cannot be confirmed: it carries text addressed to the agent", "无法确认：其中含有写给代理的文字")
    return t(lang, "Waiting for your review", "等待您审核")


def _status_tone(record: ContractRecord) -> str:
    if record.status == DocumentStatus.CONFIRMED:
        return "ok"
    if record.status == DocumentStatus.REJECTED:
        return "mute"
    return "bad" if record.blocked else "warn"


def reading_status_text(status: str, lang: Lang) -> str:
    """The reading's status as a sentence the page shows as it is: the agent read it, could not, or found terms that disagree."""
    if status == "COMPILED":
        return t(lang, "The agent read this document.", "代理已读取此文件。")
    if status == "CONFLICTING_SOURCES":
        return t(lang, "The agent found terms that contradict each other.", "代理发现条款相互矛盾。")
    return t(lang, "The agent could not read this document.", "代理无法读取此文件。")


def replacement_words(record: ContractRecord | ContractGuardRow, records: Sequence[ContractRecord | ContractGuardRow], lang: Lang,
                      today: int | None, state: FinancialState | None = None) -> dict[str, Any]:
    """What a later confirmed buyer contract means for this one, in the owner's words: `replaces` is the earlier contract this
    one superseded, `superseded_by` the later one that superseded this. The ids stay in their fields; the sentences say when.
    A document the owner filed again under another counterparty (`refiled`) is said as that: who it was under, who it is under
    now, by their registry names."""
    # A confirmed contract this one replaced comes before a record the owner filed again under another counterparty: the
    # refile-closed record was never "the contract you confirmed" (REG-5).
    replaced = (next((r for r in records if r.superseded_by == record.id and not refiled(r)), None)
                or next((r for r in records if r.superseded_by == record.id), None))
    later = next((r for r in records if r.id == record.superseded_by), None) if record.superseded_by else None

    def when(r: ContractRecord | ContractGuardRow | None) -> str:
        said = when_text(r.decided_day, today, lang) if r is not None and today is not None and r.decided_day is not None else ""
        return said or t(lang, "earlier", "之前")

    replaces_text: str | None
    superseded_text: str | None
    if replaced is not None and refiled(replaced):
        before = _registry_name(state, replaced.counterparty_id)
        replaces_text = (t(lang, f"You filed this document here instead of under {before}", f"您已将此文件从{before}改归于此")
                         if before else t(lang, "You filed this document here instead", "您已将此文件改归于此"))
    else:
        replaces_text = t(lang, f"Replaces the contract you confirmed {when(replaced)}",
                          f"取代您{when(replaced)}确认的合同") if replaced else None
    if record.superseded_by and refiled(record):
        now = _registry_name(state, later.counterparty_id) if later is not None else None
        superseded_text = (t(lang, f"You filed this document again under {now}", f"您已将此文件改为归入{now}")
                           if now else t(lang, "You filed this document again under another counterparty",
                                         "您已将此文件改为归入其他对方"))
    else:
        superseded_text = t(lang, f"Replaced by a contract you confirmed {when(later)}",
                            f"已被您{when(later)}确认的合同取代") if record.superseded_by else None
    return {
        "replaces": replaced.id if replaced else None,
        "replaces_text": replaces_text,
        "superseded_by": record.superseded_by,
        "superseded_by_text": superseded_text,
    }


def record_summary(record: ContractRecord, state: FinancialState | None, lang: Lang = "en",
                   today: int | None = None, records: Sequence[ContractRecord | ContractGuardRow] = ()) -> dict[str, Any]:
    if record.kind in CONTRACT_READING_KINDS and record.contract is not None:
        n_blank = len(blanks(record))
        summary = t(lang, f"{len(record.contract.terms)} terms read, {n_blank} left blank",
                    f"已读取 {len(record.contract.terms)} 项条款，{n_blank} 项留空")
    else:
        ts = record.term_sheet
        summary = (facility_summary(ts.proposed_facility, lang) if ts and ts.proposed_facility
                   else t(lang, "the agent could not read a facility from it", "代理无法从中读出融资安排"))
    return {
        "id": record.id, "kind": record.kind.value, "kind_text": _kind_text(record.kind, lang), "title": record.title,
        "counterparty_id": record.counterparty_id,
        "counterparty_name": _name(state, record.counterparty_id), "status": record.status.value,
        "status_text": _status_text(record, lang, today, state, records), "status_tone": _status_tone(record),
        "uploaded_day": record.uploaded_day, "decided_day": record.decided_day, "decided_seq": record.decided_seq,
        "uploaded_when": when_text(record.uploaded_day, today, lang) if today is not None else None,
        "decided_when": (when_text(record.decided_day, today, lang)
                         if today is not None and record.decided_day is not None else None),
        "linked_facility_id": record.linked_facility_id, "summary": summary, "blocked": record.blocked,
        "flags": len(record.flags), "source": record.source, **replacement_words(record, records, lang, today, state),
        "label": (AI_LABEL if lang != "zh" else AI_LABEL_ZH) if record.status != DocumentStatus.CONFIRMED
        else t(lang, "Read by the agent, confirmed by you", "由代理读取，经您确认"),
    }


def record_view(record: ContractRecord, state: FinancialState | None, lang: Lang = "en",
                today: int | None = None, records: Sequence[ContractRecord | ContractGuardRow] = (),
                short_names: Mapping[str, Sequence[str]] | None = None) -> dict[str, Any]:
    """The review screen. `named_parties` are the parties the reading found, each with the registry counterparty it is
    (`on_books_id`, by the party check's matcher; `short_names` are the short names the owner gave customers it added)."""
    anchor = state.as_of if state is not None else None
    view = record_summary(record, state, lang, today, records)
    view.update({
        "named_parties": named_parties(record, state.counterparties if state is not None else [], short_names),
        "doc_hash": record.doc_hash,
        "document": {"doc_id": record.document.doc_id, "text": record.document.text},
        "ai_label": AI_LABEL_ZH if lang == "zh" else AI_LABEL, "ai_label_zh": AI_LABEL_ZH,
        "flags": [{"kind": f.kind, "kind_text": flag_kind_text(f.kind, lang), "blocking": f.blocking,
                   "note": (party_note(f, record, _registry_name(state, record.counterparty_id), lang)
                            if f.kind in PARTY_FLAG_KINDS else flag_note(f.kind, f.blocking, f.note, lang)),
                   "note_raw": f.note, "quote": f.span.text,
                   "span": {"start": f.span.start, "end": f.span.end}} for f in record.flags],
        "can_confirm": record.status == DocumentStatus.PROPOSED and not record.blocked,
    })
    if record.contract is not None:
        c = record.contract
        view.update({
            "reading_status": c.status.value, "reading_text": reading_status_text(c.status.value, lang),
            "compiler": c.compiler, "prompt_version": c.prompt_version,
            "chunks": c.chunks,
            "terms": [term_view(x, anchor, lang, today) for x in c.terms],
            "blanks": blanks(record, lang),
            "notes": [{"field": a.field.removeprefix("note:"), "reason": reason_words(a.reason, lang),
                       "reason_raw": a.reason} for a in c.abstentions if a.field.startswith("note:")],
        })
    if record.term_sheet is not None:
        ts = record.term_sheet
        target = record.linked_facility_id or record.suggested_facility_id
        books = next((f for f in (state.facilities if state else []) if f.id == target), None)
        agreed = ts.proposed_facility
        view.update({
            "reading_status": ts.status.value, "reading_text": reading_status_text(ts.status.value, lang),
            "compiler": ts.compiler, "prompt_version": ts.prompt_version,
            "clauses": [{"field": cl.field, "value_text": cl.value_text, "quote": cl.span.text,
                         "span": {"start": cl.span.start, "end": cl.span.end}} for cl in ts.clauses],
            "facility": None if agreed is None else {
                "kind": agreed.kind.value, "summary": facility_summary(agreed, lang),
                "all_in_rate_display": fmt_pct(bp(ts.all_in_rate_bp)) if ts.all_in_rate_bp is not None else None,
                "repayment": agreed.repayment.value,
                "tier3": [{"field": cl.field, "quote": cl.span.text} for cl in ts.tier3_clauses],
            },
            "suggested_facility_id": record.suggested_facility_id,
            "suggested_facility_name": next((f.name for f in (state.facilities if state else [])
                                             if f.id == record.suggested_facility_id), None),
            "compared_with": books.id if books is not None else None,
            "comparison": _facility_rows(agreed, books, lang) if agreed is not None else [],
            "notes": [{"field": a.field, "reason": reason_words(a.reason, lang), "reason_raw": a.reason}
                      for a in ts.abstentions],
        })
    return view


__all__ = ["AI_LABEL", "FIELD_LABELS", "blanks", "facility_summary", "flag_kind_text", "reading_status_text",
           "reason_words", "record_summary", "record_view", "refiled", "replacement_words", "term_display", "term_view"]
