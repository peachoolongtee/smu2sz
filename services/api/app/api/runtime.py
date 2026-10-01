"""Process-wide wiring: one store, one simulated clock, the owner's pinned key, module instances.
Owned by the main architect. Modules never import this; only app/api does."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings, get_settings
from app.domain.fixtures import load_scenario
from app.domain.models import Commitment, CompiledOffer, CompileStatus, FinancialState, Mandate, Outcome
from app.domain.ports import LedgerStore
from app.mandate import load_signed_mandate
from app.mandate.fixture import demo_owner_public_key_hex
from app.operations import Executor
from app.persistence import InMemoryLedgerStore, SqlLedgerStore

# Demo-only owner credential. The real deployment sets OWNER_TOKEN; the UI's owner console sends it
# as X-Owner-Token. Without it, a request claiming to be the OWNER is treated as the AGENT.
DEMO_OWNER_TOKEN = "demo-owner-token"


@dataclass
class Runtime:
    settings: Settings
    store: LedgerStore
    owner_key_hex: str
    day: int = 0
    scenario: str = "golden_sme"
    lock: threading.RLock = field(default_factory=threading.RLock)
    latest_verdict: dict[str, str] = field(default_factory=dict)  # offer_id -> verdict_id
    documents: dict[str, Any] = field(default_factory=dict)  # doc_id -> SourceDocument (inbound, untrusted)

    def clock(self) -> int:
        return self.day

    @property
    def executor(self) -> Executor:
        return Executor(self.store, trusted_owner_key_hex=self.owner_key_hex, clock=self.clock,
                        reverify=self.reverify)

    def reverify(self, c: Commitment, state: FinancialState, mandate: Mandate, now: int) -> Outcome | None:
        """Re-evaluate a commitment's obligations on today's books (ADR-0006 section 5). The other commitments
        in the store count as live; the one being committed does not. None when it cannot be evaluated."""
        try:
            from app.verifier import evaluate_verdict

            offer = CompiledOffer(offer_id=f"REVERIFY-{c.id}", counterparty_id=c.counterparty_id,
                                  doc_ids=sorted({sp.doc_id for o in c.obligations for sp in o.spans}),
                                  received_day=now, status=CompileStatus.COMPILED, obligations=list(c.obligations),
                                  compiler="whatif-reverify", prompt_version="reverify-v1")
            others = [x for x in self.store.commitments() if x.id != c.id]
            return evaluate_verdict(offer, state, mandate, trusted_owner_key_hex=self.owner_key_hex, day=now,
                                    commitments=others).outcome
        except Exception:  # noqa: BLE001  fail closed: the executor refuses on None
            return None

    def is_owner(self, token: str | None) -> bool:
        from app.api.auth import is_owner

        return is_owner(token)

    def advance_to(self, day: int) -> Any:
        """Move simulated time forward (ADR-0006 §2). The books close every day before `day`."""
        from app.clock import advance
        from app.domain.models import Actor

        with self.lock:
            from app.domain.fixtures import scenario_events

            adv = advance(self.store, day, Actor.SYSTEM, events=scenario_events(self.scenario))
            self.day = self.store.get_state().as_of_day
            return adv

    def reset(self, scenario: str = "golden_sme") -> None:
        """Reload fixtures and clear the ledger (POST /demo/reset)."""
        with self.lock:
            self.store.reset()
            state, _unsigned = load_scenario(scenario)
            self.store.put_state(state)
            self.store.put_mandate(load_signed_mandate())
            self.day = 0
            self.scenario = scenario
            self.latest_verdict.clear()
            self.documents.clear()
            from app.nl import reset_sessions

            reset_sessions()


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        s = get_settings()
        store: LedgerStore = InMemoryLedgerStore() if s.database_url == "memory" else SqlLedgerStore(s.database_url)
        _runtime = Runtime(settings=s, store=store, owner_key_hex=demo_owner_public_key_hex())
        _runtime.reset()
    return _runtime


def set_runtime(rt: Runtime | None) -> None:
    """Tests inject an in-memory runtime."""
    global _runtime
    _runtime = rt
