"""Marginal impact: what the router, the trajectory and the alerts say about two sets of books, and the scenarios
that produce the second set (docs/STRATEGY_MVP_BRIEF.md section 3).

Read-only: every state passed to the kernel is a `model_copy`, nothing is stored, nothing is booked. A receipt that
"arrives" is a labelled projection (`ScenarioState.hypothetical`), never a bank receipt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.alerts import alerts
from app.api.presentation import party_name, t, when_text
from app.books import Books, binds, current_books
from app.domain.models import (
    CashFlow,
    Commitment,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FlowKind,
    FundingLot,
    LedgerEventKind,
    Mandate,
    Mode,
    Obligation,
    Receivable,
)
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.financial import lots as funding_lots
from app.financial import project
from app.financial.invoices import InvoiceRef, issue_terms
from app.funding import plan
from app.funding.router import shared_runs
from app.strategy.capacity import Package, books_with, resolve_package
from app.strategy.types import MarginalImpact, ScenarioState, StressRow
from app.strategy.words import invoice_labels

_OPEN = ("OPEN", "FINANCED")


# ---------------------------------------------------------------- scenarios


def _find(state: FinancialState, receivable_id: str) -> Receivable:
    r = next((x for x in state.receivables if x.id == receivable_id), None)
    if r is None:
        raise ValueError(f"receivable {receivable_id} is not on the books")
    if r.status not in _OPEN or r.outstanding_fen <= 0:
        raise ValueError(f"receivable {receivable_id} is {r.status} with {fmt_yuan(r.outstanding_fen)} outstanding: "
                         f"nothing is left to collect")
    return r


def _who(state: FinancialState, r: Receivable) -> str:
    return next((c.name for c in state.counterparties if c.id == r.counterparty_id), r.counterparty_id)


def _received_today(state: FinancialState, r: Receivable) -> FinancialState:
    """The outstanding face credited to cash and the receivable SETTLED (`settled_fen = face_fen`). A FINANCED
    receivable pays the lender first, as the executor's receipt does (ADR-0010): the advance lot is cleared with its
    charges out of the receipt, the facility's drawn balance falls with it and cash gets the rest."""
    state = funding_lots.ensure_lots(state)
    amount = r.outstanding_fen
    cash = state.cash_fen + amount
    facilities, lots = state.facilities, list(state.lots)
    if r.status == "FINANCED":
        lot = next((x for x in state.lots if x.receivable_id == r.id and x.remaining_fen > 0), None)
        if lot is None:
            raise ValueError(f"no advance on record for financed {r.id}")
        f = next(x for x in state.facilities if x.id == lot.facility_id)
        still: FundingLot | None = None
        if lot.settled:
            applied = funding_lots.apply_receipt(f, lot, amount, state.as_of_day, True)
            cash -= applied.applied  # the lender is paid first, from the receipt only
            still = applied.lot
        # an advance that has not landed is cancelled by a receipt that settles the invoice: nothing is charged
        lots = [x for x in lots if x.id != lot.id] + ([still] if still is not None else [])
        drawn = f.drawn_fen - lot.remaining_fen + (still.remaining_fen if still is not None else 0)
        facilities = [x.model_copy(update={"drawn_fen": drawn}) if x.id == f.id else x for x in state.facilities]
    paid = r.model_copy(update={"status": "SETTLED", "settled_fen": r.face_fen, "advance_fen": 0,
                                "advance_facility_id": None})
    receivables = [paid if x.id == r.id else x for x in state.receivables]
    return state.model_copy(update={"cash_fen": cash, "receivables": receivables, "facilities": facilities,
                                    "lots": lots})


def _received_on(state: FinancialState, r: Receivable, on_day: int) -> FinancialState:
    """The receipt moved to `on_day` the way the collections spike moved it: the receivable's terms on the COPY end on
    that day, so the engine posts the RECEIPT there and the invoice stays financeable until then. The books' own
    receivable, the commitments and the contract are untouched. (An `IMMEDIATE_DISCOUNT` at 0 bp dates the receipt
    too, but it marks the invoice settled early and the router then cannot finance it: it prices another source.)"""
    receivables = [x.model_copy(update={"terms_days": on_day - x.issue_day}) if x.id == r.id else x
                   for x in state.receivables]
    return state.model_copy(update={"receivables": receivables})


