"""Authority audit (18 Oct): what "go ahead" runs, what a bare acknowledgement is, and what a retry may never repeat.

- the confirmation reply reports each leg's real outcome and the funding still to arrange, never "funded" for a part-run plan;
- a retried "go ahead" repeats no executed leg and never approves the leg the first one queued;
- "ok", "ok thanks", "thanks", 好的谢谢 are acknowledgements, not consent; "go ahead", "yes, run it", "do it", 执行, 确认执行 are;
- an approval is decided by its id, or by the word approve (alone) when exactly one approval was named in the previous reply;
  "yes", "go ahead", "do it" and 好的办吧 never decide an approval;
- a question or an answer that offers a plan never replaces the plan that waits.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import set_runtime
from app.nl import reset_sessions
from app.nl.sessions import SESSIONS
from tests.funding.test_planner_executor_agree import SHORT_HOLD, build
from tests.nl.conftest import Chat, build_app, ops
from tests.nl.test_plan_binding import books
from tests.nl.test_plan_flags import GOAL, drawn, pending


@pytest.fixture
def world():
    """A runtime built from one of the planner/executor worlds, behind the real /nl app."""

    def make(w):
        rt = build(w)
        set_runtime(rt)
        reset_sessions()
        return rt, TestClient(build_app())

    yield make
    set_runtime(None)
    reset_sessions()


ACKS = ["ok", "ok thanks", "thanks", "okay", "sure", "fine", "好的谢谢", "好的", "好", "行", "可以", "没问题", "sounds good", "对"]
EXPLICIT = ["go ahead", "yes, run it", "do it", "执行", "确认执行", "yes", "confirm", "ok, do it", "好的，请执行"]


def executed(rt) -> list[str]:
    return [o.kind for o in rt.store.operations() if json.loads(o.result_json)["status"] == "EXECUTED"]


# ---------------------------------------------------------------- 1. the reply reports each leg, a retry repeats none


def test_a_part_run_plan_reports_each_leg_the_funding_still_to_arrange_and_never_says_funded(world):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-1")
    c.say(GOAL["en"])
    r = c.say("go ahead")
    assert ops(r) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    reply = r["reply"]
    assert "Draw ¥150,000.00 on FAC-LINE: done" in reply and "queued, not executed" in reply
    assert "Still to arrange: ¥90,000.00" in reply and "not fully funded" in reply
    assert "Cash in now: ¥150,000.00" in reply  # what is available now, apart from the advance still waiting
    assert "funded." not in reply.replace("not fully funded.", "")
    assert drawn(rt, "FAC-IF") == 0


def test_a_retried_go_ahead_repeats_no_executed_leg_and_approves_nothing(world):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-2")
    c.say(GOAL["en"])
    first = c.say("go ahead")
    assert ops(first)[0] == ("DRAW_FACILITY", "EXECUTED")
    [aid] = pending(rt)
    before = books(rt)
    for retry in ("go ahead", "yes do it", "好的办吧", "ok", "执行"):
        r = c.say(retry)
        assert ops(r) == [], (retry, r["reply"])
    assert books(rt) == before  # no second draw, and the queued advance is still waiting
    assert pending(rt) == [aid] and executed(rt).count("DRAW_FACILITY") == 1
    assert drawn(rt, "FAC-IF") == 0


def test_the_http_retry_with_the_same_request_id_is_replayed_not_run_again(world):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-3")
    c.say(GOAL["en"])
    a = c.say("go ahead", request_id="req-1")
    cash = rt.store.get_state().cash_fen
    b = c.say("go ahead", request_id="req-1")
    assert b["replayed"] is True and [k for k, _ in ops(b)] == [k for k, _ in ops(a)]
    assert [st for _, st in ops(b)] == ["DUPLICATE", "DUPLICATE"]  # the executor answers the same keys with the first results
    assert rt.store.get_state().cash_fen == cash and executed(rt).count("DRAW_FACILITY") == 1


# ---------------------------------------------------------------- 2. acknowledgements are not consent


@pytest.mark.parametrize("text", ACKS)
def test_a_bare_acknowledgement_runs_nothing_and_leaves_the_plan_waiting(world, text):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-ack")
    assert c.say(GOAL["en"])["awaiting_confirmation"]
    before = books(rt)
    r = c.say(text)
    assert ops(r) == [] and books(rt) == before, r["reply"]
    assert SESSIONS.get("aa-ack").pending_plan is not None
    assert len(ops(c.say("go ahead"))) == 2  # the plan is still the one shown


@pytest.mark.parametrize("text", EXPLICIT)
def test_explicit_consent_runs_the_plan_shown(world, text):
    _rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-yes")
    c.say(GOAL["en"])
    assert [o[0] for o in ops(c.say(text))] == ["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]


@pytest.mark.parametrize("text", ACKS)
def test_a_bare_acknowledgement_decides_no_approval(world, text):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-ack-apr")
    c.say(GOAL["en"])
    c.say("go ahead")  # queues the advance and names it
    [aid] = pending(rt)
    c.say(text)
    assert pending(rt) == [aid]


def test_an_intervening_question_does_not_swap_the_pending_plan(world):
    _rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-swap")
    c.say(GOAL["en"])
    plan = SESSIONS.get("aa-swap").pending_plan
    for q in ("what is my cash?", "can I pay everyone this month?", "should we draw ¥100,000 on the credit line?", "thanks"):
        c.say(q)
        assert SESSIONS.get("aa-swap").pending_plan is plan, q
    go = c.say("go ahead")
    assert [o[0] for o in ops(go)] == ["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]
    assert "¥100,000.00" not in go["reply"].split("Still to arrange")[0].replace("¥150,000.00", "")


def test_the_pay_everyone_offer_never_replaces_a_waiting_plan(world):
    from app.nl.sessions import SESSIONS as S

    _rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-offer")
    c.say(GOAL["en"])
    plan = S.get("aa-offer").pending_plan
    c.say("Can I pay everyone this month?")
    assert S.get("aa-offer").pending_plan is plan
    assert "go ahead" in c.say("thanks")["reply"]  # and the reminder still points at the plan the owner was shown


# ---------------------------------------------------------------- 2b. when "approve it" is contextual


def test_approve_it_binds_only_to_the_one_approval_the_previous_reply_named(world):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-ctx")
    c.say(GOAL["en"])
    c.say("go ahead")
    [aid] = pending(rt)
    c.say("thanks")  # an unrelated turn between: the approval is no longer the one just shown
    asked = c.say("approve it")
    assert ops(asked) == [] and pending(rt) == [aid] and asked["clarification"] is not None
    assert ops(c.say("approve it")) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]  # the queue was shown, then it binds


def test_approve_the_pending_one_does_not_reach_into_a_queue_that_was_not_shown(world):
    rt, client = world(SHORT_HOLD)
    Chat(client, "aa-q1").say(GOAL["en"])
    Chat(client, "aa-q1").say("go ahead")
    [aid] = pending(rt)
    r = Chat(client, "aa-q2").say("approve the pending one")
    assert ops(r) == [] and pending(rt) == [aid]


def test_an_id_always_decides_regardless_of_what_was_shown(world):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-id")
    c.say(GOAL["en"])
    c.say("go ahead")
    [aid] = pending(rt)
    c.say("thanks")
    assert ops(c.say(f"approve {aid}")) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_yes_and_go_ahead_never_decide_the_approval_just_shown(world):
    rt, client = world(SHORT_HOLD)
    c = Chat(client, "aa-nogo")
    c.say(GOAL["zh"])
    c.say("执行")
    [aid] = pending(rt)
    for text in ("go ahead", "yes do it", "好的办吧", "确认执行"):
        r = c.say(text)
        assert ops(r) == [] and pending(rt) == [aid], text
        assert f"approve {aid}" in r["reply"] or f"批准 {aid}" in r["reply"]
    assert ops(c.say("批准"))[0][1] == "EXECUTED"


# ---------------------------------------------------------------- 3. approved but the re-run was refused


def test_chat_says_approved_but_could_not_run_when_the_rerun_is_refused(client, rt):
    from tests.nl.conftest import AGENT, OWNER

    receipt = {"kind": "RECEIVE_PAYMENT", "requested_by": "AGENT", "op_id": "AUD-R", "idempotency_key": "AUD-R", "mandate_version": 1,
               "receivable_id": "RCV-A", "amount_fen": 10_000}
    assert client.post("/operations", json=receipt, headers=AGENT).json()["result"]["status"] == "PENDING_APPROVAL"
    booked = {**receipt, "requested_by": "SYSTEM", "op_id": "AUD-B", "idempotency_key": "AUD-B", "bank_reference": "BANK-AUD"}
    feed = {**OWNER, "X-Bank-Feed-Key": "demo-bank-feed-key"}
    assert client.post("/operations", json=booked, headers=feed).json()["result"]["status"] == "EXECUTED"
    cash = rt.store.get_state().cash_fen
    r = Chat(client, "aa-refused").say("approve APR-000001")
    assert ops(r) == [("RECEIVE_PAYMENT", "REFUSED")]
    assert r["reply"].startswith("You approved APR-000001, but it could not run:") and "no money moved" in r["reply"]
    assert rt.store.get_state().cash_fen == cash
