from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.counterparties import BuyerDecision, BuyerResponse, negotiate
from app.counterparties.negotiation import BUYER_ROUNDS_ENDED, SUPPLIER_WITHDREW
from app.domain.fixtures import golden_values
from app.domain.models import CounterProposal, ObligationType, Outcome
from tests.counterparties.builders import option_a, option_b

API_DIR = Path(__file__).resolve().parents[2]


def resend_option_a(_: BuyerResponse) -> CounterProposal:
    return option_a()


def test_scene1_accommodating_buyer_accepts_option_a_in_round_1() -> None:
    t = negotiate([option_a(), option_b()], "BUYER-1", resend_option_a)
    assert t.outcome is Outcome.ACCEPT
    assert t.accepted_counter_id == "CTR-A"
    assert t.rounds_used == 1
    assert [m.sender for m in t.messages] == ["SUPPLIER", "SUPPLIER", "BUYER"]
    assert t.messages[-1].decision is BuyerDecision.ACCEPT


def test_scene2_hardline_is_no_deal_after_exactly_three_rounds() -> None:
    t = negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", resend_option_a)
    assert t.outcome is Outcome.NO_DEAL
    assert t.accepted_counter_id is None
    assert t.rounds_used == 3
    assert [r.round for r in t.rounds] == [1, 2, 3]
    assert [r.response.decision for r in t.rounds] == [
        BuyerDecision.COUNTER,
        BuyerDecision.COUNTER,
        BuyerDecision.REJECT,
    ]
    assert t.ended_reason == BUYER_ROUNDS_ENDED
    assert t.rounds[0].supplier_counter_ids == ["CTR-A", "CTR-B"]


def test_scene2_hardline_counters_move_toward_but_never_into_the_feasible_region() -> None:
    gv = golden_values()
    break_even_bp = gv["break_even_discount_bp"]  # 88: above it early pay costs more than financing
    t = negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", resend_option_a)
    rates = []
    for r in t.rounds:
        if r.response.decision is not BuyerDecision.COUNTER:
            continue
        by_type = {o.type: o for o in r.response.obligations}
        disc = by_type[ObligationType.IMMEDIATE_DISCOUNT]
        assert disc.rate_bp is not None and disc.rate_bp > break_even_bp
        # a 15-day extension with no price adjustment is ¥22,455.62 of forward concession > ¥5,000 cap
        ext = by_type[ObligationType.TERMS_EXTENSION]
        assert ext.days_delta == 15
        assert ObligationType.PRICE_ADJUSTMENT not in by_type
        assert gv["extension_committed_12m"] > gv["concession_cap"]
        rates.append(disc.rate_bp)
    assert len(rates) == 2 and rates[0] > rates[1]


def test_scene2_transcript_is_deterministic() -> None:
    a = negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", resend_option_a)
    b = negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", resend_option_a)
    assert a.model_dump_json() == b.model_dump_json()
    assert a.transcript_hash == b.transcript_hash


_HASH_SCRIPT = """
from app.counterparties import negotiate
from tests.counterparties.builders import option_a, option_b
print(negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", lambda r: option_a()).transcript_hash)
"""


def test_scene2_transcript_hash_is_stable_across_processes() -> None:
    hashes = set()
    for seed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run(
            [sys.executable, "-c", _HASH_SCRIPT], cwd=API_DIR, env=env, capture_output=True, text=True, check=True
        )
        hashes.add(out.stdout.strip())
    assert len(hashes) == 1
    assert hashes == {negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", resend_option_a).transcript_hash}


def test_supplier_withdrawing_ends_in_no_deal() -> None:
    t = negotiate([option_a()], "BUYER-1-HARDLINE", lambda _: None)
    assert t.outcome is Outcome.NO_DEAL
    assert t.rounds_used == 1
    assert t.ended_reason == SUPPLIER_WITHDREW


def test_supplier_improving_in_round_2_can_close() -> None:
    def improve(resp: BuyerResponse) -> CounterProposal:
        # accept the buyer's own counter terms as a new supplier counter
        return CounterProposal(
            id="CTR-C",
            label="Option C",
            text="Supplier counter C.",
            obligations=list(resp.obligations),
            supplier_cost_fen=0,
            rationale="",
            formula="",
        )

    t = negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", improve)
    assert t.outcome is Outcome.ACCEPT and t.accepted_counter_id == "CTR-C" and t.rounds_used == 2


def test_supplier_next_sees_only_the_public_response() -> None:
    seen: list[object] = []

    def spy(resp: BuyerResponse) -> CounterProposal:
        seen.append(resp)
        return option_a()

    negotiate([option_a(), option_b()], "BUYER-1-HARDLINE", spy)
    assert len(seen) == 2 and all(isinstance(s, BuyerResponse) for s in seen)


def test_negotiation_needs_a_counter() -> None:
    with pytest.raises(ValueError):
        negotiate([], "BUYER-1", resend_option_a)


def test_transcript_does_not_carry_supplier_private_fields() -> None:
    private = option_a(supplier_cost_fen=777_777, rationale="PRIVATE-RATIONALE", formula="PRIVATE-FORMULA")
    t = negotiate([private], "BUYER-1-HARDLINE", lambda _: None)
    dumped = t.model_dump_json()
    assert "PRIVATE-RATIONALE" not in dumped and "PRIVATE-FORMULA" not in dumped and "777777" not in dumped
