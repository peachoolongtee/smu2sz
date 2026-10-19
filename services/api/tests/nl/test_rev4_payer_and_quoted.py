"""REV-4 (the 19 Oct review, Hao En): a keyed buyer's message whose payer is the reader ("You can pay …", 你们/贵司 … 支付) or whose
whole text is quoted or forwarded (">", "»", "|", 「…」) was accepted at Tier 1, because the coverage proof's filler list held
"you" and the punctuation is never an unread word. Such a message now waits for the owner; the plain offer is still accepted."""

from __future__ import annotations

import pytest

from tests.nl.conftest import Chat, ops, stored_ops

HELD = [
    "You can pay the ¥420,000 invoice early at a 0.5% discount.",
    "You could pay the ¥420,000 invoice early at a 0.5% discount.",
    "你们可以提前支付420,000元发票，折扣0.5%。",
    "贵司可以提前支付420,000元发票，折扣0.5%。",
    "> We can pay the ¥420,000 invoice early at a 0.5% discount.",
    ">> We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "» We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "| We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "「我们可以提前支付420,000元发票，折扣0.5%。」",
    "> 我们可以提前支付420,000元发票，折扣0.5%。",
]

ACCEPTED = [
    "We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "我们可以提前支付420,000元发票，折扣0.5%。",
]


def _buyer(client, sid: str) -> Chat:
    return Chat(client, sid, actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1")


@pytest.mark.parametrize("text", HELD)
def test_a_reversed_payer_or_a_quoted_message_waits_for_the_owner(client, rt, text: str) -> None:
    r = _buyer(client, f"rev4-{abs(hash(text))}").say(text)
    assert ("ACCEPT_OFFER", "EXECUTED") not in ops(r) and ("ACCEPT_OFFER", "EXECUTED") not in stored_ops(rt)
    assert not r["reply"].startswith(("Agreed", "同意"))


@pytest.mark.parametrize("text", ACCEPTED)
def test_the_plain_offer_is_still_accepted_alone(client, rt, text: str) -> None:
    r = _buyer(client, f"rev4-ok-{abs(hash(text))}").say(text)
    assert ("ACCEPT_OFFER", "EXECUTED") in stored_ops(rt), r["reply"]
