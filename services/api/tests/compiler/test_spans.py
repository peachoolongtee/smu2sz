"""Every span the compiler emits is an exact substring of its source document."""

from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.domain.fixtures import load_offers, offer_documents
from app.domain.models import CompiledOffer, CompiledTermSheet, SourceDocument, SourceSpan

OFFERS = load_offers()


def _spans_offer(o: CompiledOffer) -> list[SourceSpan]:
    out = [s for ob in o.obligations for s in ob.spans]
    out += [s for a in o.abstentions for s in a.spans]
    out += [d.span for d in o.data_requests] + [a.span for a in o.authority_claims] + [f.span for f in o.funding_claims]
    return out


def _spans_ts(t: CompiledTermSheet) -> list[SourceSpan]:
    return [c.span for c in t.clauses] + [c.span for c in t.tier3_clauses] + [s for a in t.abstentions for s in a.spans]


def _check(spans: list[SourceSpan], docs: list[SourceDocument]) -> None:
    by_id = {d.doc_id: d.text for d in docs}
    for s in spans:
        assert s.doc_id in by_id
        assert by_id[s.doc_id][s.start : s.end] == s.text, s
        assert s.text.strip() == s.text and s.text


@pytest.mark.parametrize("oid", list(OFFERS))
def test_spans_match_document_substrings(compiler: Compiler, oid: str) -> None:
    docs = offer_documents(oid)
    if OFFERS[oid].get("kind") == "term_sheet":
        spans = _spans_ts(compiler.compile_term_sheet(docs[0]))
    else:
        spans = _spans_offer(compiler.compile_offer(docs, OFFERS[oid]["counterparty_id"]))
    _check(spans, docs)


def test_spans_on_chinese_and_multiline_text(rules_compiler: Compiler) -> None:
    docs = [SourceDocument(doc_id="zh", channel="chat", sender_id="BUYER-1", received_day=0,
                           text="我们可以提前付款，折扣1.2%。\n今后账期改为60天，\n下季度再给我们1%的返利。")]
    offer = rules_compiler.compile_offer(docs, "BUYER-1")
    assert len(offer.obligations) == 3
    _check(_spans_offer(offer), docs)
