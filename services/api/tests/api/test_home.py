"""GET /home: the owner's home in business words, a presentation read over the engine's own results (alerts, the
queue, the log, the reconciliation). Every amount and day here is one the alerts or the executor already state; the
view only sentences them. The approvals queue carries the same presentation fields for its cards."""

from __future__ import annotations

from app.api.runtime import get_runtime
from app.domain.fixtures import load_scenario

BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}


def _exhaust_line(rt) -> None:
    state, _ = load_scenario()
    rt.store.put_state(state.model_copy(update={"facilities": [
        f.model_copy(update={"drawn_fen": f.limit_fen}) if f.id in ("FAC-LINE", "FAC-IF") else f
        for f in state.facilities]}))


def test_day_zero_answers_safe_do_cost(client):
    h = client.get("/home").json()
    assert h["day"] == 0 and h["status"] == "ACTION_NEEDED"
    assert h["headline"] == "Cash falls ¥240,000.00 below your ¥300,000.00 safe level on day 12 (in 12 days)."
    assert h["note"] == "The agent has a fix ready and can run it alone."
    assert h["cash"]["cash_display"] == "¥400,000.00" and h["cash"]["floor_display"] == "¥300,000.00"
    assert h["cash"]["lowest_display"] == "−¥105,000.00" and h["cash"]["lowest_day"] == 30
    a = h["next_action"]
    assert a["title"] == ("Draw ¥150,000.00 on Bank credit line and finance ¥336,000.00 of the ¥420,000.00 invoice to "
                          "Foshan Home Retail Co. on Invoice financing (onboarded platform)")
    assert a["receive_display"] == "¥486,000.00" and a["needs_owner"] is False
    # the invoice leg is priced by the alert; the open-ended draw is not, and the note says so
    assert a["cost_display"] == "¥2,994.08" and a["rate_text"] == "11.2%" and "not included" in a["cost_note"]
    assert a["lands_day"] == 3 and [leg["lands_day"] for leg in a["legs"]] == [0, 3]
    assert a["if_nothing"].startswith("¥240,000.00 below your safe level on day 12")
    assert a["after"] == "Cash stays above your safe level through day 31."
    s1 = a["suggestions"][1]
    assert (s1["operation_kind"], s1["facility_id"], s1["receivable_id"], s1["amount_fen"]) == (
        "SUBMIT_INVOICE_FOR_FINANCING", "FAC-IF", "RCV-A", 33600000)
    assert h["approvals"] == [] and h["pending_count"] == 0 and h["changes"] == []
    r = h["receivables"]
    assert r["past_due"] == [] and r["next_receipt"]["buyer_name"] == "Foshan Home Retail Co."
    assert r["next_receipt"]["due_day"] == 32 and r["open_total_display"] == "¥420,000.00"
    assert [w["kind"] for w in h["warnings"]] == ["RESERVE_HEADROOM_LOW"]


def test_the_fix_is_bound_to_what_the_home_showed_and_the_home_turns_calm(client):
    h = client.get("/home").json()
    a = h["next_action"]
    r = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["executed"] == 2 and r["cured"]
    h = client.get("/home").json()
    assert h["status"] == "WATCH" and h["next_action"] is None
    assert h["headline"] == "Cash stays above your ¥300,000.00 safe level for the next 120 days."
    assert h["cash"]["in_transit"]["lots"] == [{"facility_name": "Invoice financing (onboarded platform)",
                                                "amount_display": "¥336,000.00", "arrival_day": 3}]
    kinds = [c["kind"] for c in h["changes"]]
    assert kinds == ["OPERATION", "OPERATION"] and "Bank credit line" in h["changes"][1]["text"]


