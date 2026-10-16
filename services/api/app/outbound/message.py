"""One verified counter as a message to the buyer (map: negotiation communication, phase 1).

The engine's counter text ("... paid on or before day 2", "this invoice") is the verifier's record of the terms, not a message: it names a
simulated day and no invoice. Here each obligation of the counter becomes one clause in the buyer's words, with the calendar date of every day it
names (day 0 is the books' `as_of`) and the invoice it is about named by its amount, issue date and due date. An early payment says what paying
by the day settles (the net payment for the face it covers) and that the rest of the invoice stays due on its existing day. Then every term the
buyer asked for that the counter does not offer is answered in its own clause (the terms stay at the current days, no rebate, no discount), so
nothing they asked for is left to "everything else stays as it is". The offer is open until `valid_until_day`, which the message states.

Supported terms (anything else is `NoWording`, so the owner writes to the buyer themself):
- IMMEDIATE_DISCOUNT on one named invoice, with its rate, the face it covers and the day it must be paid by;
- TERMS_EXTENSION on future invoices (all of them, the next N, or those issued until a day), firm;
- PRICE_ADJUSTMENT on future invoices, with its rate;
- CONTINGENT_REBATE on next quarter's purchases, with its rate and the purchases it covers.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.domain.models import (
    BaseKind,
    Contingency,
    CounterProposal,
    DurationKind,
    FinancialState,
    Obligation,
    ObligationType,
)
from app.domain.money import bp, fmt_pct, fmt_yuan, post

Lang = Literal["en", "zh"]

TEMPLATE_VERSION = "buyer-message-v2"  # v2: every ask answered, the net payment and the rest of the invoice stated
OFFER_DAYS = 7  # how long a copied offer stays open: the window `POST /negotiate` gives a send

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


class NoWording(ValueError):
    """The counter holds a term this module has no buyer wording for. `code` says which, for the API to word."""

    def __init__(self, code: str, obligation_id: str | None = None) -> None:
        super().__init__(f"{code}: {obligation_id or ''}".strip())
        self.code = code
        self.obligation_id = obligation_id


@dataclass(frozen=True, slots=True)
class BuyerMessage:
    lang: Lang
    text: str
    clauses: tuple[str, ...]
    valid_until_day: int
    template_version: str
    terms_hash: str
    message_hash: str


def _t(lang: Lang, en: str, zh: str) -> str:
    return zh if lang == "zh" else en


def calendar_date(as_of: str, day: int, lang: Lang) -> str:
    """The calendar date of a books day (day 0 is `as_of`): "3 October 2026", "2026年10月3日"."""
    d = date.fromisoformat(as_of) + timedelta(days=day)
    return _t(lang, f"{d.day} {_MONTHS[d.month - 1]} {d.year}", f"{d.year}年{d.month}月{d.day}日")


def _money(fen: int) -> str:
    """Whole yuan without decimals ("¥211,900"), else two decimals: the counter text's own form."""
    s = fmt_yuan(fen)
    return s[:-3] if fen % 100 == 0 else s


def _rate(rate_bp: int) -> str:
    return fmt_pct(bp(abs(rate_bp)))


def message_hash(text: str, *, lang: Lang, terms_hash: str, template_version: str = TEMPLATE_VERSION) -> str:
    """What binds a copied message to the terms it states: the template, the language, the terms' hash and the exact words."""
    return hashlib.sha256(f"{template_version}\n{lang}\n{terms_hash}\n{text}".encode()).hexdigest()


def valid_until(counter: CounterProposal, today: int, mandate_expires_day: int) -> int:
    """The last day the offer stays open: `OFFER_DAYS` from today, never past the mandate's expiry nor past the day an early payment it
    offers must be made by (the buyer accepts an early-payment offer by paying)."""
    days = [today + OFFER_DAYS, mandate_expires_day]
    days += [o.effective_day for o in counter.obligations
             if o.type == ObligationType.IMMEDIATE_DISCOUNT and o.effective_day is not None]
    return min(days)


def _scope(o: Obligation, as_of: str, lang: Lang) -> str:
    """Which invoices a recurring term covers, in the buyer's words."""
    d = o.duration
    if d.kind == DurationKind.RECURRING_PERPETUAL:
        return _t(lang, "future invoices", "今后发票")
    if d.kind == DurationKind.RECURRING_BOUNDED and d.invoices:
        return (_t(lang, "the next invoice", "下一张发票") if d.invoices == 1
                else _t(lang, f"the next {d.invoices} invoices", f"接下来的 {d.invoices} 张发票"))
    if d.kind == DurationKind.RECURRING_BOUNDED and d.end_day is not None:
        until = calendar_date(as_of, d.end_day, lang)
        return _t(lang, f"invoices issued until {until}", f"{until}前开具的发票")
    if d.kind == DurationKind.ONE_OFF:
        return _t(lang, "the next invoice", "下一张发票")
    raise NoWording("SCOPE_UNSUPPORTED", o.id)


