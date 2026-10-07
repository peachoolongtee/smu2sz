"""Wave 6 (wayfinder #35): `GET /ledger` carries `event_text` beside `summary` and `message_when`: the business sentence for
what the operation did, built from the typed operation and the executor's result (never priced here), in English. The
executor's own sentence stays in `summary` for the audit level."""

from __future__ import annotations

from app.api.runtime import get_runtime

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def _ops(client) -> list[dict]:
    return client.get("/ledger").json()["operations"]


def test_executed_advance_and_draw_read_as_business_events(client):
    a = client.get("/home").json()["next_action"]
    client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    by_kind = {o["kind"]: o for o in _ops(client)}
    adv, draw = by_kind["SUBMIT_INVOICE_FOR_FINANCING"], by_kind["DRAW_FACILITY"]
    assert adv["event_text"] == ("¥255,000.00 of invoice financing drawn against the Foshan Home Retail Co. invoice. "
                                 "Funds arrive in 3 days.")
    assert draw["event_text"] == "¥150,000.00 drawn on the Bank credit line. Cash received today."
    # the executor's sentence is untouched for the audit level
    assert adv["summary"].startswith("Advance ¥255,000.00 on ") and draw["summary"].startswith("Drew ¥150,000.00 on FAC-LINE")


def test_a_queued_then_declined_approval_reads_waiting_then_declined(client):
    rt = get_runtime()
    m = rt.store.get_mandate()
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign
    rt.store.put_mandate(sign(m.model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    a = client.get("/home").json()["next_action"]
    client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    queued = [o for o in _ops(client) if o["status"] == "PENDING_APPROVAL"]
    assert queued and all(o["event_text"].startswith("Waiting for your approval: ") for o in queued)
    assert any("of invoice financing at " in o["event_text"] and "a year, above the 5.00% limit you signed for funding without "
               "your approval." in o["event_text"] for o in queued)
    assert not any("APR-" in o["event_text"] or "agent may borrow" in o["event_text"] for o in queued)
    aid = next(o["approval_id"] for o in queued if o["kind"] == "SUBMIT_INVOICE_FOR_FINANCING")
    client.post(f"/approvals/{aid}", json={"decision": "REJECT"})
    declined = [o for o in _ops(client) if o["status"] == "REFUSED"]
    assert [o["event_text"] for o in declined] == ["You declined ¥255,000.00 of invoice financing."]


def test_a_refusal_says_what_was_asked_and_why(client):
    mv = client.get("/mandate").json()["mandate"]["version"]
    res = client.post("/operations", headers=BANK, json={
        "kind": "DRAW_FACILITY", "op_id": "t-big", "idempotency_key": "t-big", "mandate_version": mv,
        "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 99_000_000_000, "day": 0}).json()["result"]
    assert res["status"] == "REFUSED"
    refused = next(o for o in _ops(client) if o["op_id"] == "t-big")
    text = refused["event_text"]
    assert text.startswith("Refused: draw ¥990,000,000.00 on Bank credit line. ") and text.endswith(".")
    assert "FAC-LINE" not in text and refused["summary"].startswith("Refused: ")


def test_a_receipt_names_the_buyer_and_keeps_the_figure(client):
    o = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{o}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{o}", json={"buyer_profile": "cooperative"})
    client.post("/clock/advance", json={"days": 2})
    promised = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
    mv = client.get("/mandate").json()["mandate"]["version"]
    client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "t-r9", "idempotency_key": "t-r9", "mandate_version": mv,
        "requested_by": "SYSTEM", "receivable_id": promised["receivable_id"], "amount_fen": promised["expected_fen"],
        "bank_reference": "T-RCPT-9"})
    receipt = next(o for o in _ops(client) if o["kind"] == "RECEIVE_PAYMENT")
    assert receipt["event_text"] == "Received ¥255,013.80 from Foshan Home Retail Co."
    assert receipt["event_detail"] is None or "day " not in receipt["event_detail"]


def test_an_agreement_is_said_as_the_home_says_it_and_no_row_loses_its_sentence(client):
    o = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{o}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{o}", json={"buyer_profile": "cooperative"})
    rows = _ops(client)
    agreement = next(r for r in rows if r["kind"] == "ACCEPT_OFFER")
    assert agreement["event_text"].startswith("Agreement with Foshan Home Retail Co. recorded; future give-aways booked: ¥")
    assert "CMT-" not in agreement["event_text"]
    assert all(r["event_text"] for r in rows)


def test_a_queued_and_a_declined_application_are_nouns_not_commands(client):
    agent = {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}
    op = {"kind": "APPLY_FOR_FACILITY", "op_id": "t-apply", "idempotency_key": "t-apply", "mandate_version": 1,
          "requested_by": "AGENT", "facility_id": "FAC-GGL", "amount_fen": 20_000_000}
    res = client.post("/operations", json=op, headers=agent).json()["result"]
    assert res["status"] == "PENDING_APPROVAL"
    queued = next(o for o in _ops(client) if o["op_id"] == "t-apply")
    assert queued["event_text"].startswith("Waiting for your approval: an application for ¥200,000.00 on ")
    assert "FAC-GGL" not in queued["event_text"] and queued["event_detail"]
    client.post(f"/approvals/{res['approval_id']}", json={"decision": "REJECT"})
    declined = next(o for o in _ops(client) if o["status"] == "REFUSED")
    assert declined["event_text"].startswith("You declined an application for ¥200,000.00 on ")
