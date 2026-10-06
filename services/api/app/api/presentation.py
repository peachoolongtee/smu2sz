"""Presentation helpers for the owner's screens: business words for what the engine already decided.

Nothing here prices, projects or decides. Every amount and rate is read from an engine result (an alert's priced
suggestion, a queued operation, the books) and only put into a sentence, so the web app can show it without
computing anything (INVARIANT 13). Facility and buyer names come from the books; ids stay available beside them.
"""

from __future__ import annotations

import re
from typing import Any

from app.alerts import Alert, AlertKind
from app.domain.models import FinancialState, Mandate
from app.domain.money import bp, fmt_pct, fmt_yuan, fmt_yuan_short
from app.financial.invoices import InvoiceRef, issue_terms

Lang = str  # "en" | "zh"


def t(lang: Lang, en: str, zh: str) -> str:
    return zh if lang == "zh" else en


def facility_name(state: FinancialState, facility_id: str | None) -> str:
    if not facility_id:
        return ""
    return next((f.name for f in state.facilities if f.id == facility_id), facility_id)


def lead_days(state: FinancialState, facility_id: str | None) -> int:
    return next((f.lead_time_days for f in state.facilities if f.id == facility_id), 0)


def party_name(state: FinancialState, party_id: str | None) -> str:
    if not party_id:
        return ""
    return next((c.name for c in state.counterparties if c.id == party_id), party_id)


def buyer_of_receivable(state: FinancialState, receivable_id: str | None) -> str | None:
    if not receivable_id:
        return None
    r = next((r for r in state.receivables if r.id == receivable_id), None)
    if r is not None:
        return r.counterparty_id
    # a recurring invoice not issued yet: "RI:<buyer>:<n>"
    if receivable_id.startswith("RI:"):
        parts = receivable_id.split(":")
        if len(parts) >= 2:
            return parts[1]
    return None


def receivable_face(state: FinancialState, receivable_id: str | None) -> int | None:
    if not receivable_id:
        return None
    r = next((r for r in state.receivables if r.id == receivable_id), None)
    if r is not None:
        return r.face_fen
    if receivable_id.startswith("RI:"):
        buyer = receivable_id.split(":")[1]
        ri = next((x for x in state.recurring_invoices if x.counterparty_id == buyer), None)
        return ri.face_fen if ri is not None else None
    return None


def invoice_words(state: FinancialState, receivable_id: str | None, lang: Lang) -> str:
    """"the ¥420,000.00 invoice to Foshan Home Retail Co." (or the id when the books do not name it)."""
    if not receivable_id:
        return ""
    buyer = party_name(state, buyer_of_receivable(state, receivable_id))
    face = receivable_face(state, receivable_id)
    if face is not None and buyer:
        return t(lang, f"the {fmt_yuan(face)} invoice to {buyer}", f"{buyer} 的 {fmt_yuan(face)} 发票")
    if buyer:
        return t(lang, f"the invoice to {buyer}", f"{buyer} 的发票")
    return t(lang, f"invoice {receivable_id}", f"发票 {receivable_id}")


_RI_TOKEN = re.compile(r"(?<![\w:-])RI:[\w-]+:\d+(?![\w:-])")


def invoice_due_day(state: FinancialState, receivable_id: str) -> int | None:
    """The day an invoice falls due: issue day plus its terms. For a recurring invoice not issued yet ("RI:<buyer>:<n>",
    n its issue day) the terms are the ones the clock will write on it (`issue_terms`)."""
    r = next((r for r in state.receivables if r.id == receivable_id), None)
    if r is not None:
        return r.issue_day + r.terms_days
    parts = receivable_id.split(":")
    if parts[0] != "RI" or len(parts) != 3 or not parts[2].isdigit():
        return None
    ri = next((x for x in state.recurring_invoices if x.counterparty_id == parts[1]), None)
    if ri is None:
        return None
    day = int(parts[2])
    terms = issue_terms(state, InvoiceRef(receivable_id, ri.counterparty_id, day), ri.face_fen, ri.terms_days)["terms_days"]
    return day + terms if isinstance(terms, int) else None


