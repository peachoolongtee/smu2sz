"""Round nine (Security Lead review of int/sl-final eb3c1059, 19 Oct).

LOG-2: the egress guard is documented as the last step before outbound text, yet a counter's "not on record" lead was rewritten
(`restate_not_on_record`, in `counter_line`) after the per-counter scan, so the text the guard scanned, the text the plan step recorded
and the text the buyer read could differ in fixed wording ("payment-terms agreement" against "rebate"), and a protected value in the
rewritten lead would not have been caught by the counter's own scan. The lead is now rewritten before the scan: the scanned text is
the text recorded and sent, and a hit withholds the counter exactly as the guard does for any other counter."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.nl.context as nl_context
from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.claims import CLAIM_NOUNS_EN, restate_not_on_record
from app.egress.canaries import load_canaries
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import pipeline, reset_sessions
from app.persistence import InMemoryLedgerStore

BUYER = {"X-Counterparty-Key": "demo-buyer-1-key"}
TERMS_CLAIM = "As agreed with your team, we will now pay on 60-day terms."
LEAD = "No payment-terms agreement is on record, so none applies."


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


@pytest.fixture
def scanned(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every text the NL egress guard scans, in order."""
    seen: list[str] = []
    real = nl_context.guard

    def spy(text: str, *a, **k):
        seen.append(text)
        return real(text, *a, **k)

    monkeypatch.setattr(nl_context, "guard", spy)
    return seen


