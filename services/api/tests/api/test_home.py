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
    # Business words: the reserve is the "minimum cash reserve", days are distances from today, authority is the owner's
    assert h["headline"] == "Your cash reserve becomes unsafe in 12 days."
    assert h["note"] == "Cash falls to ¥60k, ¥240k below your ¥300k minimum cash reserve."
    assert h["worst"] == "Worst point: −¥105k in 30 days if you do nothing."
    assert h["plan_note"] == "A funding plan is ready, within your signed limits. No approval is needed."
    assert h["cash"]["first_breach_cash_short"] == "¥60k" and h["cash"]["lowest_short"] == "−¥105k" and h["cash"]["floor_short"] == "¥300k"
    # what is driving it, from the projection's own events
    assert h["cash"]["drivers"] == ["Payroll of ¥340k falls due in 12 days.", "The next receipt, ¥420k, lands only in 32 days."]
    assert h["cash"]["cash_display"] == "¥400,000.00" and h["cash"]["floor_display"] == "¥300,000.00"
    assert h["cash"]["lowest_display"] == "−¥105,000.00" and h["cash"]["lowest_day"] == 30
    a = h["next_action"]
    # The recommendation is the router's cheapest runnable plan (wayfinder #15), the figure the documents quote
    assert a["plan_source"] == "router"
    assert a["title"] == ("Draw ¥150,000.00 on Bank credit line and finance ¥255,000.00 of the ¥420,000.00 invoice to "
                          "Foshan Home Retail Co. on Invoice financing (onboarded platform)")
    assert a["receive_display"] == "¥405,000.00" and a["needs_owner"] is False and a["cheaper_option"] is None
    assert a["outcome_title"] == "Secure ¥405k of funding" and a["after_lowest_short"] == "¥300k"
    assert a["components"] == [{"amount_short": "¥150k", "what": "Bank credit line", "lands_when": "today",
                                "name_display": "Bank credit line", "cost_display": "¥841.64"},
                               {"amount_short": "¥255k", "what": "against the ¥420k invoice to Foshan Home Retail Co.", "lands_when": "in 3 days",
                                "name_display": "Invoice financing (onboarded platform)", "cost_display": "¥2,272.29"}]
    # all-in: every leg priced on the router's own convention, the basis said in words, nothing left to a footnote
    assert a["cost_total_display"] == "¥3,113.93" and a["cost_display"] == "¥3,113.93" and a["cost_note"] is None
    assert [(c["label"], c["display"]) for c in a["cost_breakdown"]] == [
        ("Bank credit line: draw ¥150,000.00, repaid in 32 days", "¥841.64"),
        ("Invoice financing (onboarded platform): advance ¥255,000.00 on the ¥420,000.00 invoice to Foshan Home Retail Co. due in 32 days", "¥2,272.29")]
    assert a["lands_day"] == 3 and [leg["lands_day"] for leg in a["legs"]] == [0, 3]
    assert [leg["cost_display"] for leg in a["legs"]] == ["¥841.64", "¥2,272.29"]
    assert a["if_nothing"] == "¥240,000.00 below your minimum cash reserve in 12 days; the gap peaks at ¥405,000.00 in 30 days."
    assert a["after"] == "Cash stays above your minimum cash reserve for the next 120 days."
    # the alert's own cure (a different plan, priced on its own basis) is a fallback beside the recommendation, not its figures
    assert "A committed cure exists" not in a["detail"] and "lasts until in" not in a["detail"]
    assert ("A fallback also exists: draw on Bank credit line ¥150,000.00 and finance an invoice on Invoice financing (onboarded platform) "
            "for ¥336,000.00, at ¥2,994.08 (11.2% a year for 29 days); FLOW recommends the plan above.") in a["detail"]
    assert a["authority_text"] == "Within your signed limits. No additional approval required." and a["lands_when"] == "in 3 days"
    assert h["cash"]["lowest_when"] == "in 30 days" and h["cash"]["first_breach_when"] == "in 12 days"
    assert h["receivables"]["open_total_display"] == "¥420,000.00" and h["receivables"]["overdue_total_display"] == "¥0.00"
    assert a["cost_basis"].startswith("Estimated through the expected repayment of the Bank credit line in 32 days")
    assert a["why"].startswith("The cheapest plan your committed facilities can fund in time")
    s1 = a["suggestions"][1]
    assert (s1["operation_kind"], s1["facility_id"], s1["receivable_id"], s1["amount_fen"]) == (
        "SUBMIT_INVOICE_FOR_FINANCING", "FAC-IF", "RCV-A", 25500000)
    # one projection for every figure and the chart: the baseline and the same books with the plan applied
    series, plan_series = h["cash"]["series"], h["cash"]["plan_series"]
    assert len(series) == 121 and series[12]["closing_display"] == "¥60,000.00" and series[30]["closing_display"] == "−¥105,000.00"
    assert series[12]["events"][0]["label"] == "Payroll" and series[12]["events"][0]["amount_display"] == "−¥340,000.00"
    assert min(d["closing_fen"] for d in series) == h["cash"]["lowest_fen"]
    assert len(plan_series) == 121 and min(d["closing_fen"] for d in plan_series) >= h["cash"]["floor_fen"]
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
    # the act's own results carry the same business sentences (the mock ledger replays them)
    assert [x["event_text"] for x in r["results"]] == [
        "¥150,000.00 drawn on the Bank credit line. Cash received today.",
        "¥255,000.00 of invoice financing drawn against the Foshan Home Retail Co. invoice. Funds arrive in 3 days."]
    h = client.get("/home").json()
    assert h["status"] == "WATCH" and h["next_action"] is None
    assert h["headline"] == "You're covered." and h["plan_note"] is None
    assert h["note"].startswith("Cash stays above your ¥300k minimum cash reserve for the next 120 days.")
    assert h["cash"]["in_transit"]["lots"] == [{"facility_name": "Invoice financing (onboarded platform)",
                                                "amount_display": "¥255,000.00", "arrival_day": 3, "arrival_when": "in 3 days",
                                                "headline": "¥255k funding arriving in 3 days"}]
    assert h["cash"]["plan_series"] is None
    kinds = [c["kind"] for c in h["changes"]]
    assert kinds == ["OPERATION", "OPERATION"] and "Bank credit line" in h["changes"][1]["text"]
    # the changes lead with a business sentence; the executor's own sentence stays in `text` for the audit level
    assert [c["event_text"] for c in h["changes"]] == [
        "¥255,000.00 of invoice financing drawn against the Foshan Home Retail Co. invoice. Funds arrive in 3 days.",
        "¥150,000.00 drawn on the Bank credit line. Cash received today."]
    assert h["changes"][0]["event_detail"] == "Financed through Invoice financing (onboarded platform)."
    assert h["changes"][1]["event_detail"] is None
    assert h["changes"][0]["text"].startswith("Advance ¥255,000.00 on ")
    # on its way: the headline, in both languages, beside the cash that is already here
    assert h["cash"]["in_transit"]["lots"][0]["headline"] == "¥255k funding arriving in 3 days"
    zh = client.get("/home?lang=zh").json()
    assert zh["cash"]["in_transit"]["lots"][0]["headline"] == "¥255k 资金将于3 天后到账"
    assert zh["changes"][1]["event_text"] == "已从Bank credit line提取 ¥150,000.00。资金今天已到账。"


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
    # both legs of the router plan are above a 5% ceiling; each queued leg carries the router's own cost line
    assert [x["op_id"].split(":")[-2] for x in rows] == ["plan", "plan"]
    priced = [x["presentation"] for x in rows if x["kind"] == "SUBMIT_INVOICE_FOR_FINANCING"]
    assert priced and priced[0]["cost_display"] == "¥2,272.29" and priced[0]["lands_day"] == 3
    assert priced[0]["headline"] == "Approve ¥255,000.00 of invoice financing?"
    drawn = [x["presentation"] for x in rows if x["kind"] == "DRAW_FACILITY"]
    assert drawn[0]["cost_display"] == "¥841.64"
    h = client.get("/home").json()
    assert {c["cost_display"] for c in h["approvals"]} == {"¥841.64", "¥2,272.29"}


