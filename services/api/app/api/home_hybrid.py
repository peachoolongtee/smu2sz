"""The Home hybrid, server side: the position, the attention queue, the event rail and the cards (wayfinder map #88, Home E).

Additive fields on `GET /home`, built from what the home already holds: the CONSERVATIVE trajectory (and the recommended plan's, when one
is ready), the recommended plan, the approvals, the receivables block, the ledger rows, the decision record and the deals read. Every
sentence goes through `t(lang, en, zh)`; every figure is a display string from the kernel's own values (a trajectory's closing cash, an
event's amount, a plan's cost line, a verdict's cost). The route adds no money: at most one difference of two kernel figures per
statement, and the sum of the engine's own postings of one day (the same `net` the series already carries).

    cash.status_word, status_tone      the pill's word and its tone, from the pill's own rule
    cash.headline_conditional, headline_note, assumptions     the position, with what the forecast leans on
    cash.facts                          today, the lowest point ahead, the next arrival
    cash.events_rail                    at most six key events in the picture window, with the lowest point as one
    cash.counterfactual_series, _label  the grey line (the books without the funding the plan created, or doing nothing) and what it is
    cash.stress_available, cash.stress  the buyer paid 30 days late (behind the exposure flag)
    cash.pending, cash.receipts_legend_text  the reply FLOW recommends, drawn as an alternative until the buyer accepts it
    (every receipt event of a series, and the rail's receipt rows, carry `basis` and `basis_text`: what the receipt rests on)
    attention                           one primary at a time, the rest of the queue in order
    funding_line                        the plan's state as one sentence, with the cost split
    deals_card, receivables_card, changes_card

Presentation only: nothing here evaluates, stores, logs, prices or decides.
"""

from __future__ import annotations

import copy
import importlib
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.api.financing_words import State, state_of, state_word
from app.api.home import _lowest_ahead, _series
from app.api.presentation import (
    buyer_of_receivable,
    facility_name,
    fmt_short,
    in_language,
    in_words,
    party_name,
    t,
    when_text,
)
from app.api.presentation import tick_label as _short
from app.api.receipt_basis import RECEIPT_KINDS, BasisReader, annotate
from app.books import Books
from app.decisions.identity import deal_id
from app.decisions.state import DealState, FundingState
from app.domain.models import FacilityKind, FinancialState, LedgerEventKind, Mandate, Mode, ObligationType
from app.domain.money import fmt_yuan
from app.financial import EngineError, project
from app.financial.lots import ensure_lots
from app.strategy import words as basis_words
from app.strategy.cache import AnswerCache, cache_key

log = logging.getLogger("termsledger.decisions")

MAX_RAIL = 6
MAX_LEG_FACTS = 3
_LANDING_KINDS = ("DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING")
MAX_CHANGES = 3
_RECEIPTS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)
_CHARGES = (LedgerEventKind.INTEREST, LedgerEventKind.FEE)
_REPAYING = (LedgerEventKind.REPAYMENT, LedgerEventKind.INTEREST, LedgerEventKind.FEE)
_PAREN = re.compile(r"\s*[(（].*$")


@dataclass(frozen=True)
class HomeRead:
    """What the home has read when the hybrid is built (under the runtime's lock)."""

    rt: Any
    books: Books
    mandate: Mandate
    today: int
    lang: str
    traj: Any  # the CONSERVATIVE projection of the books
    plan_traj: Any | None  # the same books with the recommended plan applied, when one is ready and not yet run
    plan_series: list[dict[str, Any]] | None
    action: dict[str, Any] | None
    status: str
    status_text: str
    headline: str
    note: str
    low: tuple[int, int]  # (fen, day) of the lowest cash ahead
    breach_day: int | None
    picture_days: int
    queue: list[dict[str, Any]]  # the pending approvals' cards
    receivables: dict[str, Any]
    changes: list[dict[str, Any]]
    record: Any | None  # the decision record's context
    open_decisions: list[dict[str, Any]]
    basis: BasisReader | None = None  # what each receipt rests on, when it could be read
    partial: Any | None = None  # the home's `Partial`, for a supporting read that fails inside the hybrid

    @property
    def state(self) -> FinancialState:
        return self.books.state

    @property
    def waiting(self) -> bool:
        """The plan that is ready waits for the owner's approval rather than for a go-ahead."""
        return bool(self.action and self.action.get("pending_approval_id"))

    @property
    def floor(self) -> int:
        return self.mandate.min_cash_fen


# ---------------------------------------------------------------- small words


def whole(fen: int) -> str:
    """¥5,000 for a whole number of yuan, ¥3,027.77 otherwise (the limit the owner set)."""
    return fmt_yuan(fen).removesuffix(".00")


def _sp(lang: str) -> str:
    """The space between two sentences: Chinese runs them together."""
    return "" if lang == "zh" else " "


def _signed(fen: int) -> str:
    return "¥0" if fen == 0 else (f"+{fmt_short(fen)}" if fen > 0 else fmt_short(fen))


def _tone(cash_fen: int, floor_fen: int) -> str:
    """ok above the minimum, warn exactly on it, bad below it."""
    return "ok" if cash_fen > floor_fen else "warn" if cash_fen == floor_fen else "bad"


def room_text(cash_fen: int, floor_fen: int, lang: str) -> str:
    gap = cash_fen - floor_fen
    figure = _short(abs(gap))
    if gap >= 0:
        return t(lang, f"{figure} above your minimum", f"比您的最低现金高 {figure}")
    return t(lang, f"{figure} below your minimum", f"比您的最低现金低 {figure}")


def _layer(module: str) -> Any | None:
    """A module of the exposure layer, or None when it is not on this branch (the hybrid reads it only behind its flag and never requires it)."""
    try:
        return importlib.import_module(module)
    except ImportError:
        return None


def buyer_short(name: str, lang: str = "en") -> str:
    """The name an owner says aloud: its first word ("Foshan Home Retail Co." -> "Foshan"), the same in both languages (the one helper of
    `app.strategy.words`; a one-word name stays whole)."""
    return basis_words.buyer_short(name)


def _source(name: str, lang: str = "en") -> str:
    """A facility said without its parenthetical ("Invoice financing (onboarded platform)" -> "Invoice financing"); in Chinese, by the name
    the books give it."""
    return name if lang == "zh" else _PAREN.sub("", name)


def _pct(rate_bp: int | None) -> str:
    """A rate as the owner says it ("1%", "1.2%"), from integer basis points."""
    if rate_bp is None:
        return "?"
    sign, bp = ("-" if rate_bp < 0 else ""), abs(rate_bp)
    whole_part, rest = divmod(bp, 100)
    return f"{sign}{whole_part}.{rest:02d}".rstrip("0").rstrip(".") + "%"


def _link(decision_id: str) -> str:
    return f"/decisions/{quote(decision_id, safe='')}"


# ---------------------------------------------------------------- what the forecast leans on


def _pending_lots(state: FinancialState, today: int) -> list[Any]:
    """The funding that has been requested and has not landed yet, earliest first."""
    return sorted((lot for lot in ensure_lots(state).lots if not lot.settled and not lot.assumed_date and lot.arrival_day >= today),
                  key=lambda lot: (lot.arrival_day, lot.id))


