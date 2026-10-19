"""Live mode's two readers (`compiler.cross_check`): a recorded reading replays before any model is called, and a model's reading
of a new buyer message is checked against the rules grammar's. The models are stand-ins; the conftest refuses every connection."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from types import SimpleNamespace

import pytest

from app.api.presentation import abstention_words
from app.compiler import Compiler
from app.compiler.base import OfferResult
from app.compiler.cache import CacheBackend
from app.compiler.cross_check import DISAGREE_FIELD, DISAGREE_REASON, check_against_rules, disputed
from app.compiler.rules import RULES_MODEL_ID, rules_offer
from app.compiler.schema import OfferExtraction
from app.compiler.service import cache_dir
from app.config import get_settings
from app.domain.fixtures import offer_documents
from app.domain.models import CompiledOffer, CompileStatus, ObligationType, SourceDocument
from app.nl.offers import clarification_request

MODEL = "deepseek-flash"


class StandIn:
    """A model that answers with an extraction made from the documents (None: it must not be called), counting its calls."""

    name = "deepseek"

    def __init__(self, extraction: Callable[[Sequence[SourceDocument]], OfferExtraction] | None) -> None:
        self.extraction = extraction
        self.calls = 0

    def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
        self.calls += 1
        if self.extraction is None:
            raise AssertionError("the model was called for a message that has a recorded reading")
        return OfferResult(self.extraction(docs), MODEL)


def new_message(fixture: str = "EX01_PACKAGE") -> list[SourceDocument]:
    """The demo message's own text under a new id: it has no recording, and the rules grammar reads it as it reads the demo's."""
    return [d.model_copy(update={"doc_id": f"NEW-{d.doc_id}"}) for d in offer_documents(fixture)]


def checked(model: StandIn) -> Compiler:
    return Compiler([CacheBackend(cache_dir(get_settings())), model], cross_check=True)


def without(kind: ObligationType) -> Callable[[Sequence[SourceDocument]], OfferExtraction]:
    def read(docs: Sequence[SourceDocument]) -> OfferExtraction:
        ex = rules_offer(docs)
        return ex.model_copy(update={"obligations": [o for o in ex.obligations if o.type != kind]})
    return read


def retyped(kind: ObligationType, to: ObligationType) -> Callable[[Sequence[SourceDocument]], OfferExtraction]:
    def read(docs: Sequence[SourceDocument]) -> OfferExtraction:
        ex = rules_offer(docs)
        return ex.model_copy(update={"obligations": [o.model_copy(update={"type": to}) if o.type == kind else o
                                                     for o in ex.obligations]})
    return read


def flagged(offer: CompiledOffer) -> list[str]:
    return [a.field for a in offer.abstentions if a.field.startswith(DISAGREE_FIELD)]


# ---------------------------------------------------------------- the recorded reading first


def test_a_recorded_demo_message_costs_no_model_call() -> None:
    model = StandIn(None)
    offer = checked(model).compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1")
    assert model.calls == 0 and offer.compiler == "fixture-cache" and offer.status == CompileStatus.COMPILED


def test_the_default_live_compiler_replays_the_recording_and_checks_new_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "live")
    live = Compiler()
    assert live.cross_check and live.backends[0].name == "cache"
    assert live.compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1").compiler == "fixture-cache"
    monkeypatch.setenv("LLM_LIVE_RAW", "1")
    raw = Compiler()
    assert not raw.cross_check and "cache" not in [b.name for b in raw.backends]


def test_a_chain_given_explicitly_is_not_checked_unless_asked() -> None:
    assert not Compiler([StandIn(rules_offer)]).cross_check
    assert Compiler([StandIn(rules_offer)], cross_check=True).cross_check


# ---------------------------------------------------------------- the model's reading, checked against the rules grammar's


def test_a_new_message_the_two_readers_agree_on_is_the_models_reading() -> None:
    model = StandIn(rules_offer)
    offer = checked(model).compile_offer(new_message(), "BUYER-1")
    assert model.calls == 1 and offer.compiler == MODEL
    assert offer.status == CompileStatus.COMPILED and not flagged(offer)
    assert [(o.type, o.rate_bp, o.target_terms_days) for o in offer.obligations] == [
        (ObligationType.IMMEDIATE_DISCOUNT, 120, None), (ObligationType.TERMS_EXTENSION, None, 60),
        (ObligationType.CONTINGENT_REBATE, 100, None)]


def test_a_term_the_model_did_not_read_is_disputed_and_nothing_is_decided() -> None:
    """The model misses the rebate. Its clause then reads as a condition on the other two terms (CONTINGENT, where the rules
    grammar reads them FIRM), so the two readings really do differ on all three, and all three are disputed."""
    offer = checked(StandIn(without(ObligationType.CONTINGENT_REBATE))).compile_offer(new_message(), "BUYER-1")
    assert set(flagged(offer)) == {f"{DISAGREE_FIELD}.{t}" for t in ("IMMEDIATE_DISCOUNT", "TERMS_EXTENSION", "CONTINGENT_REBATE")}
    assert offer.status == CompileStatus.ABSTAINED and not offer.autonomy_eligible
    rebate = next(a for a in offer.abstentions if a.field == f"{DISAGREE_FIELD}.CONTINGENT_REBATE")
    assert rebate.reason == DISAGREE_REASON and rebate.spans  # the rules' passage is quoted for the owner


def test_a_term_the_model_read_as_another_kind_is_disputed() -> None:
    """The rebate read as a discount: the rules' rebate has no match, whatever else the model read."""
    offer = checked(StandIn(retyped(ObligationType.CONTINGENT_REBATE, ObligationType.IMMEDIATE_DISCOUNT))).compile_offer(
        new_message(), "BUYER-1")
    assert f"{DISAGREE_FIELD}.CONTINGENT_REBATE" in flagged(offer)
    assert offer.status in (CompileStatus.ABSTAINED, CompileStatus.CONFLICTING_SOURCES) and not offer.autonomy_eligible


