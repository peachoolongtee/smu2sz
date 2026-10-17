"""ADR-0014: what a confirmed customer contract can set up in the books, derived again by code from the stored record.

A confirmed buyer contract may set up exactly one thing, its customer's repeating invoice (`RecurringInvoice`: the price of
one delivery, the invoicing interval, the next invoice day, the payment days). This module decides whether it can, and with
what figures, on the books as they are today. It never writes: the preview route shows the result and the executor derives
it again inside the operation's unit of work (`Executor._set_up_terms`), refusing unless the figures and the hash are those
the owner was shown.

Only figures that survive every check below are used; anything missing or unchecked blocks, with the reason in words:

- the record is a CONFIRMED buyer contract, not superseded, with no blocking or party flag, and a COMPILED reading;
- it names the chosen customer as its buyer (PARTY_BUYER), not as its supplier;
- PRICE (per delivery), INVOICING (a day interval with a first date) and PAYMENT_TERMS (calendar days from the invoice
  date) are each stated once, each quotes the document verbatim, and each figure is parsed again by the reader's own code
  from the quoted words; no abstention other than a note, and no failed cross-check, touches them;
- the contract's end is certain and not inside today's forecast window (the engine's repeating invoice has no end): exactly
  one checked END_DATE, or a term in months from a checked start date, and no unexplained term, renewal or expiry wording;
  END_NOT_CERTAIN blocks otherwise (CT-1).

Pure: no store, no clock, no I/O.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from app.compiler.contract_parsing import (
    DATE_PAT,
    basis_of,
    business_days,
    parse_date,
    parse_days,
    parse_money,
    parse_months,
    unit_of,
)
from app.compiler.contract_rules import DURATION, END, START
from app.contracts.derive import buyer_terms, day_of
from app.contracts.parties import PARTY_FLAG_KINDS, party_matches, registry_names
from app.domain.models import (
    CompileStatus,
    ContractField,
    ContractRecord,
    ContractTerm,
    Counterparty,
    DocumentKind,
    DocumentStatus,
    FinancialState,
    PaymentBasis,
    PriceUnit,
    RecurringInvoice,
)

F = ContractField
Status = Literal["READY", "ALREADY", "CONFLICT", "BLOCKED"]

# The fields whose figures become the repeating invoice, in the order they are shown.
SET_UP_FIELDS = (F.PRICE, F.INVOICING, F.PAYMENT_TERMS)
# The party check's flags (`app.contracts.parties.PARTY_FLAG_KINDS`): any of them on a record blocks the set-up.
_DATE_RE = re.compile(DATE_PAT, re.IGNORECASE)


@dataclass(frozen=True)
class Problem:
    """One reason the set-up cannot be made, in the owner's words, with a stable code for tests and the web."""

    code: str
    en: str
    zh: str


@dataclass(frozen=True)
class Source:
    """A contract term a figure came from: its field, clause number and verbatim quote."""

    field: ContractField
    clause: str | None
    quote: str
    value_text: str
    start: int
    end: int


@dataclass(frozen=True)
class TermsSetUp:
    """What the contract would set up, and whether it can, on the books of `today`."""

    document_id: str
    doc_hash: str
    counterparty_id: str
    status: Status
    recurring: RecurringInvoice | None  # the repeating invoice the contract gives (None when its figures cannot be read)
    existing: RecurringInvoice | None  # the customer's repeating invoice in the books today, if any
    sources: tuple[Source, ...] = ()
    problems: tuple[Problem, ...] = ()
    end_day: int | None = None
    early_payment: ContractTerm | None = None  # read, never set up (an option the forecast does not assume)
    terms_hash: str | None = None  # set when the figures are read (READY, ALREADY or CONFLICT)
    notes: tuple[Problem, ...] = field(default_factory=tuple)  # warnings that do not block

    @property
    def ready(self) -> bool:
        return self.status == "READY"


