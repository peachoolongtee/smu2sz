"""Wave 8 pass A (wayfinder #47, ticket #57): the owner's words on the day-34 books. A clock move, an agreement, the comparison
roles and the approval result sentence are presentation reads over what the engine already decided; no figure is priced here."""

from __future__ import annotations

from tests.alerts.test_repay_alert import OWNER, to_day34
from tests.api.test_ledger_events import ENGINE_WORDS
from tests.nl import conftest as nl_conftest

rt = nl_conftest.rt  # the in-memory runtime and the app client of the chat tests
client = nl_conftest.client


def test_no_business_event_on_the_day34_books_speaks_the_engine(client, rt):
    to_day34(client, rt)
    rows = client.get("/ledger", headers=OWNER).json()["operations"]
    clocks = [r for r in rows if r["kind"] == "ADVANCE_CLOCK"]
    assert clocks and all(r["event_text"] for r in rows)
    assert any(r["event_text"].startswith("4 days passed: the ¥45,000.00 debt payment went out and one invoice was issued") for r in clocks)
    for r in rows:
        assert not any(w in r["event_text"] for w in ENGINE_WORDS), r["event_text"]
        assert not any(w in (r["event_detail"] or "") for w in ENGINE_WORDS), r["event_detail"]
    for lang in ("en", "zh"):
        for c in client.get("/home", params={"lang": lang}, headers=OWNER).json()["changes"]:
            assert not any(w in c["event_text"] for w in ENGINE_WORDS), c["event_text"]


# ---------------------------------------------------------------- the comparison names the plan the next step recommends (finding 2)


def _comparison(client, lang: str = "en") -> dict:
    return client.post("/router/plan", params={"lang": lang}, headers=OWNER).json()


def test_day34_the_recommended_cure_is_a_row_and_the_cheapest_plan_is_the_alternative(client, rt):
    to_day34(client, rt)
    na = client.get("/home", headers=OWNER).json()["next_action"]
    assert na["plan_source"] == "alert" and na["recommended_key"] == "recommended_plan"
    plan = _comparison(client)
    rows = {r["key"]: r for r in plan["comparison"]}
    assert plan["recommended_key"] == "recommended_plan"
    rec, cheapest = rows["recommended_plan"], rows["router_optimum"]
    assert (rec["role"], rec["total_display"], rec["total_fen"]) == ("recommended", "¥1,782.19", 178_219)
    assert rec["total_display"] == na["cost_total_display"]  # the card and the row say the same figure
    assert rec["role_reason"] == ("The next step: it needs one approval; the cheapest plan (¥1,706.10 in all) needs 2 separate "
                                  "approvals.")
    assert (cheapest["role"], cheapest["total_display"]) == ("alternative", "¥1,425.75 + ¥1,069.32 = ¥1,706.10")
    assert cheapest["role_reason"] == "Cheapest in all, but it needs 2 separate approvals; the recommended plan needs one."
    # exactly one recommended row, listed first; the router's own status and selection are untouched
    assert [r["role"] for r in plan["comparison"]].count("recommended") == 1 and plan["comparison"][0]["key"] == "recommended_plan"
    assert (cheapest["status"], cheapest["selected"]) == ("recommended", True) and rec["selected"] is False
    assert rows["full_discount"]["role"] == "alternative" and rows["full_discount"]["role_reason"] == "Only if the buyer agrees to pay early."
    # the cure row carries what a page needs to draw it
    assert [(g["name_display"], g["cost_display"]) for g in rec["legs"]] == [("Invoice financing (onboarded platform)", "¥1,782.19")]
    assert rec["actions"][0]["amount_fen"] == 20_000_000 and rec["actions"][0]["lands_day"] == 37 and rec["executable_now"] is True
    zh = {r["key"]: r for r in _comparison(client, "zh")["comparison"]}
    assert zh["recommended_plan"]["role_reason"] == "下一步所用方案：只需一次批准；最便宜的方案（合计 ¥1,706.10）需要 2 次单独批准。"
    assert zh["router_optimum"]["role_reason"] == "合计最便宜，但需要 2 次单独批准；推荐方案只需一次。"


def test_day34_two_advances_on_one_source_are_told_apart_and_the_total_reconciles(client, rt):
    to_day34(client, rt)
    cheapest = next(r for r in _comparison(client)["comparison"] if r["key"] == "router_optimum")
    assert [(g["name_display"], g["cost_display"]) for g in cheapest["legs"]] == [
        ("Invoice financing (onboarded platform), ¥80k", "¥1,425.75"), ("Invoice financing (onboarded platform), ¥120k", "¥1,069.32")]
    # the total is not the sum of the legs: the difference is a named line, so the page never shows an equation that fails
    assert cheapest["offset_display"] == "−¥788.97" and cheapest["offset_label"] == "Change in other interest and fees across the forecast"
    assert sum(g["cost_fen"] for g in cheapest["legs"]) + cheapest["offset_fen"] == cheapest["total_fen"] == 170_610


