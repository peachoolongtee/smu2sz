"""Books and packages for the buyer-exposure tests (map #88, ticket #96): the fixtures' scenarios as `Books` plus the
Demo's three packages for Foshan (EX01 as asked, Option A and Option B), each as a `CandidatePackage`.

A helper, not a conftest: the tests import what they use. Nothing here writes; every state is a fresh load."""

from __future__ import annotations

from functools import cache

from app.books import Books, current_books
from app.domain.fixtures import load_scenario
from app.domain.models import FinancialState, Mandate
from app.mandate.fixture import demo_owner_public_key_hex, load_signed_mandate
from app.strategy.types import CandidatePackage

OWNER_KEY = demo_owner_public_key_hex()
FOSHAN = "BUYER-1"

# EX01 as asked: early settlement of the whole RCV-A at 1.2%, 60-day terms, 1% off the next quarter's order.
ASKED = CandidatePackage(buyer_id=FOSHAN, terms_days=60, early_pay_bp=120, rebate_bp=100)
# Option A: ¥257,200 of RCV-A settled early at 0.85%, the terms as they are.
OPTION_A = CandidatePackage(buyer_id=FOSHAN, terms_days=45, early_pay_bp=85, early_pay_face_fen=25_720_000)
# Option B: 55-day terms at a 0.30% price.
OPTION_B = CandidatePackage(buyer_id=FOSHAN, terms_days=55, price_bp=30)
PACKAGES = {"asked": ASKED, "option_a": OPTION_A, "option_b": OPTION_B}


@cache
def _scenario(name: str) -> tuple[FinancialState, Mandate]:
    return load_scenario(name)


def scenario_books(name: str) -> tuple[Books, Mandate]:
    """A fixture scenario's books (no commitments) and its mandate."""
    state, mandate = _scenario(name)
    return current_books(state, []), mandate


def golden() -> tuple[Books, Mandate]:
    """The golden books on day 0 with the golden mandate signed by the demo owner key (the verifier needs the signature)."""
    books, _ = scenario_books("golden_sme")
    return books, load_signed_mandate()