def test_the_rules_grammars_own_answer_is_not_checked_against_itself() -> None:
    class Down(StandIn):
        def extract_offer(self, docs: Sequence[SourceDocument]) -> OfferResult:
            from app.compiler.base import BackendError

            raise BackendError("down")

    offer = checked(Down(None)).compile_offer(new_message(), "BUYER-1")
    assert offer.compiler == RULES_MODEL_ID and not flagged(offer)


# ---------------------------------------------------------------- the comparison itself


def _reading(fixture: str = "EX01_PACKAGE") -> CompiledOffer:
    return Compiler().compile_offer(offer_documents(fixture), "BUYER-1")


def test_a_term_only_the_model_read_stands() -> None:
    model = _reading()
    rules = model.model_copy(update={"obligations": [o for o in model.obligations
                                                     if o.type != ObligationType.CONTINGENT_REBATE]})
    assert disputed(model.obligations, rules.obligations) == {}
    assert check_against_rules(model, rules).status == model.status


def test_a_value_the_rules_left_unread_matches_any_value() -> None:
    model = _reading()
    rules = model.model_copy(update={"obligations": [o.model_copy(update={"rate_bp": None}) for o in model.obligations]})
    assert check_against_rules(model, rules).status == model.status


def test_a_value_the_two_read_differently_is_disputed_with_both_passages() -> None:
    model = _reading()
    terms = next(o for o in model.obligations if o.type == ObligationType.TERMS_EXTENSION)
    rules = model.model_copy(update={"obligations": [o.model_copy(update={"target_terms_days": 90}) if o is terms else o
                                                     for o in model.obligations]})
    out = check_against_rules(model, rules)
    assert flagged(out) == [f"{DISAGREE_FIELD}.TERMS_EXTENSION"]
    assert out.status == CompileStatus.ABSTAINED and not out.autonomy_eligible and [o.model_copy(update={"field_provenance": {}}) for o in out.obligations] == model.obligations
    dispute = next(a for a in out.abstentions if a.field.startswith(DISAGREE_FIELD))
    assert len(dispute.spans) == len({(s.doc_id, s.start, s.end) for s in dispute.spans})  # each passage quoted once


def test_a_reading_that_already_conflicts_keeps_its_status() -> None:
    model = _reading().model_copy(update={"status": CompileStatus.CONFLICTING_SOURCES})
    rules = model.model_copy(update={"obligations": [o.model_copy(update={"rate_bp": 999}) for o in model.obligations]})
    assert check_against_rules(model, rules).status == CompileStatus.CONFLICTING_SOURCES


# ---------------------------------------------------------------- what the buyer and the owner are told


def test_the_buyer_is_asked_to_restate_the_terms_and_no_value_is_echoed() -> None:
    v = SimpleNamespace(violations=[SimpleNamespace(code=None, observed=f"{DISAGREE_FIELD}.TERMS_EXTENSION",
                                                    inputs={"fields": f"{DISAGREE_FIELD}.TERMS_EXTENSION"}, spans=[])])
    en = clarification_request(SimpleNamespace(lang="en"), v)
    zh = clarification_request(SimpleNamespace(lang="zh"), v)
    assert en.startswith("We could not read the terms in your message with certainty") and not any(c.isdigit() for c in en)
    assert zh.startswith("我方无法确定贵方消息中的条款")


def test_the_owner_is_told_in_their_own_words() -> None:
    assert abstention_words(DISAGREE_REASON, ["chat"], "en").startswith("FLOW read a term in this message two different ways")
    assert abstention_words(DISAGREE_REASON, ["chat"], "zh").startswith("FLOW 对这条消息中的某项条款有两种不同的理解")
