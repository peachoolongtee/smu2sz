"""Wave 1 of map #47: the shared types and `marginal_impact`, pinned to the collections spike's recorded oracle
(fixtures/strategy/collections_both.json). Every figure is compared as integer fen, against the oracle's `fen` values
and against the literal the brief's pin table names."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.display import displayed
from app.api.runtime import Runtime
from app.books import Books
from app.domain.models import FundingLot, Mandate, Mode
from app.financial import project
from app.financial.charges import finance_invoice_charges
from app.strategy import (
    CandidatePackage,
    MarginalImpact,
    ScenarioState,
    marginal_impact,
    scenario_inflow,
    scenario_received,
)

_ORACLE = Path(__file__).resolve().parents[4] / "fixtures" / "strategy" / "collections_both.json"
TEN_THOUSAND_YUAN = 1_000_000


def _oracle() -> list[dict[str, Any]]:
    books: list[dict[str, Any]] = json.loads(_ORACLE.read_text(encoding="utf-8"))["books"]
    return books


def _fen(m: dict[str, Any]) -> int:
    return int(m["fen"])


def _effects() -> list[Any]:
    out = []
    for b in _oracle():
        for row in b["ranking"]:
            for e in row.get("effects", []):
                out.append(pytest.param(b["books"], row["receivable"], e, id=f"{b['books']}-{row['receivable']}-{e['receipt_day']}"))
    return out


def _impact(rt: Runtime, books: Books, receivable_id: str, on_day: int) -> MarginalImpact:
    s = scenario_received(books, receivable_id, on_day)
    mandate = rt.store.get_mandate()
    return marginal_impact(books, s, mandate, store=rt.store, day=books.state.as_of_day, label=s.label)


@pytest.fixture(scope="module")
def mandate0(rt_day0: Runtime) -> Mandate:
    return rt_day0.store.get_mandate()


@pytest.fixture(scope="module")
def mandate34(rt_day34: Runtime) -> Mandate:
    return rt_day34.store.get_mandate()


# ---------------------------------------------------------------- the books are the oracle's books


def test_the_day34_books_are_the_demo_path_books(books_day34: Books, books_day0: Books):
    s = books_day34.state
    assert s.as_of_day == 34 and s.cash_fen == 30_000_000
    assert sorted((r.id, r.outstanding_fen, r.due_day) for r in s.receivables if r.status == "OPEN") == [
        ("RCV-A", 16_280_000, 32), ("RI:BUYER-1:2", 42_000_000, 47), ("RI:BUYER-1:32", 42_000_000, 77)]
    assert books_day0.state.as_of_day == 0


# ---------------------------------------------------------------- the pins (brief section 7, Wave 1)


def test_rcv_a_received_by_day_12_on_the_day0_books(rt_day0: Runtime, books_day0: Books):
    effect = next(e for r in _oracle()[0]["ranking"] if r["receivable"] == "RCV-A"
                  for e in r["effects"] if e["receipt_day"] == 12)
    mi = _impact(rt_day0, books_day0, "RCV-A", 12)
    assert -mi.posted_cost_delta_fen == _fen(effect["saving"]) == 311_393  # ¥3,113.93
    assert mi.before_cost_fen == 311_393 and mi.after_cost_fen == 0
    assert (mi.first_breach_before, mi.first_breach_after) == (12, None)  # the day-12 breach is removed
    assert mi.after_need_fen == _fen(effect["after"]["need"]) == 0
    assert mi.breach_days_removed == effect["breach_days_removed"] == 20
    assert mi.alerts_removed == ["RESERVE_BREACH_AHEAD"] and mi.alerts_added == []
    assert displayed(mi.model_dump())["posted_cost_delta_display"] == "−¥3,113.93"


def test_rcv_a_residual_received_today_on_the_day34_books(rt_day34: Runtime, books_day34: Books):
    effect = next(e for r in _oracle()[1]["ranking"] if r["receivable"] == "RCV-A"
                  for e in r["effects"] if e["receipt_day"] == 34)
    assert _fen(next(r for r in _oracle()[1]["ranking"] if r["receivable"] == "RCV-A")["outstanding"]) == 16_280_000
    mi = _impact(rt_day34, books_day34, "RCV-A", 34)
    assert -mi.posted_cost_delta_fen == _fen(effect["saving"]) == 137_461  # ¥1,374.61
    assert mi.after_need_fen == _fen(effect["after"]["need"]) == 3_720_000  # ¥37,200
    assert mi.after_cost_fen == _fen(effect["after"]["cost"]) == 33_149  # ¥331.49
    assert mi.after_needs_owner is True and effect["after"]["plan_needs_owner_approval"] is True
    assert mi.before_need_fen == 20_000_000 and mi.before_cost_fen == 170_610
    assert mi.alerts_removed == ["RECEIVABLE_PAST_DUE", "RESERVE_HEADROOM_LOW"]


def test_a_receipt_five_days_early_is_a_cost_and_is_kept_negative(rt_day34: Runtime, books_day34: Books):
    effect = next(e for r in _oracle()[1]["ranking"] if r["receivable"] == "RI:BUYER-1:32"
                  for e in r["effects"] if e["receipt_day"] == 72)
    mi = _impact(rt_day34, books_day34, "RI:BUYER-1:32", 72)
    assert mi.posted_cost_delta_fen == 7_609  # +¥76.09: dearer than the standing plan, never clamped to zero
    assert -mi.posted_cost_delta_fen == _fen(effect["saving"]) == -7_609
    assert mi.after_cost_fen - mi.before_cost_fen == 7_609
    assert displayed(mi.model_dump())["posted_cost_delta_display"] == "¥76.09"
    assert mi.breach_days_removed == 0 and mi.alerts_removed == [] and mi.alerts_added == []


# ---------------------------------------------------------------- every receipt the spike recorded


@pytest.mark.parametrize(("books_name", "rid", "effect"), _effects())
def test_every_recorded_effect_is_reproduced_to_the_fen(
        books_name: str, rid: str, effect: dict[str, Any], rt_day0: Runtime, books_day0: Books,
        rt_day34: Runtime, books_day34: Books):
    rt, books = (rt_day0, books_day0) if books_name == "day 0" else (rt_day34, books_day34)
    base = next(b for b in _oracle() if b["books"] == books_name)["baseline"]
    mi = _impact(rt, books, rid, effect["receipt_day"])
    after = effect["after"]
    assert -mi.posted_cost_delta_fen == _fen(effect["saving"])
    assert (mi.before_cost_fen, mi.before_need_fen) == (_fen(base["cost"]), _fen(base["need"]))
    assert (mi.after_cost_fen, mi.after_need_fen) == (_fen(after["cost"]), _fen(after["need"]))
    assert mi.need_delta_fen == _fen(after["need"]) - _fen(base["need"])
    assert (mi.first_breach_before, mi.first_breach_after) == (base["first_breach_day"], after["first_breach_day"])
    assert mi.breach_days_removed == effect["breach_days_removed"]
    assert mi.alerts_removed == effect["alerts_cleared"]
    assert mi.alerts_added == [k for k in after["alerts"] if k not in base["alerts"]]
    assert (mi.before_needs_owner, mi.after_needs_owner) == (
        base["plan_needs_owner_approval"], after["plan_needs_owner_approval"])


# ---------------------------------------------------------------- identity and shape


def test_the_same_books_against_themselves_change_nothing(rt_day34: Runtime, books_day34: Books, mandate34: Mandate):
    mi = marginal_impact(books_day34, books_day34, mandate34, store=rt_day34.store, day=34, label="same")
    zeros = {k: v for k, v in mi.model_dump().items() if k.endswith("_delta_fen") or k == "breach_days_removed"}
    assert zeros == {"need_delta_fen": 0, "posted_cost_delta_fen": 0, "lowest_headroom_delta_fen": 0,
                     "budget_used_delta_fen": 0, "breach_days_removed": 0}
    assert mi.alerts_removed == [] and mi.alerts_added == []
    assert mi.first_breach_before == mi.first_breach_after == 42
    assert (mi.before_cost_fen, mi.before_need_fen) == (mi.after_cost_fen, mi.after_need_fen) == (170_610, 20_000_000)
    assert mi.label == "same"


def test_a_scenario_that_changes_nothing_is_the_same_as_the_books(rt_day0: Runtime, books_day0: Books, mandate0: Mandate):
    unchanged = ScenarioState(state=books_day0.state, label="as is", assumption="assumes nothing",
                              source_state_version=books_day0.state.state_version, day=0)
    mi = marginal_impact(books_day0, unchanged, mandate0, store=rt_day0.store, day=0)
    assert mi.posted_cost_delta_fen == mi.need_delta_fen == mi.breach_days_removed == 0
    assert mi.alerts_removed == mi.alerts_added == []


def test_a_scenario_is_hypothetical_labelled_and_leaves_the_books_alone(books_day34: Books):
    before = books_day34.state.model_dump_json()
    s = scenario_received(books_day34, "RCV-A", 34, label="RCV-A received today")
    assert s.hypothetical is True and s.label == "RCV-A received today"
    assert s.day == 34 and s.source_state_version == books_day34.state.state_version
    assert s.assumption == "assumes the ¥162,800.00 from Foshan Home Retail Co. arrives today"
    assert books_day34.state.model_dump_json() == before  # a model_copy: the books are untouched
    with pytest.raises(ValidationError):
        ScenarioState.model_validate({**s.model_dump(), "hypothetical": False})
    with pytest.raises(ValidationError):
        s.label = "other"  # type: ignore[misc]
    assert scenario_received(books_day34, "RCV-A", 34).label == "RCV-A received today"


def test_display_strings_are_fmt_yuan_strings(rt_day0: Runtime, books_day0: Books):
    shown = displayed(_impact(rt_day0, books_day0, "RCV-A", 12).model_dump())
    assert shown["before_cost_display"] == "¥3,113.93" and shown["after_cost_display"] == "¥0.00"
    assert shown["before_need_display"] == "¥405,000.00" and shown["need_delta_display"] == "−¥405,000.00"
    assert shown["posted_cost_delta_display"] == "−¥3,113.93"


# ---------------------------------------------------------------- scenario_received

def test_a_receipt_moved_to_a_later_day_changes_the_copy_only(books_day0: Books):
    before = books_day0.state.model_dump_json()
    s = scenario_received(books_day0, "RCV-A", 12)
    moved = next(r for r in s.state.receivables if r.id == "RCV-A")
    assert (moved.due_day, moved.status, moved.settled_fen) == (12, "OPEN", 0)  # the receipt moves on the copy
    assert s.state.cash_fen == books_day0.state.cash_fen  # no cash credited before it arrives
    assert [r for r in s.state.receivables if r.id != "RCV-A"] == [r for r in books_day0.state.receivables if r.id != "RCV-A"]
    assert books_day0.state.model_dump_json() == before  # the books keep their contract
    assert next(r for r in books_day0.state.receivables if r.id == "RCV-A").due_day == 32
    assert s.assumption == "assumes the ¥420,000.00 from Foshan Home Retail Co. arrives in 12 days"


def test_a_receipt_on_the_due_day_is_the_contract(books_day0: Books):
    assert scenario_received(books_day0, "RCV-A", 32).state == books_day0.state


def test_a_receipt_today_settles_the_receivable_and_credits_cash(books_day0: Books):
    s = scenario_received(books_day0, "RCV-A", 0)
    paid = next(r for r in s.state.receivables if r.id == "RCV-A")
    assert (paid.status, paid.settled_fen) == ("SETTLED", paid.face_fen)
    assert s.state.cash_fen == books_day0.state.cash_fen + 42_000_000


@pytest.mark.parametrize(("rid", "day"), [
    ("RCV-A", 35),  # overdue on day 34: only today
    ("RCV-A", 33),  # before today
    ("RI:BUYER-1:2", 48),  # after its due day
    ("RI:BUYER-1:2", 20),  # before today
    ("NOPE", 34),
])
def test_impossible_receipts_are_refused(books_day34: Books, rid: str, day: int):
    with pytest.raises(ValueError):
        scenario_received(books_day34, rid, day)


def test_a_settled_receivable_has_nothing_to_collect(books_day34: Books):
    paid = scenario_received(books_day34, "RCV-A", 34).state
    with pytest.raises(ValueError, match="nothing is left to collect"):
        scenario_received(Books(state=paid, obligations=()), "RCV-A", 34)


def test_a_financed_receivable_pays_the_lender_first(rt_day34: Runtime, books_day34: Books, mandate34: Mandate):
    s0 = books_day34.state
    rcv = next(r for r in s0.receivables if r.id == "RI:BUYER-1:2")
    advance = rcv.face_fen * 8000 // 10_000
    lot = FundingLot(id="LOT-T", facility_id="FAC-IF", principal_fen=advance, remaining_fen=advance, request_day=30,
                     arrival_day=33, receivable_id=rcv.id, settled=True)
    fac = next(f for f in s0.facilities if f.id == "FAC-IF")
    financed = s0.model_copy(update={
        "receivables": [r.model_copy(update={"status": "FINANCED", "advance_fen": advance, "advance_facility_id": "FAC-IF"})
                        if r.id == rcv.id else r for r in s0.receivables],
        "facilities": [f.model_copy(update={"drawn_fen": advance}) if f.id == "FAC-IF" else f for f in s0.facilities],
        "lots": [*s0.lots, lot]})
    interest, fee, _ = finance_invoice_charges(fac, advance, 34 - lot.arrival_day)
    s = scenario_received(Books(state=financed, obligations=()), rcv.id, 34)
    paid = next(r for r in s.state.receivables if r.id == rcv.id)
    assert (paid.status, paid.settled_fen, paid.advance_fen) == ("SETTLED", rcv.face_fen, 0)
    assert s.state.cash_fen == s0.cash_fen + rcv.face_fen - (advance + interest + fee)  # the lender takes the claim
    assert next(f for f in s.state.facilities if f.id == "FAC-IF").drawn_fen == 0
    assert all(x.id != "LOT-T" for x in s.state.lots)
    project(s.state, [], [], Mode.CONSERVATIVE, mandate34.horizon_days)  # the lots still sum to the balances
    with pytest.raises(ValueError, match="financed"):
        scenario_received(Books(state=financed, obligations=()), rcv.id, 40)
    marginal_impact(Books(state=financed, obligations=()), s, mandate34, store=rt_day34.store, day=34)


# ---------------------------------------------------------------- scenario_inflow


def test_an_inflow_appends_one_confirmed_flow(books_day34: Books):
    s = scenario_inflow(books_day34, TEN_THOUSAND_YUAN, 40)
    [new] = s.state.flows[len(books_day34.state.flows):]
    assert (new.day, new.amount_fen, new.confirmed) == (40, TEN_THOUSAND_YUAN, True)
    assert s.hypothetical is True and s.label == "¥10,000.00 arrives on day 40"
    assert s.assumption == "assumes ¥10,000.00 arrives in 6 days"
    assert s.state.cash_fen == books_day34.state.cash_fen


def test_an_inflow_can_leave_again_on_a_later_day(books_day34: Books):
    s = scenario_inflow(books_day34, TEN_THOUSAND_YUAN, 40, outflow_day=70)
    new = s.state.flows[len(books_day34.state.flows):]
    assert [(f.day, f.amount_fen) for f in new] == [(40, TEN_THOUSAND_YUAN), (70, -TEN_THOUSAND_YUAN)]
    assert len({f.id for f in s.state.flows}) == len(s.state.flows)


@pytest.mark.parametrize(("amount", "day", "out"), [(0, 40, None), (-5, 40, None), (TEN_THOUSAND_YUAN, 33, None),
                                                     (TEN_THOUSAND_YUAN, 40, 33)])
def test_a_bad_inflow_is_refused(books_day34: Books, amount: int, day: int, out: int | None):
    with pytest.raises(ValueError):
        scenario_inflow(books_day34, amount, day, outflow_day=out)


@pytest.mark.parametrize("which", [0, 34])
def test_the_curve_points_are_reproduced_by_the_spikes_pair(
        which: int, rt_day0: Runtime, books_day0: Books, rt_day34: Runtime, books_day34: Books):
    """The spike's curve: the plan's cost with the money arriving on day d + 30 less its cost with it arriving on d."""
    rt, books = (rt_day0, books_day0) if which == 0 else (rt_day34, books_day34)
    curve = {p["arrival_day"]: _fen(p["worth"]) for p in next(
        b for b in _oracle() if b["books"] == f"day {which}")["cash_price_curve"]["points"]}
    mandate = rt.store.get_mandate()
    for d in (which, which + 1, which + 8, which + 9, which + 14, which + 27, which + 30, which + 31, which + 70):
        mi = marginal_impact(scenario_inflow(books, TEN_THOUSAND_YUAN, d + 30), scenario_inflow(books, TEN_THOUSAND_YUAN, d),
                             mandate, store=rt.store, day=which)
        assert -mi.posted_cost_delta_fen == curve[d], d


# ---------------------------------------------------------------- CandidatePackage


def test_a_package_on_the_grid_is_accepted():
    p = CandidatePackage(buyer_id="BUYER-1", terms_days=55, price_bp=30, early_pay_bp=85,
                         early_pay_face_fen=25_720_000, rebate_bp=125)
    assert (p.terms_days, p.price_bp, p.early_pay_bp, p.rebate_bp) == (55, 30, 85, 125)
    assert CandidatePackage(buyer_id="BUYER-1", terms_days=45).early_pay_face_fen is None
    with pytest.raises(ValidationError):
        p.terms_days = 60  # type: ignore[misc]


@pytest.mark.parametrize("bad", [
    {"terms_days": 53},  # off the 5-day grid
    {"terms_days": 3},
    {"terms_days": 25},  # below the what-if range
    {"terms_days": 95},  # above it
    {"terms_days": 45, "price_bp": 7},  # off the 5 bp grid
    {"terms_days": 45, "early_pay_bp": 7},
    {"terms_days": 45, "rebate_bp": 12},
    {"terms_days": 45, "price_bp": 105},  # above the price range
    {"terms_days": 45, "early_pay_bp": 205},
    {"terms_days": 45, "rebate_bp": 205},
    {"terms_days": 45, "price_bp": -5},
    {"terms_days": 45, "early_pay_face_fen": 10_050},  # off the ¥100 grid
    {"terms_days": 45, "early_pay_face_fen": 0},
])
def test_a_package_off_the_grid_or_the_ranges_is_rejected(bad: dict[str, int]):
    with pytest.raises(ValidationError):
        CandidatePackage(buyer_id="BUYER-1", **bad)  # type: ignore[arg-type]
