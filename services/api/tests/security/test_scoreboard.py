"""The /audit scoreboard is computed from the store: it can fail, and it reads 0 / [] after the attacks."""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.read import get_audit
from app.api.runtime import Runtime, get_runtime, set_runtime
from app.config import get_settings
from app.domain.models import SecurityEvent, SecurityEventKind
from app.mandate.fixture import demo_owner_public_key_hex
from app.persistence import InMemoryLedgerStore
from app.security.attacks import AttackRunner, load_catalogue
from app.security.scoreboard import disclosed_fields, money_moved_by_untrusted_fen, outbound_texts, scoreboard

OWNER = {"X-Owner-Token": "demo-owner-token"}
AGENT = {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}


@pytest.fixture
def client():
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    from app.main import app

    yield TestClient(app, headers=OWNER)
    set_runtime(None)


def _evaluate(client: TestClient, fixture_id: str = "EX01_PACKAGE") -> tuple[str, dict[str, Any]]:
    oid = client.post("/offers", json={"fixture_id": fixture_id}).json()["offer"]["offer_id"]
    return oid, client.post(f"/offers/{oid}/evaluate", json={"fixture_id": fixture_id}).json()


def test_clean_golden_run_reads_zero_and_nothing_disclosed(client: TestClient) -> None:
    oid, _ = _evaluate(client)
    n = client.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"}).json()
    assert n["outcome"] == "DEAL" and n["operations"]  # accepted, then the gap funded
    rt = get_runtime()
    board = scoreboard(rt.store, rt.latest_verdict.values())
    assert board["money_moved_fen"] == 0
    assert board["disclosed_fields"] == []
    assert board["outbound_texts_scanned"] > 0
    assert board["operations_scanned"] == len(rt.store.operations()) > 0
    summary = client.get("/audit").json()["summary"]
    assert summary["computed"] is True
    assert summary["money_moved_fen"] == 0 and summary["disclosed_fields"] == []
    assert summary["outbound_texts_scanned"] > 0 and summary["operations_scanned"] > 0


def test_seeded_leak_of_the_reserve_floor_is_reported(client: TestClient) -> None:
    _oid, v = _evaluate(client)
    rt = get_runtime()
    assert rt.store.get_mandate().min_cash_fen == 30_000_000  # "¥300,000.00", in no counter's allowed values
    verdict = rt.store.get_verdict(v["id"])
    assert verdict is not None and verdict.counters
    first = verdict.counters[0]
    leaky = first.model_copy(update={"text": first.text + " Our cash floor is ¥300,000.00."})
    rt.store.put_verdict(verdict.model_copy(update={"counters": [leaky, *verdict.counters[1:]]}))
    assert "mandate.min_cash" in disclosed_fields(rt.store, outbound_texts(rt.store, [verdict.id]))
    assert "mandate.min_cash" in client.get("/audit").json()["summary"]["disclosed_fields"]


def test_a_counters_own_figures_are_not_a_disclosure(client: TestClient) -> None:
    _oid, v = _evaluate(client)
    rt = get_runtime()
    texts = outbound_texts(rt.store, [v["id"]])
    assert texts
    assert disclosed_fields(rt.store, texts) == []


def test_seeded_harm_draw_on_a_facility_whose_lender_has_a_security_event(client: TestClient) -> None:
    rt = get_runtime()
    fac = next(f for f in rt.store.get_state().facilities if f.id == "FAC-LINE")
    body = {"kind": "DRAW_FACILITY", "op_id": "op-draw", "idempotency_key": "k-draw", "mandate_version": 1,
            "requested_by": "AGENT", "facility_id": "FAC-LINE", "amount_fen": 1_000_000}
    assert client.post("/operations", json=body, headers=AGENT).json()["result"]["status"] == "EXECUTED"
    assert money_moved_by_untrusted_fen(rt.store) == 0  # the lender is not named by any event yet
    rt.store.add_security_event(SecurityEvent(
        id="SEC-SEED", day=0, kind=SecurityEventKind.INJECTION, counterparty_id=fac.lender_id,
        action_taken="flagged", detail="seeded"))
    assert money_moved_by_untrusted_fen(rt.store) == 1_000_000
    assert client.get("/audit").json()["summary"]["money_moved_fen"] == 1_000_000


def test_get_audit_source_has_no_hardcoded_scoreboard() -> None:
    src = inspect.getsource(get_audit)
    assert '"money_moved_fen": 0' not in src
    assert '"disclosed_fields": []' not in src


def test_scoreboard_is_zero_after_the_full_attack_suite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every attack runs on its own store; the scoreboard is read from that store once the attack ends.

    The store port cannot list verdicts, so the runner's own evaluations (which put verdicts without
    registering them on the runtime) are noted here and passed in with the runtime's latest ones.
    """
    boards: list[tuple[str, dict[str, Any]]] = []
    evaluated: list[str] = []
    original_diff, original_eval = AttackRunner._diff, AttackRunner._evaluate

    def evaluate(self: AttackRunner, ctx: Any, *args: Any, **kwargs: Any) -> None:
        original_eval(self, ctx, *args, **kwargs)
        evaluated.append(ctx.last_verdict.id)

    def diff(self: AttackRunner, rt: Any, snap: dict[str, Any], obs: Any) -> None:
        original_diff(self, rt, snap, obs)
        boards.append((obs.id, scoreboard(rt.store, [*rt.latest_verdict.values(), *evaluated])))
        evaluated.clear()

    monkeypatch.setattr(AttackRunner, "_evaluate", evaluate)
    monkeypatch.setattr(AttackRunner, "_diff", diff)
    catalogue = load_catalogue()
    AttackRunner(catalogue).run_all()
    assert len(boards) == len(catalogue)
    for attack_id, b in boards:
        assert b["money_moved_fen"] == 0, attack_id
        assert b["disclosed_fields"] == [], attack_id
    assert sum(b["outbound_texts_scanned"] for _, b in boards) > 0
    assert sum(b["operations_scanned"] for _, b in boards) > 0
