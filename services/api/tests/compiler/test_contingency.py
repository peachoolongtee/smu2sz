"""F-04: contingency is decided in grounding, whatever the backend labels.

A gain or concession stated under a condition on a future business event (an order, a volume, a
quarter, delivery performance) is CONTINGENT; offer-package conditionality ("we'll settle early if you
extend terms") is not. Backends are mocked with deliberately mislabelled extractions.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from app.compiler import Compiler
from app.compiler.base import OfferResult
from app.compiler.rules import rules_offer
from app.compiler.schema import OfferExtraction, Quote, XObligation
from app.domain.fixtures import load_scenario, offer_documents
from app.domain.models import (
    CompileStatus,
    Contingency,
    ObligationType,
    Outcome,
    SourceDocument,
    ViolationCode,
)
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate

C, F = Contingency.CONTINGENT, Contingency.FIRM


class _Mocked:
    """A backend that returns a fixed extraction (a model's mislabelled answer)."""

    name = "mocked-model"

    def __init__(self, ex: OfferExtraction) -> None:
        self.ex = ex

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        return OfferResult(self.ex, "mocked-model")

    def extract_term_sheet(self, doc: SourceDocument) -> Any:  # pragma: no cover
        raise NotImplementedError


def _doc(text: str, doc_id: str = "D1") -> SourceDocument:
    return SourceDocument(doc_id=doc_id, channel="chat", sender_id="BUYER-1", received_day=0, text=text)


def _ob(doc: SourceDocument, quote: str, t: ObligationType, contingency: Contingency, **kw: Any) -> XObligation:
    base: dict[str, Any] = {
        "type": t, "quotes": [Quote(doc_id=doc.doc_id, text=quote)], "rate_text": None, "amount_text": None,
        "base_kind": "UNSPECIFIED", "base_amount_text": None, "events_per_year_text": None,
        "target_terms_text": None, "current_terms_text": None, "contingency": contingency,
        "duration_kind": "ONE_OFF", "bounded_invoices_text": None, "confidence": 0.9, "unresolved": [],
    }
    base.update(kw)
    return XObligation(**base)


def _ex(*obs: XObligation) -> OfferExtraction:
    return OfferExtraction(obligations=list(obs), quantities=[], unresolved_references=[], missing_material=[],
                           data_requests=[], authority_claims=[], funding_claims=[])


def _compile(docs: list[SourceDocument], ex: OfferExtraction):  # type: ignore[no-untyped-def]
    return Compiler([_Mocked(ex)]).compile_offer(docs, "BUYER-1")


def _labels(offer) -> dict[ObligationType, Contingency]:  # type: ignore[no-untyped-def]
    return {o.type: o.contingency for o in offer.obligations}


# ---------------------------------------------------------------- EX01: package conditionality


def _ex01(label: dict[ObligationType, Contingency]) -> OfferExtraction:
    ex = rules_offer(offer_documents("EX01_PACKAGE"))
    return ex.model_copy(update={"obligations": [o.model_copy(update={"contingency": label[o.type]})
                                                 for o in ex.obligations]})


@pytest.mark.parametrize("label", [
    {ObligationType.IMMEDIATE_DISCOUNT: C, ObligationType.TERMS_EXTENSION: C, ObligationType.CONTINGENT_REBATE: C},
    {ObligationType.IMMEDIATE_DISCOUNT: F, ObligationType.TERMS_EXTENSION: F, ObligationType.CONTINGENT_REBATE: F},
    {ObligationType.IMMEDIATE_DISCOUNT: C, ObligationType.TERMS_EXTENSION: F, ObligationType.CONTINGENT_REBATE: F},
], ids=["deepseek-all-contingent", "all-firm", "mixed"])
def test_ex01_discount_and_extension_firm_rebate_contingent_whatever_the_backend(label) -> None:  # type: ignore[no-untyped-def]
    offer = _compile(offer_documents("EX01_PACKAGE"), _ex01(label))
    assert offer.status == CompileStatus.COMPILED
    assert _labels(offer) == {ObligationType.IMMEDIATE_DISCOUNT: F, ObligationType.TERMS_EXTENSION: F,
                              ObligationType.CONTINGENT_REBATE: C}
    changed = [a for a in offer.abstentions if a.field.startswith("note:") and a.field.endswith(".contingency")]
    assert len(changed) == sum(1 for t, c in label.items() if c != _labels(offer)[t])


def test_ex01_with_a_terse_rebate_quote_still_reads_as_package_conditionality() -> None:
    [doc] = offer_documents("EX01_PACKAGE")
    ex = _ex(
        _ob(doc, "settle the ¥420k early at 1.2%", ObligationType.IMMEDIATE_DISCOUNT, C, rate_text="1.2%",
            base_kind="INVOICE", base_amount_text="¥420k"),
        _ob(doc, "extend our standard terms to 60 days", ObligationType.TERMS_EXTENSION, C,
            target_terms_text="60 days", base_kind="FUTURE_INVOICES", duration_kind="RECURRING_PERPETUAL"),
        _ob(doc, "1%", ObligationType.CONTINGENT_REBATE, C, rate_text="1%", base_kind="PERIOD_PURCHASES"),
    )
    assert _labels(_compile([doc], ex)) == {ObligationType.IMMEDIATE_DISCOUNT: F, ObligationType.TERMS_EXTENSION: F,
                                            ObligationType.CONTINGENT_REBATE: C}


def test_zh_package_conditionality_stays_firm() -> None:
    doc = _doc("如果你们把账期延长到60天，我们提前付款，折扣1.2%。")
    ex = _ex(
        _ob(doc, "账期延长到60天", ObligationType.TERMS_EXTENSION, C, target_terms_text="60天",
            base_kind="FUTURE_INVOICES", duration_kind="RECURRING_PERPETUAL"),
        _ob(doc, "提前付款，折扣1.2%", ObligationType.IMMEDIATE_DISCOUNT, C, rate_text="1.2%", base_kind="INVOICE"),
    )
    assert _labels(_compile([doc], ex)) == {ObligationType.TERMS_EXTENSION: F, ObligationType.IMMEDIATE_DISCOUNT: F}


# ---------------------------------------------------------------- future-event conditions


FR05 = ("If your on-time delivery stays above 98%, we'll pay a 1.5% price premium on next quarter's purchases of "
        "up to ¥400,000; in return give us 2% off next quarter's purchases of up to ¥400,000.")
PREMIUM = "we'll pay a 1.5% price premium on next quarter's purchases of up to ¥400,000"
REBATE = "give us 2% off next quarter's purchases of up to ¥400,000"


def _fr05(label: Contingency) -> tuple[SourceDocument, OfferExtraction]:
    doc = _doc(FR05)
    return doc, _ex(
        _ob(doc, PREMIUM, ObligationType.PRICE_ADJUSTMENT, label, rate_text="1.5%", base_kind="PERIOD_PURCHASES",
            base_amount_text="¥400,000"),
        _ob(doc, REBATE, ObligationType.CONTINGENT_REBATE, C, rate_text="2%", base_kind="PERIOD_PURCHASES",
            base_amount_text="¥400,000"),
    )


def test_fr05_conditional_premium_labelled_firm_is_forced_contingent() -> None:
    doc, ex = _fr05(F)
    offer = _compile([doc], ex)
    assert _labels(offer)[ObligationType.PRICE_ADJUSTMENT] == C
    note = next(a for a in offer.abstentions if a.field == "note:PRICE_ADJUSTMENT.contingency")
    assert "future business event" in note.reason and note.spans[0].text == PREMIUM


@pytest.mark.parametrize("label", [F, C])
def test_fr05_verdict_does_not_depend_on_the_models_label(label: Contingency) -> None:
    """The premium must not net off the rebate: AGG_CONCESSION_EXCEEDED either way, never ACCEPT."""
    doc, ex = _fr05(label)
    offer = _compile([doc], ex)
    state, _ = load_scenario()
    v = evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex()).verdict
    assert v.outcome not in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL)
    assert ViolationCode.AGG_CONCESSION_EXCEEDED in {x.code for x in v.violations}