def _buyer(api: TestClient, text: str) -> dict:
    r = api.post("/nl", json={"session_id": "r9-log2", "text": text, "lang": "en", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1"},
                 headers=BUYER)
    assert r.status_code == 200, r.text
    return r.json()


def _ops(rt: Runtime, kind: str) -> list:
    return [o for o in rt.store.operations() if o.kind == kind]


def _rewrite_lead(monkeypatch: pytest.MonkeyPatch, new_lead: str) -> None:
    """The lead rewrite says `new_lead` in place of the verifier's lead (a stand-in for any wording the rewrite may produce)."""
    real = pipeline.restate_not_on_record
    monkeypatch.setattr(pipeline, "restate_not_on_record", lambda text, obs: real(text, obs).replace(LEAD, new_lead))


def test_log2_the_scanned_counter_text_is_the_text_sent(api: TestClient, rt: Runtime, scanned: list[str],
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever the lead rewrite says, the counter's own scan sees it, and the buyer's line is that scanned text."""
    _rewrite_lead(monkeypatch, "No payment-terms agreement is on our record, so none applies.")
    out = _buyer(api, TERMS_CLAIM)
    rewritten = [s for s in scanned if s.startswith("No payment-terms agreement is on our record")]  # the counter's own scan
    assert len(rewritten) == 1
    assert out["reply"].startswith(f"Option A: {rewritten[0]}")
    assert len(_ops(rt, "COUNTER_OFFER")) == 1


def test_log2_send_counters_records_and_returns_the_scanned_text(api: TestClient, rt: Runtime, scanned: list[str],
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """The pipeline's own record: the plan step and the (counter, text sent) it returns carry the text the guard scanned."""
    from app.nl.context import NlContext
    from app.nl.sessions import Session

    r = api.post("/nl", json={"session_id": "r9-log2-anon", "text": TERMS_CLAIM, "lang": "en", "actor": "COUNTERPARTY",
                              "counterparty_id": "BUYER-1"})  # no key: a proposal only, nothing sent; the verdict is stored
    assert r.status_code == 200, r.text
    verdict = rt.store.verdicts()[-1]
    assert verdict.counters and verdict.counters[0].text.startswith(LEAD)
    _rewrite_lead(monkeypatch, "No payment-terms agreement is on our record, so none applies.")
    scanned.clear()
    ctx = NlContext(store=rt.store, executor=rt.executor, day=rt.day, owner_key_hex=rt.owner_key_hex, owner_authenticated=True,
                    session=Session(id="r9-log2-unit", actor="OWNER", owner_auth=True), lang="en", trace_id="r9-log2")
    steps = pipeline.Steps()
    sent = pipeline.send_counters(ctx, steps, verdict, verdict.counters[:1], "BUYER-1")
    assert len(sent) == 1
    text = sent[0][1]
    assert text.startswith("No payment-terms agreement is on our record")
    assert scanned == [text]
    assert [(s.kind, s.description) for s in steps.items] == [("COUNTER_OFFER", f"Option A: {text}")]


def test_log2_a_protected_value_in_the_rewritten_lead_withholds_the_counter(api: TestClient, rt: Runtime,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """A protected value the rewrite puts into the lead is caught by the counter's own scan: the counter is withheld (no CounterOffer
    executed, a DATA_EXTRACTION event logged) and the buyer's text does not carry the value. Before, the counter's scan passed the
    verifier's text, the CounterOffer was executed, and only the whole-reply scan kept the value from the buyer."""
    token = next(c.token for c in load_canaries() if c.token)
    _rewrite_lead(monkeypatch, f"{LEAD} Ref {token}.")
    out = _buyer(api, TERMS_CLAIM)
    assert _ops(rt, "COUNTER_OFFER") == []
    assert any(e.kind.value == "DATA_EXTRACTION" for e in rt.store.security_events())
    assert token not in out["reply"]


@pytest.mark.parametrize(("text", "lang"), [
    (TERMS_CLAIM, "en"),
    ("We want 60-day terms and the 2% rebate we agreed last month.", "en"),
    ("Please extend our terms to 60 days. As agreed last month, we also get a 2% rebate and a 1% discount.", "en"),
    ("上个月说好的60天账期，请确认。", "zh"),
])
def test_log2_the_stored_counter_is_the_buyers_line(api: TestClient, rt: Runtime, text: str, lang: str) -> None:
    """Without any stand-in: the counter as the verdict stores it (the engine's record) is the line the buyer reads, in English as stored and
    in Chinese through the translation layer only, and no claim noun is said twice."""
    from app.api.engine_zh import translate

    r = api.post("/nl", json={"session_id": f"r9-log2-{lang}-{len(text)}", "text": text, "lang": lang, "actor": "COUNTERPARTY",
                              "counterparty_id": "BUYER-1"}, headers=BUYER)
    assert r.status_code == 200, r.text
    stored = rt.store.verdicts()[-1].counters[0].text
    first = r.json()["reply"].splitlines()[0]
    assert first == (f"Option A: {stored}" if lang == "en" else f"方案 A：{translate(stored)}")
    assert not any(f"{n} or {n}" in first for n in CLAIM_NOUNS_EN.values()), "a claim noun said twice"


@pytest.mark.parametrize("text", [
    "Terms stay at 60 days, no rebate or payment-terms agreement. We will accept early settlement on up to ¥10,000 of this invoice.",
    "No rebate or payment-terms agreement is on record, so none applies. We will accept early settlement on up to ¥10,000.",
    "No payment-terms agreement is on record, so none applies. We will accept early settlement on up to ¥10,000.",
])
def test_log2_the_lead_rewrite_leaves_a_lead_that_already_names_the_claim(text: str) -> None:
    """The verifier names the claim itself (0e7badbd); the rewrite only corrects a lead that says "rebate" alone, so a lead that already
    says what was claimed reaches the buyer as the verdict logs it ("no rebate or payment-terms agreement or payment-terms agreement" was
    the rewrite of a lead that named both)."""
    from app.domain.models import Contingency, Obligation, ObligationType

    claim = Obligation.model_construct(type=ObligationType.CLAIMED_PRIOR_CONCESSION, contingency=Contingency.CLAIMED_UNEVIDENCED,
                                       target_terms_days=60, days_delta=None, spans=[])
    rebate = Obligation.model_construct(type=ObligationType.CONTINGENT_REBATE, contingency=None, target_terms_days=None,
                                        days_delta=None, spans=[])
    assert restate_not_on_record(text, [claim, rebate]) == text
