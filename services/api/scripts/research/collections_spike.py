"""Spike 3, collections prioritisation: which open receivable is worth a call, an early-pay offer or financing.

Read-only research (wayfinder map #39, ticket #43). On the day-0 books and on the day-34 books of the demo path, for
each open receivable it simulates the receipt (a labelled projection on a `model_copy`, never a bank receipt):

  - today: the receivable settled and its outstanding face credited to cash;
  - N days before it is due (default 5): the receipt moved with the terms-days lever on the receivable copy;
  - on the first day the reserve would be breached (the day the cash is needed), by the same lever;

re-runs `plan()` and `alerts()` on each copy and reports what changes: the funding cost the router's plan carries, the
shortfall, the days below the reserve and the alerts. The early-payment rate below which a discount beats the standing
plan is found as the verifier finds it (ADR-0007: C1 = interest + fees + discounts under the router's plan with the
discount, against C0 without it), at whole 5 bp steps. The cash price curve is the funding cost of ¥10,000 arriving
`--shift` days late against on the day, for every day of the horizon.

The day-34 books are reached by replaying the demo path in process (scripts/demo_run.py; the same steps as
tests/alerts/test_repay_alert.py::to_day34: EX01, Option A agreed, the agreed receipt on day 2, the clock to day 34).

    FLOW_RESEARCH_SPIKES=1 uv run --project services/api python services/api/scripts/research/collections_spike.py [--json]
"""

from __future__ import annotations

import _common

_common.require_flag()

import argparse
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

_common.quiet_logs()

from fastapi.testclient import TestClient

from app.alerts import Alert, AlertKind, alerts
from app.api.runtime import get_runtime
from app.books import current_books
from app.domain.fixtures import load_scenario
from app.domain.models import (
    BaseKind,
    CashFlow,
    Contingency,
    Duration,
    DurationKind,
    FinancialState,
    FlowKind,
    FundingPlan,
    Mandate,
    Mode,
    Obligation,
    ObligationBase,
    ObligationType,
    Receivable,
    SourceSpan,
)
from app.domain.money import bp, post, yuan
from app.financial import EngineError, project
from app.funding import plan as funding_plan
from app.main import app
from app.mandate import load_signed_mandate
from app.persistence import InMemoryLedgerStore
from app.verifier.bind import early_pay_lead
from app.verifier.evaluate import clear_caches

OWNER = {"X-Owner-Token": "demo-owner-token"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
RATE_STEP_BP = 5


@dataclass
class Books:
    name: str
    how: str
    state: FinancialState
    mandate: Mandate
    store: Any  # a LedgerStore: alerts() reads the commitments and expiries from it


def day0_books() -> Books:
    state, _ = load_scenario()
    mandate = load_signed_mandate()
    store = InMemoryLedgerStore()
    store.put_state(state)
    store.put_mandate(mandate)
    return Books("day 0", "the golden scenario as loaded (fixtures/scenarios/golden_sme.json)", state, mandate, store)


def day34_books() -> Books:
    """The demo path in process: EX01 evaluated, Option A agreed, the agreed receipt on day 2, the clock to day 34."""
    rt = get_runtime()
    rt.reset()
    c = TestClient(app)
    oid = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    c.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER)
    n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER).json()
    commitment = rt.store.get_commitment(n["commitment"]["id"])
    assert commitment is not None
    ob = commitment.obligations[0]
    assert ob.base.amount_fen is not None and ob.rate_bp is not None and ob.effective_day is not None
    agreed = ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
    c.post("/clock/advance", json={"to_day": ob.effective_day}, headers=OWNER)
    r = c.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "spike-receipt-1", "idempotency_key": "spike-receipt-1",
        "mandate_version": rt.store.get_mandate().version, "requested_by": "SYSTEM",
        "receivable_id": ob.base.receivable_id, "amount_fen": agreed}).json()
    if r["result"]["status"] != "EXECUTED":
        raise SystemExit(f"the demo path did not reach day 34: {r}")
    c.post("/clock/advance", json={"to_day": 30}, headers=OWNER)
    c.post("/clock/advance", json={"to_day": 34}, headers=OWNER)
    return Books("day 34", "the demo path replayed in process (scripts/demo_run.py; as tests/alerts/test_repay_alert.py::to_day34)",
                 rt.store.get_state(), rt.store.get_mandate(), rt.store)