@pytest.mark.parametrize(("text", "quote", "rate"), [
    ("We'll pay a 1% premium provided that next quarter's volume exceeds ¥1,000,000.", "pay a 1% premium", "1%"),
    ("Subject to next quarter's orders, we'll add a 0.5% price increase.", "add a 0.5% price increase", "0.5%"),
    ("As long as monthly orders stay above ¥300,000, we'll pay a 0.8% premium.", "pay a 0.8% premium", "0.8%"),
    ("Only when the Q3 target is met will we pay a 1% premium.", "pay a 1% premium", "1%"),
    ("Assuming sales hold next quarter, a 0.6% price uplift applies.", "a 0.6% price uplift", "0.6%"),
    ("We'll pay a 0.7% premium if orders reach ¥2,000,000 next month.", "pay a 0.7% premium", "0.7%"),
    ("如果下季度采购超过100万，我们把价格上调0.5%。", "价格上调0.5%", "0.5%"),
    ("若下个月订单达到50万，价格上浮0.5%。", "价格上浮0.5%", "0.5%"),
    ("只要准时交货率保持在98%以上，价格上调0.4%。", "价格上调0.4%", "0.4%"),
    ("前提是明年销量增长，价格上调0.3%。", "价格上调0.3%", "0.3%"),
    ("价格上调0.5%视下季度销量而定。", "价格上调0.5%", "0.5%"),
])
def test_gain_under_a_future_event_condition_is_contingent(text: str, quote: str, rate: str) -> None:
    doc = _doc(text)
    ex = _ex(_ob(doc, quote, ObligationType.PRICE_ADJUSTMENT, F, rate_text=rate, base_kind="FUTURE_INVOICES"))
    assert _labels(_compile([doc], ex)) == {ObligationType.PRICE_ADJUSTMENT: C}