def terms_hash(document_id: str, doc_hash: str, ri: RecurringInvoice, sources: tuple[Source, ...]) -> str:
    """sha256 of the canonical JSON of what the owner is shown and approves: the document, its text hash, the customer, the
    four figures and the span each source term quotes."""
    body = {"document_id": document_id, "doc_hash": doc_hash, "counterparty_id": ri.counterparty_id,
            "face_fen": ri.face_fen, "every_days": ri.every_days, "next_issue_day": ri.next_issue_day,
            "terms_days": ri.terms_days, "sources": [[s.field.value, s.start, s.end] for s in sources]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- who the contract is with
#
# The comparison is the party check's own (`app.contracts.parties`, the owner's rule of 17 Oct): the registry name and its short
# form against the names the reading found. That check already blocks confirming a document that does not name the chosen
# counterparty at all; here the contract must name the customer as its BUYER, never as its supplier.


def _party_problem(record: ContractRecord, party: Counterparty) -> Problem | None:
    assert record.contract is not None
    names = registry_names(party)
    buyers = [(t.text or t.value_text or "").strip() for t in record.contract.terms if t.field == F.PARTY_BUYER]
    suppliers = [(t.text or t.value_text or "").strip() for t in record.contract.terms if t.field == F.PARTY_SUPPLIER]
    if party_matches(suppliers, names) and not party_matches(buyers, names):
        return Problem("PARTY_IS_SUPPLIER",
                       f"The contract names {party.name} as the supplier, not the buyer: it is not a contract under which "
                       f"this customer pays you.",
                       f"合同把{party.name}列为供货方而非买方：这不是该客户向您付款的合同。")
    if not [x for x in buyers if x]:
        return Problem("PARTY_NOT_READ", "The reading found no buyer named in the contract, so it cannot be checked "
                       "that the contract is with this customer.",
                       "未从合同中读出买方名称，无法核实合同是与该客户签订的。")
    if not party_matches(buyers, names):
        return Problem("PARTY_NOT_THIS_CUSTOMER",
                       f"The contract's buyer is {buyers[0]}, not {party.name.rstrip('.')}.",
                       f"合同的买方是{buyers[0]}，而不是{party.name}。")
    return None


# ---------------------------------------------------------------- the terms, checked against their quotes


def _quoted(record: ContractRecord, t: ContractTerm) -> bool:
    """The term quotes the document verbatim and its value fragment sits inside the quote."""
    text = record.document.text
    if not (0 <= t.span.start < t.span.end <= len(text)) or text[t.span.start:t.span.end] != t.span.text:
        return False
    return bool(t.value_text) and (t.value_text or "") in t.span.text


def _dates_in(quote: str) -> set[str]:
    out: set[str] = set()
    for m in _DATE_RE.finditer(quote):
        p = parse_date(m.group(0))
        if p.ok:
            out.add(str(p.value))
    return out


_LABEL = {F.PRICE: ("the price", "价格"), F.INVOICING: ("the invoicing interval", "开票间隔"),
          F.PAYMENT_TERMS: ("the payment terms", "账期")}


def _figure_problem(record: ContractRecord, t: ContractTerm) -> Problem | None:
    """Whether the term's figures are the ones the reader's own code finds in its quoted words."""
    en, zh = _LABEL[t.field]
    clause = f" (clause {t.clause})" if t.clause else ""
    if not _quoted(record, t):
        return Problem("NOT_QUOTED", f"The reading of {en}{clause} does not quote the contract word for word.",
                       f"{zh}的读取结果{('（第 ' + t.clause + ' 条）') if t.clause else ''}与合同原文不一致。")
    v = t.value_text or ""
    if t.field == F.PRICE:
        p = parse_money(v)
        ok = p.ok and p.value == t.amount_fen and (t.amount_fen or 0) > 0
        if ok and (t.unit != PriceUnit.PER_DELIVERY or unit_of(t.span.text) != PriceUnit.PER_DELIVERY):
            return Problem("PRICE_NOT_PER_DELIVERY",
                           f"The price{clause} is not stated per delivery or batch, so it is not the amount of each invoice.",
                           "合同价格不是按每批或每次交货计算的，不能作为每张发票的金额。")
    elif t.field == F.INVOICING:
        if t.months is not None and t.days is None:
            return Problem("INVOICING_MONTHLY", f"The contract invoices monthly{clause}; the books need an interval in days.",
                           "合同按月开票；账簿需要以天数表示的开票间隔。")
        p = parse_days(v)
        ok = p.ok and p.value == t.days and 1 <= (t.days or 0) <= 366 and t.date is not None and t.date in _dates_in(t.span.text)
        if ok and business_days(v):
            return Problem("INVOICING_BUSINESS_DAYS", f"The invoicing interval{clause} is in business days; the books count "
                           f"calendar days.", "开票间隔以工作日计算；账簿按自然日计算。")
        if t.date is None:
            return Problem("NO_FIRST_INVOICE", f"The contract does not say when the first regular invoice is{clause}.",
                           "合同没有写明第一张定期发票的日期。")
    else:  # PAYMENT_TERMS
        if t.basis != PaymentBasis.INVOICE or basis_of(t.span.text) != PaymentBasis.INVOICE:
            return Problem("TERMS_NOT_FROM_INVOICE",
                           f"The payment days{clause} do not count from the invoice date, as the books count them.",
                           "账期不是从发票日期起算的，而账簿从发票日期起算。")
        if t.business_days or business_days(v):
            return Problem("TERMS_BUSINESS_DAYS", f"The payment terms{clause} are in business days; the books count "
                           f"calendar days.", "账期以工作日计算；账簿按自然日计算。")
        p = parse_days(v)
        ok = p.ok and p.value == t.days and t.days is not None and 0 <= t.days <= 365
    if not ok:
        return Problem("FIGURE_NOT_IN_QUOTE", f"The figure read for {en}{clause} is not the one its quoted words state.",
                       f"{zh}读出的数字与所引用原文中的数字不一致。")
    return None


def _missing(field_: ContractField, n: int) -> Problem:
    en, zh = _LABEL[field_]
    if n == 0:
        return Problem(f"MISSING_{field_.value}", f"The reading has no {en.removeprefix('the ')}.",
                       f"读取结果中没有{zh}。")
    return Problem(f"TWICE_{field_.value}", f"The contract states {en} more than once.", f"合同多次写明{zh}。")


def _abstention_problems(record: ContractRecord) -> list[Problem]:
    """A dropped or conflicting term in a field the set-up needs, or any failed cross-check of the reading."""
    assert record.contract is not None
    out: list[Problem] = []
    needed = {f.value for f in SET_UP_FIELDS}
    for a in record.contract.abstentions:
        name = a.field.removeprefix("note:")
        if a.reason.startswith("check failed"):
            out.append(Problem("CHECK_FAILED", "A check of the reading failed: " + a.reason.removeprefix("check failed: "),
                               "读取结果的一项核对未通过。"))
        elif name in needed and not a.field.startswith("note:"):
            en, zh = _LABEL[F(name)]
            out.append(Problem(f"DROPPED_{name}", f"Part of the contract about {en} could not be read exactly.",
                               f"合同中关于{zh}的部分无法准确读取。"))
    return out


# ---------------------------------------------------------------- when the contract ends (CT-1: fail closed)
#
# The engine's repeating invoice has no end, so a contract that ends inside the forecast window cannot be set up. That check
# is only as good as the end date it is given. An end is used when exactly one END_DATE term quotes the document, re-parses
# from its quote to the same date, and agrees with any term in months counted from the start date. Wording about a term,
# renewal, expiry or lapse that no checked end or term covers blocks: the contract may end sooner than the reading says. "The
# contract states no end date" is said only when nothing in the reading or the text points to an end.

# Wording that points to an end. Deliberately narrow on "term" and "until" (payment terms; "withheld until acceptance").
_END_WORDING = re.compile(
    r"\b(?:term|period|duration)\s+of\s+[^.;\n]{0,30}?\b(?:months?|years?)\b"
    r"|\bfor\s+(?:a\s+)?(?:(?:fixed|initial)\s+)?(?:term|period)\b"
    r"|\bfor\s+(?:\w+\s+)?(?:\(\d{1,3}\)|\d{1,3})\s*(?:months?|years?)\b"
    r"|\b(?:renew\w*|expir\w*|lapse[sd]?|lapsing|duration)\b"
    r"|\bremains?\s+in\s+(?:force|effect)\b|\bcontinues?\s+(?:in\s+(?:force|effect)|until|to|for)\b"
    r"|\bvalid\s+(?:for|until|through|to)\b|\buntil\b(?=[^.;\n]{0,40}\d)|\b(?:ends?|ending|terminates?)\s+(?:on|at|by)\b"
    r"|有效期|期限|到期|届满|续约|续期|自动续|终止日期|终止之日", re.IGNORECASE)


def _end_problem(en: str, zh: str) -> Problem:
    return Problem("END_NOT_CERTAIN", en, zh)


def _dated_term_ok(record: ContractRecord, t: ContractTerm, pattern: re.Pattern[str]) -> bool:
    """The term quotes the document, its date is the one its value fragment states, and the reader's own pattern, run again
    over the quote, finds that date. A date the reader derived rather than found written never passes."""
    if t.date is None or (t.text or "").startswith("derived: ") or not _quoted(record, t):
        return False
    if parse_date(t.value_text).value != t.date:
        return False
    return any(parse_date(g).value == t.date for m in pattern.finditer(t.span.text)
               for g in (m.group("d"), m.group("d2"), m.group("dz")) if g)


def _months_ok(record: ContractRecord, t: ContractTerm) -> bool:
    if t.months is None or not _quoted(record, t) or parse_months(t.value_text).value != t.months:
        return False
    return any(parse_months(g).value == t.months for m in DURATION.finditer(t.span.text)
               for g in (m.group("p"), m.group("p2"), m.group("pz")) if g)


def _add_months(iso: str, months: int) -> date:
    d = date.fromisoformat(iso)
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, min(d.day, calendar.monthrange(d.year + y, m + 1)[1]))


