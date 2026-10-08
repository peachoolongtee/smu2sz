"""Wave 7 addendum (map #65, ticket #76), from the design review of the merged pages: the Deals workspace in the mission order with the
lines under the send, a state's tone and its "funded, reserve still short" words, one line for what came of an approval, the forecast
line shown once in Activity, the home's lowest point after the owner has acted, and the owner's words in the alert sentences. All
additive presentation: no figure, id or status changes, in either language."""

from __future__ import annotations

import json

from app.api.causality import mark_changed
from app.api.presentation import (
    approval_result_state,
    business_text,
    decision_state_text,
    decision_state_tone,
    funding_lines,
    plural,
)
from app.api.runtime import get_runtime
from tests.api.test_time_semantics import _act, _queue, _walk

EX01 = "EX01_PACKAGE"


def _evaluate(client, lang: str) -> dict:
    offer = client.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
    return client.post(f"/offers/{offer}/evaluate", params={"lang": lang}, json={"fixture_id": EX01}).json(), offer


# ---------------------------------------------------------------- 1 and 2. the workspace order and the lines under the send


def test_the_workspace_follows_the_mission_order_and_names_the_buyer_and_the_agreements(client):
    (en, offer), (zh, _) = _evaluate(client, "en"), _evaluate(client, "zh")
    order = ["buyer", "recommends", "priced_response", "buyer_asks", "financial_impact", "why_it_matters", "agreements", "advanced"]
    assert en["workspace"]["order"] == zh["workspace"]["order"] == order
    assert all(key in en["workspace"] for key in order)
    assert en["workspace"]["buyer"] == {"title": "Who is asking", "counterparty_id": "BUYER-1", "name": "Foshan Home Retail Co.",
                                        "offer_id": offer, "received_when": "today"}
    assert zh["workspace"]["buyer"]["title"] == "提出方" and zh["workspace"]["buyer"]["received_when"] == "今天"
    assert en["workspace"]["agreements"]["items"] == [] and en["workspace"]["agreements"]["title"] == "Your agreements with Foshan Home Retail Co."
    # once the counter is sent the agreement is listed, with the terms in words
    client.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"})
    after, _ = _evaluate(client, "zh")
    [item] = after["workspace"]["agreements"]["items"]
    assert item["status"] == "ACTIVE" and item["status_text"] == "已生效" and item["text"].startswith("买家可提前付款")


def test_the_send_has_lines_with_the_router_plans_own_figures_in_both_languages(client):
    (en, offer), (zh, _) = _evaluate(client, "en"), _evaluate(client, "zh")
    assert en["workspace"]["priced_response"]["send_scope_lines"] == [
        "Records the agreement with Foshan Home Retail Co. (needs your approval when it changes terms)",
        "Draws ¥149,986.20 on the Bank credit line today",
        "Funding cost ¥841.57 for the draw (already inside the ¥3,027.77 above)"]
    assert zh["workspace"]["priced_response"]["send_scope_lines"] == [
        "记录与Foshan Home Retail Co.的协议（若改变条款，需要您批准）", "从Bank credit line提款 ¥149,986.20，今天到账",
        "融资成本 ¥841.57（已计入上方的 ¥3,027.77）"]
    sent = client.post(f"/negotiate/{offer}", json={"buyer_profile": "cooperative"}).json()
    assert sent["plan"]["total_cost_display"] == "¥841.57" and sent["plan"]["actions"][0]["amount_fen"] == 14_998_620  # the lines are what runs
    assert "send_scope" in en["workspace"]["priced_response"]  # the sentence stays beside the lines


def test_funding_lines_say_each_leg_and_the_cost_and_nothing_when_nothing_runs(client):
    state = get_runtime().store.get_state()
    legs = [("DRAW", "FAC-LINE", 15_000_000, 0), ("FINANCE_INVOICE", "FAC-IF", 25_500_000, 3)]
    assert funding_lines(state, legs, 311_393, 0, "en") == [
        "Draws ¥150,000.00 on the Bank credit line today", "Requests ¥255,000.00 of invoice financing, arriving in 3 days",
        "Estimated cost ¥3,113.93"]
    assert funding_lines(state, legs, 311_393, 0, "zh") == [
        "从Bank credit line提款 ¥150,000.00，今天到账", "申请 ¥255,000.00 的发票融资，3 天后到账", "预计成本 ¥3,113.93"]
    assert funding_lines(state, [], None, 0, "en") == []