def test_concession_under_a_future_event_condition_is_contingent() -> None:
    doc = _doc("If next quarter's orders exceed ¥1,000,000, we'll settle early at 1%.")
    ex = _ex(_ob(doc, "settle early at 1%", ObligationType.IMMEDIATE_DISCOUNT, F, rate_text="1%", base_kind="INVOICE"))
    assert _labels(_compile([doc], ex)) == {ObligationType.IMMEDIATE_DISCOUNT: C}


def test_unconditional_firm_gain_stays_firm_and_contingent_gain_is_never_made_firm() -> None:
    doc = _doc("We'll accept a 0.45% price adjustment on future invoices.")
    for label in (F, C):
        ex = _ex(_ob(doc, "0.45% price adjustment on future invoices", ObligationType.PRICE_ADJUSTMENT, label,
                     rate_text="0.45%", base_kind="FUTURE_INVOICES"))
        assert _labels(_compile([doc], ex)) == {ObligationType.PRICE_ADJUSTMENT: label}


def test_contingent_discount_stays_contingent_when_the_document_has_a_future_condition_elsewhere() -> None:
    doc = _doc("If Q3 orders exceed ¥1,000,000: we'll talk. We can pay early at 1%.")
    ex = _ex(_ob(doc, "pay early at 1%", ObligationType.IMMEDIATE_DISCOUNT, C, rate_text="1%", base_kind="INVOICE"))
    assert _labels(_compile([doc], ex)) == {ObligationType.IMMEDIATE_DISCOUNT: C}


def test_claimed_prior_concession_keeps_its_label() -> None:
    doc = _doc("If next quarter's orders hold, confirm the 2% rebate we agreed last month.")
    ex = _ex(_ob(doc, "the 2% rebate we agreed last month", ObligationType.CLAIMED_PRIOR_CONCESSION,
                 Contingency.CLAIMED_UNEVIDENCED, rate_text="2%"))
    offer = _compile([doc], ex)
    assert _labels(offer) == {ObligationType.CLAIMED_PRIOR_CONCESSION: Contingency.CLAIMED_UNEVIDENCED}


