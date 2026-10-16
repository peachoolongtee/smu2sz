"""EX12 goal -> plan -> fallback, and multi-turn corrections of a pending plan."""

from __future__ import annotations

import pytest

from app.domain.models import ObligationType
from tests.nl.conftest import Chat, ops

EX12 = "Get paid early on the Foshan invoice without giving anything away next quarter."


def _counter_obligations(rt, verdict_id):
    v = rt.store.get_verdict(verdict_id)
    (c,) = v.counters
    return c, c.obligations


def test_ex12_plan_is_a_zero_forward_counter_at_or_below_break_even(client, rt):
    r = Chat(client, "g-plan").say(EX12)
    assert r["intent"] == "ACCELERATE_RECEIPT" and r["awaiting_confirmation"]
    assert ops(r) == []  # proposed, not executed
    c, obs = _counter_obligations(rt, r["verdict"]["id"])
    assert [o.type for o in obs] == [ObligationType.IMMEDIATE_DISCOUNT]
    assert obs[0].rate_bp == 85 and obs[0].base.amount_fen == 26_000_000 and obs[0].base.receivable_id == "RCV-A"
    assert c.forward_value_fen == 0
    kinds = [(s["kind"], s["condition"]) for s in r["plan"]]
    assert ("COUNTER_OFFER", None) in kinds and ("NEGOTIATE", None) in kinds
    fallback = [k for k, cond in kinds if cond and "refuses" in cond]
    assert "SUBMIT_INVOICE_FOR_FINANCING" in fallback
    assert "0.88%" in r["reply"] and "¥0.00 of forward concessions" in r["reply"]


def test_ex12_buyer_accepts(client, rt):
    c = Chat(client, "g-acc")
    c.say(EX12)
    r = c.say("go ahead")
    assert r["negotiation"]["outcome"] == "ACCEPT"
    assert ops(r) == [("COUNTER_OFFER", "EXECUTED"), ("ACCEPT_OFFER", "EXECUTED"), ("DRAW_FACILITY", "EXECUTED")]
    assert all(o["tier"] == "TIER_1" for o in r["operations"])
    (cm,) = rt.store.commitments()
    assert cm.forward_value_fen >= 0 and all(o.type == ObligationType.IMMEDIATE_DISCOUNT for o in cm.obligations)
    assert sum(fc.value_fen for fc in rt.store.get_state().forward_concessions if fc.value_fen) == cm.forward_value_fen


def test_ex12_fallback_when_the_buyer_refuses(client, rt):
    c = Chat(client, "g-fb", buyer_profile="BUYER-1-HARDLINE")
    c.say(EX12)
    r = c.say("go ahead")
    assert r["negotiation"]["outcome"] == "NO_DEAL"
    assert ops(r) == [("COUNTER_OFFER", "EXECUTED"), ("DRAW_FACILITY", "EXECUTED"),
                      ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert rt.store.commitments() == []
    rcv = next(x for x in rt.store.get_state().receivables if x.id == "RCV-A")
    assert rcv.status == "FINANCED"


def test_ex12_inline_execution_marker_no_longer_runs_in_one_turn(client):
    # a sentence with a rider is not in the closed command grammar: it proposes, and the plan runs on a plain go-ahead
    c = Chat(client, "g-now")
    r = c.say(EX12.rstrip(".") + ", go ahead and do it now.")
    assert ops(r) == [] and r["awaiting_confirmation"]
    assert ops(c.say("go ahead"))[:1] == [("COUNTER_OFFER", "EXECUTED")]


def test_correction_amends_the_rate(client, rt):
    c = Chat(client, "g-rate")
    c.say(EX12)
    r = c.say("actually make it 0.8%")
    assert r["amended"] and r["awaiting_confirmation"] and ops(r) == []
    _, obs = _counter_obligations(rt, r["verdict"]["id"])
    assert obs[0].rate_bp == 80
    r = c.say("go ahead")
    assert ("COUNTER_OFFER", "EXECUTED") in ops(r)
    assert "0.80%" in r["plan"][1]["description"]


def test_correction_above_break_even_is_refused_and_the_plan_kept(client, rt):
    c = Chat(client, "g-high")
    first = c.say(EX12)
    r = c.say("actually make it 1%")
    assert not r["amended"] and ops(r) == [] and "unchanged" in r["reply"]
    r = c.say("go ahead")  # still the original 0.85% plan
    assert "0.85%" in r["plan"][1]["description"]
    assert first["verdict"]["id"] == r["verdict"]["id"]


def test_correction_switches_to_invoice_financing(client):
    c = Chat(client, "g-if")
    c.say(EX12)
    r = c.say("no, use invoice financing instead")
    assert r["amended"] and r["intent"] == "ACCELERATE_RECEIPT"
    assert [s["kind"] for s in r["plan"] if s["status"] == "PROPOSED"] == ["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]
    r = c.say("go ahead")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_cancel_discards_the_pending_plan(client, rt):
    c = Chat(client, "g-cancel")
    c.say(EX12)
    r = c.say("cancel")
    assert r["intent"] == "REJECT" and ops(r) == []
    assert all(s["status"] == "SKIPPED" for s in r["plan"])
    assert c.say("go ahead")["operations"] == []  # nothing pending any more
    assert rt.store.operations() == []


def test_correction_in_chinese(client, rt):
    c = Chat(client, "g-zh")
    c.say("佛山那张发票想提前收款，但下季度不做任何让步。")
    r = c.say("改成0.8%")
    assert r["amended"]
    _, obs = _counter_obligations(rt, r["verdict"]["id"])
    assert obs[0].rate_bp == 80


@pytest.mark.parametrize("question", ["为什么被拒绝?", "why was it rejected?", "Why cancel that?"])
def test_why_explains_and_keeps_the_pending_plan(client, rt, question):
    """"为什么被拒绝?" contains 拒绝, but it asks why: EXPLAIN wins over REJECT/cancel."""
    c = Chat(client, "g-why")
    c.say(EX12)
    r = c.say(question)
    assert r["intent"] == "EXPLAIN"
    assert ops(r) == []
    r = c.say("go ahead")
    assert ("COUNTER_OFFER", "EXECUTED") in ops(r)
