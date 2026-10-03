"""Regression tests for the fifth red team of 3 Oct 2026 (docs/research/redteam-2026-10-03e), operations side: F3
(scenario events), F4 (the early-pay promise: day and portions), F5 (owner repayment after expiry) and F6 (a queued
receipt keeps its reported day). F1 and F2 are in tests/verifier/test_redteam_e.py.

Each test asserts the stored state (the store's FinancialState, commitments, approvals and log).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import Runtime, set_runtime
from app.config import get_settings
from app.domain.fixtures import load_scenario
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.persistence import InMemoryLedgerStore

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Agent-Key": "demo-agent-key"}
BANK = {"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}
RCV_A = 42_000_000


def _runtime(store: Any = None) -> Runtime:
    return Runtime(settings=get_settings(), store=store or InMemoryLedgerStore(),
                   owner_key_hex=demo_owner_public_key_hex())


@pytest.fixture
def rt() -> Any:
    r = _runtime()
    r.reset()
    set_runtime(r)
    reset_sessions()
    yield r
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def client(rt: Runtime) -> TestClient:
    from app.main import app

    return TestClient(app)


def post_op(client: TestClient, rt: Runtime, headers: dict, body: dict) -> dict:
    body = {"mandate_version": rt.store.get_mandate().version, "day": rt.day, **body}
    body.setdefault("idempotency_key", body["op_id"])
    r = client.post("/operations", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()["result"]


def move(client: TestClient, day: int) -> None:
    assert client.post("/clock/advance", json={"to_day": day}, headers=OWNER).status_code == 200


def rcv(rt: Runtime, rid: str = "RCV-A") -> Any:
    return next(r for r in rt.store.get_state().receivables if r.id == rid)


def flows(rt: Runtime) -> set[str]:
    return {f.id for f in rt.store.get_state().flows}


# ================================================================ F3: scenario events stay with their scenario


def test_f3_the_demo_seed_stores_its_scenario_and_the_golden_payroll_still_arrives(rt: Runtime) -> None:
    s = rt.store.get_state()
    assert s.scenario == "golden_sme" and json.loads(s.model_dump_json())["scenario"] == "golden_sme"
    rt.advance_to(30)
    assert "F-PAYROLL-M2" in flows(rt) and rt.store.get_state().scenario == "golden_sme"


def test_f3_a_fixture_state_names_no_scenario_and_serialises_as_before() -> None:
    state, _ = load_scenario()
    assert state.scenario is None and "scenario" not in json.loads(state.model_dump_json())


def test_f3_provisioned_books_get_no_scenario_events(rt: Runtime) -> None:
    own, _ = load_scenario()  # stands in for any business's provisioned books: no scenario stored
    rt.store.put_state(own)
    rt.advance_to(30)
    assert "F-PAYROLL-M2" not in flows(rt) and rt.store.get_state().scenario is None
    adv = [json.loads(o.payload_json) for o in rt.store.operations() if o.kind == "ADVANCE_CLOCK"][-1]
    assert "F-PAYROLL-M2" not in json.dumps(adv)


def test_f3_outside_demo_mode_even_seeded_books_get_no_scenario_events(rt: Runtime,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "0")
    rt.advance_to(30)
    assert "F-PAYROLL-M2" not in flows(rt)


def test_f3_a_restart_hydrates_the_scenario_and_applies_only_its_events(rt: Runtime) -> None:
    rt.reset("short_facilities")
    rt.advance_to(20)
    again = _runtime(rt.store)  # what get_runtime() does on start-up with a store that already holds books
    again.hydrate()
    assert (again.scenario, again.day) == ("short_facilities", 20)
    again.advance_to(30)
    assert "F-PAYROLL-M2" not in flows(again) and again.store.get_state().scenario == "short_facilities"