def test_an_offer_with_no_counter_has_no_priced_response_and_so_no_lines(client):
    offer = client.post("/offers", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}).json()["offer"]["offer_id"]
    ws = client.post(f"/offers/{offer}/evaluate", json={"fixture_id": "SEC_DEMO_FASTCAPITAL"}).json()["workspace"]
    assert ws["priced_response"] is None and ws["order"][0] == "buyer"


# ---------------------------------------------------------------- 3. a decision's state words and tone


def test_a_funding_done_with_the_reserve_still_short_says_so_and_every_state_has_a_tone():
    assert decision_state_text("FUNDING", "SETTLED", "en", residual=True) == "Funded, reserve still short"
    assert decision_state_text("FUNDING", "EXECUTED", "zh", residual=True) == "已融资，储备仍有缺口"
    assert decision_state_text("FUNDING", "SETTLED", "en") == "Done; the cash has landed"
    assert decision_state_text("FUNDING", "SETTLEMENT_PENDING", "en", residual=True) == "Requested; the cash is on its way"
    tone = lambda state, awaited=False, residual=False: decision_state_tone(state, awaited=awaited, residual=residual)
    assert tone("FAILED") == tone("MISSED") == "bad" and tone("FAILED", awaited=True) == "bad"
    assert tone("AUTHORIZATION_REQUIRED", awaited=True) == "warn" and tone("SETTLED", residual=True) == "warn"
    assert tone("FULFILLED") == tone("SETTLED") == "ok" and tone("EXECUTED") == "info"
    assert tone("SETTLEMENT_PENDING") == tone("AGREED") == tone("RECEIVED") == "info"
    assert tone("DECLINED") == tone("NO_DEAL") == tone("EXPIRED") == tone("REVOKED") == "neutral"


def test_every_decision_summary_carries_a_tone_in_both_languages(client):
    _walk(client)
    _act(client)
    rows = {lang: client.get("/decisions", params={"lang": lang}).json()["decisions"] for lang in ("en", "zh")}
    assert [(r["id"], r["state_tone"]) for r in rows["en"]] == [(r["id"], r["state_tone"]) for r in rows["zh"]]
    by_state = {r["state"]: r for r in rows["en"]}
    assert by_state["AUTHORIZATION_REQUIRED"]["state_tone"] == "warn" and by_state["MISSED"]["state_tone"] == "bad"
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    funding = next(r for r in client.get("/decisions").json()["decisions"] if r["family"] == "FUNDING")
    assert funding["residual"] is not None and funding["state_tone"] == "warn"
    detail = client.get(f"/decisions/{funding['id']}", params={"lang": "zh"}).json()
    assert detail["state_tone"] == "warn" and detail["state"] == funding["state"]
    home = client.get("/home").json()
    assert all(r["state_tone"] in ("warn", "bad", "ok", "info", "neutral") for r in home["open_decisions"])


# ---------------------------------------------------------------- 4. one line for what came of an approval


def test_the_queue_says_in_one_line_what_came_of_each_approval(client):
    _walk(client)
    _act(client)
    for lang, want in (("en", "Waiting for your approval"), ("zh", "等待您批准")):
        row = client.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]
        assert row["result_state_text"] == row["presentation"]["result_state_text"] == want and row["result_tone"] == "warn"
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    en = client.get("/approvals/queue").json()["approvals"][0]
    zh = client.get("/approvals/queue", params={"lang": "zh"}).json()["approvals"][0]
    assert (en["result_state_text"], en["result_tone"]) == ("Approved, cash arrives in 3 days", "info")
    assert (zh["result_state_text"], zh["result_tone"]) == ("已批准，资金将于3 天后到账", "info")


def test_the_words_for_a_declined_a_refused_and_a_received_approval():
    one = lambda **k: approval_result_state(today=10, lang="en", kind="DRAW_FACILITY", status="APPROVED", execution_status="EXECUTED",
                                            lands_day=None, **k)
    assert approval_result_state(kind="DRAW_FACILITY", status="REJECTED", execution_status="DECLINED", lands_day=None, today=10,
                                 lang="en") == ("Declined, nothing ran", "neutral")
    assert approval_result_state(kind="DRAW_FACILITY", status="APPROVED", execution_status="REFUSED", lands_day=None, today=10,
                                 lang="en") == ("Approved, did not run. No money moved.", "bad")
    assert approval_result_state(kind="DRAW_FACILITY", status="APPROVED", execution_status="REFUSED", lands_day=None, today=10,
                                 lang="zh") == ("已批准，但未能执行。资金未动。", "bad")
    assert one() == ("Approved, cash received", "ok")
    assert approval_result_state(kind="DRAW_FACILITY", status="APPROVED", execution_status="EXECUTED", lands_day=10, today=10,
                                 lang="en") == ("Approved, cash received", "ok")
    assert approval_result_state(kind="ACCEPT_OFFER", status="APPROVED", execution_status="EXECUTED", lands_day=None, today=10,
                                 lang="en") == ("Approved, agreement recorded", "ok")