def _next_receipts(c: HomeRead) -> list[dict[str, Any]]:
    """The next expected receipt of each buyer inside the horizon, from the trajectory's own events, earliest first."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for d in c.traj.days:
        if d.day < c.today:
            continue
        for e in d.events:
            if e.kind not in _RECEIPTS or e.amount_fen <= 0:
                continue
            buyer = buyer_of_receivable(c.state, e.ref)
            if buyer is None or buyer in seen:
                continue
            seen.add(buyer)
            out.append({"buyer_id": buyer, "name": buyer_short(party_name(c.state, buyer), c.lang), "day": d.day, "amount_fen": e.amount_fen,
                        "when": when_text(d.day, c.today, c.lang)})
    return out


def _lot_kind(lot: Any, lang: str, state: FinancialState) -> str:
    if lot.receivable_id:
        return t(lang, "invoice financing", "发票融资")
    return t(lang, f"funding from {facility_name(state, lot.facility_id)}", f"来自{facility_name(state, lot.facility_id)}的资金")


def _assumptions(c: HomeRead, lots: list[Any], receipts: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for lot in lots:
        amount, when = _short(lot.remaining_fen), when_text(lot.arrival_day, c.today, c.lang)
        out.append(t(c.lang, f"The {amount} of {_lot_kind(lot, 'en', c.state)} arrives {when}.",
                     f"{amount} {_lot_kind(lot, 'zh', c.state)}将于{when}到账。"))
    for r in receipts:
        out.append(t(c.lang, f"{r['name']} pays {_short(r['amount_fen'])} {r['when']}, as scheduled.",
                     f"{r['name']}将于{r['when']}按计划支付 {_short(r['amount_fen'])}。"))
    out.append(t(c.lang, "The scheduled payroll, supplier and debt payments are paid as entered.",
                 "已录入的工资、供应商和债务还款按计划支付。"))
    return out


def _clauses(c: HomeRead, lots: list[Any], receipts: list[dict[str, Any]]) -> str:
    """What the heading note says the cover rests on: "the financing arrives in 3 days and Foshan pays in 32 days as scheduled"."""
    parts: list[str] = []
    for lot in lots:
        when = when_text(lot.arrival_day, c.today, c.lang)
        what = _short(lot.remaining_fen) + " " if len(lots) > 1 else ""
        parts.append(t(c.lang, f"the {what}financing arrives {when}", f"{what}融资将于{when}到账"))
    if receipts:
        said = [t(c.lang, f"{r['name']} pays {r['when']}", f"{r['name']}将于{r['when']}付款") for r in receipts]
        joined = t(c.lang, " and ".join(said) + " as scheduled", "、".join(said) + "（按计划）")
        parts.append(joined)
    return t(c.lang, " and ".join(parts), "，".join(parts))


def _position(c: HomeRead, lots: list[Any], receipts: list[dict[str, Any]], low: tuple[int, int]) -> dict[str, Any]:
    covered = c.breach_day is None
    floor = _short(c.floor)
    low_fen, low_day = low
    depends = covered and bool(lots or receipts)
    if not depends:
        return {"headline_conditional": c.headline, "headline_note": c.note}
    stays = (t(c.lang, "at or above", "不低于") if low_fen == c.floor else t(c.lang, "above", "高于"))
    lowest = (t(c.lang, f"It touches the minimum {when_text(low_day, c.today, c.lang)}.",
                f"{when_text(low_day, c.today, c.lang)}会触及最低现金。") if low_fen == c.floor
              else t(c.lang, f"Its lowest point is {_short(low_fen)} {when_text(low_day, c.today, c.lang)}.",
                     f"最低点为{when_text(low_day, c.today, c.lang)}的 {_short(low_fen)}。"))
    h = c.mandate.horizon_days
    note = t(c.lang, f"Cash stays {stays} your {floor} minimum for the next {h} days, assuming {_clauses(c, lots, receipts)}. {lowest}",
             f"未来 {h} 天现金都{stays}您 {floor} 的最低现金，前提是{_clauses(c, lots, receipts)}。{lowest}")
    return {"headline_conditional": t(c.lang, "Your cash is covered on the current plan.", "按当前方案，您的现金是安全的。"),
            "headline_note": note}


def _facts(c: HomeRead, lots: list[Any], receipts: list[dict[str, Any]], low: tuple[int, int]) -> list[dict[str, Any]]:
    """The three facts. The lowest point is that of the line the page draws (the recommended plan's when one is ready, else the books'),
    the same point the rail names."""
    cash = c.state.cash_fen
    low_fen, low_day = low
    low_when = when_text(low_day, c.today, c.lang)
    with_plan = c.plan_traj is not None
    arrivals: list[tuple[int, int, dict[str, Any]]] = []
    for lot in lots:
        arrivals.append((lot.arrival_day, 0, {"fen": lot.remaining_fen, "source": _source(facility_name(c.state, lot.facility_id), c.lang),
                                              "when": when_text(lot.arrival_day, c.today, c.lang)}))
    for r in receipts:
        arrivals.append((r["day"], 1, {"fen": r["amount_fen"], "source": r["name"], "when": r["when"]}))
    nxt = min(arrivals, key=lambda a: (a[0], a[1]))[2] if arrivals else None
    arriving: dict[str, Any] = {"key": "arriving", "label": t(c.lang, "Arriving next", "下一笔到账"), "tone": "neutral"}
    if nxt is not None:
        arriving.update(value_fen=nxt["fen"], value_short=_short(nxt["fen"]), note=f"{nxt['source']}{t(c.lang, ', ', '，')}{nxt['when']}")
    else:
        arriving.update(value_fen=None, value_short=None,
                        note=t(c.lang, "Nothing is expected to arrive in the forecast.", "预测期内没有预计到账的款项。"))
    return [
        {"key": "today", "label": t(c.lang, "Cash today", "今日现金"), "value_fen": cash, "value_short": _short(cash),
         "note": room_text(cash, c.floor, c.lang), "tone": _tone(cash, c.floor)},
        {"key": "lowest", "label": (t(c.lang, f"Lowest point with the plan, {low_when}", f"采用方案后的最低点，{low_when}") if with_plan
                                                  else t(c.lang, f"Lowest point, {low_when}", f"最低点，{low_when}")), "when": low_when,
         "value_fen": low_fen, "value_short": _short(low_fen), "note": room_text(low_fen, c.floor, c.lang),
         "tone": _tone(low_fen, c.floor)},
        arriving,
    ]


# ---------------------------------------------------------------- the grey line: without the plan


def _without_plan(state: FinancialState) -> FinancialState | None:
    """The books as they were before the plan ran: the funding the plan's operations created taken off the copy (the cash they landed,
    the facility balance they added, the invoice they advanced on), for the kernel to project. None when nothing can be taken off
    cleanly (a lot already part-repaid)."""
    with_lots = ensure_lots(state)
    plan_lots = [lot for lot in with_lots.lots if not lot.assumed_date]
    if not plan_lots:
        return None
    cash = with_lots.cash_fen
    facilities = {f.id: f for f in with_lots.facilities}
    receivables = {r.id: r for r in with_lots.receivables}
    for lot in plan_lots:
        facility = facilities.get(lot.facility_id)
        if facility is None or lot.remaining_fen != lot.principal_fen:
            return None
        facilities[facility.id] = facility.model_copy(update={"drawn_fen": facility.drawn_fen - lot.remaining_fen})
        if lot.settled:
            cash -= lot.principal_fen
        r = receivables.get(lot.receivable_id) if lot.receivable_id else None
        if r is not None:
            receivables[r.id] = r.model_copy(update={"status": "OPEN", "advance_fen": 0, "advance_facility_id": None})
    keep = [lot for lot in with_lots.lots if lot.assumed_date]
    return with_lots.model_copy(update={
        "cash_fen": cash, "facilities": [facilities[f.id] for f in with_lots.facilities],
        "receivables": [receivables[r.id] for r in with_lots.receivables], "lots": keep})


def _plan_has_run(state: FinancialState) -> bool:
    return any(not lot.assumed_date for lot in ensure_lots(state).lots)


def _grey_line(c: HomeRead) -> tuple[Any | None, str]:
    """(the trajectory the grey line draws, what it is). "nothing": the books as they stand, against the plan that is ready. "proposed": the
    same books, against a further plan that is ready after one already ran. "ran": the books without the funding the plan created, against
    the books as they are now. "none": there is nothing to compare."""
    ran = _plan_has_run(c.state)
    if c.plan_traj is not None:
        return c.traj, "proposed" if ran else "nothing"
    if not ran:
        return None, "none"
    cf = _without_plan(c.state)
    if cf is None:
        return None, "none"
    try:
        return project(cf, c.books.with_([]), [], Mode.CONSERVATIVE, c.mandate.horizon_days, c.floor), "ran"
    except EngineError:
        log.exception("the books without the plan could not be projected for the home")
        return None, "none"


# ---------------------------------------------------------------- the event rail


def _main_event(events: list[Any]) -> Any | None:
    """The posting that names the day: a receipt when there is one, else the largest of the others (interest and fees follow their
    repayment and never name a day)."""
    named = [e for e in events if e.kind not in _CHARGES and e.kind != LedgerEventKind.OPENING and e.amount_fen != 0]
    receipt = [e for e in named if e.kind in _RECEIPTS and e.amount_fen > 0]
    pool = receipt or named
    return max(pool, key=lambda e: (abs(e.amount_fen), e.label)) if pool else None


def _cause_event(events: list[Any]) -> Any | None:
    """The posting that causes the day's low: the largest outflow (a receipt that day does not cause a low), else, with no outflow, the
    day's largest posting."""
    out = [e for e in events if e.amount_fen < 0 and e.kind not in _CHARGES and e.kind != LedgerEventKind.OPENING]
    return min(out, key=lambda e: (e.amount_fen, e.label)) if out else _main_event(events)


def _flow_kind(label: str, amount_fen: int) -> str:
    low = label.lower()
    if low.startswith("payroll"):
        return "payroll"
    if low.startswith("debt service"):
        return "debt"
    if amount_fen > 0:
        return "receipt"
    return "supplier"