def scenario_received(books: Books, receivable_id: str, on_day: int, *, label: str | None = None) -> ScenarioState:
    """The receivable's outstanding face received on `on_day` (a labelled projection, not a bank receipt).

    Today: cash is credited and the receivable settled. A later day, up to its due day: the receipt is moved on the
    copy (`_received_on`). `ValueError` for an unknown or settled receivable, a day before today, an overdue
    receivable asked for any day but today, a day after the due day, and a financed receivable asked for any day but
    today (the lender is paid first, and only that case is modelled)."""
    state = books.state
    today = state.as_of_day
    r = _find(state, receivable_id)
    if on_day < today:
        raise ValueError(f"day {on_day} is before today (day {today})")
    if on_day == today:
        scenario = _received_today(state, r)
    elif r.due_day < today:
        raise ValueError(f"{receivable_id} is overdue (due day {r.due_day}): only today can be asked for")
    elif r.status == "FINANCED":
        raise ValueError(f"{receivable_id} is financed: only a receipt today is modelled (the lender is paid first)")
    elif on_day > r.due_day:
        raise ValueError(f"day {on_day} is after {receivable_id}'s due day {r.due_day}: a later receipt is not modelled")
    else:
        scenario = _received_on(state, r, on_day)
    when = when_text(on_day, today, "en")
    return ScenarioState(
        state=scenario, label=label or f"{receivable_id} received {when}",
        assumption=f"assumes the {fmt_yuan(r.outstanding_fen)} from {_who(state, r)} arrives {when}",
        source_state_version=state.state_version, day=today)


def scenario_inflow(books: Books, amount_fen: int, on_day: int, *, outflow_day: int | None = None) -> ScenarioState:
    """One confirmed `CashFlow` of `amount_fen` on `on_day` appended to the state's flows. With `outflow_day` the same
    amount also leaves on that day (the pair that moves money earlier, brief section 5.1)."""
    state = books.state
    today = state.as_of_day
    if amount_fen <= 0:
        raise ValueError("an inflow must be positive")
    if on_day < today or (outflow_day is not None and outflow_day < today):
        raise ValueError(f"a flow cannot be dated before today (day {today})")
    flows = [CashFlow(id=f"SCENARIO-INFLOW-{on_day}", day=on_day, amount_fen=amount_fen, kind=FlowKind.OTHER,
                      label="hypothetical inflow", confirmed=True)]
    label = f"{fmt_yuan(amount_fen)} arrives on day {on_day}"
    assumption = f"assumes {fmt_yuan(amount_fen)} arrives {when_text(on_day, today, 'en')}"
    if outflow_day is not None:
        flows.append(CashFlow(id=f"SCENARIO-OUTFLOW-{outflow_day}", day=outflow_day, amount_fen=-amount_fen,
                              kind=FlowKind.OTHER, label="hypothetical outflow", confirmed=True))
        label += f" and leaves on day {outflow_day}"
        assumption += f" and leaves {when_text(outflow_day, today, 'en')}"
    return ScenarioState(
        state=state.model_copy(update={"flows": [*state.flows, *flows]}), label=label, assumption=assumption,
        source_state_version=state.state_version, day=today)


# ---------------------------------------------------------------- marginal impact


@dataclass(frozen=True)
class Reading:
    cost_fen: int
    need_fen: int
    needs_owner: bool
    executable_now: bool
    first_breach_day: int | None
    breach_days: int
    lowest_headroom_fen: int
    budget_used_fen: int
    alert_codes: tuple[str, ...]
    plan_admissible: bool = True  # the router found a plan that restores the reserve (False: no committed plan covers it)
    lowest_cash_fen: int = 0  # the unfunded trajectory's lowest closing from today, and the first day it is reached
    lowest_day: int = 0