def test_a_declined_approval_in_the_queue_reads_declined(client):
    _walk(client)
    _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "REJECT"})
    row = client.get("/approvals/queue").json()["approvals"][0]
    assert (row["result_state_text"], row["result_tone"]) == ("Declined, nothing ran", "neutral")


# ---------------------------------------------------------------- 5. the forecast line once


def test_the_forecast_line_is_marked_only_where_it_changes():
    rows = [{"why_it_matters": "A"}, {"why_it_matters": "A"}, {"why_it_matters": "B"}, {"why_it_matters": None}, {"why_it_matters": "B"},
            {"why_it_matters": "B"}]
    mark_changed(rows)
    assert [r["why_it_matters_changed"] for r in rows] == [True, False, True, False, True, False]


def test_activity_and_the_home_changes_say_whether_the_forecast_line_changed(client):
    _walk(client, receipt="half")
    _act(client)
    for rows in (client.get("/ledger").json()["operations"], client.get("/home").json()["changes"]):
        assert rows and all(isinstance(r["why_it_matters_changed"], bool) for r in rows)
        previous = None
        for row in rows:
            assert row["why_it_matters_changed"] == (bool(row["why_it_matters"]) and row["why_it_matters"] != previous)
            previous = row["why_it_matters"]
        assert sum(r["why_it_matters_changed"] for r in rows) < len(rows)  # a run that shares its forecast line shows it once
    zh = client.get("/ledger", params={"lang": "zh"}).json()["operations"]
    en = client.get("/ledger").json()["operations"]
    assert [r["why_it_matters_changed"] for r in zh] == [r["why_it_matters_changed"] for r in en]


# ---------------------------------------------------------------- 6. the home's lowest point


def test_the_lowest_point_says_if_nothing_more_is_done_only_after_the_owner_has_acted(client):
    _walk(client)
    before = client.get("/home").json()
    assert before["worst"] == "Worst point: −¥155k in 8 days if you do nothing."
    _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    en, zh = client.get("/home").json(), client.get("/home", params={"lang": "zh"}).json()
    assert en["worst"] == "Lowest point: ¥0.00 in 8 days if nothing more is done."
    assert zh["worst"] == "若不再采取其他行动，最低点为8 天后的 ¥0.00。"


# ---------------------------------------------------------------- 7. the owner's words in the alert sentences


def test_the_alert_titles_and_details_use_the_owners_words_with_the_right_plural(client):
    state = get_runtime().store.get_state()

    def said(text: str, today: int = 0) -> str | None:
        return business_text(state, text, today, "en")

    assert said("Reserve headroom thin on day 0") == "Cash is close to your minimum today"
    assert said("Reserve headroom thin on day 12") == "Cash is close to your minimum in 12 days"
    assert said("Cash stays above the floor but only by ¥0.00 on day 0 (1 day(s) under 10% of the floor).") == (
        "Cash stays above your minimum cash reserve by only ¥0.00 today (1 day with less than 10% of your minimum cash reserve to spare).")
    assert said("The conservative trajectory no longer counts on a dated receipt.") == "The cash forecast no longer counts on a dated receipt."
    assert said("A committed cure exists: DRAW_FACILITY FAC-LINE ¥1.00") == "A funding plan is available: draw on Bank credit line ¥1.00"
    assert said("DSCR headroom below 0.10× in month 2") == "DSCR is within 0.10× of its limit in month 2"
    assert said("DSCR 1.29× against mandate v1 limit 1.25× (headroom 0.04×); months affected: 1.") == (
        "DSCR 1.29× against mandate v1 limit 1.25× (0.04× above the limit); months affected: 1.")
    assert said("DSCR 1.13× against mandate v1 limit 1.25× (headroom −0.12×); months affected: 1.").count("0.12× below the limit") == 1
    assert said("Receivable RCV-A is 1 day(s) past due") .endswith("is 1 day past due")
    assert said("Receivable RCV-A is 2 day(s) past due").endswith("is 2 days past due")
    assert plural("1 invoice(s) issued, 3 commitment(s) expired, 1 whole period(s)") == "1 invoice issued, 3 commitments expired, 1 whole period"
    assert "headroom" not in said("reduce drawn balances to restore leverage headroom")


