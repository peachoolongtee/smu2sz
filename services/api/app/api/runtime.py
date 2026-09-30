"""Process-wide wiring: one store, one simulated clock, the owner's pinned key, module instances.
Owned by the main architect. Modules never import this; only app/api does."""

from __future__ import annotations

import hmac
import os
import threading
from dataclasses import dataclass, field

from app.config import Settings, get_settings
from app.domain.fixtures import load_scenario
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

    def clock(self) -> int:
        return self.day

    @property
    def executor(self) -> Executor:
        return Executor(self.store, trusted_owner_key_hex=self.owner_key_hex, clock=self.clock)

    def is_owner(self, token: str | None) -> bool:
        expected = os.environ.get("OWNER_TOKEN", DEMO_OWNER_TOKEN)
        return bool(token) and hmac.compare_digest(token or "", expected)

    def reset(self, scenario: str = "golden_sme") -> None:
        """Reload fixtures and clear the ledger (POST /demo/reset)."""
        with self.lock:
            self.store.reset()
            state, _unsigned = load_scenario(scenario)
            self.store.put_state(state)
            self.store.put_mandate(load_signed_mandate())
            self.day = 0
            self.scenario = scenario


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
