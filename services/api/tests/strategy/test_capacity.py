"""Capacity as day series (map #88, ticket #96, brief section F): every dimension reconciled to the figure the product
already shows, on the golden books, the demo path at day 34, the short-facilities scenario, the public-record SME and
the Demo's three packages; the edge rules; the display. Read-only: the books are byte-identical afterwards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.strategy.capacity as capacity_module
from app.alerts.engine import _candidates
from app.api.runtime import Runtime, set_runtime
from app.books import Books, current_books
from app.covenants import evaluate as evaluate_covenants
from app.domain.models import (
    CovenantKind,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    FundingActionKind,
    FundingLot,
    Mandate,
    Mode,
    ViolationCode,
)
from app.domain.money import fmt_yuan
from app.financial import project
from app.financial.debts import debt_payments
from app.funding import plan
from app.funding.router import shared_runs
from app.strategy.capacity import (
    NO_NEW_BORROWING,
    BoundPackage,
    CapacityWindow,
    _window,
    books_with,
    capacity_before_after,
    facility_balances,
    in_flight,
    resolve_package,
    snapshot,
    window_view,
)
from app.strategy.impact import read_books
from app.whatif.params import WhatIfParams
from app.whatif.simulate import simulate

from .conftest import OWNER
from .exposure_books import ASKED, OPTION_A, OPTION_B, OWNER_KEY, PACKAGES, golden, scenario_books

SCENARIOS = Path(__file__).resolve().parents[4] / "fixtures" / "scenarios"


def _w(snap, dimension: str, facility: str | None = None, reading: str | None = None, buyer: str | None = None) -> CapacityWindow:
    found = [w for w in snap.windows if w.dimension == dimension and w.facility_id == facility
             and w.reading == reading and w.buyer_id == buyer]
    assert len(found) == 1, (dimension, facility, reading, [x.dimension for x in snap.windows])
    return found[0]


def _funded(books: Books, mandate: Mandate):
    p = plan(books.state, books.with_([]), mandate)
    actions = list(p.actions) if p.admissible else []
    t = project(books.state, books.with_([]), actions, Mode.CONSERVATIVE, mandate.horizon_days, mandate.min_cash_fen)
    return p, actions, t


def _debt_principal(state: FinancialState, until: int) -> list[int]:
    """The existing debts' principal outstanding on every day 0..until (the schedule the clock posts)."""
    out = []
    pays = {d.id: debt_payments(d, state.as_of_day, until + 1) for d in state.debts}
    for day in range(until + 1):
        out.append(sum(d.principal_fen - sum(p.principal for p in pays[d.id] if p.day <= day) for d in state.debts))
    return out


# ---------------------------------------------------------------- the Demo's books, pinned (r4 section 7)


def test_current_books_pins_the_golden_day0_figures():
    books, mandate = golden()
    s = snapshot(books, mandate, 0)
    buffer = _w(s, "cash_buffer")
    assert (buffer.today_fen, buffer.lowest_fen, buffer.lowest_day) == (10_000_000, -40_500_000, 30)
    assert (buffer.through_day, buffer.recovers_day, buffer.over_by) == (31, 32, True)  # below the minimum through 1 Nov
    line = _w(s, "credit_line", "FAC-LINE")
    assert (line.today_fen, line.lowest_fen, line.through_day, line.recovers_day, line.after_fen) == (0, 0, 31, 32, 15_000_000)
    assert line.recovery_assumed is True  # the line's repayment is the plan's, not an executed one (ADR-0010 section 5)
    today = _w(s, "invoice_finance", "FAC-IF", "TODAY")
    assert (today.today_fen, today.through_day) == (8_100_000, 31)  # ¥336,000 of advances less the plan's ¥255,000
    as_issued = _w(s, "invoice_finance", "FAC-IF", "AS_ISSUED")
    assert (as_issued.today_fen, as_issued.recovers_day, as_issued.after_fen) == (8_100_000, 2, 9_500_000)
    assert _w(s, "concession").today_fen == 500_000
    dscr, lev = _w(s, "dscr_room"), _w(s, "leverage_room")
    assert (dscr.lowest_fen, dscr.month) == (2_388_607, 2)  # ¥23,886.07, month 2
    assert (lev.today_fen, lev.month) == (84_000_000, 1)  # ¥840,000
    assert s.plan_admissible is True and (s.need_first_day, s.need_last_day) == (12, 31)


