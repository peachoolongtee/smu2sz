"""Wave 7 addendum (map #65, ticket #76), item 8: the owner's chat in Business words. Only the reply strings change, and only when the
request asks for it (`POST /nl?mode=business`): the verdict, the funding plan and the confirmed run are said without ids, tier words or
reason codes, with one outcome line, the plan (amount, estimated cost, arrival) and the confirm words "Yes, run it". The raw replies of
the same turns stay as they were for the Demo and the audit, and the same operations run."""

from __future__ import annotations

import re

from app.nl.sessions import SESSIONS
from tests.alerts.test_repay_alert import to_day47
from tests.nl.conftest import OWNER
from tests.nl.test_alerts_opener import _day34

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
        ("If the buyer accepts Option A, the rest of the gap is funded: draws ¥147,210.00 on the Bank credit line today; "
         "estimated cost ¥825.99."),
        ("If the buyer refuses, the gap is funded another way: draws ¥150,000.00 on the Bank credit line today; requests ¥255,000.00 of "
         "invoice financing, arriving in 3 days; estimated cost ¥3,113.93."),
        'Reply "Yes, run it" to send Option A and Option B to Foshan Home Retail Co. Nothing is sent before that.']
    assert not ID_OR_CODE.search(j["reply"]) and j["awaiting_confirmation"] is True and j["operations"] == []


def test_yes_run_it_sends_the_counters_and_says_what_happened_in_business_words(client):
    _say(client, "Evaluate EX01", "b2")
    j = _say(client, "Yes, run it", "b2")
    assert j["reply"] == "Foshan Home Retail Co. accepted Option A and the agreement is recorded. Drew ¥147,210.00 on the Bank credit line today."
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
    assert done["reply"] == "Foshan Home Retail Co.接受了方案 A，协议已记录。已从Bank credit line提款 ¥147,210.00，今天到账。"


def test_the_funding_plan_in_chinese(client):
    plan = _say(client, "fund the gap", "b5", "zh")
    assert plan["reply"] == ("FLOW 的方案：融资 ¥405,000.00，预计成本 ¥3,113.93。从Bank credit line提款 ¥150,000.00，今天到账；"
                             "申请 ¥255,000.00 的发票融资，3 天后到账。回复“好，执行”即可执行。")


def test_without_the_mode_the_raw_replies_are_exactly_as_before_and_the_same_operations_run(client):
    raw = _say(client, "Evaluate EX01", "r1", mode=None)
    assert raw["reply"].startswith("Verdict REJECT (TIER_1): AGG_CONCESSION_EXCEEDED") and "Reply 'go ahead' to negotiate" in raw["reply"]
    assert ID_OR_CODE.search(raw["reply"])
    ran = _say(client, "go ahead", "r1", mode=None)
    assert "Draw ¥147,210.00 on FAC-LINE: done." in ran["reply"]


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
            ("en", ("FLOW recommends a counter: the offer's future concessions cost ¥28,326.92 over the next 12 months, above your ¥5,000 "
                    "limit, and cash would fall below your minimum in 47 days."), "Recommended response: send Option A to the buyer."),
            ("zh", "FLOW 建议还价：此报价的未来让步在未来 12 个月内共需 ¥28,326.92，高于您 ¥5,000 的上限，并且现金将在47 天后低于您的最低现金储备。",
             "建议的回应：向买方发送方案 A。")):
        j = _say(client, "Why are we countering this?" if lang == "en" else "为什么要还价？", "e1", lang)
        # the counter is the plan waiting for "go ahead": every owner read says so (ASK-2b), after the two lines in business words
        reply, _, reminder = j["reply"].partition(" Your earlier plan is still waiting" if lang == "en" else "您之前的方案仍在等待")
        assert reminder and j["awaiting_confirmation"]
        assert j["intent"] == "EXPLAIN" and reply.rstrip().splitlines() == [first, second]
        assert "Verdict" not in j["reply"] and "TIER" not in j["reply"] and not re.search(r"[A-Z_]{6,}", j["reply"])
    raw = _say(client, "Why are we countering this?", "e1", mode=None)  # the raw reply stays for the Demo
    assert raw["reply"].startswith("Verdict REJECT (TIER_1): AGG_CONCESSION_EXCEEDED")
    other = _say(client, "Why is Option A cheaper?", "e1")  # a read with no verdict line is left as it was
    assert other["reply"].startswith("Option A: Terms stay at 45 days")


