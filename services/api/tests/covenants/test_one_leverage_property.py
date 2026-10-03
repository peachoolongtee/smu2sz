"""One leverage definition (docs/FINANCIAL_SEMANTICS.md section 5), property-tested across every reader.

For any books and any plan, the leverage the verifier reports, the leverage the projection's month points carry, the
leverage capex reports for a structure, the borrower file's figure and the chat SHOW_RATIOS figure are the same exact
fen-ratio, recomputed here by hand from the month point's raw figures:

    leverage_m = month-end debt_m / (12 × EBITDA_m),
    debt_m     = DebtPosition principal + drawn balances of facilities that count in leverage (from the request day).

A committed line's undrawn room is never in it. The worlds are the planner/executor agreement's
(tests/funding/test_planner_executor_agree.py): the golden fixture with its cash, flows, receivables, facility terms,
EBITDA and day varied.
"""

from __future__ import annotations

import os
from fractions import Fraction
from typing import Any

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from app.books import current_books
from app.borrower_file import build as build_file
from app.capex import CapexRequest, evaluate_capex
from app.covenants import ratios_for
from app.domain.models import (
    CashFlow,
    CompiledOffer,
    CompileStatus,
    FacilityStatus,
    FlowKind,
    FundingAction,
    FundingActionKind,
    Mode,
    MonthPoint,
    Trajectory,
    ViolationCode,
)
from app.domain.money import Ratio
from app.financial import project
from app.financial.trajectory import MONTH_DAYS
from app.mandate import demo_owner_public_key_hex
from app.nl.capabilities import show_ratios
from app.nl.context import NlContext
from app.nl.sessions import Session
from app.verifier import evaluate
from tests.financial.builders import extension
from tests.funding.test_planner_executor_agree import (
    GOLDEN,
    LINE_HELD,
    TERM_LOAN,
    World,
    build,
    committed_plan,
    worlds,
)

C = Mode.CONSERVATIVE
KEY = demo_owner_public_key_hex()
PROPS = settings(max_examples=int(os.environ.get("LEVERAGE_EXAMPLES", "12")), deadline=None,
                 suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


def fen_ratio(m: MonthPoint) -> Fraction | None:
    """By hand, from the raw month figures: debt / (12 × EBITDA); undefined when EBITDA <= 0."""
    return Fraction(m.total_debt_fen, 12 * m.ebitda_fen) if m.ebitda_fen > 0 else None


def worst(t: Trajectory) -> tuple[int, Fraction] | None:
    """(month, ratio) of the highest leverage, the earliest month on a tie."""
    best: tuple[int, Fraction] | None = None
    for m in t.months:
        r = fen_ratio(m)
        if r is not None and (best is None or r > best[1]):
            best = (m.month, r)
    return best


def _live(rt: Any) -> list:
    """The live commitments' obligations (current books, ADR-0006)."""
    return list(current_books(rt.store.get_state(), rt.store.commitments()).obligations)


def _offer(offer_id: str, counterparty: str, obligations: list, day: int, compiler: str) -> CompiledOffer:
    return CompiledOffer(offer_id=offer_id, counterparty_id=counterparty, doc_ids=[offer_id], received_day=day,
                         status=CompileStatus.COMPILED, obligations=obligations, compiler=compiler,
                         prompt_version="t")


def check_verifier(rt: Any, offer: CompiledOffer) -> None:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    b = evaluate(offer, state, mandate, trusted_owner_key_hex=KEY, day=rt.day, commitments=rt.store.commitments(),
                 plans="committed")
    if b.plan_committed is None:  # stopped before the predicates (an unbindable term): no ratio is reported
        return
    pc = b.plan_committed
    live = _live(rt)
    acts = list(pc.actions) if pc.admissible and pc.actions else []
    funded = project(state, [*live, *b.bound_obligations], acts, C, mandate.horizon_days, mandate.min_cash_fen)
    w = worst(funded)
    passed = {p.code: p for p in b.passed_checks}
    breaches = [v for v in b.verdict.violations if v.code == ViolationCode.LEVERAGE_BREACH]
    if "LEVERAGE_MAX" in passed:
        assert w is not None and not breaches
        p = passed["LEVERAGE_MAX"]
        assert Fraction(p.inputs["leverage_exact"]) == w[1] and p.inputs["month"] == str(w[0])
    else:
        assert breaches and w is not None
        assert max(Fraction(v.inputs["leverage_exact"]) for v in breaches) == w[1]
    # the extension's pro-forma inputs carry the same reading (its DSCR is the labelled steady-state estimate)
    for p in b.passed_checks:
        if "pro_forma_leverage" in p.inputs:
            assert w is not None and p.inputs["pro_forma_leverage"] == Ratio.of(w[1]).text + "x"
            assert p.inputs["pro_forma_leverage_month"] == str(w[0])


def check_capex(rt: Any, price: int) -> None:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    r = evaluate_capex(CapexRequest(price_fen=price), state, mandate, commitments=rt.store.commitments())
    for s in r.structures:
        if s.kind == "CASH_LINE" or s.leverage is None:
            continue
        f = next(x for x in state.facilities if x.id == s.facility_id)
        if price > f.limit_fen - f.drawn_fen:
            continue  # not projected: the labelled estimate, not a projection figure
        granted = f.model_copy(update={"status": FacilityStatus.COMMITTED, "owner_approved": True,
                                       "term_months": s.term_months})
        buy = CashFlow(id="CAPEX-PURCHASE", day=state.as_of_day + f.lead_time_days, amount_fen=-price,
                       kind=FlowKind.OTHER, label="purchase")
        scenario = state.model_copy(update={"flows": [*state.flows, buy], "facilities": [
            granted if x.id == f.id else x for x in state.facilities]})
        draw = FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=state.as_of_day, amount_fen=price)
        t = project(scenario, _live(rt), [draw], C, mandate.horizon_days, mandate.min_cash_fen)
        w = worst(t)
        assert w is not None and s.leverage.value == w[1]
        working = next(x for x in s.workings if x.label == "Leverage")
        assert working.inputs["month"] == str(w[0])