# ---------------------------------------------------------------- duplicates (task 5)


def test_repeated_phrase_is_booked_once_and_the_dedupe_is_noted() -> None:
    doc = _doc("We can pay early at 1.5%. To repeat: we can pay early at 1.5%.")
    ex = _ex(
        _ob(doc, "We can pay early at 1.5%", ObligationType.IMMEDIATE_DISCOUNT, F, rate_text="1.5%", base_kind="INVOICE"),
        _ob(doc, "we can pay early at 1.5%", ObligationType.IMMEDIATE_DISCOUNT, F, rate_text="1.5%", base_kind="INVOICE"),
    )
    offer = _compile([doc], ex)
    assert offer.status == CompileStatus.COMPILED
    assert [o.rate_bp for o in offer.obligations] == [150]
    note = next(a for a in offer.abstentions if "duplicate" in a.reason)
    assert note.field == "note:obligation:IMMEDIATE_DISCOUNT" and len(note.spans) == 2
    assert note.spans[0].start != note.spans[1].start


def test_rules_grammar_dedupes_a_repeated_rebate(rules_compiler: Compiler) -> None:
    text = "Give us 1% off next quarter. Again, 1% off next quarter, please."
    offer = rules_compiler.compile_offer([_doc(text)], "BUYER-1")
    assert [(o.type, o.rate_bp) for o in offer.obligations] == [(ObligationType.CONTINGENT_REBATE, 100)]
    assert any("duplicate" in a.reason for a in offer.abstentions)


def test_different_values_are_not_deduped() -> None:
    doc = _doc("We can pay early at 1.5%. Or pay early at 1.2%.")
    ex = _ex(
        _ob(doc, "pay early at 1.5%", ObligationType.IMMEDIATE_DISCOUNT, F, rate_text="1.5%", base_kind="INVOICE"),
        _ob(doc, "pay early at 1.2%", ObligationType.IMMEDIATE_DISCOUNT, F, rate_text="1.2%", base_kind="INVOICE"),
    )
    assert sorted(o.rate_bp for o in _compile([doc], ex).obligations) == [120, 150]


def test_duplicate_keeps_the_more_conservative_contingency() -> None:
    doc = _doc("We'll add a 0.5% credit. We'll add a 0.5% credit.")
    ex = _ex(
        _ob(doc, "We'll add a 0.5% credit", ObligationType.PRICE_ADJUSTMENT, F, rate_text="0.5%"),
        _ob(doc, "We'll add a 0.5% credit.", ObligationType.PRICE_ADJUSTMENT, C, rate_text="0.5%"),
    )
    offer = _compile([doc], ex)
    assert [(o.type, o.contingency) for o in offer.obligations] == [(ObligationType.PRICE_ADJUSTMENT, C)]


def test_correction_notes_are_not_reported_as_material_gaps() -> None:
    """A relabel or dedupe note never makes an offer ABSTAINED, and a NO_VERDICT on an abstained offer
    lists only the real gaps."""
    from app.compiler.schema import XMissing

    ex = _ex01({ObligationType.IMMEDIATE_DISCOUNT: C, ObligationType.TERMS_EXTENSION: C,
                ObligationType.CONTINGENT_REBATE: C})
    docs = offer_documents("EX01_PACKAGE")
    assert _compile(docs, ex).status == CompileStatus.COMPILED
    missing = XMissing(obligation_type=ObligationType.IMMEDIATE_DISCOUNT, missing_field="rate_bp",
                       doc_id=docs[0].doc_id, quote="We'll")
    offer = _compile(docs, ex.model_copy(update={"missing_material": [missing]}))
    assert offer.status == CompileStatus.ABSTAINED
    state, _ = load_scenario()
    v = evaluate(offer, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex()).verdict
    assert v.outcome == Outcome.NO_VERDICT
    assert v.violations[0].observed == "IMMEDIATE_DISCOUNT.rate_bp"
