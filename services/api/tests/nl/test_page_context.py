"""Wave 4 part A (wayfinder #65, F08 F20): Ask FLOW is bound to the page and the selected deal, and the page's own
questions have deterministic reads. The browser names ids only; the server validates every one against its stores and
ignores what it cannot find, so a bad id leaves the turn exactly as if no context had been sent."""

from __future__ import annotations

import pytest

from app.domain.fixtures import load_scenario
from app.nl.rules import parse
from tests.nl.conftest import OWNER, Chat, ops

STATE = load_scenario()[0]

NO_VERDICT = "There is no verdict to explain yet. Evaluate an offer first."


def _evaluated(client) -> tuple[str, str]:
    """The Deals page's own path: submit and evaluate EX01 over REST. The /nl session knows nothing of it."""
    oid = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()["offer"]["offer_id"]
    verdict = client.post(f"/offers/{oid}/evaluate", json={"fixture_id": "EX01_PACKAGE"}, headers=OWNER).json()
    return oid, verdict["id"]


def _day34_missed_receipt(client) -> None:
    """EX01 agreed, the early payment never arrives, the clock reaches day 34, and the owner's "go ahead" queues the
    over-the-ceiling cure for approval (the Home page's missed-receipt story)."""
    oid, _ = _evaluated(client)
    client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}, headers=OWNER)
    client.post("/clock/advance", json={"to_day": 30}, headers=OWNER)
    client.post("/clock/advance", json={"to_day": 34}, headers=OWNER)
    client.post("/nl/opener", json={"session_id": "w4-op"}, headers=OWNER)
    done = Chat(client, "w4-op").say("go ahead")
    assert ops(done) == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]


# ---------------------------------------------------------------- the page's deal binds the explain intents


def test_a_fresh_session_without_context_still_has_no_verdict(client, rt):
    _evaluated(client)
    r = Chat(client, "w4-bare").say("Why are we countering this?")
    assert r["intent"] == "EXPLAIN" and r["reply"] == NO_VERDICT and r["context_echo"] is None


def test_the_page_context_makes_why_explain_the_deal_the_page_evaluated(client, rt):
    oid, vid = _evaluated(client)
    r = Chat(client, "w4-ctx").say("Why are we countering this?", context={"page": "/deals", "offer_id": oid})
    assert r["intent"] == "EXPLAIN"
    assert r["reply"].startswith("About the Foshan Home Retail Co. offer evaluated today: Verdict REJECT")
    assert "AGG_CONCESSION_EXCEEDED" in r["reply"]
    assert r["verdict"]["id"] == vid
    assert r["context_echo"] == {"offer_id": oid, "counterparty_name": "Foshan Home Retail Co.", "decision_id": vid,
                                 "invoice_id": None}
    assert r["operations"] == []  # a question: nothing runs


def test_the_decision_id_alone_binds_and_a_matching_pair_agrees(client, rt):
    oid, vid = _evaluated(client)
    alone = Chat(client, "w4-dec").say("Why are we countering this?", context={"page": "/deals", "decision_id": vid})
    assert alone["verdict"]["id"] == vid and alone["context_echo"]["offer_id"] == oid
    both = Chat(client, "w4-both").say("Why are we countering this?",
                                        context={"page": "/deals", "offer_id": oid, "decision_id": vid})
    assert both["verdict"]["id"] == vid


@pytest.mark.parametrize("context", [
    {"page": "/deals", "offer_id": "OFF-does-not-exist"},                       # a foreign offer id
    {"page": "/deals", "decision_id": "VER-does-not-exist"},                     # a foreign decision id
    {"page": "/deals", "offer_id": "OFF-does-not-exist", "decision_id": "VER-does-not-exist"},
    {"page": "/deals", "invoice_id": "RCV-NOPE"},                                # an invoice the books do not hold
    {"page": "/deals"},
])
def test_an_unknown_id_is_ignored_and_the_reply_is_the_one_without_context(client, rt, context):
    _evaluated(client)
    r = Chat(client, "w4-bad").say("Why are we countering this?", context=context)
    assert r["reply"] == NO_VERDICT and r["verdict"] is None and r["context_echo"] is None


