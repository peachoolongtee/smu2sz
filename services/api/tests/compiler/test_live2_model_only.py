"""LIVE-2 (the second live language-boundary run of 20 Oct, BO-014): a term or value only the model read stands for a priced
proposal, but autonomy is off and the reading carries MODEL_ONLY_NOTE, so `app.nl.offers.decide` sends no Tier-1 counter on
it. Before the fix such a reading passed the cross-check unchanged, and a live misreading of full-width figures sent a counter."""

from __future__ import annotations

from app.compiler.cross_check import MODEL_ONLY_NOTE, check_against_rules, held_for_owner, model_only
from app.compiler.grounding import build_offer
from app.compiler.prompts import PROMPT_VERSION
from app.compiler.rules import RULES_MODEL_ID, rules_offer
from app.domain.fixtures import offer_documents
from app.domain.models import ObligationType


def _offer(extraction, model_id: str = "deepseek-flash"):
    docs = offer_documents("EX01_PACKAGE")
    return build_offer(docs, "BUYER-1", extraction, model_id, PROMPT_VERSION)


def _rules():
    return rules_offer(offer_documents("EX01_PACKAGE"))


def test_a_reading_the_rules_confirm_in_full_is_not_held() -> None:
    model, rules = _offer(_rules()), _offer(_rules(), RULES_MODEL_ID)
    assert not model_only(model.obligations, rules.obligations)
    checked = check_against_rules(model, rules)
    assert MODEL_ONLY_NOTE not in checked.autonomy_notes


def test_a_term_only_the_model_read_holds_the_reading_for_the_owner() -> None:
    model = _offer(_rules())
    rules = model.model_copy(update={"obligations": [o for o in model.obligations if o.type != ObligationType.CONTINGENT_REBATE]})
    assert model_only(model.obligations, rules.obligations)
    checked = check_against_rules(model, rules)
    assert MODEL_ONLY_NOTE in checked.autonomy_notes and checked.autonomy_eligible is False


def test_when_the_rules_read_nothing_every_term_is_the_models_alone() -> None:
    model = _offer(_rules())
    assert model_only(model.obligations, [])
    held = held_for_owner(model)
    assert held.autonomy_eligible is False and held.autonomy_notes.count(MODEL_ONLY_NOTE) == 1
    assert held_for_owner(held).autonomy_notes.count(MODEL_ONLY_NOTE) == 1  # idempotent