def _event_kind(e: Any) -> str:
    if e.kind in (LedgerEventKind.ADVANCE, LedgerEventKind.DRAW):
        return "landing" if e.amount_fen > 0 else "repayment"
    if e.kind in _RECEIPTS:
        return "receipt"
    if e.kind == LedgerEventKind.REPAYMENT:
        return "repayment"
    return _flow_kind(e.label, e.amount_fen)


def _label(kind: str, e: Any, c: HomeRead, planned: bool = False) -> str:
    lang, state = c.lang, c.state
    if kind == "landing":
        what = (t(lang, "invoice financing", "发票融资") if e.kind == LedgerEventKind.ADVANCE
                else t(lang, f"the {_source(facility_name(state, e.ref), lang)} draw", f"{_source(facility_name(state, e.ref), lang)}提款"))
        if planned:  # the plan has not run: nothing arrives unless the owner runs it (or approves it)
            if c.waiting:
                return t(lang, f"{what} would arrive, if you approve the plan", f"{what}将到账，前提是您批准方案")
            return t(lang, f"{what} would arrive, if you run the plan", f"{what}将到账，前提是您执行方案")
        return t(lang, f"{what} arrives", f"{what}到账")
    if kind == "payroll":
        return t(lang, "payroll is paid", "发放工资")
    if kind == "debt":
        return t(lang, "debt service is paid", "支付债务还款")
    if kind == "receipt":
        buyer = buyer_of_receivable(state, e.ref)
        who = buyer_short(party_name(state, buyer), lang) if buyer else ""
        if who:
            return t(lang, f"{who} pays", f"{who}付款")
        return t(lang, "a payment arrives", "收到一笔款项")
    if kind == "repayment":
        return t(lang, f"{_source(facility_name(state, e.ref), lang)} is repaid", f"偿还{_source(facility_name(state, e.ref), lang)}")
    if kind == "lowest":
        return t(lang, "cash is at its lowest", "现金降到最低点")
    if e.label.lower().startswith("supplier"):
        return t(lang, "a supplier payment goes out", "支付供应商款项")
    name = in_language(in_words(state, e.label.split(" (")[0].split(", ")[0]), lang, state) or ""
    return t(lang, f"{name.lower()} is paid", f"支付{name}")


def _cause_label(kind: str, e: Any, c: HomeRead, planned: bool) -> str:
    """What the lowest point's row names: the event that causes it, in its own words."""
    if kind == "debt":
        return t(c.lang, "a loan repayment goes out", "一笔贷款还款支出")
    return _label(kind, e, c, planned)


def _lowest_note(c: HomeRead, after: int) -> str:
    """"cash at its lowest, ¥300k, at your minimum": the one figure the lowest point has, and where it stands against the minimum."""
    where = (t(c.lang, "at your minimum", "正好是您的最低现金") if after == c.floor else room_text(after, c.floor, c.lang))
    return t(c.lang, f"cash at its lowest, {_short(after)}, {where}", f"现金降到最低，{_short(after)}，{where}")


def _effect_rows(c: HomeRead, d: Any) -> list[dict[str, str]]:
    """The day's effect as a table, from the figures the paragraph uses: cash before, cash after, the minimum, and the room above it."""
    gap = d.closing_fen - c.floor
    return [{"label": t(c.lang, "Cash before", "此前现金"), "display": _short(d.opening_fen)},
            {"label": t(c.lang, "Cash after", "此后现金"), "display": _short(d.closing_fen)},
            {"label": t(c.lang, "Minimum reserve", "最低现金储备"), "display": _short(c.floor)},
            {"label": (t(c.lang, "Cash above reserve", "高于储备的现金") if gap >= 0 else t(c.lang, "Cash below reserve", "低于储备的现金")),
             "display": _short(abs(gap))}]


def _noun(kind: str, lang: str) -> str:
    return {"payroll": t(lang, "payroll", "工资"), "supplier": t(lang, "the supplier payment", "供应商付款"),
            "debt": t(lang, "debt service", "债务还款")}.get(kind, t(lang, "the payment", "这笔付款"))


def _room_sentence(after: int, floor: int, lang: str) -> str:
    gap = after - floor
    if gap > 0:
        return t(lang, f"Your minimum is {_short(floor)}, so {_short(gap)} of room remains.",
                 f"您的最低现金是 {_short(floor)}，所以还有 {_short(gap)} 的余量。")
    if gap == 0:
        return t(lang, f"Your minimum is {_short(floor)}, so there is no room left.", f"您的最低现金是 {_short(floor)}，已没有余量。")
    return t(lang, f"Your minimum is {_short(floor)}, so cash is {_short(-gap)} below it.",
             f"您的最低现金是 {_short(floor)}，现金比它低 {_short(-gap)}。")


def _grey_subject(c: HomeRead, kind: str) -> str:
    """How a sentence names the grey line, by what it is."""
    if kind == "ran":
        return t(c.lang, "Without the financing plan", "如果没有融资方案")
    if kind == "proposed":
        return t(c.lang, "Without the plan FLOW proposes", "如果不采用 FLOW 建议的方案")
    return t(c.lang, "If you did nothing", "如果您什么都不做")


def _financing_refs(state: FinancialState, receipt_ref: str | None) -> set[str]:
    """The facilities that lend against an invoice: the one that advanced on it, else every invoice-financing facility."""
    r = next((x for x in state.receivables if x.id == receipt_ref), None)
    if r is not None and r.advance_facility_id:
        return {r.advance_facility_id}
    return {f.id for f in state.facilities if f.kind == FacilityKind.INVOICE_FINANCING}


def receipt_words(c: HomeRead, day: Any, receipt: Any, lang: str) -> str:
    """A receipt day in words, the one claim the rail and the receivables card both make: what came in, what of it repays the invoice
    financing (its principal and charges, the day's own postings on the lender's facility), what is left, and what else the day repays.
    The one difference is the receipt less the financing it repays."""
    buyer = buyer_of_receivable(c.state, receipt.ref)
    who = buyer_short(party_name(c.state, buyer), lang) if buyer else t(lang, "The buyer", "买方")
    rest = [e for e in day.events if e is not receipt and e.kind in _REPAYING]
    refs = _financing_refs(c.state, receipt.ref)
    financing = [e for e in rest if e.ref in refs]
    other = [e for e in rest if e.ref not in refs]
    amount = receipt.amount_fen
    head = t(lang, f"{who} pays {_short(amount)}", f"{who}支付 {_short(amount)}")
    if financing:
        repaid = -sum(e.amount_fen for e in financing)
        head += t(lang, f", and {_short(repaid)} of it repays the invoice financing, leaving {_short(amount - repaid)}.",
                  f"，其中 {_short(repaid)} 用于偿还发票融资，剩余 {_short(amount - repaid)}。")
    else:
        head += t(lang, ".", "。")
    if other:
        names = list(dict.fromkeys(_source(facility_name(c.state, e.ref), lang) for e in other if e.kind == LedgerEventKind.REPAYMENT))
        name = t(lang, " and the ", "和").join(names) or t(lang, "credit line", "信用额度")
        total = -sum(e.amount_fen for e in other)
        of = t(lang, "that" if financing else "it", "")
        head += t(lang, f" {_short(total)} of {of} repays the {name}.", f"{'剩余的钱中 ' if financing else '其中 '}{_short(total)} 用于偿还{name}。")
    return head


def _explain(c: HomeRead, day: Any, kind: str, main: Any, grey_close: dict[int, int], grey_kind: str) -> str:
    lang = c.lang
    before, after = day.opening_fen, day.closing_fen
    if kind == "receipt" and main.kind in _RECEIPTS:
        lead = receipt_words(c, day, main, lang)
        move = t(lang, f" Cash {'rises' if after >= before else 'falls'} from {_short(before)} to {_short(after)}, "
                       f"{room_text(after, c.floor, lang)}.",
                 f"现金从 {_short(before)} {'升至' if after >= before else '降至'} {_short(after)}，{room_text(after, c.floor, lang)}。")
        return lead + move
    verb = t(lang, "rises" if after >= before else "falls", "升至" if after >= before else "降至")
    text = (t(lang, f"Cash {verb} from {_short(before)} to {_short(after)}.", f"现金从 {_short(before)} {verb} {_short(after)}。")
            + _sp(lang) + _room_sentence(after, c.floor, lang))
    grey = grey_close.get(day.day)
    if grey is not None and grey < c.floor and kind in ("payroll", "supplier", "debt"):
        subject = _grey_subject(c, grey_kind)
        took = "would have taken" if grey_kind == "ran" else "would take"
        text += _sp(lang) + t(lang, f"{subject}, {_noun(kind, lang)} {took} cash to {_short(grey)}, below your minimum.",
                        f"{subject}，{_noun(kind, lang)}会使现金降至 {_short(grey)}，低于您的最低现金。")
    return text


