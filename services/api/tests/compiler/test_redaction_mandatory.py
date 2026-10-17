"""PRIV-1 to PRIV-3 (security register, model-privacy review of 16 Oct, re-checked on 719c9dcf).

PRIV-1: redaction was a wrapper each caller had to remember. The provider backends sent the original text when built
directly, and the live language-boundary script built them directly. Each provider backend now redacts its own input by
default (LLM_REDACT), however it is built; only `redact=False`, or LLM_REDACT=0, sends the original.
PRIV-2: a labelled address swallowed the rest of its sentence, hiding the terms after it from the model.
PRIV-3: a labelled short number (an order quantity after 手机, a day count after 账户) was taken for a phone or account, and
"+86 (755) 8600 1234" kept most of its digits."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.compiler.backends import ClaudeBackend, DeepSeekBackend
from app.compiler.base import BackendError
from app.compiler.contract import contract_document
from app.compiler.redaction import RedactingBackend, Redactor, redacting
from app.compiler.rules import RulesBackend
from app.domain.models import DocumentKind, SourceDocument
from app.nl import classifier

PHONE = "138 2345 6789"
EMAIL = "ap@foshan-retail.example.com"
ACCOUNT = "4420 1500 0000 5123 4567"
TEXT = (f"Please call {PHONE} or write to {EMAIL}. Pay to Account No. {ACCOUNT}. "
        "We can pay the ¥420,000 invoice INV-2026-0871 30 days early at 1.5%.")
SECRETS = (PHONE, EMAIL, ACCOUNT)


class Capture:
    """Any provider SDK: records what would have been sent, then fails so the chain moves on."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.beta = self.messages = self.chat = self.completions = self

    def create(self, **kw: Any) -> Any:
        self.sent.append(json.dumps(kw["messages"], ensure_ascii=False))
        raise RuntimeError("offline")


def _doc() -> SourceDocument:
    return SourceDocument(doc_id="D1", channel="email", sender_id="BUYER-1", received_day=3, text=TEXT)


CALLS = {
    "offer": lambda b: b.extract_offer([_doc()]),
    "term_sheet": lambda b: b.extract_term_sheet(_doc()),
    "contract": lambda b: b.extract_contract(contract_document(TEXT, DocumentKind.BUYER_CONTRACT, "BUYER-1")),
}
MAKERS = {
    "claude": lambda c, **kw: ClaudeBackend(client=c, **kw),
    "deepseek": lambda c, **kw: DeepSeekBackend(client=c, retries=0, **kw),
}


@pytest.mark.parametrize("maker", MAKERS)
@pytest.mark.parametrize("call", CALLS)
def test_a_provider_backend_built_directly_redacts_by_default(maker: str, call: str) -> None:
    c = Capture()
    with pytest.raises(BackendError):
        CALLS[call](MAKERS[maker](c))
    assert c.sent, "the request was built"
    assert not [s for s in SECRETS if s in c.sent[0]], c.sent[0]
    assert "420,000" in c.sent[0] and "INV-2026-0871" in c.sent[0]  # what FLOW reads still goes


@pytest.mark.parametrize("maker", MAKERS)
def test_only_an_explicit_choice_sends_the_original(maker: str, monkeypatch: pytest.MonkeyPatch) -> None:
    c = Capture()
    with pytest.raises(BackendError):
        MAKERS[maker](c, redact=False).extract_offer([_doc()])
    assert PHONE in c.sent[0]
    monkeypatch.setenv("LLM_REDACT", "0")
    c2 = Capture()
    with pytest.raises(BackendError):
        MAKERS[maker](c2).extract_offer([_doc()])
    assert PHONE in c2.sent[0]


def test_the_classifier_backend_redacts_by_default() -> None:
    sent: list[str] = []

    def complete(system: str, user: str, schema: dict) -> str:
        sent.append(user)
        return json.dumps({"intent": "EVALUATE_OFFER", "slots": {}, "confidence": 0.9})

    classifier.classify(TEXT, [classifier.CallableBackend("deepseek", "m", complete)])
    assert sent and not [s for s in SECRETS if s in sent[0]]


def test_nothing_is_redacted_twice_and_fakes_are_still_wrapped() -> None:
    claude, rules = ClaudeBackend(client=Capture()), RulesBackend()
    out = redacting([claude, rules], True)
    assert out[0] is claude  # redacts on its own: not wrapped again
    assert isinstance(out[1], RedactingBackend)  # a backend that does not redact is wrapped
    assert redacting([claude, rules], False) == [claude, rules]


@pytest.mark.parametrize(("text", "kept", "gone"), [
    # PRIV-2: the terms after a labelled address reach the model
    ("Address: 12 Keyuan Road, Shenzhen. We will pay invoice INV-2026-0871 within 10 days for a 2% discount.",
     "We will pay invoice INV-2026-0871 within 10 days for a 2% discount.", "12 Keyuan Road"),
    ("地址：深圳市南山区科苑路12号，我方将于10日内付款，享受2%折扣。", "我方将于10日内付款，享受2%折扣。", "科苑路12号"),
    ("Address: Room 1203, Tower A, No. 88 Example Rd. Nanshan, Shenzhen", "Address: ", "No. 88 Example Rd. Nanshan"),
    # PRIV-3: a quantity or a day count after a label is not an identifier; a bracketed area code is one number
    ("采购手机 2000 台，账户 30 天内付清", "采购手机 2000 台，账户 30 天内付清", "⟦"),
    ("Tel: +86 (755) 8600 1234", "Tel: ", "8600 1234"),
    ("Mobile: 138 2345 6789", "Mobile: ", "2345 6789"),
])
def test_labelled_values_end_where_they_should(text: str, kept: str, gone: str) -> None:
    red = Redactor().redact(text).redacted
    assert kept in red and gone not in red, red
