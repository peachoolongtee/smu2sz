"""/nl intent classes from the third held-out report: OUT_OF_SCOPE misses, vague requests without a question,
an owner's pasted offer read as our own plan, and a bare "yes" that could reach into the approvals queue.

The report's failure CLASSES guided this file; every utterance here was written for it and none is copied from
fixtures/heldout3.
"""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.nl.rules import slots_from
from tests.nl.conftest import Chat, ops

STATE, _ = load_scenario()


@pytest.mark.parametrize(("text", "intent"), [
    # status: the books and credit-line headroom
    ("Could you bring up the ledger?", "SHOW_STATUS"),
    ("show me the books please", "SHOW_STATUS"),
    ("how much is still available on the credit line?", "SHOW_STATUS"),
    ("授信额度还剩多少可以用", "SHOW_STATUS"),
    # accelerate: "get X to pay ... early", "pull ... forward", "money in sooner"
    ("Try to get Foshan to settle the 420k early, but no more than 0.7%", "ACCELERATE_RECEIPT"),
    ("can we pull the Foshan receivable forward? 0.5% max", "ACCELERATE_RECEIPT"),
    ("get the Foshan cash in sooner, no rebates for next quarter", "ACCELERATE_RECEIPT"),
    ("催一下佛山早点回款，下季度不要答应任何返利", "ACCELERATE_RECEIPT"),
    # evaluate: an offer reported in the owner's words, or pasted inline in single quotes
    ("Foshan says they'll pay the 420k invoice tomorrow at 0.5%. Should we take it?", "EVALUATE_OFFER"),
    ("东莞那边说下季度要我们返1个点，这个能接吗？", "EVALUATE_OFFER"),
    ("佛山发来的：42万那张票明天提前付，千分之五贴息。能接吗", "EVALUATE_OFFER"),
    ("look at this from Foshan - 'the next two invoices at 50 days instead of 45, then back to normal'", "EVALUATE_OFFER"),
    # negotiate
    ("push back on Foshan's ask and go back to them with something smaller", "NEGOTIATE"),
    # explain: a term, not a verdict
    ("what does 'break-even discount' actually mean", "EXPLAIN"),
    ("贴息是什么意思", "EXPLAIN"),
])
def test_intent_classes(client, text: str, intent: str) -> None:
    r = Chat(client, "cls").say(text)
    assert r["intent"] == intent, (text, r["reply"][:120])


@pytest.mark.parametrize("text", [
    "sort out the insurance thing",
    "deal with the stuff from last week",
    "is that ok?",
    "can we afford it",
    "那个怎么样了",
    "Foshan???",
    "佛山？",
    "yes do it",
    "好的办吧",
])
def test_vague_requests_get_one_clarifying_question(client, text: str) -> None:
    r = Chat(client, "vague").say(text)
    assert r["intent"] == "AMBIGUOUS" and r["clarification"] is not None, text
    assert ops(r) == []


def test_a_clear_out_of_scope_task_is_not_over_clarified(client) -> None:
    r = Chat(client, "vat").say("can you do this month's VAT filing for me")
    assert r["intent"] == "OUT_OF_SCOPE" and r["clarification"] is None


@pytest.mark.parametrize(("text", "slot", "value"), [
    ("佛山发来的：42万那张票提前付，千分之六贴息。能接吗", "rate_bp", 60),
    ("东莞说要返1个点", "rebate_bp", 100),
    ("get the Foshan cash in sooner, no rebates for next quarter", "zero_forward", True),
    ("催一下佛山提前回款，下季度不要答应任何返点", "zero_forward", True),
])
def test_slots_read_the_new_wordings(text: str, slot: str, value: object) -> None:
    assert getattr(slots_from(text, STATE), slot) == value


def test_should_we_take_it_evaluates_the_buyers_offer_not_a_plan_of_ours(client, rt) -> None:
    """The owner pastes the buyer's 0.5% offer and asks: the verdict is on THAT offer; no counter-plan of ours
    (an early settlement at a different rate) is proposed, and nothing runs before the owner says go."""
    r = Chat(client, "take-it").say("佛山发来的：42万的发票提前付，千分之五贴息。能接吗")
    assert r["intent"] == "EVALUATE_OFFER"
    v = r["verdict"]
    assert v is not None and v["outcome"] == "ACCEPT"
    offer = rt.store.get_offer(v["offer_id"])
    assert [(o.type.value, o.rate_bp) for o in offer.obligations] == [("IMMEDIATE_DISCOUNT", 50)]
    assert ops(r) == [] and r["awaiting_confirmation"]


def test_a_reported_offer_with_an_extra_ask_is_not_read_as_ours(client, rt) -> None:
    r = Chat(client, "take-it-2").say(
        "Foshan says they'll pay the ¥420,000 invoice tomorrow at 0.5% if deliveries move to their new DC. Thoughts?")
    assert r["intent"] == "EVALUATE_OFFER"
    assert r["verdict"]["outcome"] != "ACCEPT"