def _lowest_explain(c: HomeRead, day: Any, main: Any | None, kind: str | None, grey: Any | None, grey_kind: str) -> str:
    lang = c.lang
    after = day.closing_fen
    text = t(lang, f"This is the lowest point on your cash line: {_short(after)}, {room_text(after, c.floor, lang)}.",
             f"这是您现金线上的最低点：{_short(after)}，{room_text(after, c.floor, lang)}。")
    if main is not None and kind in ("payroll", "supplier", "debt"):
        text += _sp(lang) + t(lang, f"{_noun(kind, lang).capitalize()} of {_short(abs(main.amount_fen))} takes cash from "
                              f"{_short(day.opening_fen)} to {_short(after)}.",
                        f"{_noun(kind, lang)} {_short(abs(main.amount_fen))} 使现金从 {_short(day.opening_fen)} 降至 {_short(after)}。")
    if grey is not None:
        g_fen, g_day = _lowest_ahead(grey, c.today)
        subject = _grey_subject(c, grey_kind)
        be = "would have been" if grey_kind == "ran" else "would be"
        text += _sp(lang) + t(lang, f"{subject}, the lowest point {be} {_short(g_fen)} {when_text(g_day, c.today, lang)}.",
                        f"{subject}，最低点会是{when_text(g_day, c.today, lang)}的 {_short(g_fen)}。")
    return text


def _rail(c: HomeRead, line: Any, grey: Any | None, grey_kind: str, reader: BasisReader | None = None) -> list[dict[str, Any]]:
    """The key events of the picture window on the line the page draws, and the lowest point ahead (which the window may not reach: then
    the rail runs past it), ascending."""
    end = c.today + c.picture_days
    by_day = {d.day: d for d in line.days if c.today <= d.day <= end}
    ahead = [d for d in line.days if d.day >= c.today]
    if not ahead:
        return []
    _, low_day = _lowest_ahead(line, c.today)
    by_day[low_day] = next(d for d in ahead if d.day == low_day)
    weights: dict[int, int] = {}
    for d in by_day.values():
        main = _main_event(d.events)
        if main is not None and d.day != low_day:
            weights[d.day] = abs(main.amount_fen)
    chosen = sorted(sorted(weights, key=lambda day: (-weights[day], day))[:MAX_RAIL - 1] + [low_day])
    grey_close = {d.day: d.closing_fen for d in grey.days} if grey is not None else {}
    # what the plan ready (not run) adds to the books: its landings are only planned
    # (two identical landings are two events: the plan's are those the books do not already hold, counted)
    already = Counter((d.day, e.kind, e.ref, e.amount_fen) for d in c.traj.days for e in d.events) if c.plan_traj is not None else Counter()
    line_count = Counter((d.day, e.kind, e.ref, e.amount_fen) for d in line.days for e in d.events)
    out: list[dict[str, Any]] = []
    for day_no in chosen:
        d = by_day[day_no]
        main = _cause_event(d.events) if day_no == low_day else _main_event(d.events)
        kind = _event_kind(main) if main is not None else None
        net = sum(e.amount_fen for e in d.events)
        planned = False
        if main is not None and kind == "landing" and c.plan_traj is not None:
            ident = (d.day, main.kind, main.ref, main.amount_fen)
            planned = line_count[ident] > already[ident]
        note = None
        if day_no == low_day:
            event_kind = "lowest"
            # the row names the event that causes the low, with its amount; the low itself is the note, never a second number
            label = (_cause_label(kind, main, c, planned) if main is not None and kind is not None
                     else t(c.lang, "cash is at its lowest", "现金降到最低点"))
            note = _lowest_note(c, d.closing_fen)
            explain = _lowest_explain(c, d, main, kind, grey, grey_kind)
        else:
            assert main is not None and kind is not None
            event_kind = kind
            label = _label(kind, main, c, planned)
            explain = _explain(c, d, kind, main, grey_close, grey_kind)
        said = reader.fields(main) if reader is not None and main is not None and main.kind in RECEIPT_KINDS else {}
        out.append({"key": f"day-{day_no}", "day": day_no, "when": when_text(day_no, c.today, c.lang), "kind": event_kind,
                    "basis": said.get("basis"), "basis_text": said.get("basis_text"),
                    "label": label, "note": note, "planned": planned, "amount_fen": main.amount_fen if main is not None else 0,
                    "amount_short": _signed(main.amount_fen) if main is not None else "¥0", "net_short": _signed(net),
                    "cash_after_fen": d.closing_fen, "cash_after_short": _short(d.closing_fen),
                    "room_after_fen": d.closing_fen - c.floor, "room_after_short": room_text(d.closing_fen, c.floor, c.lang),
                    "tone": _tone(d.closing_fen, c.floor), "explain": explain, "effect_rows": _effect_rows(c, d)})
    return out


# ---------------------------------------------------------------- the late-payment stress (behind the exposure flag)


def _exposure_on(rt: Any) -> bool:
    return bool(getattr(rt.settings.features, "exposure", False))


def _stress_buyer(c: HomeRead, primary_buyer: str | None) -> str | None:
    if primary_buyer is not None:
        return primary_buyer
    nxt = c.receivables.get("next_receipt")
    return nxt["buyer_id"] if nxt else None


_STRESS: AnswerCache[dict[str, Any]] = AnswerCache()


def _net_later(c: HomeRead, buyer_id: str, delay: int) -> str | None:
    """What the buyer's open invoices leave the owner `delay` days after the day each is priced on, in the buyer route's own words
    (`exposure_words.net_later`: one function for the Home and the buyer's pages); None when the buyer owes nothing."""
    from app.api.exposure_words import net_later

    said = net_later(c.state, buyer_id, c.today, delay, c.lang)
    return said["net_later_text"] if said is not None else None


def _stress(c: HomeRead, buyer_id: str | None) -> dict[str, Any] | None:
    """The buyer paying every invoice 30 days late (a test, not a forecast), when the exposure flag is on and the layer has its stress.
    The row and the line are the layer's own (`stress` and `_stress_line`); the answer is cached by the books, the mandate, the day, the
    commitments, the buyer and the language, like the offer picture, so a Home read pays for it once per state."""
    if buyer_id is None or not _exposure_on(c.rt):
        return None
    impact, exposure = _layer("app.strategy.impact"), _layer("app.strategy.exposure")
    stress = getattr(impact, "stress", None)
    stress_line = getattr(exposure, "_stress_line", None)
    delay = getattr(exposure, "STRESS_DELAY_DAYS", None)
    if stress is None or stress_line is None or delay is None:
        log.warning("the exposure flag is on but the exposure layer has no late-payment stress; the home omits it")
        return None
    commitments = tuple(c.rt.store.commitments())
    key = cache_key(c.state, c.mandate, c.today, commitments, "home-stress", "|".join(o.model_dump_json() for o in c.books.obligations),
                    buyer_id, c.lang)

    def compute() -> dict[str, Any]:
        row = stress(c.books, c.mandate, buyer_id, (delay,), c.today, commitments, lang=c.lang)[0]
        line = stress_line(c.books, c.mandate, buyer_id, c.today, delay, c.lang)
        receipt = next((d.day for d in c.traj.days if d.day >= c.today for e in d.events
                        if e.kind == LedgerEventKind.RECEIPT and buyer_of_receivable(c.state, e.ref) == buyer_id), None)
        moved = (receipt + delay) if receipt is not None else row.lowest_day
        needed = max(row.lowest_day, moved) - c.today + 4
        name = party_name(c.state, buyer_id)
        sentence = getattr(exposure, "stress_sentence", None)
        return {"delay_days": delay, "buyer": buyer_short(party_name(c.state, buyer_id), c.lang), "buyer_id": buyer_id, "series": line,
                "lowest_fen": row.lowest_fen, "lowest_short": _short(row.lowest_fen),
                "lowest_when": when_text(row.lowest_day, c.today, c.lang), "breach_days": row.breach_days,
                "need_fen": row.need_fen, "need_short": _short(row.need_fen), "plan_text": row.funding_text,
                "text": sentence(row, name, c.today, c.floor, c.lang) if sentence is not None else None,
                "funding_text": row.funding_text, "net_later_text": _net_later(c, buyer_id, delay),
                "assumption_text": in_words(c.state, row.assumption), "window_days_needed": max(1, min(c.mandate.horizon_days, needed))}

    try:
        return dict(_STRESS.get_or_compute(key, compute))
    except ValueError:  # nothing open or scheduled to pay late: there is nothing to test
        return None
    except Exception:  # a supporting read: the home never goes down for it, and the fault is logged
        log.exception("the late-payment stress could not be read for the home")
        return None


