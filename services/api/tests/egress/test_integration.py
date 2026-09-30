"""The guard on real outbound paths available today: negotiation transcripts and buyer replies.

Also shows how a caller hands buyer reservation values to the guard (`reservation_private_values`)
and checks that the egress package depends on `app.domain` only.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.counterparties import negotiate
from app.counterparties.profiles import get_profile, load_buyer_profiles
from app.egress import OWNER_ID, ProtectedSet, allowed_for_counter, assert_no_leak, guard
from tests.counterparties.builders import option_a, option_b
from tests.egress.helpers import golden, reservation_private_values

PROFILES = sorted(load_buyer_profiles())
EGRESS_DIR = Path(__file__).resolve().parents[2] / "app" / "egress"


def _set_with_reservations(*profile_ids: str) -> ProtectedSet:
    """Protect the reservation of the buyer(s) in this conversation.

    Pass only the buyers actually talking: another buyer's reservation can share a number with an
    ordinary proposal (BUYER-2 proposing a 0.80% rebate is not BUYER-1's 0.80% floor).
    """
    state, mandate = golden()
    extra = [pv for pid in profile_ids for pv in reservation_private_values(get_profile(pid))]
    return ProtectedSet.build(state, mandate, extra_private=extra)


@pytest.mark.parametrize("profile_id", PROFILES)
def test_negotiation_transcripts_pass_the_guard_both_ways(profile_id: str) -> None:
    ps = _set_with_reservations(profile_id)
    counters = {c.id: c for c in (option_a(), option_b())}
    buyer = get_profile(profile_id).counterparty_id
    for nxt in (lambda _r: option_a(), lambda _r: option_b(), lambda _r: None):
        t = negotiate(list(counters.values()), profile_id, nxt)
        for m in t.messages:
            texts = [m.text_en, m.text_zh or ""]
            if m.sender == "SUPPLIER":
                # supplier -> buyer: only the counter's own values may appear
                allow = allowed_for_counter(counters[m.counter_id]) if m.counter_id in counters else []
                assert_no_leak(texts, ps, buyer, allow)
            else:
                # buyer -> supplier: the buyer's hidden reservation must never surface
                assert_no_leak(texts, ps, OWNER_ID)


def test_a_reply_that_states_a_reservation_is_blocked_before_it_reaches_the_owner() -> None:
    ps = _set_with_reservations("BUYER-1")
    result = guard("Our floor is 0.80% early-pay discount and we fund at 4.2%.", ps, recipient_id=OWNER_ID, day=0)
    assert not result.ok
    labels = {x.label for x in result.leaks}
    assert {"reservation.BUYER-1.min_early_pay_discount", "reservation.BUYER-1.funding_cost"} <= labels


def test_reservation_values_are_hidden_from_everyone() -> None:
    for pv in reservation_private_values(get_profile("BUYER-1")):
        assert not pv.entitled(OWNER_ID) and not pv.entitled("BUYER-1") and not pv.entitled("BUYER-2")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


def test_egress_depends_on_domain_only() -> None:
    files = sorted(EGRESS_DIR.rglob("*.py"))
    assert files
    for f in files:
        internal = {n for n in _imports(f) if n.startswith("app.")}
        assert all(n.startswith(("app.domain", "app.egress")) for n in internal), (f.name, internal)


def test_assert_no_leak_names_labels_never_values() -> None:
    ps = _set_with_reservations()
    assert_no_leak("Round 1. We accept Option A as proposed.", ps, "BUYER-1")
    with pytest.raises(AssertionError) as exc:
        assert_no_leak(["Round 1.", "Our reserve is ¥300,000."], ps, "BUYER-1")
    msg = str(exc.value)
    assert "text #1" in msg and "mandate.min_cash" in msg and "300" not in msg