def early_settlement(o: Obligation) -> tuple[int, int]:
    """(the face an early payment covers, the net the buyer pays to settle it): the face less the discount at the obligation's rate,
    posted once, as the commitment's promise books it."""
    cap, rate = o.base.amount_fen or 0, o.rate_bp or 0
    return cap, cap - post(bp(rate) * cap)


def remainder_fen(o: Obligation, state: FinancialState) -> int:
    """What stays owed on the invoice beyond the face the early payment covers (0 when it covers all of it)."""
    rcv = next((r for r in state.receivables if r.id == o.base.receivable_id), None)
    return max(0, rcv.outstanding_fen - (o.base.amount_fen or 0)) if rcv is not None else 0


def _discount(o: Obligation, state: FinancialState, lang: Lang) -> str:
    rcv = next((r for r in state.receivables if r.id == o.base.receivable_id), None)
    if (o.base.kind != BaseKind.INVOICE or rcv is None or o.rate_bp is None or o.base.amount_fen is None
            or o.effective_day is None or o.rate_bp <= 0):
        raise NoWording("DISCOUNT_UNSUPPORTED", o.id)
    face, issued = _money(rcv.face_fen), calendar_date(state.as_of, rcv.issue_day, lang)
    due = calendar_date(state.as_of, rcv.issue_day + rcv.terms_days, lang)
    by, rate = calendar_date(state.as_of, o.effective_day, lang), _rate(o.rate_bp)
    cap_fen, net_fen = early_settlement(o)
    cap, net, rest = _money(cap_fen), _money(net_fen), remainder_fen(o, state)
    en = (f"Early payment of the {face} invoice issued on {issued} and due on {due}: we will accept early settlement of up to {cap} of it "
          f"at a {rate} discount if paid on or before {by}. Paying {net} by then settles {cap} of the invoice.")
    zh = (f"提前付款：对于{issued}开具、{due}到期的 {face} 发票，如贵方于{by}或之前付款，我方接受其中最多 {cap} 按 {rate} 的折扣提前结清；"
          f"届时支付 {net} 即可结清发票中的 {cap}。")
    if rest:
        en += f" Any amount not settled early, including the other {_money(rest)}, stays due on {due} under the existing terms."
        zh += f"未提前结清的部分（包括其余 {_money(rest)}）仍按原条款于{due}到期。"
    return _t(lang, en, zh)


def _terms(o: Obligation, state: FinancialState, lang: Lang) -> str:
    if o.base.kind != BaseKind.FUTURE_INVOICES or o.contingency != Contingency.FIRM:
        raise NoWording("TERMS_UNSUPPORTED", o.id)
    scope = _scope(o, state.as_of, lang)
    target, delta = o.target_terms_days, o.days_delta
    if target is not None and delta is not None and delta != 0:
        return _t(lang, f"Payment terms on {scope} move from {target - delta} to {target} days.",
                  f"{scope}的付款期限由 {target - delta} 天调整为 {target} 天。")
    if target is not None:
        return _t(lang, f"Payment terms on {scope} are {target} days.", f"{scope}的付款期限为 {target} 天。")
    if delta:
        return (_t(lang, f"Payment terms on {scope} are extended by {delta} days.", f"{scope}的付款期限延长 {delta} 天。") if delta > 0
                else _t(lang, f"Payment terms on {scope} are shortened by {-delta} days.", f"{scope}的付款期限缩短 {-delta} 天。"))
    raise NoWording("TERMS_UNSUPPORTED", o.id)


def _price(o: Obligation, state: FinancialState, lang: Lang) -> str:
    if o.base.kind != BaseKind.FUTURE_INVOICES or o.rate_bp is None or o.rate_bp == 0:
        raise NoWording("PRICE_UNSUPPORTED", o.id)
    scope, rate = _scope(o, state.as_of, lang), _rate(o.rate_bp)
    if o.rate_bp > 0:  # a positive rate is a price the buyer pays more (models.ObligationType.PRICE_ADJUSTMENT)
        return _t(lang, f"Prices on {scope} rise by {rate}.", f"{scope}的价格上调 {rate}。")
    return _t(lang, f"Prices on {scope} fall by {rate}.", f"{scope}的价格下调 {rate}。")