def _moved_by_reply(c: HomeRead, deal: _Deal) -> Counter[tuple[int, str, int]] | None:
    """The receipts the reply's own obligations produce that the books do not hold, as (day, kind, amount) counted: the books with the
    reply's obligations and no funding, projected by the engine, less the books' own receipts. Only these are pending on the buyer; the
    funding legs of the reply's plan (an early-pay leg, a discounted bill) are FLOW's to run whatever the buyer says. None when the
    reply cannot be projected or found."""
    from app.api.decisions import latest_verdict_for

    verdict = latest_verdict_for(c.rt, deal.offer_id)
    counter = next((x for x in verdict.counters if deal.pick is not None and x.id == deal.pick.get("key")), None) if verdict else None
    if counter is None:
        return None
    try:
        traj = project(c.state, c.books.with_(counter.obligations), [], Mode.CONSERVATIVE, c.mandate.horizon_days, c.floor)
    except EngineError:
        log.exception("the recommended reply could not be projected for the home")
        return None

    def receipts(t_: Any) -> Counter[tuple[int, str, int]]:
        return Counter((d.day, e.kind.value, e.amount_fen) for d in t_.days if d.day >= c.today for e in d.events if e.kind in RECEIPT_KINDS)

    return receipts(traj) - receipts(c.traj)


def _pending(c: HomeRead, deals: list[_Deal] | None) -> dict[str, Any] | None:
    """The reply FLOW recommends, as an alternative to the plan line and never the plan: the picture's own series for that path (copied,
    the picture's cache is shared), with the receipts the reply's obligations move marked PENDING. Present while an open offer has a
    sendable reply that no agreement records; absent once the buyer accepts (the agreement then moves the receipts and they are AGREED)
    or the offer closes. A receipt the reply leaves alone keeps the basis the books give it (matched by day, kind and amount against the
    trajectory); a funding leg of the reply's plan stays bare."""
    reader = c.basis
    deal = next((d for d in deals or [] if reader is not None and d.pick is not None and d.pick.get("kind") == "reply"
                 and d.pick.get("sendable") and d.pick.get("series")), None)
    if deal is None or deal.pick is None or reader is None:
        return None
    moved = _moved_by_reply(c, deal)
    if moved is None:
        return None
    option = str(deal.pick.get("label") or "")
    known: dict[tuple[int, str, int], list[Any]] = {}
    for d in c.traj.days:
        if d.day >= c.today:
            for e in d.events:
                if e.kind in RECEIPT_KINDS:
                    known.setdefault((d.day, e.kind.value, e.amount_fen), []).append(reader.of(e))
    kinds = {k.value for k in RECEIPT_KINDS}
    series = copy.deepcopy(deal.pick["series"])
    rows: list[dict[str, Any]] = []
    for row in series:
        for e in row["events"]:
            if e["kind"] not in kinds:
                continue
            key = (row["day"], e["kind"], e["amount_fen"])
            if moved[key] > 0:  # the reply's obligations produce this receipt
                moved[key] -= 1
                discount = e["kind"] == LedgerEventKind.DISCOUNT.value
                text = basis_words.pending_text(c.lang, deal.buyer, option, amount_fen=e["amount_fen"], days_after=row["day"] - c.today,
                                                discount=discount)
                e["basis"], e["basis_text"] = basis_words.PENDING, text
                rows.append({"day": row["day"], "when": when_text(row["day"], c.today, c.lang), "kind": e["kind"],
                             "label_short": t(c.lang, "Early-payment discount", "提前付款折扣") if discount else e["label_short"],
                             "amount_fen": e["amount_fen"], "amount_short": e["amount_short"],
                             "basis": basis_words.PENDING, "basis_text": text})
            elif known.get(key):  # the books already hold this receipt: the reply leaves it alone
                b = known[key].pop(0)
                if b is not None:
                    e["basis"], e["basis_text"] = b.code, reader.text(b)
    return {"label": basis_words.pending_label(c.lang, deal.buyer, option), "series": series, "receipt_rows": rows,
            "legend_text": basis_words.receipts_legend(c.lang, deal.buyer, option)}


def _guarded(c: HomeRead, read: Any) -> Any:
    """A read of what the receipts rest on: whatever fails is logged and named in `partial` (never the summary), and the picture stands
    without it."""
    try:
        return read()
    except Exception:
        log.exception("the basis of the receipts could not be read for the home")
        if c.partial is not None:
            c.partial.add("receipt_basis")
        return None


def cash_block(c: HomeRead, stress_buyer: str | None, deals: list[_Deal] | None = None) -> dict[str, Any]:
    lots, receipts = _pending_lots(c.state, c.today), _next_receipts(c)
    tone = {"SAFE": "ok", "WATCH": "warn"}.get(c.status, "bad")
    line = c.plan_traj if c.plan_traj is not None else c.traj
    low = _lowest_ahead(line, c.today)  # one lowest point on the page: the line's, for the fact and for the rail
    grey, grey_kind = _grey_line(c)
    stress = _stress(c, stress_buyer)
    rail = _rail(c, line, grey, grey_kind, c.basis)
    out: dict[str, Any] = {
        "status_word": c.status_text, "status_tone": tone,
        **_position(c, lots, receipts, low), "assumptions": _assumptions(c, lots, receipts),
        "facts": _facts(c, lots, receipts, low),
        "events_rail": rail, "events_rail_days": max([c.picture_days, *(e["day"] - c.today for e in rail)]),
        "stress_available": stress is not None,
    }
    if grey is not None:  # the grey line and its words go together: no series, no label
        out["counterfactual_series"] = _series(c.state, grey, c.lang, c.today)
        if c.basis is not None:
            _guarded(c, lambda: annotate(out["counterfactual_series"], grey, c.basis))
        out["counterfactual_label"] = {
            "ran": t(c.lang, "without FLOW's financing plan (a comparison, not a choice you still have)",
                     "没有 FLOW 融资方案的情形（仅供对比，不是您还能选择的做法）"),
            "proposed": t(c.lang, "without the plan FLOW proposes (a comparison)", "不采用 FLOW 建议方案的情形（仅供对比）"),
            "nothing": t(c.lang, "if you did nothing", "如果您什么都不做")}[grey_kind]
    if c.plan_traj is not None:  # the plan line's legend: until its operations execute it is a question, then it is the executed plan
        out["plan_line_label"] = (t(c.lang, "If you approve FLOW's plan", "如果您批准 FLOW 的方案") if c.waiting
                                  else t(c.lang, "If you run FLOW's plan", "如果您执行 FLOW 的方案"))
    elif _plan_has_run(c.state):
        out["plan_line_label"] = t(c.lang, "With FLOW's plan", "采用 FLOW 的方案")
    if stress is not None:
        out["stress"] = stress
    pending = _guarded(c, lambda: _pending(c, deals))
    if pending is not None:  # a reply is waiting on the buyer: drawn dashed, with the sentence that tells it from the solid line
        out["receipts_legend_text"] = pending.pop("legend_text")
        out["pending"] = pending
    return out


# ---------------------------------------------------------------- the deals


@dataclass(frozen=True)
class _Deal:
    buyer_id: str
    buyer: str
    offer_id: str
    state: DealState
    view: dict[str, Any]  # the Deals read's open offer
    offer: Any | None
    pick: dict[str, Any] | None  # the picture's recommended path


_ASK_ORDER = {ObligationType.TERMS_EXTENSION: 0, ObligationType.CONTINGENT_REBATE: 1, ObligationType.IMMEDIATE_DISCOUNT: 2}


