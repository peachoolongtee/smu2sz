"""Wave 3 (wayfinder #65, ticket #72, audit section 12): the evaluate view carries a `workspace` block, the Deals page in its order:
what the buyer asks, what it costs (named lines with their valuation window), why it matters, what FLOW recommends, the one priced
response with its send scope, and the folded fields by name. Every figure is one the verifier or the engine already produced."""

from __future__ import annotations

from tests.alerts.test_repay_alert import OWNER
from tests.nl import conftest as nl_conftest
import pytest

pytestmark = pytest.mark.usefixtures("fast_busy")  # the busy seed is replayed once per process (tests/api/busy_snapshot.py)

rt = nl_conftest.rt
client = nl_conftest.client


def _eval(client, fixture: str = "EX01_PACKAGE", lang: str = "en") -> dict:
    oid = client.post("/offers", json={"fixture_id": fixture}, headers=OWNER).json()["offer"]["offer_id"]
    return client.post(f"/offers/{oid}/evaluate", params={"lang": lang}, json={"fixture_id": fixture}, headers=OWNER).json()


def test_the_workspace_is_in_the_pages_order(client, rt):
    ws = _eval(client)["workspace"]
    assert ws["order"] == ["buyer", "recommends", "priced_response", "buyer_asks", "financial_impact", "why_it_matters", "agreements", "advanced"]
    assert all(key in ws for key in ws["order"])


def test_the_buyers_asks_are_sentences_not_codes(client, rt):
    v = _eval(client)
    asks = v["workspace"]["buyer_asks"]["asks"]
    assert [a["type"] for a in asks] == [o["type"] for o in v["bound_obligations"]] == ["IMMEDIATE_DISCOUNT", "TERMS_EXTENSION", "CONTINGENT_REBATE"]
    assert asks[0]["text"].startswith("The buyer may pay early and take 1.20% off the ¥420,000.00 invoice to Foshan Home Retail Co.")
    assert asks[1]["text"].startswith("The buyer gets 60-day payment terms") and asks[2]["text"].startswith("A rebate of 1.00%")
    assert not any("OFF-" in a["text"] or "RCV-" in a["text"] for a in asks)


def test_the_financial_impact_names_each_line_and_keeps_the_forward_figure_apart_from_the_immediate_discount(client, rt):
    v = _eval(client)
    impact = v["workspace"]["financial_impact"]
    lines = {ln["type"]: ln for ln in impact["lines"]}
    assert (lines["TERMS_EXTENSION"]["amount_display"], lines["CONTINGENT_REBATE"]["amount_display"]) == ("¥24,326.92", "¥4,000.00")
    assert lines["IMMEDIATE_DISCOUNT"]["amount_display"] == "¥5,040.00" and lines["IMMEDIATE_DISCOUNT"]["horizon"] == "IMMEDIATE"
    assert "12 months" in lines["TERMS_EXTENSION"]["window_text"] and "not part of the forward figure" in lines["IMMEDIATE_DISCOUNT"]["window_text"]
    # the forward total is the verifier's own and the sum of the forward lines; the discount is never added to it
    assert impact["forward_total_display"] == v["forward_concession"]["total_display"] == "¥28,326.92"
    assert sum(ln["amount_fen"] for ln in impact["lines"] if ln["horizon"] == "FORWARD") == impact["forward_total_fen"] == 2_832_692
    assert impact["over_cap"] is True and impact["cap_display"] == "¥5,000.00" and "not added" in impact["total_note"]
    # the lines reference the same obligations and values the view already carries
    assert {ln["obligation_id"]: ln["amount_fen"] for ln in impact["lines"] if ln["horizon"] == "FORWARD"} == {
        cv["obligation_id"]: cv["value_fen"] for cv in v["concession_values"] if cv["value_fen"]}


def test_why_it_matters_and_what_flow_recommends(client, rt):
    v = _eval(client)
    ws = v["workspace"]
    assert ws["why_it_matters"]["reasons"] == [
        "The forward concessions in this offer come to ¥28,326.92, above your ¥5,000.00 limit.",
        "If you accept their request, cash would fall below your minimum in 47 days."]
    assert ws["recommends"] == {"action": "counter", "text": "Counter recommended"} and v["business_action"] == "counter"