def test_a_decision_that_belongs_to_another_offer_is_not_bound(client, rt):
    _, vid = _evaluated(client)
    other = client.post("/offers", json={"fixture_id": "EX02_EARLY_1_5"}, headers=OWNER).json()["offer"]["offer_id"]
    client.post(f"/offers/{other}/evaluate", json={"fixture_id": "EX02_EARLY_1_5"}, headers=OWNER)
    r = Chat(client, "w4-mix").say("Why are we countering this?",
                                    context={"page": "/deals", "offer_id": other, "decision_id": vid})
    # the named decision is EX01's, the named offer is EX02's: the page cannot be showing both; the offer's own verdict is used
    assert r["context_echo"]["offer_id"] == other and r["verdict"]["id"] != vid


def test_a_known_invoice_is_echoed_and_an_amount_in_the_context_is_refused(client, rt):
    r = Chat(client, "w4-inv").say("status", context={"page": "/receivables", "invoice_id": "RCV-A"})
    assert r["context_echo"] == {"offer_id": None, "counterparty_name": None, "decision_id": None, "invoice_id": "RCV-A"}
    refused = client.post("/nl", headers=OWNER, json={"session_id": "w4-amt", "actor": "OWNER", "text": "status",
                                                      "context": {"page": "/deals", "amount_fen": 100}})
    assert refused.status_code == 422  # the context carries ids, never figures


def test_the_context_is_for_the_owner_only(client, rt):
    oid, _ = _evaluated(client)
    ctx = {"page": "/deals", "offer_id": oid}
    agent = Chat(client, "w4-agent", owner=False).say("Why are we countering this?", context=ctx)
    # R-11 (16 Oct): an explanation is a read the agent key does not get; nor does it get the page context
    assert agent["reply"] == "This needs the owner's sign-in." and agent["context_echo"] is None
    buyer = Chat(client, "w4-buyer", actor="COUNTERPARTY", owner=False, counterparty_id="BUYER-1").say(
        "We can pay this one early at 1.5%. Nothing else changes.", context=ctx)
    assert "context_echo" not in buyer  # the buyer's view is an allow-list of keys


def test_the_page_deal_is_bound_once_so_a_deal_evaluated_in_chat_keeps_the_conversation(client, rt):
    oid, vid = _evaluated(client)
    chat = Chat(client, "w4-once")
    ctx = {"page": "/deals", "offer_id": oid}
    assert chat.say("Why are we countering this?", context=ctx)["verdict"]["id"] == vid
    chat.say("Evaluate EX02", context=ctx)
    again = chat.say("Why was it decided that way?", context=ctx)
    assert again["verdict"]["id"] != vid  # the owner moved the conversation to EX02; the same page deal does not pull it back


# ---------------------------------------------------------------- the Deals page questions


def test_accepting_their_original_terms_is_answered_from_the_verdict_held(client, rt):
    oid, _ = _evaluated(client)
    r = Chat(client, "w4-orig").say("What if I accept their original terms?", context={"page": "/deals", "offer_id": oid})
    assert r["intent"] == "WHAT_IF" and r["operations"] == []
    assert r["reply"].startswith("About the Foshan Home Retail Co. offer evaluated today: FLOW would not accept their original terms")
    assert "¥28,326.92" in r["reply"] and "¥5,000.00 cap" in r["reply"] and "in 47 days" in r["reply"]  # server figures, day as a distance
    assert "Option A" in r["reply"] and r["reply"].endswith("Nothing has been accepted or sent.")


