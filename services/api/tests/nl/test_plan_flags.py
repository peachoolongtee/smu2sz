"""Chat tells the truth about the two things the router flags on a plan (docs/FINANCIAL_SEMANTICS.md, "Rates"):

- `needs_owner_approval`: a leg costs more a year than the mandate lets the agent borrow alone, so the executor queues it
  for the owner. The proposal names the cost, the rate and the ceiling and says the leg will wait (APR-...); after the
  go-ahead the reply names the approval and how to approve it, and the leg runs only when the owner approves it. The
  agent channel is the one whose legs are queued (an owner-token session's own go-ahead is sent as the owner's);
- `executable_now` False: a leg uses an invoice that is not issued yet, so the executor would refuse it today. The plan
  is never offered for a go-ahead: the reply says what it waits for and nothing is stored.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import set_runtime
from app.nl import reset_sessions
from app.nl.sessions import SESSIONS
from tests.funding.test_planner_executor_agree import SHORT_HOLD, UNISSUED, build
from tests.nl.conftest import Chat, build_app, ops

GOAL = {"en": "Find me the cheapest way to fund the cash gap", "zh": "帮我找最便宜的方式补上资金缺口"}
GO = {"en": "go ahead", "zh": "执行"}
COMPARE = {"en": "compare financing options", "zh": "比较融资方案"}


@pytest.fixture
def world():
    """A runtime built from one of the planner/executor worlds, behind the real /nl app."""
    made = []

    def make(w):
        rt = build(w)
        set_runtime(rt)
        reset_sessions()
        made.append(rt)
        return rt, TestClient(build_app())

    yield make
    set_runtime(None)
    reset_sessions()


def pending(rt) -> list[str]:
    return [a.id for a in rt.store.approvals() if str(getattr(a.status, "value", a.status)) == "PENDING"]


def drawn(rt, fid: str) -> int:
    return next(f.drawn_fen for f in rt.store.get_state().facilities if f.id == fid)


# ---------------------------------------------------------------- a leg above the ceiling


def test_a_proposal_names_the_rate_and_ceiling_and_the_leg_waits_for_approval(world):
    rt, client = world(SHORT_HOLD)  # the advance on RCV-A is held 10 days: 32.53% a year against a 15.00% ceiling
    cash = rt.store.get_state().cash_fen
    agent = Chat(client, "flag-en", owner=False)  # the agent channel: its legs are queued for the owner
    r = agent.say(GOAL["en"])
    reply = r["reply"]
    assert r["awaiting_confirmation"] and ops(r) == []
    assert "costs ¥801.99, which is 32.53% a year, above your 15.00% yearly ceiling" in reply
    assert "will wait for your approval (APR-…) rather than run" in reply
    assert "Submit RCV-A to FAC-IF for a ¥90,000.00 advance" in reply
    assert "Draw ¥150,000.00 on FAC-LINE" not in reply.split("above your")[0].split("costs ¥801.99")[-1]  # not flagged
    # go ahead: the line draw runs, the advance is queued, and the reply names the approval and how to approve it
    done = agent.say(GO["en"])
    assert ops(done) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    [aid] = pending(rt)
    assert aid in done["reply"] and f'"approve {aid}"' in done["reply"] and "approval card" in done["reply"]
    assert "queued, not executed" in done["reply"] and "Cost as quoted" not in done["reply"]
    assert rt.store.get_state().cash_fen == cash + 15_000_000 and drawn(rt, "FAC-IF") == 0  # nothing from the advance
    assert SESSIONS.get("flag-en").pending_plan is None
    # the owner approves it, and only then does it run
    owner = Chat(client, "flag-owner")
    approved = owner.say(f"approve {aid}")
    assert ops(approved) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]
    assert drawn(rt, "FAC-IF") == 9_000_000 and pending(rt) == []


def test_a_proposal_names_the_rate_and_ceiling_in_chinese(world):
    rt, client = world(SHORT_HOLD)
    agent = Chat(client, "flag-zh", owner=False)
    r = agent.say(GOAL["zh"])
    reply = r["reply"]
    assert r["awaiting_confirmation"]
    assert "费用 ¥801.99，年化 32.53%，高于您 15.00% 的年度融资成本上限" in reply
    assert "不会直接执行，而是等待您批准（APR-…）" in reply
    done = agent.say(GO["zh"])
    assert ops(done) == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "PENDING_APPROVAL")]
    [aid] = pending(rt)
    assert f"批准 {aid}" in done["reply"] and "审批卡" in done["reply"] and drawn(rt, "FAC-IF") == 0
    assert ops(Chat(client, "flag-zh-owner").say(f"批准 {aid}")) == [("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_an_owner_session_is_not_promised_a_queue_it_will_not_get(world):
    """The owner's own go-ahead is sent as the owner's request, which the executor does not queue: the proposal still
    states the cost, rate and ceiling, but promises no APR-... wait."""
    rt, client = world(SHORT_HOLD)
    r = Chat(client, "flag-own").say(GOAL["en"])
    assert "costs ¥801.99, which is 32.53% a year, above your 15.00% yearly ceiling" in r["reply"]
    assert "APR-…" not in r["reply"] and "will wait for your approval" not in r["reply"]


def test_a_plan_that_needs_no_one_says_nothing_about_approval(client, rt):
    r = Chat(client, "flag-golden", owner=False).say(GOAL["en"])
    assert r["awaiting_confirmation"] and "approval" not in r["reply"] and "ceiling" not in r["reply"]


# ---------------------------------------------------------------- a plan that cannot run today


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_a_plan_on_an_invoice_not_issued_yet_is_not_offered_and_nothing_is_stored(world, lang):
    rt, client = world(UNISSUED)
    chat = Chat(client, f"flag-un-{lang}")
    cash = rt.store.get_state().cash_fen
    r = chat.say(GOAL[lang])
    reply = r["reply"]
    assert r["awaiting_confirmation"] is False and ops(r) == [] and SESSIONS.get(f"flag-un-{lang}").pending_plan is None
    if lang == "en":
        assert "It cannot run today" in reply and "RI:BUYER-1:2 is not an invoice I can finance today" in reply
        assert "it is issued on day 2" in reply and "Nothing was stored and nothing was executed" in reply
        assert "Reply 'go ahead'" not in reply
    else:
        assert "该方案今天无法执行" in reply and "RI:BUYER-1:2 目前还不能用来融资" in reply
        assert "第 2 天开出" in reply and "未保存任何操作" in reply and "回复“执行”" not in reply
    # "go ahead" runs nothing, and no operation was ever stored
    done = chat.say(GO[lang])
    assert ops(done) == [] and rt.store.operations() == [] and rt.store.approvals() == []
    assert rt.store.get_state().cash_fen == cash


# ---------------------------------------------------------------- the comparison


def test_the_compare_reply_shows_both_flags_in_words(world):
    rt, client = world(SHORT_HOLD)
    # SHORT_HOLD has no gap on day 0 once the golden draws are made; ask on the books as they stand
    en = Chat(client, "cmp-sh").say(COMPARE["en"])["reply"]
    assert "It needs your approval: " in en and "32.53% a year, above your 15.00% yearly ceiling" in en
    assert "legs above your ceiling will wait for your approval" not in en  # an owner session: no queue is promised
    assert "its rate alone is above your 15.00% yearly ceiling, so any use of it needs your approval" in en

    rt, client = world(UNISSUED)
    en = Chat(client, "cmp-un").say(COMPARE["en"])["reply"]
    assert "It cannot run today: " in en and "RI:BUYER-1:2 is not an invoice I can finance today" in en
    assert "'fund the gap' would not run this plan today" in en
    zh = Chat(client, "cmp-un-zh").say(COMPARE["zh"])["reply"]
    assert "该方案今天无法执行：" in zh and "今天回复“补足资金缺口”也不会执行该方案" in zh
    rt, client = world(SHORT_HOLD)
    zh = Chat(client, "cmp-sh-zh").say(COMPARE["zh"])["reply"]
    assert "该方案需要您批准：" in zh and "年化 32.53%，高于您 15.00% 的年度融资成本上限" in zh
    assert "其利率本身高于您 15.00% 的年度上限" in zh


def test_the_compare_reply_lists_a_flagged_alternative_priced_by_the_router(client, rt):
    """The buyer's early-payment offer at 1.5% costs 18.5% a year: the row that uses it is admissible, priced and
    flagged, while the selected plan (the line and the advance) needs no one."""
    from tests.funding.variants import golden, with_facility

    s, _ = golden()
    s = with_facility(s, "FAC-EARLYPAY", rate_bp=150)
    rt.store.put_state(s.model_copy(update={"state_version": rt.store.get_state().state_version + 1}))
    en = Chat(client, "cmp-alt").say(COMPARE["en"])["reply"]
    assert "It needs your approval" not in en  # the selected plan is the one that needs no one
    line = next(x for x in en.splitlines() if x.startswith("- Also priced:"))
    assert "needs your approval: " in line and "above the mandate's 15.00% ceiling" in line
    zh = Chat(client, "cmp-alt-zh").say(COMPARE["zh"])["reply"]
    assert "- 另有测算：" in zh and "需要您批准：年化" in zh and "高于 15.00% 上限" in zh