def test_no_business_sentence_of_the_home_or_the_alerts_still_says_the_engines_words(client):
    _walk(client, receipt="half")
    for path in ("/home", "/alerts", "/approvals/queue", "/ledger"):
        body = client.get(path).json()
        if path == "/alerts":  # the engine's own title, detail and note stay as written beside the `_when` twins
            body = [{k: v for k, v in a.items() if k.endswith("_when")} for a in body["alerts"]]
        text = json.dumps(body)
        for word in ("headroom thin", "Compare options", "committed cure", "trajectory", "day(s)", "Tier 2", "Tier-2", "reserve floor"):
            assert word not in text, (path, word)


def test_the_funding_cost_line_says_whether_it_is_inside_the_counters_cost_or_in_addition(client):
    from types import SimpleNamespace

    from app.api.workspace import send_scope_lines

    (en, _), (zh, _) = _evaluate(client, "en"), _evaluate(client, "zh")
    a = en["counters"][0]
    assert a["supplier_cost_display"] == "¥3,027.77" and "¥841.57" in a["formula"]  # Option A's cost is the discount plus this funding
    state = get_runtime().store.get_state()
    action = SimpleNamespace(kind=SimpleNamespace(value="DRAW"), facility_id="FAC-LINE", amount_fen=14_998_620, lands_day=0)
    plan = SimpleNamespace(actions=[action], executable_now=True, total_cost_fen=84_157)
    inside = send_scope_lines(state, "Foshan Home Retail Co.", plan, 0, "en", a)
    assert inside[-1] == "Funding cost ¥841.57 for the draw (already inside the ¥3,027.77 above)"
    other = {"supplier_cost_display": "¥1,000.00", "formula": "extension ¥900.00 + firm credit ¥100.00 = ¥1,000.00"}  # a price adjustment's cost
    assert send_scope_lines(state, "Foshan Home Retail Co.", plan, 0, "en", other)[-1] == "Funding cost ¥841.57 in addition"
    assert send_scope_lines(state, "Foshan Home Retail Co.", plan, 0, "zh", other)[-1] == "融资成本 ¥841.57（另计）"
    assert all("Estimated cost" not in line for line in en["workspace"]["priced_response"]["send_scope_lines"])


# ---------------------------------------------------------------- the residual sentence when the shortfall began in the past


def test_the_residual_sentence_says_how_long_the_reserve_has_been_short_when_it_began_in_the_past():
    from app.api.presentation import remaining_task_words

    assert remaining_task_words(30_000_000, 0, 57, "en") == (
        "Your minimum cash reserve has been ¥300,000.00 short for 57 days; no committed funding restores it. This needs your decision.")
    assert remaining_task_words(30_000_000, 56, 57, "en", True) == (
        "Your minimum cash reserve has been ¥300,000.00 short for 1 day; a funding plan is ready (see the next step).")
    assert remaining_task_words(30_000_000, 0, 57, "zh", True) == "您的最低现金储备已差 ¥300,000.00 达 57 天；融资方案已准备好（见下一步）。"
    # today or a future day keeps "from {when}"
    assert remaining_task_words(10_000_000, 57, 57, "en", True) == (
        "Your minimum cash reserve is still ¥100,000.00 short from today; a funding plan is ready (see the next step).")
    assert remaining_task_words(10_000_000, 60, 57, "en") .startswith("Your minimum cash reserve is still ¥100,000.00 short from in 3 days;")
    assert remaining_task_words(10_000_000, 60, 57, "zh", True) == "您的最低现金储备仍差 ¥100,000.00，从3 天后起；融资方案已准备好（见下一步）。"


def test_a_decided_card_says_how_long_the_reserve_has_been_short(client):
    _walk(client)
    _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    client.post("/clock/advance", json={"to_day": 40})
    for lang, want in (("en", "Cash has stayed ¥300,000.00 below your minimum cash reserve for 6 days."),
                       ("zh", "现金已连续 6 天比最低现金储备低 ¥300,000.00。")):
        card = client.get("/approvals/queue", params={"lang": lang}).json()["approvals"][0]
        assert card["presentation"]["protects"] == card["presentation"]["residual"]["text"] == want
    home = client.get("/home").json()
    assert home["remaining_task"] == ("Your minimum cash reserve is still ¥100,000.00 short from today; no committed funding restores it. "
                                      "This needs your decision.")  # began today: the forward form