# ---------------------------------------------------------------- alert cures, repayments, approvals and the status read (map #65 debt, #83)

ENGINE_ID = re.compile(r"\b(?:FAC-[A-Z]+|RCV-[A-Z]+|RI:\S+|BUYER-\d+|APR-\d{6})\b")


def _owner_words(reply: str) -> None:
    """The Business rule for every rewritten reply: no verdict line, no tier word, no engine code, and an id only inside a parenthesis."""
    assert "Verdict" not in reply and "TIER" not in reply and not re.search(r"[A-Z_]{6,}", reply), reply
    assert not ENGINE_ID.search(re.sub(r"[(（][^)）]*[)）]", "", reply)), reply
    assert "Go ahead?" not in reply and "go ahead" not in reply.lower().replace("yes, do it", ""), reply


def test_the_alert_cure_proposal_is_one_outcome_line_the_plan_and_the_confirm_words(client, rt):
    _day34(client, rt)
    en = _say(client, "what needs me today?", "ac1")
    assert en["reply"] == ("Cash would fall ¥200,000.00 below your minimum in 8 days. FLOW's plan: ¥200,000.00 of funding, estimated cost "
                           "¥1,782.19. Requests ¥200,000.00 of invoice financing, arriving in 3 days. Some of this needs your approval before "
                           'it runs; it would wait in your approvals. Reply "Yes, run it" to run it.')
    assert en["awaiting_confirmation"] is True and en["operations"] == []
    zh = _say(client, "今天有什么需要我处理的？", "ac2", "zh")
    assert zh["reply"] == ("现金将在8 天后比您的最低现金储备低 ¥200,000.00。FLOW 的方案：融资 ¥200,000.00，预计成本 ¥1,782.19。申请 ¥200,000.00 的发票融资，"
                           "3 天后到账。其中一部分需要您批准后才会执行，会先放在待批事项中。回复“好，执行”即可执行。")
    for reply in (en["reply"], zh["reply"]):
        _owner_words(reply)
    raw = _say(client, "what needs me today?", "ac3", mode=None)  # the Demo keeps the engine's sentence, ids and all
    assert raw["reply"].startswith("Day 34.") and "RI:BUYER-1:2" in raw["reply"] and raw["reply"].endswith("Go ahead?")


