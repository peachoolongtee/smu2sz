"""Public charge helpers: the rules the engine posts with, exposed for the executor."""

from __future__ import annotations

from app.domain.fixtures import golden_values, load_scenario
from app.domain.models import FundingAction, FundingActionKind, LedgerEventKind, Mode
from app.domain.money import bp, post, simple_interest
from app.financial import finance_invoice_charges, line_interest, project, upfront_fee, whole_periods


def _facility(fid: str):
    state, _ = load_scenario()
    return next(f for f in state.facilities if f.id == fid)


def test_line_interest_matches_golden_value() -> None:
    assert line_interest(15_000_000, 640, 32) == golden_values()["line_interest_150k_32d"] == 84164


def test_whole_periods() -> None:
    assert [whole_periods(d, 30) for d in (0, 1, 29, 30, 31, 60, 61)] == [1, 1, 1, 1, 2, 2, 3]


def test_finance_invoice_charges_bill_whole_periods() -> None:
    f = _facility("FAC-IF")
    interest, fee, periods = finance_invoice_charges(f, 10_000_000, 31)
    assert periods == 2
    assert interest == post(simple_interest(10_000_000, bp(780), 60))
    assert fee == post(bp(25) * 10_000_000 * 2)
    assert upfront_fee(f, 10_000_000) == 0


def test_engine_posts_the_same_charges() -> None:
    state, _ = load_scenario()
    advance = 33_600_000
    traj = project(state, [], [FundingAction(kind=FundingActionKind.FINANCE_INVOICE, facility_id="FAC-IF", day=0,
                                             amount_fen=advance, receivable_id="RCV-A")], Mode.CONSERVATIVE, 40)
    events = next(d for d in traj.days if d.day == 32).events
    posted = {e.kind: -e.amount_fen for e in events if e.ref == "FAC-IF" and e.kind in
              (LedgerEventKind.INTEREST, LedgerEventKind.FEE)}
    interest, fee, _ = finance_invoice_charges(_facility("FAC-IF"), advance, 32 - 3)  # lands day 3, due day 32
    assert posted == {LedgerEventKind.INTEREST: interest, LedgerEventKind.FEE: fee}
