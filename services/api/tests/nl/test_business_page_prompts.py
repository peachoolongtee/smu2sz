"""Wave 6 (wayfinder #35) and wave 4 part A (wayfinder #65): the page prompts the web offers beside "Ask FLOW" (apps/web/lib/chat-prompts.ts) are sentences the
rules already understand. Keep this list in step with that file: a prompt the rules cannot read must not be offered."""

from __future__ import annotations

import pytest

from tests.nl.conftest import Chat

PROMPTS = [
    # Home
    ("What changed today?", "CHANGES"), ("今天有什么变化？", "CHANGES"),
    ("What needs my attention?", "SHOW_ALERTS"), ("有什么需要我关注的？", "SHOW_ALERTS"),
    # "Do we have enough cash this month?" is a top owner question (LIQ-01): the answer module leads with the answer
    ("Do we have enough cash this month?", "ASK_BOOKS"), ("会不会缺钱？", "SHOW_STATUS"),
    ("What should I deal with today?", "SHOW_ALERTS"), ("今天有什么需要我处理的？", "SHOW_ALERTS"),
    # Deals
    ("Why are we countering this?", "EXPLAIN"), ("为什么要还价？", "EXPLAIN"),
    ("What if I accept their original terms?", "WHAT_IF"), ("如果我接受对方的原始条款会怎样？", "WHAT_IF"),
    ("Why is Option A cheaper?", "EXPLAIN"), ("为什么方案A更便宜？", "EXPLAIN"),
    ("What are we waiting for?", "SHOW_STATUS"), ("我们在等什么？", "SHOW_STATUS"),
    ("What would happen if I accepted?", "WHAT_IF"), ("如果我接受会怎样？", "WHAT_IF"),
    # Cash & funding
    ("Why did FLOW choose this plan?", "EXPLAIN"), ("FLOW 为什么选这个方案？", "EXPLAIN"),
    ("When does the money arrive?", "SHOW_STATUS"), ("资金什么时候到账？", "SHOW_STATUS"),
    ("What happens if this payment is late?", "WHAT_IF"), ("如果这笔款项延迟会怎样？", "WHAT_IF"),
    ("Why is this the cheapest plan?", "EXPLAIN"), ("为什么这是最便宜的方案？", "EXPLAIN"),
    ("Compare our financing options", "COMPARE_FINANCING"), ("比较一下融资方案", "COMPARE_FINANCING"),
    # Receivables
    ("Who should I chase first?", "RECONCILE"), ("应该先催哪一家？", "RECONCILE"),
    ("What is overdue?", "RECONCILE"), ("哪些款项逾期了？", "RECONCILE"),
    ("Which payments are late?", "RECONCILE"), ("哪些回款没到？", "RECONCILE"),
    ("Who owes us money?", "SHOW_STATUS"), ("谁欠我们钱？", "SHOW_STATUS"),
]


@pytest.mark.parametrize(("text", "intent"), PROMPTS)
def test_a_page_prompt_is_read_by_the_rules(client, text, intent):
    r = Chat(client, "t-page-prompt").say(text)
    assert r["intent"] == intent
    assert r["operations"] == []  # a question: nothing runs
