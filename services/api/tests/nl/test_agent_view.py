"""R-11, the owner's decision of 16 Oct 2026: the agent's chat channel does not read cash and limits.

The agent key (no owner token) gets an allow-list from POST /nl: the intent, the operation steps, the outcome word, what
ran or was queued for the owner, the refusal reason in words. Checked against the egress guard's own protected set
(`protected_for(store)`), the only figures it may carry are the amounts of the operations the turn proposed or ran.
The owner's chat is unchanged."""

from __future__ import annotations

import json

import pytest

from app.api.agent_view import operation_amounts
from app.egress import protected_for, scan
from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat

EX12 = "Get paid early on the Foshan invoice without giving anything away next quarter."
READS = {
    "en": ["show cash status", "show alerts", "Evaluate EX05", "why?", "why are we countering this?",
           "What if we give Foshan 60-day terms?", "how much cash do we have?"],
    "zh": ["显示现金状况", "评估 EX05", "为什么？", "如果给佛山60天账期会怎样？"],
}
ACTIONS = ["Fund the cash gap", "Find me the cheapest way to fund the cash gap", EX12, "Repay the credit line",
           "帮我找最便宜的方式补上资金缺口"]
FORBIDDEN_KEYS = ("verdict", "negotiation", "context_echo", "scope_used")


def _labels(rt, resp: dict, allow=()) -> list[str]:
    return sorted({lk.label for lk in scan(json.dumps(resp, ensure_ascii=False), protected_for(rt.store),
                                           recipient_id="AGENT-KEY", allow=allow)})


def _allowed(rt, resp: dict) -> list:
    """The amounts of the operations this turn proposed or ran (the agent's own acts)."""
    session = SESSIONS.get(resp["session_id"])
    held = list(session.pending_plan.ops) if session is not None and session.pending_plan is not None else []
    ids = [o["op_id"] for o in resp["operations"]] + [s["op_id"] for s in resp["plan"] if s["op_id"]]
    return operation_amounts(rt.store, ids, held)


@pytest.mark.parametrize("text", [*READS["en"], *READS["zh"]])
def test_the_agent_key_reads_no_protected_value(client, rt, text):
    r = Chat(client, f"ag-read-{abs(hash(text)) % 10_000}", owner=False).say(text)
    assert _labels(rt, r, _allowed(rt, r)) == [], r["reply"]
    assert all(r.get(k) is None for k in FORBIDDEN_KEYS)
    if r["awaiting_confirmation"]:  # a read that proposes a cure (alerts): the agent sees the steps it may run
        assert all(s["kind"] != "VERIFY" or "¥" not in s["description"] for s in r["plan"])
    else:
        assert _labels(rt, r) == [], r["reply"]
        assert r["reply"].endswith(("This needs the owner's sign-in.", "这需要业主登录。"))
        assert "¥" not in r["reply"] and "%" not in r["reply"]


@pytest.mark.parametrize("text", ACTIONS)
def test_an_agent_action_states_only_its_own_amounts(client, rt, text):
    chat = Chat(client, f"ag-act-{abs(hash(text)) % 10_000}", owner=False)
    first = chat.say(text)
    assert _labels(rt, first, _allowed(rt, first)) == [], first["reply"]
    assert all(first.get(k) is None for k in FORBIDDEN_KEYS)
    if first["awaiting_confirmation"]:
        done = chat.say("go ahead")
        assert _labels(rt, done, _allowed(rt, done)) == [], done["reply"]
        assert done["operations"] and all("entry_hash" not in o for o in done["operations"])


def test_the_evaluate_turn_gives_the_outcome_word_only(client, rt):
    r = Chat(client, "ag-eval", owner=False).say("Evaluate EX05")
    assert r["intent"] == "EVALUATE_OFFER" and r["verdict"] is None and r["outcome"] in {
        "ACCEPT", "COUNTER", "REJECT", "NO_DEAL", "NEEDS_OWNER_APPROVAL", "NO_VERDICT"}
    assert r["reply"].startswith("Outcome: ") and _labels(rt, r) == []


def test_the_owner_still_reads_cash_and_limits(client, rt):
    status = Chat(client, "own-status").say("show cash status")
    assert {"state.cash", "mandate.min_cash"} <= set(_labels(rt, status))
    evaluated = Chat(client, "own-eval").say("Evaluate EX05")
    assert evaluated["verdict"] is not None and "outcome" not in evaluated


def test_the_agent_still_runs_and_queues_its_plan(client, rt):
    chat = Chat(client, "ag-run", owner=False)
    proposal = chat.say("Fund the cash gap")
    assert proposal["awaiting_confirmation"] and "Reply 'go ahead' to execute." in proposal["reply"]
    assert any(s["kind"] == "DRAW_FACILITY" and "¥" in s["description"] for s in proposal["plan"])
    done = chat.say("go ahead")
    assert [o["status"] for o in done["operations"]] and all(o["status"] == "EXECUTED" for o in done["operations"])
    assert ": done." in done["reply"]


def test_a_refusal_comes_back_in_words(client, rt):
    owner = Chat(client, "ag-ref-owner")
    owner.say("Evaluate EX05")
    owner.say("go ahead")
    refused = Chat(client, "ag-ref", owner=False).say("approve APR-000001")
    assert [o["status"] for o in refused["operations"]] == ["REFUSED"]
    assert refused["reply"].startswith("Refused: only the owner") and _labels(rt, refused) == []
