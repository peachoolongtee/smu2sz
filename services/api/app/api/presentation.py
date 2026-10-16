"""Presentation helpers for the owner's screens: business words for what the engine already decided.

Nothing here prices, projects or decides. Every amount and rate is read from an engine result (an alert's priced
suggestion, a queued operation, the books) and only put into a sentence, so the web app can show it without
computing anything (INVARIANT 13). Facility and buyer names come from the books; ids stay available beside them.
"""

from __future__ import annotations

import hmac
import re
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from typing import Any

from app.alerts import Alert, AlertKind
from app.api.engine_zh import translate
from app.books import current_books
from app.compiler.cross_check import DISAGREE_PREFIX
from app.domain.models import (
    BaseKind,
    Commitment,
    CommitmentStatus,
    Contingency,
    DurationKind,
    FinancialState,
    Mandate,
    Obligation,
    ObligationType,
)
from app.domain.money import bp, fmt_pct, fmt_yuan, fmt_yuan_short, post
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


_RI_TOKEN = re.compile(r"(?<![\w:-])RI:[\w-]+:\d+(?![\w-]|:\w)")


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


# The engine's own terms in the owner's words (audit section 16, wayfinder #65 Wave 7): a Business sentence never says "headroom" of the
# reserve, "trajectory", "Tier 2", "obligation" or "committed cure". The raw sentence (the audit level, the hash-chained log) keeps the
# engine's words; only the Business field is re-said. Order matters: the longer phrases first.
_OWNER_LAYER: tuple[tuple[re.Pattern[str], Any], ...] = tuple((re.compile(p), w) for p, w in (
    (r"\bDays? \d+(?: to \d+)? (?:are|is) below the (¥[\d,]+(?:\.\d+)?) reserve floor until then: the cash is not in before day (\d+)",
     r"Cash is below your \1 minimum cash reserve until the funds land on day \2"),
    (r"\bA committed cure exists:", "A funding plan is available:"),
    (r"\ba committed cure exists:", "a funding plan is available:"),
    (r"\bno committed plan restores the reserve; the cure that keeps cash at or above zero is:",
     "no funding plan restores your minimum cash reserve; the plan that keeps cash at or above zero is:"),
    (r"\bNo committed plan restores the reserve; the cure that keeps cash at or above zero is:",
     "No funding plan restores your minimum cash reserve; the plan that keeps cash at or above zero is:"),
    (r"\bReserve headroom thin\b", "Cash is close to your minimum"),
    # a covenant's headroom is the distance to its limit: said as above or below it
    (r"\(headroom [−-]([\d.]+×)\)", lambda m: f"({m.group(1)} below the limit)"),
    (r"\(headroom ([\d.]+×|undefined)\)", lambda m: f"({m.group(1)} above the limit)"),
    (r"\b(DSCR|Leverage) headroom below 0\.10×", r"\1 is within 0.10× of its limit"),
    (r"restore leverage headroom", "bring leverage back inside its limit"),
    (r"\bCash stays above the floor but only by (¥[\d,]+(?:\.\d+)?)", r"Cash stays above your minimum cash reserve by only \1"),
    (r"\((\d+) day\(s\) under 10% of the floor\)",
     lambda m: f"({m.group(1)} {'day' if m.group(1) == '1' else 'days'} with less than 10% of your minimum cash reserve to spare)"),
    (r"\bbelow the reserve floor\b", "below your minimum cash reserve"),
    (r"\bbelow the (¥[\d,]+(?:\.\d+)?) reserve floor\b", r"below your \1 minimum cash reserve"),
    (r"\bcash stays above the floor\b", "cash stays above your minimum cash reserve"),
    (r"\bthe conservative trajectory\b", "the cash forecast"),
    (r"\bThe conservative trajectory\b", "The cash forecast"),
    # the owner's signed mandate is "your signed limits"; the version stays, in words
    (r"\bMandate v(\d+) expires\b", r"Your signed limits (version \1) expire"),
    (r"\bMandate v(\d+) is valid\b", r"Your signed limits (version \1) are valid"),
    (r"\bMandate v(\d+) has been revoked\b", r"Your signed limits (version \1) have been revoked"),
    (r"\bMandate v(\d+)\b", r"Your signed limits (version \1)"),
    (r"\bmandate v(\d+) limit ([\d.×]+)", r"your signed limit \2 (version \1)"),
    (r"\bmandate v(\d+), current is v(\d+)", r"your signed limits (version \1), current is version \2"),
    (r"\bmandate v(\d+)\b", r"your signed limits (version \1)"),
    (r"\bTier 2: the owner applies; zero until committed", "Needs your approval: you apply; counted as zero until committed"),
    (r"\babove the Tier-2 threshold (¥[\d,]+(?:\.\d+)?)", r"above the \1 you allow without your approval"),
    (r"\babove the Tier-2 threshold\b", "above the limit you set for what needs your approval"),
    (r"\bTier[ -]?2\b", "needs your approval"),
    (r"\bobligation (?:OB|CTR)[\w:.#-]*", "the terms you agreed"),
    (r"\bbound obligations\b", "terms"),
    (r"\bobligations\b", "terms"),
))


def owner_words(text: str) -> str:
    """Engine clauses re-said in the owner's words: the rate ceiling is "the limit you signed for funding without your
    approval", never "what the agent may borrow alone", and "the owner's approval" is "your approval". Amounts and rates
    are kept exactly."""
    out = _CEILING_CLAUSE.sub(lambda m: f"the yearly cost of {m.group(1)} is above the {m.group(2)} limit you signed for funding "
                                        f"without your approval", text)
    out = _CEILING_SHORT.sub(lambda m: f"above the {m.group(1)} limit you signed for funding without your approval", out)
    out = out.replace("needs the owner's approval", "needs your approval")
    for pattern, words in _OWNER_LAYER:
        out = pattern.sub(words, out)
    return out


def in_words(state: FinancialState, text: str) -> str:
    """Server text with invoice, facility and buyer ids replaced by their names (ids are on the audit level), and the rate
    ceiling clause in the owner's words (`owner_words`)."""
    out = operation_words(owner_words(text))
    out = _RI_TOKEN.sub(lambda m: _invoice_in_words(state, m.group(0)) or m.group(0), out)
    for rid in sorted((r.id for r in state.receivables if not r.id.startswith("RI:")), key=len, reverse=True):
        out = re.sub(rf"(?<![\w:-]){re.escape(rid)}(?![\w-]|:\w)", lambda m: _invoice_in_words(state, m.group(0)) or m.group(0), out)
    for f in state.facilities:
        out = re.sub(rf"(?<![\w:-]){re.escape(f.id)}(?![\w-]|:\w)", f.name, out)
    for c in state.counterparties:
        if c.id != c.name:
            out = re.sub(rf"(?<![\w:-]){re.escape(c.id)}(?![\w-]|:\w)", c.name, out)
    return out


def fmt_short(fen: int) -> str:
    """Overview precision ("¥240k"); the rounding rule lives in app.domain.money (INVARIANT 9)."""
    return fmt_yuan_short(fen)


_TICK_STEPS = (1, 2, 5)  # times a power of ten
_MIN_TICK_STEP_FEN = 100_000  # never finer than ¥1,000: the short labels would repeat
_MAX_TICKS = 7
_MIN_TICKS = 3


def tick_label(value_fen: int) -> str:
    """A tick's label: the short formatter's, except zero, which is "¥0" (an axis has no use for the fen)."""
    return "¥0" if value_fen == 0 else fmt_short(value_fen)


