"""End to end through /nl (compile, verify, execute) for the Tier-1 path of ADR-0005.

The four failure PATTERNS of the third held-out report, rewritten here in new words (en and zh), must never be
accepted autonomously: each ends NEEDS_OWNER_APPROVAL or NO_VERDICT and no acceptance executes. A clean, fully
covered early-pay offer below break-even still is accepted at Tier 1. None of these messages is copied from
fixtures/heldout3.
"""

from __future__ import annotations

import pytest

from tests.nl.conftest import Chat, ops

PATTERNS = {
    # 1. an invoice number and amount that are not ours: never bound to the open invoice
    "other_invoice_en": "Re: INV-2025-1904 (CNY 63,800) - we're able to pay this early at 0.5%, kindly reissue the invoice.",
    "other_invoice_zh": "关于发票INV-2025-5512（金额7.3万元），我们可以提前付款，贴息0.5%。",
    # 2. a transfer sum that contradicts the rate
    "net_conflict_en": "We'll clear the ¥420,000 invoice early at 0.4%, so you'll receive ¥405,000 from us tomorrow.",
    "net_conflict_mixed": "420k invoice we pay today at 0.5%, 到账41万。",
    # 3. a yuan deduction that contradicts the percentage
    "deduction_conflict_zh": "42万的货款提前结清，贴息按0.5%算，扣3500元，明天转账。",
    "deduction_conflict_en": "We pay the ¥420,000 invoice tomorrow at 0.5% off, that's a ¥4,200 discount.",
    # 4. an extra operational ask riding on a clean discount
    "extra_ask_en": "Happy to settle the ¥420k invoice early at 0.6%. One request: please route all future deliveries to our "
                    "Shunde depot from now on.",
    "extra_ask_zh": "42万那张我们明天提前付，扣0.6%。还有个事，以后的货麻烦都送到顺德新仓。",
}


@pytest.mark.parametrize("key", list(PATTERNS))
def test_the_tier1_failure_patterns_are_never_accepted_autonomously(client, rt, key: str) -> None:
    r = Chat(client, f"t1-{key}", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(PATTERNS[key])
    v = r["verdict"]
    assert v["outcome"] in ("NEEDS_OWNER_APPROVAL", "NO_VERDICT"), (key, v["outcome"], v["summary"])
    assert ("ACCEPT_OFFER", "EXECUTED") not in ops(r)
    assert rt.store.get_state().forward_concessions == []
    assert "Agreed" not in r["reply"]


def test_a_clean_covered_offer_below_break_even_is_accepted_at_tier1(client, rt) -> None:
    r = Chat(client, "t1-clean", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(
        "Hi, we can pay invoice RCV-A (¥420,000) tomorrow if you give us 0.5% off. Thanks!")
    assert r["verdict"]["outcome"] == "ACCEPT"
    assert ops(r) == [("ACCEPT_OFFER", "EXECUTED")] and r["operations"][0]["tier"] == "TIER_1"
    assert r["reply"] == ("Agreed: payment of invoice RCV-A (¥420,000.00) on day 2 at a 0.50% discount. "
                          "Nothing else in your message is agreed.")
    offer = rt.store.get_offer(r["verdict"]["offer_id"])
    assert offer.autonomy_eligible and offer.autonomy_notes == []


def test_the_same_offer_at_or_above_break_even_is_countered_not_accepted(client) -> None:
    r = Chat(client, "t1-be", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(
        "Hi, we can pay invoice RCV-A (¥420,000) tomorrow if you give us 0.9% off. Thanks!")
    assert r["verdict"]["outcome"] == "COUNTER"
    assert ("ACCEPT_OFFER", "EXECUTED") not in ops(r)
