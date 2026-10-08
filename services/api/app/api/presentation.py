"""Presentation helpers for the owner's screens: business words for what the engine already decided.

Nothing here prices, projects or decides. Every amount and rate is read from an engine result (an alert's priced
suggestion, a queued operation, the books) and only put into a sentence, so the web app can show it without
computing anything (INVARIANT 13). Facility and buyer names come from the books; ids stay available beside them.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

from app.alerts import Alert, AlertKind
from app.domain.models import Contingency, FinancialState, Mandate
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


_OPERATION_WORDS = {
    "DRAW_FACILITY": "draw on",
    "SUBMIT_INVOICE_FOR_FINANCING": "finance an invoice on",
    "REPAY_FACILITY": "repay",
    "APPLY_FOR_FACILITY": "apply for",
}
_OPERATION_TOKEN = re.compile(r"(?<![\w:-])(" + "|".join(_OPERATION_WORDS) + r")(?![\w:-])")


def operation_words(text: str) -> str:
    """The engine's operation-kind tokens in the owner's words ("DRAW_FACILITY Bank credit line" reads "draw on Bank
    credit line"); a token that opens a sentence keeps its capital."""
    def word(m: re.Match[str]) -> str:
        w = _OPERATION_WORDS[m.group(1)]
        return w[0].upper() + w[1:] if m.start() == 0 or text[max(0, m.start() - 2):m.start()] == ". " else w
    return _OPERATION_TOKEN.sub(word, text)


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
    """The business words for an invoice id the books know; when another invoice looks the same, with its due day as a
    distance from the books' first open day ("due in 77 days"), since a Business page never says "day N"."""
    if receivable_face(state, receivable_id) is None:
        return None
    words = invoice_words(state, receivable_id, "en")
    due = invoice_due_day(state, receivable_id)
    if due is not None and _shares_face(state, receivable_id):
        words += f" due {when_text(due, state.as_of_day, 'en')}"
    return words


# The executor's and the alert engine's clause for a leg above the mandate's rate ceiling, in the owner's words (the same
# words `needs_owner_reason` uses): "the 15.00% limit you signed for funding without your approval".
_CEILING_CLAUSE = re.compile(r"effective annual cost (\S+%) is above the mandate's (\S+%) ceiling for what the agent may borrow alone")
_CEILING_SHORT = re.compile(r"above the (\S+%) ceiling for what the agent may borrow alone")


def owner_words(text: str) -> str:
    """Engine clauses re-said in the owner's words: the rate ceiling is "the limit you signed for funding without your
    approval", never "what the agent may borrow alone", and "the owner's approval" is "your approval". Amounts and rates
    are kept exactly."""
    out = _CEILING_CLAUSE.sub(lambda m: f"the yearly cost of {m.group(1)} is above the {m.group(2)} limit you signed for funding "
                                        f"without your approval", text)
    out = _CEILING_SHORT.sub(lambda m: f"above the {m.group(1)} limit you signed for funding without your approval", out)
    return out.replace("needs the owner's approval", "needs your approval")


def in_words(state: FinancialState, text: str) -> str:
    """Server text with invoice, facility and buyer ids replaced by their names (ids are on the audit level), and the rate
    ceiling clause in the owner's words (`owner_words`)."""
    out = operation_words(owner_words(text))
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
    """Server sentences written with day numbers ("lands on day 37", "by day 47", "paid on or before day 2", "lasts to day 41",
    "(day 37 to day 47)", "from day 0 to day 32", "arrives day 21", "(day 12)", "第 37 天"), re-said as distances from today
    for the Business pages. The Demo views show the originals. English engine text inside a Chinese page is rewritten too,
    since the engine writes English."""
    def on(m: re.Match[str]) -> str:
        return when_text(int(m.group(1)), today, "en")

    def by(m: re.Match[str]) -> str:
        n = int(m.group(1)) - today
        if n <= 0:
            return "by today"
        return "within 1 day" if n == 1 else f"within {n} days"

    def through(m: re.Match[str]) -> str:
        return f"for the next {max(int(m.group(1)) - today, 0)} days"

    def span(m: re.Match[str]) -> str:
        return f"from {when_text(int(m.group(1)), today, 'en')} to {when_text(int(m.group(2)), today, 'en')}"

    if lang == "zh":
        text = re.sub(r"第 (\d+) 天", lambda m: when_text(int(m.group(1)), today, "zh"), text)
    text = re.sub(r"\bfrom day (\d+) to day (\d+)\b", span, text)
    text = re.sub(r"\(day (\d+) to day (\d+)\)", lambda m: "(" + span(m) + ")", text)
    text = re.sub(r"\bthrough day (\d+)\b", through, text)
    text = re.sub(r"\b(?:by|on or before) day (\d+)\b", by, text)
    text = re.sub(r"\brepaid day (\d+)\b", lambda m: "repaid " + on(m), text)
    text = re.sub(r"\barrives day (\d+)\b", lambda m: "arrives " + on(m), text)
    text = re.sub(r"\bdue day (\d+)\b", lambda m: "due " + on(m), text)
    text = re.sub(r"\b(?:on|for) day (\d+)\b", on, text)
    def until(m: re.Match[str]) -> str:
        when = on(m)
        return "until " + (when[3:] + " from now" if when.startswith("in ") else when)

    text = re.sub(r"\bto day (\d+)\b", until, text)
    text = re.sub(r"\(day (\d+)\)", lambda m: "(" + on(m) + ")", text)
    text = re.sub(r", day (\d+)\b", lambda m: ", " + on(m), text)
    return text


_CURE_CLAUSE = re.compile(r"A committed cure exists: (?P<legs>.+?), cost (?P<cost>¥[\d,.]+) \((?P<rate>[^()]*)\)(?P<rest>[^.]*)\.")


def fallback_words(text: str) -> str:
    """The alert's own cure, said as a fallback beside a recommended plan that is not it. The alert detail quotes its cure
    ("A committed cure exists: draw on … + finance an invoice on … ¥336,000.00, cost ¥2,994.08 (11.2% a year for 29 days).");
    under a recommendation of a different plan that sentence contradicts the plan's own amounts and cost, so on the Business
    home it reads as what it is: another way, priced on its own basis, and not the one recommended. Business strings only:
    the raw alert detail is untouched."""
    def say(m: re.Match[str]) -> str:
        legs = m.group("legs").replace(" + ", " and ")
        legs = re.sub(r"(finance an invoice on [^+]*?) (¥[\d,.]+)(?= and |$)", r"\1 for \2", legs)
        return f"A fallback also exists: {legs}, at {m.group('cost')} ({m.group('rate')}); FLOW recommends the plan above."
    return _CURE_CLAUSE.sub(say, text)


_ADMISSIBLE = (
    (re.compile(r"\bnot admissible\b"), "not within your limits"),
    (re.compile(r"\badmissible, but the owner must approve it"), "within your limits, but you must approve it"),
    (re.compile(r"\badmissible\b"), "within your limits"),
)


# "(commitment CMT-a78afaa5becb5273)": a record id, which belongs to the audit level.
_COMMITMENT_REF = re.compile(r"\s*\(commitment CMT-[0-9a-f]+\)")
# "… the cash lands in 3 days after the 3-day lead time": the landing is said once, as a distance from today.
_LEAD_TIME = re.compile(r" after the \d+-day lead time")


def limits_words(text: str) -> str:
    """The router's "admissible" is the engine's word for a plan inside the owner's signed limits: Business strings say so."""
    for pattern, words in _ADMISSIBLE:
        text = pattern.sub(words, text)
    return text


def business_text(state: FinancialState, text: str | None, today: int, lang: Lang = "en") -> str | None:
    """One engine sentence as a Business page shows it: names for ids, the owner's words for the ceiling clause, distances
    from today for its day numbers and "within your limits" for the engine's "admissible". None stays None; the raw
    sentence stays beside it for the audit level."""
    if text is None:
        return None
    return _COMMITMENT_REF.sub("", _LEAD_TIME.sub("", limits_words(relative_days(in_words(state, text), today, lang))))


# The executor's working behind a rate: "(all charges on ¥200,000.00 held 10 days (day 37 to day 47), annualised = 32.52%)".
_FORMULA_PAREN = re.compile(r"\s*\(all charges on [^()]*(?:\([^()]*\)[^()]*)*\)")
_YEARLY_COST = re.compile(r"\b(yearly cost of )(\d+(?:\.\d+)?)%")


def approval_reason_words(state: FinancialState, text: str | None, today: int, lang: Lang = "en") -> str | None:
    """Why a request needs the owner, for the card, as a full sentence: the Business sentence without the executor's working (the "all charges on
    ¥… annualised = …" parenthesis stays at the audit level) and the yearly cost to one decimal, as the home says it
    ("32.5% a year"), never 32.52% beside 32.5%."""
    out = business_text(state, text, today, lang)
    if out is None:
        return None
    out = _FORMULA_PAREN.sub("", out)
    return _sentence(_YEARLY_COST.sub(lambda m: f"{m.group(1)}{fmt_pct(Fraction(m.group(2)) / 100, 1)}", out))


def plan_when(state: FinancialState, plan: dict[str, Any] | None, today: int, lang: Lang = "en") -> dict[str, Any] | None:
    """A serialised funding plan with `*_when` beside every sentence that can carry a day number: the plan's and each cost
    line's `approval_reason` and `not_executable_reason`, each cost line's `label`, each violation's `message` and
    `cure_note`, each rejected candidate's `note`. The raw fields are untouched; nothing is recomputed."""
    if plan is None:
        return None
    out = dict(plan)
    for key in ("approval_reason", "not_executable_reason"):
        if out.get(key):
            out[f"{key}_when"] = business_text(state, out[key], today, lang)
    out["costs"] = [{**c, "label_when": business_text(state, c.get("label"), today, lang),
                     **{f"{k}_when": business_text(state, c[k], today, lang) for k in ("approval_reason", "not_executable_reason") if c.get(k)}}
                    for c in out.get("costs") or []]
    out["violations"] = [{**v, "message_when": business_text(state, v.get("message"), today, lang),
                          "cure_note_when": business_text(state, v.get("cure_note"), today, lang)}
                         for v in out.get("violations") or []]
    out["rejected"] = [{**r, "note_when": business_text(state, r.get("note"), today, lang)} for r in out.get("rejected") or []]
    return out


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
    for leg, name in zip(legs, leg_names(state, [(x["facility_id"], x["amount_fen"]) for x in legs]), strict=True):
        leg["name_display"] = name
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
                   lang: Lang, plan_costs: dict[tuple[str, str, str | None, int], Any] | None = None,
                   after: str | None = None) -> dict[str, Any]:
    """Business fields for one queued operation: the question, the amount, what it costs (from the alert whose cure
    it is, when that alert is still open; or from the router's cost line when the operation is a leg of the recommended
    plan, `plan_costs` keyed by kind, facility, receivable and amount), when the cash lands, and the names behind the ids.
    `after` is the cure's after-state sentence, the one the home says (`home.cure_after_words`); `protects` carries it."""
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
        "protects": after,
    }


