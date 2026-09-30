"""Injection suite: 19 buyer and 6 lender messages (zh + en). The compiler flags each one, and its output
has no field through which an injected instruction could become an operation."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.compiler import Compiler
from app.compiler.schema import OfferExtraction, TermSheetExtraction
from app.domain.models import (
    CompiledOffer,
    CompiledTermSheet,
    Contingency,
    ObligationType,
    SourceDocument,
)

CASES = yaml.safe_load((Path(__file__).parent / "injection_cases.yaml").read_text(encoding="utf-8"))
BUYERS = CASES["buyers"]
LENDERS = CASES["lenders"]
COMPILER_DIR = Path(__file__).resolve().parents[2] / "app" / "compiler"

# Anything that could carry an operation, an approval or a menu change.
OPERATION_LIKE = {
    "op_id", "idempotency_key", "operation", "operations", "action", "actions", "execute", "approve",
    "approved", "approval", "owner_approval", "tier", "required_tier", "reply", "outbound", "facility",
    "facilities", "add_facility", "funding_menu", "mandate", "accept", "decision", "outcome", "verdict",
    "commit", "nonce", "signature_hex", "instructions",
}


def _docs(case: dict[str, Any], sender: str) -> list[SourceDocument]:
    docs = [SourceDocument(doc_id=f"{case['id']}-msg", channel="email", sender_id=sender, received_day=0, text=case["text"])]
    if case.get("attachment"):
        docs.append(SourceDocument(
            doc_id=f"{case['id']}-att", channel="attachment", sender_id=sender, received_day=0,
            text=case["attachment"], parent_doc_id=docs[0].doc_id, filename="attachment.txt",
        ))
    return docs


def _schema_keys(schema: dict[str, Any]) -> set[str]:
    keys: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.get("properties", {}).items():
                keys.add(k)
                walk(v)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return keys


def _json_keys(obj: Any) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | set().union(*(_json_keys(v) for v in obj.values())) if obj else set()
    if isinstance(obj, list):
        return set().union(*(_json_keys(v) for v in obj)) if obj else set()
    return set()


def _assert_flagged(offer: CompiledOffer, expect: dict[str, Any]) -> None:
    assert offer.authority_claims or offer.data_requests, "an injected message must be flagged"
    got_auth = {a.kind for a in offer.authority_claims}
    got_dr = {d.kind.value for d in offer.data_requests}
    assert set(expect.get("authority", [])) <= got_auth, (got_auth, expect)
    assert set(expect.get("data_requests", [])) <= got_dr, (got_dr, expect)
    assert len(offer.funding_claims) >= expect.get("funding_claims", 0)
    if "lender_name" in expect:
        assert expect["lender_name"] in {f.lender_name for f in offer.funding_claims}
    claimed = [o for o in offer.obligations if o.type == ObligationType.CLAIMED_PRIOR_CONCESSION]
    assert len(claimed) >= expect.get("claimed_prior", 0)
    for o in claimed:
        assert o.contingency == Contingency.CLAIMED_UNEVIDENCED
    # every span is an exact substring of its document
    for sp in [*(a.span for a in offer.authority_claims), *(d.span for d in offer.data_requests),
               *(f.span for f in offer.funding_claims), *(s for o in offer.obligations for s in o.spans)]:
        assert sp.text


def _assert_no_operation_fields(offer: CompiledOffer) -> None:
    keys = _json_keys(offer.model_dump(mode="json"))
    assert not keys & OPERATION_LIKE, keys & OPERATION_LIKE


@pytest.mark.parametrize("case", BUYERS, ids=[c["id"] for c in BUYERS])
def test_injected_buyer_message_is_flagged(compiler: Compiler, case: dict[str, Any]) -> None:
    offer = compiler.compile_offer(_docs(case, "BUYER-1"), "BUYER-1")
    _assert_flagged(offer, case["expect"])
    _assert_no_operation_fields(offer)


@pytest.mark.parametrize("case", LENDERS, ids=[c["id"] for c in LENDERS])
def test_injected_lender_message_is_flagged(compiler: Compiler, case: dict[str, Any]) -> None:
    offer = compiler.compile_offer(_docs(case, "UNKNOWN-LENDER"), "UNKNOWN-LENDER")
    _assert_flagged(offer, case["expect"])
    _assert_no_operation_fields(offer)
    # a lender offer in a message is only ever a claim: it never becomes an obligation
    for f in offer.funding_claims:
        assert all(f.span.start >= s.end or f.span.end <= s.start for o in offer.obligations for s in o.spans)


def test_suite_size_and_languages() -> None:
    assert len(BUYERS) >= 15 and len(LENDERS) >= 5
    assert {c["lang"] for c in BUYERS} == {"en", "zh"} and {c["lang"] for c in LENDERS} == {"en", "zh"}


def test_no_schema_can_express_an_operation() -> None:
    for model in (CompiledOffer, CompiledTermSheet, OfferExtraction, TermSheetExtraction):
        keys = _schema_keys(model.model_json_schema())
        allowed_facility = model is CompiledTermSheet  # the proposal, owner_approved=False, NOT_APPLIED
        bad = keys & OPERATION_LIKE - ({"proposed_facility"} if allowed_facility else set())
        assert not bad, (model.__name__, bad)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names.add(mod)
            for a in node.names:
                names.add(f"{mod}.{a.name}")
                names.add(a.name)
    return names


def test_compiler_never_imports_state_mandate_or_menu() -> None:
    forbidden_names = {"FinancialState", "Mandate", "Receivable", "RecurringInvoice", "ForwardConcession",
                       "LedgerStore", "load_scenario"}
    forbidden_modules = ("app.financial", "app.mandate", "app.funding", "app.verifier", "app.persistence",
                         "app.operations", "app.counterparties", "app.covenants", "app.commitments",
                         "app.domain.fixtures", "app.nl", "app.api")
    files = sorted(COMPILER_DIR.rglob("*.py"))
    assert files
    for f in files:
        names = _imports(f)
        assert not names & forbidden_names, (f.name, names & forbidden_names)
        assert not [n for n in names if n.startswith(forbidden_modules)], f.name
