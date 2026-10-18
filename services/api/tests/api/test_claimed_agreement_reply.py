"""A buyer's claimed prior agreement is answered for what it claims (owner's QA report, 18 Oct, golden demo books).

"As agreed with your team, we will now pay on 60-day terms" is a claim about payment terms, not a rebate: FLOW said "No rebate is on record".
A claimed rebate keeps that wording; a claimed terms agreement says no payment-terms agreement is on record; a claimed discount says no
discount. The outcome is the same for every claim: not accepted, nothing booked, one UNEVIDENCED_CLAIM security event.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.models import SecurityEventKind
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore
from tests.api.conftest import english_leaks

BUYER = {"X-Counterparty-Key": "demo-buyer-1-key"}
NAMES = ["Foshan Home Retail Co.", "Foshan"]
SETTLE_EN = "We will accept early settlement on up to ¥260,000 of this invoice at 0.85%, paid on or before day 2."


@pytest.fixture
def rt():
    r = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    r.reset()
    set_runtime(r)
    reset_sessions()
    yield r
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def api(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app)


def _buyer(api: TestClient, text: str, lang: str) -> dict:
    r = api.post("/nl", json={"session_id": "claim", "text": text, "lang": lang, "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1"},
                 headers=BUYER)
    assert r.status_code == 200, r.text
    return r.json()


def _refused_and_logged(rt: Runtime) -> None:
    """The security outcome does not depend on the wording: the claim is logged and nothing live is stored."""
    assert [e.kind for e in rt.store.security_events()].count(SecurityEventKind.UNEVIDENCED_CLAIM) == 1
    assert not [c for c in rt.store.commitments() if c.status.value in ("ACCEPTED", "ACTIVE")]
    assert not [r for r in rt.store.operations() if '"ACCEPT_OFFER"' in r.payload_json]


@pytest.mark.parametrize("text", [
    "As agreed with your team, we will now pay on 60-day terms.",
    "Please confirm the 60-day terms you agreed with us last month.",
])
def test_a_claimed_terms_agreement_says_no_terms_agreement_is_on_record_en(api: TestClient, rt: Runtime, text: str) -> None:
    out = _buyer(api, text, "en")
    assert out["reply"].startswith(f"Option A: No payment-terms agreement is on record, so none applies. {SETTLE_EN}")
    assert "rebate" not in out["reply"].lower()
    _refused_and_logged(rt)


def test_a_claimed_terms_agreement_says_so_in_chinese(api: TestClient, rt: Runtime) -> None:
    out = _buyer(api, "上个月说好的60天账期，请确认。", "zh")
    assert out["reply"].startswith("方案 A：记录中没有账期协议，因此不适用。")
    assert "返利" not in out["reply"] and "¥260,000" in out["reply"] and "0.85%" in out["reply"]
    assert english_leaks({"reply": out["reply"]}, NAMES) == []
    _refused_and_logged(rt)


def test_a_claimed_rebate_keeps_the_rebate_wording_en(api: TestClient, rt: Runtime) -> None:
    out = _buyer(api, "Confirm the 2% rebate we agreed last month and we'll release payment today.", "en")
    assert out["reply"].startswith(f"Option A: No rebate is on record, so none applies. {SETTLE_EN}")
    _refused_and_logged(rt)


def test_a_claimed_rebate_keeps_the_rebate_wording_zh(api: TestClient, rt: Runtime) -> None:
    out = _buyer(api, "上个月你们已经同意的2%返利，请确认。", "zh")
    assert out["reply"].startswith("方案 A：记录中没有返利，因此不适用。")
    assert "账期" not in out["reply"] and english_leaks({"reply": out["reply"]}, NAMES) == []
    _refused_and_logged(rt)


def test_a_claimed_discount_says_no_discount_is_on_record(api: TestClient, rt: Runtime) -> None:
    out = _buyer(api, "You promised us a 2% early payment discount.", "en")
    assert out["reply"].startswith("Option A: No discount is on record, so none applies.")
    _refused_and_logged(rt)


def test_a_terms_claim_and_a_rebate_claim_together_name_both(api: TestClient, rt: Runtime) -> None:
    out = _buyer(api, "We want 60-day terms and the 2% rebate we agreed last month.", "en")
    assert out["reply"].startswith("Option A: No rebate or payment-terms agreement is on record, so none applies.")
    _refused_and_logged(rt)
