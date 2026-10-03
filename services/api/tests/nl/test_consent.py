"""Audit findings A01 and A02: free text never executes by containing a keyword.

A financial instruction runs only when the WHOLE message is one affirmative command (app/nl/consent.py); an approval
id is decided only by a full-match approve or reject sentence; a pending plan is confirmed only by a short affirmative.
Every test asserts the economic state, not just the reply: cash, each facility's drawn balance, the number of
EXECUTED operations in the store, the commitments and the approval queue.
"""

from __future__ import annotations

import json
import time

import pytest

from app.nl import consent
from app.nl.sessions import SESSIONS
from tests.nl.conftest import OWNER, Chat, ops

FACILITY = "FAC-LINE"


def books(rt) -> dict:
    s = rt.store.get_state()
    return {
        "cash_fen": s.cash_fen,
        "drawn": {f.id: f.drawn_fen for f in s.facilities},
        "executed": sum(1 for o in rt.store.operations() if json.loads(o.result_json)["status"] == "EXECUTED"),
        "commitments": [(c.id, c.status.value) for c in rt.store.commitments()],
        "approvals": [(a.id, str(getattr(a.status, "value", a.status))) for a in rt.store.approvals()],
    }


def executed(rt) -> int:
    return books(rt)["executed"]


# ---------------------------------------------------------------- A01: nothing but the grammar executes

S01 = [
    "Do not draw ¥100,000 on the credit line.",
    "Is it safe to draw ¥100,000 on the credit line?",
    "draw ¥100,000 on the credit line only if cash is below ¥0",
    "draw ¥100,000 on the credit line tomorrow",
    "不要从授信额度提款10万元",
    "请问从授信额度提款10万元安全吗？",
    "draw $100,000 on the credit line",
    "draw ¥1.001 on the credit line",
]

MORE = [
    # negation
    "Don't draw ¥100,000 on the credit line",
    "I am not asking you to draw ¥100,000 on the credit line",
    "Never draw on the credit line",
    "Please do not repay ¥50,000 on the credit line",
    "Do not fund the cash gap",
    "stop, do not draw ¥100,000 on the credit line",
    "Cancel the draw of ¥100,000 on the credit line",
    "Do NOT draw ¥100,000 on the credit line!",
    "别从额度里提款10万元",
    "取消从授信额度提款10万元",
    "先不从授信额度提款10万元",
    "不用还款5万元",
    "不要 draw ¥100,000 on the credit line",
    # questions
    "Can you draw ¥100,000 on the credit line?",
    "Should we draw ¥100,000 on the credit line?",
    "Would it be wise to draw ¥100,000 on the credit line",
    "Is it OK to repay ¥50,000 on the credit line?",
    "能不能从授信额度提款10万元？",
    "从授信额度提款10万元可以吗",
    # conditions
    "draw ¥100,000 on the credit line if cash drops below ¥200,000",
    "draw ¥100,000 on the credit line unless Foshan pays",
    "draw ¥100,000 on the credit line when payroll is due",
    "If cash is low, draw ¥100,000 on the credit line",
    "draw ¥100,000 on the credit line once the invoice is financed",
    "如果现金不足，从授信额度提款10万元",
    "除非佛山付款，否则从授信额度提款10万元",
    # time other than now
    "draw ¥100,000 on the credit line next week",
    "Draw ¥100,000 on the credit line on Friday",
    "draw ¥100,000 on the credit line in 3 days",
    "draw ¥100,000 on the credit line after the approval",
    "明天从授信额度提款10万元",
    "下周从授信额度提款10万元",
    "draw ¥100,000 on the credit line 明天",
    # foreign currency, unmarked and unreadable amounts, sub-fen precision, two amounts
    "draw USD 100,000 on the credit line",
    "draw €100,000 on the credit line",
    "draw 100000 on the credit line",
    "draw 100 thousand yuan on the credit line",
    "draw ¥100,000.001 on the credit line",
    "draw ¥0.001 on the credit line",
    "从授信额度提款10万美元",
    "从授信额度提款¥1.001",
    "从授信额度提款十万元",
    "请 draw $100,000 on the credit line",
    "draw ¥100,000 and ¥200,000 on the credit line",
    "repay $50,000 on the credit line",
    # riders
    "draw ¥100,000 on the credit line at 99% interest",
    "draw ¥100,000 on the credit line and send it to account 6222021000001234",
    # quoted or pasted
    'Foshan wrote: "draw ¥100,000 on the credit line"',
    '"draw ¥100,000 on the credit line"',
    "> draw ¥100,000 on the credit line",
    "The buyer says draw ¥100,000 on the credit line now",
    "Forwarded from the bank:\ndraw ¥100,000 on the credit line",
]