def test_accept_as_asked_pins_the_line_the_ask_and_the_cap():
    books, mandate = golden()
    ba = capacity_before_after(books, mandate, ASKED, 0, (), trusted_owner_key_hex=OWNER_KEY)
    assert ba.after is not None and ba.before == snapshot(books, mandate, 0)
    line = _w(ba.after, "credit_line", "FAC-LINE")
    assert (line.today_fen, line.through_day, line.recovers_day) == (1_496_000, 61, 62)  # ¥14,960 to 1 Dec, full from 2 Dec
    assert _w(ba.after, "invoice_finance", "FAC-IF", "TODAY").today_fen == 0  # RCV-A is under the early-payment agreement
    concession = _w(ba.after, "concession")
    assert concession.today_fen == -2_332_692 and concession.over_by  # ¥500,000 cap less ¥28,326.92 + the booked ¥0
    assert _w(ba.after, "dscr_room").lowest_fen == 2_553_195  # ¥25,531.95, month 3
    assert _w(ba.after, "leverage_room").today_fen == 110_996_000  # ¥1,109,960


def test_option_a_leaves_thirteen_yuan_eighty_of_the_line_to_the_first_of_november():
    books, mandate = golden()
    after = capacity_before_after(books, mandate, OPTION_A, 0, (), trusted_owner_key_hex=OWNER_KEY).after
    assert after is not None
    line = _w(after, "credit_line", "FAC-LINE")
    assert (line.today_fen, line.through_day, line.recovers_day) == (1_380, 31, 32)  # ¥13.80 until 1 Nov
    assert _w(after, "invoice_finance", "FAC-IF", "TODAY").today_fen == 0  # the part-early-paid invoice is wholly ineligible
    assert _w(after, "concession").today_fen == 500_000
    assert (_w(after, "dscr_room").lowest_fen, _w(after, "leverage_room").today_fen) == (2_615_843, 109_501_380)


def test_option_b_pins_the_line_to_the_26th_and_the_21000_of_invoice_finance():
    books, mandate = golden()
    after = capacity_before_after(books, mandate, OPTION_B, 0, (), trusted_owner_key_hex=OWNER_KEY).after
    assert after is not None
    line = _w(after, "credit_line", "FAC-LINE")
    assert (line.today_fen, line.through_day, line.recovers_day) == (6_000_000, 56, 57)  # ¥60,000 to 26 Nov
    assert _w(after, "invoice_finance", "FAC-IF", "TODAY").today_fen == 2_100_000
    assert _w(after, "dscr_room").lowest_fen == 2_329_354


# ---------------------------------------------------------------- reconciliations to the figures the product shows


def test_cash_buffer_reconciles_to_the_reading_and_to_home(rt_day0: Runtime, books_day0: Books):
    mandate = rt_day0.store.get_mandate()
    s = snapshot(books_day0, mandate, 0)
    lowest = _w(s, "cash_buffer").lowest_fen
    assert lowest == read_books(books_day0, mandate, rt_day0.store, 0).lowest_headroom_fen
    assert lowest == _home(rt_day0)["cash"]["lowest_headroom_fen"]


def test_with_no_plan_the_line_today_is_homes_available():
    """No funding needed: the line's room today is `limit - drawn`, the figure Home prints as `available`."""
    rt = _rich_runtime()
    books = Books(state=rt.store.get_state(), obligations=())
    mandate = rt.store.get_mandate()
    assert plan(books.state, [], mandate).actions == []
    line = _w(snapshot(books, mandate, 0), "credit_line", "FAC-LINE")
    row = next(f for f in _home(rt)["facilities"] if f["id"] == "FAC-LINE")
    assert fmt_yuan(line.today_fen) == row["available_display"] == "¥150,000.00"
    assert line.recovers_day is None and line.lowest_fen == 15_000_000