def test_a_queued_cure_is_a_question_with_its_cost_and_landing_day(client):
    _exhaust_line(get_runtime())
    h = client.get("/home").json()
    a = h["next_action"]
    assert a["needs_owner"] is True and a["pending_approval_id"] is None
    r = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["pending_approval"] == 1
    h = client.get("/home").json()
    # no committed facility can cure it (the line and the platform are full): CRITICAL, and the application waits
    assert h["status"] == "CRITICAL" and h["pending_count"] == 1
    assert h["next_action"]["pending_approval_id"] == "APR-000001"
    [card] = h["approvals"]
    assert card["id"] == "APR-000001" and card["headline"].startswith("Approve ") and card["headline"].endswith("?")
    # an application for an uncommitted facility: the alert prices nothing for it and nothing lands until it is committed
    assert card["kind"] == "APPLY_FOR_FACILITY" and card["cost_display"] is None and card["lands_day"] is None
    assert card["facility_name"] == "Equipment lease" and card["protects"] is None
    assert card["what"].startswith("Apply for ") and "FAC-" not in card["what"]
    # the queue row carries the same words for its card
    [row] = client.get("/approvals/queue").json()["approvals"]
    p = row["presentation"]
    assert p["headline"] == card["headline"] and p["what"] == card["what"] and p["facility_name"] == card["facility_name"]
    assert h["changes"][0]["kind"] == "WAITING"


def test_a_priced_cure_in_the_queue_carries_its_cost_and_landing_day(client):
    # cap the agent's rate ceiling below the invoice platform's tariff: the day-0 cure then needs the owner, priced
    rt = get_runtime()
    m = rt.store.get_mandate()
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign
    rt.store.put_mandate(sign(m.model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    h = client.get("/home").json()
    a = h["next_action"]
    assert a["needs_owner"] is True and "5.00%" in a["needs_owner_reason"]
    r = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert r["pending_approval"] >= 1
    rows = client.get("/approvals/queue").json()["approvals"]
    priced = [x["presentation"] for x in rows if x["kind"] == "SUBMIT_INVOICE_FOR_FINANCING"]
    assert priced and priced[0]["cost_display"] == "¥2,994.08" and priced[0]["lands_day"] == 3
    assert priced[0]["headline"] == "Approve ¥336,000.00 of invoice financing?"


def test_chinese_sentences(client):
    h = client.get("/home?lang=zh").json()
    assert h["lang"] == "zh" and h["headline"].startswith("现金将在第 12 天")
    assert h["next_action"]["title"].startswith("从Bank credit line提款 ¥150,000.00")


def test_a_late_buyer_is_named_in_receivables_and_changes(client):
    # the deal, the early payment, then the clock past the due day: as scripts/demo_run.py
    o = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{o}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{o}", json={"buyer_profile": "cooperative"})
    h = client.get("/home").json()
    assert h["status"] == "WATCH" and h["receivables"]["promised"]["expected_display"] == "¥255,013.80"
    assert any(c["kind"] == "AGREEMENT" and c["text"].startswith("Agreement with Foshan Home Retail Co. recorded") for c in h["changes"])
    client.post("/clock/advance", json={"days": 2})
    promised = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
    mv = client.get("/mandate").json()["mandate"]["version"]
    res = client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "t-r1", "idempotency_key": "t-r1", "mandate_version": mv,
        "requested_by": "SYSTEM", "receivable_id": promised["receivable_id"], "amount_fen": promised["expected_fen"],
        "bank_reference": "T-RCPT-1"})
    assert res.json()["result"]["status"] == "EXECUTED"
    h = client.get("/home").json()
    assert h["changes"][0]["kind"] == "RECEIPT" and h["changes"][0]["text"].startswith("Received ¥255,013.80")
    client.post("/clock/advance", json={"days": 28})
    client.post("/clock/advance", json={"days": 4})
    h = client.get("/home").json()
    assert h["status"] == "ACTION_NEEDED"
    assert h["headline"] == "Cash falls ¥200,000.00 below your ¥300,000.00 safe level on day 42 (in 8 days)."
    assert h["note"] == "The agent has a fix ready. It needs your approval because of its cost."
    [late] = h["receivables"]["past_due"]
    assert late["buyer_name"] == "Foshan Home Retail Co." and late["face_display"] == "¥162,800.00" and late["days_late"] == 2
    assert any(c["kind"] == "LATE" and "Foshan Home Retail Co." in c["text"] for c in h["changes"])
    assert not any("Clock moved" in c["text"] for c in h["changes"])
    a = h["next_action"]
    assert a["cost_display"] == "¥1,782.19" and a["rate_text"] == "32.5%" and a["lands_day"] == 37
    assert a["needs_owner_reason"] == "The yearly cost of 32.5% is above your 15.00% limit for what the agent may borrow alone."
    assert a["after"] == "Cash stays above your safe level through day 46."
