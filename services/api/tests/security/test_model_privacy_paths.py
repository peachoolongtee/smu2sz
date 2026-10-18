"""What leaves the process in live mode, path by path (docs/deliverables/submission/work/control_audit_privacy.md, area 4).

Every model call FLOW makes goes through one of five entry points. Each is run here in LLM_MODE=live, built the way the product builds
it (the default chain, not a backend assembled by the test), with the provider SDKs replaced by a recorder: `anthropic.Anthropic` and
`openai.OpenAI` return an object that records the request and then fails, so the chain falls through to the next backend and, for the
compiler, to the rules grammar. No network, no key (DEEPSEEK_API_KEY is set to a dummy only so the DeepSeek client is built).

  1. compile_offer       a buyer message or offer document (POST /offers, the buyer's POST /nl turn, outbound replies)
  2. compile_contract    a buyer or capex contract, chunk by chunk (POST /documents, setup)
  3. compile_term_sheet  a lender agreement or term sheet
  4. classifier.classify an owner or agent chat turn no rule parsed (app/nl/service.py _parse)
  5. router.route        an owner question the answer layer did not answer (app/nl/ask.py)

Each test checks: every request the recorder saw (every provider, every retry) holds none of the identifiers and still holds the terms
FLOW reads; and nothing logged on the way (structlog and stdlib logging, the provider failure included, whose exception text here
carries the original identifiers) holds an identifier. Pattern-based redaction: these identifiers are the ones the patterns cover; the
test does not claim that every identifying string in every document is found."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
import structlog

from app.compiler import service
from app.compiler.contract import contract_document
from app.domain.models import DocumentKind, SourceDocument
from app.nl import classifier
from app.nl.router import route as router

PHONE = "138 2345 6789"
EMAIL = "ap@foshan-retail.example.com"
ACCOUNT = "4420 1500 0000 5123 4567"
USCC = "91440300MA5FXXXX1Y"
NATIONAL_ID = "440301199003071234"
ADDRESS = "18 Keyuan Road, Nanshan"
SECRETS = (PHONE, EMAIL, ACCOUNT, USCC, NATIONAL_ID, ADDRESS)
KEPT = ("Foshan Retail", "420,000", "INV-2026-0871", "1.5%")  # a party name, an amount, an invoice number, a rate: FLOW reads them

TEXT = (f"Foshan Retail Co. (Unified Social Credit Code: {USCC}), Address: {ADDRESS}; contact ID No. {NATIONAL_ID}. "
        f"Please call {PHONE} or write to {EMAIL}. Pay to Account No. {ACCOUNT}. "
        "We can pay the ¥420,000 invoice INV-2026-0871 30 days early at 1.5%.")
QUESTION = f"Foshan Retail owes ¥420,000 on INV-2026-0871 at 1.5%; my phone is {PHONE}, account {ACCOUNT}, email {EMAIL}: are we ok?"


class Recorder:
    """Stands in for either SDK client: records each request's messages, then fails with an error that quotes the original text."""

    sent: ClassVar[list[str]] = []

    def __init__(self, *a: Any, **kw: Any) -> None:
        self.beta = self.messages = self.chat = self.completions = self

    def create(self, **kw: Any) -> Any:
        Recorder.sent.append(json.dumps([kw.get("system", ""), kw["messages"]], ensure_ascii=False))
        raise RuntimeError(f"provider unavailable while handling {TEXT}")  # an SDK error that echoes local text must not reach a log


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> Iterator[list[dict]]:
    import anthropic
    import openai

    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.delenv("LLM_REDACT", raising=False)  # the shipped default
    monkeypatch.delenv("LLM_LIVE_RAW", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-not-a-key")
    monkeypatch.setattr(anthropic, "Anthropic", Recorder)
    monkeypatch.setattr(openai, "OpenAI", Recorder)
    Recorder.sent = []
    service._default_compiler.cache_clear()
    caplog.set_level(logging.DEBUG)
    with structlog.testing.capture_logs() as logs:
        yield logs
    service._default_compiler.cache_clear()
    logged = json.dumps(logs, ensure_ascii=False, default=str) + "\n".join(r.getMessage() for r in caplog.records)
    leaked = [s for s in SECRETS if s in logged]
    assert not leaked, f"logged: {leaked}"


def _doc() -> SourceDocument:
    return SourceDocument(doc_id="D-PRIV", channel="email", sender_id="BUYER-1", received_day=3, text=TEXT)


def _assert_redacted(min_calls: int, kept: tuple[str, ...] = KEPT) -> None:
    assert len(Recorder.sent) >= min_calls, Recorder.sent
    for body in Recorder.sent:
        assert not [s for s in SECRETS if s in body], body
        assert all(k in body for k in kept), body
        assert "⟦" in body  # placeholders stand where the identifiers were


def test_a_buyer_message_reaches_the_providers_redacted(live: list[dict]) -> None:
    from app.compiler import compile_offer

    compile_offer([_doc()], "BUYER-1")  # the module entry the routes call; both providers fail, the rules grammar reads it
    _assert_redacted(min_calls=2)  # Claude, then DeepSeek with its retries: every attempt redacted
    assert any(e.get("event") == "model.redaction" and e.get("total", 0) >= 5 for e in live)  # counts only


def test_a_contract_reaches_the_providers_redacted(live: list[dict]) -> None:
    from app.compiler import compile_contract

    compile_contract(contract_document(TEXT, DocumentKind.BUYER_CONTRACT, "BUYER-1"))
    _assert_redacted(min_calls=2)


def test_a_term_sheet_reaches_the_providers_redacted(live: list[dict]) -> None:
    from app.compiler import compile_term_sheet

    compile_term_sheet(_doc())
    _assert_redacted(min_calls=2)


def test_a_chat_turn_reaches_the_intent_classifier_redacted(live: list[dict]) -> None:
    got, rejected = classifier.classify(TEXT)  # the default live chain: the recorded classifications, then both providers
    assert got is None and [r.backend for r in rejected] == ["cache", "claude", "deepseek"]
    assert all("Foshan" not in r.reason and PHONE not in r.reason for r in rejected)  # failure reasons name the error type only
    _assert_redacted(min_calls=2)


def test_an_owner_question_reaches_the_router_redacted(live: list[dict]) -> None:
    ctx = SimpleNamespace(owner_authenticated=True, session=None)
    answer, outcome = router.route_outcome(QUESTION, "en", ctx)
    assert answer is None and outcome.outcome == "failed" and outcome.q_hash  # one live call, failed; only the hash is kept
    _assert_redacted(min_calls=1, kept=("Foshan Retail", "420,000", "INV-2026-0871"))


def test_llm_redact_0_is_the_only_switch_that_sends_the_original(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented opt-out, for every path at once: with LLM_REDACT=0 the original text goes (a developer measuring a model)."""
    import anthropic
    import openai

    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("LLM_REDACT", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-not-a-key")
    monkeypatch.setattr(anthropic, "Anthropic", Recorder)
    monkeypatch.setattr(openai, "OpenAI", Recorder)
    Recorder.sent = []
    service.Compiler().compile_offer([_doc()], "BUYER-1")
    classifier.classify(TEXT)
    router.route_outcome(QUESTION, "en", SimpleNamespace(owner_authenticated=True, session=None))
    assert Recorder.sent and all(PHONE in body for body in Recorder.sent)
