"""Each intent end to end through POST /nl (in-memory runtime, cache-mode compiler)."""

from __future__ import annotations

from app.domain.models import CashFlow, FlowKind
from tests.nl.conftest import OWNER, Chat, codes, ops

EX12 = "Get paid early on the Foshan invoice without giving anything away next quarter."


def test_evaluate_offer_by_fixture_proposes_counters(client):
    r = Chat(client, "t-eval").say("Evaluate EX01")
    assert r["intent"] == "EVALUATE_OFFER"
    assert r["verdict"]["outcome"] == "REJECT"
    assert codes(r) == ["AGG_CONCESSION_EXCEEDED", "RESERVE_BREACH"]
    assert ops(r) == [] and r["awaiting_confirmation"]
    assert [s["kind"] for s in r["plan"]][:4] == ["VERIFY", "COUNTER_OFFER", "COUNTER_OFFER", "NEGOTIATE"]
    assert r["verdict"]["forward_concession_total_display"] == "¥26,455.62"


def test_evaluate_pasted_offer_compiles_the_quoted_text(client):
    r = Chat(client, "t-paste").say("Should we accept this from Foshan? “We can pay this one early at 1.5%. Nothing else changes.”")
    assert r["intent"] == "EVALUATE_OFFER" and r["verdict"]["outcome"] == "COUNTER"
    assert codes(r) == ["MAX_APR_EXCEEDED"]


def test_term_sheet_with_personal_guarantee(client):
    r = Chat(client, "t-ts").say("Evaluate EX09")
    assert r["verdict"]["outcome"] == "REJECT" and "TIER3_PERSONAL_GUARANTEE" in codes(r)
    assert ops(r) == []


def test_negotiate_accept_records_commitment_and_draws_the_line(client, rt):
    c = Chat(client, "t-neg")
    c.say("Evaluate EX01")
    r = c.say("Send the counters")
    assert r["intent"] == "NEGOTIATE" and r["negotiation"]["outcome"] == "ACCEPT"
    assert ops(r) == [("COUNTER_OFFER", "EXECUTED"), ("COUNTER_OFFER", "EXECUTED"), ("ACCEPT_OFFER", "EXECUTED"),
                      ("DRAW_FACILITY", "EXECUTED")]
    (commitment,) = rt.store.commitments()
    assert commitment.status.value == "ACTIVE" and commitment.nonce


def test_negotiate_without_counters_says_so(client):
    r = Chat(client, "t-neg0").say("negotiate")
    assert r["intent"] == "NEGOTIATE" and ops(r) == []
    assert "no counters" in r["reply"].lower()


def test_fund_gap_executes_the_router_plan(client, rt):
    r = Chat(client, "t-fund").say("Fund the cash gap")
    assert r["intent"] == "FUND_GAP"
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert rt.store.get_state().cash_fen == 76_000_000
    assert all(o["tier"] == "TIER_1" for o in r["operations"])


def test_repay_is_held_when_it_would_breach_the_reserve(client):
    c = Chat(client, "t-repay")
    c.say("Fund the cash gap")
    r = c.say("Repay the credit line")
    assert r["intent"] == "REPAY_FACILITY" and ops(r) == []
    assert "reserve" in r["reply"]


def test_repay_executes_with_headroom(client, rt):
    st = rt.store.get_state()
    rt.store.put_state(st.model_copy(update={"cash_fen": 90_000_000}))
    c = Chat(client, "t-repay2")
    assert ops(c.say("Draw ¥50,000 on the credit line")) == [("DRAW_FACILITY", "EXECUTED")]
    r = c.say("Repay the credit line")
    assert ops(r) == [("REPAY_FACILITY", "EXECUTED")]
    assert rt.store.get_state().cash_fen == 90_000_000


def test_show_status(client):
    r = Chat(client, "t-status").say("How's our cash position?")
    assert r["intent"] == "SHOW_STATUS" and ops(r) == []
    for s in ("¥400,000.00", "days 12–31", "DSCR", "Leverage", "Forward concessions"):
        assert s in r["reply"]


