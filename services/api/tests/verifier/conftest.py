"""Shared fixtures for the verifier tests: the golden state, the signed mandate, compiled offers."""

from __future__ import annotations

from functools import lru_cache

import pytest

from app.compiler import compile_offer, compile_term_sheet
from app.domain.fixtures import golden_values, load_offers, load_scenario, offer_documents
from app.domain.models import CompiledOffer, CompiledTermSheet, FinancialState, Mandate
from app.mandate import demo_owner_public_key_hex, load_signed_mandate
from app.verifier import VerdictBundle, evaluate

# spec v2 §6.1: the buyer's next-quarter order (optional, not firm) is the supplier's own knowledge.
# FinancialState has no field for it yet (INTERFACE_CHANGE_REQUEST), so the owner declares it.
GOLDEN_DECLARED = {"period_purchases_fen": {"BUYER-1": 40_000_000}}


@lru_cache
def compiled(offer_id: str) -> CompiledOffer:
    o = load_offers()[offer_id]
    return compile_offer(offer_documents(offer_id), o["counterparty_id"])


@lru_cache
def compiled_term_sheet(offer_id: str) -> CompiledTermSheet:
    return compile_term_sheet(offer_documents(offer_id)[0])


def declared_for(offer_id: str) -> dict:
    return {**GOLDEN_DECLARED, **(load_offers()[offer_id].get("declared_costs") or {})}


@lru_cache
def _bundle(offer_id: str) -> VerdictBundle:
    state, _ = load_scenario()
    return evaluate(compiled(offer_id), state, load_signed_mandate(),
                    trusted_owner_key_hex=demo_owner_public_key_hex(), owner_declared=declared_for(offer_id))


def bundle(offer_id: str) -> VerdictBundle:
    return _bundle(offer_id)


def codes(violations) -> list[str]:
    return list(dict.fromkeys(v.code.value for v in violations))


@pytest.fixture(scope="session")
def g() -> dict:
    return golden_values()


@pytest.fixture(scope="session")
def state() -> FinancialState:
    return load_scenario()[0]


@pytest.fixture(scope="session")
def mandate() -> Mandate:
    return load_signed_mandate()


@pytest.fixture(scope="session")
def key() -> str:
    return demo_owner_public_key_hex()


@pytest.fixture(scope="session")
def offers() -> dict:
    return load_offers()