# ---------------------------------------------------------------- a log entry as a business event (wayfinder #35)

_RATE_IN_REASON = re.compile(r"effective annual cost (\d+(?:\.\d+)?)% is above the mandate's (\S+%) ceiling")
_RECEIPT_DETAIL = re.compile(r"^Received \S+ on \S+ \((.+?)\)")
_MONEY_KINDS = ("SUBMIT_INVOICE_FOR_FINANCING", "DRAW_FACILITY")


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".。!?" else text + ("。" if "一" <= text[-1] <= "鿿" else ".")


def _stop(text: str, lang: Lang) -> str:
    """The sentence's full stop, unless the text already ends in one (a buyer named "… Co.")."""
    return text if text.endswith((".", "。")) else text + t(lang, ".", "。")


def _op_amount(payload: dict[str, Any]) -> int | None:
    amount = payload.get("advance_fen", payload.get("amount_fen"))
    return amount if isinstance(amount, int) else None


def _landing_day(state: FinancialState, payload: dict[str, Any], day: int | None) -> int | None:
    """The day the cash of a draw or advance lands: the funding lot the operation created (ADR-0010), else the request day
    plus the facility's lead time."""
    op_id = str(payload.get("op_id") or "")
    for lot in state.lots:
        if op_id and (lot.id == op_id or lot.id.startswith(op_id + "#")):
            return lot.arrival_day
    request = day if day is not None else payload.get("day")
    return request + lead_days(state, payload.get("facility_id")) if isinstance(request, int) else None