def test_day0_the_router_optimum_is_the_recommended_row_and_the_legs_are_named(client, rt):
    na = client.get("/home", headers=OWNER).json()["next_action"]
    assert na["plan_source"] == "router" and na["recommended_key"] == "router_optimum"
    plan = _comparison(client)
    rows = {r["key"]: r for r in plan["comparison"]}
    assert plan["recommended_key"] == "router_optimum" and "recommended_plan" not in rows
    assert [k for k, r in rows.items() if r["role"] == "recommended"] == ["router_optimum"]
    opt = rows["router_optimum"]
    assert opt["role_reason"] == "The cheapest plan your committed facilities can fund in time."
    assert [(g["name_display"], g["cost_display"]) for g in opt["legs"]] == [
        ("Bank credit line", "¥841.64"), ("Invoice financing (onboarded platform)", "¥2,272.29")]
    assert opt["name_display"] == "Bank credit line + Invoice financing (onboarded platform)" and opt["offset_display"] is None
    # the next-step card names its legs the same way
    assert [(g["name_display"], g["cost_display"]) for g in na["legs"]] == [(g["name_display"], g["cost_display"]) for g in opt["legs"]]
    assert [(c["name_display"], c["cost_display"]) for c in na["components"]] == [(g["name_display"], g["cost_display"]) for g in opt["legs"]]
    assert rows["line_only"]["role"] == "insufficient" and rows["line_only"]["role_reason"].startswith("Cash still falls below your reserve in 12 days; ")
    assert rows["line_guaranteed_loan"]["role"] == "unavailable"
    # every row has a role and (but for the empty "no funding needed" row) a sentence
    assert all(r["role"] and r["role_reason"] for r in plan["comparison"])


def test_the_roles_change_no_cost_and_no_order_of_the_routers_rows(client, rt):
    to_day34(client, rt)
    rows = _comparison(client)["comparison"]
    assert [(r["key"], r["total_fen"]) for r in rows if r["key"] != "recommended_plan"] == [("full_discount", 504_000), ("router_optimum", 170_610)]


# ---------------------------------------------------------------- the approval's result and reason are owner sentences (finding 18)


def test_an_approved_advance_says_what_was_requested_and_when_the_cash_lands(client, rt):
    to_day34(client, rt)
    a = client.get("/home", headers=OWNER).json()["next_action"]
    r = client.post(f"/alerts/{a['alert_id']}/act", json={"state_version": a["state_version"], "suggestions": a["suggestions"]}, headers=OWNER)
    aid = r.json()["results"][0]["approval_id"]
    [queued] = client.get("/approvals/queue", headers=OWNER).json()["approvals"]
    assert queued["presentation"]["reason"] == ("The yearly cost of 32.5% is above the 15.00% limit you signed for funding without "
                                                "your approval.")
    client.post(f"/approvals/{aid}", json={"decision": "APPROVE"}, headers=OWNER)
    [done] = client.get("/approvals/queue", headers=OWNER).json()["approvals"]
    assert done["presentation"]["result_message"] == "¥200,000.00 of invoice financing was requested today; the cash lands in 3 days."
    for text in (done["presentation"]["result_message"], done["presentation"]["reason"]):
        assert "lead time" not in text and "not today" not in text and "Arrives in" not in text
    # the executor's own sentence stays at the audit level
    assert "lead time" in done["result_message"]


def test_result_words_in_both_languages_and_for_a_decline():
    from app.api.presentation import result_words
    from app.domain.fixtures import load_scenario
    state, _ = load_scenario()
    draw = {"op_id": "x", "facility_id": "FAC-LINE", "amount_fen": 15_000_000, "day": 0}
    assert result_words(state, kind="DRAW_FACILITY", status="EXECUTED", payload=draw, day=0, today=0) == (
        "A ¥150,000.00 draw on the Bank credit line was requested today; the cash arrived today.")
    assert result_words(state, kind="DRAW_FACILITY", status="EXECUTED", payload=draw, day=0, today=0, lang="zh") == (
        "从Bank credit line提取 ¥150,000.00已于今天提交；资金今天已到账。")
    assert result_words(state, kind="DRAW_FACILITY", status="REFUSED", payload=draw, day=0, today=0) == (
        "You declined a ¥150,000.00 draw on the Bank credit line.")
    assert result_words(state, kind="REPAY_FACILITY", status="EXECUTED", payload=draw, day=0, today=0) is None
