"""The clock (ADR-0006 §2)."""

from __future__ import annotations

from app.clock import ADVANCE_CLOCK_KIND, advance, close_days
from app.domain.fixtures import load_scenario
from app.domain.models import Mode
from app.financial import project
from app.persistence import InMemoryLedgerStore

H = 150


def _store():
    s = InMemoryLedgerStore()
    s.put_state(load_scenario("golden_sme")[0])
    return s


def test_advancing_posts_flows_and_issues_invoices_without_recording_receipts():
    s0 = load_scenario("golden_sme")[0]
    s1, adv = close_days(s0, 40)
    due = [f for f in s0.flows if f.day < 40 and (f.confirmed or f.amount_fen < 0)]
    assert adv.posted_net_fen == sum(f.amount_fen for f in due)
    # the existing loan's day-30 payment (¥45,000) is paid by the simulated bank as well
    assert adv.debt_service_fen == 4_500_000 and s1.debts[0].principal_fen == s0.debts[0].principal_fen - 4_500_000
    assert s1.cash_fen == s0.cash_fen + adv.posted_net_fen - adv.debt_service_fen
    assert s1.as_of_day == 40 and s1.state_version == s0.state_version + 1
    assert not [f for f in s1.flows if f.id in adv.posted_flow_ids]
    assert [r.status for r in s1.receivables if r.id in {x.id for x in s0.receivables}] == [r.status for r in s0.receivables]
    assert all(ri.next_issue_day >= 40 for ri in s1.recurring_invoices)
    assert all(r.issue_day < 40 for r in s1.receivables if r.id in adv.issued_receivable_ids)


def test_future_cash_is_unchanged_by_closing_days_when_every_receipt_arrived():
    """Closing days moves postings from the projection into cash; it must not change where cash ends up,
    except for receipts that were due and did not arrive (those are no longer assumed)."""
    s0 = load_scenario("golden_sme")[0]
    base = project(s0, [], [], Mode.CONSERVATIVE, H)
    for day in (1, 15, 33, 47, 90):
        s1, _ = close_days(s0, day)
        missed = sum(e.amount_fen for d in base.days[:day] for e in d.events if e.kind.value in ("RECEIPT",))
        t = project(s1, [], [], Mode.CONSERVATIVE, H)
        assert t.days[H].closing_fen == base.days[H].closing_fen - missed, day
        assert t.days[day].opening_fen == base.days[day - 1].closing_fen - missed, day


def test_advance_logs_once_and_is_idempotent():
    st = _store()
    a = advance(st, 34)
    assert a.moved and a.result is not None and a.result.kind == ADVANCE_CLOCK_KIND
    assert st.get_state().as_of_day == 34 and st.verify_chain()
    n = len(st.operations())
    b = advance(st, 34)
    assert not b.moved and len(st.operations()) == n
    assert not advance(st, 10).moved and st.get_state().as_of_day == 34


def test_two_steps_equal_one_step():
    a, b = _store(), _store()
    advance(a, 20)
    advance(a, 60)
    advance(b, 60)
    sa, sb = a.get_state(), b.get_state()
    assert sa.cash_fen == sb.cash_fen and sa.receivables == sb.receivables and sa.flows == sb.flows


def test_scenario_events_add_flows_only_when_the_clock_passes_them():
    from app.domain.fixtures import scenario_events

    ev = scenario_events("golden_sme")
    assert ev and all(e["day"] > 0 for e in ev)  # nothing exists on day 0: golden values are unaffected
    st = _store()
    assert not advance(st, 20, events=ev).added_flow_ids
    a = advance(st, 34, events=ev)
    assert a.added_flow_ids == ["F-PAYROLL-M2"]
    assert [f.day for f in st.get_state().flows if f.id == "F-PAYROLL-M2"] == [42]
    assert not advance(st, 40, events=ev).added_flow_ids  # never twice
    b = advance(st, 60, events=ev)
    assert "F-PAYROLL-M2" in b.posted_flow_ids and st.verify_chain()
