"""Language-boundary follow-ups (certification BO-012 and the wrong-harmless class): each reading the typed rows cannot
carry makes the offer abstain, with a reason that says why, on the rules grammar and on the shipped cache chain."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.compiler.parsing import find_rates, parse_rate_bp
from app.domain.models import CompileStatus, SourceDocument
from tests.compiler.boundary_cases import CASES, Case


def _compile(compiler: Compiler, case: Case):
    doc = SourceDocument(doc_id="d1", channel="chat", sender_id=case.sender, received_day=0, text=case.text)
    return compiler.compile_offer([doc], case.sender)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_the_offer_abstains_and_says_why(rules_compiler: Compiler, case: Case) -> None:
    offer = _compile(rules_compiler, case)
    assert offer.status in (CompileStatus.ABSTAINED, CompileStatus.CONFLICTING_SOURCES), offer.status
    hits = [a for a in offer.abstentions if a.field == case.field]
    assert hits, [(a.field, a.reason) for a in offer.abstentions]
    assert case.reason in hits[0].reason
    assert hits[0].spans and all(sp.text in case.text for sp in hits[0].spans)
    assert offer.autonomy_eligible is False


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_the_shipped_cache_chain_abstains_alike(compiler: Compiler, case: Case) -> None:
    offer = _compile(compiler, case)
    assert offer.status in (CompileStatus.ABSTAINED, CompileStatus.CONFLICTING_SOURCES)
    assert any(a.field == case.field for a in offer.abstentions)


def test_a_decimal_comma_rate_is_never_read_as_a_rate_or_as_two_numbers(rules_compiler: Compiler) -> None:
    """BO-012: 0,5% was read as 500 bp (5%), and the counter-offer then offered more than the buyer's own ask."""
    for t in ("0,5%", "6,4%", "百分之0,5", "give 12,5 percent"):
        assert find_rates(t) == [] or all(f.value not in (500, 400, 1250, 5, 4) for f in find_rates(t)), t
    assert parse_rate_bp("for 0,5% off") is None
    offer = _compile(rules_compiler, CASES[0])
    assert [o for o in offer.obligations if o.rate_bp is not None] == []  # no 500 bp obligation survives


@pytest.mark.parametrize("text", [
    "We pay the full ¥420,000 invoice early for 0.5% off.",
    "We pay the full ¥420,000 invoice early for 0.5% off, 1,000 units shipped.",
    "42万那张发票我们提前付，折扣千分之五。",
    "We can pay invoice RCV-A (¥420,000) early if you give us 0.9% off.",
])
def test_ordinary_offers_still_compile(rules_compiler: Compiler, text: str) -> None:
    offer = _compile(rules_compiler, Case("ok", text, "", ""))
    assert offer.status == CompileStatus.COMPILED
    assert not [a for a in offer.abstentions if a.field.startswith("offer.")]