def test_accepting_with_no_evaluated_deal_says_so(client, rt):
    r = Chat(client, "w4-orig0").say("What if I accept their original terms?")
    assert r["intent"] == "WHAT_IF" and "no evaluated offer" in r["reply"] and "Which buyer" not in r["reply"]


def test_option_a_is_explained_with_its_price_and_the_original_for_comparison(client, rt):
    oid, _ = _evaluated(client)
    r = Chat(client, "w4-opt").say("Why is Option A cheaper?", context={"page": "/deals", "offer_id": oid})
    assert r["intent"] == "EXPLAIN"
    assert "Option A:" in r["reply"] and "costs you ¥3,027.77 now" in r["reply"]
    assert "cheaper than financing the invoice" in r["reply"]  # the counter's own rationale
    assert "Their original terms, for comparison:" in r["reply"] and "¥6,508.05" in r["reply"]
    b = Chat(client, "w4-optb").say("Why is Option B cheaper?", context={"page": "/deals", "offer_id": oid})
    assert b["reply"].split(": ", 1)[1].startswith("Option B:")


# ---------------------------------------------------------------- Cash, Receivables and Home questions


def test_the_cash_page_plan_is_explained_from_the_home_read(client, rt):
    oid, _ = _evaluated(client)
    r = Chat(client, "w4-plan").say("Why did FLOW choose this plan?", context={"page": "/cash", "offer_id": oid})
    assert r["intent"] == "EXPLAIN" and r["verdict"] is None
    assert r["reply"].startswith("FLOW's plan: Draw ¥150,000.00 on Bank credit line")
    assert "It costs ¥3,113.93 in all" in r["reply"] and r["reply"].endswith("Nothing has been run.")
    # without the Cash page and with a deal in hand, the same words ask about the deal
    deal = Chat(client, "w4-plan2").say("Why did FLOW choose this plan?", context={"page": "/deals", "offer_id": oid})
    assert deal["verdict"] is not None


def test_the_missed_receipt_questions_are_answered_from_the_home_read(client, rt):
    _day34_missed_receipt(client)
    waiting = Chat(client, "w4-wait").say("What are we waiting for?")
    assert waiting["intent"] == "SHOW_STATUS" and waiting["operations"] == []
    assert "Waiting for your decision: Request ¥155,013.80 of invoice financing." in waiting["reply"]
    assert "Waiting for payment: Not yet paid: the ¥420,000.00 invoice to Foshan Home Retail Co., due 2 days ago." in waiting["reply"]
    money = Chat(client, "w4-money").say("When does the money arrive?")
    assert money["intent"] == "SHOW_STATUS" and "If you approve today, the cash lands in 3 days." in money["reply"]
    assert "The next payment due is the ¥420,000.00 invoice to Foshan Home Retail Co., in 13 days." in money["reply"]
    for text in ("Who should I chase first?", "What is overdue?"):
        r = Chat(client, f"w4-overdue-{abs(hash(text)) % 1000}").say(text)
        assert r["intent"] == "RECONCILE" and r["operations"] == []
        assert r["reply"].startswith("¥420,000.00 is overdue across 1 invoice")
        assert "Chase Foshan Home Retail Co. first" in r["reply"] and r["reply"].endswith("I have not contacted anyone.")


def test_nothing_overdue_is_said_plainly(client, rt):
    r = Chat(client, "w4-none").say("What is overdue?")
    assert r["reply"].startswith("Nothing is overdue. The next payment due is the ¥420,000.00 invoice to Foshan Home Retail Co.")


def test_a_late_payment_is_answered_from_the_forecast_figures_without_a_new_projection(client, rt):
    r = Chat(client, "w4-late").say("What happens if this payment is late?", context={"page": "/receivables"})
    assert r["intent"] == "WHAT_IF" and r["operations"] == [] and r["verdict"] is None
    assert "The next payment due is the ¥420,000.00 invoice to Foshan Home Retail Co., due in 32 days" in r["reply"]
    assert "I have not re-run the forecast for a late payment." in r["reply"]
    assert "Today's forecast bottoms out at −¥105k in 30 days." in r["reply"]
    named = Chat(client, "w4-late2").say("What happens if this payment is late?",
                                          context={"page": "/receivables", "invoice_id": "RCV-A"})
    assert named["context_echo"]["invoice_id"] == "RCV-A" and "The payment in question is the ¥420,000.00 invoice" in named["reply"]


