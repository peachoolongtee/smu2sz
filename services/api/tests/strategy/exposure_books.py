"""Books and packages for the buyer-exposure tests (map #88, ticket #96): the fixtures' scenarios as `Books` plus the
Demo's three packages for Foshan (EX01 as asked, Option A and Option B), each as a `CandidatePackage`.

A helper, not a conftest: the tests import what they use. Nothing here writes; every state is a fresh load."""

from __future__ import annotations

from functools import cache

from app.books import Books, current_books
from app.domain.fixtures import load_scenario
from app.domain.models import FinancialState, FundingLot, Mandate
from app.mandate.fixture import demo_owner_public_key_hex, load_signed_mandate
from app.strategy.types import CandidatePackage

OWNER_KEY = demo_owner_public_key_hex()
FOSHAN = "BUYER-1"

# EX01 as asked: early settlement of the whole RCV-A at 1.2%, 60-day terms, 1% off the next quarter's order.
ASKED = CandidatePackage(buyer_id=FOSHAN, terms_days=60, early_pay_bp=120, rebate_bp=100)
# Option A: ¥260,000 of RCV-A settled early at 0.85%, the terms as they are.
OPTION_A = CandidatePackage(buyer_id=FOSHAN, terms_days=45, early_pay_bp=85, early_pay_face_fen=26_000_000)
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


def financed_golden(landed: bool, *, outstanding_fen: int = 42_000_000) -> Books:
    """The golden books with RCV-A financed (ticket #107): a ¥255,000 advance on FAC-IF, landed already (RECEIVED, day -2) or
    arranged and arriving on day 3 (ARRANGED). `outstanding_fen` below the face leaves the rest as already received."""
    books, _ = golden()
    state = books.state
    rcv = next(r for r in state.receivables if r.id == "RCV-A")
    lot = FundingLot(id="LOT-IF", facility_id="FAC-IF", principal_fen=25_500_000, remaining_fen=25_500_000,
                     request_day=-5 if landed else 0, arrival_day=-2 if landed else 3, receivable_id="RCV-A", settled=landed)
    financed = state.model_copy(update={
        "receivables": [rcv.model_copy(update={"status": "FINANCED", "advance_fen": 25_500_000, "advance_facility_id": "FAC-IF",
                                              "settled_fen": rcv.face_fen - outstanding_fen})],
        "facilities": [f.model_copy(update={"drawn_fen": 25_500_000}) if f.id == "FAC-IF" else f for f in state.facilities],
        "lots": [lot]})
    return Books(state=financed, obligations=())