def test_chinese_sentences(client):
    h = client.get("/home?lang=zh").json()
    assert h["lang"] == "zh" and h["headline"] == "您的现金储备将在12 天后不再安全。"
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
    rec = client.get("/reconciliation").json()["reconciliation"]
    # the Business sentences carry names, never the commitment or invoice ids; the engine's sentence stays beside them
    assert all("CMT-" not in r["detail_when"] and "RCV-" not in r["detail_when"] for r in rec["promised"] + rec["receipts"])
    assert rec["promised"][0]["detail_when"].startswith("The agreed ¥255,013.80 for the ¥420,000.00 invoice to Foshan Home Retail Co.")
    # a full sentence under the buyer's name: a capital, commas round the due clause, a full stop
    assert rec["promised"][0]["detail_when"] == "The agreed ¥255,013.80 for the ¥420,000.00 invoice to Foshan Home Retail Co., due in 30 days, arrived."
    assert "CMT-" in rec["promised"][0]["detail"]
    h = client.get("/home").json()
    assert h["changes"][0]["kind"] == "RECEIPT" and h["changes"][0]["text"].startswith("Received ¥255,013.80")
    client.post("/clock/advance", json={"days": 28})
    client.post("/clock/advance", json={"days": 4})
    h = client.get("/home").json()
    assert h["status"] == "ACTION_NEEDED"
    assert h["headline"] == "Your cash reserve becomes unsafe in 8 days."
    assert h["note"] == "Cash falls to ¥100k, ¥200k below your ¥300k minimum cash reserve."
    assert h["plan_note"] == "A funding plan is ready. It needs your approval because of its cost."
    assert h["cash"]["drivers"][0] == "Payroll of ¥200k falls due in 8 days."
    [late] = h["receivables"]["past_due"]
    assert late["buyer_name"] == "Foshan Home Retail Co." and late["face_display"] == "¥162,800.00" and late["days_late"] == 2
    assert late["due_when"] == "2 days ago"
    assert h["receivables"]["overdue_total_display"] == "¥162,800.00"
    import re as _re
    assert not any(_re.search(r"\bday \d", c["text"]) for c in h["changes"]), [c["text"] for c in h["changes"]]
    assert all(c["when"] for c in h["changes"])
    assert any(c["kind"] == "LATE" and "Foshan Home Retail Co." in c["text"] for c in h["changes"])
    assert not any("Clock moved" in c["text"] for c in h["changes"])
    a = h["next_action"]
    assert a["cost_display"] == "¥1,782.19" and a["cost_total_display"] == "¥1,782.19" and a["rate_text"] == "32.5%" and a["lands_day"] == 37
    assert a["needs_owner_reason"] == "The yearly cost of 32.5% is above the 15.00% limit you signed for funding without your approval."
    assert a["authority_text"].startswith("Needs your approval: The yearly cost of 32.5%")
    assert a["lands_when"] == "in 3 days" and a["after"] == "Cash stays above your minimum cash reserve for the next 120 days."
    # The router's cheapest plan (¥80,000 on RI:BUYER-1:32 + ¥120,000 on RI:BUYER-1:2) needs two approvals, so the
    # single-approval cure is shown and the cheaper option is named (wayfinder #15 refinement)
    assert a["plan_source"] == "alert" and a["cheaper_option"]["approvals"] == 2
    c = a["cheaper_option"]
    assert c["cost_total_display"] == "¥1,706.10"
    # the router's total is net: the two advances cost ¥2,495.07 and the plan repays the drawn line 30 days sooner,
    # so the lines shown add up to the total and the saving is named rather than hidden in an equation
    assert c["label"] == ("Finance ¥80,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co. on Invoice financing (onboarded platform) and "
                          "Finance ¥120,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co. on Invoice financing (onboarded platform)")
    assert c["legs"][-1] == "Change in other interest and fees across the forecast: −¥788.97"
    # no invoice id is left in the sentences; the two invoices of the same buyer and face stay apart by their due day
    assert c["legs"][:2] == [
        "Invoice financing (onboarded platform): advance ¥80,000.00 on the ¥420,000.00 invoice to Foshan Home Retail Co. due in 43 days: ¥1,425.75",
        "Invoice financing (onboarded platform): advance ¥120,000.00 on the ¥420,000.00 invoice to Foshan Home Retail Co. due in 13 days: ¥1,069.32"]
    assert not any("RI:BUYER-1" in c_["text"] for c_ in h["changes"]) and not any("RI:BUYER-1" in leg for leg in c["legs"])
    assert any("¥162,800.00 outstanding from Foshan Home Retail Co." in c_["text"] for c_ in h["changes"])
    assert a["why"].startswith("The cheapest option, ¥1,706.10 in all (including ¥788.97 less in other interest and fees across the "
                               "forecast), needs 2 separate approvals; this one needs one.")
    # queued for the owner, the approval says what declining leaves: the alert's shortfall sentence, relative to today
    client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    [card] = client.get("/home").json()["approvals"]
    assert card["if_decline"] == "¥200,000.00 below your minimum cash reserve in 8 days; the gap peaks at ¥200,000.00 in 8 days."
    # one cure, one horizon: the approval card says what the home says (the plan projected on the books), on the home and in the queue
    assert card["protects"] == a["after"] == "Cash stays above your minimum cash reserve for the next 120 days."
    [row] = client.get("/approvals/queue").json()["approvals"]
    assert row["presentation"]["reason"] == ("The yearly cost of 32.5% is above the 15.00% limit you signed for funding without your approval.")
    assert card["reason"] == row["presentation"]["reason"]
    assert row["presentation"]["protects"] == a["after"]
    assert client.get("/home?lang=zh").json()["approvals"][0]["protects"] == client.get("/home?lang=zh").json()["next_action"]["after"]
    # the queued fix reads as a business event in the changes, never as the executor's "Queued for owner approval (APR-…)"
    waiting = next(c for c in client.get("/home").json()["changes"] if c["kind"] == "WAITING")
    assert waiting["event_text"] == ("Waiting for your approval: ¥200,000.00 of invoice financing at 32.5% a year, above the "
                                     "15.00% limit you signed for funding without your approval.")
    assert waiting["text"].startswith("Queued for owner approval (APR-000001): ")
    assert "APR-" not in waiting["event_text"] and "mandate" not in waiting["event_text"]
    # once approved the same fix reads "You approved …" with its landing as a distance from today
    assert client.post(f"/approvals/{card['id']}", json={"decision": "APPROVE"}).json()["result"]["status"] == "EXECUTED"
    approved = client.get("/home").json()["changes"]
    assert approved[0]["event_text"] == "You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days."
    assert not any(c["event_text"].startswith("Advance ") for c in approved)
    # one operation, one story: the decision is the news, and the earlier "waiting" entry is not repeated beside it
    assert not any(c["kind"] == "WAITING" or "Waiting for your approval" in c["event_text"] for c in approved)
    assert sum("¥200,000.00 of invoice financing" in c["event_text"] for c in approved) == 1


