"""ADR-0013: the buy side against the threat model. A purchase reaches the books only through the owner's approval of a
CommitPurchase whose schedule the executor derives again from the stored, confirmed contract; nothing a caller writes into
the operation (an amount, a hash, another document, the early-payment flag) can change what is booked, and a switched-off
feature books nothing whichever route queued the operation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}
AGENT = {"X-Agent-Key": "demo-agent-key"}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")


@pytest.fixture
def rt(client):
    from app.api.runtime import get_runtime

    return get_runtime()


@pytest.fixture
def agent(client):  # type: ignore[no-untyped-def]
    from app.main import app

    return TestClient(app, headers=AGENT)


def _confirmed(client) -> tuple[str, str, str]:  # type: ignore[no-untyped-def]
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    return d["id"], d["doc_hash"], ev["schedule"]["schedule"]["schedule_hash"]


def _op(doc: str, doc_hash: str, schedule_hash: str, over: dict | None = None) -> dict:  # type: ignore[type-arg]
    over = over or {}
    body = {"kind": "COMMIT_PURCHASE", "op_id": f"attack-{sorted(over.items())}", "idempotency_key": f"attack:{sorted(over.items())}",
            "mandate_version": 1, "requested_by": "OWNER", "document_id": doc, "doc_hash": doc_hash,
            "schedule_hash": schedule_hash, "amount_fen": 60_000_000, **TIMELINE}
    body.update(over)
    return body


def _capex_flows(rt) -> list[str]:  # type: ignore[no-untyped-def]
    return [f.id for f in rt.store.get_state().flows if f.kind.value == "CAPEX"]


def test_the_agent_cannot_queue_a_purchase_and_cannot_approve_the_owners(client, agent, on, rt):
    doc, h, sh = _confirmed(client)
    refused = agent.post("/operations", json=_op(doc, h, sh, {"requested_by": "AGENT"})).json()["result"]
    assert refused["status"] == "REFUSED" and refused["approval_id"] is None  # CAPEX-2: nothing queued for the owner
    assert refused["violations"][0]["code"] == "INSUFFICIENT_AUTHORITY"
    assert not rt.store.approvals()
    queued = client.post("/operations", json=_op(doc, h, sh, {"op_id": "owner-op", "idempotency_key": "owner-op"})).json()["result"]
    assert queued["status"] == "PENDING_APPROVAL" and queued["tier"] == "TIER_2"
    assert _capex_flows(rt) == []
    denied = agent.post(f"/approvals/{queued['approval_id']}", json={"decision": "APPROVE"})
    assert denied.status_code in (401, 403) or denied.json()["result"]["status"] == "REFUSED"
    assert _capex_flows(rt) == []


def test_an_owner_claim_from_the_agent_is_still_the_agent_and_is_refused(client, agent, on, rt):
    doc, h, sh = _confirmed(client)
    r = agent.post("/operations", json=_op(doc, h, sh, {"requested_by": "OWNER"})).json()["result"]
    assert r["status"] == "REFUSED" and r["approval_id"] is None and not rt.store.approvals() and _capex_flows(rt) == []


@pytest.mark.parametrize(("over", "code"), [
    ({"delivery_day": 200}, "PRECONDITION_FAILED"),  # a timeline out of order: no schedule follows from it
    ({"amount_fen": 6_000_000}, "TERMS_CHANGED"),  # a smaller amount with the real schedule's hash
    ({"schedule_hash": "f" * 64}, "TERMS_CHANGED"),  # a schedule the owner was never shown
    ({"doc_hash": "e" * 64}, "TERMS_CHANGED"),  # another text
    ({"delivery_day": 70}, "TERMS_CHANGED"),  # another (valid) timeline under the shown schedule's hash
    ({"take_early_pay": True}, "TERMS_CHANGED"),  # the early schedule under the plain schedule's hash
])
def test_a_forged_commitment_books_nothing_even_when_the_owner_approves(client, agent, on, rt, over, code):
    doc, h, sh = _confirmed(client)
    r = client.post("/operations", json=_op(doc, h, sh, over)).json()["result"]
    assert r["status"] == "PENDING_APPROVAL"
    out = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    assert out["status"] == "REFUSED" and out["violations"][0]["code"] == code, out
    assert _capex_flows(rt) == []


def test_a_buyer_contract_cannot_be_committed_as_a_purchase(client, agent, on, rt):
    d = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    r = client.post("/operations", json=_op(d["id"], d["doc_hash"], "0" * 64)).json()["result"]
    out = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    assert out["status"] == "REFUSED" and "not a capex contract" in out["message"]
    assert _capex_flows(rt) == []


def test_with_the_feature_off_a_queued_purchase_books_nothing(client, agent, monkeypatch, rt):
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")
    doc, h, sh = _confirmed(client)
    r = client.post("/operations", json=_op(doc, h, sh)).json()["result"]
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "0")
    out = client.post(f"/approvals/{r['approval_id']}", json={"decision": "APPROVE"}).json()["result"]
    assert out["status"] == "REFUSED" and out["violations"][0]["code"] == "FEATURE_DISABLED"
    assert _capex_flows(rt) == []


def test_a_counterparty_reaches_no_buy_side_route(client, on):
    from app.main import app

    buyer = TestClient(app, headers={"X-Counterparty-Key": "demo-buyer-1-key"})
    for method, path in [("get", "/purchases"), ("get", "/finance/health"), ("get", "/lending/eligibility"),
                         ("post", "/capex/plans"), ("post", "/capex/contracts/DOC-000001/evaluate"),
                         ("post", "/capex/contracts/DOC-000001/commit"),
                         ("post", "/lending/products/PRD-BANK1-TERM-60/add-to-menu"), ("post", "/operations")]:
        r = getattr(buyer, method)(path, **({"json": {}} if method == "post" else {}))
        assert r.status_code == 401, (path, r.status_code)


def test_the_agent_cannot_add_a_catalogue_loan_to_the_menu(client, agent, on, rt):
    """Only the owner adds a facility (INVARIANT 3): the agent's AddFacility is Tier 3, whatever it claims."""
    from app.lending import facility_of, product

    p = product("PRD-BANK1-TERM-60")
    assert p is not None
    body = {"kind": "ADD_FACILITY", "op_id": "attack-add", "idempotency_key": "attack-add", "mandate_version": 1,
            "requested_by": "AGENT", "facility": facility_of(p).model_dump(mode="json")}
    r = agent.post("/operations", json=body).json()["result"]
    assert r["status"] == "REFUSED" and r["tier"] == "TIER_3"
    assert not any(f.id == "FAC-BANK1-TERM-60" for f in rt.store.get_state().facilities)