def test_the_priced_response_is_the_recommended_counter_with_its_send_scope_and_the_binding_ids(client, rt):
    v = _eval(client)
    pr = v["workspace"]["priced_response"]
    first = v["counters"][0]
    assert pr["counter_id"] == first["id"] and pr["label"] == first["label"] == "Option A"
    assert pr["send_scope"] == first["send_scope"]  # the same sentence the counter itself carries
    assert (pr["supplier_cost_display"], pr["forward_value_display"]) == (first["supplier_cost_display"], first["forward_value_display"])
    assert (pr["verdict_id"], pr["state_version"]) == (v["id"], v["state_version"])  # what a bound send needs (409 COUNTER_CHANGED)
    # and the decision record names the same counter as the recommended one
    detail = client.get(f"/decisions/{v['decision_id']}", headers=OWNER).json()
    assert detail["response"]["recommended_counter_id"] == pr["counter_id"]


def test_the_advanced_keys_name_fields_the_view_already_has(client, rt):
    v = _eval(client)
    keys = v["workspace"]["advanced"]["keys"]
    assert set(keys) == {"parsed_obligations", "source_text", "checks", "formula", "engine_verdict", "audit_evidence"}
    for names in keys.values():
        assert all(name in v for name in names), names


def test_the_workspace_is_in_chinese_too(client, rt):
    ws = _eval(client, lang="zh")["workspace"]
    assert ws["buyer_asks"]["title"] == "买方的要求" and ws["recommends"]["text"] == "建议还价"
    assert ws["financial_impact"]["lines"][0]["label"] == "立即折扣" and "12 个月" in ws["financial_impact"]["lines"][1]["window_text"]
    assert ws["why_it_matters"]["reasons"][0].startswith("此报价的远期让步合计 ¥28,326.92")
    assert ws["priced_response"]["send_scope"].startswith("向买方发送方案 A")


def test_an_offer_with_no_counter_has_no_priced_response(client, rt):
    ws = _eval(client, "SEC_DEMO_FASTCAPITAL")["workspace"]
    assert ws["priced_response"] is None and ws["recommends"]["action"] == "decline"
    assert ws["buyer_asks"]["asks"] == [] or all("text" in a for a in ws["buyer_asks"]["asks"])


# ---------------------------------------------------------------- Slice B: a receipt for every sendable reply


