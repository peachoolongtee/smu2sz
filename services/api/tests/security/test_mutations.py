"""Mutation tests: switch one control off and run a few catalogue attacks through the real runner.

The harness is only evidence if it can fail. For each control below one function is monkeypatched off (and restored by the
fixture), a small subset of the attack catalogue runs through the real runner, and the runner must report either harm or the
specific control that did not fire (`CONTROL_NOT_SEEN`: the evidence the entry names was missing). Where it reports neither,
that is a finding about the catalogue, and the test says so in a comment.

Two controls turned out to be backed by a second, independent layer: with the tier forced to Tier 1 the Tier-3 operations are
still refused by their own handlers, and with the terms-hash check off a Tier-2 acceptance still waits for the owner. The runner
then shows the control missing, not harm; the Tier-1 catalogue attack TC-04 does show harm.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.models import Tier
from app.security.attacks import AttackRunner, NlAttackRunner, Observation, load_catalogue, nl_catalogue

API = {a["id"]: a for a in load_catalogue()}
NL = {a["id"]: a for a in nl_catalogue()}


def run_api(*ids: str) -> dict[str, Observation]:
    return {o.id: o for o in AttackRunner([API[i] for i in ids]).run_all()}


def run_nl(*ids: str) -> dict[str, Observation]:
    return {o.id: o for o in NlAttackRunner([NL[i] for i in ids]).run_all()}


def harmed(obs: dict[str, Observation]) -> set[str]:
    return {i for i, o in obs.items() if o.harm}


def not_defended(obs: dict[str, Observation]) -> set[str]:
    return {i for i, o in obs.items() if not o.defended}


# ---------------------------------------------------------------- the unmutated runs are clean (the control group)

TIER_IDS = ("PE-01", "PE-05", "PE-07", "PE-08", "PE-12", "PE-13", "PE-14", "PE-16", "PE-17")
OWNER_IDS = ("PE-01", "PE-02", "PE-03", "PE-04", "PE-08", "PE-09", "PE-11", "MX-05", "RX-06", "FR-15", "DOC-03", "DOC-04")
SIG_IDS = ("RV-04", "RV-05")
HASH_IDS = ("TC-01", "TC-03", "RP-08", "EX-01")  # Tier-2 rebates: the owner queue stands behind the hash check
FORBID_IDS = ("FL-06", "PE-06", "PE-19", "SE-04")


def test_without_a_mutation_every_subset_is_defended() -> None:
    """If these were not clean, a mutation test would prove nothing."""
    for ids in (TIER_IDS, OWNER_IDS, SIG_IDS, HASH_IDS, FORBID_IDS, ("TC-04",)):
        obs = run_api(*ids)
        assert not not_defended(obs), {i: (o.outcome(), o.harm_reasons, o.expectation_failures) for i, o in obs.items() if not o.defended}


# ---------------------------------------------------------------- 1. the executor's tier computation


def test_tier_forced_to_tier1_makes_privilege_escalation_attacks_show_harm(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.operations.executor import Executor

    monkeypatch.setattr(Executor, "_tier", lambda self, ctx: Tier.TIER_1)
    obs = run_api(*TIER_IDS)
    # Tier-2 work runs without the owner: the facility application and the in-process AddFacility execute.
    assert {"PE-07", "PE-08", "PE-16"} <= harmed(obs), {i: o.outcome() for i, o in obs.items()}
    assert "facilities added: ['FAC-FASTCAPITAL']" in obs["PE-16"].harm_reasons[1]
    assert any("APPLY_FOR_FACILITY" in r for r in obs["PE-07"].harm_reasons)
    # Tier-3 operations are still refused by their own handlers (a second layer), so there is no harm; but the runner
    # sees the Tier-3 control missing in every one of them: the refusal code the entry names did not appear.
    for i in ("PE-12", "PE-13", "PE-01", "PE-17"):
        assert not obs[i].defended, (i, obs[i].outcome())
        assert obs[i].outcome() in ("HARM", "CONTROL_NOT_SEEN")
    assert any("TIER3" in f for f in obs["PE-12"].expectation_failures)


# ---------------------------------------------------------------- 2. the owner check in app/api/auth.py


def test_owner_check_bypassed_makes_owner_route_attacks_show_harm_or_a_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import auth

    monkeypatch.setattr(auth, "is_owner", lambda token: True)
    obs = run_api(*OWNER_IDS)
    assert harmed(obs) >= {"PE-03", "PE-04", "PE-08", "PE-09", "PE-11", "FR-15", "DOC-04", "MX-05", "RX-06", "DOC-03"}, \
        {i: o.outcome() for i, o in obs.items()}
    # the read routes answer an outsider with the books: leaks, not executions
    assert obs["MX-05"].read_api_leaks and obs["RX-06"].read_api_leaks and obs["DOC-03"].read_api_leaks
    # an approval decided by a caller who is not the owner executes
    assert any("APPLY_FOR_FACILITY" in r for r in obs["PE-08"].harm_reasons)
    # a wrong owner token that is now believed makes the AddFacility a Tier-2 request, not a Tier-3 refusal: the runner
    # does not see harm (it only queues) but sees the control missing
    for i in ("PE-01", "PE-02"):
        assert not obs[i].defended


# ---------------------------------------------------------------- 3. the egress guard


def _leak_into_the_instruction_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """An upstream fault: the fixed refusal sentence carries the reserve floor."""
    import app.nl.offers as nl_offers

    monkeypatch.setattr(nl_offers, "INSTRUCTION_REFUSAL", nl_offers.INSTRUCTION_REFUSAL + " Our cash floor is ¥300,000.00.")


def _guard_scans_find_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """egress.scan returns no hits where the product calls it. The harness's own oracle uses `app.egress.scan` itself and
    is left alone, so a leak that gets through is still seen."""
    import importlib

    # `app.egress.guard` the module, not the function of the same name that the package re-exports
    for name in ("app.egress.guard", "app.nl.offers", "app.api.agent_view"):
        monkeypatch.setattr(importlib.import_module(name), "scan", lambda *a, **k: [])


def test_egress_scan_returning_nothing_alone_is_invisible_to_the_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """FINDING. With the product's scan emptied, no exfiltration attack shows a leak: the replies are fixed templates that
    never carry a protected value, so the guard is the last line and nothing in the catalogue pushes a value at it. The
    catalogue cannot tell that the guard is gone. (`test_egress_guard_off_with_a_leaking_template_shows_a_leak` shows the
    harness does see a leak once something upstream produces one.)"""
    _guard_scans_find_nothing(monkeypatch)
    obs = run_nl("NL-CX01", "NL-CX06", "NL-CX14", "NL-CX14K", "NL-CI01", "NL-CX16")
    obs.update(run_api("MX-01", "MX-04", "RX-01", "CB-02"))
    assert harmed(obs) == set(), harmed(obs)


def test_egress_guard_on_blocks_a_leaking_template(monkeypatch: pytest.MonkeyPatch) -> None:
    _leak_into_the_instruction_refusal(monkeypatch)
    obs = run_nl("NL-CI01", "NL-CI02", "NL-CI05")
    assert not harmed(obs), {i: o.harm_reasons for i, o in obs.items()}
    assert all(not o.leaks for o in obs.values())


def test_egress_guard_off_with_a_leaking_template_shows_a_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    _leak_into_the_instruction_refusal(monkeypatch)
    _guard_scans_find_nothing(monkeypatch)
    obs = run_nl("NL-CI01", "NL-CI02", "NL-CI05")
    assert harmed(obs) == {"NL-CI01", "NL-CI02", "NL-CI05"}, {i: o.outcome() for i, o in obs.items()}
    assert all("mandate.min_cash" in o.leaks for o in obs.values()), {i: o.leaks for i, o in obs.items()}


# ---------------------------------------------------------------- 4. mandate signature verification


def test_signature_verification_disabled_makes_the_forged_mandate_attacks_show_harm(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.mandate import validity

    monkeypatch.setattr(validity, "verify_signature", lambda mandate, trusted=None: True)
    obs = run_api(*SIG_IDS)
    assert harmed(obs) == {"RV-04", "RV-05"}, {i: o.outcome() for i, o in obs.items()}
    for o in obs.values():
        assert any("DRAW_FACILITY" in r for r in o.harm_reasons) and o.drawn_delta_fen == 1_000_000


# ---------------------------------------------------------------- 5. the terms-hash and nonce check


def test_terms_hash_check_on_refuses_the_tier1_changed_terms_attack() -> None:
    """TC-04: a Tier-1 early-pay acceptance, presented after the buyer revised its terms, under the old nonce."""
    obs = run_api("TC-04")["TC-04"]
    assert obs.defended and "TERMS_CHANGED" in obs.refusal_codes and not obs.harm
    assert obs.steps[-1]["revised_terms_hash_differs"] is True


def test_terms_hash_check_disabled_makes_the_tier1_changed_terms_attack_show_harm(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.operations import executor

    monkeypatch.setattr(executor, "check_acceptance", lambda *a, **k: [])
    obs = run_api("TC-04")["TC-04"]
    assert obs.harm and obs.executed_ops == ["ACCEPT_OFFER"], (obs.outcome(), obs.harm_reasons)
    assert not obs.defended


def test_terms_hash_check_disabled_is_seen_by_the_catalogue_only_as_a_missing_control(monkeypatch: pytest.MonkeyPatch) -> None:
    """FINDING. TC-01 and TC-03 (and RP-08, EX-01) change the hash, nonce or day of a rebate acceptance. A rebate is Tier 2, so
    with the check off it is queued for the owner instead of executed: no harm. The runner reports the control missing
    (TERMS_CHANGED / REPLAY / COMMITMENT_EXPIRED not observed), not harm. TC-04 is the Tier-1 case (an early-pay acceptance)
    and is the one that shows harm with the check off (test above)."""
    from app.operations import executor

    monkeypatch.setattr(executor, "check_acceptance", lambda *a, **k: [])
    obs = run_api(*HASH_IDS)
    assert not harmed(obs)
    assert not_defended(obs) == set(HASH_IDS), {i: o.outcome() for i, o in obs.items()}
    assert all(o.outcome() == "CONTROL_NOT_SEEN" for o in obs.values())
    assert any("TERMS_CHANGED" in f for f in obs["TC-01"].expectation_failures)
    assert obs["TC-01"].pending_approvals == 1  # the owner queue is what held


# ---------------------------------------------------------------- 6. strict typed operations (extra fields forbidden)


def test_extra_fields_tolerated_makes_the_differential_attacks_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /operations answers 422 for an unknown field and names no field. FL-06, PE-06, PE-19 and SE-04 therefore send the same
    body twice, with and without the forbidden field, and require 422 for the first and the executor's answer for the second. With
    the route silently dropping the unknown fields the first no longer answers 422: none of the four is defended, and the
    induced transfers (a draw "to" a destination) execute."""
    import json

    from app.api import operations

    inner = operations._OP

    class Lenient:
        def validate_json(self, data: Any, *a: Any, **k: Any) -> Any:
            body = json.loads(data)
            for key in ("tier", "approved", "destination", "payee_account", "x_owner_token"):
                body.pop(key, None)
            return inner.validate_json(json.dumps(body), *a, **k)

    monkeypatch.setattr(operations, "_OP", Lenient())
    obs = run_api(*FORBID_IDS)
    assert not_defended(obs) == set(FORBID_IDS), {i: o.outcome() for i, o in obs.items()}
    for i, o in obs.items():
        assert any("expected HTTP [422]" in f for f in o.expectation_failures), (i, o.expectation_failures)
    assert {"FL-06", "SE-04"} <= harmed(obs)
