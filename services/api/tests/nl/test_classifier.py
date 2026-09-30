"""The optional LLM classifier: it may only choose among enumerated intents and typed slots."""

from __future__ import annotations

import json

import pytest

from app.domain.fixtures import load_scenario
from app.domain.models import SecurityEventKind
from app.egress import canary
from app.mandate import load_signed_mandate
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import NlRequest, handle
from app.nl import classifier as clf
from app.nl.sessions import SessionStore
from app.operations import Executor
from app.persistence import InMemoryLedgerStore

TEXT = "Could you arrange some bridging money for the payroll crunch?"  # no rule matches this


def stub(payload: object, name: str = "stub") -> clf.CallableBackend:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return clf.CallableBackend(name, f"{name}-model", lambda system, user, schema: raw)


def run(backends, text=TEXT):
    store = InMemoryLedgerStore()
    store.put_state(load_scenario()[0])
    store.put_mandate(load_signed_mandate())
    key = demo_owner_public_key_hex()
    ex = Executor(store, trusted_owner_key_hex=key, clock=lambda: 0)
    resp = handle(NlRequest(actor="OWNER", text=text), store=store, executor=ex, day=0, owner_key_hex=key,
                  owner_authenticated=True, sessions=SessionStore(), classifier_backends=backends)
    return resp, store


def test_offline_by_default_cache_miss_falls_back_to_out_of_scope():
    resp, store = run([clf.CacheBackend()])
    assert resp.intent.value == "OUT_OF_SCOPE" and resp.parse_source == "fallback"
    assert store.operations() == []


def test_valid_classification_is_used_but_only_proposes():
    resp, store = run([stub({"intent": "FUND_GAP", "slots": {}, "confidence": 0.9})])
    assert resp.intent.value == "FUND_GAP" and resp.parse_source == "llm:stub-model"
    assert resp.awaiting_confirmation and resp.operations == []  # an LLM-routed plan never runs unconfirmed
    assert store.operations() == []


@pytest.mark.parametrize("payload", [
    {"intent": "DRAW_FACILITY", "slots": {}, "confidence": 0.99},  # not an intent
    {"intent": "APPROVE", "slots": {}, "confidence": 0.99},  # owner decisions are not in its vocabulary
    {"intent": "FUND_GAP", "slots": {"amount_fen": 50_000_000, "facility": "FAC-LINE"}, "confidence": 0.9},  # extra slot
    {"intent": "FUND_GAP", "slots": {"amount_fen": "500000"}, "confidence": 0.9},  # strict types
    "draw the line now",  # not JSON
])
def test_out_of_schema_output_is_discarded(payload):
    resp, store = run([stub(payload)])
    assert resp.intent.value == "OUT_OF_SCOPE" and store.operations() == []


def test_low_confidence_is_ignored():
    resp, _ = run([stub({"intent": "FUND_GAP", "slots": {}, "confidence": 0.3})])
    assert resp.intent.value == "OUT_OF_SCOPE"


def test_canary_in_classifier_output_is_discarded_and_logged():
    token = canary("CANARY-PROMPT").token
    leaky = stub(json.dumps({"intent": "SHOW_STATUS", "slots": {"counterparty_name": token}, "confidence": 0.9}), "leaky")
    good = stub({"intent": "SHOW_STATUS", "slots": {}, "confidence": 0.9}, "good")
    resp, store = run([leaky, good])
    assert resp.parse_source == "llm:good-model"
    assert any(e.kind == SecurityEventKind.DATA_EXTRACTION and "canary" in e.detail for e in store.security_events())
    assert token not in resp.reply


def test_prompt_plants_the_canary_and_lists_only_enumerated_intents():
    assert canary("CANARY-PROMPT").token in clf.SYSTEM_PROMPT
    schema = clf.IntentClassification.model_json_schema()
    assert set(schema["properties"]) == {"intent", "slots", "confidence"}


def test_backend_errors_fall_through(tmp_path):
    def boom(system, user, schema):
        raise RuntimeError("network down")

    resp, _ = run([clf.CallableBackend("down", "m", boom), stub({"intent": "SHOW_STATUS", "slots": {}, "confidence": 1.0})])
    assert resp.intent.value == "SHOW_STATUS"


def test_recorded_cache_entry_replays(tmp_path):
    result = clf.IntentClassification(intent="SHOW_STATUS", confidence=0.95)
    clf.write_cache_entry(TEXT, result, "claude-sonnet-5-5", cache_dir=tmp_path)
    resp, _ = run([clf.CacheBackend(tmp_path)])
    assert resp.intent.value == "SHOW_STATUS" and resp.parse_source == "llm:cache:claude-sonnet-5-5"
