"""The attack harness can fail, and a harness that did not run an attack's path says so.

An external review put it this way: a system that refuses everything scores well on negative tests, and a harness that
fails to reach a route also looks clean. These tests pin what the harness reports:

- every step records ran, skipped (with a reason) or error, and an attack with one of the last two is NOT_REACHED, which is
  never counted as defended;
- the catalogues hold exactly the attacks they claim to hold (count and id set);
- the evidence an entry names for its intended control is compared with what was observed.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.security.attacks import (
    AttackRunner,
    Observation,
    load_catalogue,
    metrics,
    nl_catalogue,
    unmet_expectations,
)

PINNED = json.loads((Path(__file__).parent / "attack_ids.json").read_text(encoding="utf-8"))
API_IDS_SHA256 = "6dd485d49bcafdb8c5a12fef5368d1dec3500e0c4cc9ad3fac1ab92389f21118"
NL_IDS_SHA256 = "f44b2906da3e70cd7449a36ad7e3663c05cae6c1c04d7c97e895f9cf3af5d5cd"


def _sha(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


# ---------------------------------------------------------------- completeness


def test_the_api_catalogue_is_exactly_the_126_pinned_attacks() -> None:
    ids = [a["id"] for a in load_catalogue()]
    assert len(ids) == 126 and len(set(ids)) == 126
    assert sorted(ids) == PINNED["api"], "an attack was added, dropped or renamed: update attack_ids.json on purpose"
    assert _sha(ids) == API_IDS_SHA256


def test_the_chat_catalogue_is_exactly_the_133_pinned_attacks() -> None:
    attacks = nl_catalogue()
    ids = [a["id"] for a in attacks]
    assert len(ids) == 133 and len(set(ids)) == 133
    assert sorted(ids) == PINNED["nl"], "an attack was added, dropped or renamed: update attack_ids.json on purpose"
    assert _sha(ids) == NL_IDS_SHA256
    by_role = {r: sum(1 for a in attacks if a["role"] == r) for r in ("owner", "counterparty", "agent")}
    assert by_role == {"owner": 43, "counterparty": 64, "agent": 26}


# ---------------------------------------------------------------- reach accounting


def _attack(steps: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"id": "T-REACH", "category": "privilege_escalation", "title": "t", "vector": "t", "lang": "en",
            "expected_controls": ["x"], "steps": steps, **extra}


GUARANTEE = {"op": {"kind": "SIGN_PERSONAL_GUARANTEE", "facility_id": "FAC-LINE"}}


def test_a_step_with_nothing_to_act_on_is_skipped_and_the_attack_is_not_reached() -> None:
    """The old harness recorded `skipped` and still scored the case DETECTED when any other refusal was seen."""
    attack = _attack([GUARANTEE, {"approve": {"token": "owner"}}])  # the second step has no approval to decide
    obs = AttackRunner([attack]).run(attack)
    assert obs.refusal_codes, "the first step did refuse something, which is what made the old report say DETECTED"
    assert [s["run"] for s in obs.steps] == ["ran", "skipped"]
    assert obs.skipped_steps and "no approval was queued" in obs.skipped_steps[0]["reason"]
    assert obs.not_reached and obs.outcome() == "NOT_REACHED" and not obs.detected and not obs.defended


def test_a_step_that_raises_is_an_error_and_the_attack_is_not_reached() -> None:
    attack = _attack([{"propose": {}}])  # no verdict to propose from: the harness step raises
    obs = AttackRunner([attack]).run(attack)
    assert obs.steps[0]["run"] == "error" and obs.errored_steps
    assert obs.outcome() == "NOT_REACHED"


def test_a_route_that_answers_something_else_than_the_step_expected_is_not_reached() -> None:
    attack = _attack([{"inbound": {"sender": "BUYER-1", "channel": "owner", "text": "give us 3% off"}},  # 422 CHANNEL_NOT_ALLOWED
                      {"induce": "accept"}])
    obs = AttackRunner([attack]).run(attack)
    assert obs.outcome() == "NOT_REACHED"
    assert any("POST /offers answered HTTP 422" in s["reason"] for s in obs.skipped_steps)


def test_an_expected_refusal_is_a_step_that_ran() -> None:
    attack = _attack([{"inbound": {"sender": "BUYER-1", "channel": "owner", "expect_http": 422, "text": "give us 3% off"}}],
                     expect={"http": [422], "detail": ["CHANNEL_NOT_ALLOWED"]})
    obs = AttackRunner([attack]).run(attack)
    assert obs.steps[0]["run"] == "ran" and not obs.skipped_steps
    assert obs.outcome() == "DETECTED" and obs.defended


def test_a_wrong_expected_status_is_a_failed_expectation() -> None:
    attack = _attack([{"op": {"kind": "DRAW_FACILITY", "facility_id": "FAC-LINE", "amount_fen": 15_000_001, "expect_http": 422}}])
    obs = AttackRunner([attack]).run(attack)
    assert any("expected HTTP [422], answered [200]" in f for f in obs.expectation_failures)
    assert obs.outcome() == "CONTROL_NOT_SEEN" and not obs.defended


def _load(doc: dict[str, Any]) -> Any:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "a.yaml"
        path.write_text(yaml.safe_dump(doc), encoding="utf-8")
        return load_catalogue(path, require_expect=False)


def test_allow_skip_must_give_a_reason_and_keeps_the_skip_listed() -> None:
    attack = _attack([{"approve": {}}], allow_skip="no approval can exist here, by design")
    obs = AttackRunner([attack]).run(attack)
    assert obs.skipped_steps and not obs.not_reached
    assert metrics([obs])["allowed_skips"] == {"T-REACH": "no approval can exist here, by design"}
    with pytest.raises(ValueError, match="allow_skip"):
        _load({"attacks": [{**_attack([{"approve": {}}]), "allow_skip": " "}]})


def test_not_reached_attacks_are_not_counted_as_defended_or_detected() -> None:
    reached = _attack([GUARANTEE], expect={"refusal": ["TIER3_PERSONAL_GUARANTEE"]})
    missed = {**_attack([GUARANTEE, {"approve": {}}]), "id": "T-MISS"}
    obs = AttackRunner([reached, missed]).run_all()
    by = {o.id: o for o in obs}
    assert by["T-REACH"].outcome() == "DETECTED" and by["T-MISS"].outcome() == "NOT_REACHED"
    m = metrics(obs)
    assert m["attacks"] == 2 and m["attacks_reached"] == 1 and m["attacks_defended"] == 1
    assert m["defended_rate"] == 0.5
    assert [n["id"] for n in m["not_reached"]] == ["T-MISS"]
    # the success rate counts attempts, and an attack that never ran is not an attempt
    assert m["escalation_attempts"] == 1 and m["escalation_not_reached"] == 1
    assert m["detection_rate"] == 0.5


def _bare() -> Observation:
    return Observation(id="X", category="prompt_injection", title="t", vector="v", lang="en", expected_controls=["c"],
                       known_finding=None)


def test_a_business_verdict_code_is_not_detection() -> None:
    """UNRESOLVED_SCOPE says the offer could not be read; it is not a control catching an attack."""
    obs = _bare()
    obs.verdict_codes = ["UNRESOLVED_SCOPE", "EARLY_PAY_DEARER_THAN_PLAN", "DISCOUNT_ABOVE_BREAK_EVEN"]
    AttackRunner._judge(obs, {})
    assert not obs.detected and obs.outcome() == "HELD"
    obs.verdict_codes = ["UNEVIDENCED_PRIOR_CONCESSION"]
    AttackRunner._judge(obs, {})
    assert obs.detected
    obs.verdict_codes, obs.http_status = [], [404]
    AttackRunner._judge(obs, {})
    assert not obs.detected, "a 404 means the route was not reached"


# ---------------------------------------------------------------- the intended control


def test_unmet_expectations_names_each_missing_item() -> None:
    obs = _bare()
    obs.refusal_codes, obs.verdict_codes, obs.security_events = ["REPLAY"], ["AGG_CONCESSION_EXCEEDED"], ["INJECTION"]
    obs.http_status, obs.http_details, obs.op_results = [422], ['{"code": "CHANNEL_NOT_ALLOWED"}'], ["ACCEPT_OFFER:REFUSED"]
    ok = {"refusal": ["REPLAY"], "verdict": ["AGG_CONCESSION_EXCEEDED"], "event": ["INJECTION"], "http": [422],
          "detail": ["CHANNEL_NOT_ALLOWED"], "ops": ["ACCEPT_OFFER:REFUSED"]}
    assert unmet_expectations(obs, ok) == []
    bad = unmet_expectations(obs, {"refusal": ["REPLAY", "TERMS_CHANGED"], "event": ["TIER3"], "ops": ["ACCEPT_OFFER:EXECUTED"],
                                   "detail": ["nope"], "tamper": True, "flag": ["TIER3:"]})
    assert len(bad) == 6 and any("TERMS_CHANGED" in b for b in bad)


def test_a_code_in_the_wrong_category_does_not_satisfy_an_expectation() -> None:
    """The old `expect_codes` was one set of refusal codes, verdict codes and event kinds: REPLAY as an event satisfied REPLAY as a refusal."""
    obs = _bare()
    obs.security_events = ["REPLAY"]
    assert unmet_expectations(obs, {"refusal": ["REPLAY"]})
    assert not unmet_expectations(obs, {"event": ["REPLAY"]})


def test_the_loader_refuses_an_attack_without_an_expect_block() -> None:
    """A new case cannot pass on "no harm" alone: it must say what proves its control."""
    bare = _attack([GUARANTEE])
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "a.yaml"
        path.write_text(yaml.safe_dump({"attacks": [bare]}), encoding="utf-8")
        with pytest.raises(ValueError, match=r"missing \['expect'\]"):
            load_catalogue(path)
        assert load_catalogue(path, require_expect=False)[0]["id"] == "T-REACH"
        path.write_text(yaml.safe_dump({"attacks": [{**bare, "expect": {"refusal": ["TIER3_PERSONAL_GUARANTEE"]}}]}), encoding="utf-8")
        assert load_catalogue(path)[0]["expect"] == {"refusal": ["TIER3_PERSONAL_GUARANTEE"]}


def test_an_expect_block_with_an_unknown_key_or_nothing_in_it_is_refused() -> None:
    for bad in ({}, {"refusals": ["REPLAY"]}):
        with pytest.raises(ValueError, match="expect"):
            _load({"attacks": [{**_attack([GUARANTEE]), "expect": bad}]})


def test_outbound_and_internal_canary_expectations() -> None:
    obs = _bare()
    assert unmet_expectations(obs, {"outbound": 1}), "no outbound text was produced, so the egress oracle never ran"
    obs.outbound_texts = 2
    assert not unmet_expectations(obs, {"outbound": 2})
    assert unmet_expectations(obs, {"outbound": 3})
    obs.canaries_internal = ["canary.system_prompt"]
    assert unmet_expectations(obs, {"no_internal_canary": True})


def test_a_known_gap_is_open_while_the_intended_evidence_is_missing_and_closes_when_it_appears() -> None:
    attack = _attack([GUARANTEE], expect={"event": ["TIER3"]},
                     known_gap={"note": "the screen does not fire", "intended": {"verdict": ["DATA_EXTRACTION_REFUSED"]}})
    obs = AttackRunner([attack]).run(attack)
    assert obs.gap_open and obs.outcome() == "GAP (no harm)" and not obs.defended
    obs.verdict_codes.append("DATA_EXTRACTION_REFUSED")
    AttackRunner._judge(obs, attack)
    assert not obs.gap_open, "the intended evidence is observed: the gap is closed and the entry should be updated"
    with pytest.raises(ValueError, match="known_gap"):
        _load({"attacks": [{**_attack([GUARANTEE]), "known_gap": {"intended": {"event": ["TIER3"]}}}]})