def axis_ticks(min_fen: int, max_fen: int) -> list[dict[str, Any]]:
    """3 to 7 round ticks (`value_fen`, `label`) that cover [min_fen, max_fen] on a chart's money axis, ascending. The step is the
    smallest 1, 2 or 5 times a power of ten (at least ¥1,000) whose ticks fit in seven; the ticks run from the largest multiple of the
    step at or below the minimum to the smallest multiple at or above the maximum, so zero is among them whenever the range crosses or
    touches it. Labels are the short formatter's (zero is "¥0"), so a page never formats a tick."""
    lo_v, hi_v = min(min_fen, max_fen), max(min_fen, max_fen)
    step = _MIN_TICK_STEP_FEN
    while True:
        for m in _TICK_STEPS:
            size = step * m
            lo = (lo_v // size) * size
            hi = -((-hi_v) // size) * size
            if (hi - lo) // size + 1 <= _MAX_TICKS:
                ticks = list(range(lo, hi + 1, size))
                while len(ticks) < _MIN_TICKS:
                    ticks.append(ticks[-1] + size)
                return [{"value_fen": v, "label": tick_label(v)} for v in ticks]
        step *= 10


def series_axis(series: Sequence[Sequence[dict[str, Any]] | None], floor_fen: int | None = None,
                window_days: int | None = None) -> dict[str, Any] | None:
    """The money axis for any number of cash series (the points' `closing_fen`) and the reserve line drawn with them: its ticks and
    the domain they span. `window_days` keeps only the points within that many days of the first day drawn (the days a picture shows).
    None when there is no series to draw."""
    first = min((p["day"] for s in series if s for p in s), default=None)
    values = [p["closing_fen"] for s in series if s for p in s if window_days is None or p["day"] - first <= window_days]
    if not values:
        return None
    if floor_fen is not None:
        values.append(floor_fen)
    ticks = axis_ticks(min(values), max(values))
    return {"min_fen": ticks[0]["value_fen"], "max_fen": ticks[-1]["value_fen"], "ticks": ticks}


def series_axes(series: Sequence[Sequence[dict[str, Any]] | None], floor_fen: int | None, windows: Sequence[int]) -> dict[str, Any]:
    """`series_axis` for each window in days, keyed by the window ("30", "60", "120"): a page that switches between views reads the axis of
    the one it shows."""
    return {str(w): series_axis(series, floor_fen, w) for w in sorted(set(windows))}


# ---------------------------------------------------------------- days, as the owner reads them

def first_breach_ahead(traj: Any, today: int, floor: int) -> tuple[int, int] | None:
    """The first day from today on whose closing cash is below the reserve (day, closing fen), or None. The projection's
    own `first_breach_day` scans from day 0 and the closed days before today carry the opening cash, so when cash is already
    low it names a day in the past ("34 days ago", F01); the home speaks of what is ahead, and when today is already below
    the reserve the first breach is today. Never earlier than today."""
    hit = next((d for d in traj.days if d.day >= today and d.closing_fen < floor), None)
    return (max(hit.day, today), hit.closing_fen) if hit is not None else None


def whole(fen: int) -> str:
    """¥5,000 for a whole number of yuan, ¥3,027.77 otherwise (the limit the owner set): the KPIs' form, without the cents of a round sum."""
    return fmt_yuan(fen).removesuffix(".00")


def point_words(rows: list[dict[str, Any]] | None, today: int, lang: Lang) -> None:
    """The words of every point of a cash series drawn from `today` (the Home read's chart): `when`, the day as a distance from today
    ("in 30 days"), and `display`, the closing cash in the KPIs' form (`whole`). Every point has both, whatever its day: the words are
    made from the point's own day and closing cash, not looked up among the rail's events."""
    for row in rows or []:
        row["when"] = when_text(row["day"], today, lang)
        row["display"] = whole(row["closing_fen"])


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


def deadline_text(n: int) -> str:
    """A deadline `n` days from today, said for a CURRENT eligibility ("may still be settled early by today"): today and
    tomorrow are named, later is "within N days". A deadline that has passed (n < 0) is never "by today": an immutable
    event is re-said by `settlement_words` before this runs, so a past day here is only a safety net and says it passed."""
    if n == 0:
        return "by today"
    if n == 1:
        return "by tomorrow"
    if n > 1:
        return f"within {n} days"
    return "by a deadline that passed yesterday" if n == -1 else f"by a deadline that passed {-n} days ago"


PAST_CASH_DAY = "when approved"  # a facility's cash day already past: the cash comes once the facility is approved


def relative_days(text: str, today: int, lang: Lang) -> str:
    """Server sentences written with day numbers ("lands on day 37", "by day 47", "paid on or before day 2", "lasts to day 41",
    "(day 37 to day 47)", "from day 0 to day 32", "arrives day 21", "(day 12)", "第 37 天"), re-said as distances from today
    for the Business pages. The Demo views show the originals. English engine text inside a Chinese page is rewritten too,
    since the engine writes English."""
    def on(m: re.Match[str]) -> str:
        return when_text(int(m.group(1)), today, "en")

    def by(m: re.Match[str]) -> str:
        return deadline_text(int(m.group(1)) - today)

    def through(m: re.Match[str]) -> str:
        return f"for the next {max(int(m.group(1)) - today, 0)} days"

    def span(m: re.Match[str]) -> str:
        return f"from {when_text(int(m.group(1)), today, 'en')} to {when_text(int(m.group(2)), today, 'en')}"

    if lang == "zh":
        text = re.sub(r"第 (\d+) 天", lambda m: when_text(int(m.group(1)), today, "zh"), text)
    text = re.sub(r"\bfrom day (-?\d+) to day (-?\d+)\b", span, text)
    text = re.sub(r"\(day (-?\d+) to day (-?\d+)\)", lambda m: "(" + span(m) + ")", text)
    text = re.sub(r"\bthrough day (-?\d+)\b", through, text)
    text = re.sub(r"\b(?:by|on or before) day (-?\d+)\b", by, text)
    text = re.sub(r"\brepaid day (-?\d+)\b", lambda m: "repaid " + on(m), text)
    # A facility not yet in place whose cash day the router states as its lead time ("cash on day 21", "arrives day 21")
    # reads "13 days ago" once the clock is past it: that day means nothing today, so it says when the cash can come.
    text = re.sub(r"\b(cash on|arrives) day (-?\d+)\b",
                  lambda m: (("cash" if m.group(1) == "cash on" else "arrives") + " " + PAST_CASH_DAY)
                  if int(m.group(2)) < today else m.group(0), text)
    text = re.sub(r"\barrives day (-?\d+)\b", lambda m: "arrives " + on(m), text)
    text = re.sub(r"\bdue day (-?\d+)\b", lambda m: "due " + on(m), text)
    text = re.sub(r"\b(?:on|for) day (-?\d+)\b", on, text)
    def until(m: re.Match[str]) -> str:
        when = on(m)
        return "until " + (when[3:] + " from now" if when.startswith("in ") else when)

    text = re.sub(r"\brequested day (-?\d+)\b", lambda m: "requested " + on(m), text)
    text = re.sub(r"\bfrom day (-?\d+)\b", lambda m: "starting " + on(m), text)
    text = re.sub(r"\bto day (-?\d+)\b", until, text)
    text = re.sub(r"\(day (-?\d+)\)", lambda m: "(" + on(m) + ")", text)
    text = re.sub(r", day (-?\d+)\b", lambda m: ", " + on(m), text)
    return text


_CURE_CLAUSE = re.compile(r"A (?:committed cure exists|funding plan is available): (?P<legs>.+?), cost (?P<cost>¥[\d,.]+) \((?P<rate>[^()]*)\)"
                          r"(?P<rest>(?:[^.]|\.\d)*)\.")


def engine_sentence(state: FinancialState, text: str, today: int, lang: Lang, *, fallback: bool = False) -> str:
    """An engine sentence the home shows as it is (an alert's detail, a cost line's label): names for ids, distances from today, the owner's
    words, and in Chinese the engine-sentence templates. `fallback` says it as the alternative to a recommended plan (`fallback_words`)."""
    out = relative_days(in_words(state, text), today, lang)
    return in_language(fallback_words(out) if fallback else out, lang, state) or ""


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
_SENTENCE_THE = re.compile(r"(?<=[a-z0-9)]\. )the (?=¥|invoice|agreement)")
_LEAD_TIME = re.compile(r" after the \d+-day lead time")


def limits_words(text: str) -> str:
    """The router's "admissible" is the engine's word for a plan inside the owner's signed limits: Business strings say so."""
    for pattern, words in _ADMISSIBLE:
        text = pattern.sub(words, text)
    return text


# An event the log wrote on an earlier day names a deadline by its day number; read later, that day may have passed. The
# receipt's "up to ¥X more may be settled early by day 2" was true on day 2 and is history on day 34, so it is re-said before
# `relative_days` turns every day into a distance from today (a past deadline is never "by today", F03).
_WINDOW_CLAUSE = re.compile(r"; up to (¥[\d,.]+) more may be settled early by day (\d+)")
_STILL_DUE_PAST = re.compile(r"(¥[\d,.]+) still due on day (\d+)")
_PROMISED_FOR_DAY = re.compile(r"\bpromised for day (\d+)\b")
# A record id the owner never reads: "under commitment CMT-9c61e3666e753a1d", "Commitment CMT-… is ACTIVE", "revoke CMT-… first",
# "of accepted commitment CMT-…", "the earlier REVOKED commitment CMT-…". Said as the agreement with the buyer.
_COMMITMENT_ID = re.compile(r"(?:\b(?P<adj>[A-Z]{4,}|accepted) )?(?P<word>\b[Cc]ommitment )?(?<![\w-])(?P<id>CMT-[0-9a-f]+)")
_RECORD_ID = re.compile(r"\s*\((?:APR|OP)-[\w:-]+\)|(?<![\w-])(?:APR|OP)-[\w:-]+")


def until_text(n: int) -> str:
    """"until today" / "until tomorrow" / "until 5 days from now": the last day a thing could be done, for a deadline n days ahead."""
    return "until today" if n == 0 else "until tomorrow" if n == 1 else f"until {n} days from now"


def settlement_words(text: str, today: int, live: bool = False) -> str:
    """The early-payment window and the amount still due, said by their own day. A deadline still ahead is a claim about now
    only when the promise behind it is still live (`live`: the obligation is in the books and not paid in full): "may still be
    settled early by today"; otherwise it is the neutral "could be settled early until …". One that has passed is what
    happened ("the early-payment window for the other ¥X ended 32 days ago", "¥X was still due 2 days ago"). Anything else
    is untouched."""
    def window(m: re.Match[str]) -> str:
        n = int(m.group(2)) - today
        if n >= 0 and live:
            return f"; up to {m.group(1)} more may still be settled early {deadline_text(n)}"
        if n >= 0:
            return f"; up to {m.group(1)} more could be settled early {until_text(n)}"
        return f"; the early-payment window for the other {m.group(1)} ended {when_text(int(m.group(2)), today, 'en')}"

    def still_due(m: re.Match[str]) -> str:
        return f"{m.group(1)} was still due {when_text(int(m.group(2)), today, 'en')}" if int(m.group(2)) < today else m.group(0)

    def promised(m: re.Match[str]) -> str:
        n = int(m.group(1)) - today
        return f"due early {deadline_text(n)}" if n >= 0 else f"promised as an early payment due {when_text(int(m.group(1)), today, 'en')}"

    return _PROMISED_FOR_DAY.sub(promised, _STILL_DUE_PAST.sub(still_due, _WINDOW_CLAUSE.sub(window, text)))


def agreement_ref(text: str, agreements: Mapping[str, str] | None = None) -> str:
    """A commitment id in the owner's words: "the agreement with {buyer}" (the buyer when the caller knows whose commitment it
    is, else "the agreement"), "Commitment CMT-… is ACTIVE" reading "The agreement with … is ACTIVE"; the bracketed
    "(commitment CMT-…)" form is dropped."""
    def say(m: re.Match[str]) -> str:
        buyer = (agreements or {}).get(m.group("id"))
        adj = f"{m.group('adj').lower()} " if m.group("adj") else ""
        phrase = f"the {adj}agreement" + (f" with {buyer}" if buyer else "")
        capital = m.group("word") is not None and m.group("word")[0] == "C" and not m.group("adj")
        return phrase[0].upper() + phrase[1:] if capital else phrase

    out = _COMMITMENT_ID.sub(say, _COMMITMENT_REF.sub("", text))
    return re.sub(r"\b(earlier|other|first|later) the ", r"\1 ", out)


def business_text(state: FinancialState, text: str | None, today: int, lang: Lang = "en",
                  agreements: Mapping[str, str] | None = None, window_live: bool = False) -> str | None:
    """One engine sentence as a Business page shows it: names for ids, the owner's words for the ceiling clause, distances
    from today for its day numbers (a deadline that has already passed is said as past, never "by today") and "within your
    limits" for the engine's "admissible". `agreements` maps a commitment id to its buyer's name; `window_live` says the
    early-payment promise a settlement clause speaks of is still live (`live_windows`). None stays None; the raw sentence
    stays beside it for the audit level."""
    out = _owner_english(state, text, today, lang, agreements, window_live)
    return in_language(out, lang, state)


def _owner_english(state: FinancialState, text: str | None, today: int, lang: Lang = "en",
                   agreements: Mapping[str, str] | None = None, window_live: bool = False) -> str | None:
    """`business_text` before the language step: the engine sentence in the owner's English (names, distances from today, the owner's
    words). A caller that edits the sentence further (a full stop, a clause removed) edits this and says it in Chinese last."""
    if text is None:
        return None
    said = agreement_ref(_LEAD_TIME.sub("", limits_words(relative_days(in_words(state, settlement_words(text, today, window_live)), today, lang))),
                         agreements)
    return _SENTENCE_THE.sub("The ", said)  # an id at the start of a sentence became "the invoice to ...": it takes its capital


def book_names(state: FinancialState | None) -> list[str]:
    """The names the books give (buyers, facilities): carried over exactly in a Chinese sentence, never translated."""
    if state is None:
        return []
    return [*(c.name for c in state.counterparties), *(f.name for f in state.facilities), *(x.label for x in state.flows)]


_PLURAL_S = re.compile(r"\b(\d+) ([A-Za-z][A-Za-z-]*(?: [A-Za-z-]+)?)\(s\)")


def plural(text: str) -> str:
    """"1 day(s)" is "1 day" and "15 day(s)" is "15 days": the engine's hedged plural in the right number."""
    def say(m: re.Match[str]) -> str:
        return f"{m.group(1)} {m.group(2)}" + ("" if m.group(1) == "1" else "s")

    return _PLURAL_S.sub(say, text)


def in_language(text: str | None, lang: Lang, state: FinancialState | None = None) -> str | None:
    """The owner's English sentence in the page's language: Chinese through the engine-sentence templates (`engine_zh`), English with its
    plurals said right. A sentence no template knows passes through unchanged."""
    if lang == "zh":
        return translate(text, book_names(state))
    return plural(_status_words(text)) if text is not None else None


# The engine ends an overdue alert "... and is still OPEN": the invoice's status code, said for a person.
_STATUS_CODE = re.compile(r"(?<=\bis still )(OPEN|FINANCED)\b")
# The executor's own sentence for a facility application: the status code and the "committed" it waits for, for a person.
_APPLICATION_PENDING = re.compile(r"\bit is PENDING and counts as zero until committed\b")


def _status_words(text: str) -> str:
    text = _APPLICATION_PENDING.sub("the application is submitted and counts as zero cash until the bank commits", text)
    return _STATUS_CODE.sub(lambda m: "unpaid" if m.group(1) == "OPEN" else "financed", text)


def last_read(today: int, lang: Lang) -> dict[str, Any]:
    """When the books behind a read were last read (F21): the page says "as of {when}" beside a conclusion. Every read here is taken from
    the books as they stand now, so the day is today; the fields are the same ones `GET /home` carries in its forecast basis."""
    return {"last_read_when": when_text(today, today, lang), "last_read_day": today}


def executed_words(state: FinancialState, *, payload: dict[str, Any], result: dict[str, Any], today: int, lang: Lang,
                   agreements: Mapping[str, str] | None = None) -> dict[str, str | None]:
    """The Business words for one operation result (an act on an alert, an owner's decision on an approval): the executor's sentence as
    a Business page reads it (`message_when`) and the sentence for what the operation did (`event_text`, `event_detail`). The raw
    `message` of the result stays beside them for the audit level."""
    message = str(result.get("message") or "")
    words = event_words(state, kind=str(result.get("kind") or ""), status=str(result.get("status") or ""), payload=payload, message=message,
                        approval_id=result.get("approval_id"), day=result.get("effective_day"), today=today, lang=lang,
                        agreements=agreements)
    when = business_text(state, message, today, lang, agreements)
    return {"message_when": when, "event_text": words["event_text"] or when, "event_detail": words["event_detail"]}


def live_windows(report: Any, commitments: Sequence[Commitment], state: FinancialState) -> frozenset[tuple[str, str]]:
    """The early-payment promises still open, as (commitment id, receivable id): the obligation is in the current books (its
    commitment is live, its day has not lapsed, the invoice is not settled) and has not been paid in full. Only these may be
    spoken of as "may still be settled early"."""
    books = current_books(state, commitments)
    by_id = {c.id: c for c in commitments}
    live = {(cid, o.id) for o, cid in zip(books.obligations, books.owners, strict=False)}
    out: set[tuple[str, str]] = set()
    for p in report.promised:
        c = by_id.get(p.commitment_id)
        ob = next((o for o in c.obligations if o.id == p.obligation_id), None) if c is not None else None
        if ob is None or (p.commitment_id, p.obligation_id) not in live:
            continue
        agreed = ob.base.amount_fen
        if p.status.value == "RECEIVED" and (agreed is None or p.face_fen >= agreed):
            continue  # paid in full: nothing is left to settle early
        out.add((p.commitment_id, p.receivable_id))
    return frozenset(out)


def window_is_live(live: frozenset[tuple[str, str]] | None, receivable_id: str | None, commitment_id: str | None = None) -> bool:
    """Whether the early-payment window of this receivable (under this commitment, when known) is in `live`."""
    return bool(live) and any(r == receivable_id and (commitment_id is None or c == commitment_id) for c, r in live)


# A reconciliation sentence as a Business page reads it. "…Foshan Home Retail Co. due 2 days ago arrived" gets the commas its clause
# needs, and the engine's "for ¥257,200.00 of face" says "of the invoice" (the owner has an invoice, not a face value).
_DUE_ARRIVED = re.compile(r" due ([^,;]+?) arrived\b")
_OF_FACE = re.compile(r"(\bfor ¥[\d,]+(?:\.\d+)?) of face\b")


def reconciliation_words(state: FinancialState, text: str | None, today: int, *, promise: bool, lang: Lang = "en",
                         agreements: Mapping[str, str] | None = None, window_live: bool = False) -> str | None:
    """The sentence for one reconciliation row (`detail_when`). A promise stands alone under the buyer's name, so it is a full sentence
    (capital, commas round the due clause, full stop); a receipt follows the day ("today · agreed early payment for ... of the invoice")
    and stays a clause. The raw `detail` is untouched."""
    out = _owner_english(state, text, today, lang, agreements, window_live)
    if out is None:
        return None
    out = _OF_FACE.sub(r"\1 of the invoice", out)
    if lang == "zh":  # the Chinese templates read the sentence before the English comma rule below
        said = in_language(out, lang, state) or ""
        return _sentence(said) if promise else said
    if not promise:
        return out
    return _sentence(_DUE_ARRIVED.sub(r", due \1, arrived", out))


# The executor's working behind a rate: "(all charges on ¥200,000.00 held 10 days (day 37 to day 47), annualised = 32.52%)".
_FORMULA_PAREN = re.compile(r"\s*\(all charges on [^()]*(?:\([^()]*\)[^()]*)*\)")
_YEARLY_COST = re.compile(r"\b(yearly cost of )(\d+(?:\.\d+)?)%")


def approval_reason_words(state: FinancialState, text: str | None, today: int, lang: Lang = "en") -> str | None:
    """Why a request needs the owner, for the card, as a full sentence: the Business sentence without the executor's working (the "all charges on
    ¥… annualised = …" parenthesis stays at the audit level) and the yearly cost to one decimal, as the home says it
    ("32.5% a year"), never 32.52% beside 32.5%."""
    out = _owner_english(state, text, today, lang)
    if out is None:
        return None
    out = _FORMULA_PAREN.sub("", out)
    return _sentence(in_language(_YEARLY_COST.sub(lambda m: f"{m.group(1)}{fmt_pct(Fraction(m.group(2)) / 100, 1)}", out), lang, state) or "")


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
    out["rejected"] = [{**r, "label_when": business_text(state, r.get("label"), today, lang),
                        "note_when": business_text(state, r.get("note"), today, lang)} for r in out.get("rejected") or []]
    out["label_when"] = business_text(state, out.get("label"), today, lang)
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
    if kind == "COMMIT_PURCHASE":  # ADR-0013
        return t(lang, f"Book the {amount} equipment purchase on the contract's payment days",
                 f"按合同付款日记入 {amount} 的设备采购")
    return f"{kind.replace('_', ' ').capitalize()} {amount}".strip()


_KIND_TEXT = {
    "ACCEPT_OFFER": ("Agreement recorded", "协议已记录"), "RECORD_COMMITMENT": ("Agreement recorded", "协议已记录"),
    "DRAW_FACILITY": ("Credit line drawn", "信用额度已提款"), "SUBMIT_INVOICE_FOR_FINANCING": ("Invoice financing requested", "已申请发票融资"),
    "RECEIVE_PAYMENT": ("Payment received", "已收到付款"), "ADVANCE_CLOCK": ("Time passed", "时间已推进"),
    "REPAY_FACILITY": ("Repayment", "还款"), "APPLY_FOR_FACILITY": ("Facility application", "融资申请"),
    "COUNTER_OFFER": ("Counter sent", "已发送还价"), "REVOKE_COMMITMENT": ("Agreement revoked", "协议已撤销"),
    "ADD_FACILITY": ("Facility added", "已添加融资工具"), "REJECT_OFFER": ("Offer declined", "报价已拒绝"),
    "CONFIRM_DOCUMENT": ("Document confirmed", "文件已确认"), "REJECT_DOCUMENT": ("Document rejected", "文件已驳回"),
    "COMMIT_PURCHASE": ("Purchase committed", "采购已确定"),  # ADR-0013
    "OPEN_BOOKS": ("Books opened", "账簿已开立"),
}


def kind_text(kind: str, lang: Lang) -> str:
    """An operation's kind in the owner's words ("Credit line drawn"); the raw `kind` stays beside it for the audit level."""
    en, zh = _KIND_TEXT.get(kind, (kind.replace("_", " ").capitalize(), kind.replace("_", " ").capitalize()))
    return t(lang, en, zh)


def short_kind(kind: str, lang: Lang) -> str:
    words = {
        "SUBMIT_INVOICE_FOR_FINANCING": ("invoice financing", "发票融资"),
        "DRAW_FACILITY": ("credit line draw", "信用额度提款"),
        "REPAY_FACILITY": ("repayment", "还款"),
        "APPLY_FOR_FACILITY": ("facility application", "融资申请"),
        "RECEIVE_PAYMENT": ("payment receipt", "收款入账"),
        "ACCEPT_OFFER": ("buyer agreement", "买方协议"),
        "RECORD_COMMITMENT": ("buyer agreement", "买方协议"),
        "COMMIT_PURCHASE": ("equipment purchase", "设备采购"),  # ADR-0013
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


COMMERCIAL_KINDS = ("ACCEPT_OFFER", "RECORD_COMMITMENT")


def _base_phrase(state: FinancialState, ob: Obligation, lang: Lang) -> str:
    """What an obligation is about. For an invoice, `base.amount_fen` is the face OR a cap on it (models.ObligationBase), so a
    cap below the invoice's own face reads "up to ¥257,200.00 of the ¥420,000.00 invoice to {buyer}", never a smaller invoice
    that does not exist; an invoice id is never printed (the invoice to {buyer} when the books know no face)."""
    b = ob.base
    if b.kind == BaseKind.INVOICE:
        face = receivable_face(state, b.receivable_id)
        buyer = party_name(state, buyer_of_receivable(state, b.receivable_id) or ob.counterparty_id)
        whole = face if face is not None else b.amount_fen
        cap = b.amount_fen if b.amount_fen is not None and face is not None and b.amount_fen < face else None
        amount = f"{fmt_yuan(whole)} " if whole is not None else ""
        en = f"the {amount}invoice" + (f" to {buyer}" if buyer else "")
        zh = (f"{buyer} 的 " if buyer else "") + (f"{amount}发票" if buyer else (f"{amount}的发票" if amount else "发票"))
        if cap is not None:
            return t(lang, f"up to {fmt_yuan(cap)} of {en}", f"{zh}中最多 {fmt_yuan(cap)}")
        return t(lang, en, zh)
    if b.kind == BaseKind.FUTURE_INVOICES:
        return t(lang, "future invoices", "今后的发票")
    if b.kind == BaseKind.PERIOD_PURCHASES:
        return t(lang, "purchases in the period", "本期采购")
    if b.kind == BaseKind.PER_EVENT:
        return t(lang, "each qualifying event", "每次符合条件的事件")
    return t(lang, "an unstated amount", "未注明的金额")


_OBLIGATION_LABEL = {
    "OPERATIONAL_CONCESSION": ("Operational concession", "运营让步"),
    "CLAIMED_PRIOR_CONCESSION": ("Claimed prior concession", "声称的旧让步"),
}


def obligation_sentence(state: FinancialState, ob: Obligation, today: int, lang: Lang = "en") -> str:
    """One agreed term as a sentence a non-accountant can read: the server's port of the web's `obligationSentence`
    (discount, terms, price, rebate, volume) with the effective day and the duration in one bracket. Typed fields only."""
    base = _base_phrase(state, ob, lang)
    rate = fmt_pct(bp(ob.rate_bp)) if ob.rate_bp is not None else None
    amount = fmt_yuan(ob.amount_fen) if ob.amount_fen is not None else None
    if ob.type == ObligationType.IMMEDIATE_DISCOUNT:
        sentence = t(lang, f"The buyer may pay early and take {rate or '?'} off {base}", f"买家可提前付款，{base} 减免 {rate or '?'}")
    elif ob.type == ObligationType.TERMS_EXTENSION:
        if ob.target_terms_days is not None:
            sentence = t(lang, f"The buyer gets {ob.target_terms_days}-day payment terms on {base}", f"{base} 的账期改为 {ob.target_terms_days} 天")
        elif ob.days_delta is not None and ob.days_delta > 0:
            sentence = t(lang, f"The buyer gets {ob.days_delta} more days to pay on {base}", f"{base} 的付款期延长 {ob.days_delta} 天")
        elif ob.days_delta is not None and ob.days_delta < 0:
            sentence = t(lang, f"The buyer pays {-ob.days_delta} days sooner on {base}", f"{base} 的付款期缩短 {-ob.days_delta} 天")
        else:
            sentence = t(lang, f"The buyer gets longer payment terms on {base}", f"{base} 的账期延长")
    elif ob.type == ObligationType.PRICE_ADJUSTMENT:
        sentence = t(lang, f"The price changes by {rate or amount or '?'} on {base}", f"{base} 价格调整 {rate or amount or '?'}")
    elif ob.type == ObligationType.CONTINGENT_REBATE:
        sentence = t(lang, f"A rebate of {rate or amount or '?'} on {base} if its conditions are met",
                     f"满足条件时，{base} 返利 {rate or amount or '?'}")
    elif ob.type == ObligationType.VOLUME_COMMITMENT:
        sentence = t(lang, f"The buyer commits to buying {amount or '?'}", f"买家承诺采购 {amount or '?'}")
    else:
        en, zh = _OBLIGATION_LABEL.get(ob.type.value, (ob.type.value.replace("_", " ").capitalize(), ob.type.value))
        sentence = f"{t(lang, en, zh)}: {base}"
    notes: list[str] = []
    if ob.type == ObligationType.IMMEDIATE_DISCOUNT and ob.effective_day is not None:
        notes.append(t(lang, f"effective {when_text(ob.effective_day, today, 'en')}", f"{when_text(ob.effective_day, today, 'zh')}生效"))
    d = ob.duration
    if d.kind == DurationKind.ONE_OFF:
        notes.append(t(lang, "one time", "一次性"))
    elif d.kind == DurationKind.RECURRING_PERPETUAL:
        notes.append(t(lang, "ongoing, no end date", "长期有效，无截止日"))
    elif d.invoices is not None:
        notes.append(t(lang, f"for {d.invoices} invoice{'' if d.invoices == 1 else 's'}", f"适用于 {d.invoices} 张发票"))
    elif d.end_day is not None:
        notes.append(t(lang, f"ends {when_text(d.end_day, today, 'en')}", f"{when_text(d.end_day, today, 'zh')}结束"))
    if not notes:
        return sentence
    return f"{sentence}（{'；'.join(notes)}）" if lang == "zh" else f"{sentence} ({'; '.join(notes)})"


def agreement_face_fen(state: FinancialState, c: Commitment) -> int | None:
    """The scope of an agreement in money, from one base kind only: the invoice face or cap each of its obligations names,
    each invoice once (the largest it names). None when any obligation is about something else (future invoices, a period's
    purchases, each event: the bases are mixed) or when no invoice amount is known."""
    if not c.obligations or any(ob.base.kind != BaseKind.INVOICE for ob in c.obligations):
        return None
    per_invoice: dict[str | None, int] = {}
    for ob in c.obligations:
        amount = ob.base.amount_fen if ob.base.amount_fen is not None else receivable_face(state, ob.base.receivable_id)
        if amount is not None:
            per_invoice[ob.base.receivable_id] = max(per_invoice.get(ob.base.receivable_id, 0), amount)
    return sum(per_invoice.values()) if per_invoice else None


def find_agreement(op: dict[str, Any], commitments: list[Commitment]) -> Commitment | None:
    """The commitment a queued ACCEPT_OFFER / RECORD_COMMITMENT row refers to: RECORD_COMMITMENT by its commitment id,
    ACCEPT_OFFER by offer id, offer version and the exact nonce (a later version or another nonce is not it)."""
    if op.get("kind") == "RECORD_COMMITMENT":
        return next((c for c in commitments if c.id == op.get("commitment_id")), None)
    nonce = op.get("nonce")
    return next((c for c in commitments if c.offer_id == op.get("offer_id") and c.offer_version == op.get("offer_version")
                 and isinstance(nonce, str) and hmac.compare_digest(c.nonce.encode(), nonce.encode())), None)


def economic_effect_text(commitment: Commitment, horizon_days: int | None, lang: Lang = "en") -> str:
    """What the terms cost the owner over the next months (the concession horizon), from the commitment's stored forward value (never recomputed): a
    discount alone has no forward cost, so a zero value says so instead of showing "¥0.00" as if the agreement were free."""
    only_discount = all(ob.type == ObligationType.IMMEDIATE_DISCOUNT for ob in commitment.obligations)
    if commitment.forward_value_fen == 0 and only_discount:
        months = max(1, round(horizon_days * 12 / 365)) if horizon_days is not None else None
        if months is None:
            return t(lang, "No cost beyond the early-payment discount.", "除提前付款折扣外，没有其他成本。")
        return t(lang, f"No cost over the next {months} months beyond the early-payment discount.",
                 f"除提前付款折扣外，未来 {months} 个月内没有其他成本。")
    window = t(lang, f" over the next {horizon_days} days", f"，未来 {horizon_days} 天内") if horizon_days is not None else ""
    return t(lang, f"Future cost of the terms you promise: {fmt_yuan(commitment.forward_value_fen)}{window}.",
             f"您承诺的条款带来的未来成本：{fmt_yuan(commitment.forward_value_fen)}{window}。")


def approve_label(state: FinancialState, commitment: Commitment, lang: Lang) -> str:
    """The button of an agreement card, naming what the owner signs: "Approve the agreement (0.50% early-payment discount, about
    ¥2,100.00)", or for terms alone "Approve the agreement (45-day terms)". The discount is the terms' own rate on the portion they cover."""
    discount = next((o for o in commitment.obligations if o.type == ObligationType.IMMEDIATE_DISCOUNT), None)
    if discount is not None:
        portion = discount.base.amount_fen
        if portion is None:
            portion = receivable_face(state, discount.base.receivable_id)
        if discount.rate_bp is not None and portion:
            rate, money = fmt_pct(bp(discount.rate_bp)), fmt_yuan(post(Fraction(portion * discount.rate_bp, 10_000)))
            return t(lang, f"Approve the agreement ({rate} early-payment discount, about {money})",
                     f"批准该协议（{rate} 提前付款折扣，约 {money}）")
        if discount.amount_fen is not None:
            return t(lang, f"Approve the agreement ({fmt_yuan(discount.amount_fen)} early-payment discount)",
                     f"批准该协议（{fmt_yuan(discount.amount_fen)} 提前付款折扣）")
    ext = next((o for o in commitment.obligations if o.type == ObligationType.TERMS_EXTENSION), None)
    if ext is not None and ext.target_terms_days is not None:
        return t(lang, f"Approve the agreement ({ext.target_terms_days}-day terms)", f"批准该协议（{ext.target_terms_days} 天账期）")
    if ext is not None and ext.days_delta:
        n = abs(ext.days_delta)
        return (t(lang, f"Approve the agreement ({n} more days to pay)", f"批准该协议（付款期延长 {n} 天）") if ext.days_delta > 0
                else t(lang, f"Approve the agreement (paid {n} days sooner)", f"批准该协议（付款期缩短 {n} 天）"))
    return t(lang, "Approve the agreement", "批准该协议")


def agreement_terms(state: FinancialState, commitment: Commitment | None, today: int, lang: Lang = "en", *,
                    pending: bool = True, horizon_days: int | None = None) -> dict[str, Any]:
    """What the owner is asked to agree to, written by the server: `terms_available` (the commitment is found, readable, has
    obligations and, while the approval is `pending`, still waits for a yes: PROPOSED or ACCEPTED), the reason when it is not,
    one sentence per obligation, the buyer, the concessions booked against the budget and the whole in one line. A decided
    approval shows the terms that were approved whatever the agreement has become since (in force, settled, expired).
    Nothing here prices anything."""
    none: dict[str, Any] = {"terms_available": False, "terms_unavailable_reason": None, "terms": [], "counterparty_name": None,
                            "forward_value_display": None, "what_you_agree_to": None, "agreement_fen": None,
                            "economic_effect_text": None, "approve_label": None}
    if commitment is None:
        return {**none, "terms_unavailable_reason": t(lang, "The agreement this approval refers to could not be found.",
                                                      "找不到此批准所对应的协议。")}
    buyer = party_name(state, commitment.counterparty_id) or None
    base = {**none, "counterparty_name": buyer,
            "forward_value_display": fmt_yuan(commitment.forward_value_fen) if commitment.forward_value_fen else None,
            "economic_effect_text": economic_effect_text(commitment, horizon_days, lang)}
    status = commitment.status
    if pending and status == CommitmentStatus.EXPIRED:
        return {**base, "terms_unavailable_reason": t(lang, "The agreement this approval refers to has expired.", "此批准所对应的协议已到期。")}
    if pending and status == CommitmentStatus.REVOKED:
        return {**base, "terms_unavailable_reason": t(lang, "The agreement this approval refers to was revoked.", "此批准所对应的协议已被撤销。")}
    if pending and status not in (CommitmentStatus.PROPOSED, CommitmentStatus.ACCEPTED):
        return {**base, "terms_unavailable_reason": t(lang, "The agreement this approval refers to is already in force or settled.",
                                                      "此批准所对应的协议已生效或已结清。")}
    try:
        terms = [obligation_sentence(state, ob, today, lang) for ob in commitment.obligations]
    except (ValueError, KeyError, AttributeError):
        terms = []
    if not terms:
        return {**base, "terms_unavailable_reason": t(lang, "The terms of the agreement this approval refers to could not be read.",
                                                      "无法读取此批准所对应协议的条款。")}
    return {**base, "terms_available": True, "terms": terms, "agreement_fen": agreement_face_fen(state, commitment),
            "approve_label": approve_label(state, commitment, lang) if pending else None,
            "what_you_agree_to": ("; " if lang != "zh" else "；").join(terms) + t(lang, ".", "。")}


_FINANCING_NOUN = {  # what a facility is, as the owner says it after "Apply for ¥200,000 in ..."
    "CREDIT_LINE": ("working-capital financing", "营运资金融资"), "GOV_GUARANTEED_LOAN": ("working-capital financing", "营运资金融资"),
    "INVOICE_FINANCING": ("invoice financing", "发票融资"), "EQUIPMENT_TERM_LOAN": ("equipment financing", "设备融资"),
    "EQUIPMENT_LEASE": ("equipment financing", "设备融资"),
}


def _whole(fen: int) -> str:
    """¥200,000 for a whole number of yuan, else with the fen."""
    return fmt_yuan(fen).removesuffix(".00")


def approval_title(state: FinancialState, kind: str, op: dict[str, Any], buyer: str | None, lang: Lang) -> str:
    """What an approval asks the owner to authorize, as a statement and not a question: "Apply for ¥200,000 in working-capital financing",
    "Draw ¥150,000 on the Bank credit line", "Record the agreement with Foshan Home Retail Co."."""
    amount = op.get("amount_fen", op.get("advance_fen"))
    money = _whole(amount) if isinstance(amount, int) else None
    fac = facility_name(state, op.get("facility_id"))
    if kind in COMMERCIAL_KINDS:
        return t(lang, f"Record the agreement with {buyer}", f"记录与{buyer}的协议") if buyer else t(lang, "Record this agreement", "记录这项协议")
    if kind == "APPLY_FOR_FACILITY" and money:
        facility = next((f for f in state.facilities if f.id == op.get("facility_id")), None)
        noun = _FINANCING_NOUN.get(facility.kind.value if facility is not None else "", ("financing", "融资"))
        return t(lang, f"Apply for {money} in {noun[0]}", f"申请 {money} 的{noun[1]}")
    if kind == "DRAW_FACILITY" and money:
        return t(lang, f"Draw {money} on the {fac}" if fac else f"Draw {money}", f"从{fac}提款 {money}" if fac else f"提款 {money}")
    if kind == "SUBMIT_INVOICE_FOR_FINANCING" and money:
        return t(lang, f"Request {money} of invoice financing", f"申请 {money} 的发票融资")
    if kind == "REPAY_FACILITY" and money:
        return t(lang, f"Repay {money} to the {fac}" if fac else f"Repay {money}", f"向{fac}还款 {money}" if fac else f"还款 {money}")
    if kind == "COMMIT_PURCHASE" and money:  # ADR-0013
        return t(lang, f"Commit to the {money} equipment purchase", f"确定 {money} 的设备采购")
    return t(lang, f"Authorize this {short_kind(kind, 'en')}", f"授权这项{short_kind(kind, 'zh')}")


_DECIDED = {  # kind: (what was authorized, what FLOW did with it, what did not happen when declined), en then zh
    "APPLY_FOR_FACILITY": (("the application", "FLOW sent it to the lender", "the application was not sent"),
                           ("该申请", "FLOW 已将其提交给贷款方", "该申请未提交")),
    "DRAW_FACILITY": (("the draw", "FLOW ran it", "the draw did not run"), ("该提款", "FLOW 已执行", "该提款未执行")),
    "SUBMIT_INVOICE_FOR_FINANCING": (("the financing request", "FLOW sent it to the lender", "the request was not sent"),
                                     ("该融资申请", "FLOW 已将其提交给贷款方", "该申请未提交")),
    "REPAY_FACILITY": (("the repayment", "FLOW paid it", "nothing was repaid"), ("该还款", "FLOW 已还款", "没有还款")),
    "RECORD_COMMITMENT": (("the agreement", "FLOW recorded it", "the agreement was not recorded"), ("该协议", "FLOW 已记录", "该协议未记录")),
    "ACCEPT_OFFER": (("the agreement", "FLOW recorded it", "the agreement was not recorded"), ("该协议", "FLOW 已记录", "该协议未记录")),
    "COMMIT_PURCHASE": (("the purchase", "FLOW booked its payments", "nothing was booked"),
                        ("该采购", "FLOW 已记入其付款", "没有记入任何付款")),
}
_DECIDED_OTHER = (("the request", "FLOW ran it", "nothing ran"), ("该请求", "FLOW 已执行", "没有执行任何操作"))


def decided_text(kind: str, status: str, execution_status: str | None, lang: Lang) -> str | None:
    """What came of an approval the owner has answered, in one sentence by kind: "You authorized the application; FLOW sent it to the lender.",
    "You declined; the application was not sent.", or, when the run was refused, "You authorized the application, but it could not run. Nothing
    was sent." None while it waits."""
    if status == "PENDING":
        return None
    en, zh = _DECIDED.get(kind, _DECIDED_OTHER)
    if status == "REJECTED" or execution_status == "DECLINED":
        return t(lang, f"You declined; {en[2]}.", f"您已拒绝；{zh[2]}。")
    if execution_status == "REFUSED":
        return t(lang, f"You authorized {en[0]}, but it could not run. No money moved.", f"您已授权{zh[0]}，但未能执行。资金未动。")
    return t(lang, f"You authorized {en[0]}; {en[1]}.", f"您已授权{zh[0]}；{zh[1]}。")


def approval_words(state: FinancialState, op: dict[str, Any], kind: str | None, today: int, alert: Alert | None,
                   lang: Lang, plan_costs: dict[tuple[str, str, str | None, int], Any] | None = None,
                   after: str | None = None, *, status: str = "PENDING", agreement: dict[str, Any] | None = None) -> dict[str, Any]:
    """Business fields for one queued operation: the question, the amount, what it costs (from the alert whose cure
    it is, when that alert is still open; or from the router's cost line when the operation is a leg of the recommended
    plan, `plan_costs` keyed by kind, facility, receivable and amount), when the cash lands, and the names behind the ids.
    `after` is the cure's after-state sentence, the one the home says (`home.cure_after`); `protects` carries it."""
    kind = kind or str(op.get("kind") or "")
    pending = status == "PENDING"
    facility_id = op.get("facility_id")
    receivable_id = op.get("receivable_id")
    amount = op.get("amount_fen", op.get("advance_fen"))
    amount_display = fmt_yuan(amount) if isinstance(amount, int) else None
    ag = agreement or {}
    agreement_buyer = ag.get("counterparty_name")
    if kind in COMMERCIAL_KINDS:
        # An agreement with a buyer has no funding amount; its scope is the face it states (None when it states none), never ¥0.00.
        amount_display = fmt_yuan(ag["agreement_fen"]) if ag.get("agreement_fen") else None
    headline = approval_title(state, kind, op, agreement_buyer, lang)  # a statement of what is authorized, never a question
    lands: int | None = None
    if kind in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"):
        if pending:
            # A waiting request has not started the lead time: if approved, the cash lands that many days after the day the
            # owner approves (today at the earliest), never on a day already past (F03).
            lands = max(today, int(op.get("day", today))) + lead_days(state, facility_id)
        else:
            lands = _lot_arrival(state, str(op.get("op_id") or ""))  # a decided request lands when its lot says
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
    if_decline: str | None = t(lang, *CLOSED_IF_DECLINED)
    if not pending:
        if_decline = None  # the owner has answered: there is nothing left to decline
    elif alert is not None and alert.kind == AlertKind.RESERVE_BREACH_AHEAD:
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
    if kind in COMMERCIAL_KINDS:
        words = (t(lang, f"Agreement with {agreement_buyer}", f"与{agreement_buyer}的协议") if agreement_buyer
                 else t(lang, "Buyer agreement", "买方协议"))
    else:
        words = leg_words(state, kind, facility_id, receivable_id, amount if isinstance(amount, int) else None, lang)
    out: dict[str, Any] = {
        "headline": headline,
        "title_text": headline,
        "what": words,
        "facility_name": facility_name(state, facility_id) or None,
        "buyer_name": buyer or agreement_buyer,
        "invoice": invoice_words(state, receivable_id, lang) or None,
        "cost_display": cost_display,
        "rate_text": rate_text,
        "cost_due_day": cost_due_day,
        "lands_day": lands,
        "lands_when": when_text(lands, today, lang) if lands is not None else None,
        "lands_text": (t(lang, f"If you approve today, the cash lands {when_text(lands, today, lang)}.",
                         f"若您今天批准，资金将于{when_text(lands, today, lang)}到账。")
                       if pending and lands is not None else None),
        "if_decline": if_decline,
        "protects": after,
    }
    if kind in COMMERCIAL_KINDS:
        out.update({"amount_display": amount_display, "terms_available": bool(ag.get("terms_available")),
                    "terms_unavailable_reason": ag.get("terms_unavailable_reason"), "terms": list(ag.get("terms") or []),
                    "counterparty_name": agreement_buyer, "forward_value_display": ag.get("forward_value_display"),
                    "economic_effect_text": ag.get("economic_effect_text"),
                    "what_you_agree_to": ag.get("what_you_agree_to"),
                    "approve_label": ag.get("approve_label") if pending else None,
                    "why_text": t(lang, "This changes the terms with a buyer, which you keep for yourself.",
                                  "这会改变与买方的条款，这类决定由您自己保留。")})
    return out


# ---------------------------------------------------------------- a log entry as a business event (wayfinder #35)

_RATE_IN_REASON = re.compile(r"effective annual cost (\d+(?:\.\d+)?)% is above the mandate's (\S+%) ceiling")
_RECEIPT_DETAIL = re.compile(r"^Received \S+ on \S+ \((.+?)\)")
_MONEY_KINDS = ("SUBMIT_INVOICE_FOR_FINANCING", "DRAW_FACILITY")


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".。!?" else text + ("。" if any("一" <= ch <= "鿿" for ch in text) else ".")


def _stop(text: str, lang: Lang) -> str:
    """The sentence's full stop, unless the text already ends in one (a buyer named "… Co.")."""
    return text if text.endswith((".", "。")) else text + t(lang, ".", "。")


def _op_amount(payload: dict[str, Any]) -> int | None:
    amount = payload.get("advance_fen", payload.get("amount_fen"))
    return amount if isinstance(amount, int) else None


def _lot_arrival(state: FinancialState, op_id: str) -> int | None:
    """The day the funding lot an operation created lands (ADR-0010); None when it created none."""
    for lot in state.lots:
        if op_id and (lot.id == op_id or lot.id.startswith(op_id + "#")):
            return lot.arrival_day
    return None


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
                 lang: Lang = "en", approval_status: str | None = None, message: str | None = None,
                 agreements: Mapping[str, str] | None = None) -> str | None:
    """What came of the owner's decision on an approval, as one sentence: "¥200,000.00 of invoice financing was requested
    today; the cash lands in 3 days." (the landing is the funding lot's own day, ADR-0010), "You declined ...", or, when the
    owner approved but the run was refused, "You approved it, but it could not run: {reason}. No money moved." (F14: only an
    approval the owner REJECTED is a decline; `approval_status` says which, and `message` is the executor's refusal). None for
    a kind or status with no such reading; the caller keeps the executor's own sentence then."""
    if status == "REFUSED" and approval_status == "APPROVED":
        reason = (message or "").removeprefix("Refused: ").strip().rstrip(".")
        why = business_text(state, reason, today, lang, agreements) if reason else None
        if why and lang != "zh" and why.startswith("Your "):
            why = why[:1].lower() + why[1:]  # it follows a colon
        if why:  # an approval or operation id belongs to the audit level (the raw `result_message` keeps it)
            why = _RECORD_ID.sub(lambda m: "" if m.group(0).lstrip().startswith("(") else "this request", why).replace("  ", " ")
        return t(lang, f"You approved it, but it could not run{': ' + why.rstrip('.') if why else ''}. No money moved.",
                 f"您已批准，但未能执行{'：' + why.rstrip('.') if why else ''}。资金未动。")
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


def decided_headline(*, kind: str, status: str, execution_status: str | None, amount_display: str | None, what: str,
                     buyer: str | None, lang: Lang) -> tuple[str, str | None, str | None]:
    """The card of an approval the owner has answered (`decided_text`): "You authorized the application; FLOW sent it to the lender.",
    "You declined; the application was not sent.". A refused run also says what to do next (`next_step_text`, `next_step_href`)."""
    said = decided_text(kind, status, execution_status, lang) or ""
    if execution_status == "REFUSED" and status != "REJECTED":
        return (said, t(lang, "Renew your signed limits, then ask FLOW to try again.", "请续签您的授权，然后让 FLOW 重试。"), "/limits")
    return said, None, None


def approval_result_state(*, kind: str, status: str, execution_status: str | None, lands_day: int | None, today: int,
                          lang: Lang) -> tuple[str, str]:
    """One line for what came of an approval, authorization and execution together, and its tone (`warn` while the owner is awaited, `ok`,
    `info`, `neutral`, `bad`): "Approved, cash arrives in 3 days", "Approved, did not run. No money moved.", "Declined, nothing ran"."""
    if status == "PENDING":
        return t(lang, "Waiting for your approval", "等待您批准"), "warn"
    if status == "REJECTED" or execution_status == "DECLINED":
        return t(lang, "Declined, nothing ran", "已拒绝，未执行任何操作"), "neutral"
    if execution_status == "REFUSED":
        return t(lang, "Approved, did not run. No money moved.", "已批准，但未能执行。资金未动。"), "bad"
    if execution_status == "DUPLICATE":
        return t(lang, "Approved, already done", "已批准，此前已执行"), "info"
    if execution_status != "EXECUTED":
        return t(lang, "Approved, waiting to run", "已批准，等待执行"), "info"
    if kind in COMMERCIAL_KINDS:
        return t(lang, "Approved, agreement recorded", "已批准，协议已记录"), "ok"
    if kind in _MONEY_KINDS:
        if lands_day is not None and lands_day > today:
            when = when_text(lands_day, today, lang)
            return t(lang, f"Approved, cash arrives {when}", f"已批准，资金将于{when}到账"), "info"
        return t(lang, "Approved, cash received", "已批准，资金已到账"), "ok"
    if kind == "APPLY_FOR_FACILITY":  # submitted, not done: it counts as zero cash until the lender commits
        return t(lang, "Approved and submitted", "已批准并已提交"), "info"
    return t(lang, "Approved, done", "已批准，已完成"), "ok"


def agreement_words(state: FinancialState, counterparty_id: str, forward_value_fen: int, lang: Lang = "en") -> str:
    """"Agreement with Foshan Home Retail Co. recorded; concessions booked against your budget: ¥0.00." (the home's
    AGREEMENT event)."""
    buyer = party_name(state, counterparty_id)
    return t(lang, f"Agreement with {buyer} recorded; concessions booked against your budget: {fmt_yuan(forward_value_fen)}.",
             f"已记录与{buyer}的协议；已计入您预算的让步：{fmt_yuan(forward_value_fen)}。")


def request_of(buyer: str | None, lang: Lang) -> str:
    """"Zhuhai's request" / "the buyer's request" (the buyer as the owner says it aloud: its first word)."""
    if not buyer:
        return t(lang, "the buyer's request", "买方的请求")
    short = buyer.replace(",", " ").split()[0] if buyer.split() else buyer
    return t(lang, f"{short}'s request", f"{short}的请求")


def offer_buyers(store: Any, state: FinancialState, payloads: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """{offer id: the buyer's name} for the offers the owner accepted or declined in these logged operations (`event_words(offers=...)`). An offer
    the store does not hold is simply absent."""
    out: dict[str, str] = {}
    for payload in payloads:
        offer_id = payload.get("offer_id")
        if payload.get("kind") not in ("ACCEPT_OFFER", "REJECT_OFFER") or not isinstance(offer_id, str) or offer_id in out:
            continue
        try:
            offer = store.get_offer(offer_id)
        except Exception:  # noqa: BLE001  a missing offer is absent
            offer = None
        if offer is not None:
            out[offer_id] = party_name(state, offer.counterparty_id)
    return out


def owner_offer_words(kind: str, status: str, *, buyer: str | None, lang: Lang, decided: bool = True) -> dict[str, str | None] | None:
    """The owner's own act on a buyer's request as asked (an AcceptOffer or a RejectOffer the owner requested), in the Activity's words: "You
    accepted Zhuhai's request as asked." and "You declined Zhuhai's request." The accept is queued for the owner's approval and approved by
    the same click, so its queued entry reads as the owner's choice (`decided`: the owner has since answered it; an entry still waiting says so).
    None for a status with no such reading (a refusal keeps its own words)."""
    asked = request_of(buyer, lang)
    if kind == "ACCEPT_OFFER" and status == "EXECUTED":
        return {"event_text": t(lang, f"You accepted {asked} as asked.", f"您已按对方要求接受{asked}。"), "event_detail": None}
    if kind == "ACCEPT_OFFER" and status == "PENDING_APPROVAL":
        if not decided:
            return {"event_text": t(lang, f"Waiting for your approval: accepting {asked} as asked.", f"等待您批准：按对方要求接受{asked}。"),
                    "event_detail": None}
        return {"event_text": t(lang, f"You chose to accept {asked} as asked.", f"您选择按对方要求接受{asked}。"), "event_detail": None}
    if kind == "REJECT_OFFER" and status == "EXECUTED":
        return {"event_text": t(lang, f"You declined {asked}.", f"您已拒绝{asked}。"),
                "event_detail": t(lang, "Nothing was agreed, sent or funded.", "未达成、发送或融资任何事项。")}
    return None


def buyer_yes_words(status: str, *, buyer: str | None, lang: Lang, decided: bool = True) -> dict[str, str | None] | None:
    """The owner recording a buyer's yes to a counter the owner sent outside FLOW (`app.api.outbound`, op id "buyer-yes-..."), in the
    Activity's words: never "as asked", because the buyer accepted a counter, not their own request."""
    who = buyer or t(lang, "the buyer", "买方")
    if status == "EXECUTED":
        return {"event_text": t(lang, f"You recorded that {who} accepted the counter you sent.", f"您记录了{who}已接受您发出的还价。"),
                "event_detail": None}
    if status == "PENDING_APPROVAL":
        if not decided:
            return {"event_text": t(lang, f"Waiting for your approval: {who} accepted the counter you sent.",
                                    f"等待您批准：{who}已接受您发出的还价。"), "event_detail": None}
        return {"event_text": t(lang, f"{who} accepted the counter you sent; it went to your approval.", f"{who}已接受您发出的还价；已提交您批准。"),
                "event_detail": None}
    return None


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
                decided: bool = False, agreements: Mapping[str, str] | None = None,
                window_live: bool = False, offers: Mapping[str, str] | None = None) -> dict[str, str | None]:
    """One operations-log entry as a business sentence: what happened in the owner's words, never the executor's own
    sentence. `event_text` is the sentence (the landing of a draw or advance is its second sentence) and `event_detail`
    one more sentence when there is something more to say, else None. Every figure is the operation's own amount, the
    executor's own rate and the funding lot's own landing day; nothing is priced here. An entry with no business reading
    (anything the executor says in its own words only) returns `event_text` None and the caller keeps the sentence it has.
    `decided` says the owner has since answered the approval a PENDING_APPROVAL entry waited on: the entry then reads in the
    past ("Approval requested"), never "Waiting", beside the entry of the decision (the row's `current_decision_state` says where the
    decision stands now). `offers` names the buyer of an offer by its id: the owner's own acceptance or refusal of a request says whose
    request it was."""
    none: dict[str, str | None] = {"event_text": None, "event_detail": None}
    if kind == "ACCEPT_OFFER" and payload.get("requested_by") == "OWNER" and str(payload.get("op_id") or "").startswith("buyer-yes-"):
        buyer_yes = buyer_yes_words(status, buyer=(offers or {}).get(str(payload.get("offer_id") or "")), lang=lang, decided=decided)
        if buyer_yes is not None:
            return buyer_yes
    if kind in ("ACCEPT_OFFER", "REJECT_OFFER") and payload.get("requested_by") == "OWNER":
        owner_words = owner_offer_words(kind, status, buyer=(offers or {}).get(str(payload.get("offer_id") or "")), lang=lang, decided=decided)
        if owner_words is not None:
            return owner_words
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
        lead = t(lang, "Approval requested" if decided else "Waiting for your approval",
                 "已请求批准" if decided else "等待您批准")
        reason = message.split("): ", 1)[1] if "): " in message else ""
        m = _RATE_IN_REASON.search(reason)
        if m:
            rate = fmt_pct(Fraction(m.group(1)) / 100, 1)
            return {"event_text": t(lang, f"{lead}: {asked} at {rate} a year, above the {m.group(2)} limit you "
                                          f"signed for funding without your approval.",
                                    f"{lead}：{asked}，年化成本 {rate}，高于您签署的无需批准融资上限 {m.group(2)}。"),
                    "event_detail": None}
        detail = _sentence(business_text(state, reason, today, lang, agreements) or "") if reason else None
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
        why = _sentence(business_text(state, reason, today, lang, agreements) or "")
        return {"event_text": t(lang, f"{_stop(f'Refused: {asked}', lang)} {why}".strip(), f"{_stop(f'已拒绝：{asked}', lang)}{why}".strip()),
                "event_detail": None}

    if status == "EXECUTED" and kind == "RECEIVE_PAYMENT" and amount is not None and buyer:
        m = _RECEIPT_DETAIL.match(message)
        detail = _sentence(business_text(state, m.group(1), today, lang, agreements, window_live) or "") if m else None
        ref = payload.get("bank_reference")
        if isinstance(ref, str) and ref.startswith("DEMO-"):  # the guided Demo's one receipt says it is synthetic, wherever it is read
            note = bank_note(lang, ref)
            detail = f"{detail} {note}" if detail else note
        return {"event_text": _stop(t(lang, f"Received {fmt_yuan(amount)} from {buyer}", f"已收到{buyer}的 {fmt_yuan(amount)}"), lang),
                "event_detail": detail or None}
    return none


def bank_note(lang: str, ref: str) -> str:
    """The sentence that says the guided Demo's receipt is synthetic and names the bank's reference (evidence, not Business prose)."""
    return t(lang, f"Synthetic bank event, reference {ref}; no real funds moved.", f"模拟银行事件，银行参考号 {ref}；没有真实资金流动。")


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


# ---------------------------------------------------------------- the comparison contract (wayfinder #65 Wave 3, F18)

GROUP_ORDER = ("RECOMMENDED", "ALTERNATIVE", "CONDITIONAL_ON_BUYER", "INSUFFICIENT", "NOT_AVAILABLE_YET", "BLOCKED")
_RANKED = ("RECOMMENDED", "ALTERNATIVE")


def comparison_order_text(lang: Lang) -> str:
    """How the list is ordered, in one sentence (it is true of the order `comparison_contract` gives)."""
    return t(lang, "The recommended plan first, then the other plans that can run now, cheapest first. Plans that depend on the "
                   "buyer, leave a gap or are not available yet follow, and are not ranked.",
             "推荐方案在前，其后是现在即可执行的其他方案，按成本从低到高。依赖买方、仍有缺口或暂不可用的方案排在后面，不参与排名。")


def _row_group(row: dict[str, Any]) -> str:
    """The group a row belongs to, from the router's own flags (`role`, `executable_now`, `reason_kind`)."""
    role = row.get("role")
    if role == "recommended":
        return "RECOMMENDED"
    if row.get("executable_now") is False and row.get("reason_kind") == "buyer_early_pay":
        return "CONDITIONAL_ON_BUYER"
    if role == "insufficient":
        return "INSUFFICIENT"
    if role == "blocked":
        return "BLOCKED"
    if role == "unavailable" or row.get("executable_now") is False:
        return "NOT_AVAILABLE_YET"
    return "ALTERNATIVE"


def _landing_days(row: dict[str, Any]) -> list[int | None]:
    return [a.get("lands_day") for a in row.get("actions") or []]


def _row_arrival(row: dict[str, Any], today: int, lang: Lang) -> tuple[int | None, str | None, str | None]:
    """The day every source in the plan has paid out, as the router's own landing days give it. None when a leg has no landing
    day (a buyer's early payment lands when the buyer says), and then the text says so."""
    days = _landing_days(row)
    if not days:
        return None, None, None
    if any(d is None for d in days):
        return None, None, t(lang, "When the cash arrives depends on the buyer agreeing to pay early.",
                             "资金何时到账取决于买方是否同意提前付款。")
    last = max(d for d in days if d is not None)
    when = when_text(last, today, lang)
    return last, when, (t(lang, "All of the funds are available today.", "全部资金今天到位。") if last <= today
                        else t(lang, f"All of the funds are available {when}.", f"全部资金将于{when}到位。"))


def _row_basis(row: dict[str, Any], action: dict[str, Any] | None, today: int, lang: Lang) -> str | None:
    """What the plan's cost assumes: the line is priced to the day it is assumed repaid, an advance in whole 30-day periods.
    A row with neither says nothing (its cost is the discount alone)."""
    if row.get("key") == RECOMMENDED_PLAN_KEY and action is not None:
        return action.get("cost_basis") or None
    actions = row.get("actions") or []
    parts: list[str] = []
    repay = [a["repay_day"] for a in actions if a.get("kind") == "DRAW" and a.get("repay_day") is not None]
    if repay:
        parts.append(t(lang, f"All charges to the assumed repayment day {when_text(max(repay), today, lang)}.",
                       f"所有费用均计算至假定还款日（{when_text(max(repay), today, lang)}）。"))
    if any(a.get("kind") == "FINANCE_INVOICE" for a in actions):
        parts.append(t(lang, "Invoice financing is billed in whole 30-day periods until the invoice is paid.",
                       "发票融资按整 30 天计费，直至发票付清。"))
    return t(lang, " ", "").join(parts) or None


def _consent_text(state: FinancialState, row: dict[str, Any], lang: Lang) -> str:
    rid = next((a.get("receivable_id") for a in row.get("actions") or [] if a.get("kind") == "EARLY_PAY"), None)
    buyer = party_name(state, buyer_of_receivable(state, rid)) if rid else ""
    return t(lang, f"Needs {buyer or 'the buyer'} to agree to pay early; it cannot run until they do.",
             f"需要{buyer or '买方'}同意提前付款；对方同意前无法执行。")


def _available_when(row: dict[str, Any], today: int, lang: Lang) -> str | None:
    """The earliest day a not-yet-available plan can have its cash, from the router's own landing days or the day an invoice is
    issued; None when the router names no day (a source that is not committed)."""
    days = [d for d in (*_landing_days(row), *(a.get("available_from_day") for a in row.get("actions") or [])) if isinstance(d, int)]
    later = [d for d in days if d > today]
    return when_text(max(later), today, lang) if later else None


def _group_text(group: str, row: dict[str, Any], available: str | None, lang: Lang) -> str:
    if group == "RECOMMENDED":
        return t(lang, "Recommended", "推荐方案")
    if group == "ALTERNATIVE":
        return t(lang, "Another way to fund it", "其他融资方式")
    if group == "CONDITIONAL_ON_BUYER":
        return t(lang, "Only if the buyer agrees to early payment", "仅当买方同意提前付款")
    if group == "INSUFFICIENT":
        short = row.get("shortfall_display")
        return (t(lang, f"Leaves {short} uncovered", f"仍有 {short} 缺口未覆盖") if short
                else t(lang, "Does not cover the gap", "无法覆盖缺口"))
    if group == "NOT_AVAILABLE_YET":
        return (t(lang, f"Not available yet: earliest {available}", f"暂不可用：最早{available}") if available
                else t(lang, "Not available yet", "暂不可用"))
    return t(lang, "Breaks one of your limits", "违反您的某项限额")


def _gap_text(group: str, row: dict[str, Any], action: dict[str, Any] | None, lang: Lang) -> str | None:
    if group == "INSUFFICIENT":
        short = row.get("shortfall_display")
        return t(lang, f"Leaves {short} uncovered.", f"仍有 {short} 缺口未覆盖。") if short else None
    if row.get("key") == RECOMMENDED_PLAN_KEY and action is not None:
        return action.get("after") or None  # the next-step card's own after-state sentence
    if group in ("NOT_AVAILABLE_YET", "BLOCKED") or row.get("result") == "NOT_ADMISSIBLE" or not row.get("actions"):
        return None
    return t(lang, "No gap is left.", "不留缺口。")


def comparison_contract(rows: list[dict[str, Any]], action: dict[str, Any] | None, state: FinancialState, today: int,
                        lang: Lang) -> list[dict[str, Any]]:
    """Order the roled rows and give each its place in the comparison (F18). `group` is RECOMMENDED, ALTERNATIVE, INSUFFICIENT,
    CONDITIONAL_ON_BUYER, NOT_AVAILABLE_YET or BLOCKED (a plan that breaks a limit), from the router's own flags. The order is the
    recommended plan first, then the plans that can run now by the router's all-in cost, cheapest first; the plans that depend on
    the buyer follow (by cost), then the rest in the router's order. Only RECOMMENDED and ALTERNATIVE rows get a `rank`, 1 to n in
    that order, so no plan that cannot run today is numbered among the ones that can. `router_order` is the row's place in the
    router's own spec 7.4 order (None for the cure row the API adds), which the Demo funding view keeps. No figure is
    recomputed: each field is the row's own, and a field the row has no figure for is None."""
    router_pos = {r["key"]: i for i, r in enumerate(r for r in rows if r.get("key") != RECOMMENDED_PLAN_KEY)}
    staged: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for i, r in enumerate(rows):
        group = _row_group(r)
        total = r.get("total_fen")
        cost_key = total if isinstance(total, int) else 1 << 62
        sort = (GROUP_ORDER.index(group), cost_key if group in ("ALTERNATIVE", "CONDITIONAL_ON_BUYER") else 0, i)
        arrival_day, arrival_when, arrival_text = _row_arrival(r, today, lang)
        available = _available_when(r, today, lang) if group == "NOT_AVAILABLE_YET" else None
        short = r.get("shortfall_display") if group == "INSUFFICIENT" else None
        gap_text = _gap_text(group, r, action, lang)
        staged.append((sort, {
            **r, "group": group, "group_text": _group_text(group, r, available, lang), "rank": None,
            "router_order": router_pos.get(r["key"]),
            "arrival_day": arrival_day, "arrival_when": arrival_when, "arrival_text": arrival_text,
            "available_when": available, "uncovered_display": short,
            "remaining_gap_fen": r.get("shortfall_fen") if group == "INSUFFICIENT" else None,
            "remaining_gap_display": short, "remaining_gap_text": gap_text,
            "basis_text": _row_basis(r, action, today, lang),
            "consent_text": _consent_text(state, r, lang) if group == "CONDITIONAL_ON_BUYER" else None,
        }))
    ordered = [row for _, row in sorted(staged, key=lambda p: p[0])]
    rank = 0
    for row in ordered:
        if row["group"] in _RANKED:
            rank += 1
            row["rank"] = rank
    return ordered


def with_roles(rows: list[dict[str, Any]], action: dict[str, Any] | None, state: FinancialState, today: int,
               lang: Lang) -> tuple[list[dict[str, Any]], str | None]:
    """The comparison as the owner reads it: every row says what it is for the owner (`role`) and why (`role_reason`), and the
    plan the next-step card recommends is in the list. `role` is `recommended` (the plan the card shows), `alternative`
    (within the limits, not chosen) or the row's own status (`insufficient`, `unavailable`, `blocked`). When the card shows
    the router's cheapest plan that row is the recommended one; when it shows the alert's cure (the cheaper plan needs
    several approvals) the cure is added as a row, listed first, and the router's cheapest becomes an alternative whose reason
    names the approvals it would ask for. Returns the rows and the recommended row's key. `status` and `selected` stay the
    router's own; no plan is priced here (`funding/recommend.py` already decided). The rows come back in the order the owner reads
    them and carry the comparison contract (`comparison_contract`): a `group`, a `rank` for the runnable ones only, and the
    words for arrival, gap, basis and consent."""
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
        reason: str | None
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
    return comparison_contract(out, action if source == "alert" else None, state, today, lang), key


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


# ---------------------------------------------------------------- the decision record's words (ADR-0011, wayfinder #65)
#
# The record stores codes, ids and numbers; these functions write every sentence, per request and language (INVARIANT 13).
# Nothing here prices or projects: each figure is read from a stored fact, a lot or the operations' own amounts.

_DEAL_STATE_WORDS = {
    "RECEIVED": ("Received; not evaluated yet", "已收到，尚未评估"),
    "NEEDS_CLARIFICATION": ("Needs clarification from the buyer", "需要买方澄清"),
    "AUTHORIZATION_REQUIRED": ("Waiting for your approval", "等待您批准"),
    "DECLINED": ("You declined it", "您已拒绝"),
    "FAILED": ("Could not run; nothing changed", "未能执行，没有任何改动"),
    "NO_DEAL": ("No deal: the buyer did not accept", "未成交：买方未接受"),
    "AGREED": ("Agreed", "已达成协议"),
    "EXPIRED": ("Expired before it was agreed", "未达成协议即已到期"),
    "MISSED": ("Early payment did not arrive", "提前付款未到账"),
    "FULFILLED": ("Fulfilled", "已履行"),
    "REVOKED": ("Revoked", "已撤销"),
    "AWAITING_BUYER": ("Offer sent; waiting for the buyer's answer", "报价已发出，等待买方答复"),
    "REPLIED": ("The buyer answered with new terms", "买方提出了新条款"),
    "LAPSED": ("Lapsed · the invoice it was about has since been settled under another agreement",
               "已失效 · 它所针对的发票此后已按另一份协议结算"),
}
# A negotiation also lapses when nothing but the books moved (the invoice was financed, the days it named have passed): said without an agreement.
_LAPSED_CHANGED = ("Lapsed · the invoice or the dates it was about have since changed", "已失效 · 它所针对的发票或日期此后已有变动")
_RESPONSE_WORDS = {
    "accept": ("Acceptable, awaiting agreement", "可接受，等待达成协议"),
    "counter": ("Counter recommended", "建议还价"),
    "decline": ("Decline recommended", "建议拒绝"),
    "needs_owner": ("Needs your approval", "需要您批准"),
    "cannot": ("Cannot be decided yet", "暂时无法决定"),
}
_FUNDING_STATE_WORDS = {
    "AUTHORIZATION_REQUIRED": ("Waiting for your approval", "等待您批准"),
    "DECLINED": ("You declined it", "您已拒绝"),
    "FAILED": ("Could not run. No money moved", "未能执行，资金未动"),
    "PARTIALLY_EXECUTED": ("Partly done", "部分完成"),
    "SETTLEMENT_PENDING": ("Requested; the cash is on its way", "已提交，资金在途"),
    "SETTLED": ("Done; the cash has landed", "已完成，资金已到账"),
    "EXECUTED": ("Done", "已完成"),
}


# What declining a request that answers no alert comes to; the Deals queue says what approving does instead (`approving_text`).
CLOSED_IF_DECLINED = ("Nothing runs; the request is closed.", "不会执行任何操作；该请求关闭。")


def approving_text(kind: str, lang: Lang) -> str | None:
    """What approving a waiting request comes to, in a sentence, for the kinds that have no cost or agreement effect to say."""
    if kind == "APPLY_FOR_FACILITY":
        return t(lang, "Approving submits the application; nothing runs until the bank commits.", "批准后将提交这份申请；在银行承诺之前不会执行任何操作。")
    if kind == "COMMIT_PURCHASE":  # ADR-0013
        return t(lang, "Approving books the contract's payments on the days they fall; each is paid from cash on its day.",
                 "批准后，合同的各笔付款将按到期日记入账簿；每笔款项在到期日从现金中支付。")
    if kind in ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING", "REPAY_FACILITY"):
        return t(lang, "Approving sends the request as soon as you approve.", "批准后立即提交该请求。")
    return None


def commitment_cost_words(c: Any, lang: Lang) -> dict[str, str | None]:
    """The words for an agreement's cost lines, so a figure is never said under the wrong label. `forward_label_text` names the commitment's
    `forward_value_display` ("Forward cost"): an immediate discount is not forward, so an agreement that is only a discount shows a true ¥0.00
    there; `immediate_label_text` and `immediate_text` give the discount on a line of its own ("0.85% off ¥211,900.00"), null when the agreement
    has none. Rates and faces are the obligations' own; nothing is computed."""
    parts: list[str] = []
    for o in c.obligations:
        if o.type != ObligationType.IMMEDIATE_DISCOUNT:
            continue
        rate = fmt_pct(bp(o.rate_bp)) if o.rate_bp is not None else None
        face = fmt_yuan(o.base.amount_fen) if o.base.amount_fen is not None else None
        if rate is None:
            continue
        parts.append(t(lang, f"{rate} off {face}" if face else f"{rate} off", f"{face} 减免 {rate}" if face else f"减免 {rate}"))
    return {"forward_label_text": t(lang, "Forward cost you have promised", "您已承诺的远期成本"),
            "immediate_label_text": t(lang, "Immediate discount", "立即折扣") if parts else None,
            "immediate_text": t(lang, "; ", "；").join(parts) if parts else None}


_CONFLICT = re.compile(r"^conflicting sources: the documents state (\d+) different values for (\w+)$")
_QUANTITY_WORDS = {"order_size": ("order size", "订单量"), "invoice_amount": ("invoice amount", "发票金额")}
_COUNT_WORDS = {2: ("two", "两"), 3: ("three", "三"), 4: ("four", "四")}


def abstention_words(reason: str, channels: Iterable[str], lang: Lang) -> str | None:
    """An abstention's reason in the owner's words. The compiler's "conflicting sources: the documents state 2 different values for order_size"
    becomes "The message and its attachment give two different order sizes"; `channels` are the channels of the documents the abstention quotes
    (chat, email, portal: the message; attachment). None for a reason this has no sentence for (the page then says nothing of it)."""
    if reason.startswith("unresolved reference"):  # "as usual" / "same arrangement": the terms it points to are not on the books, so nothing was booked
        return t(lang, "The buyer refers to an earlier arrangement that is not in your books.", "买方提到了一项此前的约定，但您的账目中没有这项记录。")
    if reason.startswith(DISAGREE_PREFIX):  # the model and the rules grammar read a term differently (live mode): nothing was booked on it
        return t(lang, "FLOW read a term in this message two different ways, so nothing was booked on it. Check the highlighted "
                       "words, or ask the buyer to confirm.",
                 "FLOW 对这条消息中的某项条款有两种不同的理解，因此未就此记录任何内容。请查看高亮的文字，或请买方确认。")
    if reason.startswith("unresolved scope: the discount names several invoices"):  # what is unclear, then what to ask (round four)
        return t(lang, "Their message does not say which single invoice the discount is for. Ask them which invoice it applies to.",
                 "对方的消息没有说明折扣适用于哪一张发票。请询问对方折扣适用于哪张发票。")
    if reason.startswith("partial early payment"):
        return t(lang, "They offer to pay only part of an invoice early. Ask how much they will pay, and by when.",
                 "对方提出只提前支付发票的一部分。请询问对方将支付多少、何时支付。")
    if reason.startswith("conflicting sources: the message states two different amounts for the invoice"):
        return t(lang, "Their message gives two different amounts for the invoice. Ask which amount is right.",
                 "对方的消息给出了两个不同的发票金额。请询问哪个金额正确。")
    m = _CONFLICT.match(reason)
    if m is None:
        return None
    n, kind = int(m.group(1)), m.group(2)
    kinds = set(channels)
    message = bool(kinds & {"chat", "email", "portal"})
    both = message and "attachment" in kinds
    who = (t(lang, "The message and its attachment", "消息及其附件") if both else t(lang, "The documents", "这些文件"))
    en_what, zh_what = _QUANTITY_WORDS.get(kind, (kind.replace("_", " "), kind.replace("_", " ")))
    en_n, zh_n = _COUNT_WORDS.get(n, (str(n), str(n)))
    return t(lang, f"{who} give {en_n} different {en_what}s.", f"{who}给出了{zh_n}个不同的{zh_what}。")


def lapsed_offer_text(lang: Lang, by_agreement: bool = True) -> str:
    """Why a negotiation whose invoice has changed since can no longer be answered: it is closed, and there is nothing to read on it.
    `by_agreement` says another agreement settled the invoice (the usual cause); otherwise the invoice or the dates it named have changed."""
    if by_agreement:
        return t(lang, "This offer has lapsed: the invoice it was about has since been settled under another agreement, so there is nothing to reply to.",
                 "该报价已失效：它所针对的发票此后已按另一份协议结算，无需再答复。")
    return t(lang, "This offer has lapsed: the invoice or the dates it was about have since changed, so there is nothing to reply to.",
             "该报价已失效：它所针对的发票或日期此后已有变动，无需再答复。")


def _calendar(state: FinancialState, day: int, lang: Lang) -> str:
    from datetime import date, timedelta

    d = date.fromisoformat(state.as_of) + timedelta(days=day)
    return t(lang, f"{d.day} {d.strftime('%b')} {d.year}", f"{d.year}年{d.month}月{d.day}日")


def clarification_words(state: FinancialState, offer: Any, verdict: Any, lang: Lang) -> dict[str, Any] | None:
    """Why an offer cannot be decided yet, in the owner's words, and the question to put to the buyer. Read from the verdict's
    UNRESOLVED_SCOPE gaps (`"<obligation id>:<field>"`): an invoice the message names only by amount, when the books hold several
    open invoices of that amount, lists them by date. Any other gap is said in general terms. None when nothing is unresolved."""
    from app.verifier.bind import open_receivables

    gaps = [k for v in getattr(verdict, "violations", []) if v.code.value == "UNRESOLVED_SCOPE" for k in v.inputs]
    if not gaps:
        return None
    party = party_name(state, getattr(offer, "counterparty_id", None)) or t(lang, "the buyer", "买方")
    obligations = {o.id: o for o in getattr(offer, "obligations", [])}
    for key in gaps:
        ob_id, _, fieldname = key.partition(":")
        ob = obligations.get(ob_id)
        if ob is None or fieldname != "base.receivable_id":
            continue
        pool = open_receivables(state, ob.counterparty_id)
        if ob.base.amount_fen is not None:
            pool = [r for r in pool if r.face_fen == ob.base.amount_fen]
        amount = fmt_yuan(ob.base.amount_fen) if ob.base.amount_fen is not None else ""
        options = [{"receivable_id": r.id, "sent_text": _calendar(state, r.issue_day, lang), "due_text": _calendar(state, r.due_day, lang),
                    "face_display": fmt_yuan(r.face_fen)} for r in sorted(pool, key=lambda r: (r.issue_day, r.id))]
        if len(options) > 1:
            listed_en = " and ".join(f"sent {o['sent_text']} (due {o['due_text']})" for o in options)
            listed_zh = "和".join(f"{o['sent_text']}开出（{o['due_text']}到期）" for o in options)
            sent_en = " or ".join(f"the one dated {o['sent_text']}" for o in options)
            sent_zh = "还是".join(f"{o['sent_text']}的那张" for o in options)
            return {
                "kind": "WHICH_INVOICE", "options": options,
                "text": t(lang, f"Which {amount} invoice does {party} mean? You have {len(options)} open: {listed_en}. FLOW will not guess, "
                                "because the discount would land on the wrong invoice.",
                          f"{party}指的是哪一张 {amount} 发票？您有 {len(options)} 张未收：{listed_zh}。FLOW 不会猜测，否则折扣可能用错发票。"),
                "ask_buyer_text": t(lang, f"Thanks for the offer. Which {amount} invoice would you like to settle early: {sent_en}?",
                                    f"感谢您的报价。请问您希望提前结清哪一张 {amount} 发票：{sent_zh}？"),
            }
        if not options:
            return {"kind": "NO_SUCH_INVOICE", "options": [],
                    "text": t(lang, f"{party} refers to {amount or 'an'} invoice that is not open in your books. Check whether it was paid, or ask "
                                    f"{party} which invoice they mean.",
                              f"{party}提到的 {amount} 发票在您的账簿中不是未收状态。请确认是否已付款，或询问{party}指的是哪一张。"),
                    "ask_buyer_text": t(lang, "Thanks for the offer. Which invoice do you mean? We can't find it among the open ones.",
                                        "感谢您的报价。请问您指的是哪一张发票？我们在未收发票中没有找到它。")}
    return {"kind": "OTHER", "options": [],
            "text": t(lang, f"Part of {party}'s offer cannot be pinned down from the message and your books, so FLOW books nothing until "
                            f"{party} clarifies.", f"{party}报价中的部分内容无法根据消息和账簿确定，因此在{party}澄清之前 FLOW 不会记录任何内容。"),
            "ask_buyer_text": None}


def business_action_text(code: str, lang: Lang) -> str:
    """The owner's words for `business_action` (accept, counter, decline, needs_owner, cannot)."""
    en, zh = _RESPONSE_WORDS.get(code, _RESPONSE_WORDS["cannot"])
    return t(lang, en, zh)


_ANSWER_STATE_WORDS = {"declined": ("Declined by the buyer", "买方已拒绝"), "no_answer": ("Closed without an answer", "未获答复，已关闭")}


def decision_state_text(family: str, state: str, lang: Lang, *, response: str | None = None, residual: bool = False,
                        lapsed_by_agreement: bool = True, answer: str | None = None) -> str:
    """A decision's state in the owner's words. A deal ready for a response says what the verdict recommends ("Acceptable,
    awaiting agreement" for an acceptable offer, never "Agreed": the agreement words follow the commitment only). A funding that is
    done while the reserve is still short says so ("Funded, reserve still short"): `residual` is the decision record's own."""
    if family == "DEAL":
        if state == "NO_DEAL" and answer in _ANSWER_STATE_WORDS:  # an offer sent outside FLOW: the buyer said no, or never answered
            return t(lang, *_ANSWER_STATE_WORDS[answer])
        if state == "RESPONSE_READY":
            return business_action_text(response or "cannot", lang)
        en, zh = (_LAPSED_CHANGED if state == "LAPSED" and not lapsed_by_agreement
                  else _DEAL_STATE_WORDS.get(state, (state.replace("_", " ").capitalize(), state)))
    else:
        if residual and state in ("SETTLED", "EXECUTED"):
            return t(lang, "Funded, reserve still short", "已融资，储备仍有缺口")
        en, zh = _FUNDING_STATE_WORDS.get(state, _DEAL_STATE_WORDS.get(state, (state.replace("_", " ").capitalize(), state)))
    return t(lang, en, zh)


def decision_state_tone(state: str, *, awaited: bool, residual: bool) -> str:
    """The colour of a decision's state, said by the server so no page colours a state itself: `bad` for a request that failed or an early
    payment that did not arrive; `warn` whenever the owner is awaited or a residual is set; `ok` only for a deal fulfilled or a funding
    settled with nothing left short; `info` for what is under way; `neutral` for what is closed without news."""
    if state in ("FAILED", "MISSED"):
        return "bad"
    if awaited or residual:
        return "warn"
    if state in ("FULFILLED", "SETTLED"):
        return "ok"
    if state in ("DECLINED", "NO_DEAL", "EXPIRED", "REVOKED", "LAPSED", "REPLIED"):
        return "neutral"
    return "info"


def waiting_text(code: str, party: str, day: int | None, today: int, lang: Lang, *, family: str = "DEAL", lapsed: bool = False) -> str:
    """What FLOW is waiting for, as one sentence. `party` is the name of the buyer or the lender where there is one. `lapsed`: the decision is a
    negotiation that lapsed, which nobody is waiting on and nothing was completed for."""
    if lapsed:
        return t(lang, "Nothing to do: this offer lapsed.", "无需处理：该报价已失效。")
    when = when_text(day, today, lang) if day is not None else ""
    if code == "OWNER_RESPONSE":
        return t(lang, "Waiting for your response.", "等待您的回复。")
    if code == "BUYER_CLARIFICATION":
        return t(lang, f"Waiting for {party or 'the buyer'} to clarify the offer.", f"等待{party or '买方'}澄清报价。")
    if code == "BUYER_ANSWER":
        return (t(lang, f"Waiting for {party or 'the buyer'} to answer the offer you sent; it closes {when}.",
                  f"等待{party or '买方'}答复您发出的报价；该报价将于{when}截止。")
                if day is not None else t(lang, f"Waiting for {party or 'the buyer'} to answer the offer you sent.",
                                          f"等待{party or '买方'}答复您发出的报价。"))
    if code == "OWNER_APPROVAL":
        if day is None:
            return t(lang, "Waiting for your approval.", "等待您批准。")
        if family == "DEAL":
            return t(lang, f"Waiting for your approval; the offer expires {when}.", f"等待您批准；该报价将于{when}到期。")
        return t(lang, f"Waiting for your approval; the cash is needed {when}.", f"等待您批准；资金需要在{when}到位。")
    if code == "BANK_RECEIPT":
        return (t(lang, f"Waiting for {party or 'the buyer'} to pay, due {when}.", f"等待{party or '买方'}付款，应于{when}到账。")
                if day is not None else t(lang, f"Waiting for {party or 'the buyer'} to pay.", f"等待{party or '买方'}付款。"))
    if code == "INVOICE_ISSUE":
        return (t(lang, f"Waiting for the next invoice to {party or 'the buyer'}, issued {when}, which carries the new terms.",
                  f"等待下一张开给{party or '买方'}的发票（{when}开出），其中包含新条款。")
                if day is not None else t(lang, "Waiting for the next invoice, which carries the new terms.", "等待下一张发票，其中包含新条款。"))
    if code == "FUNDING_SETTLEMENT":
        return (t(lang, f"Waiting for {party or 'the lender'} to land the funds {when}.", f"等待{party or '放款方'}于{when}放款到账。")
                if day is not None else t(lang, f"Waiting for {party or 'the lender'} to land the funds.", f"等待{party or '放款方'}放款到账。"))
    if code == "OWNER_DECISION":
        return (t(lang, f"Waiting for your decision; the shortfall starts {when}.", f"等待您的决定；缺口从{when}开始。")
                if day is not None else t(lang, "Waiting for your decision.", "等待您的决定。"))
    return t(lang, "Nothing is waiting: the action is complete.", "没有待办事项：操作已完成。")


def execution_summary(lang: Lang, today: int, *, family: str, state: str, buyer: str | None, agreement: str | None,
                      requested_fen: int, landed_fen: int, in_transit_fen: int, arrival_day: int | None, repaid_fen: int,
                      pending: int, refused: int, blocked: bool, as_asked: bool = False) -> str:
    """What has actually been executed for this decision, in one or two sentences (F04: never "nothing executed" after a
    negotiation funded a gap). `agreement` is "recorded", "waiting" or None for a deal; the amounts are the operations' own
    amounts and the funding lots' own principal."""
    parts: list[str] = []
    if agreement == "waiting":
        pending = max(pending - 1, 0)  # the agreement is the step already said
    if agreement == "recorded":
        parts.append(t(lang, f"Agreement with {buyer or 'the buyer'} recorded.", f"已记录与{buyer or '买方'}的协议。"))
        if as_asked and not requested_fen:  # the owner accepted the request as asked: no reply was sent and no gap plan runs
            parts.append(t(lang, "No payment and no funding moved.", "没有付款，也没有融资。"))
    elif agreement == "waiting":
        parts.append(t(lang, "The agreement is waiting for your approval and is not in force.", "协议正等待您批准，尚未生效。"))
    if requested_fen:
        if landed_fen and not in_transit_fen:
            parts.append(t(lang, f"Funding of {fmt_yuan(requested_fen)} was requested and has landed.",
                           f"已提交 {fmt_yuan(requested_fen)} 的融资，并已到账。"))
        elif in_transit_fen:
            when = when_text(arrival_day, today, lang) if arrival_day is not None else ""
            parts.append(t(lang, f"Funding of {fmt_yuan(requested_fen)} was requested; {fmt_yuan(in_transit_fen)} is on its way"
                                 f"{' and lands ' + when if when else ''}.",
                           f"已提交 {fmt_yuan(requested_fen)} 的融资；{fmt_yuan(in_transit_fen)} 在途"
                           f"{'，将于' + when + '到账' if when else ''}。"))
        else:
            parts.append(t(lang, f"Funding of {fmt_yuan(requested_fen)} was requested.", f"已提交 {fmt_yuan(requested_fen)} 的融资。"))
    if repaid_fen:
        parts.append(t(lang, f"{fmt_yuan(repaid_fen)} was repaid.", f"已还款 {fmt_yuan(repaid_fen)}。"))
    if pending:
        parts.append(t(lang, "One step is waiting for your approval." if pending == 1 else f"{pending} steps are waiting for your approval.",
                       f"有 {pending} 步正等待您批准。"))
    if refused:
        parts.append(t(lang, "One step could not run. No money moved for it." if refused == 1
                       else f"{refused} steps could not run. No money moved for them.", f"有 {refused} 步未能执行，对应资金未动。"))
    if blocked and family == "DEAL":
        parts.append(t(lang, "The gap was not funded: today's funding plan could not run.", "缺口未获融资：今天的融资方案无法执行。"))
    if not parts and family == "DEAL" and state == "DECLINED":
        return t(lang, "You declined this request. Nothing was agreed, sent or funded.", "您已拒绝该请求。未达成、发送或融资任何事项。")
    if not parts:
        return t(lang, "Nothing has been executed yet.", "尚未执行任何操作。")
    return " ".join(parts)


def lowest_point_words(gap_fen: int, low_day: int, now_fen: int | None, today: int, lang: Lang) -> str:
    """The after-state of a cure that leaves the reserve short: the gap at the lowest point (the episode's minimum), and today's gap
    beside it when the shortfall has begun, so the worst point is never read as today's. Both figures are the engine's own."""
    when = when_text(low_day, today, lang)
    return t(lang, f"At its lowest point, {when}, cash {'would still be' if low_day >= today else 'was still'} {fmt_yuan(gap_fen)} below your minimum cash reserve"
                   + (f"; today it is {fmt_yuan(now_fen)} below" if now_fen is not None else "") + ".",
             f"在最低点（{when}），现金仍比最低现金储备低 {fmt_yuan(gap_fen)}" + (f"；今天低 {fmt_yuan(now_fen)}" if now_fen is not None else "") + "。")


def quote_view(fact: Any, state: FinancialState, today: int, quote_day: int, lang: Lang) -> dict[str, Any]:
    """A stored QUOTED fact as the owner reads it: one line per leg (what, amount, cost, rate, when it lands), the total, the
    basis of the price, the after-state and what declining leaves. Every figure is the fact's; nothing is priced here."""
    lines: list[dict[str, Any]] = []
    for leg in fact.legs:
        # a cure's rate is the alert's own, shown to one place as the home shows it; a router line states its rate to two
        rate = (fmt_pct(Fraction(leg.annual_rate.num, leg.annual_rate.den), 2 if fact.source == "router" else 1)
                if leg.annual_rate is not None else None)
        lines.append({
            "label": leg_words(state, leg.kind, leg.facility_id, leg.receivable_id, leg.amount_fen, lang),
            "op_id": leg.op_id, "kind": leg.kind, "amount_fen": leg.amount_fen, "amount_display": fmt_yuan(leg.amount_fen),
            "cost_fen": leg.cost_fen, "cost_display": fmt_yuan(leg.cost_fen) if leg.cost_fen is not None else None,
            "rate_text": rate, "cost_days": leg.cost_days, "lands_day": leg.lands_day,
            "lands_when": when_text(leg.lands_day, today, lang) if leg.lands_day is not None else None,
            "above_ceiling": leg.above_ceiling,
        })
    note = None
    if fact.cost_note == "draw_interest_excluded":
        names = ", ".join(facility_name(state, leg.facility_id) for leg in fact.legs
                          if leg.kind == "DRAW_FACILITY" and leg.cost_fen is None)
        note = t(lang, f"Interest on the {names} draw is not included: it runs only while the balance stays drawn.",
                 f"不含{names}提款的利息：利息只在余额未还期间产生。")
    basis_parts: list[str] = []
    if note:
        basis_parts.append(note)
    elif any(leg.kind == "SUBMIT_INVOICE_FOR_FINANCING" and leg.cost_fen is not None for leg in fact.legs):
        basis_parts.append(t(lang, "Invoice financing is billed in whole 30-day periods until the invoice is paid.",
                             "发票融资按整 30 天计费，直至发票付清。"))
    if fact.source == "router":
        for leg in fact.legs:
            if leg.kind == "DRAW_FACILITY" and leg.cost_end_day is not None:
                basis_parts.append(t(lang, f"Estimated through the expected repayment of the {facility_name(state, leg.facility_id)} "
                                           f"{when_text(leg.cost_end_day, today, lang)}; the final interest depends on the actual repayment day.",
                                     f"按预计{when_text(leg.cost_end_day, today, lang)}偿还{facility_name(state, leg.facility_id)}估算；最终利息取决于实际还款日。"))
    lands = [leg.lands_day for leg in fact.legs if leg.lands_day is not None]
    if not fact.projected:
        # nothing was projected (a repayment, an application, a projection that failed): say nothing about the reserve
        after = (t(lang, "The balance is repaid and the interest stops.", "余额还清，利息停止。")
                 if fact.alert_kind == "FACILITY_REPAYABLE" else None)
    elif fact.after_first_short_day is None:
        after = t(lang, f"Cash stays above your minimum cash reserve for the next {fact.horizon_days} days.",
                  f"未来 {fact.horizon_days} 天现金都保持在您的最低现金储备以上。")
    elif fact.restores_reserve is False and fact.residual_shortfall_fen is not None:
        if fact.after_lowest_day is not None:  # the gap at the lowest point, and today's beside it when this is read the day it was asked
            shortfall_now = fact.if_decline.shortfall_fen if (fact.if_decline is not None and quote_day == today and fact.alert_day is not None
                                                              and fact.alert_day <= today) else None
            after = lowest_point_words(fact.residual_shortfall_fen, fact.after_lowest_day, shortfall_now, today, lang)
        elif fact.after_first_short_day < today:  # it began in the past: how long, not "from 6 days ago"
            n = today - fact.after_first_short_day
            after = t(lang, f"Cash has stayed {fmt_yuan(fact.residual_shortfall_fen)} below your minimum cash reserve for {n} {'day' if n == 1 else 'days'}.",
                      f"现金已连续 {n} 天比最低现金储备低 {fmt_yuan(fact.residual_shortfall_fen)}。")
        else:
            after = t(lang, f"Cash stays {fmt_yuan(fact.residual_shortfall_fen)} below your minimum cash reserve from "
                            f"{when_text(fact.after_first_short_day, today, lang)}.",
                      f"从{when_text(fact.after_first_short_day, today, lang)}起现金仍比最低现金储备低 {fmt_yuan(fact.residual_shortfall_fen)}。")
    else:
        after = t(lang, f"Cash stays above your minimum cash reserve for the next {max(fact.after_first_short_day - 1 - quote_day, 0)} days.",
                  f"未来 {max(fact.after_first_short_day - 1 - quote_day, 0)} 天现金都保持在最低现金储备以上。")
    return {
        "recorded": True,
        "quoted_when": when_text(quote_day, today, lang),
        "lines": lines,
        "total_fen": fact.total_cost_fen,
        "total_display": fmt_yuan(fact.total_cost_fen) if fact.total_cost_fen is not None else None,
        "cost_note": note,
        "rate_basis": " ".join(basis_parts) or None,
        "lands_day": max(lands) if lands else None,
        "lands_when": when_text(max(lands), today, lang) if lands else None,
        "after": after,
        "if_declined": decline_words(fact.if_decline, fact.alert_kind, today, lang),
        "needs_owner": fact.needs_owner,
        "text": None,
    }


def decline_words(d: Any, alert_kind: str, today: int, lang: Lang) -> str | None:
    """What declining leaves, from the stored shortfall and days."""
    if d is None:
        return t(lang, "Interest keeps running on the drawn balance.", "已提款余额将继续产生利息。") if alert_kind == "FACILITY_REPAYABLE" else None
    if d.kind == "below_zero" and d.zero_day is not None:
        return t(lang, f"Cash goes below zero {when_text(d.zero_day, today, lang)}.", f"现金将在{when_text(d.zero_day, today, lang)}跌破零。")
    if d.kind == "below_reserve" and d.shortfall_fen is not None and d.day is not None:
        peak = d.max_shortfall_fen if d.max_shortfall_fen is not None else d.shortfall_fen
        worst = when_text(d.worst_day if d.worst_day is not None else d.day, today, lang)
        return t(lang, f"{fmt_yuan(d.shortfall_fen)} below your minimum cash reserve {when_text(d.day, today, lang)}; the gap peaks at "
                       f"{fmt_yuan(peak)} {worst}.",
                 f"{when_text(d.day, today, lang)}比最低现金储备低 {fmt_yuan(d.shortfall_fen)}；缺口在{worst}最大，为 {fmt_yuan(peak)}。")
    return t(lang, "Interest keeps running on the drawn balance.", "已提款余额将继续产生利息。") if d.kind == "closed" else None


def quote_not_recorded(decided: bool, lang: Lang) -> dict[str, Any]:
    """A decision with no QUOTED fact: a decided row never shows a price taken from today's alert; a waiting row says its price
    is today's."""
    text = (t(lang, "The quoted cost was not recorded.", "当时报价的成本没有记录。") if decided
            else t(lang, "Price today.", "按今日价格。"))
    return {"recorded": False, "quoted_when": None, "lines": [], "total_fen": None, "total_display": None, "cost_note": None,
            "rate_basis": None, "lands_day": None, "lands_when": None, "after": None, "if_declined": None, "needs_owner": None,
            "text": text}


def lands_difference(quoted_lands: int | None, actual_lands: int | None, today: int, lang: Lang) -> str | None:
    """The difference between the quoted landing day and the lot's own, when they differ."""
    if quoted_lands is None or actual_lands is None or quoted_lands == actual_lands:
        return None
    later = actual_lands > quoted_lands
    return t(lang, f"Approved {'later' if later else 'sooner'} than quoted, so the cash lands {when_text(actual_lands, today, lang)} "
                   f"instead of {when_text(quoted_lands, today, lang)}.",
             f"批准时间{'晚于' if later else '早于'}报价，资金将于{when_text(actual_lands, today, lang)}到账，而非{when_text(quoted_lands, today, lang)}。")


def remaining_task_words(shortfall_fen: int | None, starts_day: int | None, today: int, lang: Lang,
                         committed_cure: bool | None = False) -> str:
    """The sentence for the reserve still at risk after a cure: F17. When a committed cure exists the engine has a plan, so the
    sentence points at the next step instead of saying nothing restores the reserve."""
    if shortfall_fen is None:
        return t(lang, "Nothing is waiting: the action is complete.", "没有待办事项：操作已完成。")
    money = fmt_yuan(shortfall_fen)
    if starts_day is not None and starts_day < today:  # it began in the past: say how long it has been short, not "from 57 days ago"
        n = today - starts_day
        en = f"Your minimum cash reserve has been {money} short for {n} {'day' if n == 1 else 'days'}"
        zh = f"您的最低现金储备已差 {money} 达 {n} 天"
    else:
        when = when_text(starts_day, today, lang) if starts_day is not None else ""
        en = f"Your minimum cash reserve is still {money} short{' from ' + when if when else ''}"
        zh = f"您的最低现金储备仍差 {money}{'，从' + when + '起' if when else ''}"
    if committed_cure:
        return t(lang, f"{en}; a funding plan is ready (see the next step).", f"{zh}；融资方案已准备好（见下一步）。")
    return t(lang, f"{en}; no committed funding restores it. This needs your decision.", f"{zh}；没有已承诺的融资能恢复它。这需要您决定。")


def option_label(label: str | None, lang: Lang) -> str:
    """A counter's label ("Option A") as a Business page names it ("方案 A" in Chinese); any other label is the counter's own."""
    if not label:
        return ""
    m = re.fullmatch(r"Option ([A-Z])", label)
    return t(lang, label, f"方案 {m.group(1)}") if m else label


def funding_lines(state: FinancialState, legs: Sequence[tuple[str, str | None, int, int | None]], cost_fen: int | None, today: int,
                  lang: Lang, *, past: bool = False) -> list[str]:
    """What a funding plan would do, one short line per leg and one for its cost, from the plan's own figures. A leg is (kind, facility id,
    amount in fen, the day its cash lands) with kind DRAW or FINANCE_INVOICE: "Draws ¥149,986.20 on the Bank credit line today",
    "Requests ¥255,000.00 of invoice financing, arriving in 3 days", "Estimated cost ¥3,113.93". Nothing is priced here."""
    out: list[str] = []
    for kind, facility_id, amount, lands in legs:
        money, fac = fmt_yuan(amount), facility_name(state, facility_id)
        arrives = lands is None or lands <= today
        when = when_text(lands if lands is not None else today, today, lang)
        if kind == "DRAW":
            out.append(t(lang, f"{'Drew' if past else 'Draws'} {money} on the {fac}" + (" today" if arrives else f", arriving {when}"),
                         f"{'已' if past else ''}从{fac}提款 {money}，" + ("今天到账" if arrives else f"{when}到账")))
        else:
            out.append(t(lang, f"{'Requested' if past else 'Requests'} {money} of invoice financing, arriving {when}",
                         f"{'已' if past else ''}申请 {money} 的发票融资，{when}到账"))
    if legs and cost_fen is not None:
        out.append(t(lang, f"Estimated cost {fmt_yuan(cost_fen)}", f"预计成本 {fmt_yuan(cost_fen)}"))
    return out


def send_scope_text(lang: Lang, label: str | None = None) -> str:
    """What sending a counter does: the buyer's reply is simulated, the agreement waits for the owner when it changes terms, and the
    funding runs within the limits."""
    which = label or t(lang, "this counter", "此还价")
    return t(lang, f"Sends {which} to the buyer (the reply is simulated); records the agreement, with your approval when it changes "
                   f"terms; runs the funding for any remaining gap within your limits.",
             f"向买方发送{which}（回复为模拟）；记录协议，若改变条款则需您批准；在您的额度内为剩余缺口融资。")


# ---------------------------------------------------------------- the owner's decision on a document, in words

_DOC_REF = re.compile(r"\s+(?=\S*\d)[A-Z0-9][A-Za-z0-9_./-]*$")  # a trailing reference code ("GBR-IF-2026-118")
_ID_PAREN = re.compile(r"\s*[(（](?:APR|DOC|RCV|COM|FAC|BUYER|OFF|CTR|VER)-[\w-]+[)）]")
_DOC_KIND_WORDS = {"BUYER_CONTRACT": ("the buyer contract", "买方合同"), "LENDER_AGREEMENT": ("the lender agreement", "贷款方协议")}


def without_record_ids(text: str | None) -> str | None:
    """A sentence without the parenthesised record id the executor writes after "Queued for owner approval"; the id lives in the row's
    own id fields."""
    return _ID_PAREN.sub("", text) if text is not None else None


def document_name(title: str | None, kind: str | None, lang: Lang = "en") -> str:
    """A document as the owner names it: its title without the contract's reference code ("the invoice financing agreement"), in the
    kind's own words when the title is not one the books know (Chinese) or still holds a code."""
    from app.api.engine_zh import _DOC_TITLES

    plain = _DOC_REF.sub("", (title or "").strip())
    known = plain in _DOC_TITLES
    fallback = _DOC_KIND_WORDS.get(kind or "", ("the document", "该文件"))
    if lang == "zh":
        return _DOC_TITLES[plain] if known else fallback[1]
    if known:
        return "the " + plain[:1].lower() + plain[1:]
    if plain and not _ID_CODES.search(plain):
        return f"“{plain}”"
    return fallback[0]


_ID_CODES = re.compile(r"(?:DOC|RCV|COM|FAC|BUYER|OFF|CTR|VER|APR)-|RI:")


def document_decision_words(state: FinancialState | None, *, confirmed: bool, title: str | None, kind: str | None,
                            link_facility_id: str | None, lang: Lang = "en") -> dict[str, str | None]:
    """`event_text` / `event_detail` of the owner's CONFIRM_DOCUMENT / REJECT_DOCUMENT: a Business sentence from the record (its kind and
    title in words), never its id or the contract's reference code. A confirmed document changes nothing in the books."""
    name = document_name(title, kind, lang)
    if not confirmed:
        return {"event_text": t(lang, f"You rejected {name}. Nothing was recorded from it.", f"您已驳回{name}。未从中记录任何内容。"),
                "event_detail": None}
    detail = None
    if link_facility_id:
        fac = facility_name(state, link_facility_id) if state is not None else ""
        if fac:
            detail = t(lang, f"Linked to {fac} for reference; the facility itself is unchanged.",
                       f"已关联到{fac}以供参考；该融资工具本身未变。")
    return {"event_text": t(lang, f"You confirmed {name}, as FLOW read it. Nothing in the books changed.",
                            f"您已确认{name}，按 FLOW 读取的内容。账本未作任何更改。"),
            "event_detail": detail}


def deal_back_label(lang: Lang, who: str) -> str:
    """The words of a link back to a deal: one place, used by the Customer overview's back link and by the Cash page's."""
    return t(lang, f"Back to the {who} deal", f"返回与{who}的交易")
