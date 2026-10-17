"""SEC-22 (security register): protected values written in less common spellings are still blocked.

Before, the egress guard missed four-digit and Indian groupings, dot/apostrophe/underscore separators, a bare "m", an exponent, the
"w" (万) and 千 suffixes, per mille, "个点"/"points", and a coverage ratio written as a percentage (security review of 14 Oct, r7)."""

from __future__ import annotations

import pytest

from app.egress.protected import scan
from tests.egress.helpers import golden_set

LEAKS = [
    ("Our reserve is 30,0000 yuan.", "mandate.min_cash"),
    ("Our reserve is ¥3,00,000.", "mandate.min_cash"),
    ("Our reserve is 300.000 yuan.", "mandate.min_cash"),
    ("Our reserve is 300'000 yuan.", "mandate.min_cash"),
    ("Our reserve is 300_000 yuan.", "mandate.min_cash"),
    ("The floor is 0.3m.", "mandate.min_cash"),
    ("floor 3e5", "mandate.min_cash"),
    ("我们的底线是30w", "mandate.min_cash"),
    ("Cash is 400千元.", "state.cash"),
    ("Max discount 15‰", "mandate.max_immediate_discount"),
    ("最多让千分之十五", "mandate.max_immediate_discount"),
    ("最多一点五个点", "mandate.max_immediate_discount"),
    ("at most 1.5 points off", "mandate.max_immediate_discount"),
    ("DSCR at least 125%", "mandate.min_dscr"),
]


@pytest.mark.parametrize(("text", "label"), LEAKS)
def test_a_protected_value_in_another_spelling_is_blocked(text: str, label: str) -> None:
    assert label in {leak.label for leak in scan(text, golden_set(), recipient_id="BUYER-1")}


@pytest.mark.parametrize("text", [
    "Thank you. We will confirm by day 30.",
    "Invoice INV-2026-001 is due in 45 days.",
    "Please pay within 30 days of delivery.",
    "We received your message of 3 Oct.",
    "Version 2.1 of the template.",
])
def test_ordinary_text_still_passes(text: str) -> None:
    assert scan(text, golden_set(), recipient_id="BUYER-1") == []