def _shares_face(state: FinancialState, receivable_id: str) -> bool:
    """Whether the books hold another invoice to the same buyer for the same face: another open invoice, or a recurring
    invoice that keeps generating them."""
    buyer, face = buyer_of_receivable(state, receivable_id), receivable_face(state, receivable_id)
    if any(r.id != receivable_id and r.counterparty_id == buyer and r.face_fen == face and r.status in ("OPEN", "FINANCED")
           for r in state.receivables):
        return True
    return any(x.counterparty_id == buyer and x.face_fen == face and x.every_days > 0 for x in state.recurring_invoices)


def _invoice_in_words(state: FinancialState, receivable_id: str) -> str | None:
    """The business words for an invoice id the books know (with its due day when another invoice looks the same)."""
    if receivable_face(state, receivable_id) is None:
        return None
    words = invoice_words(state, receivable_id, "en")
    due = invoice_due_day(state, receivable_id)
    if due is not None and _shares_face(state, receivable_id):
        words += f" due day {due}"
    return words


def in_words(state: FinancialState, text: str) -> str:
    """Server text with invoice, facility and buyer ids replaced by their names (ids are on the audit level)."""
    out = text
    out = _RI_TOKEN.sub(lambda m: _invoice_in_words(state, m.group(0)) or m.group(0), out)
    for rid in sorted((r.id for r in state.receivables if not r.id.startswith("RI:")), key=len, reverse=True):
        out = re.sub(rf"(?<![\w:-]){re.escape(rid)}(?![\w:-])", lambda m: _invoice_in_words(state, m.group(0)) or m.group(0), out)
    for f in state.facilities:
        out = re.sub(rf"(?<![\w:-]){re.escape(f.id)}(?![\w:-])", f.name, out)
    for c in state.counterparties:
        if c.id != c.name:
            out = re.sub(rf"(?<![\w:-]){re.escape(c.id)}(?![\w:-])", c.name, out)
    return out


def fmt_short(fen: int) -> str:
    """Overview precision ("¥240k"); the rounding rule lives in app.domain.money (INVARIANT 9)."""
    return fmt_yuan_short(fen)


# ---------------------------------------------------------------- days, as the owner reads them

def when_text(day: int | None, today: int, lang: Lang) -> str:
    """A simulated day as a distance from today ("in 12 days", "today", "3 days ago"): Business mode never says
    "day N"; the Demo views keep the day numbers."""
    if day is None:
        return ""
    n = day - today
    if n == 0:
        return t(lang, "today", "今天")
    if n == 1:
        return t(lang, "tomorrow", "明天")
    if n == -1:
        return t(lang, "yesterday", "昨天")
    if n > 0:
        return t(lang, f"in {n} days", f"{n} 天后")
    return t(lang, f"{-n} days ago", f"{-n} 天前")


def relative_days(text: str, today: int, lang: Lang) -> str:
    """Server sentences written with day numbers ("lands on day 37", "by day 47", "lasts to day 41", "(day 12)", "第 37 天"),
    re-said as distances from today for the Business pages. The Demo views show the originals. English engine text inside a
    Chinese page is rewritten too, since the engine writes English."""
    def on(m: re.Match[str]) -> str:
        return when_text(int(m.group(1)), today, "en")

    def by(m: re.Match[str]) -> str:
        n = int(m.group(1)) - today
        if n <= 0:
            return "by today"
        return "within 1 day" if n == 1 else f"within {n} days"

    def through(m: re.Match[str]) -> str:
        return f"for the next {max(int(m.group(1)) - today, 0)} days"

    if lang == "zh":
        text = re.sub(r"第 (\d+) 天", lambda m: when_text(int(m.group(1)), today, "zh"), text)
    text = re.sub(r"\bthrough day (\d+)\b", through, text)
    text = re.sub(r"\bby day (\d+)\b", by, text)
    text = re.sub(r"\brepaid day (\d+)\b", lambda m: "repaid " + on(m), text)
    text = re.sub(r"\bdue day (\d+)\b", lambda m: "due " + on(m), text)
    text = re.sub(r"\b(?:on|for) day (\d+)\b", on, text)
    text = re.sub(r"\bto day (\d+)\b", lambda m: "until " + on(m), text)
    text = re.sub(r"\(day (\d+)\)", lambda m: "(" + on(m) + ")", text)
    text = re.sub(r", day (\d+)\b", lambda m: ", " + on(m), text)
    return text


# ---------------------------------------------------------------- one funding leg


