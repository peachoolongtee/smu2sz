"""Wave 7 addendum (map #65, ticket #76), item 8: the owner's chat in Business words. Only the reply strings change, and only when the
request asks for it (`POST /nl?mode=business`): the verdict, the funding plan and the confirmed run are said without ids, tier words or
reason codes, with one outcome line, the plan (amount, estimated cost, arrival) and the confirm words "Yes, run it". The raw replies of
the same turns stay as they were for the Demo and the audit, and the same operations run."""

from __future__ import annotations

import re

from tests.nl.conftest import OWNER

ID_OR_CODE = re.compile(r"\b(?:FAC-[A-Z]+|RCV-[A-Z]+|BUYER-\d+|RI:\S+|TIER_\d|Tier[- ]?\d|AGG_CONCESSION_EXCEEDED|RESERVE_BREACH|"
                        r"DISCOUNT_ABOVE_BREAK_EVEN|EARLY_PAY_DEARER_THAN_PLAN|REJECT)\b")


def _say(client, text: str, sid: str, lang: str = "en", mode: str | None = "business") -> dict:
    params = {"mode": mode} if mode else {}
    r = client.post("/nl", params=params, json={"session_id": sid, "actor": "OWNER", "text": text, "lang": lang}, headers=OWNER)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_verdict_on_an_offer_is_one_outcome_line_the_plan_and_the_confirm_words(client):
    j = _say(client, "Evaluate EX01", "b1")
    assert j["reply"].splitlines() == [
        "FLOW recommends a counter: the offer's future concessions cost ¥28,326.92 over the next 12 months, above your ¥5,000 limit.",
        ("If the buyer accepts Option A, the rest of the gap is funded: draws ¥149,986.20 on the Bank credit line today; "
         "estimated cost ¥841.57."),
        ("If the buyer refuses, the gap is funded another way: draws ¥150,000.00 on the Bank credit line today; requests ¥255,000.00 of "
         "invoice financing, arriving in 3 days; estimated cost ¥3,113.93."),
        'Reply "Yes, run it" to send Option A and Option B to Foshan Home Retail Co. Nothing is sent before that.']
    assert not ID_OR_CODE.search(j["reply"]) and j["awaiting_confirmation"] is True and j["operations"] == []


def test_yes_run_it_sends_the_counters_and_says_what_happened_in_business_words(client):
    _say(client, "Evaluate EX01", "b2")
    j = _say(client, "Yes, run it", "b2")
    assert j["reply"] == "Foshan Home Retail Co. accepted Option A and the agreement is recorded. Drew ¥149,986.20 on the Bank credit line today."
    assert [(o["kind"], o["status"]) for o in j["operations"]] == [("COUNTER_OFFER", "EXECUTED"), ("COUNTER_OFFER", "EXECUTED"),
                                                                   ("ACCEPT_OFFER", "EXECUTED"), ("DRAW_FACILITY", "EXECUTED")]


def test_the_funding_plan_and_its_confirmed_run(client):
    j = _say(client, "fund the gap", "b3")
    assert j["reply"] == ("FLOW's plan: ¥405,000.00 of funding, estimated cost ¥3,113.93. Draws ¥150,000.00 on the Bank credit line today; "
                          'requests ¥255,000.00 of invoice financing, arriving in 3 days. Reply "Yes, run it" to run it.')
    done = _say(client, "Yes, run it", "b3")
    assert done["reply"] == ("Done. Drew ¥150,000.00 on the Bank credit line today; requested ¥255,000.00 of invoice financing, arriving "
                             "in 3 days. Cost as quoted ¥3,113.93.")
    assert [(o["kind"], o["status"]) for o in done["operations"]] == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_the_same_in_chinese(client):
    j = _say(client, "Evaluate EX01", "b4", "zh")
    assert j["reply"].splitlines()[0] == "FLOW 建议还价：此报价的未来让步在未来 12 个月内共需 ¥28,326.92，高于您 ¥5,000 的上限。"
    assert j["reply"].splitlines()[-1].startswith("回复“好，执行”即可向Foshan Home Retail Co.发送方案 A、方案 B")
    assert not ID_OR_CODE.search(j["reply"])
    done = _say(client, "好，执行", "b4", "zh")  # the Chinese confirm words confirm the plan
    assert done["reply"] == "Foshan Home Retail Co.接受了方案 A，协议已记录。已从Bank credit line提款 ¥149,986.20，今天到账。"


def test_the_funding_plan_in_chinese(client):
    plan = _say(client, "fund the gap", "b5", "zh")
    assert plan["reply"] == ("FLOW 的方案：融资 ¥405,000.00，预计成本 ¥3,113.93。从Bank credit line提款 ¥150,000.00，今天到账；"
                             "申请 ¥255,000.00 的发票融资，3 天后到账。回复“好，执行”即可执行。")


def test_without_the_mode_the_raw_replies_are_exactly_as_before_and_the_same_operations_run(client):
    raw = _say(client, "Evaluate EX01", "r1", mode=None)
    assert raw["reply"].startswith("Verdict REJECT (TIER_1): AGG_CONCESSION_EXCEEDED") and "Reply 'go ahead' to negotiate" in raw["reply"]
    assert ID_OR_CODE.search(raw["reply"])
    ran = _say(client, "go ahead", "r1", mode=None)
    assert "Draw ¥149,986.20 on FAC-LINE: done." in ran["reply"]


def test_the_demo_mode_funding_plan_keeps_its_ids_and_its_go_ahead(client):
    plan = _say(client, "fund the gap", "r2", mode="demo")
    assert plan["reply"].endswith("Reply 'go ahead' to execute.") and "FAC-IF" in plan["reply"]


def test_a_counterparty_never_gets_the_business_rewrite_and_a_business_mode_cannot_confirm_for_the_buyer(client):
    r = client.post("/nl", params={"mode": "business"}, json={"session_id": "c1", "actor": "COUNTERPARTY", "counterparty_id": "BUYER-1",
                                                           "text": "Evaluate EX01"}, headers={"X-Counterparty-Key": "demo-buyer-1-key"})
    assert r.status_code == 200 and "FLOW recommends" not in r.json()["reply"] and "Yes, run it" not in r.json()["reply"]


def test_why_are_we_countering_this_is_two_lines_in_business_words(client):
    _say(client, "Evaluate EX01", "e1")
    for lang, first, second in (
            ("en", "FLOW recommends a counter: the offer's future concessions cost ¥28,326.92 over the next 12 months, above your ¥5,000 "
                   "limit, and cash would fall below your minimum in 47 days.", "Recommended response: send Option A to the buyer."),
            ("zh", "FLOW 建议还价：此报价的未来让步在未来 12 个月内共需 ¥28,326.92，高于您 ¥5,000 的上限，并且现金将在47 天后低于您的最低现金储备。",
             "建议的回应：向买方发送方案 A。")):
        j = _say(client, "Why are we countering this?" if lang == "en" else "为什么要还价？", "e1", lang)
        assert j["intent"] == "EXPLAIN" and j["reply"].splitlines() == [first, second]
        assert "Verdict" not in j["reply"] and "TIER" not in j["reply"] and not re.search(r"[A-Z_]{6,}", j["reply"])
    raw = _say(client, "Why are we countering this?", "e1", mode=None)  # the raw reply stays for the Demo
    assert raw["reply"].startswith("Verdict REJECT (TIER_1): AGG_CONCESSION_EXCEEDED")
    other = _say(client, "Why is Option A cheaper?", "e1")  # a read with no verdict line is left as it was
    assert other["reply"].startswith("Option A: Terms stay at 45 days")
