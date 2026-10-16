"""ADR-0013: once a purchase is committed its payments are on the books (FlowKind.CAPEX) and the vendor is on the registry.
Every read of the product must still answer, before and after the clock pays the first payment, in both languages."""

from __future__ import annotations

import pytest

TIMELINE = {"signing_day": 20, "delivery_day": 60, "acceptance_day": 80}
READS = ["/activity", "/alerts", "/approvals/queue", "/audit", "/clock", "/customers", "/deals", "/decisions",
         "/documents", "/home", "/ledger", "/mandate", "/nav/counts", "/receivables", "/reconciliation",
         "/security/summary", "/state", "/trajectory", "/worklist", "/purchases", "/finance/health",
         "/lending/eligibility"]


@pytest.fixture
def committed(client, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FEATURE_CAPEX_CONTRACTS", "1")
    d = client.post("/documents", json={"fixture_id": "GZPM_EQUIPMENT_PURCHASE"}).json()["document"]
    client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]})
    ev = client.post(f"/capex/contracts/{d['id']}/evaluate", json={"timeline": TIMELINE}).json()
    aid = client.post(f"/capex/contracts/{d['id']}/commit", json={
        "timeline": TIMELINE, "schedule_hash": ev["schedule"]["schedule"]["schedule_hash"]}).json()["approval_id"]
    assert client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    return {"doc": d["id"], "approval": aid}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_every_read_answers_with_a_committed_purchase(client, committed, lang):
    for path in READS:
        r = client.get(f"{path}?lang={lang}")
        assert r.status_code == 200, (path, r.status_code, r.text[:300])


def test_every_read_answers_after_the_clock_pays_the_deposit(client, committed):
    assert client.post("/clock/advance", json={"to_day": 21}).status_code == 200
    for path in READS:
        r = client.get(path)
        assert r.status_code == 200, (path, r.status_code, r.text[:300])


def test_the_purchase_approval_has_a_decision_record(client, committed):
    r = client.get(f"/decisions/approval:{committed['approval']}")
    assert r.status_code == 200, r.text[:300]


def test_the_trajectory_shows_the_committed_payments(client, committed):
    body = client.get("/trajectory").json()
    assert f"CAPEX:{committed['doc']}:1" in str(body)
