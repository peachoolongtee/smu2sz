"""`Obligation.target_terms_days` carries the terms the text states; `days_delta` only when the text states
both the old and the new terms. `unresolved` names `current_terms_days` exactly when the delta is open."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import ObligationType, SourceDocument

T = ObligationType
OFFERS = load_offers()


def _terms(c: Compiler, oid: str):
    offer = c.compile_offer(offer_documents(oid), OFFERS[oid]["counterparty_id"])
    return [o for o in offer.obligations if o.type in (T.TERMS_EXTENSION, T.CLAIMED_PRIOR_CONCESSION)]


@pytest.mark.parametrize("chain", ["compiler", "rules_compiler"])
@pytest.mark.parametrize(("oid", "expected"), [
    ("EX01_PACKAGE", [(T.TERMS_EXTENSION, 60, None)]),
    ("EX01B_REWORDED", [(T.TERMS_EXTENSION, 60, None)]),
    ("EX05_CONSOLIDATE", [(T.TERMS_EXTENSION, 30, None)]),
    ("EX06_THREE_INVOICES", [(T.TERMS_EXTENSION, 45, 15)]),
    ("EX10_FASTCAPITAL", [(T.CLAIMED_PRIOR_CONCESSION, 60, None)]),
])
def test_examples_carry_their_stated_target(oid, expected, chain, request):
    got = [(o.type, o.target_terms_days, o.days_delta) for o in _terms(request.getfixturevalue(chain), oid)]
    assert got == expected


def test_cache_entries_for_ex01_yield_sixty_days(compiler: Compiler):
    for oid in ("EX01_PACKAGE", "EX01B_REWORDED"):
        offer = compiler.compile_offer(offer_documents(oid), "BUYER-1")
        assert offer.compiler == "fixture-cache"
        (ext,) = [o for o in offer.obligations if o.type == T.TERMS_EXTENSION]
        assert ext.target_terms_days == 60 and ext.days_delta is None
        assert "current_terms_days" in ext.unresolved


@pytest.mark.parametrize(("text", "target", "delta"), [
    ("Please extend our standard terms to 60 days going forward.", 60, None),
    ("We'd like 30-day terms from now on.", 30, None),
    ("以后账期改为60天。", 60, None),
    ("我们需要60天账期。", 60, None),
    ("账期从30天延长到45天。", 45, 15),
    ("Take 45 days on the next three invoices instead of 30.", 45, 15),
    ("Extend our terms from 45 to 60 days.", 60, 15),
])
def test_paraphrases_set_target_and_delta_consistently(text, target, delta, rules_compiler: Compiler):
    doc = SourceDocument(doc_id="t1", channel="chat", sender_id="BUYER-1", received_day=0, text=text)
    offer = rules_compiler.compile_offer([doc], "BUYER-1")
    (ext,) = [o for o in offer.obligations if o.type == T.TERMS_EXTENSION]
    assert (ext.target_terms_days, ext.days_delta) == (target, delta)
    assert ("current_terms_days" in ext.unresolved) == (delta is None)


def test_other_obligations_have_no_target(compiler: Compiler):
    for oid in ("EX01_PACKAGE", "EX02_EARLY_1_5", "EX08A_JOINT_BUYER1"):
        offer = compiler.compile_offer(offer_documents(oid), OFFERS[oid]["counterparty_id"])
        assert all(o.target_terms_days is None for o in offer.obligations if o.type != T.TERMS_EXTENSION)


def test_documents_disagreeing_on_target_terms_conflict(rules_compiler: Compiler):
    docs = [
        SourceDocument(doc_id="a", channel="email", sender_id="BUYER-1", received_day=0,
                       text="Please extend our standard terms to 60 days going forward."),
        SourceDocument(doc_id="b", channel="attachment", sender_id="BUYER-1", received_day=0, parent_doc_id="a",
                       text="Payment terms: 90 days."),
    ]
    offer = rules_compiler.compile_offer(docs, "BUYER-1")
    assert offer.status.value == "CONFLICTING_SOURCES"
