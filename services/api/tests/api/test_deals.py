"""Brief 03 §5.2: GET /deals and GET /deals/{buyer}, composed read-only from the confirmed contract and the current
books. The golden demo on day 34 is the prototype's state."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.fixtures import contract_fixture_bytes
from app.domain.money import bp, post

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def confirm_demo_documents(client: TestClient) -> None:
    for fid, link in (("FHR_SUPPLY_AGREEMENT", None), ("MB_CREDIT_LINE_AGREEMENT", "FAC-LINE"),
                      ("GBR_INVOICE_FINANCING_AGREEMENT", "FAC-IF")):
        d = client.post("/documents", json={"fixture_id": fid}).json()["document"]
        body = {"doc_hash": d["doc_hash"], **({"link_facility_id": link} if link else {})}
        assert client.post(f"/documents/{d['id']}/confirm", json=body).json()["result"]["status"] == "EXECUTED"


def run_demo_to_day_34(client: TestClient) -> None:
    """The golden demo (scripts/demo_run.py): EX01 -> Counter A accepted -> the early payment on day 2 -> day 34 ->
    the owner says go ahead and the cure is queued for approval."""
    from app.api.runtime import get_runtime

    rt = get_runtime()
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    ob = rt.store.get_commitment(n["commitment"]["id"]).obligations[0]
    agreed = ob.base.amount_fen - post(bp(ob.rate_bp) * ob.base.amount_fen)
    client.post("/clock/advance", json={"to_day": ob.effective_day})
    r = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "r1", "idempotency_key": "r1", "mandate_version": 1,
        "requested_by": "SYSTEM", "receivable_id": ob.base.receivable_id, "amount_fen": agreed, "bank_reference": "B1"})
    assert r.json()["result"]["status"] == "EXECUTED"
    client.post("/clock/advance", json={"to_day": 30})
    client.post("/clock/advance", json={"to_day": 34})
    client.post("/nl/opener", json={"session_id": "s", "lang": "en"})
    client.post("/nl", json={"session_id": "s", "actor": "OWNER", "text": "go ahead"})


@pytest.fixture
def anon(client):
    from app.main import app

    return TestClient(app)


def test_deal_routes_are_owner_only(anon):
    for path in ("/deals", "/deals/BUYER-1"):
        for headers in ({}, {"X-Agent-Key": "demo-agent-key"}, {"X-Counterparty-Key": "demo-buyer-1-key"}):
            assert anon.get(path, headers=headers).status_code == 401


def test_without_a_confirmed_contract_a_buyer_is_a_placeholder(client):
    deals = client.get("/deals").json()["deals"]
    assert [(d["counterparty_name"], d["has_contract"]) for d in deals] == [
        ("Foshan Home Retail Co.", False), ("Dongguan Office Supplies Ltd.", False)]
    d = client.post("/documents", json={"fixture_id": "FHR_SUPPLY_AGREEMENT"}).json()["document"]
    deal = client.get("/deals/BUYER-1").json()["deal"]
    assert deal["has_contract"] is False and deal["pending_documents"] == [d["id"]]  # read, not yet confirmed
    assert client.get("/deals/BANK-1").status_code == 404 and client.get("/deals/NOBODY").status_code == 404


def test_day_zero_after_confirmation(client):
    confirm_demo_documents(client)
    deal = client.get("/deals/BUYER-1").json()["deal"]
    assert deal["has_contract"] and deal["label"] == "Read by the agent, confirmed by you"
    c = deal["contract"]
    assert (c["title"], c["reference"], c["signed_display"], c["term_display"], c["end_day"]) == (
        "Supply agreement FHR-2026-07", "FHR-2026-07", "1 Sep 2026", "12 months", 334)
    assert [t["field"] for t in deal["contract_terms"]] == ["PRICE", "INVOICING", "PAYMENT_TERMS", "EARLY_PAYMENT",
                                                           "SCHEDULED_INVOICE"]
    assert [s["state"] for s in deal["stages"]] == ["done", "skipped", "skipped", "now", "todo"]
    assert all(x["status"] == "ok" for x in deal["checks"]), deal["checks"]
    assert [i["id"] for i in deal["invoices"]] == ["RCV-A"] and deal["invoices"][0]["status"] == "NOT_DUE"
    assert deal["next_invoice"] == {"day": 2, "amount_display": "¥420,000.00"}
    assert deal["next_action"]["text"] == "Nothing needs you on this deal today."


def test_the_golden_demo_on_day_34_matches_the_prototype(client):
    confirm_demo_documents(client)
    run_demo_to_day_34(client)
    deal = client.get("/deals/BUYER-1").json()["deal"]
    assert deal["day"] == 34
    assert [p["label"] for p in deal["pills"]] == ["Payment overdue", "1 approval waiting"]
    assert [(s["key"], s["state"], s["note"]) for s in deal["stages"]] == [
        ("read", "done", "day 0"), ("negotiated", "done", "day 0"), ("early_payment", "done", "day 2"),
        ("collecting", "now", "RCV-A late"), ("fulfilled", "todo", "day 334")]
    assert [(e["day"], e["label"]) for e in deal["changes"]] == [
        (0, "You confirmed"), (0, "Buyer asked"), (0, "Agent replied"), (0, "Buyer accepted"), (2, "Bank feed")]
    assert deal["changes"][3]["text"] == ("early settlement of ¥257,200.00 of RCV-A at 0.85%, paid by day 2; booked "
                                          "by the agent (Tier 1)")
    assert deal["changes"][4]["text"] == "¥255,013.80 received on RCV-A (the agreed early payment)"
    rcv = deal["invoices"][0]
    assert (rcv["id"], rcv["outstanding_display"], rcv["due_day"], rcv["status"], rcv["status_text"]) == (
        "RCV-A", "¥162,800.00", 32, "LATE", "2 days late")
    assert rcv["notes"] == ["¥257,200.00 settled early on day 2"]
    second = deal["invoices"][1]
    assert (second["label"], second["status"], second["notes"]) == (
        "Invoice of day 2", "ADVANCE_WAITING", ["¥200,000.00 advance waiting for your approval (APR-000001)"])
    assert deal["invoices"][2]["status"] == "NOT_DUE"
    force = {r["key"]: (r["value_display"], r["vs_contract"]) for r in deal["in_force"]}
    assert force["payment_terms"] == ("45 days", "SAME") and force["price"] == ("¥420,000.00", "SAME")
    assert force["early_payment"][1] == "DIFFERENT" and force["rebate"] == ("None", "NONE")
    assert all(x["status"] == "ok" for x in deal["checks"])
    assert any("0.85% early payment is within the contract's 1.20%" in x["text"] for x in deal["checks"])
    assert deal["next_action"]["text"] == ("Chase the ¥162,800.00 on RCV-A (2 days late). Review APR-000001: a "
                                           "¥200,000.00 advance on the invoice of day 2 to stay above your floor on "
                                           "day 42.")
    assert [a["href"] for a in deal["next_action"]["actions"]] == ["/approvals", "/reconciliation"]
    assert [d["text"] for d in deal["owed_by_us"]["documents"]] == [
        "a delivery note signed by the Buyer's warehouse", "a VAT special invoice (fapiao) for the Batch",
        "a quality inspection certificate for the Batch"]


def test_the_summary_is_read_only(client):
    from app.api.runtime import get_runtime

    confirm_demo_documents(client)
    run_demo_to_day_34(client)
    rt = get_runtime()
    before = (rt.store.get_state(), len(rt.store.operations()), len(rt.store.approvals()), len(rt.store.security_events()))
    client.get("/deals")
    client.get("/deals/BUYER-1")
    client.get("/documents")
    after = (rt.store.get_state(), len(rt.store.operations()), len(rt.store.approvals()), len(rt.store.security_events()))
    assert after == before


# ---------------------------------------------------------------- the contract check (the first slips check)


def _confirm_text(client: TestClient, text: str) -> None:
    d = client.post("/documents", json={"kind": "BUYER_CONTRACT", "counterparty_id": "BUYER-1", "text": text}).json()
    d = d["document"]
    assert client.post(f"/documents/{d['id']}/confirm", json={"doc_hash": d["doc_hash"]}).json()["result"]["status"] == \
        "EXECUTED"


def _demo_text() -> str:
    return contract_fixture_bytes("FHR_SUPPLY_AGREEMENT")[1].decode()


def test_a_contract_counted_from_acceptance_is_a_slip(client):
    _confirm_text(client, _demo_text().replace("forty-five (45) days after the Invoice Date",
                                               "forty-five (45) days after acceptance of the Batch"))
    checks = client.get("/deals/BUYER-1").json()["deal"]["checks"]
    assert checks[0]["status"] == "warn" and "from acceptance (clause 4.2), but the books count them from the invoice " \
                                              "date" in checks[0]["text"]


def test_a_different_price_is_a_slip(client):
    _confirm_text(client, _demo_text().replace("RMB 420,000 (four hundred and twenty thousand yuan)", "RMB 400,000"))
    checks = client.get("/deals/BUYER-1").json()["deal"]["checks"]
    assert any(x["status"] == "warn" and "the contract price is ¥400,000.00" in x["text"] for x in checks)


def test_an_accepted_terms_change_needs_a_written_amendment(client):
    from app.api.runtime import get_runtime
    from app.domain.models import AcceptOffer, Actor

    _confirm_text(client, _demo_text())
    rt = get_runtime()
    doc = {"doc_id": "TERMS-30", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0,
           "text": "We'll move you to 30-day terms going forward."}
    offer = client.post("/offers", json={"documents": [doc], "counterparty_id": "BUYER-1"}).json()["offer"]
    v = client.post(f"/offers/{offer['offer_id']}/evaluate").json()
    assert v["outcome"] == "NEEDS_OWNER_APPROVAL", v["outcome"]  # any change of terms is the owner's
    c = rt.executor.propose_commitment(v["id"], expires_day=5)
    res = rt.executor.execute(AcceptOffer(op_id="acc-1", idempotency_key="acc-1", mandate_version=1,
                                          requested_by=Actor.OWNER, day=0, offer_id=offer["offer_id"],
                                          offer_version=1, terms_hash=c.terms_hash, nonce=c.nonce))
    assert res.status.value == "PENDING_APPROVAL"
    assert rt.executor.decide(res.approval_id, True, Actor.OWNER).status.value == "EXECUTED"
    deal = client.get("/deals/BUYER-1").json()["deal"]
    texts = [x["text"] for x in deal["checks"] if x["status"] == "warn"]
    assert any("requires amendments made in writing and signed by both Parties (clause 9.1)" in t for t in texts), texts
    assert any(r["key"] == "payment_terms" and r["vs_contract"] == "DIFFERENT" for r in deal["in_force"])
