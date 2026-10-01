"""The coverage proof fails closed on unread words (ADR-0005, audit S3 / C7).

A clean early-pay offer on a named invoice below break-even is accepted at Tier 1. The same offer with ANY rider the
compiler did not read (a means of settlement, a set-off, a waiver, a per-week rate, an unsupplied attachment, another
currency, exclusivity, a penalty, a guarantee, an unknown sentence) is not: `autonomy_eligible` is False, the verdict
is NEEDS_OWNER_APPROVAL or stricter, nothing is accepted autonomously, and the notes name the unread words. Through /nl
the reply never says "Agreed" and no commitment is made; for the clean offer it restates the typed terms.

Every sentence was written for this file; the riders are the ones the audit reproduced plus a few more.
"""

from __future__ import annotations

import re

import pytest

from app.compiler import Compiler
from app.domain.fixtures import load_scenario
from app.domain.models import CompiledOffer, CompileStatus, SourceDocument
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate
from tests.nl.conftest import Chat, client, ops, rt  # noqa: F401  (fixtures)

STATE, _ = load_scenario()
MANDATE = load_signed_mandate()
KEY = demo_owner_public_key_hex()

BASE_EN = "Hi, we can pay invoice RCV-A (¥420,000) tomorrow if you give us 0.5% off. Thanks!"
BASE_ZH = "42万的发票我们明天就付清，扣千分之五，谢谢"
UNREAD = "text not read into the terms: "


def _compile(c: Compiler, *texts: str) -> CompiledOffer:
    docs = [SourceDocument(doc_id=f"fc{i}", channel="email" if i == 0 else "attachment", sender_id="BUYER-1",  # type: ignore[arg-type]
                           received_day=0, text=t) for i, t in enumerate(texts)]
    return c.compile_offer(docs, "BUYER-1")


def _verdict(offer: CompiledOffer):
    return evaluate(offer, STATE, MANDATE, trusted_owner_key_hex=KEY).verdict


def _unread(offer: CompiledOffer) -> list[str]:
    """The words the unread-text note names."""
    (note,) = [n for n in offer.autonomy_notes if n.startswith(UNREAD)]
    return re.findall(r"'([^']+)'", note)


def _en(rider: str) -> str:
    return f"{BASE_EN[:-len(' Thanks!')]}{rider} Thanks!"


def _zh(rider: str) -> str:
    return f"{BASE_ZH[:-len('，谢谢')]}，{rider}。谢谢"


# ---------------------------------------------------------------- the base case still passes


def test_the_clean_base_offers_are_still_eligible_and_accepted_at_tier_1(rules_compiler: Compiler) -> None:
    for text in (BASE_EN, BASE_ZH):
        offer = _compile(rules_compiler, text)
        assert offer.status == CompileStatus.COMPILED
        assert offer.autonomy_eligible and offer.autonomy_notes == [], offer.autonomy_notes
        v = _verdict(offer)
        assert (v.outcome.value, v.required_tier.value) == ("ACCEPT", "TIER_1")


# ---------------------------------------------------------------- each rider fails the proof

# (text, a word the unread-text note must name)
RIDERS = {
    "bank_draft_en": (_en(" Settled by a six-month bank acceptance draft."), "settled"),
    "bank_draft_zh": (_zh("用六个月银行承兑汇票结算"), "承兑汇票"),
    "bank_draft_inside_the_clause": (
        "Hi, we can pay invoice RCV-A (¥420,000) tomorrow by bank draft if you give us 0.5% off. Thanks!", "draft"),
    "set_off_en": (_en(" It will be netted against what our sister company owes you."), "netted"),
    "set_off_zh": (_zh("与关联公司欠款抵销"), "关联公司欠款抵销"),
    "waiver_en": (_en(" And you waive all late-payment claims."), "waive"),
    "waiver_zh": (_zh("放弃逾期付款索赔"), "放弃逾期索赔"),
    "per_week_rate": ("Hi, we can pay invoice RCV-A (¥420,000) tomorrow if you give us 0.5% per week off. Thanks!", "week"),
    "per_month_rate_zh": ("42万的发票我们明天就付清，每月扣千分之五，谢谢", "每月"),
    "unsupplied_attachment": (_en(" Per the attached schedule."), "attached"),
    "unsupplied_attachment_zh": (_zh("详见附表"), "详见附表"),
    "usd": ("Hi, we can pay invoice RCV-A (USD 420,000) tomorrow if you give us 0.5% off. Thanks!", "usd"),
    "exclusivity_en": (_en(" You will not supply our competitor."), "not"),
    "exclusivity_zh": (_zh("你们不得向我们的竞争对手供货"), "不得向"),
    "penalty_en": (_en(" A penalty applies if delivery is late."), "penalty"),
    "penalty_zh": (_zh("交货延迟需支付违约金"), "交货延迟需"),
    "guarantee_en": (_en(" The owner gives a personal guarantee."), "owner"),
    "guarantee_zh": (_zh("请老板提供个人担保"), "老板提供"),
    "unknown_sentence": (_en(" The pricing committee's framework applies."), "pricing"),
    "unknown_sentence_zh": (_zh("适用定价委员会的框架"), "适用定价委员会框架"),
    "ahead_of_schedule": ("We will settle the 420k invoice ahead of schedule, 0.7% off please.", "schedule"),
}


