"""A 2,000-character outbound message is scanned in well under 10 ms."""

from __future__ import annotations

import time

from app.egress import allowed_for_counter, guard, scan
from tests.counterparties.builders import OPTION_A_TEXT, OPTION_B_TEXT, option_a
from tests.egress.helpers import buyer_b_set

CHUNK = (
    OPTION_A_TEXT + " " + OPTION_B_TEXT + " 第2轮。我方接受本发票不超过¥211,800的部分以0.85%提前结算，账期维持45天。"
    " Invoice RCV-A (¥420,000.00) is due on day 32, 2026-11-02. Round 3 of 3; 12 invoices a year. "
)
MESSAGE = (CHUNK * (2000 // len(CHUNK) + 1))[:2000]


def _best_ms(fn: object, runs: int = 30) -> float:
    best = float("inf")
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()  # type: ignore[operator]
        best = min(best, (time.perf_counter() - t0) * 1000)
    return best


def test_scan_of_a_2000_char_message_is_under_10ms() -> None:
    ps = buyer_b_set()
    allow = allowed_for_counter(option_a())
    assert len(MESSAGE) == 2000
    scan(MESSAGE, ps, recipient_id="BUYER-1", allow=allow)  # warm the regex cache
    assert _best_ms(lambda: scan(MESSAGE, ps, recipient_id="BUYER-1", allow=allow)) < 10.0


def test_guard_of_a_leaking_2000_char_message_is_under_10ms() -> None:
    ps = buyer_b_set()
    leaking = MESSAGE[:1900] + " Our minimum reserve is ¥300,000; Buyer B pays in 60 days."
    result = guard(leaking, ps, recipient_id="BUYER-1", day=0)
    assert not result.ok
    assert _best_ms(lambda: guard(leaking, ps, recipient_id="BUYER-1", day=0)) < 10.0
