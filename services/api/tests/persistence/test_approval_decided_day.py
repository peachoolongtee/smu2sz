"""The approval record keeps the clock day the owner decided it (both stores, G1)."""

from __future__ import annotations

from tests.persistence.test_store_contract import _op


def test_an_approval_keeps_the_day_it_was_decided(store):
    a1 = store.add_approval(_op(1)[3], "Tier 2")
    a2 = store.add_approval(_op(2)[3], "Tier 2")
    a3 = store.add_approval(_op(3)[3], "Tier 2")
    assert store.get_approval(a1).decided_day is None  # still pending
    assert store.decide_approval(a1, True, "OWNER", 34).decided_day == 34
    assert store.decide_approval(a2, False, "OWNER", 0).decided_day == 0  # day 0 is a day, not "unset"
    assert store.decide_approval(a3, True, "OWNER").decided_day is None  # a caller that gives no day
    assert [a.decided_day for a in store.approvals()] == [34, 0, None]
    assert store.get_approval(a1).decided_day == 34