def _asks(offer: Any, lang: str, card: bool, state: FinancialState, today: int) -> str:
    """What the buyer asked for, in the owner's words: "60-day terms + 1% rebate" on the card, "60-day terms and a 1% rebate" in a sentence."""
    from app.deals import _join, _obligation_text

    parts: list[str] = []
    for o in sorted(offer.obligations, key=lambda o: _ASK_ORDER.get(o.type, 9)):
        if o.type == ObligationType.CLAIMED_PRIOR_CONCESSION:
            continue
        if o.type == ObligationType.TERMS_EXTENSION and o.target_terms_days is not None:
            parts.append(t(lang, f"{o.target_terms_days}-day terms", f"{o.target_terms_days} 天账期"))
        elif o.type == ObligationType.CONTINGENT_REBATE and o.rate_bp is not None:
            parts.append(t(lang, f"{_pct(o.rate_bp)} rebate" if card else f"a {_pct(o.rate_bp)} rebate", f"{_pct(o.rate_bp)} 返利"))
        elif o.type == ObligationType.IMMEDIATE_DISCOUNT and o.rate_bp is not None:
            parts.append(t(lang, f"{_pct(o.rate_bp)} off for early payment" if card else f"a {_pct(o.rate_bp)} discount for paying early",
                           f"提前付款折扣 {_pct(o.rate_bp)}"))
        else:
            parts.append(_obligation_text(o, lang, today, state))
    if not parts:
        return ""
    return " + ".join(parts) if card else _join(parts, lang)


def _picture_pick(c: HomeRead, offer_id: str) -> dict[str, Any] | None:
    """The path the Deals page recommends for this offer (the picture's, cached per state version), or None."""
    try:
        from app.api.offer_picture import cached_picture

        pic = cached_picture(c.rt, offer_id, c.lang)
    except Exception:  # a supporting read: the deal then reads from the Deals read's own words
        log.exception("the offer picture could not be read for the home")
        return None
    return next((p for p in pic.get("paths") or [] if p.get("recommended")), None)


def _deals(c: HomeRead) -> list[_Deal] | None:
    """The open offers of the buyers; None when the decision record could not be read (the home names that in `partial`, and the page
    must not read it as "No deals are open"). An offers read that fails raises: the home then says its summary could not be built."""
    ctx = c.record
    if ctx is None:
        return None
    from app.api.deal_offers import open_offers

    found = open_offers(ctx, c.lang)
    out: list[_Deal] = []
    for buyer_id, (view, state) in found.items():
        offer = ctx.offer(view["offer_id"])
        pick = (_picture_pick(c, view["offer_id"])
                if view.get("verdict_id") and state in (DealState.RESPONSE_READY, DealState.AUTHORIZATION_REQUIRED) else None)
        out.append(_Deal(buyer_id, party_name(c.state, buyer_id), view["offer_id"], state, view, offer, pick))
    return sorted(out, key=lambda d: (_ORDER.get(d.state, 9), d.buyer))


_ORDER = {DealState.RECEIVED: 0, DealState.RESPONSE_READY: 0, DealState.AUTHORIZATION_REQUIRED: 1, DealState.NEEDS_CLARIFICATION: 2}
_STATUS = {DealState.RECEIVED: ("Your response needed", "需要您答复"), DealState.RESPONSE_READY: ("Your response needed", "需要您答复"),
           DealState.AUTHORIZATION_REQUIRED: ("Needs your approval", "需要您批准"),
           DealState.NEEDS_CLARIFICATION: ("Awaiting the buyer", "等待买方"), DealState.AGREED: ("Agreed", "已达成")}


def _recommendation(d: _Deal, lang: str) -> tuple[str, str | None]:
    """(the card's recommendation, the sentence's), from the picture's recommended path; the Deals read's own words when there is none."""
    p = d.pick
    if p is None:
        text = d.view.get("action_text") or ""
        return text, text
    cost = p.get("cost_display") or ""
    free = cost in ("", fmt_yuan(0))
    if p.get("kind") == "asked":
        card = (t(lang, "Accept as asked, no estimated cost", "按对方要求接受，预计无成本") if free
                else t(lang, f"Accept as asked, estimated cost {cost}", f"按对方要求接受，预计成本 {cost}"))
        return card, t(lang, "FLOW recommends accepting it.", "FLOW 建议接受。")
    label = p.get("label") or ""
    card = (t(lang, f"Counter with {label}, no estimated cost", f"以{label}还价，预计无成本") if free
            else t(lang, f"Counter with {label}, estimated cost {cost}", f"以{label}还价，预计成本 {cost}"))
    return card, t(lang, f"FLOW recommends countering with {label}.", f"FLOW 建议以{label}还价。")