def test_a_payment_that_is_already_late_is_said_to_be(client, rt):
    _day34_missed_receipt(client)
    r = Chat(client, "w4-late3").say("What happens if this payment is late?", context={"page": "/receivables", "invoice_id": "RCV-A"})
    assert "is already late (due 2 days ago)" in r["reply"] and "no longer counts on it" in r["reply"]


# ---------------------------------------------------------------- "what changed?"


def test_what_changed_after_the_day_34_walk_lists_each_event_its_status_the_consequence_and_the_task(client, rt):
    _day34_missed_receipt(client)
    r = Chat(client, "w4-chg").say("What changed today?", context={"page": "/", "since_day": 0})
    assert r["intent"] == "CHANGES" and r["operations"] == [] and r["plan"] == []
    lines = r["reply"].splitlines()
    assert lines[0] == "Since your last visit 34 days ago:"
    assert "- Time moved forward 34 days, to today." in lines  # the clock move
    assert any(x.startswith("- Waiting for your approval: ¥155,013.80 of invoice financing") and x.endswith(
        "Status: still waiting for your decision.") for x in lines)  # the pending approval, its status
    assert any("early payment promised" in x and "did not arrive" in x and x.endswith("Status: still unpaid.") for x in lines)  # the missed receipt
    assert any(x.startswith("What it means for your cash: Below reserve today.") and "goes below zero in 8 days" in x for x in lines)
    assert "Still to do:" in lines  # the remaining tasks
    assert "- Request ¥155,013.80 of invoice financing. It costs ¥1,381.32. If you approve today, the cash lands in 3 days. " \
           "If you decline, cash goes below zero in 8 days." in lines
    assert "- Not yet paid: the ¥420,000.00 invoice to Foshan Home Retail Co., due 2 days ago." in lines
    assert "APR-" not in r["reply"] and "CMT-" not in r["reply"]  # business words, no record ids


def test_what_changed_without_a_visit_marker_reads_today(client, rt):
    _day34_missed_receipt(client)
    r = Chat(client, "w4-chg2").say("What changed today?")
    assert r["reply"].startswith("Today:\n- Waiting for your approval") and "Time moved forward" not in r["reply"]
    assert "the Bank credit line" not in r["reply"]  # the day-0 draw is not today's news


def test_when_nothing_changed_the_reply_says_so_and_gives_the_forecast(client, rt):
    r = Chat(client, "w4-quiet").say("What changed today?")
    assert r["reply"].startswith("Nothing has changed today; the forecast is unchanged: Your cash reserve becomes unsafe in 12 days.")
    marker = Chat(client, "w4-quiet2").say("what's new?", context={"page": "/", "since_day": 0})
    assert marker["intent"] == "CHANGES" and marker["reply"].startswith("Nothing has changed today;")  # a marker of today is today


def test_nothing_changed_since_an_earlier_visit_names_how_long_ago(client, rt):
    client.post("/clock/advance", json={"to_day": 3}, headers=OWNER)
    r = Chat(client, "w4-quiet3").say("What changed since my last visit?", context={"page": "/", "since_day": 0})
    assert r["reply"].startswith("Nothing changed since your last visit 3 days ago; the forecast is unchanged: ")


def test_a_visit_marker_in_the_future_is_dropped(client, rt):
    r = Chat(client, "w4-future").say("What changed today?", context={"page": "/", "since_day": 500})
    assert r["reply"].startswith("Nothing has changed today;")


