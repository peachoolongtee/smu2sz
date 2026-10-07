"""Wave 6 (wayfinder #35): the page prompts the web offers beside "Ask FLOW" (apps/web/lib/chat-prompts.ts) are sentences the
rules already understand. Keep this list in step with that file: a prompt the rules cannot read must not be offered."""

from __future__ import annotations

import pytest

from tests.nl.conftest import Chat

PROMPTS = [
    # Home
    ("Do we have enough cash this month?", "SHOW_STATUS"), ("会不会缺钱？", "SHOW_STATUS"),
    ("What should I deal with today?", "SHOW_ALERTS"), ("今天有什么需要我处理的？", "SHOW_ALERTS"),
    # Deals
    ("Why are we countering this?", "EXPLAIN"), ("为什么要还价？", "EXPLAIN"),
    ("What would happen if I accepted?", "WHAT_IF"), ("如果我接受会怎样？", "WHAT_IF"),
    # Cash & funding
    ("Why is this the cheapest plan?", "EXPLAIN"), ("为什么这是最便宜的方案？", "EXPLAIN"),
    ("Compare our financing options", "COMPARE_FINANCING"), ("比较一下融资方案", "COMPARE_FINANCING"),
    # Receivables
    ("Which payments are late?", "RECONCILE"), ("哪些回款没到？", "RECONCILE"),
    ("Who owes us money?", "SHOW_STATUS"), ("谁欠我们钱？", "SHOW_STATUS"),
]


@pytest.mark.parametrize(("text", "intent"), PROMPTS)
def test_a_page_prompt_is_read_by_the_rules(client, text, intent):
    r = Chat(client, "t-page-prompt").say(text)
    assert r["intent"] == intent
    assert r["operations"] == []  # a question: nothing runs