def _end_of(record: ContractRecord, state: FinancialState, *, today: int,
            horizon_days: int) -> tuple[int | None, list[Problem], bool]:
    """(the contract's last day as a day number or None, the problems it raises, whether the reading or text suggests an end)."""
    assert record.contract is not None
    c = record.contract
    ends = [t for t in c.terms if t.field == F.END_DATE]
    durations = [t for t in c.terms if t.field == F.DURATION]
    starts = [t for t in c.terms if t.field == F.START_DATE]
    problems: list[Problem] = []
    suggested = bool(ends or durations)
    if any(a.field.removeprefix("note:") in (F.END_DATE.value, F.DURATION.value) for a in c.abstentions):
        problems.append(_end_problem("Part of the contract about its end or term could not be read exactly.",
                                     "合同中关于到期或期限的部分无法准确读取。"))
        suggested = True
    end_iso: str | None = None
    if len(ends) > 1:
        problems.append(_end_problem("The contract states more than one end date.", "合同写明了不止一个到期日。"))
    elif ends:
        if _dated_term_ok(record, ends[0], END):
            end_iso = ends[0].date
        else:
            problems.append(_end_problem("The end date the reading gives is not the one its quoted words state.",
                                         "读取到的到期日与所引用原文中的日期不一致。"))
    # a term in months counted from the start date is an end of its own, and a check on the stated one
    counted: date | None = None
    if len(durations) > 1:
        problems.append(_end_problem("The contract states more than one term.", "合同写明了不止一个期限。"))
    elif len(durations) == 1 and len(starts) == 1 and _months_ok(record, durations[0]) and _dated_term_ok(record, starts[0], START):
        counted = _add_months(starts[0].date, durations[0].months) - timedelta(days=1)  # type: ignore[arg-type]
    if counted is not None and end_iso is not None:
        if date.fromisoformat(end_iso) not in (counted, counted + timedelta(days=1)):
            problems.append(_end_problem("The contract's term and its end date do not agree.", "合同的期限与到期日不一致。"))
    elif counted is not None and not problems:
        end_iso = counted.isoformat()
    # wording that points to an end and that no checked end or term covers
    covered = [(t.span.start, t.span.end) for t in (*ends, *durations) if _quoted(record, t)]
    if any(not any(a <= m.start() < b for a, b in covered) for m in _END_WORDING.finditer(record.document.text)):
        suggested = True
        if not problems:
            problems.append(_end_problem(
                "The contract mentions a term, renewal or expiry, but the reading does not give one end date that can be "
                "checked against its words, so FLOW will not guess when invoices stop.",
                "合同提到了期限、续期或到期，但读取结果没有给出一个可与原文核对的到期日，FLOW 不会猜测发票何时停止。"))
    if problems:
        return None, problems, suggested
    end_day = day_of(end_iso, state.as_of) if end_iso is not None else None
    if end_day is not None and end_day < today:
        problems.append(Problem("CONTRACT_ENDED", "The contract has already ended.", "该合同已经到期。"))
    elif end_day is not None and end_day <= today + horizon_days:
        problems.append(Problem("ENDS_IN_FORECAST",
                                f"The contract ends inside your {horizon_days}-day forecast, and the books cannot yet stop "
                                f"repeating invoices at a contract's end.",
                                f"合同在您 {horizon_days} 天的预测期内到期，而账簿目前还不能在合同到期时停止循环发票。"))
    return end_day, problems, suggested


