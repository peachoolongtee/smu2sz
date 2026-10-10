"""The buyer context's third case: a buyer with an expected order and no open invoice gets the rebate lever only."""

from __future__ import annotations

import pytest

from app.domain.models import ExpectedOrder, FinancialState, Mandate, ObligationType, Outcome
from app.verifier import evaluate
from app.whatif.offer import Context, EarlyPayContext, RebateOnlyContext, build, context
from app.whatif.params import WhatIfParamError, WhatIfParams

ORDER = ExpectedOrder(counterparty_id="BUYER-2", label="next quarter", start_day=92, end_day=182, amount_fen=25_000_000)


@pytest.fixture
def with_order(state: FinancialState) -> FinancialState:
    """The golden books with an expected order for BUYER-2 (the golden books carry one for BUYER-1 only)."""
    return state.model_copy(update={"expected_orders": [*state.expected_orders, ORDER]})


def test_a_buyer_with_none_of_the_three_levers_is_refused(state: FinancialState):
    assert not any(o.counterparty_id == "BUYER-2" for o in state.expected_orders)
    with pytest.raises(WhatIfParamError) as err:
        context(state, 0, "BUYER-2")
    assert str(err.value) == "FLOW has no terms, payment or rebate lever to value for Dongguan Office Supplies Ltd. yet."


def test_an_expected_order_without_an_invoice_is_the_rebate_lever(with_order: FinancialState):
    ctx = context(with_order, 0, "BUYER-2")
    assert ctx == RebateOnlyContext("BUYER-2", ORDER)
    with pytest.raises(WhatIfParamError):  # code written for an invoice refuses the buyer as before
        _ = ctx.receivable


def test_the_rebate_only_build_emits_the_rebate_clause_alone(with_order: FinancialState):
    ctx = context(with_order, 0, "BUYER-2")
    offer, text = build(WhatIfParams(terms_days=30, discount_bp=0, rebate_bp=80), ctx)
    assert [(o.type, o.counterparty_id, o.rate_bp, o.base.amount_fen) for o in offer.obligations] == [
        (ObligationType.CONTINGENT_REBATE, "BUYER-2", 80, 25_000_000)]
    clause = "0.80% rebate on the expected next quarter order of ¥250,000.00."
    assert text.endswith(clause) and offer.obligations[0].spans[0].text == clause
    # the clause is the recurring path's own: BUYER-1 (terms, price and rebate levers) words it the same way
    _, text1 = build(WhatIfParams(terms_days=45, discount_bp=0, rebate_bp=80), context(with_order, 0, "BUYER-1"))
    assert text1.endswith("0.80% rebate on the expected next quarter order of ¥400,000.00.")


def test_the_rebate_only_build_ignores_terms_and_price_and_refuses_an_early_payment(with_order: FinancialState):
    ctx = context(with_order, 0, "BUYER-2")
    offer, text = build(WhatIfParams(terms_days=60, discount_bp=0, rebate_bp=0, price_adjustment_bp=30), ctx)
    assert offer.obligations == [] and text.endswith("no change to the current terms.")
    with pytest.raises(WhatIfParamError):
        build(WhatIfParams(terms_days=30, discount_bp=50, rebate_bp=0), ctx)


def test_the_verifier_evaluates_the_rebate_only_offer(with_order: FinancialState, mandate: Mandate, key: str):
    ctx = context(with_order, 0, "BUYER-2")
    offer, _ = build(WhatIfParams(terms_days=30, discount_bp=0, rebate_bp=80), ctx)
    verdict = evaluate(offer, with_order, mandate, trusted_owner_key_hex=key, day=0, commitments=(), plans="committed").verdict
    assert verdict.outcome == Outcome.NEEDS_OWNER_APPROVAL and verdict.violations == []  # Tier 2: not a pure early-pay discount


def test_the_other_cases_are_unchanged(state: FinancialState, with_order: FinancialState):
    assert isinstance(context(state), Context) and isinstance(context(state, 0, "BUYER-1"), Context)
    assert isinstance(context(with_order, 0, "BUYER-1"), Context)  # an invoice and a recurring invoice win over the order
    no_rec = with_order.model_copy(update={"recurring_invoices": [], "expected_orders": [
        ORDER, ExpectedOrder(counterparty_id="BUYER-1", label="next quarter", start_day=92, end_day=182, amount_fen=40_000_000)]})
    assert isinstance(context(no_rec, 0, "BUYER-1"), EarlyPayContext)  # an open invoice and no recurring invoice
