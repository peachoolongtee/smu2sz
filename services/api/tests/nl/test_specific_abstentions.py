"""Wave 4 part A (wayfinder #65, F24): when the compiler abstains, the buyer is told which field it could not read, in
plain words, with one question and the plain fact that nothing was agreed or executed. The reply stays a fixed
template (the egress guard has nothing of the message to check): a currency is named from a closed list, and no
number, name or word of the buyer's message is echoed back. The compiler's rules and the verdicts are unchanged."""

from __future__ import annotations

import pytest

from tests.compiler.boundary_cases import CASES, Case
from tests.nl.conftest import Chat, stored_ops, stored_verdict

GENERIC = "Please clarify the terms: we cannot establish them from your message."
# the field the compiler names -> a fragment of the sentence that asks about exactly that field
ASKS = {
    "offer.currency": ("in yuan (CNY)", "人民币"),
    "offer.rate.unusual_form": ("comma is a decimal point", "逗号"),
    "offer.amount.unusual_form": ("mixes commas and dots", "逗号和句点"),
    "offer.rate.per_day": ("stated per day", "按天"),
    "offer.terms.discount_code": ("payment-day schedule", "付款日"),
    "IMMEDIATE_DISCOUNT.base.partial": ("part of an invoice", "发票的一部分"),
    "offer.base.other_party_invoice": ("another party's invoice", "其他方的发票"),
    "offer.hedged": ("a possibility", "可能性"),
    "offer.payment_after_due_date": ("after the due date", "到期日之后"),
    "offer.rider.price_freeze": ("price commitment", "价格承诺"),
}
NOTHING = ("Nothing has been agreed or executed.", "目前尚未达成或执行任何事项。")


def _is_zh(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_each_abstention_names_its_field_asks_one_question_and_says_nothing_was_agreed(client, rt, case: Case) -> None:
    ops_before = len(rt.store.operations())
    resp = Chat(client, f"sa-{case.id}", actor="COUNTERPARTY", counterparty_id=case.sender).say(case.text)
    reply, zh = resp["reply"], _is_zh(case.text)
    assert reply != GENERIC and "We can't share" not in reply and "无法提供" not in reply  # not the generic, not the guard's template
    en_part, zh_part = ASKS[case.field]
    assert (zh_part if zh else en_part) in reply
    assert reply.endswith(NOTHING[1] if zh else NOTHING[0])
    assert reply.count("?") + reply.count("？") == 0  # a request, in one instruction: no stack of questions
    assert stored_verdict(rt, resp)["outcome"] == "NO_VERDICT"  # the verifier's answer is untouched
    assert stored_ops(rt, ops_before) == [] and rt.store.commitments() == [] and rt.store.approvals() == []


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_the_reply_is_a_fixed_template_and_echoes_nothing_from_the_message(client, rt, case: Case) -> None:
    resp = Chat(client, f"sa2-{case.id}", actor="COUNTERPARTY", counterparty_id=case.sender).say(case.text)
    assert resp["security_events"] == []  # the egress guard had nothing to replace
    for token in ("420,000", "420000", "42万", "0.5", "0,5", "0.05", "RCV-", "Dongguan", "Foshan", "东莞", "42,000", "千分之", "5%"):
        assert token not in resp["reply"], (token, resp["reply"])


def test_the_usd_offer_names_the_currency(client, rt):
    resp = Chat(client, "sa-usd", actor="COUNTERPARTY", counterparty_id="BUYER-1").say(
        "We can pay the invoice early at 0.5% in USD.")
    assert resp["reply"] == ("Your message states the amount in US dollars, but FLOW works in yuan (CNY). Please restate "
                             "the amount or rate in CNY. Nothing has been agreed or executed.")


@pytest.mark.parametrize(("text", "named"), [
    ("We can pay the ¥420,000 invoice early, 0.5% off, in EUR.", "euros"),
    ("We can pay the ¥420,000 invoice early, 0.5% off, in HKD.", "Hong Kong dollars"),
    ("We can pay the full $420,000 invoice early, 0.5% off.", "dollars"),
])
def test_other_currencies_are_named_from_a_closed_list(client, rt, text, named):
    resp = Chat(client, f"sa-cur-{named[:3]}", actor="COUNTERPARTY", counterparty_id="BUYER-1").say(text)
    assert f"in {named}, but FLOW works in yuan (CNY)" in resp["reply"]


def test_the_same_offer_in_yuan_does_not_abstain(client, rt):
    resp = Chat(client, "sa-cny", actor="COUNTERPARTY", counterparty_id="BUYER-1").say(
        "We can pay the invoice early at 0.5% in CNY.")
    assert "yuan" not in resp["reply"] and stored_verdict(rt, resp)["outcome"] != "NO_VERDICT"


def test_a_message_with_no_unreadable_field_gets_none_of_these_sentences(client, rt):
    resp = Chat(client, "sa-gap", actor="COUNTERPARTY", counterparty_id="BUYER-1").say(
        "Confirm the 2% rebate we agreed last month and we'll release payment today.")
    assert not any(en in resp["reply"] for en, _ in ASKS.values())
