"""A capex contract's payment schedule, derived by code (ADR-0013 decision 2).

Input: the reading of a capex contract (`CompiledContract`: every value already parsed by code from a quoted span) and the
owner's timeline (the days the contract cannot fix: signing, delivery, acceptance, invoice). Output: a dated list of
payments that sums to the contract price exactly, or the reasons it cannot be derived. Nothing is guessed (INVARIANT 10):

- the price must be one lump sum;
- each milestone's trigger is classified by fixed patterns into one event (signing, delivery, acceptance, invoice), with
  the offset its own words state ("within forty-five (45) days after delivery" = delivery + 45); a trigger naming no
  event, or two different events, or a time before an event, makes the schedule not derivable;
- the milestone shares and the retention must reconcile: milestones + retention = 100% (the retention is a separate
  final payment), or milestones alone = 100% (the retention is then not deferred: the conservative reading for cash,
  since the contract does not say which payment it is held from); anything else is not derivable;
- with no milestones, the price falls due on the payment terms' basis day plus their days, the retention held back;
- payment terms stated beside milestones are never added on top of a milestone (D5: earlier is the conservative reading
  of an outflow), and a day count in business days is counted in calendar days for the same reason;
- a month is 30 days (the engine's month), so 12 months is 360 days: again the earlier reading.

Amounts are integer fen, each share rounded once through `app.domain.money.post`; the last payment in day order carries
the remainder, so the payments sum to the price exactly. The schedule hash binds the owner's commitment (phase 4) to the
schedule they were shown.
"""

from __future__ import annotations

import hashlib
import re
from fractions import Fraction
from typing import Literal

from pydantic import Field

from app.compiler.contract_parsing import COUNT_PAT, parse_days, parse_months
from app.contracts.derive import day_of
from app.domain.models import (
    CompiledContract,
    CompileStatus,
    Contract,
    ContractField,
    ContractTerm,
    PaymentBasis,
    PriceUnit,
)
from app.domain.money import BP_DENOM, Ratio, fmt_pct, fmt_yuan, post
from app.financial.trajectory import MONTH_DAYS
from app.funding.rates import early_pay_rate
from app.persistence.canonical import canonical_json

F = ContractField
Event = Literal["SIGNING", "DELIVERY", "ACCEPTANCE", "INVOICE"]
I = re.IGNORECASE

# ---------------------------------------------------------------- models


class Timeline(Contract):
    """The owner's expected days, on the books' own day numbers (day 0 = `FinancialState.as_of`). A contract fixes a
    price and when it is owed relative to events; when the events happen is the owner's plan, and is labelled so."""

    signing_day: int | None = Field(default=None, ge=0)  # None: the contract's stated signing date, else today
    delivery_day: int | None = Field(default=None, ge=0)
    acceptance_day: int | None = Field(default=None, ge=0)
    invoice_day: int | None = Field(default=None, ge=0)  # None: the delivery day (the earliest an invoice is likely)
    retention_release_day: int | None = Field(default=None, ge=0)  # only used when the contract states no period


class ScheduledPayment(Contract):
    n: int  # 1-based, in day order
    day: int
    amount_fen: int
    share_bp: int  # of the contract price
    kind: Literal["MILESTONE", "PAYMENT_TERMS", "RETENTION"]
    event: Event | None  # what the day counts from
    offset_days: int  # the days after that event the contract states
    label: str  # "30% on signing of this Contract"
    clause: str | None
    quote: str
    day_formula: str  # "signing day 7 + 0 days"
    owner_dated: bool  # the event's day is the owner's timeline, not the contract's text


class EarlyPayOption(Contract):
    """The vendor's discount for paying one payment early, priced as the annual return of paying it early."""

    payment_n: int
    rate_bp: int
    window_days: int
    pay_by_day: int  # the event day + the window
    due_day: int  # the payment's own day
    days_earlier: int  # due_day - pay_by_day (<= 0: the discount costs no time at all)
    discount_fen: int
    pay_early_fen: int  # amount - discount
    implied_annual_rate: Ratio | None  # d / (1 - d) x 365 / days_earlier (early_pay_rate); None when days_earlier <= 0
    clause: str | None
    quote: str
    formula: str


class PaymentSchedule(Contract):
    price_fen: int
    payments: list[ScheduledPayment]
    early_pay: EarlyPayOption | None = None
    early_pay_note: str | None = None  # why the contract's early-payment discount could not be attached, if it states one
    assumptions: list[str] = Field(default_factory=list)
    schedule_hash: str