def _read_kernel(state: FinancialState, obs: list[Obligation], mandate: Mandate) -> Reading:
    """The router's committed plan and the CONSERVATIVE unfunded trajectory of one set of books (no alerts: they need the
    ledger store). The one place these figures are taken, for `read_books` and the stress."""
    p = plan(state, obs, mandate)
    tr = project(state, obs, [], Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    floor = mandate.min_cash_fen
    live = [d for d in tr.days if d.day >= state.as_of_day]
    booked = sum(fc.value_fen for fc in state.forward_concessions)
    lowest = min(live, key=lambda d: (d.closing_fen, d.day), default=None)
    return Reading(
        cost_fen=p.total_cost_fen, need_fen=p.need_fen, needs_owner=p.needs_owner_approval,
        executable_now=p.executable_now, first_breach_day=tr.first_breach_day,
        breach_days=sum(1 for d in live if d.closing_fen < floor),
        lowest_headroom_fen=min((d.closing_fen - floor for d in live), default=0),
        budget_used_fen=max([d.forward_concession_fen for d in tr.days] + [booked]),
        alert_codes=(), plan_admissible=p.admissible,
        lowest_cash_fen=lowest.closing_fen if lowest is not None else 0,
        lowest_day=lowest.day if lowest is not None else state.as_of_day)


def read_books(side: Books | ScenarioState, mandate: Mandate, store: LedgerStore, day: int) -> Reading:
    """What the router, the trajectory and the alerts say about one set of books. Pure in the books, the mandate, the
    store's commitments and the day, so a caller that subtracts many scenarios from the same books reads those once."""
    if isinstance(side, Books):
        state, obs = side.state, side.with_([])
    else:  # a scenario's live obligations are those of the stored commitments that still bind to its state
        state = side.state
        obs = current_books(state, store.commitments()).with_([])
    reading = _read_kernel(state, obs, mandate)
    found = alerts(state, mandate, store, day)
    return replace(reading, alert_codes=tuple(dict.fromkeys(a.kind.value for a in found)))


def marginal_impact(before: Books | ScenarioState, after: Books | ScenarioState, mandate: Mandate, *,
                    store: LedgerStore, day: int, label: str = "", before_reading: Reading | None = None) -> MarginalImpact:
    """What changes between two books: the COMMITTED plan, the CONSERVATIVE trajectory and the alerts of each,
    subtracted (after minus before). `posted_cost_delta_fen` is `FundingPlan.total_cost_fen` after less before: a
    negative figure is a saving, a positive one a cost, kept as it is. The alerts read the state they are given and
    the `store` only for the commitments, expiries and repayments (a scenario's state need not be the store's).
    `before_reading` is `read_books(before, ...)` taken earlier, for a caller that measures many scenarios against the same
    books (the figures are the same whether it is given or not)."""
    with shared_runs():
        b = before_reading if before_reading is not None else read_books(before, mandate, store, day)
        a = read_books(after, mandate, store, day)
    return MarginalImpact(
        label=label,
        need_delta_fen=a.need_fen - b.need_fen,
        posted_cost_delta_fen=a.cost_fen - b.cost_fen,
        first_breach_before=b.first_breach_day, first_breach_after=a.first_breach_day,
        lowest_headroom_delta_fen=a.lowest_headroom_fen - b.lowest_headroom_fen,
        budget_used_delta_fen=a.budget_used_fen - b.budget_used_fen,
        breach_days_removed=b.breach_days - a.breach_days,
        alerts_removed=[c for c in b.alert_codes if c not in a.alert_codes],
        alerts_added=[c for c in a.alert_codes if c not in b.alert_codes],
        before_needs_owner=b.needs_owner, after_needs_owner=a.needs_owner,
        before_executable_now=b.executable_now, after_executable_now=a.executable_now,
        before_cost_fen=b.cost_fen, after_cost_fen=a.cost_fen,
        before_need_fen=b.need_fen, after_need_fen=a.need_fen)


# ---------------------------------------------------------------- the late-payment stress (brief G.3)

DEFAULT_HORIZON_DAYS = 120
LATE_REACH_DAYS = 366  # receipts dated this far past the horizon are moved too, so a longer plan search still sees them
_RECEIPTS = (LedgerEventKind.RECEIPT, LedgerEventKind.EARLY_RECEIPT)


def _template_terms(state: FinancialState, buyer_id: str, rid: str) -> int | None:
    """The terms in force for a recurring invoice the trajectory dated no receipt for (settled early in full): the
    template's terms with the accepted adjustments written on, as the clock issues it."""
    issue = int(rid.rsplit(":", 1)[1])
    for ri in state.recurring_invoices:
        if ri.counterparty_id == buyer_id and ri.every_days > 0 and issue >= ri.next_issue_day \
                and (issue - ri.next_issue_day) % ri.every_days == 0:
            terms = issue_terms(state, InvoiceRef(rid, buyer_id, issue), ri.face_fen, ri.terms_days)["terms_days"]
            assert isinstance(terms, int)
            return terms
    return None


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _ids_text(ids: Sequence[str]) -> str:
    return ", ".join(ids)


def scenario_paid_late(books: Books, buyer_id: str, delay_days: int, day: int, *,
                       horizon_days: int = DEFAULT_HORIZON_DAYS, lang: str = "en") -> ScenarioState:
    """The buyer pays every invoice `delay_days` late (a test, not a forecast): a labelled copy of the books.

    A new transform, separate from `scenario_received` (whose refusal of a late receipt stands). It never changes the
    contractual terms of a receivable on the copy (`_received_on` does; that would keep an invoice financeable past its
    due day). Instead each invoice the buyer still owes is taken off the copy and replaced by ONE confirmed `CashFlow` of
    its whole outstanding on its due day in force + `delay_days`, so a receipt moves exactly once and is never
    duplicated:

    - the open, confirmed invoices of the buyer, and every recurring invoice it is billed inside the horizon (the template
      is taken off the copy), at the due day the CONSERVATIVE trajectory dates them (the terms and prices in force);
    - an invoice that is already past due is not moved and not re-added: the conservative projection counts nothing from
      it, and a stress never adds cash the books do not count;
    - a live early-payment agreement on a moved invoice is treated as lapsed on the copy (the whole outstanding moves, no
      discount; the agreement no longer binds and `read_books` leaves it out). At a delay of 0 there is no lateness to
      lapse it: the agreement stands and the copy reproduces the books exactly;
    - the buyer's own facility (lender = the buyer) is taken off the copy: it needs the buyer's agreement to pay early;
    - a FINANCED invoice is not moved and is named ("its delay is not modelled"); with nothing else to move the stress is
      refused (`ValueError`), as is an unknown buyer, a negative delay or a buyer with nothing to pay.

    The copy cannot be financed on the moved invoices, which understates what could be financed by at most the advance
    rate times what is outstanding: the assumption says so."""
    state, today = books.state, books.state.as_of_day
    if delay_days < 0:
        raise ValueError("a delay cannot be negative")
    buyer = next((c for c in state.counterparties if c.id == buyer_id), None)
    if buyer is None:
        raise ValueError(f"{buyer_id} is not on the books")
    name = party_name(state, buyer_id)
    issued = {r.id: r for r in state.receivables if r.counterparty_id == buyer_id}
    financed = [r.id for r in issued.values() if r.status == "FINANCED" and r.outstanding_fen > 0]
    overdue = [r.id for r in issued.values() if r.status == "OPEN" and r.outstanding_fen > 0 and r.due_day < today]

    ahead = project(state, books.with_([]), [], Mode.CONSERVATIVE, horizon_days + LATE_REACH_DAYS)
    owed: dict[str, int] = {}
    due: dict[str, int] = {}
    early: set[str] = set()  # invoices with a live early-payment agreement
    for p in ahead.days:
        for e in p.events:
            if e.kind not in _RECEIPTS or e.ref is None or e.amount_fen <= 0:
                continue
            if e.ref in issued:
                if issued[e.ref].status != "OPEN":
                    continue
            elif not e.ref.startswith(f"RI:{buyer_id}:"):
                continue
            owed[e.ref] = owed.get(e.ref, 0) + e.amount_fen
            if e.kind == LedgerEventKind.RECEIPT:
                due[e.ref] = p.day
            else:
                early.add(e.ref)
    agreed = {rid for rid in owed if rid in early}
    for rid in owed:  # settled early in full: no receipt on its due day, so its due day in force is read from the books
        if rid not in due:
            if rid in issued:
                due[rid] = issued[rid].due_day
            else:
                terms = _template_terms(state, buyer_id, rid)
                if terms is None:
                    raise ValueError(f"{rid} cannot be dated: no recurring invoice of {buyer_id} issues it")
                due[rid] = int(rid.rsplit(":", 1)[1]) + terms
    if not owed:
        why = f" {_ids_text(financed)} is financed; its delay is not modelled." if financed else ""
        raise ValueError(f"{name} has no open invoice or recurring invoice to pay late.{why}")
    if delay_days == 0:  # no lateness: an agreement to pay early is honoured, so the copy reproduces the books exactly
        for rid in agreed & issued.keys():  # (one on an invoice not issued yet lapses with the template, at any delay)
            del owed[rid]

    moved = sorted(owed, key=lambda r: (due[r], r))
    flows = [CashFlow(id=f"LATE:{rid}", day=due[rid] + delay_days, amount_fen=owed[rid], kind=FlowKind.RECEIVABLE,
                      label=f"Receipt of {rid} from {name}, paid {delay_days} days late (a test)",
                      counterparty_id=buyer_id, confirmed=True) for rid in moved]
    taken_off = [f for f in state.facilities if f.lender_id == buyer_id]
    gone = {f.id for f in taken_off}
    scenario = state.model_copy(update={
        "receivables": [r for r in state.receivables if r.id not in owed],
        "recurring_invoices": [ri for ri in state.recurring_invoices if ri.counterparty_id != buyer_id],
        "facilities": [f for f in state.facilities if f.id not in gone],
        "lots": [lot for lot in state.lots if lot.facility_id not in gone],
        "flows": [*state.flows, *flows]})

    end = today + horizon_days
    past = [f for f in flows if f.day > end >= f.day - delay_days]  # the delay pushes it out of the horizon
    rates = [f.advance_rate_bp or 10_000 for f in state.facilities
             if f.kind == FacilityKind.INVOICE_FINANCING and f.status == FacilityStatus.COMMITTED and f.owner_approved]
    inside = sum(owed[rid] for rid in moved if due[rid] <= end)  # what the horizon would have collected
    understated = max((inside * r // 10_000 for r in rates), default=0)
    on_time = delay_days == 0
    head = t(lang, f"If {name} paid every invoice on its due day (a test: the books as they stand)." if on_time else
             f"If {name} paid every invoice {delay_days} days late (a test, not a forecast).",
             f"如果 {name} 的每张发票都按到期日付款（这是测试：账面就是现在的样子）。" if on_time else
             f"如果 {name} 的每张发票都晚付 {delay_days} 天（这是压力测试，不是预测）。")
    notes = []
    if financed:
        notes.append(t(lang, f"{_capital(invoice_labels(state, financed, today, 'en'))} {'is' if len(financed) == 1 else 'are'} financed; "
                             f"its delay is not modelled.",
                       f"{invoice_labels(state, financed, today, 'zh')} 已用于融资，其延期未纳入测算。"))
    if overdue:
        notes.append(t(lang, f"{_capital(invoice_labels(state, overdue, today, 'en'))} {'is' if len(overdue) == 1 else 'are'} already past due "
                             f"and {'stays' if len(overdue) == 1 else 'stay'} as the books count it.",
                       f"{invoice_labels(state, overdue, today, 'zh')} 已经逾期，保持账面原有的计算方式。"))
    if taken_off:
        notes.append(t(lang, f"{_ids_text([f.name for f in taken_off])} {'is' if len(taken_off) == 1 else 'are'} taken out: "
                             f"{'it needs' if len(taken_off) == 1 else 'they need'} {name}'s agreement.",
                       f"已去掉{_ids_text([f.name for f in taken_off])}：它需要 {name} 同意。"))
    if past:
        notes.append(t(lang, f"{fmt_yuan(sum(f.amount_fen for f in past))} from {len(past)} "
                             f"invoice{'' if len(past) == 1 else 's'} moves past the {horizon_days}-day horizon.",
                       f"{len(past)} 张发票的 {fmt_yuan(sum(f.amount_fen for f in past))} 移到了 {horizon_days} 天预测期之后。"))
    if understated:
        notes.append(t(lang, f"FLOW assumes none of these invoices can be financed; that understates what could be financed "
                             f"by at most {fmt_yuan(understated)}.",
                       f"FLOW 假设这些发票都无法融资；这最多会低估可融资的金额 {fmt_yuan(understated)}。"))
    return ScenarioState(
        state=scenario, label=t(lang, f"{name} paid {delay_days} days late", f"{name} 晚付 {delay_days} 天"),
        assumption=" ".join([head, *notes]), source_state_version=state.state_version, day=max(day, today))


def _funding_text(r: Reading, lang: str) -> str:
    """What the router says about the stressed books, leading with the breach days and the shortfall."""
    if r.breach_days == 0:
        return t(lang, "Cash stays above your minimum on every day, so no funding is needed.",
                 "每一天现金都高于您的最低现金，不需要融资。")
    days = t(lang, f"Cash is below your minimum on {r.breach_days} day{'' if r.breach_days == 1 else 's'}.",
             f"现金有 {r.breach_days} 天低于您的最低现金。")
    if not r.plan_admissible:
        return days + t(lang, f" No committed plan covers the {fmt_yuan(r.need_fen)} shortfall: FLOW finds no admissible way "
                              f"to fund it without you.",
                        f" 没有任何已承诺的方案能覆盖 {fmt_yuan(r.need_fen)} 的缺口：没有您，FLOW 找不到合规的融资办法。")
    flags_en = (", needs your approval" if r.needs_owner else "") + (", cannot run today" if not r.executable_now else "")
    flags_zh = ("，需要您批准" if r.needs_owner else "") + ("，今天还不能执行" if not r.executable_now else "")
    return days + t(lang, f" FLOW's committed plan covers the {fmt_yuan(r.need_fen)} shortfall for {fmt_yuan(r.cost_fen)}{flags_en}.",
                    f" FLOW 已承诺的方案能以 {fmt_yuan(r.cost_fen)} 覆盖 {fmt_yuan(r.need_fen)} 的缺口{flags_zh}。")


def stress(books: Books, mandate: Mandate, buyer_id: str, delays: Sequence[int] = (30,), day: int = 0,
           commitments: Sequence[Commitment] = (), *, lang: str = "en", package: Package | None = None,
           trusted_owner_key_hex: str | None = None) -> list[StressRow]:
    """One `StressRow` per fixed delay: the unfunded lowest point, the days below the minimum, the need and whether the
    router has an admissible committed plan, on the copy in which the buyer pays every invoice that many days late.
    With a `package` it is applied first, as the verifier binds it, and the delay follows (a delay of 0 reproduces the
    decision's own unfunded projection exactly). Pure in its arguments; the books are not touched."""
    side = books
    if package is not None:
        side = books_with(books, resolve_package(books, mandate, package, day=day, commitments=commitments,
                                                 trusted_owner_key_hex=trusted_owner_key_hex))
    rows: list[StressRow] = []
    with shared_runs():
        for delay in delays:
            sc = scenario_paid_late(side, buyer_id, delay, day, horizon_days=mandate.horizon_days, lang=lang)
            live = tuple(o for o in side.obligations if binds(sc.state, o))
            r = _read_kernel(sc.state, list(live), mandate)
            rows.append(StressRow(
                delay_days=delay, lowest_fen=r.lowest_cash_fen, lowest_day=r.lowest_day, breach_days=r.breach_days,
                need_fen=r.need_fen, plan_admissible=r.plan_admissible,
                plan_cost_fen=r.cost_fen if r.plan_admissible else None, needs_owner=r.needs_owner,
                executable_now=r.executable_now, first_breach_day=r.first_breach_day, assumption=sc.assumption,
                funding_text=_funding_text(r, lang)))
    return rows


__all__ = ["DEFAULT_HORIZON_DAYS", "Reading", "marginal_impact", "read_books", "scenario_inflow",
           "scenario_paid_late", "scenario_received", "stress"]
