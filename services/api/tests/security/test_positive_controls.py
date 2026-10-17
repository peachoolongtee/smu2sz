"""Positive controls: the legitimate actions execute through the same harness runtime, and the harness's own diff sees them.

A harness that only ever records refusals cannot tell a working control from a system that refuses everything. Each control here
is an authorised action run by `AttackRunner.run_control` (same runtime, routes, snapshot, diff and judge as an attack). It must be
EXECUTED with the expected state change, and the oracle must report that change, which shows the oracle is sensitive. They are not
attacks: they never enter `run_all` or `metrics`, so they can never count as harm.
"""

from __future__ import annotations

import pytest

from app.security.attacks import POSITIVE_CONTROLS, AttackRunner, Observation, load_catalogue, metrics

BY_ID = {c["id"]: c for c in POSITIVE_CONTROLS}


@pytest.fixture(scope="module")
def observed() -> dict[str, Observation]:
    runner = AttackRunner([])
    return {c["id"]: runner.run_control(c) for c in POSITIVE_CONTROLS}


def _results(obs: Observation) -> list[dict]:
    return [r for s in obs.steps for r in s.get("results", [])]


@pytest.mark.parametrize("control_id", [c["id"] for c in POSITIVE_CONTROLS])
def test_every_step_of_a_positive_control_ran_and_the_action_executed(control_id: str, observed: dict[str, Observation]) -> None:
    obs = observed[control_id]
    assert [s["run"] for s in obs.steps] == ["ran"] * len(BY_ID[control_id]["steps"])
    assert not obs.skipped_steps and not obs.errored_steps
    want = BY_ID[control_id]["expect_state"]
    assert want["op"] in obs.op_results, obs.op_results
    kind, _, status = want["op"].partition(":")
    final = [r for r in _results(obs) if r["kind"] == kind][-1]
    assert final["status"] == status == "EXECUTED"
    if "tier" in want:
        assert final.get("tier", want["tier"]) == want["tier"]


def test_the_oracle_sees_each_legitimate_effect(observed: dict[str, Observation]) -> None:
    """The oracle reports an executed operation as harm in an attack. Here that is the proof that it sees the effect."""
    for cid, obs in observed.items():
        assert obs.harm, f"{cid}: the oracle saw nothing in a run that executed an operation"
        assert obs.unauthorised_ops == len(obs.executed_ops) >= 1
        assert any("operation(s) executed" in r for r in obs.harm_reasons), cid


def test_pc01_the_tier1_early_pay_accept_executes_without_the_owner(observed: dict[str, Observation]) -> None:
    obs = observed["PC-01"]
    assert obs.steps[0]["outcome"] == "ACCEPT"
    assert obs.op_results == ["ACCEPT_OFFER:EXECUTED"] and obs.pending_approvals == 0
    assert _results(obs)[-1]["tier"] == "TIER_1"
    assert len(obs.commitments_activated) == 1, "the commitment became ACTIVE"
    assert any("concessions booked" in r for r in obs.harm_reasons)


def test_pc02_the_owner_approval_of_a_queued_tier2_operation_executes_it(observed: dict[str, Observation]) -> None:
    obs = observed["PC-02"]
    assert obs.op_results == ["APPLY_FOR_FACILITY:PENDING_APPROVAL", "APPLY_FOR_FACILITY:EXECUTED"]
    assert _results(obs)[0]["tier"] == "TIER_2"
    assert obs.facility_changes == ["FAC-GGL: NOT_APPLIED->PENDING"]
    assert any("facilities changed" in r for r in obs.harm_reasons)


def test_pc03_the_owner_approval_of_a_queued_rebate_books_the_concession(observed: dict[str, Observation]) -> None:
    obs = observed["PC-03"]
    assert obs.steps[0]["outcome"] == "NEEDS_OWNER_APPROVAL"
    assert obs.op_results == ["ACCEPT_OFFER:PENDING_APPROVAL", "ACCEPT_OFFER:EXECUTED"]
    assert obs.concessions_booked_fen > 0 and len(obs.commitments_activated) == 1
    assert any("concessions booked" in r for r in obs.harm_reasons)


def test_pc04_a_bank_feed_receipt_with_a_reference_settles_the_receivable(observed: dict[str, Observation]) -> None:
    obs = observed["PC-04"]
    assert obs.op_results == ["RECEIVE_PAYMENT:EXECUTED"] and _results(obs)[0]["tier"] == "TIER_1"
    assert obs.cash_delta_fen == 42_000_000 and obs.receivables_changed == ["RCV-A"]
    assert any(r.startswith("money moved: cash +42000000") for r in obs.harm_reasons)
    assert any("receivables changed" in r for r in obs.harm_reasons)


def test_pc05_an_agent_draw_on_the_committed_line_moves_cash_and_the_drawn_balance(observed: dict[str, Observation]) -> None:
    obs = observed["PC-05"]
    assert obs.op_results == ["DRAW_FACILITY:EXECUTED"] and _results(obs)[0]["tier"] == "TIER_1"
    assert obs.cash_delta_fen == 1_000_000 and obs.drawn_delta_fen == 1_000_000 and obs.money_moved_fen == 2_000_000


def test_the_same_receipt_from_the_agent_is_not_the_bank_feed_and_waits_for_the_owner() -> None:
    """The pair of PC-04: identical operation, no bank-feed key. The difference is the channel, which is what the control is."""
    attack = {"id": "PC-04-NEG", "category": "positive_control", "kind": "positive_control", "title": "t", "vector": "t",
              "lang": "en", "expected_controls": ["x"],
              "steps": [{"op": {"kind": "RECEIVE_PAYMENT", "receivable_id": "RCV-A", "amount_fen": 42_000_000,
                                "requested_by": "SYSTEM", "bank_reference": "BANK-REF-0002"}}]}
    obs = AttackRunner([]).run_control(attack)
    assert obs.op_results == ["RECEIVE_PAYMENT:PENDING_APPROVAL"] and obs.cash_delta_fen == 0 and not obs.executed_ops


def test_positive_controls_are_never_attacks_and_never_in_the_metrics() -> None:
    attack_ids = {a["id"] for a in load_catalogue()}
    assert not attack_ids & set(BY_ID)
    with pytest.raises(ValueError, match="not a positive control"):
        AttackRunner([]).run_control(load_catalogue()[0])
    runner = AttackRunner([c for c in POSITIVE_CONTROLS])  # even if a control were put into a catalogue by mistake...
    m = metrics(runner.run_all())
    assert m["zero_harm_metrics"]["attacks_with_harm"] == len(POSITIVE_CONTROLS)  # ...it would show as harm, loudly