# ---------------------------------------------------------------- the engine's readings of one set of books


@dataclass(frozen=True)
class Reading:
    cost_fen: int  # the router's plan: interest + fees + discounts above what the obligations alone post
    need_fen: int
    admissible: bool
    first_breach_day: int | None
    breach_days: int  # days the unfunded conservative trajectory closes below the reserve
    shortfall_fen: int  # the RESERVE_BREACH_AHEAD alert's shortfall (0: none)
    alert_kinds: tuple[str, ...]
    plan_label: str
    approval: bool


def read(state: FinancialState, books: Books, extra: Sequence[Obligation] = ()) -> Reading:
    m = books.mandate
    b = current_books(state, books.store.commitments())
    obs = b.with_(extra)
    p: FundingPlan = funding_plan(b.state, obs, m)
    t = project(b.state, obs, [], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    found: list[Alert] = alerts(state, m, books.store, state.as_of_day, obligations=extra)
    breach = next((a for a in found if a.kind == AlertKind.RESERVE_BREACH_AHEAD), None)
    return Reading(p.total_cost_fen, p.need_fen, p.admissible, t.first_breach_day,
                   sum(1 for d in t.days if d.closing_fen < m.min_cash_fen), breach.amount_fen or 0 if breach else 0,
                   tuple(dict.fromkeys(a.kind.value for a in found)), p.label,
                   p.needs_owner_approval)


def posted(state: FinancialState, books: Books, extra: Sequence[Obligation]) -> tuple[int, bool]:
    """C = interest + fees + discounts the projection posts under the router's plan for these books (ADR-0007)."""
    m = books.mandate
    b = current_books(state, books.store.commitments())
    obs = b.with_(extra)
    p = funding_plan(b.state, obs, m)
    t = project(b.state, obs, p.actions, Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
    return t.interest_posted_fen + t.fees_posted_fen + t.discounts_posted_fen, p.admissible


# ---------------------------------------------------------------- simulated receipts (labelled projections)


def with_receivable(state: FinancialState, r: Receivable, **update: Any) -> FinancialState:
    return state.model_copy(update={"receivables": [r.model_copy(update=update) if x.id == r.id else x
                                                    for x in state.receivables]})


def received_today(state: FinancialState, r: Receivable) -> FinancialState:
    paid = with_receivable(state, r, status="SETTLED", settled_fen=r.face_fen)
    return paid.model_copy(update={"cash_fen": paid.cash_fen + r.outstanding_fen})


def received_on(state: FinancialState, r: Receivable, day: int) -> FinancialState:
    """The receipt moved to `day` with the terms-days lever (the engine posts a RECEIPT on issue day + terms)."""
    return with_receivable(state, r, terms_days=day - r.issue_day)


def early_pay(state: FinancialState, r: Receivable, rate_bp: int, face_fen: int) -> Obligation:
    return Obligation(
        id="SPIKE-EARLY-PAY", type=ObligationType.IMMEDIATE_DISCOUNT, counterparty_id=r.counterparty_id,
        rate_bp=rate_bp, effective_day=early_pay_lead(state, r.counterparty_id),
        base=ObligationBase(kind=BaseKind.INVOICE, amount_fen=face_fen, receivable_id=r.id),
        contingency=Contingency.FIRM, duration=Duration(kind=DurationKind.ONE_OFF),
        spans=[SourceSpan(doc_id="spike", start=0, end=0, text="")], confidence=1.0)


# ---------------------------------------------------------------- records


@dataclass
class Effect:
    label: str
    receipt_day: int
    reading: Reading
    saving_fen: int  # the funding cost the standing plan carries less the cost with this receipt
    shortfall_removed_fen: int
    breach_days_removed: int
    alerts_cleared: list[str]


@dataclass
class EarlyPay:
    face_fen: int
    face_label: str
    max_rate_bp: int | None  # None: no whole-5bp rate beats the standing plan; 0 steps are not offered
    cost_without_fen: int
    cost_with_fen: int | None  # at max_rate_bp
    beats_by_fen: int | None
    note: str
    next_rate_bp: int | None = None  # the next 5 bp step, and how much dearer than the standing plan it is
    next_dearer_by_fen: int | None = None
    sweep: list[tuple[int, int | None]] = field(default_factory=list)  # (rate bp, C1 - C0): negative means it beats the plan


@dataclass
class Row:
    receivable: str
    buyer: str
    buyer_name: str
    face_fen: int
    outstanding_fen: int
    due_day: int
    days_late: int
    status: str
    financed_by_plan: bool
    effects: list[Effect] = field(default_factory=list)
    early_pay: list[EarlyPay] = field(default_factory=list)
    marginal_value_fen: int = 0
    net_value_fen: int = 0  # what is left after the discount that earns it, at the ceiling rate (a floor of the gain)
    action: str = ""
    sentence: str = ""
    skipped: str = ""


@dataclass
class BooksReport:
    name: str
    how: str
    day: int
    cash_fen: int
    baseline: Reading
    rows: list[Row] = field(default_factory=list)
    curve: list[dict[str, Any]] = field(default_factory=list)
    seconds: float = 0.0
    engine_calls: int = 0


def plan_uses(books: Books, rid: str) -> bool:
    b = current_books(books.state, books.store.commitments())
    p = funding_plan(b.state, list(b.obligations), books.mandate)
    return any(a.receivable_id == rid for a in p.actions)


def explore(books: Books, days_earlier: int, shift: int, amount_fen: int, curve: bool) -> BooksReport:
    watch = _common.Stopwatch()
    st, m = books.state, books.mandate
    day = st.as_of_day
    calls = 0
    base = read(st, books)
    calls += 1
    cost0, _admissible = posted(st, books, ())
    rep = BooksReport(books.name, books.how, day, st.cash_fen, base)
    names = {c.id: c.name for c in st.counterparties}
    for r in sorted((x for x in st.receivables if x.status in ("OPEN", "FINANCED") and x.outstanding_fen > 0),
                    key=lambda x: (x.due_day, x.id)):
        row = Row(r.id, r.counterparty_id, names.get(r.counterparty_id, r.counterparty_id), r.face_fen, r.outstanding_fen,
                  r.due_day, max(0, day - r.due_day), r.status, plan_uses(books, r.id))
        if r.status != "OPEN":
            row.skipped = "financed: a receipt repays the advance first (ADR-0010); the lender's lot is outside this spike"
            rep.rows.append(row)
            continue
        targets: list[tuple[str, int, FinancialState]] = [(f"received today (day {day})", day, received_today(st, r))]
        early_day = r.due_day - days_earlier
        if early_day > day:
            targets.append((f"received {days_earlier} days before it is due (day {early_day})", early_day,
                            received_on(st, r, early_day)))
        if base.first_breach_day is not None and day < base.first_breach_day < r.due_day and base.first_breach_day != early_day:
            targets.append((f"received by the first breach day (day {base.first_breach_day})", base.first_breach_day,
                            received_on(st, r, base.first_breach_day)))
        for label, rday, s1 in targets:
            rd = read(s1, books)
            calls += 1
            row.effects.append(Effect(
                label, rday, rd, base.cost_fen - rd.cost_fen, base.shortfall_fen - rd.shortfall_fen,
                base.breach_days - rd.breach_days, [k for k in base.alert_kinds if k not in rd.alert_kinds]))
        row.marginal_value_fen = row.effects[0].saving_fen
        overdue = r.due_day < day
        faces = [("the whole outstanding invoice", r.outstanding_fen)]
        if 0 < base.need_fen < r.outstanding_fen:
            faces.append(("the shortfall the plan covers", base.need_fen))
        for face_label, face in faces:
            if overdue:
                row.early_pay.append(EarlyPay(face, face_label, None, cost0, None, None,
                                              "overdue: an early-payment discount is never offered on an invoice already due"))
                break
            ep = best_early_pay(books, r, face, cost0, m)
            calls += 1
            ep.face_label = face_label
            row.early_pay.append(ep)
        row.action, row.sentence = decide(row, r, day, base)
        row.net_value_fen = net_value(row)
        rep.rows.append(row)
    rep.rows.sort(key=lambda x: (-x.marginal_value_fen, x.due_day, x.receivable))
    if curve:
        rep.curve = price_curve(books, shift, amount_fen)
    rep.engine_calls = calls
    rep.seconds = watch.seconds()
    return rep


def best_early_pay(books: Books, r: Receivable, face: int, cost0: int, m: Mandate) -> EarlyPay:
    """The largest whole-5bp rate whose C1 (interest + fees + discounts with the discount and the router's plan for
    the rest) is below C0 (the standing plan without it): ADR-0007's test, as `verifier.evaluate._early_pay_vs_plan` runs it."""
    cap = m.max_immediate_discount_bp if m.max_immediate_discount_bp is not None else 200
    rates = list(range(0, cap + 1, RATE_STEP_BP))
    cache: dict[int, int | None] = {}

    def c1(rate: int) -> int | None:
        if rate not in cache:
            try:
                cost, ok = posted(books.state, books, [early_pay(books.state, r, rate, face)]) if rate else (cost0, True)
            except EngineError:
                cost, ok = 0, False
            cache[rate] = cost if ok else None
        return cache[rate]

    found = _common.last_true(rates, lambda d: (v := c1(d)) is not None and (d == 0 or v < cost0))
    best = found.value
    if not best:
        return EarlyPay(face, "", None, cost0, None, None, "no discount of 0.05% or more costs less than the standing plan")
    with_cost = c1(best)
    assert with_cost is not None
    nxt = best + RATE_STEP_BP if best + RATE_STEP_BP <= cap else None
    nxt_cost = c1(nxt) if nxt is not None else None
    sweep: list[tuple[int, int | None]] = []
    for d in rates[1:]:
        v = c1(d)
        sweep.append((d, None if v is None else v - cost0))
    return EarlyPay(face, "", best, cost0, with_cost, cost0 - with_cost, "", nxt,
                    nxt_cost - cost0 if nxt_cost is not None else None, sweep)


def decide(row: Row, r: Receivable, day: int, base: Reading) -> tuple[str, str]:
    """The action and the sentence in the owner's words. Rules, in order, each read from an engine output:
    overdue -> call now; collecting it saves nothing -> wait; an early-pay rate beats the standing plan -> offer early
    pay up to that rate; else finance the invoice."""
    saving = row.effects[0].saving_fen
    eff = row.effects[0]
    left = eff.reading.need_fen
    who = row.buyer_name
    face = _common.yuan_text(row.outstanding_fen)
    avoided = _common.yuan_text(saving)
    remaining = (f"and leaves {_common.yuan_text(left)} to cover" if left > 0 else "and clears the shortfall")
    standing = " The standing plan already advances against it." if row.financed_by_plan else ""
    if row.days_late > 0:
        return "call now", (f"Call {who} first: recovering {face} now avoids {avoided} of financing cost {remaining}.")
    if saving <= 0:
        return "wait", (f"Wait on {r.id} ({face}, due day {r.due_day}): collecting it early saves {avoided} of financing cost, "
                        f"so there is nothing to pay for.")
    rates = [e for e in row.early_pay if e.max_rate_bp]
    if rates:
        e = max(rates, key=lambda x: (x.max_rate_bp or 0, x.face_fen))
        top = _common.pct_text(e.max_rate_bp or 0)
        others = "".join(f" ({_common.pct_text(x.max_rate_bp or 0)} if it covers {_common.yuan_text(x.face_fen)})"
                         for x in rates if x is not e)
        text = (f"Offer {who} early payment on {r.id} ({face}, due day {r.due_day}) at up to {top} on "
                f"{_common.yuan_text(e.face_fen)}{others}: paying it today would avoid {avoided} of financing cost {remaining}, "
                f"and a discount up to that rate costs less than the financing it replaces.{standing}")
        return f"offer early pay up to {top}", text
    return "finance the invoice", (f"Finance {r.id} ({face}, due day {r.due_day}) rather than ask {who} to pay early: collecting it "
                                   f"today would avoid {avoided} of financing cost, but no early-payment discount costs less than that.{standing}")


def net_value(row: Row) -> int:
    """What the action is worth after what it costs: a call is free, an early payment pays its discount (at the ceiling
    rate, so the least it can be worth), waiting or financing adds nothing over the standing plan."""
    if row.action == "call now":
        return row.effects[0].saving_fen
    if row.action.startswith("offer early pay"):
        return max((e.beats_by_fen or 0 for e in row.early_pay if e.max_rate_bp), default=0)
    return 0


def price_curve(books: Books, shift: int, amount_fen: int) -> list[dict[str, Any]]:
    """The marginal value of `amount_fen` arriving `shift` days earlier, by arrival day: the funding cost of the plan with
    the money arriving on day d + shift less the cost with it arriving on day d."""
    st, m = books.state, books.mandate
    out: list[dict[str, Any]] = []

    def cost_with_inflow(day: int) -> tuple[int, bool]:
        flow = CashFlow(id=f"SPIKE-INFLOW-{day}", day=day, amount_fen=amount_fen, kind=FlowKind.OTHER,
                        label="research spike: hypothetical inflow", confirmed=True)
        s = st.model_copy(update={"flows": [*st.flows, flow]})
        b = current_books(s, books.store.commitments())
        p = funding_plan(b.state, list(b.obligations), m)
        return p.total_cost_fen, p.admissible

    last = st.as_of_day + m.horizon_days - shift
    for d in range(st.as_of_day, last + 1):
        early, ok1 = cost_with_inflow(d)
        late, ok2 = cost_with_inflow(d + shift)
        out.append({"day": d, "value_fen": late - early if ok1 and ok2 else None, "admissible": ok1 and ok2})
    return out


def bands(curve: list[dict[str, Any]]) -> list[tuple[int, int, int | None]]:
    out: list[tuple[int, int, int | None]] = []
    for p in curve:
        if out and out[-1][2] == p["value_fen"] and out[-1][1] == p["day"] - 1:
            out[-1] = (out[-1][0], p["day"], p["value_fen"])
        else:
            out.append((p["day"], p["day"], p["value_fen"]))
    return out


# ---------------------------------------------------------------- output


def render(reps: list[BooksReport], days_earlier: int, shift: int, amount_fen: int) -> str:
    title = ("COLLECTIONS: what is each open receivable worth? Receipts are hypothetical projections on a copy of the books "
             "(never a bank receipt); nothing is booked or sent.")
    out = [title]
    for r in reps:
        b = r.baseline
        breach = f"day {b.first_breach_day}" if b.first_breach_day is not None else "none"
        head = (f"   cash {_common.yuan_text(r.cash_fen)}; the standing plan needs {_common.yuan_text(b.need_fen)} and costs "
                f"{_common.yuan_text(b.cost_fen)}; first breach {breach}; "
                f"{b.breach_days} days below the reserve; alerts: {', '.join(b.alert_kinds) or 'none'}")
        out += ["", f"== {r.name}: {r.how}", head]
        rows = []
        for i, w in enumerate(r.rows, 1):
            if w.skipped:
                rows.append([i, w.receivable, _common.yuan_text(w.outstanding_fen), w.due_day, "-", "-", "-", "-", "-", "-", "-", w.skipped])
                continue
            e = w.effects[0]
            eps = "; ".join(f"{_common.pct_text(x.max_rate_bp or 0)} on {_common.yuan_text(x.face_fen)}" for x in w.early_pay if x.max_rate_bp)
            rows.append([i, w.receivable, _common.yuan_text(w.outstanding_fen), f"{w.due_day}"
                         + (f" ({w.days_late} late)" if w.days_late else ""),
                         _common.yuan_text(e.saving_fen), _common.yuan_text(e.reading.cost_fen), _common.yuan_text(e.reading.need_fen),
                         f"{e.breach_days_removed} of {b.breach_days}", ", ".join(e.alerts_cleared) or "-",
                         eps or "-",
                         _common.yuan_text(w.net_value_fen), w.action])
        out.append(_common.table(["#", "Receivable", "Outstanding", "Due day", "Saved if received today", "Plan cost left", "Need left",
                                  "Breach days removed", "Alerts cleared", "Early-pay ceiling", "Net of the discount", "Action"], rows))
        out += ["", "   Other receipt days (saving = standing-plan cost less cost with the receipt):"]
        orow = []
        for w in r.rows:
            for e in w.effects[1:]:
                orow.append([w.receivable, e.label, _common.yuan_text(e.saving_fen), _common.yuan_text(e.reading.need_fen),
                             f"{e.breach_days_removed}", ", ".join(e.alerts_cleared) or "-"])
        out.append(_common.table(["Receivable", "Receipt", "Saved", "Need left", "Breach days removed", "Alerts cleared"], orow or [["-"] * 6]))
        out += ["", "   Early-payment discount that beats the standing plan (C1 < C0):"]
        erow = []
        for w in r.rows:
            for x in w.early_pay:
                erow.append([w.receivable, x.face_label, _common.yuan_text(x.face_fen),
                             _common.pct_text(x.max_rate_bp) if x.max_rate_bp else "none",
                             _common.yuan_text(x.cost_without_fen), _common.yuan_text(x.cost_with_fen) if x.cost_with_fen is not None else "-",
                             _common.yuan_text(x.beats_by_fen) if x.beats_by_fen is not None else "-",
                             f"{_common.pct_text(x.next_rate_bp)}: {_common.yuan_text(x.next_dearer_by_fen)}"
                             if x.next_rate_bp is not None and x.next_dearer_by_fen is not None else "-", x.note])
        out.append(_common.table(["Receivable", "Face", "Amount", "Largest rate", "C0 (without)", "C1 (with, at that rate)", "Beats by", "Next step dearer by", "Note"], erow or [["-"] * 9]))
        out += ["", "   In the owner's words, ranked by marginal value:"]
        for i, w in enumerate(r.rows, 1):
            out.append(f"   {i}. [{w.action or 'n/a'}] {w.sentence or w.skipped}")
        net = sorted((w for w in r.rows if not w.skipped), key=lambda w: (-w.net_value_fen, w.due_day, w.receivable))
        out += ["", "   Ranked by net value instead (the saving less the discount that earns it, at the ceiling rate): "
                + "; ".join(f"{w.receivable} {_common.yuan_text(w.net_value_fen)} [{w.action}]" for w in net)]
        if r.curve:
            out += ["", f"   Cash price curve: what {_common.yuan_text(amount_fen)} arriving {shift} days earlier is worth, by arrival day"]
            out.append(_common.table(["Arrival day", "Worth"], [
                [f"{a}" if a == z else f"{a}-{z}", _common.yuan_text(v) if v is not None else "no admissible plan"] for a, z, v in bands(r.curve)]))
        out.append(f"   {r.engine_calls} plan/alerts readings, {_common.seconds_text(r.seconds)}.")
    out += ["", f"({days_earlier} days earlier = the receipt moved with the terms-days lever; the curve moves a ¥ amount by {shift} days)"]
    return "\n".join(out)


def to_json(reps: list[BooksReport], amount_fen: int) -> dict[str, Any]:
    def reading(rd: Reading) -> dict[str, Any]:
        return {"cost": _common.money(rd.cost_fen), "need": _common.money(rd.need_fen), "admissible": rd.admissible,
                "first_breach_day": rd.first_breach_day, "breach_days": rd.breach_days,
                "shortfall": _common.money(rd.shortfall_fen), "alerts": list(rd.alert_kinds), "plan": rd.plan_label,
                "plan_needs_owner_approval": rd.approval}

    docs: list[dict[str, Any]] = []
    for r in reps:
        rows = []
        for w in r.rows:
            d = asdict(w)
            d.update({"outstanding": _common.money(w.outstanding_fen), "face": _common.money(w.face_fen),
                      "marginal_value": _common.money(w.marginal_value_fen),
                      "net_value_at_ceiling": _common.money(w.net_value_fen),
                      "effects": [{"label": e.label, "receipt_day": e.receipt_day, "saving": _common.money(e.saving_fen),
                                   "shortfall_removed": _common.money(e.shortfall_removed_fen),
                                   "breach_days_removed": e.breach_days_removed, "alerts_cleared": e.alerts_cleared,
                                   "after": reading(e.reading)} for e in w.effects],
                      "early_pay": [{"face": _common.money(e.face_fen), "face_label": e.face_label,
                                     "largest_rate": _common.rate(e.max_rate_bp) if e.max_rate_bp else None,
                                     "cost_without": _common.money(e.cost_without_fen),
                                     "cost_with": _common.money(e.cost_with_fen) if e.cost_with_fen is not None else None,
                                     "beats_by": _common.money(e.beats_by_fen) if e.beats_by_fen is not None else None,
                                     "next_rate": _common.rate(e.next_rate_bp) if e.next_rate_bp is not None else None,
                                     "next_rate_dearer_by": (_common.money(e.next_dearer_by_fen)
                                                             if e.next_dearer_by_fen is not None else None),
                                     "sweep": [{"rate": _common.rate(d), "c1_less_c0": _common.money(v) if v is not None else None}
                                               for d, v in e.sweep],
                                     "note": e.note} for e in w.early_pay]})
            for k in ("face_fen", "outstanding_fen", "marginal_value_fen", "net_value_fen"):
                d.pop(k, None)
            rows.append(d)
        docs.append({"books": r.name, "how": r.how, "day": r.day, "cash": _common.money(r.cash_fen),
                     "baseline": reading(r.baseline), "ranking": rows,
                     "cash_price_curve": {"amount": _common.money(amount_fen),
                                          "points": [{"arrival_day": p["day"],
                                                      "worth": _common.money(p["value_fen"]) if p["value_fen"] is not None else None}
                                                     for p in r.curve]},
                     "readings": r.engine_calls, "seconds": round(r.seconds, 3)})
    return {"spike": "collections", "hypothetical": True, "books": docs}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", choices=("0", "34", "both"), default="both", help="the books to read (default both)")
    ap.add_argument("--days-earlier", type=int, default=5, help="receipt this many days before it is due (default 5)")
    ap.add_argument("--curve-shift", type=int, default=30, help="the cash price curve moves money this many days (default 30)")
    ap.add_argument("--curve-yuan", type=int, default=10_000, help="the cash price curve amount in yuan (default 10000)")
    ap.add_argument("--no-curve", action="store_true", help="skip the cash price curve (about a minute for both books)")
    ap.add_argument("--json", action="store_true", help="print one JSON document (fen and display strings)")
    args = ap.parse_args(argv)
    if args.days_earlier < 1 or args.curve_shift < 1 or args.curve_yuan < 100:
        sys.stderr.write("refused: --days-earlier and --curve-shift must be positive and --curve-yuan at least 100\n")
        return 2
    clear_caches()
    books = ([day0_books()] if args.day in ("0", "both") else []) + ([day34_books()] if args.day in ("34", "both") else [])
    amount = yuan(args.curve_yuan)
    reps = [explore(b, args.days_earlier, args.curve_shift, amount, not args.no_curve) for b in books]
    print(_common.dump(to_json(reps, amount)) if args.json else render(reps, args.days_earlier, args.curve_shift, amount))
    return 0


if __name__ == "__main__":
    sys.exit(main())
