"""A plural "invoices" in a discount's sentence unbinds the discount (fail closed), except when it plainly belongs to another term that follows
the discount in the same clause (16 Oct: a buyer's reply "pay the 420,000 invoice early … and we need 60-day terms on future invoices" was asked
which invoice it meant). The verifier's counter-examples stay closed."""

from __future__ import annotations

import pytest

from app.compiler import compile_offer
from app.domain.models import CompileStatus, SourceDocument


def _compile(text: str):  # type: ignore[no-untyped-def]
    return compile_offer([SourceDocument(doc_id="plural-" + str(abs(hash(text))), channel="email", sender_id="BUYER-1", received_day=0,
                                         text=text)], "BUYER-1")


def _scope_abstained(text: str) -> bool:
    return any(a.field.endswith("base.receivable_id") for a in _compile(text).abstentions)


def test_a_plural_that_is_another_terms_own_words_does_not_unbind_the_discount() -> None:
    o = _compile("We can pay the 420,000 invoice early, but only with a 1.2% discount, and we need 60-day terms on future invoices.")
    assert o.status == CompileStatus.COMPILED and not o.abstentions


@pytest.mark.parametrize("text", [
    "We'll pay 420,000 early at 1.2% discount, plus a 0.3% price rise accepted, covering both invoices.",
    "价格上调0.3%，两张发票420,000元提前付款，给1.2%折扣。",
    "We accept a 0.3% price rise, and these invoices 420,000 we pay early at 1.2% off.",
    "Pay the 420,000 early at 1.2% off and give us 60-day terms, on both invoices.",
    "账期60天，两张发票420,000元提前付款，给1.2%折扣。",
    "Give us a 0.5% rebate next quarter, and the invoices of 420,000 paid early at 1.2% off.",
    "We will pay these invoices early if you give us 1.2% off.",
], ids=["trailing-both", "zh-two-invoices", "these-before", "both-after-comma", "zh-terms-then-two", "rebate-then-invoices", "these-invoices"])
def test_a_plural_that_may_be_the_discounts_still_unbinds_it(text: str) -> None:
    assert _scope_abstained(text)