class ScheduleResult(Contract):
    derivable: bool
    schedule: PaymentSchedule | None = None
    reasons: list[str] = Field(default_factory=list)  # why it is not derivable, one sentence each
    reasons_zh: list[str] = Field(default_factory=list)  # the same reasons in Chinese where the code has them (CAPEX-1)
    needs: list[str] = Field(default_factory=list)  # timeline fields the owner must give ("delivery_day")


# ---------------------------------------------------------------- trigger classification

_EVENTS: tuple[tuple[Event, re.Pattern[str]], ...] = (
    ("SIGNING", re.compile(r"\b(?:sign(?:ing|ature|ed)?|execution|executed|conclusion|order(?:ing)?|advance|down[\s-]?payment"
                           r"|effective\s+date|date\s+of\s+this\s+(?:contract|agreement))\b|签订|签署|签约|下单|预付", I)),
    ("DELIVERY", re.compile(r"\b(?:deliver(?:y|ed|ies)?|shipment|shipped|shipping|dispatch(?:ed)?|arrival|arrives?)\b"
                            r"|交货|到货|发货", I)),
    ("ACCEPTANCE", re.compile(r"\b(?:accept(?:ance|ed)?|commission(?:ing|ed)?|install(?:ation|ed)?|hand-?over|go-live"
                              r"|final\s+test)\b|验收|安装|调试", I)),
    ("INVOICE", re.compile(r"\binvoice[ds]?\b|发票|开票", I)),
)
_BEFORE = re.compile(r"\b(?:before|prior\s+to|in\s+advance\s+of)\b|之前|前", I)
_OFFSET_DAYS = re.compile(rf"(?P<n>{COUNT_PAT})\s*(?:calendar\s+|business\s+|working\s+|banking\s+)?days?\b"
                          r"|\d{1,3}\s*(?:个)?(?:工作日|天|日)", I)
_OFFSET_MONTHS = re.compile(rf"(?P<n>{COUNT_PAT})\s*(?:months?|years?)\b|\d{{1,3}}\s*(?:个月|年)", I)

_EVENT_WORDS = {"SIGNING": "signing", "DELIVERY": "delivery", "ACCEPTANCE": "acceptance", "INVOICE": "the invoice"}
_BASIS_EVENT: dict[PaymentBasis, Event] = {PaymentBasis.DELIVERY: "DELIVERY", PaymentBasis.ACCEPTANCE: "ACCEPTANCE",
                                            PaymentBasis.INVOICE: "INVOICE", PaymentBasis.MONTH_END: "INVOICE"}


def events_in(text: str) -> list[Event]:
    """The distinct events a trigger names, in the order of `_EVENTS`."""
    return [e for e, pat in _EVENTS if pat.search(text)]


class _Unclear(Exception):
    """A material value the code cannot establish: the schedule is not derivable, for this reason."""


def offset_days(text: str) -> int:
    """The days after its event a trigger states: "within forty-five (45) days after delivery" = 45; "on delivery" = 0;
    "within 2 months of acceptance" = 60 (a 30-day month). Raises _Unclear on a time before the event or two offsets."""
    if _BEFORE.search(text):
        raise _Unclear(f'"{text}" is a time before its event; a payment before the event cannot be dated from it')
    days = [m for m in _OFFSET_DAYS.finditer(text)]
    months = [m for m in _OFFSET_MONTHS.finditer(text)]
    if len(days) + len(months) > 1:
        raise _Unclear(f'"{text}" states more than one period')
    if days:
        p = parse_days(days[0].group(0))
        if not p.ok:
            raise _Unclear(f'the number of days in "{text}" is not an exact value')
        return int(p.value)  # type: ignore[call-overload]  # business days counted as calendar days (D5)
    if months:
        p = parse_months(months[0].group(0))
        if not p.ok:
            raise _Unclear(f'the number of months in "{text}" is not an exact value')
        return int(p.value) * MONTH_DAYS  # type: ignore[call-overload]
    return 0


def classify(text: str) -> tuple[Event, int]:
    """(event, offset days) of a trigger, or _Unclear."""
    found = events_in(text)
    if not found:
        raise _Unclear(f'"{text}" names no event the code can date (signing, delivery, acceptance or the invoice)')
    if len(found) > 1:
        raise _Unclear(f'"{text}" names {" and ".join(_EVENT_WORDS[e] for e in found)}; which one the payment waits '
                       f"for is not clear")
    return found[0], offset_days(text)


