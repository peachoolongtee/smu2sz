"""Random mixed operation sequences: the chain verifies, no Tier-3 operation ever executes, refusals
change nothing, and cash is conserved against an independent model of the simulated bank."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from app.domain.models import (
    Actor,
    AddFacility,
    ChangeMandate,
    DrawFacility,
    IssueEquity,
    OperationStatus,
    PledgeCollateral,
    ReceivePayment,
    RejectOffer,
    RepayFacility,
    SignPersonalGuarantee,
    SubmitInvoiceForFinancing,
    Tier,
)
from app.domain.money import bp, post, simple_interest
from app.operations import parse_operation, security_summary
from tests.operations.builders import Clock, make_executor, new_facility, op, seeded_store

TIER3_KINDS = {"SIGN_PERSONAL_GUARANTEE", "PLEDGE_COLLATERAL", "ISSUE_EQUITY", "CHANGE_MANDATE"}
TIER3_OPS: list[tuple[type, dict]] = [
    (SignPersonalGuarantee, {"facility_id": "FAC-LINE"}),
    (PledgeCollateral, {"facility_id": "FAC-IF"}),
    (IssueEquity, {"amount_fen": 1_000_000}),
    (ChangeMandate, {"new_version": 2}),
]
actors = st.sampled_from(list(Actor))
step = st.one_of(
    st.tuples(st.just("draw_line"), st.integers(1, 20_000_000)),
    st.tuples(st.just("draw_ggl"), st.integers(1, 5_000_000)),
    st.tuples(st.just("repay_line"), st.integers(1, 110)),  # percent of the drawn balance
    st.tuples(st.just("finance"), st.integers(1, 40_000_000)),
    st.tuples(st.just("receive"), st.integers(1, 42_000_000)),
    st.tuples(st.just("tier3"), st.integers(0, len(TIER3_OPS) - 1), actors),
    st.tuples(st.just("add_facility"), actors),
    st.tuples(st.just("tick"), st.integers(0, 4)),
    st.tuples(st.just("decide"), st.booleans(), actors, st.integers(0, 10)),
    st.tuples(st.just("dup")),
    st.tuples(st.just("reject")),
)


class BankModel:
    """An independent restatement of the cash effects, built only from money primitives."""

    def __init__(self, cash: int) -> None:
        self.cash = cash
        self.lots: list[list[int]] = []  # FAC-LINE draws as [day, remaining]
        self.advance: tuple[int, int] | None = None  # (day, amount) on RCV-A

    def apply(self, o: Any, day: int) -> None:
        if isinstance(o, DrawFacility):
            self.cash += o.amount_fen
            self.lots.append([day, o.amount_fen])
        elif isinstance(o, RepayFacility):
            left, interest = o.amount_fen, 0
            for lot in self.lots:
                part = min(left, lot[1])
                if part:
                    interest += post(simple_interest(part, bp(640), day - lot[0]))
                lot[1] -= part
                left -= part
            assert left == 0
            self.cash -= o.amount_fen + interest
        elif isinstance(o, SubmitInvoiceForFinancing):
            self.cash += o.advance_fen
            self.advance = (day, o.advance_fen)
        elif isinstance(o, ReceivePayment):
            self.cash += o.amount_fen
            if self.advance is not None:
                adv_day, adv = self.advance
                periods = max(1, -(-(day - adv_day) // 30))
                self.cash -= adv + post(simple_interest(adv, bp(780), 30 * periods)) + post(bp(25) * adv * periods)
                self.advance = None

    @property
    def line_drawn(self) -> int:
        return sum(lot[1] for lot in self.lots)


def build_op(s: tuple, clock: Clock, model: BankModel) -> Any:
    name = s[0]
    if name == "draw_line":
        return op(DrawFacility, clock, facility_id="FAC-LINE", amount_fen=s[1])
    if name == "draw_ggl":
        return op(DrawFacility, clock, facility_id="FAC-GGL", amount_fen=s[1])
    if name == "repay_line":
        return op(RepayFacility, clock, facility_id="FAC-LINE", amount_fen=max(1, model.line_drawn * s[1] // 100))
    if name == "finance":
        return op(SubmitInvoiceForFinancing, clock, facility_id="FAC-IF", receivable_id="RCV-A", advance_fen=s[1])
    if name == "receive":
        return op(ReceivePayment, clock, actor=Actor.SYSTEM, receivable_id="RCV-A", amount_fen=s[1])
    if name == "tier3":
        cls, fields = TIER3_OPS[s[1]]
        return op(cls, clock, actor=s[2], **fields)
    if name == "add_facility":
        return op(AddFacility, clock, actor=s[1], facility=new_facility("NEW-BANK", f"FAC-N{clock.day}"))
    return op(RejectOffer, clock, offer_id="OFF-1", reason_codes=[])


def run_sequence(store: Any, steps: list[tuple]) -> None:
    clock = Clock(0)
    ex = make_executor(store, clock)
    model = BankModel(store.get_state().cash_fen)
    last: Any = None
    for s in steps:
        name = s[0]
        o: Any = None
        if name == "tick":
            clock.day += s[1]
            continue
        before = store.get_state()
        if name == "decide":
            pending = store.approvals("PENDING")
            if not pending:
                continue
            chosen = pending[s[3] % len(pending)]
            aid = chosen.id
            queued = parse_operation(chosen.op_json)
            result = ex.decide(aid, s[1], s[2])
            o = queued.model_copy(update={"day": clock.day})
        elif name == "dup":
            if last is None:
                continue
            result = ex.execute(last)
            assert result.status == OperationStatus.DUPLICATE
            o = last
        else:
            o = build_op(s, clock, model)
            result = ex.execute(o)
            last = o
        after = store.get_state()
        event(f"{name}: {result.status.value}")
        assert result.seq == len(store.operations())
        if result.status != OperationStatus.EXECUTED:
            assert after == before, (name, result)
            continue
        assert result.tier != Tier.TIER_3
        model.apply(o, clock.day)
        assert after.state_version in (before.state_version, before.state_version + 1)
        assert after.cash_fen == model.cash, (name, result.message)
        line = next(f for f in after.facilities if f.id == "FAC-LINE")
        assert line.drawn_fen == model.line_drawn <= line.limit_fen

    assert store.verify_chain()
    summary = security_summary(store)
    assert summary["unauthorised_executions"] == 0 and summary["facilities_added_by_non_owner"] == 0
    for rec in store.operations():
        if '"status":"EXECUTED"' in rec.result_json:
            assert rec.kind not in TIER3_KINDS


@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(steps=st.lists(step, min_size=1, max_size=40))
def test_random_sequences_in_memory(steps: list[tuple]) -> None:
    run_sequence(seeded_store("memory"), steps)


@pytest.mark.filterwarnings("ignore::ResourceWarning")
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(steps=st.lists(step, min_size=1, max_size=30))
def test_random_sequences_in_sqlite(steps: list[tuple]) -> None:
    store = seeded_store("sqlite", "sqlite://")
    try:
        run_sequence(store, steps)
    finally:
        store.dispose()
