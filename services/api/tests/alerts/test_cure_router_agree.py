"""The alert's committed cure and the router do not disagree about whether a cure needs the owner (review item R01):
`above_apr_cap` on a suggestion is the executor's own test (`funding.rates.action_rate` against the mandate's ceiling),
the same one that flags the router's plan legs."""

from __future__ import annotations

from app.books import current_books
from app.domain.models import FundingActionKind, SubmitInvoiceForFinancing
from app.funding import plan
from app.funding.admission import admit
from tests.alerts.test_cure_cost import _breach, client, rt  # noqa: F401  (fixtures)
from tests.alerts.test_repay_alert import to_day34
from tests.operations.builders import Clock, op


def test_day34_the_cure_the_alert_flags_is_the_cure_the_executor_queues_and_the_router_flags(client, rt):  # noqa: F811
    to_day34(client, rt)
    [s] = _breach(client)["suggested"]
    assert s["operation_kind"] == "SUBMIT_INVOICE_FOR_FINANCING" and s["above_apr_cap"] is True
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    books = current_books(state, rt.store.commitments())
    o = op(SubmitInvoiceForFinancing, Clock(state.as_of_day), facility_id=s["facility_id"],
           receivable_id=s["receivable_id"], advance_fen=s["amount_fen"])
    assert admit(o, books, mandate).approval_reason is not None  # the executor queues it for the owner
    p = plan(books.state, books.with_([]), mandate)
    legs = [(a, c) for a, c in zip(p.actions, p.costs, strict=True)
            if a.kind == FundingActionKind.FINANCE_INVOICE and a.receivable_id == s["receivable_id"]]
    for _, line in legs:  # whatever the router chose for this invoice is flagged too
        assert line.needs_owner_approval and p.needs_owner_approval


def test_day0_the_cure_under_the_ceiling_is_flagged_by_none_of_them(client, rt):  # noqa: F811
    from app.alerts import AlertKind
    from tests.alerts.test_alerts import _of, _run, _store

    [b] = _of(_run(_store()), AlertKind.RESERVE_BREACH_AHEAD)
    inv = next(s for s in b.suggested if s.operation_kind == "SUBMIT_INVOICE_FOR_FINANCING")
    state, mandate = _store().get_state(), _store().get_mandate()
    books = current_books(state, [])
    o = op(SubmitInvoiceForFinancing, Clock(0), facility_id=inv.facility_id, receivable_id=inv.receivable_id,
           advance_fen=inv.amount_fen)
    assert inv.above_apr_cap is False and admit(o, books, mandate).approval_reason is None
    assert not plan(books.state, books.with_([]), mandate).needs_owner_approval