# ---------------------------------------------------------------- derivation


def _one(terms: list[ContractTerm], field: ContractField) -> list[ContractTerm]:
    return [t for t in terms if t.field == field]


class _Days:
    """The event days, from the owner's timeline and the contract's stated signing date, recording what is missing."""

    def __init__(self, contract: CompiledContract, timeline: Timeline, anchor_iso: str, today: int) -> None:
        signed = next((t for t in contract.terms if t.field == F.SIGNED_DATE and t.date), None)
        self.signing_owner = timeline.signing_day is not None
        if timeline.signing_day is not None:
            self.signing = timeline.signing_day
            self.signing_how = f"signing day {timeline.signing_day} (your timeline)"
        elif signed is not None and signed.date is not None:
            self.signing = day_of(signed.date, anchor_iso)
            self.signing_how = f"signing day {self.signing} (the contract's date, {signed.date})"
        else:
            self.signing = today
            self.signing_how = f"signing day {today} (today: the contract states no date)"
        self.t = timeline
        self.needs: list[str] = []

    def day(self, event: Event) -> tuple[int | None, str, bool]:
        """(day, how it was found, owner-dated) of an event; None (and the need recorded) when the owner must say."""
        if event == "SIGNING":
            return self.signing, self.signing_how, self.signing_owner
        if event == "DELIVERY":
            if self.t.delivery_day is None:
                self._need("delivery_day")
                return None, "", True
            return self.t.delivery_day, f"delivery day {self.t.delivery_day} (your timeline)", True
        if event == "ACCEPTANCE":
            if self.t.acceptance_day is None:
                self._need("acceptance_day")
                return None, "", True
            return self.t.acceptance_day, f"acceptance day {self.t.acceptance_day} (your timeline)", True
        if self.t.invoice_day is not None:
            return self.t.invoice_day, f"invoice day {self.t.invoice_day} (your timeline)", True
        if self.t.delivery_day is None:
            self._need("delivery_day")
            return None, "", True
        return (self.t.delivery_day, f"invoice day {self.t.delivery_day} (the delivery day: no invoice day given)", True)

    def _need(self, name: str) -> None:
        if name not in self.needs:
            self.needs.append(name)


def _timeline_order(t: Timeline, days: _Days) -> list[str]:
    out = []
    if t.delivery_day is not None and t.delivery_day < days.signing:
        out.append(f"delivery (day {t.delivery_day}) is before signing (day {days.signing})")
    if t.acceptance_day is not None and t.delivery_day is not None and t.acceptance_day < t.delivery_day:
        out.append(f"acceptance (day {t.acceptance_day}) is before delivery (day {t.delivery_day})")
    return out


def _unsafe_rates(terms: list[ContractTerm]) -> list[tuple[str, str]]:
    """CAPEX-1: (English, Chinese) reasons for every rate the schedule is built from that cannot be a share of a payment.
    A milestone share must be more than 0% and at most 100% of the price; a retention must be at most 100% and not
    negative; an early-payment discount must be at least 0% and below 100% (a discount of the whole payment is no
    discount). Anything else is read as a mistake in the reading, and no schedule is drawn from it: a rate above 100%
    would otherwise turn a payment into money coming in."""
    out: list[tuple[str, str]] = []

    def pct(bp: int) -> str:
        return fmt_pct(Fraction(bp, BP_DENOM))

    for t in terms:
        if t.rate_bp is None:
            continue
        where = f"clause {t.clause}" if t.clause else "a clause"
        where_zh = f"第 {t.clause} 条" if t.clause else "某一条款"
        rate = pct(t.rate_bp)
        end = "so no payment schedule is drawn from this contract. Check the reading of that clause."
        end_zh = "因此不会据此生成付款计划。请核对该条款的解读。"
        if t.field == F.MILESTONE and not 0 < t.rate_bp <= BP_DENOM:
            en = f"The payment share of {rate} ({where}) is not between 0% and 100% of the price, {end}"
            zh = f"{where_zh}的付款比例 {rate} 不在合同价款的 0% 至 100% 之间，{end_zh}"
        elif t.field == F.RETENTION and not 0 <= t.rate_bp <= BP_DENOM:
            en = f"The retention of {rate} ({where}) is more than 100% of the price, {end}"
            zh = f"{where_zh}的质保金 {rate} 超过合同价款的 100%，{end_zh}"
        elif t.field == F.EARLY_PAYMENT and not 0 <= t.rate_bp < BP_DENOM:
            en = f"The early-payment discount of {rate} ({where}) is not below 100% of the payment, {end}"
            zh = f"{where_zh}的提前付款折扣 {rate} 不低于该笔付款的 100%，{end_zh}"
        else:
            continue
        out.append((en, zh))
    return out