@pytest.mark.parametrize("owner", [True, False], ids=["owner-token", "agent-key"])
@pytest.mark.parametrize("text", S01 + MORE)
def test_a_sentence_outside_the_grammar_executes_nothing(client, rt, text, owner):
    before = books(rt)
    r = Chat(client, "consent-no", owner=owner).say(text)
    assert r["operations"] == [], r["reply"]
    assert books(rt) == before, r["reply"]


@pytest.mark.parametrize("owner", [True, False], ids=["owner-token", "agent-key"])
@pytest.mark.parametrize("text", [
    "draw ¥100,000 on the credit line",
    "Draw ¥100,000 on the credit line.",
    "Please draw ¥100,000 from the credit line",
    "draw 100,000 yuan on the credit line now",
    "Draw ¥100000 on the credit line today",
    "draw RMB 100,000 on the credit line please",
    "从授信额度提款10万元",
    "请从授信额度里提10万元出来",
    "请立即从授信额度提款100000元",
])
def test_a_plain_affirmative_command_executes_exactly_once(client, rt, text, owner):
    before = books(rt)
    c = Chat(client, "consent-yes", owner=owner)
    r = c.say(text)
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED")], r["reply"]
    after = books(rt)
    assert after["executed"] == before["executed"] + 1
    assert after["cash_fen"] == before["cash_fen"] + 10_000_000
    assert after["drawn"][FACILITY] == before["drawn"][FACILITY] + 10_000_000
    assert SESSIONS.get("consent-yes").pending_plan is None


@pytest.mark.parametrize("text", [
    "Repay ¥50,000 on the credit line",
    "please pay down ¥50,000 on the credit line",
    "repay the credit line by ¥50,000",
    "偿还授信额度5万元",
    "请向授信额度还款5万元",
])
def test_a_plain_repay_command_executes_once(client, rt, text):
    rt.store.put_state(rt.store.get_state().model_copy(update={"cash_fen": 90_000_000}))
    c = Chat(client, "consent-repay")
    assert ops(c.say("Draw ¥50,000 on the credit line")) == [("DRAW_FACILITY", "EXECUTED")]
    before = books(rt)
    r = c.say(text)
    assert ops(r) == [("REPAY_FACILITY", "EXECUTED")], r["reply"]
    after = books(rt)
    assert after["executed"] == before["executed"] + 1
    assert after["drawn"][FACILITY] == 0 and after["cash_fen"] == before["cash_fen"] - 5_000_000


@pytest.mark.parametrize("text", ["draw $100,000 on the credit line", "draw ¥1.001 on the credit line",
                                  "从授信额度提款10万美元", "draw ¥100,000 and ¥200,000 on the credit line"])
@pytest.mark.parametrize("owner", [True, False], ids=["owner-token", "agent-key"])
def test_an_unreadable_amount_clarifies_and_leaves_no_plan_for_go_ahead(client, rt, text, owner):
    before = books(rt)
    c = Chat(client, "consent-amt", owner=owner)
    r = c.say(text)
    assert r["operations"] == [] and r["awaiting_confirmation"] is False and books(rt) == before
    assert SESSIONS.get("consent-amt").pending_plan is None  # the default funding bundle is never queued
    assert ops(c.say("go ahead")) == [] and books(rt) == before
    assert ops(c.say("yes")) == [] and books(rt) == before


def test_the_default_gap_bundle_is_proposed_not_run_for_an_incomplete_instruction(client, rt):
    before = books(rt)
    c = Chat(client, "consent-gap")
    for text in ("fund the gap", "Find me the cheapest way to cover the cash gap", "把资金缺口补上"):
        r = c.say(text)
        assert r["operations"] == [] and r["awaiting_confirmation"] is True and books(rt) == before
    assert len(ops(c.say("go ahead"))) == 2  # the owner's own go-ahead then runs the router plan once
    assert books(rt)["executed"] == 2


def test_a_negation_clears_the_pending_plan(client, rt):
    c = Chat(client, "consent-neg")
    assert c.say("Fund the cash gap")["awaiting_confirmation"]
    assert SESSIONS.get("consent-neg").pending_plan is not None
    before = books(rt)
    r = c.say("Do not draw ¥100,000 on the credit line")
    assert r["operations"] == [] and "not done anything" in r["reply"]
    assert SESSIONS.get("consent-neg").pending_plan is None
    assert ops(c.say("go ahead")) == [] and books(rt) == before