def test_yes_run_it_on_an_alert_cure_queues_it_for_approval_and_keeps_the_approval_id_for_the_next_yes(client, rt):
    _day34(client, rt)
    _say(client, "what needs me today?", "ac4")
    queued = _say(client, "Yes, run it", "ac4")
    assert [(o["kind"], o["status"]) for o in queued["operations"]] == [("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    aid = queued["operations"][0]["approval_id"]
    assert queued["reply"] == (f"This needs your approval before it runs ({aid}): requests ¥200,000.00 of invoice financing, arriving in 3 days. "
                               'Estimated cost ¥1,782.19. I have not run it. Reply "Approve it" to approve it.')
    _owner_words(queued["reply"])
    assert SESSIONS.get("ac4").shown_approvals == [aid]  # the consent code still finds the id, in the parenthesis
    waiting = _say(client, "what needs me today?", "ac5")
    assert waiting["reply"] == ("Cash would fall ¥200,000.00 below your minimum in 8 days. The plan is already waiting for your approval "
                                f"({aid}): requests ¥200,000.00 of invoice financing, arriving in 3 days; estimated cost ¥1,782.19. Nothing has run "
                                'yet. Reply "Approve it" to approve it.')  # the alerts turn speaks of FLOW, never "I" (lead, 17 Oct)
    _owner_words(waiting["reply"])
    done = _say(client, "Approve it", "ac5")
    assert [(o["kind"], o["status"]) for o in done["operations"]] == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert done["intent"] == "APPROVE" and done["reply"] == "Approved and done. Requested ¥200,000.00 of invoice financing, arriving in 3 days."
    _owner_words(done["reply"])


def test_the_same_cure_run_in_chinese_and_the_raw_run_unchanged_without_the_mode(client, rt):
    _day34(client, rt)
    _say(client, "今天有什么需要我处理的？", "ac6", "zh")
    queued = _say(client, "好，执行", "ac6", "zh")
    aid = queued["operations"][0]["approval_id"]
    assert queued["reply"] == (f"这需要您批准后才会执行（{aid}）：申请 ¥200,000.00 的发票融资，3 天后到账。预计成本 ¥1,782.19。我尚未执行。回复“批准”即可批准。")
    _owner_words(queued["reply"])
    done = _say(client, "批准", "ac6", "zh")
    assert done["reply"] == "已批准并完成。已申请 ¥200,000.00 的发票融资，3 天后到账。"


def test_the_raw_cure_run_is_unchanged_without_the_mode(client, rt):
    _day34(client, rt)
    _say(client, "what needs me today?", "ac7", mode=None)
    raw = _say(client, "go ahead", "ac7", mode=None)
    assert "queued as APR-" in raw["reply"] and 'Say "approve APR-' in raw["reply"]
    assert SESSIONS.get("ac7").shown_approvals == [raw["operations"][0]["approval_id"]]


def test_a_decline_and_the_approvals_that_cannot_be_decided_are_said_without_ids(client, rt):
    _day34(client, rt)
    _say(client, "what needs me today?", "ap1")
    aid = _say(client, "Yes, run it", "ap1")["operations"][0]["approval_id"]
    declined = _say(client, f"reject {aid}", "ap1")
    assert declined["reply"] == f"Declined. Nothing was run ({aid})." and declined["intent"] == "REJECT"
    assert _say(client, f"reject {aid}", "ap1")["reply"] == "That approval was already decided; nothing was changed."
    assert _say(client, "approve APR-000099", "ap1")["reply"] == "I cannot find that approval in your queue; nothing was changed."
    assert _say(client, "批准 APR-000099", "ap1", "zh")["reply"] == "我在您的待批队列中找不到该事项；未做任何更改。"
    assert _say(client, "reject", "ap2")["reply"] == "Nothing is waiting for approval."
    for reply in (declined["reply"],):
        _owner_words(reply)


def test_which_pending_operation_names_each_one_in_words_with_its_id_in_a_parenthesis(client, rt):
    _day34(client, rt)
    _say(client, "what needs me today?", "ap3")
    first = _say(client, "Yes, run it", "ap3")["operations"][0]["approval_id"]
    _say(client, "fund the gap", "ap4")
    second = _say(client, "Yes, run it", "ap4")  # the plan's advance waits for the owner as well
    # (the ¥2,790 of the line the rounded early-pay face left unused, R-10, is drawn first at Tier 1)
    assert next(o for o in second["operations"] if o["kind"] == "SUBMIT_INVOICE_FOR_FINANCING")["status"] == "PENDING_APPROVAL"
    _owner_words(second["reply"])
    asked = _say(client, "approve it", "ap5")
    assert asked["intent"] == "AMBIGUOUS" and asked["clarification"] is not None
    labels = [o["label"] for o in asked["clarification"]["options"]]
    assert labels[0].startswith("Finance ¥200,000.00 of the ¥420,000.00 invoice to Foshan Home Retail Co.") and labels[0].endswith(f"({first})")
    assert all(re.search(r"\(APR-\d{6}\)$", x) for x in labels) and len(labels) == 2
    _owner_words(asked["reply"])
    assert asked["reply"].startswith("Which pending operation? (1) Finance ")


def test_a_funding_plan_run_that_waits_for_the_owner_says_what_ran_what_waits_and_what_was_not_sent(client, rt):
    _day34(client, rt)
    assert _say(client, "fund the gap", "fg1")["awaiting_confirmation"] is True
    j = _say(client, "Yes, run it", "fg1")
    # the rounded early-pay face (R-10) leaves ¥2,790 of the line unused, so the plan draws it first (6.40%, Tier 1)
    aid = next(o for o in j["operations"] if o["kind"] == "SUBMIT_INVOICE_FOR_FINANCING")["approval_id"]
    assert j["reply"] == (f"Done so far: Drew ¥2,790.00 on the Bank credit line today. This needs your approval before it runs ({aid}): requests ¥80,000.00 of invoice financing, arriving in 3 days. The plan's "
                          "estimated cost is ¥1,702.20 in all. I have not run it. Not sent: requests ¥117,210.00 of invoice financing, arriving in 3 "
                          'days. Reply "Approve it" to approve it.')
    _owner_words(j["reply"])
    raw = _say(client, "fund the gap", "fg2", mode=None)
    assert "Submit RI:BUYER-1:32 to FAC-IF" in raw["reply"] or "RI:BUYER-1:32" in raw["reply"]


def test_a_void_plan_says_nothing_ran_and_proposes_again_in_business_words(client, rt):
    _day34(client, rt)
    _say(client, "what needs me today?", "vd1")
    client.post("/clock/advance", json={"to_day": 35}, headers=OWNER)
    j = _say(client, "Yes, run it", "vd1")
    assert j["operations"] == [] and j["awaiting_confirmation"] is True
    assert j["reply"].startswith("Nothing was run: the books changed since I proposed it. Here is a fresh proposal. Cash would fall")
    _owner_words(j["reply"])
    zh = _say(client, "好，执行", "vd1", "zh")  # the fresh proposal is its own plan: the earlier one never ran
    assert zh["operations"][0]["status"] in ("PENDING_APPROVAL", "EXECUTED")


def test_the_repayment_proposal_and_its_confirmed_run_are_in_business_words(client, rt):
    to_day47(client, rt)
    plan = _say(client, "repay the credit line", "rp1")
    assert plan["reply"] == ("You can repay ¥147,210.00 on the Bank credit line today, and cash stays above your minimum. FLOW's plan: Repays "
                             '¥147,210.00 on the Bank credit line today. Reply "Yes, run it" to run it.')
    assert plan["awaiting_confirmation"] is True
    done = _say(client, "Yes, run it", "rp1")  # the consent flow still executes
    assert [(o["kind"], o["status"]) for o in done["operations"]] == [("REPAY_FACILITY", "EXECUTED")]
    assert done["reply"] == "Done. Repaid ¥147,210.00 on the Bank credit line, interest ¥1,213.17."
    zh = _say(client, "repay the credit line", "rp2", "zh")
    assert zh["reply"] == "没有可按需偿还的已提款额度。"  # the line is repaid now; this reply never carried an id
    for reply in (plan["reply"], done["reply"]):
        _owner_words(reply)


def test_the_repayment_in_chinese_and_the_raw_repayment_unchanged_without_the_mode(client, rt):
    to_day47(client, rt)
    raw = _say(client, "repay the credit line", "rp4", mode=None)
    assert raw["reply"].startswith("Repay ¥147,210.00 on FAC-LINE. Reply 'go ahead' to execute.")
    zh = _say(client, "repay the credit line", "rp3", "zh")
    assert zh["reply"] == "您今天可以向Bank credit line还款 ¥147,210.00，现金仍高于最低现金储备。FLOW 的方案：今天向Bank credit line还款 ¥147,210.00。回复“好，执行”即可执行。"
    assert _say(client, "好，执行", "rp3", "zh")["reply"] == "已完成。已向Bank credit line还款 ¥147,210.00，利息 ¥1,213.17。"
    _owner_words(zh["reply"])


def test_the_repayment_alert_cure_runs_after_yes_run_it(client, rt):
    to_day47(client, rt)
    plan = _say(client, "what needs me today?", "rp5")
    assert plan["reply"] == ("The ¥147,210.00 drawn on the Bank credit line can be repaid today, and cash stays above your minimum. FLOW's plan: "
                             'Repays ¥147,210.00 on the Bank credit line today. Reply "Yes, run it" to run it.')
    done = _say(client, "Yes, run it", "rp5")
    assert [(o["kind"], o["status"]) for o in done["operations"]] == [("REPAY_FACILITY", "EXECUTED")]
    assert done["reply"] == "Done. Repaid ¥147,210.00 on the Bank credit line. Interest as quoted ¥1,213.17. The line is repaid."
    _owner_words(plan["reply"])
    _owner_words(done["reply"])


def test_the_status_read_in_english_and_chinese_and_raw_without_the_mode(client, rt):
    _day34(client, rt)
    _say(client, "what needs me today?", "st0")
    assert _say(client, "Yes, run it", "st0")["operations"][0]["approval_id"]  # the plan is queued for the owner
    en = _say(client, "show cash status", "st1")
    assert en["reply"].splitlines() == [
        "Cash today is ¥300,000.00; your minimum cash reserve is ¥300,000.00.",
        "Cash would fall below your minimum: ¥200,000.00 short in 8 days.",
        "Debt service cover (DSCR) is lowest at 1.92× in month 3; your minimum is 1.25×.",
        "Leverage is highest at 1.48× in month 1; your maximum is 2.50×.",
        "Future concessions given: ¥0.00 of your ¥5,000 limit.",
        "Drawn: ¥147,210.00 on the Bank credit line.",
        "1 item waits for your approval."]  # an approval's id is not a Business word
    zh = _say(client, "show cash status", "st2", "zh")
    assert zh["reply"].splitlines() == [
        "今天现金 ¥300,000.00；您的最低现金储备为 ¥300,000.00。", "现金将低于最低现金储备：8 天后缺 ¥200,000.00。",
        "偿债覆盖率（DSCR）最低 1.92×（第 3 月），下限 1.25×。", "杠杆率最高 1.48×（第 1 月），上限 2.50×。",
        "已给出的远期让步：¥0.00，上限 ¥5,000。", "已提款：Bank credit line ¥147,210.00。", "1 项待您审批。"]
    for reply in (en["reply"], zh["reply"]):
        _owner_words(reply)
    raw = _say(client, "show cash status", "st3", mode=None)
    assert raw["reply"].splitlines()[0] == "Cash today (day 34): ¥300,000.00. Reserve floor ¥300,000.00." and "FAC-LINE" in raw["reply"]


def test_past_due_invoices_and_other_alerts_are_said_without_ids_when_no_cure_is_proposed(client, rt):
    _day34(client, rt)
    _say(client, "what needs me today?", "pd1")
    aid = _say(client, "Yes, run it", "pd1")["operations"][0]["approval_id"]
    _say(client, f"approve {aid}", "pd1")
    client.post("/clock/advance", json={"to_day": 36}, headers=OWNER)
    en = _say(client, "what needs me today?", "pd2")
    assert en["reply"] == ("¥160,000.00 on the ¥420,000.00 invoice to Foshan Home Retail Co. was due 4 days ago and has not arrived. 1 more warning: "
                           "Cash is close to your minimum today.")
    # Asked in Chinese: an English question is answered in English whatever the page's language (lead, 17 Oct; tests/nl/test_answer_card.py)
    zh = _say(client, "今天有什么需要我处理的？", "pd3", "zh")
    assert zh["reply"] == "Foshan Home Retail Co. 的 ¥420,000.00 发票的 ¥160,000.00 应于4 天前到账，至今未到。另有 1 项提醒：今天现金仅略高于最低现金储备。"
    for reply in (en["reply"], zh["reply"]):
        _owner_words(reply)