def _rebate(o: Obligation, state: FinancialState, lang: Lang) -> str:
    if o.base.kind != BaseKind.PERIOD_PURCHASES or o.rate_bp is None or o.rate_bp <= 0 or o.base.amount_fen is None:
        raise NoWording("REBATE_UNSUPPORTED", o.id)
    rate, cap = _rate(o.rate_bp), _money(o.base.amount_fen)
    return _t(lang, f"A {rate} rebate on next quarter's purchases of up to {cap}.",
              f"下一季度最高 {cap} 的采购额可享 {rate} 返利。")


_CLAUSES = {
    ObligationType.IMMEDIATE_DISCOUNT: _discount,
    ObligationType.TERMS_EXTENSION: _terms,
    ObligationType.PRICE_ADJUSTMENT: _price,
    ObligationType.CONTINGENT_REBATE: _rebate,
}


def _not_offered(asked: Sequence[Obligation], counter: CounterProposal, current_terms_days: int | None, lang: Lang) -> list[str]:
    """One clause for each kind of term the buyer asked for that the counter does not offer, in a fixed order, each said once."""
    offered = {o.type for o in counter.obligations}
    kinds = [k for k in _NOT_OFFERED_ORDER if k in {o.type for o in asked} and k not in offered]
    out = []
    for k in kinds:
        if k == ObligationType.TERMS_EXTENSION:
            out.append(_t(lang, f"Payment terms on future invoices stay at {current_terms_days} days.",
                          f"今后发票的付款期限维持 {current_terms_days} 天。") if current_terms_days
                       else _t(lang, "We are not able to change the payment terms on future invoices.", "我方无法更改今后发票的付款期限。"))
        elif k == ObligationType.IMMEDIATE_DISCOUNT:
            out.append(_t(lang, "We are not able to offer the early-payment discount you asked for.", "我方无法提供贵方所要求的提前付款折扣。"))
        elif k in (ObligationType.CONTINGENT_REBATE, ObligationType.CLAIMED_PRIOR_CONCESSION):  # said once for both (deduplicated below)
            out.append(_t(lang, "We are not able to offer the rebate you asked for.", "我方无法提供贵方所要求的返利。"))
        elif k == ObligationType.PRICE_ADJUSTMENT:
            out.append(_t(lang, "Prices on future invoices stay as they are.", "今后发票的价格保持不变。"))
        else:
            out.append(_t(lang, "We are not able to agree to the other changes you asked for.", "我方无法同意贵方提出的其他变更。"))
    return list(dict.fromkeys(out))


_NOT_OFFERED_ORDER = (ObligationType.IMMEDIATE_DISCOUNT, ObligationType.TERMS_EXTENSION, ObligationType.CONTINGENT_REBATE,
                      ObligationType.CLAIMED_PRIOR_CONCESSION, ObligationType.PRICE_ADJUSTMENT, ObligationType.VOLUME_COMMITMENT,
                      ObligationType.OPERATIONAL_CONCESSION)


def render(counter: CounterProposal, state: FinancialState, *, buyer_name: str, terms_hash: str, valid_until_day: int,
           lang: Lang, asked: Sequence[Obligation] = (), current_terms_days: int | None = None) -> BuyerMessage:
    """The message for `counter`: one clause per obligation in the counter's order, then one for each kind of term the buyer asked for
    (`asked`, the verdict's bound obligations) that the counter does not offer. Raises `NoWording` for a term it cannot say, and for a
    counter with no term at all (there would be nothing to agree to)."""
    if not counter.obligations:
        raise NoWording("NO_TERMS")
    clauses = []
    for o in counter.obligations:
        say = _CLAUSES.get(o.type)
        if say is None:
            raise NoWording("TERM_UNSUPPORTED", o.id)
        clauses.append(say(o, state, lang))
    clauses += _not_offered(asked, counter, current_terms_days, lang)
    body = (clauses[0] if len(clauses) == 1 else "\n".join(f"{n}. {c}" for n, c in enumerate(clauses, start=1)))
    until = calendar_date(state.as_of, valid_until_day, lang)
    text = _t(lang,
              f"Dear {buyer_name},\n\nThank you for your request. We can offer the following:\n\n{body}\n\n"
              f"No other terms change. This offer is open until {until}. Please reply to confirm.\n\nKind regards",
              f"{buyer_name}：\n\n感谢贵方的来函。我方可提供以下条件：\n\n{body}\n\n"
              f"其他条款均无变更。本报价有效期至{until}。请回复确认。\n\n此致\n敬礼")
    return BuyerMessage(lang=lang, text=text, clauses=tuple(clauses), valid_until_day=valid_until_day, template_version=TEMPLATE_VERSION,
                        terms_hash=terms_hash, message_hash=message_hash(text, lang=lang, terms_hash=terms_hash))