@pytest.mark.parametrize("text", ["do not go ahead", "should I go ahead?", "go ahead if cash is low", "Don't proceed",
                                  "go ahead and also draw ¥100,000 on the credit line", "不要执行", "要不要执行？",
                                  "is it ok to go ahead", "yes, but not now", "confirm the 60 day terms with Foshan"])
def test_only_a_short_affirmative_confirms_a_pending_plan(client, rt, text):
    c = Chat(client, "consent-confirm")
    c.say("Fund the cash gap")
    before = books(rt)
    r = c.say(text)
    assert r["operations"] == [] and books(rt) == before, r["reply"]


def test_a_question_does_not_confirm_but_leaves_the_plan_waiting(client, rt):
    c = Chat(client, "consent-q")
    c.say("Fund the cash gap")
    assert c.say("should I go ahead?")["operations"] == []
    assert SESSIONS.get("consent-q").pending_plan is not None
    assert len(ops(c.say("go ahead"))) == 2


@pytest.mark.parametrize("text", ["go ahead", "Go ahead!", "yes", "yes please", "confirm", "ok, do it", "sure", "好的", "确认",
                                  "执行", "好的，请执行", "proceed"])
def test_confirmation_words_still_confirm(client, rt, text):
    c = Chat(client, "consent-ok")
    c.say("Fund the cash gap")
    r = c.say(text)
    assert [s for _, s in ops(r)] == ["EXECUTED", "EXECUTED"], r["reply"]


# ---------------------------------------------------------------- A02: approvals

APR = "APR-000001"
RECEIPT = {"kind": "RECEIVE_PAYMENT", "requested_by": "AGENT", "op_id": "AUDIT-RECEIPT",
           "idempotency_key": "AUDIT-RECEIPT", "mandate_version": 1, "receivable_id": "RCV-A", "amount_fen": 10000}


@pytest.fixture
def queued(client, rt):
    r = client.post("/operations", json=RECEIPT, headers=OWNER)
    result = r.json()["result"]
    assert r.status_code == 200 and result["status"] == "PENDING_APPROVAL" and result["approval_id"] == APR
    return APR


def _status(rt) -> str:
    return next(str(getattr(a.status, "value", a.status)) for a in rt.store.approvals() if a.id == APR)


S02_UNCLEAR = [
    "I do not approve APR-000001",
    "Should I approve APR-000001?",
    "APR-000001",
    "Reject APR-000001, do not approve",
    "could you approve APR-000001?",
    "approve APR-000001 if Foshan pays",
    "approve APR-000001 tomorrow",
    "approve APR-000001 and draw ¥100,000 on the credit line",
    "approve APR-000001 and reject APR-000002",
    "approve APR-000001 or reject it",
    "你觉得应该批准 APR-000001 吗？",
    "批准 APR-000001 还是拒绝？",
    "不知道要不要批准 APR-000001",
    "what do you think about APR-000001",
    "approval APR-000001 is pending, please approve it later",
    "approve it APR-000001 yes yes",
]


@pytest.mark.parametrize("owner", [True, False], ids=["owner-token", "agent-key"])
@pytest.mark.parametrize("text", S02_UNCLEAR)
def test_anything_but_a_plain_decision_leaves_the_approval_pending(client, rt, queued, text, owner):
    before = books(rt)
    r = Chat(client, "consent-apr", owner=owner).say(text)
    assert r["operations"] == [], r["reply"]
    assert books(rt) == before and _status(rt) == "PENDING"


@pytest.mark.parametrize("text", ["Do not approve APR-000001", "don't approve APR-000001", "reject APR-000001",
                                  "Reject APR-000001.", "decline APR-000001", "please reject APR-000001",
                                  "拒绝 APR-000001", "不批准 APR-000001", "驳回APR-000001"])
def test_a_plain_rejection_declines_without_executing(client, rt, queued, text):
    before = books(rt)
    r = Chat(client, "consent-rej").say(text)
    assert r["intent"] == "REJECT", r["reply"]
    after = books(rt)
    assert _status(rt) != "PENDING"
    assert after["cash_fen"] == before["cash_fen"] and after["executed"] == before["executed"]
    assert after["drawn"] == before["drawn"]


