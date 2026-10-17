"""ASK-1 (security review of the question gate).

ASK-1: a Tier-3 request put as a question ("sign a personal guarantee?", "should we pledge the equipment?", 要不要签个人担保？)
must still reach the executor, be REFUSED, be written to the operations log and raise its TIER3 security event, for the owner
and for the agent key alike, exactly as the same words without the question mark do. Only a question that plainly asks for
information, from the owner ("Is equity an option?", "Did anyone try to change our limits?", 个人担保是什么意思？), writes
nothing (lexicon.tier3_is_information). Any other caller's Tier-3 words are always a request.
"""

from __future__ import annotations

import pytest

from app.nl import lexicon as lx
from app.nl.sessions import SESSIONS
from tests.nl.conftest import Chat, ops

# (text, lang, the Tier-3 operation the executor must refuse)
REQUESTS_AS_QUESTIONS = [
    ("sign a personal guarantee?", "en", "SIGN_PERSONAL_GUARANTEE"),
    ("Sign a personal guarantee for the bank loan, ok?", "en", "SIGN_PERSONAL_GUARANTEE"),
    ("should we sign a personal guarantee?", "en", "SIGN_PERSONAL_GUARANTEE"),
    ("Issue equity to cover the gap?", "en", "ISSUE_EQUITY"),
    ("pledge the equipment as collateral?", "en", "PLEDGE_COLLATERAL"),
    ("raise the discount limit to 5%?", "en", "CHANGE_MANDATE"),
    ("change our mandate so you can discount 5%?", "en", "CHANGE_MANDATE"),
    ("Is it ok to pledge the equipment?", "en", "PLEDGE_COLLATERAL"),
    ("What if we sign a personal guarantee?", "en", "SIGN_PERSONAL_GUARANTEE"),
    ("签署个人担保？", "zh", "SIGN_PERSONAL_GUARANTEE"),
    ("要不要签个人担保？", "zh", "SIGN_PERSONAL_GUARANTEE"),
    ("要不要抵押设备？", "zh", "PLEDGE_COLLATERAL"),
]


def security_kinds(rt) -> list[str]:
    return [e.kind.value for e in rt.store.security_events()]


@pytest.mark.parametrize("owner", [False, True], ids=["agent-key", "owner"])
@pytest.mark.parametrize(("text", "lang", "kind"), REQUESTS_AS_QUESTIONS)
def test_a_tier3_request_put_as_a_question_is_refused_logged_and_raises_its_event(client, rt, text, lang, kind, owner):
    n_ops, n_events = len(rt.store.operations()), len(rt.store.security_events())
    r = Chat(client, f"t3q-{abs(hash((text, owner))) % 10**8}", owner=owner).say(text, lang=lang)
    assert ops(r) == [(kind, "REFUSED")], r["reply"]
    assert [o.kind for o in rt.store.operations()[n_ops:]] == [kind]  # on the hash-chained operations log
    assert security_kinds(rt)[n_events:] == ["TIER3"], r["reply"]  # and the event is raised
    assert r["security_events"], r["reply"]
    assert r["intent"] == "OUT_OF_SCOPE"  # as the imperative is
    assert not r["awaiting_confirmation"] and SESSIONS.get(r["session_id"]).pending_plan is None


def test_the_owner_reply_still_answers_the_question_part(client, rt):
    r = Chat(client, "t3q-reply").say("Issue equity to cover the gap?")
    assert r["reply"].startswith("Refused: issue equity is a Tier-3 action")
    assert "Only you can decide it, outside FLOW." in r["reply"]
    assert "Owner equity or outside investor is on the funding menu for comparison only" in r["reply"]
    zh = Chat(client, "t3q-reply-zh").say("要不要签个人担保？", lang="zh")
    assert "执行器已拒绝并记录" in zh["reply"] and "只能由您在 FLOW 之外自行决定" in zh["reply"]


def test_the_agent_key_gets_the_plain_refusal_not_the_owner_guidance(client, rt):
    r = Chat(client, "t3q-agent", owner=False).say("Issue equity to cover the gap?")
    assert ops(r) == [("ISSUE_EQUITY", "REFUSED")]
    assert "funding menu" not in r["reply"] and "Only you can decide" not in r["reply"]


# information questions: the owner's are answered and write nothing; the agent key's are a request and log
INFORMATION = [
    ("Did anyone try to change our limits?", "en"),
    ("有人试图修改我们的限额吗？", "zh"),
    ("Has someone tried to lower the reserve?", "en"),
    ("Is equity an option?", "en"),
    ("增发股权是一个选项吗？", "zh"),
    ("Is a personal guarantee ever needed?", "en"),
    ("个人担保是什么意思？", "zh"),
    ("What is a personal guarantee?", "en"),
    ("什么是个人担保？", "zh"),
    ("Does the bank want collateral?", "en"),
]


@pytest.mark.parametrize(("text", "lang"), INFORMATION)
def test_an_owner_information_question_about_a_tier3_subject_writes_nothing(client, rt, text, lang):
    n_ops, n_events = len(rt.store.operations()), len(rt.store.security_events())
    r = Chat(client, f"t3i-{abs(hash(text)) % 10**8}").say(text, lang=lang)
    assert r["intent"] == "ASK_BOOKS" and ops(r) == [], r["reply"]
    assert len(rt.store.operations()) == n_ops and len(rt.store.security_events()) == n_events


@pytest.mark.parametrize(("text", "lang"), INFORMATION)
def test_the_same_information_question_from_the_agent_key_is_a_request_and_is_logged(client, rt, text, lang):
    n_events = len(rt.store.security_events())
    r = Chat(client, f"t3a-{abs(hash(text)) % 10**8}", owner=False).say(text, lang=lang)
    assert len(ops(r)) == 1 and ops(r)[0][1] == "REFUSED", r["reply"]
    assert security_kinds(rt)[n_events:] == ["TIER3"]


@pytest.mark.parametrize("text", [
    "Is equity an option? Issue it.",  # a second sentence may be the request
    "Did anyone try to change our limits? Raise the cap to 5%.",
    "Should we try pledging the equipment?",  # "try" is not an attempt by someone else
    "Is signing a personal guarantee a good idea?",
    "How do we pledge the equipment?",
])
def test_an_owner_question_that_proposes_something_is_not_information(text):
    assert not lx.tier3_is_information(text)


@pytest.mark.parametrize("text", [t for t, _ in INFORMATION])
def test_the_information_forms(text):
    assert lx.tier3_is_information(text)


def test_a_request_put_as_a_question_with_a_plan_waiting_leaves_the_plan_and_is_still_refused(client, rt):
    c = Chat(client, "t3q-pending")
    assert c.say("fund the gap")["awaiting_confirmation"]
    r = c.say("should we sign a personal guarantee?")
    assert ops(r) == [("SIGN_PERSONAL_GUARANTEE", "REFUSED")]
    assert SESSIONS.get("t3q-pending").pending_plan is not None