def _amounts(price: int, shares: list[int]) -> list[int]:
    """Each share of the price rounded once; the last (in the given order) carries the remainder."""
    out = [post(Fraction(price * s, BP_DENOM)) for s in shares[:-1]]
    return [*out, price - sum(out)]


def schedule_hash(price_fen: int, payments: list[ScheduledPayment]) -> str:
    """sha256 of what the owner commits to: the price and each payment's day, amount and kind (not its wording)."""
    body = canonical_json({"price_fen": price_fen,
                           "payments": [[p.day, p.amount_fen, p.kind, p.share_bp] for p in payments]})
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def derive_schedule(contract: CompiledContract, timeline: Timeline, *, anchor_iso: str, today: int) -> ScheduleResult:
    """The payment schedule of a capex contract on the owner's timeline, or why it cannot be derived."""

    def no(*reasons: str, needs: list[str] | None = None, zh: list[str] | None = None) -> ScheduleResult:
        return ScheduleResult(derivable=False, reasons=list(reasons), reasons_zh=zh or [], needs=needs or [])

    if contract.status != CompileStatus.COMPILED:
        return no(f"The reading is {contract.status.value.lower().replace('_', ' ')}: a schedule is derived only from a "
                  f"complete reading.")
    terms = contract.terms
    unsafe = _unsafe_rates(terms)
    if unsafe:  # CAPEX-1: before anything is derived from a rate that cannot be a share of a payment
        return no(*[en for en, _ in unsafe], zh=[zh for _, zh in unsafe])
    prices = _one(terms, F.PRICE)
    if len(prices) != 1 or prices[0].amount_fen is None:
        return no("The contract states no single price.")
    if prices[0].unit != PriceUnit.LUMP_SUM:
        return no("The price is not one lump sum (it is per delivery, unit or month), so no purchase schedule follows "
                  "from it.")
    price = prices[0].amount_fen
    days = _Days(contract, timeline, anchor_iso, today)
    order = _timeline_order(timeline, days)
    if order:
        return no(*[f"Your timeline has {o}." for o in order])

    milestones = _one(terms, F.MILESTONE)
    retention = _one(terms, F.RETENTION)
    pay_terms = _one(terms, F.PAYMENT_TERMS)
    if len(retention) > 1:
        return no("The contract states more than one retention.")
    ret = retention[0] if retention else None
    ret_bp = ret.rate_bp or 0 if ret else 0
    assumptions = [
        "A month is counted as 30 days and business days as calendar days: for a payment, the earlier reading.",
    ]
    reasons: list[str] = []
    # (kind, share, event, offset, label, term, fixed day): a fixed day is the owner's own day for the payment
    rows: list[tuple[str, int, Event, int, str, ContractTerm, int | None]] = []

    if milestones:
        shares = sum(m.rate_bp or 0 for m in milestones)
        if any(m.rate_bp is None for m in milestones):
            return no("A milestone states no share of the price.")
        for m in milestones:
            try:
                event, off = classify(m.text or "")
            except _Unclear as e:
                reasons.append(f"Milestone {m.value_text} (clause {m.clause or '?'}): {e}.")
                continue
            label = f"{fmt_pct(Fraction(m.rate_bp or 0, BP_DENOM))} {m.text}"
            rows.append(("MILESTONE", m.rate_bp or 0, event, off, label, m, None))
        if pay_terms:
            assumptions.append("The contract's payment terms are not added on top of a milestone: each milestone falls "
                               "due on the day its own words give.")
        if shares + ret_bp == BP_DENOM and ret is not None:
            separate_retention = True
        elif shares == BP_DENOM:
            separate_retention = False
            if ret is not None:
                assumptions.append(f"The {fmt_pct(Fraction(ret_bp, BP_DENOM))} retention is not deferred: the "
                                   f"milestones already add up to 100% and the contract does not say which payment it "
                                   f"is held from, so every milestone is counted in full on its day.")
        else:
            total = fmt_pct(Fraction(shares + ret_bp, BP_DENOM))
            return no(f"The milestones{' and the retention' if ret else ''} add up to {total} of the price, not 100%.")
    else:
        if len(pay_terms) != 1 or pay_terms[0].days is None:
            return no("The contract states neither milestones nor one set of payment terms.")
        pt = pay_terms[0]
        if pt.basis is None:
            return no("The payment terms do not say what their days count from.")
        separate_retention = ret is not None
        event = _BASIS_EVENT[pt.basis]
        label = f"the price{' less the retention' if ret else ''}, {pt.value_text} after {_EVENT_WORDS[event]}"
        rows.append(("PAYMENT_TERMS", BP_DENOM - ret_bp, event, pt.days or 0, label, pt, None))
        if pt.basis == PaymentBasis.MONTH_END:
            assumptions.append("Payment terms counted from the end of the invoice month: the month ends on the next "
                               "multiple of 30 days.")

    retention_need: list[str] = []
    if separate_retention and ret is not None:
        period = (ret.months * MONTH_DAYS if ret.months is not None else ret.days)
        found = events_in(ret.span.text)
        share_text = fmt_pct(Fraction(ret_bp, BP_DENOM))
        if period is None or len(found) != 1:
            if timeline.retention_release_day is None:
                why = ("states no period" if period is None else
                       "does not say from when its period counts" if not found else "names more than one event")
                reasons.append(f"The {share_text} retention (clause {ret.clause or '?'}) {why}: give the day you "
                               f"expect it to be released.")
                retention_need = ["retention_release_day"]
            else:
                rows.append(("RETENTION", ret_bp, "SIGNING", 0, f"{share_text} retention, released on the day you gave",
                             ret, timeline.retention_release_day))
        else:
            label = f"{share_text} retention, released {period} days after {_EVENT_WORDS[found[0]]}"
            rows.append(("RETENTION", ret_bp, found[0], period, label, ret, None))

    dated: list[tuple[int, str, int, Event | None, int, str, ContractTerm, str, bool]] = []
    for kind, share, event, off, label, term, fixed in rows:
        if fixed is not None:
            dated.append((fixed, kind, share, None, 0, label, term, f"release day {fixed} (your timeline)", True))
            continue
        d, how, owner = days.day(event)
        if d is None:
            continue
        due = d
        if kind == "PAYMENT_TERMS" and isinstance(term.basis, PaymentBasis) and term.basis == PaymentBasis.MONTH_END:
            due = -(-d // MONTH_DAYS) * MONTH_DAYS if d % MONTH_DAYS else d
            how += f", month end day {due}"
        dated.append((due + off, kind, share, event, off, label, term, f"{how} + {off} days", owner))
    if days.needs:
        missing = " and the ".join(n.replace("_", " ") for n in days.needs)
        reasons.append(f"Give the {missing} to date the payments that wait for {'them' if len(days.needs) > 1 else 'it'}.")
    if reasons:
        return no(*reasons, needs=[*days.needs, *retention_need])
    early = [x for x in dated if x[0] < today]
    if early:
        first = min(early, key=lambda x: x[0])
        return no(f"A payment ({first[5]}) falls on day {first[0]}, before today (day {today}): the purchase has already "
                  f"started, so enter the timeline as it stands now.")

    dated.sort(key=lambda x: (x[0], x[1] != "MILESTONE", x[6].span.start))
    amounts = _amounts(price, [x[2] for x in dated])
    payments = [ScheduledPayment(
        n=i + 1, day=x[0], amount_fen=a, share_bp=x[2], kind=x[1], event=x[3], offset_days=x[4], label=x[5],  # type: ignore[arg-type]
        clause=x[6].clause, quote=x[6].span.text, day_formula=x[7], owner_dated=x[8])
        for i, (x, a) in enumerate(zip(dated, amounts, strict=True))]
    assert sum(p.amount_fen for p in payments) == price  # the remainder rule; INVARIANT 9
    if any(p.amount_fen <= 0 for p in payments):  # CAPEX-1: every payment is money going out; none is nil or coming in
        return no("A payment in the schedule would be nil or money coming in to you, so no payment schedule is drawn "
                  "from this contract. Check the reading of its shares and retention.",
                  zh=["计划中有一笔付款为零或是流入您的资金，因此不会据此生成付款计划。请核对合同比例和质保金的解读。"])

    option, note = _early_pay(terms, payments, days)
    if any(p.owner_dated for p in payments):
        assumptions.append("Days marked as yours rest on your timeline (signing, delivery, acceptance, invoice), not on "
                           "the contract's text.")
    return ScheduleResult(derivable=True, schedule=PaymentSchedule(
        price_fen=price, payments=payments, early_pay=option, early_pay_note=note, assumptions=assumptions,
        schedule_hash=schedule_hash(price, payments)))


def _early_pay(terms: list[ContractTerm], payments: list[ScheduledPayment],
               days: _Days) -> tuple[EarlyPayOption | None, str | None]:
    """The contract's early-payment discount attached to the one payment it is about, or why it cannot be."""
    stated = _one(terms, F.EARLY_PAYMENT)
    if not stated:
        return None, None
    if len(stated) > 1:
        return None, "The contract states more than one early-payment discount; none is priced."
    e = stated[0]
    if e.rate_bp is None or e.days is None:
        return None, "The early-payment discount states no window, so it cannot be dated."
    found = events_in(e.span.text)
    if len(found) != 1:
        return None, "The early-payment clause does not name the one event its window counts from."
    event = found[0]
    targets = [p for p in payments if p.kind != "RETENTION" and p.event == event]
    if len(targets) != 1:
        return None, (f"The early-payment clause counts from {_EVENT_WORDS[event]}, and "
                      f"{'no payment' if not targets else 'more than one payment'} waits for it; none is priced.")
    p = targets[0]
    base, _, _ = days.day(event)
    assert base is not None  # the payment above was dated from the same event
    pay_by = base + e.days
    discount = post(Fraction(p.amount_fen * e.rate_bp, BP_DENOM))
    earlier = p.day - pay_by
    # the engine's own early-pay rate (app.funding.rates.early_pay_rate, the sell side's rule): d/(1−d) × 365 / days
    implied = Ratio.of(early_pay_rate(Fraction(e.rate_bp, BP_DENOM), earlier)) if earlier > 0 else None
    formula = (f"d / (1 − d) × 365 / days earlier = {fmt_pct(Fraction(e.rate_bp, BP_DENOM))} / (1 − "
               f"{fmt_pct(Fraction(e.rate_bp, BP_DENOM))}) × 365 / {earlier}; discount {fmt_yuan(discount)} on "
               f"{fmt_yuan(p.amount_fen)}, rounded once"
               if implied is not None else
               f"paying by day {pay_by} is not earlier than the payment's own day {p.day}: the discount costs no time")
    return EarlyPayOption(
        payment_n=p.n, rate_bp=e.rate_bp, window_days=e.days, pay_by_day=pay_by, due_day=p.day, days_earlier=earlier,
        discount_fen=discount, pay_early_fen=p.amount_fen - discount, implied_annual_rate=implied, clause=e.clause,
        quote=e.span.text, formula=formula), None


__all__ = [
    "EarlyPayOption",
    "PaymentSchedule",
    "ScheduleResult",
    "ScheduledPayment",
    "Timeline",
    "classify",
    "derive_schedule",
    "early_schedule",
    "events_in",
    "offset_days",
    "schedule_hash",
]


def early_schedule(schedule: PaymentSchedule) -> PaymentSchedule | None:
    """The schedule with the vendor's early-payment discount taken: the discounted payment moved to the last day of the
    window and reduced by the discount, the others unchanged, renumbered in day order and hashed on its own. None when
    the contract offers no early payment the code could attach."""
    o = schedule.early_pay
    if o is None:
        return None
    label = f"paid early at a {fmt_pct(Fraction(o.rate_bp, BP_DENOM))} discount"
    rows = [p.model_copy(update={"day": o.pay_by_day, "amount_fen": o.pay_early_fen, "label": f"{p.label}, {label}",
                                 "day_formula": f"{p.day_formula}, paid early by day {o.pay_by_day}"})
            if p.n == o.payment_n else p for p in schedule.payments]
    rows.sort(key=lambda p: (p.day, p.kind != "MILESTONE", p.n))
    payments = [p.model_copy(update={"n": i + 1}) for i, p in enumerate(rows)]
    price = schedule.price_fen - o.discount_fen
    assert sum(p.amount_fen for p in payments) == price
    if any(p.amount_fen <= 0 for p in payments):  # CAPEX-1: a discount never turns a payment into money coming in
        return None
    taken = (f"The {fmt_pct(Fraction(o.rate_bp, BP_DENOM))} early-payment discount is taken: "
             f"{fmt_yuan(o.discount_fen)} off, paid by day {o.pay_by_day}.")
    return PaymentSchedule(price_fen=price, payments=payments, early_pay=None,
                           assumptions=[*schedule.assumptions, taken], schedule_hash=schedule_hash(price, payments))