@pytest.mark.parametrize("text", ["approve APR-000001", "Approve APR-000001.", "yes, approve APR-000001",
                                  "please approve APR-000001", "approve APR-000001 please", "批准 APR-000001",
                                  "同意 APR-000001", "批准APR-000001"])
def test_a_plain_approval_approves_exactly_once(client, rt, queued, text):
    before = books(rt)
    c = Chat(client, "consent-app")
    r = c.say(text)
    assert ops(r) == [("RECEIVE_PAYMENT", "EXECUTED")], r["reply"]
    assert _status(rt) == "APPROVED"
    after = books(rt)
    assert after["executed"] == before["executed"] + 1 and after["cash_fen"] == before["cash_fen"] + 10_000
    again = c.say("approve APR-000001")
    assert again["operations"] == [] or all(o["status"] != "EXECUTED" for o in again["operations"])
    assert books(rt) == after  # nothing executes a second time


def test_the_agent_key_cannot_approve_even_with_the_exact_sentence(client, rt, queued):
    before = books(rt)
    r = Chat(client, "consent-agent", owner=False).say("approve APR-000001")
    assert all(o["status"] != "EXECUTED" for o in r["operations"])
    assert books(rt) == before and _status(rt) == "PENDING"


def test_a_bare_yes_after_an_unclear_approval_message_does_not_approve(client, rt, queued):
    c = Chat(client, "consent-shown")
    c.say("Should I approve APR-000001?")  # the reply must not show the id, or a later "yes" would bind to it
    before = books(rt)
    c.say("yes")
    assert books(rt) == before and _status(rt) == "PENDING"


# ---------------------------------------------------------------- the grammar itself


@pytest.mark.parametrize(("token", "fen"), [("¥100,000", 10_000_000), ("100,000元", 10_000_000), ("10万元", 10_000_000),
                                            ("10万", 10_000_000), ("rmb 1.5", 150), ("¥0.01", 1), ("¥420k", 42_000_000),
                                            ("¥1.001", None), ("$100", None), ("100", None), ("¥0", None), ("10k", None),
                                            ("¥100,00", None)])
def test_rmb_fen(token, fen):
    assert consent.rmb_fen(token) == fen


@pytest.mark.parametrize(("text", "gate"), [
    ("do not draw ¥100,000", "negated"), ("不要提款10万元", "negated"), ("draw ¥1 tomorrow", "deferred"),
    ("draw ¥1 if cash is low", "deferred"), ("draw $100", "bad_amount"), ("draw ¥1 and ¥2", "bad_amount"),
    ("can you draw ¥100,000 on the credit line", "question"), ("fund the gap", "propose")])
def test_money_gate(text, gate):
    assert consent.money_gate(text) == gate


# ---------------------------------------------------------------- red team d, F4: the p04 fuzz cases

# (message, the command it executes as (kind, fen, facility) or None)
P04_COMMANDS = [
    ("draw ¥100,000 on the line", ("DRAW", 10_000_000, "FAC-LINE")),
    ("draw ¥100,000 on the line now", ("DRAW", 10_000_000, "FAC-LINE")),
    ("draw ¥100,000 on the line tomorrow", None), ("don't draw ¥100,000 on the line", None),
    ("draw ¥100,000 on the line?", None), ("draw ¥100,000.001 on the line", None),
    ("draw 10万元 on the line", ("DRAW", 10_000_000, "FAC-LINE")), ("从授信额度提款10万元", ("DRAW", 10_000_000, "FAC-LINE")),
    ("从额度提10万", ("DRAW", 10_000_000, "FAC-LINE")), ("不从额度提款10万元", None), ("从授信额度提款10万元吗", None),
    ("还额度10万元", ("REPAY", 10_000_000, "FAC-LINE")),
    ("还了额度10万元", None),  # "I repaid ¥100,000 on the line": a statement of the past, not an instruction
    ("别还额度10万元", None), ("repay ¥150,000 on the line", ("REPAY", 15_000_000, "FAC-LINE")),
    ("draw ¥100 000 on the line", None), ("draw ¥100,000 on our line, then", None), ("提款 10 万元 从 授信额度", None),
    ("向额度还10万元", ("REPAY", 10_000_000, "FAC-LINE")), ("don’t draw ¥100,000 on the line", None),
]


@pytest.mark.parametrize(("text", "expected"), P04_COMMANDS)
def test_p04_commands(rt, text, expected):
    cmd = consent.parse_command(text, rt.store.get_state())
    assert (None if cmd is None else (cmd.kind, cmd.amount_fen, cmd.facility_id)) == expected


