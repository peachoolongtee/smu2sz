"""The rate ceiling decides who may run a plan, not whether it is admissible (review item R01).

- one rate function: the router and the executor's admission price an action with `funding.rates.action_rate`, so an
  advance held 10 days is 32.5% to both, not the 10.84% tariff;
- a plan with a leg above the ceiling is admissible and flagged `needs_owner_approval` with the reason; the flag is on
  the plan, its cost lines and its comparison row;
- among admissible plans one that needs no approval ranks before one that does, however much dearer it is; among plans
  of the same class the cheapest first;
- `MAX_APR_EXCEEDED` is a menu display code now (the tariff itself is above the ceiling), never a reason a plan is
  inadmissible.
"""

from __future__ import annotations

from app.books import current_books
from app.domain.models import FundingActionKind, SubmitInvoiceForFinancing, ViolationCode
from app.domain.money import bp, fmt_pct
from app.funding import compare, menu_view, plan
from app.funding.admission import admit, effective_rate
from app.funding.rates import action_rate, invoice_landing_day
from app.funding.router import _run
from tests.funding.variants import golden, with_facility, with_receivable, without_facilities
from tests.operations.builders import Clock, op


def _dear_advance_world():
    """RCV-A is due on day 13: the golden advance lands on day 3 and is held 10 days, billed as a whole 30-day period."""
    s, m = golden()
    return without_facilities(with_receivable(s, "RCV-A", terms_days=26), "FAC-EARLYPAY"), m


def test_an_advance_held_ten_days_costs_32_percent_to_the_router_and_the_executor_alike():
    s, m = _dear_advance_world()
    fac = next(f for f in s.facilities if f.id == "FAC-IF")
    rcv = next(r for r in s.receivables if r.id == "RCV-A")
    landing = invoice_landing_day(fac, 0, rcv.issue_day)
    rate, how = action_rate(fac, FundingActionKind.FINANCE_INVOICE, amount_fen=21_000_000, landing_day=landing,
                            due_day=rcv.due_day)
    assert (landing, rcv.due_day) == (3, 13) and "held 10 days" in how
    assert fmt_pct(rate) == "32.52%" and rate > bp(m.max_apr_bp)  # not the 10.84% tariff
    # the executor's admission, on the same books, prices it with the same function
    books = current_books(s, [])
    o = op(SubmitInvoiceForFinancing, Clock(0), facility_id="FAC-IF", receivable_id="RCV-A", advance_fen=21_000_000)
    assert effective_rate(o, books)[0] == rate
    assert admit(o, books, m).approval_reason is not None
    # and the router prices the same action the same way
    search = _run(s, books.with_([]), m, "COMMITTED")
    leg = next(a for a in search.ordered(search.best.actions) if a.kind == FundingActionKind.FINANCE_INVOICE)
    assert search.action_pricing(leg.model_copy(update={"amount_fen": 21_000_000}))[0] == rate


def test_a_plan_the_executor_would_queue_is_flagged_by_the_router_with_the_reason():
    s, m = _dear_advance_world()
    p = plan(s, [], m)
    assert p.admissible and p.needs_owner_approval
    adv = next(c for c in p.costs if c.facility_id == "FAC-IF")
    assert adv.needs_owner_approval and "held 10 days" in adv.approval_reason
    assert f"{adv.label}: {adv.approval_reason}" in p.approval_reason and "15.00%" in p.approval_reason
    assert not any(c.needs_owner_approval for c in p.costs if c.facility_id == "FAC-LINE")
    assert p.label.endswith("(needs the owner's approval)")
    rows = compare(s, [], m)
    selected = next(r for r in rows if r.result.value == "SELECTED")
    assert selected.needs_owner_approval and selected.approval_reason == p.approval_reason


def test_the_golden_day_zero_plan_needs_no_one():
    s, m = golden()
    p = plan(s, [], m)
    assert p.total_cost_fen == 271_294 and p.admissible and not p.needs_owner_approval
    assert p.approval_reason == "" and not any(c.needs_owner_approval or c.approval_reason for c in p.costs)
    assert [(c.facility_id, c.fen) for c in p.costs] == [("FAC-LINE", 84_164), ("FAC-IF", 187_130)]
    assert not any(r.needs_owner_approval for r in compare(s, [], m))


def _cheaper_flagged_dearer_unflagged():
    """The line (10.9%) can cover the whole gap and is under the 11% ceiling; the advance (11.22% over its 29 days) is
    flagged and cheaper. The agent can act alone with the line, so the line is the plan."""
    s, m = golden()
    s = with_facility(without_facilities(s, "FAC-EARLYPAY"), "FAC-LINE", limit_fen=40_000_000, rate_bp=1090)
    return s, m.model_copy(update={"max_apr_bp": 1100})


def test_a_plan_that_needs_no_approval_beats_a_cheaper_one_that_does():
    s, m = _cheaper_flagged_dearer_unflagged()
    chosen = plan(s, [], m)
    assert chosen.admissible and not chosen.needs_owner_approval
    assert {a.facility_id for a in chosen.actions} == {"FAC-LINE"}
    cheapest = plan(s, [], m.model_copy(update={"max_apr_bp": 5000}))  # nothing flagged: the plain cheapest
    assert not cheapest.needs_owner_approval and cheapest.total_cost_fen < chosen.total_cost_fen
    assert any(a.facility_id == "FAC-IF" for a in cheapest.actions)
    # the cheaper plan is still shown, as admissible and flagged
    flagged = [r for r in compare(s, [], m) if r.needs_owner_approval]
    assert all(r.result.value == "ADMISSIBLE" and r.cost_fen is not None and r.cost_fen < chosen.total_cost_fen
               for r in flagged)


def test_with_nothing_unflagged_the_cheapest_flagged_plan_is_the_plan():
    s, m = golden()
    tight = m.model_copy(update={"max_apr_bp": 1000})  # only the 6.4% line is within 10%, and it cannot cover the gap
    p = plan(s, [], tight)
    assert p.admissible and p.needs_owner_approval and p.total_cost_fen == 271_294
    assert ViolationCode.MAX_APR_EXCEEDED not in {v.code for v in p.violations}
    assert all(ViolationCode.MAX_APR_EXCEEDED not in r.reasons for r in compare(s, [], tight))


def test_the_menu_still_shows_max_apr_exceeded_and_says_the_owner_must_approve():
    s, m = golden()
    rows = {r.facility_id: r for r in menu_view(s, m.model_copy(update={"max_apr_bp": 1000}))}
    assert ViolationCode.MAX_APR_EXCEEDED in rows["FAC-IF"].reasons and rows["FAC-IF"].needs_owner_approval
    assert rows["FAC-IF"].admissible_for_need  # not a bar: a plan that uses it needs the owner
    assert not rows["FAC-LINE"].needs_owner_approval and not rows["FAC-LINE"].reasons