def leg_words(state: FinancialState, kind: str, facility_id: str | None, receivable_id: str | None, amount_fen: int | None,
              lang: Lang) -> str:
    fac = facility_name(state, facility_id)
    amount = fmt_yuan(amount_fen or 0)
    if kind == "SUBMIT_INVOICE_FOR_FINANCING":
        inv = invoice_words(state, receivable_id, lang)
        return t(lang, f"Finance {amount} of {inv} on {fac}", f"以{inv}在{fac}融资 {amount}")
    if kind == "DRAW_FACILITY":
        return t(lang, f"Draw {amount} on {fac}", f"从{fac}提款 {amount}")
    if kind == "REPAY_FACILITY":
        return t(lang, f"Repay {amount} on {fac}", f"向{fac}还款 {amount}")
    if kind == "APPLY_FOR_FACILITY":
        return t(lang, f"Apply for {amount} on {fac}", f"申请{fac} {amount}")
    if kind == "RECEIVE_PAYMENT":
        inv = invoice_words(state, receivable_id, lang)
        return t(lang, f"Collect {amount} on {inv}", f"收回{inv}的 {amount}")
    return f"{kind.replace('_', ' ').capitalize()} {amount}".strip()


def short_kind(kind: str, lang: Lang) -> str:
    words = {
        "SUBMIT_INVOICE_FOR_FINANCING": ("invoice financing", "发票融资"),
        "DRAW_FACILITY": ("credit line draw", "信用额度提款"),
        "REPAY_FACILITY": ("repayment", "还款"),
        "APPLY_FOR_FACILITY": ("facility application", "融资申请"),
        "RECEIVE_PAYMENT": ("payment receipt", "收款入账"),
        "ACCEPT_OFFER": ("buyer agreement", "买方协议"),
        "RECORD_COMMITMENT": ("buyer agreement", "买方协议"),
    }
    en, zh = words.get(kind, (kind.replace("_", " ").lower(), kind))
    return t(lang, en, zh)