def test_run_funding_plan_binds_to_the_plan_shown_and_refuses_a_stale_one(client):
    h = client.get("/home").json()
    a = h["next_action"]
    assert a["plan_source"] == "router"
    stale = [dict(x, amount_fen=x["amount_fen"] + 100) for x in a["suggestions"]]
    r = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": stale})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALERT_CHANGED"
    r = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert [x["kind"] + ":" + x["status"] for x in r["results"]] == ["DRAW_FACILITY:EXECUTED", "SUBMIT_INVOICE_FOR_FINANCING:EXECUTED"]
    assert r["executed"] == 2 and r["cured"]
    ops = client.get("/ledger").json()["operations"]
    assert [o["op_id"] for o in ops[-2:]] == [f"alert:{a['alert_id']}:v{a['state_version']}:plan:0",
                                               f"alert:{a['alert_id']}:v{a['state_version']}:plan:1"]
    plan = client.post("/router/plan").json()["committed"]
    assert plan["actions"] == [] and client.get("/home").json()["next_action"] is None


def test_what_changed_since_the_owners_last_visit(client):
    # the deal on day 0, the receipt on day 2; a visit marker after the receipt leaves nothing to report
    o = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]["offer_id"]
    client.post(f"/offers/{o}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
    client.post(f"/negotiate/{o}", json={"buyer_profile": "cooperative"})
    client.post("/clock/advance", json={"days": 2})
    promised = client.get("/reconciliation").json()["reconciliation"]["promised"][0]
    mv = client.get("/mandate").json()["mandate"]["version"]
    client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "t-r2", "idempotency_key": "t-r2", "mandate_version": mv,
        "requested_by": "SYSTEM", "receivable_id": promised["receivable_id"], "amount_fen": promised["expected_fen"],
        "bank_reference": "T-RCPT-2"})
    client.post("/clock/advance", json={"days": 3})
    week = client.get("/home").json()
    assert week["since_day"] is None and any(c["kind"] == "RECEIPT" for c in week["changes"])
    since = client.get("/home?since_day=3").json()
    assert since["since_day"] == 3 and not any(c["kind"] == "RECEIPT" for c in since["changes"])
    assert client.get("/home?since_day=0").json()["changes"] == week["changes"]