def _home(rt: Runtime) -> dict:
    from app.main import app

    set_runtime(rt)
    try:
        return TestClient(app).get("/home", headers=OWNER).json()
    finally:
        set_runtime(None)


def _rich_runtime() -> Runtime:
    from app.config import get_settings
    from app.mandate.fixture import demo_owner_public_key_hex
    from app.persistence import InMemoryLedgerStore

    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"cash_fen": 400_000_000}))
    return rt


def test_invoice_finance_today_is_the_alerts_candidates_less_the_plans_advances():
    books, mandate = golden()
    p, actions, _ = _funded(books, mandate)
    candidates = sum(a.amount_fen for a in _candidates(books.state, 0)
                     if a.kind == FundingActionKind.FINANCE_INVOICE and a.facility_id == "FAC-IF")
    advances = sum(a.amount_fen for a in actions if a.kind == FundingActionKind.FINANCE_INVOICE)
    assert (candidates, advances) == (33_600_000, 25_500_000)  # ¥336,000 - ¥255,000
    assert _w(snapshot(books, mandate, 0), "invoice_finance", "FAC-IF", "TODAY").today_fen == candidates - advances == 8_100_000
    assert p.admissible


def test_with_no_plan_invoice_finance_today_is_all_of_the_candidates():
    rt = _rich_runtime()
    books, mandate = Books(state=rt.store.get_state(), obligations=()), rt.store.get_mandate()
    candidates = sum(a.amount_fen for a in _candidates(books.state, 0)
                     if a.kind == FundingActionKind.FINANCE_INVOICE)
    assert _w(snapshot(books, mandate, 0), "invoice_finance", "FAC-IF", "TODAY").today_fen == candidates == 33_600_000


def test_concession_after_equals_the_what_ifs_headroom_and_the_cap_fires_iff_negative():
    books, mandate = golden()
    for params, package in ((WhatIfParams(terms_days=60, discount_bp=120, rebate_bp=100), ASKED),
                            (WhatIfParams(terms_days=45, discount_bp=85, rebate_bp=0, settle_face_fen=25_720_000), OPTION_A),
                            (WhatIfParams(terms_days=55, discount_bp=0, rebate_bp=0, price_adjustment_bp=30), OPTION_B)):
        shown = simulate(books.state, mandate, params, trusted_owner_key_hex=OWNER_KEY, day=0)
        after = capacity_before_after(books, mandate, package, 0, (), trusted_owner_key_hex=OWNER_KEY).after
        assert after is not None
        headroom = _w(after, "concession").today_fen
        assert headroom == shown.forward["headroom_fen"]
        assert (headroom < 0) == ("AGG_CONCESSION_EXCEEDED" in shown.codes)


def test_a_per_buyer_cap_is_read_the_same_way():
    books, mandate = golden()
    bound = resolve_package(books, mandate, ASKED, day=0, commitments=(), trusted_owner_key_hex=OWNER_KEY)
    capped = mandate.model_copy(update={"per_buyer_caps_fen": {"BUYER-1": 300_000}})  # no longer signed: the bound package stands in
    before = snapshot(books, capped, 0)
    assert _w(before, "concession_buyer", buyer="BUYER-1").today_fen == 300_000
    after = capacity_before_after(books, capped, bound, 0, ()).after
    assert after is not None
    # existing 0 + the package's net new, by the verifier's own netting (a negative rebate is not a gain)
    assert _w(after, "concession_buyer", buyer="BUYER-1").today_fen == 300_000 - 2_832_692


@pytest.mark.parametrize("name", ["golden", "short", "public"])
def test_covenant_room_is_non_negative_iff_there_is_no_breach(name: str):
    books, mandate = _books(name)
    # a router run on the public books is seconds; a tightened covenant is searched for far longer, so those books are read once
    variants = ((mandate.min_dscr_bp, mandate.max_leverage_bp),) if name == "public" else (
        (12_500, 25_000), (21_000, 25_000), (12_500, 12_000), (30_000, 9_000))
    for dscr_bp, lev_bp in variants:
        m = mandate.model_copy(update={"min_dscr_bp": dscr_bp, "max_leverage_bp": lev_bp})
        with shared_runs():  # the snapshot and the test ask the router the same question once
            _, _, funded = _funded(books, m)
            s = snapshot(books, m, 0)
        violations = evaluate_covenants(funded, [f for f in books.state.facilities if f.status == FacilityStatus.COMMITTED], m)
        dscr_months = {v.month for v in violations if v.code == ViolationCode.DSCR_BREACH}
        lev_months = {v.month for v in violations if v.code == ViolationCode.LEVERAGE_BREACH}
        for room in s.covenant_months:
            if room.dscr_room_fen is not None:
                assert (room.dscr_room_fen < 0) == (room.month in dscr_months), (name, dscr_bp, room)
            assert (room.leverage_room_fen < 0) == (room.month in lev_months), (name, lev_bp, room)