def cure_legs(state: FinancialState, alert: Alert, today: int, lang: Lang) -> list[dict[str, Any]]:
    """The alert's suggestions as business legs. Costs and rates are the engine's (the suggestion's own pricing);
    the landing day is the ADR-0010 rule, request day plus the facility's lead time, for a draw or an advance."""
    legs: list[dict[str, Any]] = []
    for i, s in enumerate(alert.suggested):
        lands = (today + lead_days(state, s.facility_id)
                 if s.operation_kind in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING") else None)
        end = alert.inputs.get(f"cure_end_day_{i}")
        legs.append({
            "index": i,
            "operation_kind": s.operation_kind,
            "label": leg_words(state, s.operation_kind, s.facility_id, s.receivable_id, s.amount_fen, lang),
            "facility_id": s.facility_id,
            "facility_name": facility_name(state, s.facility_id),
            "receivable_id": s.receivable_id,
            "buyer_name": party_name(state, buyer_of_receivable(state, s.receivable_id)) or None,
            "amount_fen": s.amount_fen,
            "amount_display": fmt_yuan(s.amount_fen) if s.amount_fen is not None else None,
            "cost_fen": s.cost_fen,
            "cost_display": fmt_yuan(s.cost_fen) if s.cost_fen is not None else None,
            "rate_text": fmt_pct(s.annual_rate.value, 1) if s.annual_rate is not None else None,
            "cost_days": s.cost_days,
            "cost_due_day": int(end) if end else None,
            "lands_day": lands,
            "lands_when": when_text(lands, today, lang) if lands is not None else None,
            "above_apr_cap": s.above_apr_cap,
        })
    return legs


def needs_owner_reason(mandate: Mandate, legs: list[dict[str, Any]], lang: Lang) -> str | None:
    over = [leg for leg in legs if leg["above_apr_cap"]]
    if not over:
        return None
    cap = fmt_pct(bp(mandate.max_apr_bp))
    rate = next((leg["rate_text"] for leg in over if leg["rate_text"]), None)
    if rate:
        return t(lang, f"The yearly cost of {rate} is above the {cap} limit you signed for funding without your approval.",
                 f"年化成本 {rate} 高于您签署的无需批准融资上限 {cap}。")
    return t(lang, f"The yearly cost is above the {cap} limit you signed for funding without your approval.",
             f"年化成本高于您签署的无需批准融资上限 {cap}。")


# ---------------------------------------------------------------- an approval row


def approval_words(state: FinancialState, op: dict[str, Any], kind: str | None, today: int, alert: Alert | None,
                   lang: Lang, plan_costs: dict[tuple[str, str, str | None, int], Any] | None = None) -> dict[str, Any]:
    """Business fields for one queued operation: the question, the amount, what it costs (from the alert whose cure
    it is, when that alert is still open; or from the router's cost line when the operation is a leg of the recommended
    plan, `plan_costs` keyed by kind, facility, receivable and amount), when the cash lands, and the names behind the ids."""
    kind = kind or str(op.get("kind") or "")
    facility_id = op.get("facility_id")
    receivable_id = op.get("receivable_id")
    amount = op.get("amount_fen", op.get("advance_fen"))
    amount_display = fmt_yuan(amount) if isinstance(amount, int) else None
    what = short_kind(kind, lang)
    if amount_display:
        headline = t(lang, f"Approve {amount_display} of {what}?", f"批准 {amount_display} 的{what}？")
    else:
        headline = t(lang, f"Approve this {what}?", f"批准这项{what}？")
    lands = (int(op.get("day", today)) + lead_days(state, facility_id)
             if kind in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING") else None)
    cost_display = rate_text = None
    cost_due_day = None
    is_plan_leg = ":plan:" in str(op.get("op_id") or "")
    line = (plan_costs or {}).get((kind, facility_id or "", receivable_id, amount)) if is_plan_leg else None
    if line is not None:
        cost_display = fmt_yuan(line.fen)
        m = re.search(r"effective annual cost (\S+) is above", line.approval_reason or "")
        rate_text = m.group(1) if m else None
    elif alert is not None and not is_plan_leg:
        for i, s in enumerate(alert.suggested):
            if (s.operation_kind == kind and s.facility_id == facility_id and s.receivable_id == receivable_id
                    and s.amount_fen == amount):
                if s.cost_fen is not None:
                    cost_display = fmt_yuan(s.cost_fen)
                if s.annual_rate is not None:
                    rate_text = fmt_pct(s.annual_rate.value, 1)
                end = alert.inputs.get(f"cure_end_day_{i}")
                cost_due_day = int(end) if end else None
                break
    buyer = party_name(state, buyer_of_receivable(state, receivable_id)) or None
    # What happens if the owner declines: for an approval born of a reserve alert, the alert's own shortfall sentence
    # (the same inputs the home reads), written relative to today; otherwise the request is simply closed.
    if_decline = t(lang, "Nothing runs; the request is closed.", "不会执行任何操作；该请求关闭。")
    if alert is not None and alert.kind == AlertKind.RESERVE_BREACH_AHEAD:
        short = fmt_yuan(alert.amount_fen or 0)
        if alert.inputs.get("cure_restores_reserve") == "false":
            zero_when = when_text(int(alert.inputs.get("zero_day", today)), today, lang)
            if_decline = t(lang, f"Cash goes below zero {zero_when}.", f"现金将在{zero_when}跌破零。")
        else:
            worst_when = when_text(int(alert.inputs.get("worst_day", alert.day or today)), today, lang)
            if_decline = t(lang, f"{short} below your minimum cash reserve {when_text(alert.day, today, lang)}; the gap peaks at "
                                 f"{alert.inputs.get('max_shortfall', short)} {worst_when}.",
                           f"{when_text(alert.day, today, lang)}比最低现金储备低 {short}；缺口在{worst_when}最大，为 "
                           f"{alert.inputs.get('max_shortfall', short)}。")
    return {
        "headline": headline,
        "what": leg_words(state, kind, facility_id, receivable_id, amount if isinstance(amount, int) else None, lang),
        "facility_name": facility_name(state, facility_id) or None,
        "buyer_name": buyer,
        "invoice": invoice_words(state, receivable_id, lang) or None,
        "cost_display": cost_display,
        "rate_text": rate_text,
        "cost_due_day": cost_due_day,
        "lands_day": lands,
        "lands_when": when_text(lands, today, lang) if lands is not None else None,
        "if_decline": if_decline,
        "protects": (t(lang, f"It keeps cash above your minimum cash reserve for the next "
                             f"{max(int(alert.inputs['last_day']) - today, 0)} days.",
                       f"它使现金在未来 {max(int(alert.inputs['last_day']) - today, 0)} 天保持在最低现金储备以上。")
                     if alert is not None and alert.inputs.get("last_day") and alert.committed_cure else None),
    }
