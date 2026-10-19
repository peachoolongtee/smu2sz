"""Field-level reader reconciliation: useful proposals must not gain action authority."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.compiler import Compiler
from app.compiler.cross_check import check_against_rules, field_outcomes
from app.domain.fixtures import load_scenario, offer_documents
from app.domain.models import BaseKind, CompiledOffer, CompileStatus, ObligationType
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import evaluate


def reading() -> CompiledOffer:
    return Compiler().compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1")


def test_agreement_retains_values_and_records_both_readers() -> None:
    offer = reading()
    out = check_against_rules(offer, offer)
    assert out.status == offer.status
    assert all(set(o.field_provenance.values()) == {"both"} for o in out.obligations)
    assert [o.model_copy(update={"field_provenance": {}}) for o in out.obligations] == offer.obligations


@pytest.mark.parametrize("model_missing", [False, True])
def test_one_reader_rate_remains_priced_but_never_autonomous(model_missing: bool) -> None:
    offer = reading()
    term = offer.obligations[0]
    assert term.rate_bp is not None
    incomplete = offer.model_copy(update={"obligations": [term.model_copy(update={"rate_bp": None}), *offer.obligations[1:]]})
    model, rules = (incomplete, offer) if model_missing else (offer, incomplete)
    model = model.model_copy(update={"autonomy_eligible": True})
    out = check_against_rules(model, rules)
    assert out.status == CompileStatus.COMPILED
    assert out.obligations[0].rate_bp == term.rate_bp
    assert out.obligations[0].field_provenance["rate_bp"] == ("rules" if model_missing else "model")
    assert not out.autonomy_eligible


def test_model_only_whole_term_is_reviewable_not_autonomous() -> None:
    model = reading().model_copy(update={"autonomy_eligible": True})
    out = check_against_rules(model, model.model_copy(update={"obligations": []}))
    assert out.status == model.status and not out.autonomy_eligible
    assert all(set(o.field_provenance.values()) == {"model"} for o in out.obligations)


@pytest.mark.parametrize("field,value", [
    ("rate_bp", 999), ("amount_fen", 100), ("days_delta", 14), ("target_terms_days", 90),
    ("effective_day", 3), ("counterparty_id", "BUYER-2"),
])
def test_conflicting_material_values_hold_without_overwriting(field: str, value: object) -> None:
    model = reading()
    original = model.obligations[0].model_copy(update={field: value})
    other = original.model_copy(update={field: "BUYER-3" if field == "counterparty_id" else int(value) + 1})
    model = model.model_copy(update={"obligations": [original]})
    rules = model.model_copy(update={"obligations": [other]})
    assert field_outcomes(original, other)[field] == "conflict"
    out = check_against_rules(model, rules)
    assert out.status == CompileStatus.ABSTAINED and not out.autonomy_eligible
    assert getattr(out.obligations[0], field) == value


def test_duration_end_is_material_not_an_ignored_field() -> None:
    offer = reading()
    term = offer.obligations[0]
    model = offer.model_copy(update={"obligations": [term.model_copy(update={"duration": term.duration.model_copy(update={"end_day": 30})})]})
    rules = offer.model_copy(update={"obligations": [term.model_copy(update={"duration": term.duration.model_copy(update={"end_day": 60})})]})
    assert check_against_rules(model, rules).status == CompileStatus.ABSTAINED


def test_missing_whole_rules_term_is_not_silently_added() -> None:
    rules = reading()
    model = rules.model_copy(update={"obligations": rules.obligations[:-1]})
    out = check_against_rules(model, rules)
    assert out.status == CompileStatus.ABSTAINED
    assert len(out.obligations) == len(model.obligations)


def test_ambiguous_duplicate_pairing_holds() -> None:
    model = reading()
    term = model.obligations[0]
    model = model.model_copy(update={"obligations": [term, term.model_copy(update={"id": "duplicate"})]})
    rules = model.model_copy(update={"obligations": [term]})
    assert check_against_rules(model, rules).status == CompileStatus.ABSTAINED


def test_equal_values_in_separate_documents_do_not_prove_agreement() -> None:
    model = reading()
    term = model.obligations[0]
    other = term.model_copy(update={"spans": [s.model_copy(update={"doc_id": "separate-document"}) for s in term.spans]})
    out = check_against_rules(model.model_copy(update={"obligations": [term]}), model.model_copy(update={"obligations": [other]}))
    assert out.status == CompileStatus.ABSTAINED


def test_unresolved_scope_is_not_rehabilitated_by_a_missing_base() -> None:
    model = reading()
    term = model.obligations[0].model_copy(update={"unresolved": ["scope"], "base": model.obligations[0].base.model_copy(update={"kind": BaseKind.UNSPECIFIED})})
    out = check_against_rules(model.model_copy(update={"obligations": [term]}), model)
    assert out.status == CompileStatus.ABSTAINED


def test_empty_provenance_preserves_historical_serialization() -> None:
    term = reading().obligations[0]
    assert "field_provenance" not in term.model_dump(mode="json")
    labelled = term.model_copy(update={"field_provenance": {"rate_bp": "both"}})
    assert labelled.model_dump(mode="json")["field_provenance"] == {"rate_bp": "both"}


def recorded(item_id: str, mode: str) -> CompiledOffer:
    root = Path(__file__).resolve().parents[2] / "evals/live_frozen"
    data = json.loads((root / f"results_{mode}_2026-10-18.json").read_text())
    row = next(i for i in data["items"] if i["id"] == item_id)
    rec = row["record"]["reading"]
    obs = []
    for ob in rec["obligations"]:
        ob = {**ob, "counterparty_id": row["record"]["counterparty_id"]}
        ob["base"] = {k: v for k, v in ob["base"].items() if k != "amount_display"}
        obs.append(ob)
    abstentions = [{k: a[k] for k in ("field", "reason", "spans")} for a in rec["abstentions"]]
    return CompiledOffer.model_validate_json(json.dumps({
        **{k: rec[k] for k in ("offer_id", "compiler", "prompt_version", "status", "data_requests", "authority_claims", "funding_claims", "autonomy_eligible", "autonomy_notes")},
        "counterparty_id": row["record"]["counterparty_id"], "received_day": 0,
        "doc_ids": list(row["record"]["docs_sent"]), "obligations": obs, "abstentions": abstentions,
    }))


@pytest.mark.parametrize("item_id", ["LF01", "LF03", "LF04"])
def test_recorded_missing_field_cases_become_reviewable_proposals(item_id: str) -> None:
    out = check_against_rules(recorded(item_id, "live_raw"), recorded(item_id, "rules_baseline"))
    assert out.status == CompileStatus.COMPILED, out.abstentions
    assert not out.autonomy_eligible
    terms = next(o for o in out.obligations if o.type == ObligationType.TERMS_EXTENSION)
    assert terms.base.kind == BaseKind.FUTURE_INVOICES
    assert terms.field_provenance["base.kind"] == "rules"
    state, _ = load_scenario()
    result = evaluate(out, state, load_signed_mandate(), trusted_owner_key_hex=demo_owner_public_key_hex()).verdict
    assert result.outcome.value != "NO_VERDICT"
    # Evaluation only: it cannot execute or alter the books.
    assert not out.autonomy_eligible


@pytest.mark.parametrize("item_id", ["LF12", "LF15", "LF20"])
def test_recorded_conflicts_and_hostile_cases_stay_held(item_id: str) -> None:
    out = check_against_rules(recorded(item_id, "live_raw"), recorded(item_id, "rules_baseline"))
    assert out.status in {CompileStatus.ABSTAINED, CompileStatus.CONFLICTING_SOURCES}
    assert not out.autonomy_eligible


def test_one_reader_early_payment_cannot_be_accepted_at_tier_one() -> None:
    from app.compiler.rules import RulesBackend
    from app.domain.models import SourceDocument

    offer = Compiler([RulesBackend()]).compile_offer([SourceDocument(
        doc_id="single-reader", channel="chat", sender_id="BUYER-1", received_day=0,
        text="Hi, we can pay invoice RCV-A (¥420,000) early if you give us 0.5% off. Thanks!",
    )], "BUYER-1")
    assert offer.autonomy_eligible
    state, _ = load_scenario()
    mandate, key = load_signed_mandate(), demo_owner_public_key_hex()
    assert evaluate(offer, state, mandate, trusted_owner_key_hex=key).verdict.outcome.value == "ACCEPT"
    incomplete_rules = offer.model_copy(update={"obligations": [
        o.model_copy(update={"rate_bp": None}) for o in offer.obligations]})
    out = check_against_rules(offer, incomplete_rules)
    v = evaluate(out, state, mandate, trusted_owner_key_hex=key).verdict
    assert v.outcome.value == "NEEDS_OWNER_APPROVAL"
    assert v.required_tier.value == "TIER_2"


def test_rules_backend_failure_cannot_leave_model_only_fields_autonomous(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.compiler.base import BackendError
    from app.compiler.rules import RulesBackend

    offer = reading().model_copy(update={"autonomy_eligible": True})
    compiler = Compiler([RulesBackend()], cross_check=True)

    def unavailable(*_args: object) -> object:
        raise BackendError("no rules reading")

    monkeypatch.setattr(RulesBackend, "extract_offer", unavailable)
    out = compiler._checked([], "BUYER-1", offer, "synthetic-hash")
    assert not out.autonomy_eligible
    assert all(set(o.field_provenance.values()) == {"model"} for o in out.obligations)