def test_a_facility_covenant_tightens_the_limit_the_room_is_read_against():
    books, mandate = golden()
    f = next(x for x in books.state.facilities if x.id == "FAC-LINE")
    assert any(c.kind == CovenantKind.CLEAN_DOWN for c in f.covenants)
    loose = snapshot(books, mandate, 0)
    tight = mandate.model_copy(update={"min_dscr_bp": 20_000})
    assert _w(snapshot(books, tight, 0), "dscr_room").lowest_fen < _w(loose, "dscr_room").lowest_fen


# ---------------------------------------------------------------- balances: the rebuild against the engine


def _books(name: str) -> tuple[Books, Mandate]:
    if name == "golden":
        return golden()
    if name == "short":
        return scenario_books("short_facilities")
    raw = json.loads((SCENARIOS / "public_sme.json").read_text(encoding="utf-8"))
    state = FinancialState.model_validate_json(json.dumps(raw["state"]))
    return current_books(state, []), Mandate.model_validate_json(json.dumps(raw["mandate"]))


def _reconcile(books: Books, mandate: Mandate, extra=()) -> None:
    after = books_with(books, extra) if extra else books
    state = after.state
    _, actions, funded = _funded(after, mandate)
    balances = facility_balances(state, funded, actions)
    principal = _debt_principal(state, funded.days[-1].day)
    limits = {f.id: f.limit_fen for f in state.facilities}
    for point in funded.days:
        d = point.day
        landed = sum(b[d] for b in balances.values()) - in_flight(actions, state, d)
        assert landed + principal[d] == point.debt_outstanding_fen, (d, landed, principal[d], point.debt_outstanding_fen)
    for fid, series in balances.items():
        assert max(series) <= limits[fid] or limits[fid] == 0, (fid, max(series), limits[fid])


@pytest.mark.parametrize("name", ["golden", "short", "public"])
def test_balances_plus_debt_equal_the_trajectorys_debt_every_day(name: str):
    books, mandate = _books(name)
    _reconcile(books, mandate)


@pytest.mark.parametrize("key", ["asked", "option_a", "option_b"])
def test_balances_plus_debt_equal_the_trajectorys_debt_with_each_package_in_force(key: str):
    books, mandate = golden()
    bound = resolve_package(books, mandate, PACKAGES[key], day=0, commitments=(), trusted_owner_key_hex=OWNER_KEY)
    _reconcile(books, mandate, bound)


def test_balances_reconcile_on_the_demo_path_at_day_34(books_day34: Books, rt_day34: Runtime):
    _reconcile(books_day34, rt_day34.store.get_mandate())


def test_an_unlanded_lot_is_counted_once_from_its_request_day():
    """ADR-0010 section 2: `drawn_fen` already holds a lot whose cash lands later; the DRAW the projection posts on its
    arrival day is not a second balance (the defect of `covenants.line_balances`)."""
    books, mandate = golden()
    state = books.state
    line = next(f for f in state.facilities if f.id == "FAC-LINE")
    slow = line.model_copy(update={"lead_time_days": 2, "drawn_fen": 5_000_000})
    lot = FundingLot(id="LOT-1", facility_id="FAC-LINE", principal_fen=5_000_000, remaining_fen=5_000_000, request_day=0,
                     arrival_day=2, settled=False)
    state = state.model_copy(update={"facilities": [slow if f.id == "FAC-LINE" else f for f in state.facilities],
                                     "lots": [lot]})
    b = Books(state=state, obligations=())
    s = snapshot(b, mandate, 0)
    window = _w(s, "credit_line", "FAC-LINE")
    _, actions, funded = _funded(b, mandate)
    series = facility_balances(state, funded, actions)["FAC-LINE"]
    assert series[0] == 5_000_000 + sum(a.amount_fen for a in actions if a.facility_id == "FAC-LINE" and a.day == 0)
    assert window.today_fen == 15_000_000 - series[0]
    _reconcile(b, mandate)