def check_borrower_file(rt: Any, amount: int) -> None:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    f = next(x for x in state.facilities if x.id == "FAC-GGL")
    amount = min(amount, f.limit_fen - f.drawn_fen)
    day = rt.day
    bf = build_file(rt.store, facility_id=f.id, amount_fen=amount, use_of_proceeds="Working capital", day=day)
    obs = _live(rt)
    horizon = max(mandate.horizon_days, 7 * 13, MONTH_DAYS * 12)
    before = project(state, obs, [], C, horizon)
    after_state = state.model_copy(update={"facilities": [
        x.model_copy(update={"status": FacilityStatus.COMMITTED}) if x.id == f.id else x for x in state.facilities]})
    after = project(after_state, obs, [FundingAction(kind=FundingActionKind.DRAW, facility_id=f.id, day=day,
                                                     amount_fen=amount)], C, horizon)

    def month(t: Trajectory, k: int) -> MonthPoint:
        b = day + MONTH_DAYS * k
        return t.months[min(max(1, -(-b // MONTH_DAYS)), len(t.months)) - 1]

    sec = {s.key: s for s in bf.sections}
    m1 = next(r for r in sec["summary"].rows if r.label.startswith("Month 1 "))
    assert m1.figures[1].ratio is not None and m1.figures[1].ratio.value == fen_ratio(month(before, 1))
    for k, row in enumerate(sec["trajectory_12m"].rows, start=1):
        assert row.figures[3].ratio is not None and row.figures[3].ratio.value == fen_ratio(month(after, k))
    for k, row in enumerate(sec["covenant_headroom"].rows, start=1):
        assert row.figures[3].ratio.value == fen_ratio(month(before, k))
        assert row.figures[4].ratio.value == fen_ratio(month(after, k))


def check_chat(rt: Any) -> None:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    t = project(state, _live(rt), [], C, mandate.horizon_days, mandate.min_cash_fen)
    w = worst(t)
    ctx = NlContext(store=rt.store, executor=rt.executor, day=rt.day, owner_key_hex=KEY, owner_authenticated=True,
                    session=Session(id="leverage-property", actor="OWNER", owner_auth=True), lang="en",
                    trace_id="leverage-property")
    reply = show_ratios(ctx).reply
    assert w is not None and f"Highest leverage {Ratio.of(w[1]).text}× in month {w[0]}," in reply


@PROPS
@given(w=worlds(), price=st.integers(5, 60).map(lambda n: n * 1_000_000))
@example(w=GOLDEN, price=60_000_000)
@example(w=TERM_LOAN, price=30_000_000)
@example(w=LINE_HELD, price=10_000_000)
def test_every_reader_reports_the_projection_leverage(w: World, price: int) -> None:
    rt = build(w)
    books, mandate, p = committed_plan(rt)
    # the projection under the router's committed plan: every month point carries the fen-ratio, and ratios_for
    # (the one function) returns it
    acts = list(p.actions) if p.admissible else []
    t = project(books.state, books.with_([]), acts, C, mandate.horizon_days, mandate.min_cash_fen)
    for m in t.months:
        lev = ratios_for(m)[1]
        assert (lev.value if lev else None) == (m.leverage.value if m.leverage else None) == fen_ratio(m)
    check_verifier(rt, _offer("SQ", "OWNER", [], rt.day, "nl-status-quo"))
    if w.recurring is not None:
        check_verifier(rt, _offer("EXT", "BUYER-1", [extension(15)], rt.day, "whatif-property"))
    check_capex(rt, price)
    check_borrower_file(rt, price)
    check_chat(rt)


def test_the_golden_books_read_one_figure_everywhere() -> None:
    # Golden day 0, no plan: month 1 = (1,500,000 − the day-30 ¥45,000 payment) / (12 × 90,000) = 1,455,000 /
    # 1,080,000 = 1.347 -> 1.35, the figure the chat shows; the undrawn ¥150,000 line is not in it.
    rt = build(GOLDEN)
    t = project(rt.store.get_state(), [], [], C, 120)
    assert worst(t) == (1, Fraction(145_500_000, 108_000_000))
    check_chat(rt)