def test_explain_uses_the_stored_verdict(client, rt):
    c = Chat(client, "t-explain")
    c.say("Evaluate EX01")
    r = c.say("why?")
    assert r["intent"] == "EXPLAIN" and ops(r) == []
    assert "Formula:" in r["reply"] and "RESERVE_BREACH day 47" in r["reply"]
    assert rt.store.get_verdict(r["verdict"]["id"]) is not None


def test_explain_with_nothing_to_explain(client):
    r = Chat(client, "t-explain0").say("why?")
    assert r["intent"] == "EXPLAIN" and r["verdict"] is None


def test_what_if_verifies_a_synthetic_obligation_and_executes_nothing(client, rt):
    r = Chat(client, "t-whatif").say("What if we give Foshan 60-day terms?")
    assert r["intent"] == "WHAT_IF" and ops(r) == []
    assert "AGG_CONCESSION_EXCEEDED" in codes(r)
    assert rt.store.operations() == []


def test_what_if_needs_a_change(client):
    r = Chat(client, "t-whatif0").say("What if Foshan is nice to us?")
    assert r["intent"] == "WHAT_IF" and r["verdict"] is None


def test_approve_and_reject_pending_operations(client):
    c = Chat(client, "t-appr")
    c.say("Evaluate EX05")
    assert ops(c.say("go ahead")) == [("ACCEPT_OFFER", "PENDING_APPROVAL")]
    r = c.say("reject APR-000001")
    assert r["intent"] == "REJECT" and ops(r) == [("ACCEPT_OFFER", "REFUSED")]
    assert "Declined" in r["reply"]
    assert c.say("approve it")["reply"].startswith("Nothing is waiting")


def test_counterparty_message_is_compiled_and_answered_within_tier1(client):
    r = Chat(client, "t-cp", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(
        "We can pay this one early at 1.5%. Nothing else changes.")
    assert r["intent"] == "COUNTERPARTY_MESSAGE"
    assert ops(r) == [("COUNTER_OFFER", "EXECUTED")]
    assert "0.85%" in r["reply"] and "¥211,800" in r["reply"]


def test_out_of_scope(client):
    r = Chat(client, "t-oos").say("Book me a flight to Shenzhen")
    assert r["intent"] == "OUT_OF_SCOPE" and ops(r) == []
    assert "I can evaluate" in r["reply"]


def test_ambiguous_asks_one_question_with_options(client):
    c = Chat(client, "t-amb")
    r = c.say("help me sort out our cash")
    assert r["intent"] == "AMBIGUOUS" and len(r["clarification"]["options"]) == 3
    assert c.say("2")["intent"] == "FUND_GAP"


def test_two_gaps_clarification(client, rt):
    st = rt.store.get_state()
    rt.store.put_state(st.model_copy(update={"flows": [*st.flows, CashFlow(
        id="F-TAX", day=60, amount_fen=-45_000_000, kind=FlowKind.OTHER, label="Tax")]}))
    c = Chat(client, "t-gaps")
    r = c.say("fund it")
    assert r["intent"] == "AMBIGUOUS" and ops(r) == []
    assert [o["id"] for o in r["clarification"]["options"]] == ["1", "2", "3"]
    assert "days 60–76" in r["clarification"]["options"][1]["label"]
    r = c.say("the first one")
    assert r["intent"] == "FUND_GAP"
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_unanswered_clarification_is_asked_again(client, rt):
    c = Chat(client, "t-reask")
    c.say("help me sort out our cash")
    r = c.say("hmm")
    assert r["intent"] == "AMBIGUOUS" and r["clarification"] is not None


def test_zh_replies_in_zh(client):
    r = Chat(client, "t-zh").say("帮我补足资金缺口")
    assert r["lang"] == "zh" and "融资路由方案" in r["reply"]


def test_sessions_are_multi_turn_and_ids_returned(client):
    r1 = client.post("/nl", json={"actor": "OWNER", "text": "status"}, headers=OWNER).json()
    r2 = client.post("/nl", json={"session_id": r1["session_id"], "actor": "OWNER", "text": "status"}, headers=OWNER).json()
    assert r1["session_id"] == r2["session_id"] and r2["turn"] == 2


def test_accelerate_is_proposed_first(client):
    r = Chat(client, "t-acc").say(EX12)
    assert r["intent"] == "ACCELERATE_RECEIPT" and r["awaiting_confirmation"] and ops(r) == []