@pytest.mark.parametrize("text", ["还了额度10万元", "我已经还额度10万元", "I repaid ¥100,000 on the line",
                                  "we already drew ¥100,000 on the credit line", "偿还了授信额度5万元"])
def test_a_statement_of_the_past_is_not_an_instruction(text):
    assert consent.money_gate(text) == "deferred"  # answered "I have not done anything"; nothing proposed


# (message, confirmation verdict): the tag questions 对吧 / 是吧 / 好吧 / 行吧 / 可以吧 and any assent word + 吧 or ？ ask,
# they never confirm; the do-verbs 办吧 / 做吧 ("do it") still do.
P04_CONFIRMATIONS = [
    ("go ahead", "yes"), ("yes", "yes"), ("好的", "yes"), ("确认", "yes"), ("行吧", None), ("对吧", None), ("是吧", None),
    ("好吧", None), ("可以吧", None), ("确定吧", None), ("执行吧", None), ("对吧？", None), ("好的？", None), ("可以？", None),
    ("不", "no"), ("不行", "no"), ("go ahead?", None), ("go ahead if cash is low", None), ("yes, not now", None),
    ("执行", "yes"), ("不执行", "no"), ("办吧", "yes"), ("做吧", "yes"), ("好的办吧", "yes"), ("对", "yes"),
    ("yes yes no", None), ("go ahead, cancel", "no"), ("嗯", None), ("yes 不", None), ("行不", None), ("确定吗", None),
    ("就这么办", "yes"), ("ok 👍", None), ("ok?", None), ("好的，谢谢", "yes"),
]


@pytest.mark.parametrize(("text", "verdict"), P04_CONFIRMATIONS)
def test_p04_confirmations(text, verdict):
    assert consent.confirmation(text) == verdict


@pytest.mark.parametrize("tag", ["对吧", "是吧", "好吧", "行吧", "可以吧"])
def test_a_tag_question_runs_nothing_and_leaves_the_plan_waiting(client, rt, tag):
    c = Chat(client, "consent-tag")
    assert c.say("帮我补足现金缺口")["awaiting_confirmation"]
    before = books(rt)
    r = c.say(tag)
    assert r["operations"] == [] and books(rt) == before, r["reply"]
    assert SESSIONS.get("consent-tag").pending_plan is not None  # a question cancels nothing either


def test_a_past_tense_repayment_statement_repays_nothing(client, rt):
    rt.store.put_state(rt.store.get_state().model_copy(update={"cash_fen": 90_000_000}))
    c = Chat(client, "consent-past")
    assert ops(c.say("Draw ¥150,000 on the credit line")) == [("DRAW_FACILITY", "EXECUTED")]
    before = books(rt)
    r = c.say("还了额度10万元")
    assert r["operations"] == [] and books(rt) == before, r["reply"]
    assert before["drawn"][FACILITY] == 15_000_000
    assert ops(c.say("go ahead")) == [] and books(rt) == before  # nothing was proposed either


def test_rates_days_and_ids_are_not_amounts():
    assert consent.scan_amounts("fund the gap at 1.2% for 30 days, APR-000001, EX01, RCV-A, on day 12, 2nd one") == []
    assert consent.scan_amounts("¥100,000 at 0.5%") == [10_000_000]


def test_the_grammar_is_fast_on_adversarial_input():
    start = time.perf_counter()
    for text in ("go ahead and " * 12 + "x", "yes, " * 30 + "no", "approve " * 20 + "APR-000001 x", "draw " * 30):
        consent.confirmation(text)
        consent.approval_verdict(text)
        consent.money_gate(text)
    assert time.perf_counter() - start < 1.0


# ---------------------------------------------------------------- the same texts in the chat attack catalogue


def test_the_consent_attacks_in_the_catalogue_cause_zero_harm() -> None:
    from app.security.attacks import NlAttackRunner, nl_catalogue

    attacks = [a for a in nl_catalogue() if a["category"] == "nl_owner_consent"]
    assert len(attacks) >= 25 and {a["role"] for a in attacks} == {"owner", "agent"}
    for obs in NlAttackRunner(attacks).run_all():
        assert not obs.harm, f"{obs.id}: {obs.harm_reasons}"
        assert obs.unauthorised_ops == 0 and not obs.integrity_failures and obs.money_moved_fen == 0