def test_the_module_never_uses_line_balances():
    assert not hasattr(capacity_module, "line_balances")
    from pathlib import Path as P
    code = P(capacity_module.__file__).read_text(encoding="utf-8")
    assert "import line_balances" not in code and "clean_down" not in code


# ---------------------------------------------------------------- the recovery day and the window rules


def test_the_recovery_day_is_the_plans_repay_day_and_labelled_assumed():
    books, mandate = golden()
    p, _, _ = _funded(books, mandate)
    draw = next(a for a in p.actions if a.kind == FundingActionKind.DRAW)
    line = _w(snapshot(books, mandate, 0), "credit_line", "FAC-LINE")
    assert line.recovers_day == draw.repay_day == 32 and line.recovery_assumed
    assert not _w(snapshot(books, mandate, 0), "invoice_finance", "FAC-IF", "AS_ISSUED").recovery_assumed


def test_window_runs_on_a_synthetic_series():
    # a floor run: below zero from day 12 to 14, the lowest point on day 13, back at or above on day 15
    w = _window([5, 3, -1, -4, -2, 6, 7], 10, "cash_buffer", floor_run=True)
    assert (w.today_fen, w.lowest_fen, w.lowest_day, w.through_day, w.recovers_day, w.after_fen, w.over_by) == (
        5, -4, 13, 14, 15, 6, True)
    # a level run: the lowest figure held from day 3 through day 5
    w = _window([9, 9, 4, 4, 4, 9], 0, "credit_line")
    assert (w.lowest_fen, w.lowest_day, w.through_day, w.recovers_day, w.after_fen, w.over_by) == (4, 2, 4, 5, 9, False)
    # a series that never rises again has no recovery, and a floor run that never starts is a point
    w = _window([9, 9, 4], 0, "credit_line")
    assert (w.through_day, w.recovers_day, w.after_fen) == (2, None, None)
    w = _window([5, 6, 7], 0, "cash_buffer", floor_run=True)
    assert (w.lowest_fen, w.through_day, w.recovers_day, w.over_by) == (5, 0, 1, False)


def test_a_flat_series_is_one_run_to_the_end():
    w = _window([7, 7, 7], 4, "invoice_finance", reading="TODAY")
    assert (w.lowest_day, w.through_day, w.recovers_day, w.reading) == (4, 6, None, "TODAY")


# ---------------------------------------------------------------- edge rules


def test_no_new_borrowing_makes_every_borrowing_headroom_zero_with_the_reason():
    books, mandate = golden()
    closed = mandate.model_copy(update={"allow_new_borrowing": False})
    s = snapshot(books, closed, 0)
    assert s.no_borrowing_reason == NO_NEW_BORROWING
    for w in s.windows:
        if w.dimension in ("credit_line", "invoice_finance"):
            assert (w.today_fen, w.lowest_fen, w.reason) == (0, 0, NO_NEW_BORROWING)
    assert snapshot(books, mandate, 0).no_borrowing_reason is None


def test_a_source_that_is_not_committed_counts_as_nothing():
    books, mandate = golden()
    s = snapshot(books, mandate, 0)
    assert {w.facility_id for w in s.windows if w.dimension == "credit_line"} == {"FAC-LINE"}  # FAC-GGL is NOT_APPLIED
    pending = books.state.model_copy(update={"facilities": [
        f.model_copy(update={"status": FacilityStatus.PENDING}) if f.id == "FAC-LINE" else f for f in books.state.facilities]})
    s = snapshot(Books(state=pending, obligations=()), mandate, 0)
    assert not [w for w in s.windows if w.dimension == "credit_line"]