def test_what_changed_in_chinese(client, rt):
    _day34_missed_receipt(client)
    r = Chat(client, "w4-zh").say("今天有什么变化？", context={"page": "/", "since_day": 0})
    assert r["intent"] == "CHANGES" and r["reply"].startswith("自您上次访问（34 天前）以来：")
    assert "- 时间向前推进了 34 天，到今天。" in r["reply"] and "还需处理：" in r["reply"]


def test_what_changed_needs_the_owner_token(client, rt):
    r = Chat(client, "w4-agentchg", owner=False).say("What changed today?")
    assert r["intent"] == "CHANGES" and r["reply"] == "This needs the owner's sign-in."
    for text in ("What are we waiting for?", "When does the money arrive?"):
        assert Chat(client, f"w4-ag-{abs(hash(text)) % 1000}", owner=False).say(text)["reply"] == "This needs the owner's sign-in."


# ---------------------------------------------------------------- the closed grammar reads these, in both languages


READS = [
    ("What changed today?", "CHANGES"), ("what changed since my last visit", "CHANGES"), ("What's new?", "CHANGES"),
    ("今天有什么变化？", "CHANGES"), ("自上次访问以来有什么变化", "CHANGES"),
    ("What are we waiting for?", "SHOW_STATUS"), ("我们在等什么？", "SHOW_STATUS"),
    ("When does the money arrive?", "SHOW_STATUS"), ("资金什么时候到账？", "SHOW_STATUS"),
    ("Who should I chase first?", "RECONCILE"), ("What is overdue?", "RECONCILE"),
    ("应该先催哪一家？", "RECONCILE"), ("哪些款项逾期了？", "RECONCILE"),
    ("What if I accept their original terms?", "WHAT_IF"), ("如果我接受对方的原始条款会怎样？", "WHAT_IF"),
    ("What happens if this payment is late?", "WHAT_IF"), ("如果这笔款项延迟会怎样？", "WHAT_IF"),
    ("Why is Option A cheaper?", "EXPLAIN"), ("为什么方案A更便宜？", "EXPLAIN"),
    ("Why did FLOW choose this plan?", "EXPLAIN"), ("FLOW 为什么选这个方案？", "EXPLAIN"),
    ("What needs my attention?", "SHOW_ALERTS"), ("有什么需要我关注的？", "SHOW_ALERTS"),
]


@pytest.mark.parametrize(("text", "intent"), READS)
def test_a_page_question_is_read_by_the_rules_not_the_model(text, intent):
    p = parse(text, STATE)
    assert p is not None and p.intent.value == intent and p.source == "rules"


@pytest.mark.parametrize(("text", "intent"), READS)
def test_every_page_question_gets_a_reply_that_runs_nothing(client, rt, text, intent):
    r = Chat(client, "w4-all").say(text, context={"page": "/cash"})
    assert r["intent"] == intent and r["operations"] == []
    assert "I can't do that" not in r["reply"] and "I can evaluate a buyer" not in r["reply"]


# ---------------------------------------------------------------- one recovery, not the list of everything


def test_an_ordinary_question_with_no_read_gets_one_way_forward(client, rt):
    r = Chat(client, "w4-oos").say("Who won the football match?")
    assert r["intent"] == "OUT_OF_SCOPE" and r["operations"] == []
    assert r["reply"] == ("I can answer questions about your cash, deals, approvals and what changed; "
                          "try \"What changed today?\"")
    zh = Chat(client, "w4-oos-zh").say("足球比赛谁赢了？")
    assert zh["intent"] == "OUT_OF_SCOPE" and "今天有什么变化" in zh["reply"] and "对账" not in zh["reply"]


def test_a_request_that_is_not_a_question_keeps_the_capability_list(client, rt):
    r = Chat(client, "w4-oos2").say("Book me a flight to Shenzhen")
    assert r["reply"].startswith("I can't do that. I can evaluate")