def deals_card(c: HomeRead, deals: list[_Deal]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for d in deals:
        en, zh = _STATUS[d.state]
        card, _ = _recommendation(d, c.lang)
        rows.append({"buyer": d.buyer, "buyer_id": d.buyer_id, "status_text": t(c.lang, en, zh),
                     "request_text": _asks(d.offer, c.lang, True, c.state, c.today) if d.offer is not None else d.view.get("asks_text"),
                     "recommendation_text": card, "href": f"/deals?buyer={quote(d.buyer_id, safe='')}"})
    ctx = c.record
    if ctx is not None:  # agreed deals, one per buyer with nothing open
        seen = {d.buyer_id for d in deals}
        agreed = sorted((ds for ds, _ in ctx.states().values() if ds.family == "DEAL" and ds.state == DealState.AGREED and ds.offer),
                        key=lambda ds: -ds.updated_seq)
        for ds in agreed:
            cp = ds.offer.counterparty_id
            if cp in seen:
                continue
            seen.add(cp)
            rows.append({"buyer": party_name(c.state, cp), "buyer_id": cp, "status_text": t(c.lang, *_STATUS[DealState.AGREED]),
                         "request_text": _asks(ds.offer, c.lang, True, c.state, c.today), "recommendation_text": "",
                         "href": f"/deals?buyer={quote(cp, safe='')}"})
    return {"rows": rows, "empty_text": t(c.lang, "No deals are open.", "目前没有进行中的交易。"), "href": "/deals"}


# ---------------------------------------------------------------- the funding line


def _quote_of(c: HomeRead) -> Any | None:
    """The newest funding decision that ran: its stored quote and the lots its operations created."""
    ctx = c.record
    if ctx is None:
        return None
    ran = [ds for ds, _ in ctx.states().values() if ds.family == "FUNDING" and ds.quote is not None and ds.lots]
    return max(ran, key=lambda ds: ds.updated_seq) if ran else None


def _repay_clause(c: HomeRead, lot: Any) -> str:
    """", repaid from Foshan's receipt in 32 days": the receipt that repays an advance, or the day the trajectory repays a draw."""
    r = next((x for x in c.state.receivables if x.id == lot.receivable_id), None) if lot.receivable_id else None
    if r is not None:
        who = buyer_short(party_name(c.state, r.counterparty_id), c.lang)
        if r.due_day < c.today:  # the receipt that was to repay it is late
            n = c.today - r.due_day
            return t(c.lang, f", to be repaid from {who}'s payment, which is {n} {'day' if n == 1 else 'days'} late",
                     f"，将由{who}的回款偿还，该笔款项已逾期 {n} 天")
        when = when_text(r.due_day, c.today, c.lang)
        return t(c.lang, f", repaid from {who}'s receipt {when}", f"，由{who}的回款偿还（{when}）")
    for d in c.traj.days:
        if d.day >= c.today and any(e.kind == LedgerEventKind.REPAYMENT and e.ref == lot.facility_id for e in d.events):
            when = when_text(d.day, c.today, c.lang)
            return t(c.lang, f", repaid {when}", f"，将于{when}偿还")
    return ""


def funding_line(c: HomeRead) -> dict[str, Any]:
    ds = _quote_of(c)
    q = ds.quote if ds is not None else None
    lots = list(ds.lots) if ds is not None else []
    lang = c.lang
    if lots:
        if any(not lot.settled for lot in lots):
            state = "arranged"
        elif any(lot.remaining_fen > 0 for lot in lots):
            state = "landed"
        else:
            state = "repaid"
    else:
        state = "none"
    action = c.action if state == "none" else None
    out: dict[str, Any] = {"state": state, "text": "", "cost_leg_display": None, "cost_leg_label": None, "cost_total_display": None,
                           "cost_total_label": None, "authority_text": None}
    live = [lot for lot in lots if lot.remaining_fen > 0 and (not lot.settled if state == "arranged" else True)]
    clauses = []
    for lot in live:
        amount, kind = _short(lot.remaining_fen), _lot_kind(lot, lang, c.state)
        if state == "arranged":
            when = when_text(lot.arrival_day, c.today, lang)
            clauses.append(t(lang, f"{amount} of {kind} expected {when}", f"预计{when}到账 {amount} {kind}") + _repay_clause(c, lot))
        elif lot.receivable_id:  # a landed advance is repaid from its receipt; a landed draw is in the cash already
            clauses.append(t(lang, f"{amount} of {kind} is in your cash", f"{amount} {kind}已到账") + _repay_clause(c, lot))
    if state == "arranged":
        out["text"] = t(lang, f"Funding arranged · {' and '.join(clauses)}.", f"已安排融资 · {'，'.join(clauses)}。")
    elif state == "landed":
        out["text"] = t(lang, f"Funding landed · {' and '.join(clauses) or 'the funds are in your cash'}.",
                        f"融资已到账 · {'，'.join(clauses) or '资金已到账'}。")
    elif state == "repaid":
        out["text"] = t(lang, "Funding repaid · the plan's financing has been paid back.", "融资已还清 · 方案中的融资已偿还。")
    else:
        if action is not None and action.get("kind") == "RESERVE_BREACH_AHEAD":
            out["text"] = (t(lang, "No funding is arranged yet. The plan waits for your approval.", "尚未安排融资。方案正等待您批准。")
                           if action.get("pending_approval_id")
                           else t(lang, "No funding is arranged yet. FLOW has a plan ready.", "尚未安排融资。FLOW 已准备好方案。"))
        else:
            out["text"] = t(lang, "No funding is arranged.", "目前没有安排融资。")
    # the cost split: the router's own cost lines (the stored quote of the plan that ran, or the plan that is ready), never summed here
    legs: list[tuple[str, int, int | None, bool]] = []  # (kind, amount, cost, landed)
    total: int | None = None
    if q is not None:
        def landed(op: str) -> bool:
            return any(lot.settled for lot in lots if lot.id == op or lot.id.startswith(op + "#"))

        legs = [(leg.kind, leg.amount_fen, leg.cost_fen, landed(leg.op_id)) for leg in q.legs]
        total = q.total_cost_fen
        out["authority_text"] = (t(lang, "Within your signed limits; nothing for you to do.", "在您签署的授权内，您无需做任何事。")
                                 if not q.needs_owner else
                                 t(lang, "You approved this plan: it needed your approval because of its cost.", "您已批准此方案：其成本需要您批准。"))
    elif action is not None and action.get("kind") == "RESERVE_BREACH_AHEAD":
        legs = [(leg["operation_kind"], leg["amount_fen"] or 0, leg["cost_fen"], False) for leg in action["legs"]]
        total = None
        out["cost_total_display"] = action.get("cost_total_display")
        out["authority_text"] = action.get("authority_text")
    if legs:
        at = next((i for i, leg in enumerate(legs) if leg[0] == "SUBMIT_INVOICE_FOR_FINANCING"), None)
        fin = legs[at] if at is not None else None
        others = [leg for i, leg in enumerate(legs) if i != at]
        if total is not None:
            out["cost_total_display"] = fmt_yuan(total)
        if fin is not None and fin[2] is not None:
            out["cost_leg_display"] = fmt_yuan(fin[2])
            out["cost_leg_label"] = t(lang, "the invoice-financing leg", "发票融资部分")
        draws = [x for x in others if x[0] == "DRAW_FACILITY"]
        if len(others) == 1 and draws:
            done = draws[0][3]
            amount = _short(draws[0][1])
            out["cost_total_label"] = (t(lang, f"the whole plan, with the {amount} credit-line draw already made",
                                         f"整个方案，其中 {amount} 的信用额度提款已完成") if done
                                       else t(lang, f"the whole plan, including the {amount} credit-line draw",
                                              f"整个方案，包含 {amount} 的信用额度提款"))
        else:
            out["cost_total_label"] = t(lang, "the whole plan", "整个方案")
    return out


# ---------------------------------------------------------------- the attention queue


def _item(key: str, kind: str, eyebrow: str, title: str, facts: list[dict[str, Any]], primary: tuple[str, str],
          secondary: tuple[str, str]) -> dict[str, Any]:
    return {"key": key, "kind": kind, "eyebrow": eyebrow, "title": title, "facts": facts,
            "primary": {"label": primary[0], "href": primary[1]}, "secondary": {"label": secondary[0], "href": secondary[1]}}


def _fact(label: str, value: str, tone: str = "neutral") -> dict[str, Any]:
    return {"label": label, "value": value, "tone": tone}


def _exposure_fact(c: HomeRead, buyer_id: str) -> dict[str, Any] | None:
    """"Foshan is 100% of what you are owed", when the exposure layer is on and the buyer is a material share of what is owed."""
    if not _exposure_on(c.rt):
        return None
    try:
        exposure = importlib.import_module("app.strategy.exposure")
        concentration = importlib.import_module("app.strategy.concentration").concentration
        inputs = importlib.import_module("app.strategy.inputs").inputs_from_store(c.rt.store)
        flag = exposure._flag(concentration(c.books, buyer_id, c.today, inputs, lang=c.lang), c.lang)
    except ImportError:
        log.warning("the exposure flag is on but the exposure layer is not on this branch; the home omits the concentration")
        return None
    except Exception:
        log.exception("the buyer's concentration could not be read for the home")
        return None
    return _fact(t(c.lang, "Exposure", "风险敞口"), flag["text"], "warn") if flag.get("material") and flag.get("text") else None


def _deal_item(c: HomeRead, d: _Deal, count: int) -> dict[str, Any]:
    lang = c.lang
    name = buyer_short(d.buyer, lang)
    asks = _asks(d.offer, lang, False, c.state, c.today) if d.offer is not None else ""
    _, advice = _recommendation(d, lang)
    title = (t(lang, f"{name} asked for {asks}. {advice}", f"{name}要求{asks}。{advice}") if asks
             else t(lang, f"{name} sent an offer. {advice}", f"{name}发来一份报价。{advice}"))
    facts: list[dict[str, Any]] = []
    p = d.pick
    if p is not None and p.get("kind") == "reply":
        cost = f"{p.get('cost_display')}{t(lang, ', ', '，')}{p.get('cost_note')}" if p.get("cost_note") else str(p.get("cost_display"))
        facts.append(_fact(t(lang, f"Cost of {p.get('label')}", f"{p.get('label')}的成本"), cost))
    view = d.view
    if view.get("verdict_id") and view.get("limit_fen") is not None:
        limit = whole(int(view["limit_fen"]))
        facts.append(_fact(t(lang, "As asked", "按对方要求"),
                           t(lang, f"over your {limit} limit", f"超出您 {limit} 的上限") if view.get("over_limit")
                           else t(lang, f"within your {limit} limit", f"在您 {limit} 的上限内"), "warn" if view.get("over_limit") else "ok"))
    exposed = _exposure_fact(c, d.buyer_id)
    if exposed is not None:
        facts.append(exposed)
    reply = p is not None and p.get("kind") == "reply"
    return _item(f"deal:{d.offer_id}", "deal",
                 t(lang, f"{count} deal needs your response" if count == 1 else f"{count} deals need your response",
                   f"{count} 项交易需要您答复"),
                 title, facts,
                 (t(lang, "Review the counter", "查看还价") if reply else t(lang, "Review the offer", "查看报价"),
                  f"/deals?buyer={quote(d.buyer_id, safe='')}"),
                 (t(lang, "Why this?", "为什么？"), _link(deal_id(d.offer_id))))


def _leg_fact(c: HomeRead, operation_kind: str, facility: str, amount_fen: int, when: str, state: State) -> dict[str, Any]:
    """"¥150k today (planned)": one leg of the plan, its amount, when it lands, and the state word (`financing_words`)."""
    lang = c.lang
    name = {"DRAW_FACILITY": t(lang, "Credit line draw", "信用额度提款"),
            "SUBMIT_INVOICE_FOR_FINANCING": t(lang, "Invoice financing", "发票融资")}.get(operation_kind, _source(facility, lang))
    word = state_word(lang, state)
    return _fact(name, t(lang, f"{_short(amount_fen)} {when} ({word})", f"{_short(amount_fen)}，{when}（{word}）"))


def _funding_item(c: HomeRead) -> dict[str, Any] | None:
    a = c.action
    if a is None or a["kind"] != "RESERVE_BREACH_AHEAD" or a.get("pending_approval_id"):
        return None  # a plan waiting for the owner is the approval's item
    lang = c.lang
    receive = a.get("receive_short")
    title = c.headline + _sp(c.lang) + (t(lang, f"FLOW recommends securing {receive} of funding.", f"FLOW 建议筹措 {receive} 资金。") if receive
                                else t(lang, "FLOW has a plan ready.", "FLOW 已准备好方案。"))
    facts = [_fact(t(lang, "Estimated cost", "预计成本"), str(a.get("cost_total_display")), "neutral")] if a.get("cost_total_display") else []
    if a.get("lands_when"):  # the plain landing fact (the page's `next-action-lands`), then one fact per leg that lands
        facts.append(_fact(t(lang, "Funds arrive", "资金到账"), str(a["lands_when"]), "neutral"))
    landing = [leg for leg in a["legs"] if leg["operation_kind"] in _LANDING_KINDS and leg.get("lands_when") and leg.get("amount_fen")]
    for leg in landing[:MAX_LEG_FACTS]:  # what lands when, in the state word the financing is said in everywhere
        facts.append(_leg_fact(c, leg["operation_kind"], leg["facility_name"], leg["amount_fen"], leg["lands_when"],
                               state_of(None, planned=True)))
    facts.append(_fact(t(lang, "Authority", "授权"),
                       t(lang, "needs your approval", "需要您批准") if a["needs_owner"] else t(lang, "within your signed limits", "在您签署的授权内"),
                       "warn" if a["needs_owner"] else "ok"))
    return _item(f"funding:{a['alert_id']}", "funding", t(lang, "Cash needs a decision", "现金需要决定"), title, facts,
                 (t(lang, "Review the plan", "查看方案"), "/cash#cash-options"), (t(lang, "Why this?", "为什么？"), "/cash#cash-options"))


def _approval_items(c: HomeRead) -> list[dict[str, Any]]:
    lang = c.lang
    out = []
    n = len(c.queue)
    for card in c.queue:
        facts = []
        if card.get("cost_display"):
            facts.append(_fact(t(lang, "Estimated cost", "预计成本"), str(card["cost_display"])))
        if card.get("lands_when"):
            facts.append(_fact(t(lang, "Funds arrive", "资金到账"), str(card["lands_when"])))
        if card.get("protects"):
            facts.append(_fact(t(lang, "If you approve", "批准后"), str(card["protects"]), "ok"))
        out.append(_item(f"approval:{card['id']}", "approval",
                         t(lang, f"{n} approval needs you" if n == 1 else f"{n} approvals need you", f"{n} 项批准等待您处理"),
                         str(card.get("headline") or card.get("what") or ""), facts,
                         (t(lang, "Review the approval", "查看批准事项"), f"/approvals#approval-{card['id']}"),
                         (t(lang, "Why this?", "为什么？"), f"/approvals#approval-{card['id']}")))
    return out


def _collection_items(c: HomeRead) -> list[dict[str, Any]]:
    lang = c.lang
    late = sorted(c.receivables.get("past_due") or [], key=lambda r: (-r["days_late"], -r["face_fen"], r["receivable_id"]))
    seen: set[str] = set()
    rows = []
    for r in late:
        if r["buyer_id"] not in seen:
            seen.add(r["buyer_id"])
            rows.append(r)
    out = []
    for r in rows:
        n, name = r["days_late"], buyer_short(r["buyer_name"], lang)
        title = t(lang, f"{name} is {n} {'day' if n == 1 else 'days'} late on {_short(r['face_fen'])}.",
                  f"{name}的 {_short(r['face_fen'])} 已逾期 {n} 天。")
        facts = [_fact(t(lang, "Overdue", "逾期金额"), _short(r["face_fen"]), "bad"),
                 _fact(t(lang, "Late by", "已逾期"), t(lang, f"{n} {'day' if n == 1 else 'days'}", f"{n} 天"), "bad")]
        out.append(_item(f"collection:{r['buyer_id']}", "collection",
                         t(lang, f"{len(rows)} customer is late" if len(rows) == 1 else f"{len(rows)} customers are late",
                           f"{len(rows)} 位客户逾期"), title, facts,
                         (t(lang, "Chase the payment", "催收款项"), "/receivables"), (t(lang, "Why this?", "为什么？"), "/receivables")))
    return out


def _landing_items(c: HomeRead) -> list[dict[str, Any]]:
    lang = c.lang
    why = next((f"/decisions/{quote(d['id'], safe='')}" for d in c.open_decisions
                if d.get("family") == "FUNDING" and d.get("state") == FundingState.SETTLEMENT_PENDING.value), "/activity")
    lots = _pending_lots(c.state, c.today)
    out = []
    for lot in lots:
        when, amount = when_text(lot.arrival_day, c.today, lang), _short(lot.remaining_fen)
        source = _source(facility_name(c.state, lot.facility_id), lang)
        title = t(lang, f"{amount} of funding from {source} arrives {when}.", f"来自{source}的 {amount} 资金将于{when}到账。")
        facts = [_leg_fact(c, "SUBMIT_INVOICE_FOR_FINANCING" if lot.receivable_id else "DRAW_FACILITY", source, lot.remaining_fen, when,
                           state_of(lot)), _fact(t(lang, "From", "来源"), source)]
        out.append(_item(f"landing:{lot.id}", "landing",
                         t(lang, "1 funding landing is pending" if len(lots) == 1 else f"{len(lots)} funding landings are pending",
                           f"{len(lots)} 笔融资待到账"), title, facts,
                         (t(lang, "See the funding", "查看融资"), "/cash"), (t(lang, "Why this?", "为什么？"), why)))
    return out


def attention(c: HomeRead, deals: list[_Deal]) -> dict[str, Any]:
    """One primary at a time, ranked by the review's table: cash unsafe with a runnable cure, a deal waiting for the owner's reply, an owner
    approval, a customer overdue, a funding landing; nothing when all is well."""
    waiting = [d for d in deals if d.state in (DealState.RECEIVED, DealState.RESPONSE_READY)]
    items: list[dict[str, Any]] = []
    funding = _funding_item(c)
    if funding is not None:
        items.append(funding)
    items += [_deal_item(c, d, len(waiting)) for d in waiting]
    items += _approval_items(c)
    items += _collection_items(c)
    items += _landing_items(c)
    return {"items": items, "primary_key": items[0]["key"] if items else None,
            "none_text": t(c.lang, "No urgent action required.", "没有需要紧急处理的事项。")}


def stress_buyer_of(deals: list[_Deal], att: dict[str, Any]) -> str | None:
    """The buyer the Home's late-payment test is about: the buyer of the primary deal, else the next receipt's."""
    primary = att["primary_key"]
    return next((d.buyer_id for d in deals if f"deal:{d.offer_id}" == primary), None) or next(
        (d.buyer_id for d in deals if d.state in (DealState.RECEIVED, DealState.RESPONSE_READY)), None)


# ---------------------------------------------------------------- the other cards


def _financing_note(c: HomeRead, nxt: dict[str, Any]) -> str | None:
    """What the next receipt will do when an advance is open on that invoice: the same words as the rail's event for that day, from the
    trajectory's events on the due day."""
    r = next((x for x in c.state.receivables if x.id == nxt["receivable_id"]), None)
    if r is None or r.status != "FINANCED" or r.advance_fen <= 0:
        return None
    day = next((d for d in c.traj.days if d.day == nxt["due_day"]), None)
    receipt = next((e for e in day.events if e.kind in _RECEIPTS and e.ref == r.id), None) if day is not None else None
    return receipt_words(c, day, receipt, c.lang) if receipt is not None else None


def receivables_card(c: HomeRead) -> dict[str, Any]:
    r = c.receivables
    nxt = r.get("next_receipt")
    lang = c.lang
    next_text = None
    if nxt is not None:
        who = buyer_short(nxt["buyer_name"], lang)
        next_text = t(lang, f"{who}, {_short(nxt['face_fen'])} {nxt['due_when']}", f"{who}，{nxt['due_when']} {_short(nxt['face_fen'])}")
    return {"outstanding_short": _short(r["open_total_fen"]) if r.get("open_total_fen") is not None else None,
            "overdue_short": _short(r["overdue_total_fen"]) if r.get("overdue_total_fen") is not None else None,
            "next_text": next_text, "financing_note": _financing_note(c, nxt) if nxt is not None else None, "href": "/receivables"}


def changes_card(c: HomeRead) -> dict[str, Any]:
    rows = [{"id": x["id"], "when": x["when"], "text": x["event_text"] or x["text"], "kind": x["kind"]}
            for x in c.changes if not x.get("superseded_by")][:MAX_CHANGES]
    return {"rows": rows, "empty_text": t(c.lang, "Nothing has changed lately.", "最近没有变化。"), "href": "/activity"}


def build(c: HomeRead) -> dict[str, Any]:
    """Everything the hybrid adds to `GET /home`: the cash block's new fields and the top-level blocks. When the deals could not be read
    (the decision record, which `partial` names) the queue cannot say "No urgent action required" and the deals card is absent."""
    deals = _deals(c)
    att = attention(c, deals or [])
    if deals is None:
        att = {**att, "none_text": None, "incomplete": True}
    return {"cash": cash_block(c, stress_buyer_of(deals or [], att) or _stress_buyer(c, None), deals), "attention": att,
            "funding_line": funding_line(c), "deals_card": deals_card(c, deals) if deals is not None else None,
            "receivables_card": receivables_card(c), "changes_card": changes_card(c)}