def test_a_facility_the_owner_has_not_approved_is_zero_with_the_reason():
    books, mandate = golden()
    unapproved = books.state.model_copy(update={"facilities": [
        f.model_copy(update={"owner_approved": False}) if f.id == "FAC-LINE" else f for f in books.state.facilities]})
    w = _w(snapshot(Books(state=unapproved, obligations=()), mandate, 0), "credit_line", "FAC-LINE")
    assert (w.today_fen, w.reason) == (0, "NOT_OWNER_APPROVED")


def test_leverage_is_undefined_without_ebitda_and_is_a_breach_exactly_when_there_is_debt():
    books, mandate = golden()
    broke = books.state.model_copy(update={"monthly_ebitda_fen": 0})
    s = snapshot(Books(state=broke, obligations=()), mandate, 0)
    leverage = _w(s, "leverage_room")
    assert leverage.reason == "EBITDA_NOT_POSITIVE" and leverage.over_by and leverage.lowest_fen < 0
    debt_free = broke.model_copy(update={"debts": [], "cash_fen": 1_000_000_000})  # no debt, no plan: nothing to breach
    clean = _w(snapshot(Books(state=debt_free, obligations=()), mandate, 0), "leverage_room")
    assert (clean.lowest_fen, clean.over_by, clean.reason) == (0, False, "EBITDA_NOT_POSITIVE")


def test_a_negative_headroom_is_over_by_never_clamped():
    books, mandate = golden()
    after = capacity_before_after(books, mandate, ASKED, 0, (), trusted_owner_key_hex=OWNER_KEY).after
    assert after is not None
    w = _w(after, "concession")
    en, zh = window_view(w, 0, "en"), window_view(w, 0, "zh")
    assert en["today_text"] == "over by ¥23,326.92" and en["lowest_text"] == "over by ¥23,326.92"
    assert zh["today_text"] == "超出 ¥23,326.92"
    assert w.today_fen == -2_332_692  # the contract keeps the signed figure
    over = books.state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen + 100}) if f.id == "FAC-LINE" else f for f in books.state.facilities]})
    line = _w(snapshot(Books(state=over, obligations=()), mandate, 0), "credit_line", "FAC-LINE")
    assert line.over_by and line.lowest_fen == -100


# ---------------------------------------------------------------- display, cache, purity


def test_window_view_carries_the_displays_the_relative_days_and_the_words():
    books, mandate = golden()
    s = snapshot(books, mandate, 0)
    v = window_view(_w(s, "credit_line", "FAC-LINE"), 0, "en")
    assert (v["today_display"], v["after_display"], v["through_when"], v["recovers_when"]) == (
        "¥0.00", "¥150,000.00", "in 31 days", "in 32 days")
    assert v["label"] == "Credit line room" and v["reason_text"] is None
    z = window_view(_w(s, "credit_line", "FAC-LINE"), 0, "zh")
    assert z["recovers_when"] == "32 天后" and z["label"] == "授信额度余量"
    closed = snapshot(books, mandate.model_copy(update={"allow_new_borrowing": False}), 0)
    reasons = window_view(_w(closed, "credit_line", "FAC-LINE"), 0, "zh")["reason_text"]
    assert reasons == "您的授权不允许新增借款"


def test_the_snapshot_is_cached_and_the_books_are_untouched():
    books, mandate = golden()
    before = books.state.model_dump_json()
    first = capacity_before_after(books, mandate, ASKED, 0, (), trusted_owner_key_hex=OWNER_KEY)
    again = capacity_before_after(books, mandate, ASKED, 0, (), trusted_owner_key_hex=OWNER_KEY)
    assert again is first
    assert books.state.model_dump_json() == before and books.obligations == ()


def test_a_candidate_package_needs_the_owners_key_and_an_unbound_one_is_refused():
    books, mandate = golden()
    with pytest.raises(ValueError, match="owner's key"):
        capacity_before_after(books, mandate, ASKED, 0, ())
    bound = resolve_package(books, mandate, ASKED, day=0, commitments=(), trusted_owner_key_hex=OWNER_KEY)
    assert isinstance(bound, BoundPackage) and len(bound.obligations) == 3 and bound.forward_total_fen == 2_832_692
    assert capacity_before_after(books, mandate, bound, 0, ()).after is not None