def _landing_sentence(landing: int | None, today: int, lang: Lang) -> str | None:
    if landing is None:
        return None
    n = landing - today
    when = when_text(landing, today, lang)
    if n > 0:
        return t(lang, f"Funds arrive {when}.", f"资金将于{when}到账。")
    if n == 0:
        return t(lang, "Cash received today.", "资金今天已到账。")
    return t(lang, f"Cash received {when}.", f"资金已于{when}到账。")


def _what_asked(state: FinancialState, kind: str, payload: dict[str, Any], lang: Lang) -> str:
    """What was asked, in words ("finance ¥80,000.00 of the ¥420,000.00 invoice to X on Y"), lower-cased to follow a colon."""
    amount = _op_amount(payload)
    if amount is not None:
        words = leg_words(state, kind, payload.get("facility_id"), payload.get("receivable_id"), amount, lang)
    else:
        words = t(lang, f"the {short_kind(kind, 'en')}", f"{short_kind(kind, 'zh')}")
    return words[:1].lower() + words[1:] if lang != "zh" else words


def _asked_words(state: FinancialState, kind: str, payload: dict[str, Any], lang: Lang) -> str | None:
    """The thing asked for, as a noun phrase that follows "You approved" or "Waiting for your approval:": "¥200,000.00 of
    invoice financing", "a ¥150,000.00 draw on the Bank credit line", "an application for ¥600,000.00 on Equipment lease",
    "the receipt of ¥255,013.80 from Foshan Home Retail Co."; None for a kind with no such reading."""
    amount = _op_amount(payload)
    if amount is None:
        return None
    money, fac = fmt_yuan(amount), facility_name(state, payload.get("facility_id"))
    if kind == "SUBMIT_INVOICE_FOR_FINANCING":
        return t(lang, f"{money} of {short_kind(kind, 'en')}", f"{money} 的{short_kind(kind, 'zh')}")
    if kind == "DRAW_FACILITY":
        return t(lang, f"a {money} draw on the {fac}", f"从{fac}提取 {money}")
    if kind == "APPLY_FOR_FACILITY":
        return t(lang, f"an application for {money} on {fac}", f"在{fac}申请 {money}")
    if kind == "RECEIVE_PAYMENT":
        buyer = party_name(state, buyer_of_receivable(state, payload.get("receivable_id")))
        return (t(lang, f"the receipt of {money} from {buyer}", f"来自{buyer}的 {money} 入账") if buyer
                else t(lang, f"the receipt of {money}", f"{money} 入账"))
    return None


def result_words(state: FinancialState, *, kind: str, status: str, payload: dict[str, Any], day: int | None, today: int,
                 lang: Lang = "en") -> str | None:
    """What came of the owner's decision on an approval, as one sentence: "¥200,000.00 of invoice financing was requested
    today; the cash lands in 3 days." (the landing is the funding lot's own day, ADR-0010), or "You declined ...". None for a
    kind or status with no such reading; the caller keeps the executor's own sentence then."""
    asked = _asked_words(state, kind, payload, lang)
    if asked is None:
        return None
    if status == "REFUSED":
        return _stop(t(lang, f"You declined {asked}", f"您已拒绝{asked}"), lang)
    if status != "EXECUTED" or kind not in _MONEY_KINDS:
        return None
    asked = asked[:1].upper() + asked[1:] if lang == "en" else asked
    landing = _landing_day(state, payload, day)
    request = day if day is not None else payload.get("day")
    if landing is None or not isinstance(request, int):
        return None
    n = landing - today
    when = when_text(landing, today, lang)
    asked_when = when_text(request, today, lang)
    if n > 0:
        cash = t(lang, f"the cash lands {when}.", f"资金将于{when}到账。")
    elif n == 0:
        cash = t(lang, "the cash arrived today.", "资金今天已到账。")
    else:
        cash = t(lang, f"the cash arrived {when}.", f"资金已于{when}到账。")
    return t(lang, f"{asked} was requested {asked_when}; {cash}", f"{asked}已于{asked_when}提交；{cash}")


