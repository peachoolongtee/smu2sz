"""REV-4 and LIVE-1 (the reviews of 19 and 20 Oct): a keyed buyer's message whose payer is the reader ("You can pay ...",
你们/贵司 ... 支付), that is quoted or forwarded, or that carries hidden formatting characters must wait for the owner; the plain
offer, in its ordinary wordings, is still accepted alone. BLOCKERS are the 31 bypasses of the first REV-4 fix found by Hao En's
probe (docs/security/evidence/2026-10-19/int-3be038ae/probe/); PLAIN are the 22 plain offers that probe saw accepted alone."""

from __future__ import annotations

import pytest

from app.compiler.base import BackendError
from app.compiler.service import Compiler
from app.domain.models import SourceDocument
from tests.nl.conftest import Chat, ops, stored_ops

WRITER = [
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
BLOCKERS = [
    "You're able to pay the ¥420,000 invoice early at a 0.5% discount.",
    "You'll pay the ¥420,000 invoice early at a 0.5% discount.",
    "You'd pay the ¥420,000 invoice early at a 0.5% discount.",
    "You'll settle the ¥420,000 invoice early at a 0.5% discount.",
    "You, if ok, can pay the ¥420,000 invoice early at a 0.5% discount.",
    "You, if ok, will pay the ¥420,000 invoice early at a 0.5% discount.",
    "You - can pay the ¥420,000 invoice early at a 0.5% discount.",
    "You: pay the ¥420,000 invoice early at a 0.5% discount.",
    "You can, if ok, pay the ¥420,000 invoice early at a 0.5% discount.",
    "You can do the payment of the ¥420,000 invoice early at a 0.5% discount.",
    "Thanks you can pay the ¥420,000 invoice early at a 0.5% discount.",
    "你们，可以提前支付420,000元发票，折扣0.5%。",
    "你们 可以 提前支付420,000元发票，折扣0.5%。",
    "你们也可以就是想提前支付420,000元发票，折扣0.5%。",
    "贵司，提前支付420,000元发票，折扣0.5%。",
    "Hi, \"We can pay the ¥420,000 invoice early at a 0.5% discount.\"",
    "Hi, “We can pay the ¥420,000 invoice early at a 0.5% discount.”",
    "'We can pay the ¥420,000 invoice early at a 0.5% discount.'",
    "‘We can pay the ¥420,000 invoice early at a 0.5% discount.’",
    "＂We can pay the ¥420,000 invoice early at a 0.5% discount.＂",
    "› We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "‹ We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "│ We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "¦ We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "〉 We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "《我们可以提前支付420,000元发票，折扣0.5%》",
    "\u200b> We can pay the ¥420,000 invoice early at a 0.5% discount.",
    " > We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "«We can pay the ¥420,000 invoice early at a 0.5% discount.»",
    "„We can pay the ¥420,000 invoice early at a 0.5% discount.“",
    "```\nWe can pay the ¥420,000 invoice early at a 0.5% discount.\n```",
]
PLAIN = [
    "We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "We will pay the ¥420,000 invoice early at a 0.5% discount.",
    "Can we pay the ¥420,000 invoice early at a 0.5% discount?",
    "Hi, we can pay the ¥420,000 invoice early at a 0.5% discount. Thanks!",
    "Thank you, we can pay the ¥420,000 invoice early at a 0.5% discount.",
    "Thank you we can pay the ¥420,000 invoice early at a 0.5% discount.",
    "Could you confirm, we can pay the ¥420,000 invoice early at a 0.5% discount.",
    "Please confirm: we can pay the ¥420,000 invoice early at a 0.5% discount.",
    "We can pay you the ¥420,000 invoice early at a 0.5% discount.",
    "Can we pay you the ¥420,000 invoice early at a 0.5% discount?",
    "Hope you are well, we can pay the ¥420,000 invoice early at a 0.5% discount.",
    "Hope you are well we can pay the ¥420,000 invoice early at a 0.5% discount.",
    "Thanks to you we can pay the ¥420,000 invoice early at a 0.5% discount.",
    "Thanks! We can pay the ¥420,000 invoice early at a 0.5% discount.",
    "我们可以提前支付420,000元发票，折扣0.5%。",
    "您好，我们可以提前支付420,000元发票，折扣0.5%。",
    "您好我们可以提前支付420,000元发票，折扣0.5%。",
    "谢谢你们，我们可以提前支付420,000元发票，折扣0.5%。",
    "感谢贵司，我们可以提前支付420,000元发票，折扣0.5%。",
    "请您确认，我们可以提前支付420,000元发票，折扣0.5%。",
    "我们可以付清420,000元发票，提前付款，折扣0.5%。",
    "谢谢您，我们可以提前支付420,000元发票，折扣0.5%。",
]
HIDDEN = [
    "We can pay the full ¥420,000 invoice early for 0.\u200b5% off.",  # BO-016 of the language-boundary set
    "We can pay the ¥420,000 invoice early at a 0.5\u2060% discount.",
    "We can pay the ¥420,000 invoice early at a 0.5% dis\u00adcount.",
    "\u202eWe can pay the ¥420,000 invoice early at a 0.5% discount.",
]


def _buyer(client, sid: str) -> Chat:
    return Chat(client, sid, actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1")


@pytest.mark.parametrize("text", WRITER + BLOCKERS)
def test_a_reversed_payer_or_a_quoted_message_waits_for_the_owner(client, rt, text: str) -> None:
    r = _buyer(client, f"rev4-{abs(hash(text))}").say(text)
    assert ("ACCEPT_OFFER", "EXECUTED") not in ops(r) and ("ACCEPT_OFFER", "EXECUTED") not in stored_ops(rt)
    assert not r["reply"].startswith(("Agreed", "同意"))


@pytest.mark.parametrize("text", HIDDEN)
def test_a_message_with_hidden_characters_runs_nothing(client, rt, text: str) -> None:
    r = _buyer(client, f"live1-{abs(hash(text))}").say(text)
    assert [o for o in stored_ops(rt) if o[1] == "EXECUTED"] == [], r["reply"]  # not even a counter (LIVE-1)


@pytest.mark.parametrize("text", PLAIN)
def test_the_plain_offer_is_still_accepted_alone(client, rt, text: str) -> None:
    r = _buyer(client, f"rev4-ok-{abs(hash(text))}").say(text)
    assert ("ACCEPT_OFFER", "EXECUTED") in stored_ops(rt), r["reply"]


class _ModelMustNotRead:
    name = "model"

    def extract_offer(self, docs):
        raise AssertionError("a model read a message that carries hidden formatting characters")


def test_hidden_characters_never_reach_a_model() -> None:
    doc = SourceDocument(doc_id="d1", channel="chat", sender_id="BUYER-1", received_day=0, text=HIDDEN[0])
    offer = Compiler(backends=[_ModelMustNotRead()]).compile_offer([doc], "BUYER-1")  # type: ignore[list-item]
    assert offer.compiler != "model"


def test_a_model_still_reads_a_clean_message() -> None:
    class _Fails(_ModelMustNotRead):
        def extract_offer(self, docs):
            raise BackendError("model consulted")

    doc = SourceDocument(doc_id="d1", channel="chat", sender_id="BUYER-1", received_day=0, text=PLAIN[0])
    Compiler(backends=[_Fails()]).compile_offer([doc], "BUYER-1")  # type: ignore[list-item]  # falls back to the rules