def test_a_verdicts_bound_obligations_are_the_same_after():
    from app.verifier import evaluate
    from app.whatif.offer import build, context

    books, mandate = golden()
    offer, _ = build(WhatIfParams(terms_days=55, discount_bp=0, rebate_bp=0, price_adjustment_bp=30), context(books.state, 0), 0)
    verdict = evaluate(offer, books.state, mandate, trusted_owner_key_hex=OWNER_KEY, day=0, plans="committed").verdict
    via_verdict = capacity_before_after(books, mandate, verdict, 0, ()).after
    via_candidate = capacity_before_after(books, mandate, OPTION_B, 0, (), trusted_owner_key_hex=OWNER_KEY).after
    assert via_verdict == via_candidate


def test_a_counter_is_read_as_the_offer_it_would_become():
    from app.verifier import evaluate
    from app.whatif.offer import build, context

    books, mandate = golden()
    offer, _ = build(WhatIfParams(terms_days=60, discount_bp=120, rebate_bp=100), context(books.state, 0), 0)
    counter = evaluate(offer, books.state, mandate, trusted_owner_key_hex=OWNER_KEY, day=0, plans="committed").verdict.counters[0]
    after = capacity_before_after(books, mandate, counter, 0, (), trusted_owner_key_hex=OWNER_KEY).after
    assert after is not None
    assert _w(after, "concession").today_fen >= 0  # a counter fits the budget by construction
    assert capacity_before_after(books, mandate, counter, 0, (), trusted_owner_key_hex=OWNER_KEY).label == counter.label


def test_the_demo_path_at_day_34_reads_end_to_end(books_day34: Books, rt_day34: Runtime):
    mandate = rt_day34.store.get_mandate()
    s = snapshot(books_day34, mandate, 34)
    assert s.day == 34 and {w.dimension for w in s.windows} >= {"cash_buffer", "credit_line", "invoice_finance", "concession"}
    # RCV-A is two days past due: the finance headroom does not count it (not yet due is a test), so TODAY is the alerts'
    # candidates less the plan's advances, here as on day 0
    state = books_day34.state
    _, actions, _ = _funded(books_day34, mandate)
    candidates = sum(a.amount_fen for a in _candidates(state, 34) if a.kind == FundingActionKind.FINANCE_INVOICE)
    advances = sum(a.amount_fen for a in actions if a.kind == FundingActionKind.FINANCE_INVOICE)
    assert "RCV-A" not in {a.receivable_id for a in _candidates(state, 34)}
    assert _w(s, "invoice_finance", "FAC-IF", "TODAY").today_fen == candidates - advances


def test_the_public_record_sme_reads_with_the_documented_limit_and_the_cash_buffer():
    books, mandate = _books("public")
    s = snapshot(books, mandate, 0)
    line = _w(s, "credit_line", "FAC-LINE")
    assert line.today_fen == 971_788_326 and line.recovers_day == 25
    assert {w.facility_id for w in s.windows if w.dimension == "invoice_finance"} == set()  # FAC-IF is NOT_APPLIED there
    assert _w(s, "cash_buffer").lowest_fen == read_books(books, mandate, _store(books), 0).lowest_headroom_fen


def _store(books: Books):
    from app.persistence import InMemoryLedgerStore

    store = InMemoryLedgerStore()
    store.put_state(books.state)
    return store


def test_with_no_admissible_plan_the_series_are_the_unfunded_ones_and_say_so():
    books, mandate = golden()
    bare = books.state.model_copy(update={"facilities": [
        f.model_copy(update={"limit_fen": 0}) for f in books.state.facilities if f.kind != FacilityKind.BUYER_EARLY_PAY]})
    s = snapshot(Books(state=bare, obligations=()), mandate, 0)
    assert s.plan_admissible is False
    buffer = _w(s, "cash_buffer")
    assert buffer.over_by and buffer.lowest_fen == -40_500_000 and (s.need_first_day, s.need_last_day) == (12, 31)
    assert not [w for w in s.windows if w.dimension in ("credit_line", "invoice_finance")]  # nothing to draw on