@pytest.mark.parametrize("key", list(RIDERS))
def test_a_rider_fails_the_proof_and_goes_to_the_owner(rules_compiler: Compiler, key: str) -> None:
    text, token = RIDERS[key]
    offer = _compile(rules_compiler, text)
    assert offer.autonomy_eligible is False, offer.autonomy_notes
    v = _verdict(offer)
    assert v.outcome.value in ("NEEDS_OWNER_APPROVAL", "REJECT", "NO_VERDICT"), (v.outcome, v.summary)
    if key != "usd":  # the unread-word note comes with every rider; for USD the currency note says it
        names = _unread(offer)
        assert names and len(names) <= 5
        assert any(token in n or n in token for n in names), (token, offer.autonomy_notes)


def test_a_rider_alone_never_rejects_a_clean_offer(rules_compiler: Compiler) -> None:
    """Unread text queues the decision for the owner; it is not by itself a reason to refuse."""
    offer = _compile(rules_compiler, _en(" Settled by a six-month bank acceptance draft."))
    assert _verdict(offer).outcome.value == "NEEDS_OWNER_APPROVAL"


def test_a_foreign_currency_is_named(rules_compiler: Compiler) -> None:
    for text in ("We can pay the $420,000 invoice tomorrow at 0.5% off.", "我们明天付42万美元的发票，扣千分之五。",
                 "Hi, we can pay invoice RCV-A (EUR 420,000) tomorrow if you give us 0.5% off."):
        offer = _compile(rules_compiler, text)
        assert not offer.autonomy_eligible
        assert "non-CNY currency stated" in offer.autonomy_notes, (text, offer.autonomy_notes)


@pytest.mark.parametrize("text", [
    "We can pay the ¥420,000 invoice tomorrow at 0.5% a day off.",
    "We can pay the ¥420,000 invoice tomorrow at 0.5% per month.",
    "42万的发票明天付清，每天扣千分之五。",
])
def test_a_rate_per_a_period_other_than_the_invoice_is_named(rules_compiler: Compiler, text: str) -> None:
    offer = _compile(rules_compiler, text)
    assert not offer.autonomy_eligible
    assert "a rate is stated per a period other than the invoice" in offer.autonomy_notes, offer.autonomy_notes


def test_a_reference_to_an_attachment_that_was_not_supplied_is_named(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, _en(" See the attached schedule."))
    assert "the message refers to a document that was not supplied" in offer.autonomy_notes


def test_unread_words_in_a_second_document_fail_the_proof(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, BASE_EN, "Payment shall be made by letter of credit.")
    assert not offer.autonomy_eligible
    assert {"letter", "credit"} <= set(_unread(offer))


def test_the_notes_name_at_most_five_single_words(rules_compiler: Compiler) -> None:
    offer = _compile(rules_compiler, _en(" Moreover the quarterly rebate programme shall be renegotiated annually by arbitrators."))
    names = _unread(offer)
    assert len(names) == 5 and all(" " not in n for n in names)


def test_the_filler_list_holds_no_word_that_can_carry_a_term() -> None:
    from app.compiler.coverage import _FILLER_EN, _FILLER_ZH

    banned = {"draft", "bill", "acceptance", "offset", "net", "waive", "claim", "claims", "week", "month", "attached",
              "schedule", "usd", "dollars", "per", "not", "no", "all", "any", "every", "also", "unless", "only", "finance"}
    assert not banned & set(_FILLER_EN)
    assert not {"承兑", "汇票", "抵销", "放弃", "附件", "美元", "每周", "每月", "每天", "索赔", "担保"} & set(_FILLER_ZH)


# ---------------------------------------------------------------- through /nl


@pytest.mark.parametrize("key", ["bank_draft_en", "bank_draft_zh", "bank_draft_inside_the_clause", "set_off_en", "waiver_en",
                                 "per_week_rate", "unsupplied_attachment", "usd", "exclusivity_en", "penalty_en",
                                 "guarantee_en", "unknown_sentence"])
def test_a_rider_through_nl_is_not_agreed_and_nothing_is_committed(client, rt, key: str) -> None:  # noqa: F811
    r = Chat(client, f"fc-{key}", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(RIDERS[key][0])
    assert "Agreed" not in r["reply"] and "同意" not in r["reply"], r["reply"]
    assert ("ACCEPT_OFFER", "EXECUTED") not in ops(r)
    assert not [c for c in rt.store.commitments() if c.status.value == "ACTIVE"]
    assert rt.store.get_state().forward_concessions == []


def test_the_clean_offer_through_nl_restates_the_typed_terms(client, rt) -> None:  # noqa: F811
    r = Chat(client, "fc-clean", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(BASE_EN)
    assert ops(r) == [("ACCEPT_OFFER", "EXECUTED")] and r["operations"][0]["tier"] == "TIER_1"
    reply = r["reply"]
    assert "RCV-A" in reply and "0.50%" in reply and "¥420,000.00" in reply
    assert "as proposed" not in reply.lower()
    assert reply.endswith("Nothing else in your message is agreed.")
    assert any(c.status.value == "ACTIVE" for c in rt.store.commitments())


def test_the_clean_offer_through_nl_restates_the_typed_terms_in_chinese(client, rt) -> None:  # noqa: F811
    r = Chat(client, "fc-clean-zh", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(BASE_ZH)
    assert ops(r) == [("ACCEPT_OFFER", "EXECUTED")]
    reply = r["reply"]
    assert "RCV-A" in reply and "0.50%" in reply and "同意贵方提议" not in reply
    assert "其他内容均未同意" in reply


def test_the_restatement_falls_back_when_the_egress_guard_would_block_it(client, rt, monkeypatch) -> None:  # noqa: F811
    from app.nl import offers

    monkeypatch.setattr(offers, "scan", lambda *a, **k: ["leak"])
    r = Chat(client, "fc-fallback", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(BASE_EN)
    assert r["reply"] == "Agreed on the terms we confirmed in writing; nothing else in your message is agreed."
