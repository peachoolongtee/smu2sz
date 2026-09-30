def _eval(client, fx):
    oid = client.post("/offers", json={"fixture_id": fx}).json()["offer"]["offer_id"]
    return oid, client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fx}).json()


import pytest


@pytest.mark.xfail(strict=True, reason="rebate base binds from state.expected_orders after the contracts follow-up")
def test_ex01_rejects_with_golden_numbers_and_guarded_counters(client):
    _, v = _eval(client, "EX01_PACKAGE")
    assert v["outcome"] == "REJECT"
    codes = {x["code"] for x in v["violations"]}
    assert {"AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH"} <= codes
    assert v["forward_concession"]["total_display"] == "¥26,455.62" and v["forward_concession"]["over_cap"]
    assert len(v["counters"]) >= 2 and not any(c["outbound_blocked"] for c in v["counters"])
    assert v["trajectory"]["first_breach_day"] == 47


def test_security_demo_logs_three_events_and_books_nothing(client):
    _, v = _eval(client, "SEC_DEMO_FASTCAPITAL")
    assert v["outcome"] == "REJECT"
    assert {x["code"] for x in v["violations"]} == {"UNKNOWN_COUNTERPARTY", "UNEVIDENCED_PRIOR_CONCESSION", "DATA_EXTRACTION_REFUSED"}
    assert len(client.get("/audit").json()["events"]) == 3
    assert client.get("/ledger").json()["commitments"] == []


def test_scene1_cooperative_buyer_accepts_option_a_and_line_draw_is_tier1(client):
    oid, _ = _eval(client, "EX01_PACKAGE")
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    assert n["outcome"] == "DEAL"
    statuses = [(o.get("kind", ""), o["status"], o["tier"]) for o in n["operations"]]
    assert statuses[0][1] == "EXECUTED"
    assert all(s == "EXECUTED" and t == "TIER_1" for _, s, t in statuses), statuses
    assert client.get("/ledger").json()["chain_valid"]


def test_scene2_hard_line_buyer_no_deal_and_gap_funded(client):
    oid, _ = _eval(client, "EX01_PACKAGE")
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "hard_line"}).json()
    assert n["outcome"] == "NO_DEAL" and len(n["rounds"]) == 3
    assert n["plan"]["total_cost_display"] == "¥2,712.94"
    assert [o["status"] for o in n["operations"]] == ["EXECUTED", "EXECUTED"]


def test_router_plan_golden(client):
    r = client.post("/router/plan").json()
    assert r["committed"]["total_cost_display"] == "¥2,712.94"
    assert r["marginal"]["facility_id"] == "FAC-IF" and r["marginal"]["break_even_bp"] == 88
    assert r["marginal"]["extension_committed_12m_display"] == "¥22,455.62"
    assert any(row["selected"] for row in r["comparison"])