def test_document_decisions_are_not_news_on_the_home(client):
    # the demo reset's three confirmations are on the chain but change no books; Activity and Deals show them
    bare = client.get("/home").json()["changes"]
    assert client.post("/demo/reset").status_code == 200
    assert [o["kind"] for o in client.get("/ledger").json()["operations"]] == ["CONFIRM_DOCUMENT"] * 3
    assert client.get("/home").json()["changes"] == bare


def test_one_fix_per_alert_the_other_family_is_refused_while_the_first_waits(client):
    # a 5% ceiling: the router plan needs the owner, so "Run funding plan" queues its two legs
    rt = get_runtime()
    from app.mandate.fixture import load_demo_owner_key
    from app.mandate.signing import sign
    rt.store.put_mandate(sign(rt.store.get_mandate().model_copy(update={"max_apr_bp": 500}), load_demo_owner_key()["private_key_hex"]))
    h = client.get("/home").json()
    a = h["next_action"]
    assert a["plan_source"] == "router" and a["needs_owner"] is True
    first = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}).json()
    assert first["pending_approval"] == 2
    # the same plan again: the executor's DUPLICATE, nothing new queued (the contract the alerts page relies on)
    again = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]})
    assert again.status_code == 200 and {x["status"] for x in again.json()["results"]} == {"DUPLICATE"}
    # the alert's own cure (the alerts page's suggestions) while the plan waits: refused, not queued beside it
    alert = next(x for x in client.get("/alerts").json()["alerts"] if x["id"] == a["alert_id"])
    cure = [{"operation_kind": s["operation_kind"], "facility_id": s["facility_id"], "receivable_id": s["receivable_id"],
             "amount_fen": s["amount_fen"]} for s in alert["suggested"]]
    other = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": cure})
    assert other.status_code == 409 and other.json()["detail"]["code"] == "ALREADY_QUEUED"
    assert len([x for x in client.get("/approvals/queue").json()["approvals"] if x["status"] == "PENDING"]) == 2


def test_since_day_after_a_reset_falls_back_to_the_week(client):
    h = client.get("/home?since_day=34").json()  # a visit marker from a previous run, later than today
    assert h["since_day"] is None and h["changes"] == client.get("/home").json()["changes"]


def test_the_lowest_point_carries_a_server_tone_bad_below_zero_warn_below_the_reserve_ok_otherwise(client):
    """`cash.lowest_tone` on the home read (the cash page reads the same block)."""
    rt = get_runtime()
    state, mandate = load_scenario()
    seen = {}
    for extra_fen in (0, 25_000_000, 50_000_000):  # day 0's lowest point is -¥105k against a ¥300k reserve
        rt.store.put_state(state.model_copy(update={"cash_fen": state.cash_fen + extra_fen}))
        cash = client.get("/home").json()["cash"]
        seen[extra_fen] = (cash["lowest_fen"], cash["lowest_tone"])
    assert seen[0][0] < 0 and seen[0][1] == "bad"
    assert 0 <= seen[25_000_000][0] < mandate.min_cash_fen and seen[25_000_000][1] == "warn"
    assert seen[50_000_000][0] >= mandate.min_cash_fen and seen[50_000_000][1] == "ok"
