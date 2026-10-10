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
    assert agreement["event_text"].startswith("Agreement with Foshan Home Retail Co. recorded; concessions booked against your budget: ¥")
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


def test_an_approval_that_was_answered_no_longer_reads_waiting(client):
    # day 0's plan runs alone; cap the ceiling so the same plan waits for the owner
    rt = get_runtime()
    m = rt.store.get_mandate()
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign
    rt.store.put_mandate(sign(m.model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    a = client.get("/home").json()["next_action"]
    client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    pending = [o for o in _ops(client) if o["status"] == "PENDING_APPROVAL"]
    assert pending and all(o["event_text"].startswith("Waiting for your approval: ") for o in pending)
    aid = next(o["approval_id"] for o in pending if o["kind"] == "SUBMIT_INVOICE_FOR_FINANCING")
    assert client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    ops = _ops(client)
    waiting_then = next(o for o in ops if o["status"] == "PENDING_APPROVAL" and o["approval_id"] == aid)
    assert waiting_then["event_text"].startswith("Approval requested: ")
    assert any(o["event_text"].startswith("You approved ") for o in ops if o["approval_id"] == aid and o["status"] == "EXECUTED")
    # the other leg is still waiting, and still says so
    others = [o for o in ops if o["status"] == "PENDING_APPROVAL" and o["approval_id"] != aid]
    assert all(o["event_text"].startswith("Waiting for your approval: ") for o in others)
    # the home leaves the answered "waiting" entry out of the changes
    changes = client.get("/home").json()["changes"]
    assert not any(c["kind"] == "WAITING" and "invoice financing" in c["event_text"] for c in changes)


# ---------------------------------------------------------------- a clock move in the owner's words (Wave 8, finding 1)

ENGINE_WORDS = ("flow(s)", "commitment(s)", "invoice(s)", "payment(s)", "ADVANCE_CLOCK", "give-aways", "CMT-", "day ", "Clock moved")


def test_clock_move_words_count_what_happened_and_leave_out_what_did_not():
    from app.api.presentation import clock_words
    one = {"from_day": 30, "to_day": 34, "posted_debt_service": [{"x": 1}], "debt_service_fen": -4_500_000,
           "issued_receivable_ids": ["RI:BUYER-1:32"], "posted_flow_ids": [], "expired_commitment_ids": []}
    assert clock_words(one) == "4 days passed: the ¥45,000.00 debt payment went out and one invoice was issued."
    assert clock_words(one, "zh") == "过去了 4 天：已支付 ¥45,000.00 的债务还款，已开出 1 张发票。"
    many = {"from_day": 0, "to_day": 1, "posted_flow_ids": ["a", "b"], "issued_receivable_ids": ["r1", "r2", "r3"],
            "expired_commitment_ids": ["c"], "posted_debt_service": [{}, {}], "debt_service_fen": -9_000_000}
    assert clock_words(many) == ("1 day passed: 2 debt payments totalling ¥90,000.00 went out, 2 scheduled cash movements were "
                                 "recorded, 3 invoices were issued and one agreement expired.")
    assert clock_words({"from_day": 3, "to_day": 5}) == "2 days passed; nothing was due."
    assert clock_words({"from_day": 3, "to_day": 5}, "zh") == "过去了 2 天，没有到期事项。"
    assert clock_words({}) is None