def agreement_words(state: FinancialState, counterparty_id: str, forward_value_fen: int, lang: Lang = "en") -> str:
    """"Agreement with Foshan Home Retail Co. recorded; concessions booked against your budget: ¥0.00." (the home's
    AGREEMENT event)."""
    buyer = party_name(state, counterparty_id)
    return t(lang, f"Agreement with {buyer} recorded; concessions booked against your budget: {fmt_yuan(forward_value_fen)}.",
             f"已记录与{buyer}的协议；已计入您预算的让步：{fmt_yuan(forward_value_fen)}。")


def _count(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    return len(value) if isinstance(value, list) else 0


def clock_words(payload: dict[str, Any], lang: Lang = "en") -> str | None:
    """A clock move in the owner's words: "4 days passed: the ¥45,000.00 debt payment went out and one invoice was issued."
    Built from the counts the operation recorded (scheduled cash movements posted, invoices issued, agreements expired or
    fulfilled, funding landed, loan and debt payments with their total); an item that did not happen is left out. None when
    the payload does not say how far the clock moved."""
    start, end = payload.get("from_day"), payload.get("to_day")
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    days = end - start
    head = t(lang, f"{days} day passed" if days == 1 else f"{days} days passed", f"过去了 {days} 天")
    en: list[str] = []
    zh: list[str] = []

    def add(n: int, one: str, many: str, zh_text: str) -> None:
        if n:
            en.append(one if n == 1 else many.format(n=n))
            zh.append(zh_text.format(n=n))

    debts = _count(payload, "posted_debt_service")
    total = payload.get("debt_service_fen")
    if debts:
        amount = fmt_yuan(abs(total)) if isinstance(total, int) else ""
        if debts == 1 and amount:
            en.append(f"the {amount} debt payment went out")
            zh.append(f"已支付 {amount} 的债务还款")
        else:
            en.append(f"{debts} debt payments{f' totalling {amount}' if amount else ''} went out")
            zh.append(f"已支付 {debts} 笔债务还款" + (f"，共 {amount}" if amount else ""))
    add(_count(payload, "posted_debt_payments"), "one loan payment was posted", "{n} loan payments were posted", "已入账 {n} 笔贷款还款")
    add(_count(payload, "settled_lot_ids"), "one funding request landed", "{n} funding requests landed", "{n} 笔融资已到账")
    add(_count(payload, "posted_flow_ids"), "one scheduled cash movement was recorded", "{n} scheduled cash movements were recorded",
        "已记录 {n} 笔计划收支")
    add(_count(payload, "issued_receivable_ids"), "one invoice was issued", "{n} invoices were issued", "已开出 {n} 张发票")
    add(_count(payload, "expired_commitment_ids"), "one agreement expired", "{n} agreements expired", "{n} 项协议已到期")
    add(_count(payload, "fulfilled_commitment_ids"), "one agreement was fulfilled", "{n} agreements were fulfilled", "{n} 项协议已履行")
    add(_count(payload, "lapsed_commitment_ids"), "one early-payment agreement ended", "{n} early-payment agreements ended",
        "{n} 项提前付款协议已终止")
    if not en:
        return t(lang, f"{head}; nothing was due.", f"{head}，没有到期事项。")
    if lang == "zh":
        return f"{head}：{'，'.join(zh)}。"
    return f"{head}: {', '.join(en[:-1])}{' and ' if len(en) > 1 else ''}{en[-1]}."


def event_words(state: FinancialState, *, kind: str, status: str, payload: dict[str, Any], message: str,
                approval_id: str | None, day: int | None, today: int, lang: Lang = "en",
                decided: bool = False) -> dict[str, str | None]:
    """One operations-log entry as a business sentence: what happened in the owner's words, never the executor's own
    sentence. `event_text` is the sentence (the landing of a draw or advance is its second sentence) and `event_detail`
    one more sentence when there is something more to say, else None. Every figure is the operation's own amount, the
    executor's own rate and the funding lot's own landing day; nothing is priced here. An entry with no business reading
    (anything the executor says in its own words only) returns `event_text` None and the caller keeps the sentence it has.
    `decided` says the owner has since answered the approval a PENDING_APPROVAL entry waited on: the entry then reads in the
    past ("Queued for your approval"), never "Waiting", beside the entry of the decision."""
    none: dict[str, str | None] = {"event_text": None, "event_detail": None}
    if kind == "ADVANCE_CLOCK" and status == "EXECUTED":
        return {"event_text": clock_words(payload, lang), "event_detail": None}
    amount = _op_amount(payload)
    receivable_id = payload.get("receivable_id")
    facility_id = payload.get("facility_id")
    buyer = party_name(state, buyer_of_receivable(state, receivable_id)) if receivable_id else ""
    money = kind in _MONEY_KINDS and amount is not None
    approved = status == "EXECUTED" and approval_id is not None

    if status == "EXECUTED" and money and not approved:
        fac = facility_name(state, facility_id)
        landing = _landing_sentence(_landing_day(state, payload, day), today, lang)
        if kind == "SUBMIT_INVOICE_FOR_FINANCING":
            against = (t(lang, f"the {buyer} invoice", f"{buyer}的发票") if buyer else t(lang, "an invoice", "一张发票"))
            head = t(lang, f"{fmt_yuan(amount or 0)} of invoice financing drawn against {against}.",
                     f"已以{against}融资 {fmt_yuan(amount or 0)}。")
            detail = t(lang, f"Financed through {fac}.", f"通过{fac}融资。") if fac else None
        else:
            head = t(lang, f"{fmt_yuan(amount or 0)} drawn on the {fac}.", f"已从{fac}提取 {fmt_yuan(amount or 0)}。")
            detail = None
        return {"event_text": (head + t(lang, " ", "") + landing) if landing else head, "event_detail": detail}

    asked = _asked_words(state, kind, payload, lang)
    if status == "PENDING_APPROVAL" and asked is not None:
        lead = t(lang, "Queued for your approval" if decided else "Waiting for your approval",
                 "已提交请您批准" if decided else "等待您批准")
        reason = message.split("): ", 1)[1] if "): " in message else ""
        m = _RATE_IN_REASON.search(reason)
        if m:
            rate = fmt_pct(Fraction(m.group(1)) / 100, 1)
            return {"event_text": t(lang, f"{lead}: {asked} at {rate} a year, above the {m.group(2)} limit you "
                                          f"signed for funding without your approval.",
                                    f"{lead}：{asked}，年化成本 {rate}，高于您签署的无需批准融资上限 {m.group(2)}。"),
                    "event_detail": None}
        detail = _sentence(business_text(state, reason, today, lang) or "") if reason else None
        return {"event_text": _stop(f"{lead}: {asked}" if lang == "en" else f"{lead}：{asked}", lang), "event_detail": detail or None}

    if approved and asked is not None:
        landing = _landing_sentence(_landing_day(state, payload, day), today, lang) if money else None
        head = _stop(t(lang, f"You approved {asked}", f"您已批准{asked}"), lang)
        return {"event_text": (head + t(lang, " ", "") + landing) if landing else head, "event_detail": None}

    if status == "REFUSED" and approval_id is not None and message.startswith("Declined by the owner") and asked is not None:
        return {"event_text": _stop(t(lang, f"You declined {asked}", f"您已拒绝{asked}"), lang), "event_detail": None}

    if status == "REFUSED":
        reason = message.removeprefix("Refused: ").strip()
        asked = _what_asked(state, kind, payload, lang)
        why = _sentence(business_text(state, reason, today, lang) or "")
        return {"event_text": t(lang, f"{_stop(f'Refused: {asked}', lang)} {why}".strip(), f"{_stop(f'已拒绝：{asked}', lang)}{why}".strip()),
                "event_detail": None}

    if status == "EXECUTED" and kind == "RECEIVE_PAYMENT" and amount is not None and buyer:
        m = _RECEIPT_DETAIL.match(message)
        detail = _sentence(business_text(state, m.group(1), today, lang) or "") if m else None
        return {"event_text": _stop(t(lang, f"Received {fmt_yuan(amount)} from {buyer}", f"已收到{buyer}的 {fmt_yuan(amount)}"), lang),
                "event_detail": detail or None}
    return none


# ---------------------------------------------------------------- truth fields (wayfinder #30)


def business_action(outcome: str, counters: int) -> str:
    """What the owner should do about an offer, as distinct from the verifier's verdict code: a REJECT with counters
    is the action "counter"; a REJECT with none is "decline". ACCEPT → accept; NEEDS_OWNER_APPROVAL → needs_owner;
    anything else (NO_VERDICT, NO_DEAL) → cannot."""
    if outcome == "ACCEPT":
        return "accept"
    if outcome == "COUNTER" or (outcome == "REJECT" and counters > 0):
        return "counter"
    if outcome == "REJECT":
        return "decline"
    if outcome == "NEEDS_OWNER_APPROVAL":
        return "needs_owner"
    return "cannot"


def comparison_status(result: str, reasons: list[str], breach_day: int | None) -> str:
    """One word per comparison row so a page never ranks plans that are not comparable: `recommended` (the router's
    pick), `alternative` (admissible, dearer), `insufficient` (admissible sources, but the reserve still breaks),
    `unavailable` (a source that is not committed or cannot land in time), `blocked` (not admissible for any other
    reason: the plan breaks one of the owner's limits)."""
    if result == "SELECTED":
        return "recommended"
    if result == "ADMISSIBLE":
        return "alternative"
    if "RESERVE_BREACH" in reasons or breach_day is not None:
        return "insufficient"
    if "UNCOMMITTED_FACILITY" in reasons or "LEAD_TIME_TOO_LONG" in reasons:
        return "unavailable"
    return "blocked"


def comparison_reason(actions: list[dict[str, Any]], executable_now: bool) -> str | None:
    """Why an admissible row cannot run today, as a kind the web turns into words: `buyer_early_pay` when a leg is the
    buyer paying early (not an executor operation), `invoice_not_issued` when an advance waits for its invoice."""
    if executable_now:
        return None
    if any(a.get("kind") == "EARLY_PAY" for a in actions):
        return "buyer_early_pay"
    if any(a.get("kind") == "FINANCE_INVOICE" and (a.get("available_from_day") or 0) > (a.get("day") or 0) for a in actions):
        return "invoice_not_issued"
    return None


# The row the API adds for the plan the next-step card recommends when it is the alert's own cure, not a router row.
RECOMMENDED_PLAN_KEY = "recommended_plan"
KIND_FOR_OPERATION = {"DRAW_FACILITY": "DRAW", "SUBMIT_INVOICE_FOR_FINANCING": "FINANCE_INVOICE"}


def leg_names(state: FinancialState, legs: list[tuple[str | None, int | None]]) -> list[str]:
    """The source each leg draws on, by name ("Bank credit line"); a source used twice carries its amount, so two advances
    on one facility are told apart ("Invoice financing, ¥80k")."""
    names = [facility_name(state, fid) for fid, _ in legs]
    return [n if names.count(n) == 1 else f"{n}, {fmt_short(amount or 0)}" for n, (_, amount) in zip(names, legs, strict=True)]


def plan_name(state: FinancialState, facility_ids: list[str | None]) -> str:
    """A plan named by its sources ("Bank credit line + Invoice financing"), each source once."""
    return " + ".join(dict.fromkeys(facility_name(state, f) for f in facility_ids if f))


def row_legs(state: FinancialState, actions: list[dict[str, Any]], leg_costs_fen: list[int]) -> list[dict[str, Any]]:
    """A comparison row's legs for the page: the source's name, the leg's amount and what it costs, in the order the router
    priced them (`leg_costs_fen` runs in the actions' order). Empty when the router priced no legs or not one per action."""
    if not actions or len(actions) != len(leg_costs_fen):
        return []
    names = leg_names(state, [(a.get("facility_id"), a.get("amount_fen")) for a in actions])
    return [{"index": i, "name_display": name, "facility_id": a.get("facility_id"), "amount_fen": a.get("amount_fen"),
             "amount_display": fmt_yuan(a.get("amount_fen") or 0), "cost_fen": cost, "cost_display": fmt_yuan(cost)}
            for i, (a, name, cost) in enumerate(zip(actions, names, leg_costs_fen, strict=True))]


def recommended_row(state: FinancialState, action: dict[str, Any], today: int, lang: Lang) -> dict[str, Any]:
    """The plan the next-step card recommends, as a comparison row, for the case where it is the alert's own cure and so
    none of the router's rows. Every figure is the card's own (the legs the alert priced); nothing is priced here."""
    legs = [{"index": leg["index"], "name_display": leg["name_display"], "facility_id": leg["facility_id"],
             "amount_fen": leg["amount_fen"], "amount_display": leg["amount_display"], "cost_fen": leg["cost_fen"],
             "cost_display": leg["cost_display"]} for leg in action["legs"] if leg["operation_kind"] in KIND_FOR_OPERATION]
    priced = [leg for leg in legs if leg["cost_fen"] is not None]
    total = sum(leg["cost_fen"] for leg in priced)
    total_display = action.get("cost_total_display") or "—"
    equation = (" + ".join(leg["cost_display"] for leg in priced) + f" = {total_display}") if len(priced) > 1 else total_display
    actions = [{"kind": KIND_FOR_OPERATION[leg["operation_kind"]], "facility_id": leg["facility_id"], "day": today,
                "amount_fen": leg["amount_fen"], "amount_display": leg["amount_display"], "receivable_id": leg["receivable_id"],
                "repay_day": None, "rate_bp": None, "lands_day": leg["lands_day"], "available_from_day": today}
               for leg in action["legs"] if leg["operation_kind"] in KIND_FOR_OPERATION]
    reason = action.get("needs_owner_reason")
    return {
        "key": RECOMMENDED_PLAN_KEY, "label": t(lang, "Recommended plan", "推荐方案"),
        "components": [leg["label"] for leg in action["legs"]], "components_when": [leg["label"] for leg in action["legs"]],
        "actions": actions, "cost_fen": total, "cost_display": equation, "total_fen": total, "total_display": total_display,
        "result": "ADMISSIBLE", "reasons": [], "breach_day": None, "note": "", "note_when": "",
        "needs_owner_approval": bool(action.get("needs_owner")), "approval_reason": reason or "", "approval_reason_when": reason,
        "executable_now": True, "not_executable_reason": "", "not_executable_reason_when": None, "shortfall_fen": None,
        "shortfall_display": None, "worst_day": None, "status": "alternative", "reason_kind": None, "selected": False,
        "legs": legs, "name_display": plan_name(state, [leg["facility_id"] for leg in legs]), "offset_fen": None, "offset_display": None,
    }



def _role_reason(row: dict[str, Any], role: str, recommended_cost: int | None, today: int, lang: Lang) -> str | None:
    """One sentence on why a row is where it is, for a row that is not the recommended plan."""
    kind = row.get("reason_kind")
    if role == "insufficient":
        when = when_text(row.get("breach_day"), today, lang)
        short = row.get("shortfall_display")
        if short and when:
            return t(lang, f"Cash still falls below your reserve {when}; {short} short at the worst point.",
                     f"现金仍将在{when}低于储备；最低点还差 {short}。")
        return t(lang, "It does not cover the gap.", "无法覆盖缺口。")
    if role == "blocked":
        return t(lang, "It breaks one of your limits.", "违反您的某项限额。")
    if role == "unavailable" or row.get("executable_now") is False:
        if kind == "buyer_early_pay":
            return t(lang, "Only if the buyer agrees to pay early.", "须买方同意提前付款。")
        if kind == "invoice_not_issued":
            return t(lang, "It waits for the invoice to be issued.", "须等发票开出。")
        return t(lang, "A source in this plan is not available today.", "此方案中的某个资金来源今天无法使用。")
    cost = row.get("cost_fen")
    if recommended_cost is not None and isinstance(cost, int) and cost < recommended_cost:
        return t(lang, "Cheaper, but it is not the plan FLOW recommends.", "更便宜，但不是 FLOW 推荐的方案。")
    return t(lang, "Within your limits, but dearer than the recommended plan.", "在您的限额内，但比推荐方案更贵。")


def with_roles(rows: list[dict[str, Any]], action: dict[str, Any] | None, state: FinancialState, today: int,
               lang: Lang) -> tuple[list[dict[str, Any]], str | None]:
    """The comparison as the owner reads it: every row says what it is for the owner (`role`) and why (`role_reason`), and the
    plan the next-step card recommends is in the list. `role` is `recommended` (the plan the card shows), `alternative`
    (within the limits, not chosen) or the row's own status (`insufficient`, `unavailable`, `blocked`). When the card shows
    the router's cheapest plan that row is the recommended one; when it shows the alert's cure (the cheaper plan needs
    several approvals) the cure is added as a row, listed first, and the router's cheapest becomes an alternative whose reason
    names the approvals it would ask for. Returns the rows and the recommended row's key. `status` and `selected` stay the
    router's own; no plan is ranked or priced here (`funding/recommend.py` already decided)."""
    reserve = bool(action) and action is not None and action.get("kind") == "RESERVE_BREACH_AHEAD"
    source = action.get("plan_source") if reserve and action is not None else None
    out: list[dict[str, Any]] = []
    recommended_cost: int | None = None
    cure: dict[str, Any] | None = None
    if source == "alert" and action is not None:
        cure = recommended_row(state, action, today, lang)
        recommended_cost = cure["total_fen"] if all(leg["cost_fen"] is not None for leg in cure["legs"]) else None
        cheaper = action.get("cheaper_option")
        cure["role"] = "recommended"
        cure["role_reason"] = (
            t(lang, f"The next step: it needs one approval; the cheapest plan ({cheaper['cost_total_display']} in all) needs "
                    f"{cheaper['approvals']} separate approvals.",
              f"下一步所用方案：只需一次批准；最便宜的方案（合计 {cheaper['cost_total_display']}）需要 {cheaper['approvals']} 次单独批准。")
            if cheaper else action.get("why"))
        out.append(cure)
    elif source == "router":
        recommended_cost = next((r["cost_fen"] for r in rows if r.get("result") == "SELECTED"), None)
    for r in rows:
        status = r.get("status") or "alternative"
        if source == "router" and r.get("result") == "SELECTED":
            role, reason = "recommended", t(lang, "The cheapest plan your committed facilities can fund in time.",
                                            "您已承诺的额度能及时覆盖缺口的最便宜方案。")
        elif status in ("recommended", "alternative"):
            if source == "alert":
                role = "alternative"
                cheaper = action.get("cheaper_option") if action is not None else None
                if cheaper and r.get("result") == "SELECTED":
                    reason = t(lang, f"Cheapest in all, but it needs {cheaper['approvals']} separate approvals; the recommended plan "
                                     f"needs one.", f"合计最便宜，但需要 {cheaper['approvals']} 次单独批准；推荐方案只需一次。")
                else:
                    reason = _role_reason(r, role, recommended_cost, today, lang)
            elif status == "recommended":  # nothing is recommended against it (no gap, or a repayment): the router's pick stands
                role = "recommended"
                reason = (t(lang, "The cheapest plan your committed facilities can fund in time.",
                            "您已承诺的额度能及时覆盖缺口的最便宜方案。") if r.get("actions") else None)
            else:
                role, reason = "alternative", _role_reason(r, "alternative", recommended_cost, today, lang)
        else:
            role, reason = status, _role_reason(r, status, recommended_cost, today, lang)
        out.append({**r, "role": role, "role_reason": reason})
    key = next((r["key"] for r in out if r["role"] == "recommended"), None)
    return out, key


def counter_economics(obligations: list[Any], state: FinancialState, mandate: Mandate) -> dict[str, Any] | None:
    """The parts behind a counter's cost, from the verifier's own valuation of the counter's obligations: each
    obligation's 12-month value (a price adjustment is negative: it pays the supplier), the funding cost (the positive
    parts), the offset (the negative parts) and the net. `supplier_cost_fen` stays the verifier's floored figure; this
    only shows what it floors. None when no committed source prices concessions."""
    from app.financial import value_concessions
    from app.funding import NoPermanentSourceError, marginal_cost

    try:
        rate, fid = marginal_cost(state, mandate)
    except NoPermanentSourceError:
        return None
    fac = next((f for f in state.facilities if f.id == fid), None)
    label = f"committed marginal source: {fac.name if fac else fid} {fmt_pct(rate.value, 4)}"
    values = value_concessions(list(obligations), state, rate, label, mandate.forward_concession_horizon_days)
    kinds = {o.id: str(getattr(o.type, "value", o.type)) for o in obligations}
    parts = [{"obligation_id": v.obligation_id, "type": kinds.get(v.obligation_id, ""),
              "value_fen": v.value_fen, "value_display": fmt_yuan(v.value_fen), "basis": v.basis}
             for v in values]
    funding = sum(p["value_fen"] for p in parts if p["value_fen"] > 0)
    offset = sum(p["value_fen"] for p in parts if p["value_fen"] < 0)
    net = funding + offset
    # "≈ ¥0" (the same in both languages) when the offset covers the funding cost (the verifier's floor), else the net

    net_words = "≈ ¥0" if net <= 0 else fmt_yuan(net)
    return {"components": parts, "net_words": net_words,
 "funding_cost_fen": funding, "funding_cost_display": fmt_yuan(funding),
            "offset_fen": offset, "offset_display": fmt_yuan(-offset), "net_fen": net, "net_display": fmt_yuan(net),
            "is_net": offset < 0 < funding}


_COUNTED = re.compile(r"Σ over (\d+) invoices")


def concession_interpretation(cv: dict[str, Any], ob: Any | None, lang: Lang) -> str:
    """The reading of one concession value before its equation ("60-day terms add 15 days of financing to 13 expected
    invoices …"): typed fields of the obligation, the value's display strings and the invoice count the formula states.
    The words follow the value's sign (a shortening or a price adjustment pays the supplier, never "add -15 days") and
    the obligation's contingency (a claimed, unevidenced concession is never counted). Nothing is priced here; the words
    wrap figures the engine produced."""
    value_fen = int(cv.get("value_fen") or 0)
    value = cv.get("value_display") or fmt_yuan(value_fen)
    amount = fmt_yuan(abs(value_fen))
    kind = str(getattr(getattr(ob, "type", None), "value", getattr(ob, "type", ""))) if ob is not None else ""
    if ob is not None and ob.contingency == Contingency.CLAIMED_UNEVIDENCED:
        return str(cv.get("basis") or "")
    m = _COUNTED.search(cv.get("formula") or "")
    n = int(m.group(1)) if m else None
    if kind == "TERMS_EXTENSION" and ob is not None:
        delta = ob.days_delta or 0
        to = ob.target_terms_days
        per_fen = cv.get("per_invoice_fen")
        per = fmt_yuan(abs(int(per_fen))) if per_fen is not None else cv.get("per_invoice_display")
        invoices_en = f"{n if n is not None else 'the'} expected invoices"
        if delta < 0 or value_fen < 0:
            days = abs(delta)
            terms = (f"{to}-day terms" if to else f"{days} fewer days to pay") if lang == "en" else (f"{to} 天账期" if to else f"缩短 {days} 天")
            head = t(lang, f"{terms} take {days} days of financing off {invoices_en}",
                     f"{terms}让 {n if n is not None else ''} 张预期发票各少融资 {days} 天")
            per_text = (t(lang, f", about {per} each at your cheapest committed source", f"，按您最便宜的已承诺资金来源每张约 {per}")
                        if per else "")
            return head + per_text + t(lang, f", saving {amount} over 12 months.", f"，12 个月共节省 {amount}。")
        terms = (f"{to}-day terms" if to else f"{delta} more days to pay") if lang == "en" else (f"{to} 天账期" if to else f"再延长 {delta} 天")
        head = t(lang, f"{terms} add {delta} days of financing to {invoices_en}",
                 f"{terms}让 {n if n is not None else ''} 张预期发票各多融资 {delta} 天")
        per_text = t(lang, f", about {per} each at your cheapest committed source", f"，按您最便宜的已承诺资金来源每张约 {per}") if per else ""
        return head + per_text + t(lang, f": {value} over 12 months.", f"：12 个月共 {value}。")
    if kind == "PRICE_ADJUSTMENT" and ob is not None:
        rate = fmt_pct(bp(ob.rate_bp)) if ob.rate_bp is not None else ""
        invoices = n if n is not None else "the"
        if value_fen < 0:
            return t(lang, f"A {rate} price adjustment on {invoices} future invoices pays you {amount} over 12 months.",
                     f"未来 {n if n is not None else ''} 张发票 {rate} 的价格调整，12 个月为您带来 {amount}。")
        return t(lang, f"A {rate} price adjustment on {invoices} future invoices costs you {amount} over 12 months.",
                 f"未来 {n if n is not None else ''} 张发票 {rate} 的价格调整，12 个月让您多付出 {amount}。")
    if kind == "CONTINGENT_REBATE" and ob is not None:
        if ob.rate_bp is not None and ob.base.amount_fen is not None:
            rate, base = fmt_pct(bp(ob.rate_bp)), fmt_yuan(ob.base.amount_fen)
            if ob.contingency == Contingency.CONTINGENT:
                return t(lang, f"A {rate} rebate on {base} of purchases, counted at its maximum: {value}.",
                         f"对 {base} 采购的 {rate} 返利，按最大值计：{value}。")
            return t(lang, f"A {rate} rebate on {base} of purchases: {value}.", f"对 {base} 采购的 {rate} 返利：{value}。")
        return t(lang, f"A fixed rebate of {value}.", f"固定返利 {value}。")
    if kind == "IMMEDIATE_DISCOUNT":
        return t(lang, "Settled in cash now, so it is not a forward concession; the discount is checked against its own cap.",
                 "现在以现金结算，不属于远期让利；该折扣按其单独上限检查。")
    return str(cv.get("basis") or "")