def test_every_sendable_reply_has_its_own_plan_and_receipt_with_the_first_kept_as_the_priced_response(client, rt):
    ws = _eval(client)["workspace"]
    rs = ws["priced_responses"]
    assert [r["label"] for r in rs] == ["Option A", "Option B"]
    assert rs[0] == ws["priced_response"]  # compatibility: the single field is the first entry
    a, b = rs
    assert a["counter_id"] != b["counter_id"] and a["verdict_id"] == b["verdict_id"] and a["state_version"] == b["state_version"]
    # Option A is unchanged: one draw, today
    assert a["send_scope_lines"][1] == "Draws ¥149,986.20 on the Bank credit line today"
    assert a["receipt"]["executes_now_text"] == "; ".join(a["send_scope_lines"][1:])
    # Option B runs its own funding: a draw and an invoice-financing request, said with the amounts and when they land
    assert b["send_scope_lines"][1:3] == ["Draws ¥90,000.00 on the Bank credit line today",
                                          "Requests ¥315,000.00 of invoice financing, arriving in 3 days"]
    ex = b["receipt"]["executes_now_text"]
    assert "¥90,000.00" in ex and "today" in ex and "¥315,000.00" in ex and ex != a["receipt"]["executes_now_text"]
    # Option B costs the supplier ¥0.00 (its price adjustment offsets what it gives away) and its funding is not inside that figure
    assert b["send_scope_lines"][3] == "Funding cost ¥3,706.46 in addition" and "already inside" not in ex
    assert a["send_scope_lines"][2].endswith("(already inside the ¥3,027.77 above)")
    assert b["receipt"]["in_hand_vs_future_text"].startswith("The funding arrives in 3 days.")
    assert b["receipt"]["authority_text"] == "It changes your terms, so you approve it first."  # its own authority, not A's
    # the three statements are specific to each send, and authority is said only in `authority_text` (Option B needs approval, A does not)
    for r, name in ((a, "Option A"), (b, "Option B")):
        assert r["receipt"]["authorizes_text"] == r["send_scope_lines"][0] == (
            f"Send the exact {name} counter to Foshan; FLOW records it as a proposed agreement that stands only if Foshan accepts.")
        assert r["receipt"]["remaining_text"] == ("The terms take effect only when Foshan accepts; no payment and no financing settles because "
                                                  "the counter is sent.")
        assert "approval" not in r["receipt"]["authorizes_text"] and "(" not in r["receipt"]["authorizes_text"]
    for r in rs:  # the funding runs on send whether or not the buyer agrees, said in words, with what a refusal runs (the gap as it stands)
        assert "Runs when you send, whether or not the buyer agrees." in r["receipt"]["assumptions_text"]
        assert r["receipt"]["assumptions_text"].startswith(r["recheck_text"])
        assert ("If the buyer declines, it is sized to the gap as it stands without the agreement: "
                "Draws ¥150,000.00 on the Bank credit line today; Requests ¥255,000.00 of invoice financing, arriving in 3 days.") in r["receipt"]["assumptions_text"]


def test_the_sends_funding_really_runs_on_a_refusal_which_the_receipt_says(client, rt):
    ws = _eval(client)["workspace"]
    b = ws["priced_responses"][1]
    sent = client.post(f"/negotiate/{ws['buyer']['offer_id']}", json={"buyer_profile": "hard_line", "counter_id": b["counter_id"],
                       "verdict_id": b["verdict_id"], "state_version": b["state_version"]}, headers=OWNER)
    assert sent.status_code == 200, sent.text
    out = sent.json()
    assert out["outcome"] == "NO_DEAL" and out["operations"], out  # refused, and the funding still ran
    # exactly what the receipt said a refusal runs: the draw and the invoice financing of the gap as it stands
    assert [(x["kind"], x["amount_fen"]) for x in out["plan"]["actions"]] == [("DRAW", 15_000_000), ("FINANCE_INVOICE", 25_500_000)]
    assert [(o["kind"], o["status"]) for o in out["operations"]] == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert "whether or not the buyer agrees" in b["receipt"]["assumptions_text"]


def test_the_replies_receipts_in_chinese(client, rt):
    rs = _eval(client, lang="zh")["workspace"]["priced_responses"]
    assert len(rs) == 2
    for r in rs:
        assert "无论买方是否同意" in r["receipt"]["assumptions_text"]
    assert "¥90,000.00" in rs[1]["receipt"]["executes_now_text"] and "今天" in rs[1]["receipt"]["executes_now_text"]
    assert rs[1]["receipt"]["executes_now_text"] != rs[0]["receipt"]["executes_now_text"]


def test_an_offer_with_no_counter_has_no_priced_responses(client, rt):
    assert _eval(client, "SEC_DEMO_FASTCAPITAL")["workspace"]["priced_responses"] == []


def test_a_reply_that_runs_nothing_on_send_says_so_before_the_send(client, rt):
    """On the busy books the gap cannot be funded today whatever the buyer answers, so EX01's Option A runs no funding and its receipt says so
    (the words the record uses after the send: the gap was not funded)."""
    client.post("/demo/reset", params={"scenario": "busy"}, headers=OWNER)
    ws = _eval(client)["workspace"]
    [a] = ws["priced_responses"]
    assert a["label"] == "Option A" and a["receipt"]["executes_now_text"] == "No funding runs when you send: today's plan cannot run; the gap stays open."
    assert a["receipt"]["assumptions_text"] == a["recheck_text"]
