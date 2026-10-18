"""Ask FLOW answers a live stress test found wrong or missing (18 Oct 2026), on the golden demo books, in English and Chinese.

Every figure asserted here is read back from the engine or the books (never typed in), and every question is asked through POST /nl
so the routing (rules.py, ask.py) is under test as well as the wording.
"""

from __future__ import annotations

import re

import pytest

from app.nl.answers import question_ids
from app.nl.answers.answers import W, op_words
from app.nl.answers.metrics import Reading
from tests.nl.conftest import OWNER, Chat

CJK = re.compile(r"[一-鿿]")


def say(client, text: str, n: int = 0) -> dict:
    return Chat(client, f"rule-answers-{abs(hash(text))}-{n}").say(text)


def no_ids(reply: str) -> None:
    assert not re.search(r"RCV-|FAC-|BUYER-|BANK-|PLATFORM-|APR-|SIGN_PERSONAL|OPEN_BOOKS|ADD_CUSTOMER", reply), reply


# ---------------------------------------------------------------- the audit log (item 5)

AUDIT_EN = ["Is the audit log intact?", "Can I trust the log?"]
AUDIT_ZH = ["审计日志完整吗？", "审计链校验通过吗？"]
REFUSED_EN = ["Has anything been refused or blocked?", "Were any operations refused?"]
REFUSED_ZH = ["有没有被拒绝或拦截的操作？", "有操作被拦下来吗？"]


def log_some_operations(client) -> None:
    """One operation that ran (the clock moved) and one refused (a Tier-3 request, which also raises a security event)."""
    assert client.post("/clock/advance", json={"to_day": 1}, headers=OWNER).status_code == 200
    Chat(client, "audit-setup").say("sign a personal guarantee for the loan")


@pytest.mark.parametrize("text", AUDIT_EN + AUDIT_ZH)
def test_the_audit_question_names_each_operation_and_keeps_the_chain_check(client, rt, text: str) -> None:
    log_some_operations(client)
    zh = bool(CJK.search(text))
    reply = say(client, text)["reply"]
    assert "one other operation" not in reply and "另一项操作" not in reply
    assert (CJK.search(reply) is not None) == zh, reply
    no_ids(reply)
    assert ("哈希链校验通过" if zh else "hash chain verifies") in reply
    assert ("将日期向前推进" if zh else "moved the clock forward") in reply  # the operation that ran, by name
    assert ("签署个人担保" if zh else "signing a personal guarantee") in reply  # the one refused, by name
    assert (re.search(r"被拒绝 1 项", reply) and re.search(r"待您审批 0 项", reply) and re.search(r"安全事件 1 起", reply)) if zh else (
        "1 refused" in reply and "0 waiting for your approval" in reply and "one security event" in reply), reply


@pytest.mark.parametrize("text", REFUSED_EN + REFUSED_ZH)
def test_the_refused_question_leads_with_the_refusal_and_still_names_everything(client, rt, text: str) -> None:
    log_some_operations(client)
    zh = bool(CJK.search(text))
    reply = say(client, text)["reply"]
    assert reply.startswith("有：1 项操作被拒绝" if zh else "Yes: one operation was refused"), reply
    assert ("签署个人担保" if zh else "signing a personal guarantee") in reply
    assert ("哈希链校验通过" if zh else "hash chain verifies") in reply
    assert "one other operation" not in reply


@pytest.mark.parametrize("text", [REFUSED_EN[0], REFUSED_ZH[0]])
def test_nothing_refused_says_so_on_a_fresh_book(client, rt, text: str) -> None:
    reply = say(client, text)["reply"]
    assert reply.startswith("没有操作被拒绝或拦截" if CJK.search(text) else "Nothing has been refused or blocked"), reply


def test_an_operation_kind_without_a_verb_is_named_by_its_owner_words(rt) -> None:
    for lang, expected in (("en", "books opened"), ("zh", "账簿已开立")):
        w = W(Reading.of(type("C", (), {"store": rt.store, "day": rt.day, "owner_key_hex": rt.owner_key_hex})()), lang)
        assert op_words(w, "OPEN_BOOKS", 0, None) == expected
    w = W(Reading.of(type("C", (), {"store": rt.store, "day": rt.day, "owner_key_hex": rt.owner_key_hex})()), "en")
    assert op_words(w, "NOT_A_KIND", 0, None) == "ran one other operation"


def test_the_beyond_top30_questions_are_not_among_the_top_30() -> None:
    assert "ACT-05" not in question_ids() and "ACT-04" not in question_ids()