# ---------------------------------------------------------------- the derivation


def _recurring_of(state: FinancialState, counterparty_id: str) -> list[RecurringInvoice]:
    return [r for r in state.recurring_invoices if r.counterparty_id == counterparty_id]


def _collides(state: FinancialState, ri: RecurringInvoice) -> bool:
    """A receivable already holds an id the new schedule would generate (`RI:<buyer>:<day>`)."""
    prefix = f"RI:{ri.counterparty_id}:"
    for r in state.receivables:
        if r.id.startswith(prefix):
            try:
                d = int(r.id.rsplit(":", 1)[1])
            except ValueError:
                continue
            if d >= ri.next_issue_day and (d - ri.next_issue_day) % ri.every_days == 0:
                return True
    return False


def derive(record: ContractRecord, state: FinancialState, *, today: int, horizon_days: int) -> TermsSetUp:
    """What `record` sets up on the books `state` of day `today`, and whether it can (`status`)."""
    base = {"document_id": record.id, "doc_hash": record.doc_hash, "counterparty_id": record.counterparty_id}
    existing_all = _recurring_of(state, record.counterparty_id)
    existing = existing_all[0] if len(existing_all) == 1 else None

    def blocked(*problems: Problem, **more: object) -> TermsSetUp:
        return TermsSetUp(status="BLOCKED", recurring=None, existing=existing, problems=tuple(problems), **base, **more)  # type: ignore[arg-type]

    if record.kind != DocumentKind.BUYER_CONTRACT or record.contract is None:
        return blocked(Problem("NOT_A_CUSTOMER_CONTRACT", "Only a customer's supply contract sets up invoices in the books.",
                               "只有客户的供货合同才能在账簿中设置发票。"))
    if record.status != DocumentStatus.CONFIRMED:
        return blocked(Problem("NOT_CONFIRMED", "Confirm the agent's reading of the contract first.",
                               "请先确认助手对合同的读取结果。"))
    if record.superseded_by is not None:
        return blocked(Problem("SUPERSEDED", "A later contract with this customer replaced this one.",
                               "该客户后来的合同已取代此合同。"))
    if record.blocked or any(f.kind.split(":")[0] in PARTY_FLAG_KINDS for f in record.flags):
        return blocked(Problem("FLAGGED", "The document carries a flag that stops it setting anything up.",
                               "该文件带有标记，不能据此设置任何内容。"))
    party = next((c for c in state.counterparties if c.id == record.counterparty_id), None)
    if party is None or party.role != "BUYER" or not party.known:
        return blocked(Problem("NOT_A_KNOWN_CUSTOMER", "The contract's customer is not a known customer in your books.",
                               "合同的客户不是您账簿中的已知客户。"))
    c = record.contract
    problems: list[Problem] = []
    if c.status != CompileStatus.COMPILED:
        problems.append(Problem("READING_INCOMPLETE", "The reading of this contract is incomplete or conflicting.",
                                "对该合同的读取不完整或相互矛盾。"))
    if (p := _party_problem(record, party)) is not None:
        problems.append(p)
    sources: list[Source] = []
    terms: dict[ContractField, ContractTerm] = {}
    for f in SET_UP_FIELDS:
        found = [t for t in c.terms if t.field == f]
        if len(found) != 1:
            problems.append(_missing(f, len(found)))
            continue
        t = found[0]
        if (p := _figure_problem(record, t)) is not None:
            problems.append(p)
            continue
        terms[f] = t
        sources.append(Source(field=f, clause=t.clause, quote=t.span.text, value_text=t.value_text or "",
                              start=t.span.start, end=t.span.end))
    problems += _abstention_problems(record)
    early = next(iter(t for t in c.terms if t.field == F.EARLY_PAYMENT), None)
    end_day, end_problems, _ = _end_of(record, state, today=today, horizon_days=horizon_days)
    problems += end_problems
    if len(existing_all) > 1:
        problems.append(Problem("SEVERAL_REPEATING", "Your books hold more than one repeating invoice for this customer.",
                                "您的账簿中该客户有不止一项循环发票。"))
    if problems:
        return blocked(*problems, sources=tuple(sources), end_day=end_day, early_payment=early)
    ri = buyer_terms(c, record.counterparty_id, state.as_of).recurring(today)
    if ri is None:  # every figure was checked above; this is the derivation's own refusal
        return blocked(Problem("NO_SCHEDULE", "No repeating invoice follows from the contract on today's books.",
                               "根据今天的账簿，无法从合同得出循环发票。"), sources=tuple(sources), end_day=end_day,
                       early_payment=early)
    h = terms_hash(record.id, record.doc_hash, ri, tuple(sources))
    more: dict[str, object] = {"sources": tuple(sources), "end_day": end_day, "early_payment": early, "terms_hash": h}
    notes: list[Problem] = []
    if end_day is None:  # no problem was raised, so neither the reading nor the text points to an end
        notes.append(Problem("NO_END_DATE", "The contract states no end date: the books will expect these invoices until "
                             "you undo the set-up.", "合同未写明到期日：在您撤销设置之前，账簿会一直预计这些发票。"))
    else:
        notes.append(Problem("ENDS_LATER", "The books will keep expecting these invoices after the contract ends, until you "
                             "undo the set-up.", "合同到期后，在您撤销设置之前，账簿仍会预计这些发票。"))
    if existing is not None:
        same = (existing.face_fen, existing.every_days, existing.next_issue_day, existing.terms_days) == (
            ri.face_fen, ri.every_days, ri.next_issue_day, ri.terms_days)
        return TermsSetUp(status="ALREADY" if same else "CONFLICT", recurring=ri, existing=existing, **base, **more)  # type: ignore[arg-type]
    if _collides(state, ri):
        return blocked(Problem("ALREADY_ISSUED", "An invoice on this schedule is already in your books.",
                               "该计划中的一张发票已在您的账簿中。"), **more)
    return TermsSetUp(status="READY", recurring=ri, existing=None, notes=tuple(notes), **base, **more)  # type: ignore[arg-type]


__all__ = ["PARTY_FLAG_KINDS", "SET_UP_FIELDS", "Problem", "Source", "TermsSetUp", "derive", "terms_hash"]
