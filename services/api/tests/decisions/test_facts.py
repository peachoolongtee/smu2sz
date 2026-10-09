"""The three fact models: strict, ids and numbers only, canonical body, a round trip through both stores."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.decisions import (
    EvaluatedFact,
    QuotedFact,
    SentFact,
    body_json,
    parse_fact,
    record_for,
)
from app.decisions.facts import CounterEconomics, GapLeg, GapPlan, IfDecline, QuotedLeg
from app.domain.money import Ratio
from app.persistence import InMemoryLedgerStore, SqlLedgerStore
from app.persistence.canonical import canonical_json

from .builders import evaluated_fact, quoted, sent_fact

MODELS: list[type[BaseModel]] = [EvaluatedFact, SentFact, QuotedFact, CounterEconomics, GapLeg, GapPlan, QuotedLeg, IfDecline]


def full_sent() -> SentFact:
    return sent_fact(outcome="DEAL", commitment_id="CMT-1", funding=("fund-OFF-1-cooperative-0",)).model_copy(update={
        "counter_economics": CounterEconomics(
            supplier_cost_fen=100, forward_value_fen=200, funding_cost_fen=300, offset_fen=-50, net_fen=250,
            basis_facility_id="FAC-INV", basis_rate=Ratio(num=1084, den=10000)),
        "gap_plan": GapPlan(need_fen=500, total_cost_fen=7, legs=[GapLeg(kind="DRAW", facility_id="FAC-LINE",
                                                                         receivable_id=None, amount_fen=500, lands_day=36)]),
    })


@pytest.mark.parametrize("model", MODELS)
def test_every_fact_model_forbids_unknown_fields(model: type[BaseModel]) -> None:
    assert model.model_config.get("extra") == "forbid"
    assert model.model_config.get("strict") is True and model.model_config.get("frozen") is True


@pytest.mark.parametrize("fact", [evaluated_fact(), full_sent(), quoted()], ids=["EVALUATED", "SENT", "QUOTED"])
def test_an_unknown_field_is_refused(fact: Any) -> None:
    data = json.loads(body_json(fact))
    data["note"] = "free text"
    with pytest.raises(ValidationError):
        type(fact).model_validate_json(json.dumps(data))


def test_the_models_hold_ids_numbers_enums_and_flags_but_no_free_text_field() -> None:
    """Every string field is an id, a code or a kind. A new free-text field fails this list and has to be argued for."""
    allowed_str = {
        "offer_id", "verdict_id", "counter_ids", "recommended_counter_id", "chosen_counter_id", "counter_ids_sent",
        "buyer_profile", "accepted_counter_id", "transcript_hash", "commitment_id", "accept_op_id", "funding_op_ids",
        "funding_blocked", "basis_facility_id", "kind", "facility_id", "receivable_id", "alert_id", "alert_kind",
        "source", "op_id", "outcome", "cost_note",
    }
    string_fields = {name for model in MODELS for name, field in model.model_fields.items() if "str" in str(field.annotation)}
    assert string_fields <= allowed_str, string_fields - allowed_str
    named_for_words = ("text", "sentence", "message", "label", "reason", "display", "detail", "summary", "words")
    all_names = {name for model in MODELS for name in model.model_fields}
    assert [n for n in all_names if any(w in n for w in named_for_words)] == []


def test_money_is_integer_fen_and_days_are_integers() -> None:
    for fact in (quoted(), full_sent()):
        data = json.loads(body_json(fact))

        def walk(node: Any, path: str = "") -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for n, v in enumerate(node):
                    walk(v, f"{path}[{n}]")
            else:
                assert not isinstance(node, float), path

        walk(data)
    with pytest.raises(ValidationError):
        QuotedLeg.model_validate({**quoted().legs[0].model_dump(), "amount_fen": 10.5})


def test_a_rate_is_an_exact_ratio_and_survives_the_round_trip() -> None:
    leg = quoted().legs[0].model_copy(update={"annual_rate": Ratio(num=1084170, den=10_000_000)})
    fact = quoted().model_copy(update={"legs": [leg]})
    record = record_for("alert:A:v1", "alert:A:v1", fact, state_version=1, day=1)
    back = parse_fact(record)
    assert isinstance(back, QuotedFact) and back.legs[0].annual_rate == Ratio(num=1084170, den=10_000_000)


def test_the_body_is_the_canonical_json_of_the_ledger() -> None:
    for fact in (evaluated_fact(), full_sent(), quoted()):
        assert body_json(fact) == canonical_json(fact)
        assert json.loads(body_json(fact)) == json.loads(fact.model_dump_json())


def test_the_row_for_a_fact_names_its_family_and_kind() -> None:
    rows = {
        "EVALUATED": record_for("deal:OFF-1", "V-1", evaluated_fact(), state_version=2, day=4),
        "SENT": record_for("deal:OFF-1", "accept-CMT-1", full_sent(), state_version=2, day=4),
        "QUOTED": record_for("alert:A:v2", "alert:A:v2", quoted(), state_version=2, day=4),
    }
    assert {k: (r.fact, r.family) for k, r in rows.items()} == {
        "EVALUATED": ("EVALUATED", "DEAL"), "SENT": ("SENT", "DEAL"), "QUOTED": ("QUOTED", "FUNDING"),
    }
    assert all((r.state_version, r.day) == (2, 4) and r.seq == 0 and r.recorded_at == "" for r in rows.values())


@pytest.mark.parametrize("fact", [evaluated_fact(), full_sent(), quoted()], ids=["EVALUATED", "SENT", "QUOTED"])
def test_each_fact_round_trips_through_both_stores(fact: Any, tmp_path: Any) -> None:
    for store in (InMemoryLedgerStore(), SqlLedgerStore(f"sqlite:///{tmp_path / 'f.db'}")):
        record = record_for("deal:OFF-1", "K-1", fact, state_version=1, day=0)
        stored = store.add_decision_fact(record)
        assert parse_fact(stored) == fact
        assert parse_fact(store.decision_facts("deal:OFF-1")[0]) == fact
        if isinstance(store, SqlLedgerStore):
            store.dispose()


def test_a_row_that_does_not_parse_gives_none() -> None:
    row = record_for("deal:OFF-1", "V-1", evaluated_fact(), state_version=1, day=0)
    assert parse_fact(replace(row, body_json="not json")) is None
    assert parse_fact(replace(row, body_json="{}")) is None
    assert parse_fact(replace(row, fact="OTHER")) is None
    assert parse_fact(replace(row, fact="SENT")) is None  # a body of another kind
