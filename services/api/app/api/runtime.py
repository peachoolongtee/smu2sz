"""Process-wide wiring: one store, one simulated clock, the owner's pinned key, module instances.
Owned by the main architect. Modules never import this; only app/api does.

Startup never deletes (audit A04). `get_runtime()` opens the configured store and HYDRATES from it: the clock
is read from the stored state and nothing is written. Only an EMPTY store is seeded (demo fixture + signed demo
mandate), and only in DEMO_MODE; with DEMO_MODE off an empty store is a startup error (the books must be
provisioned: state plus an owner-signed mandate). With DEMO_MODE off the pinned owner key must come from
OWNER_PUBLIC_KEY_HEX; the published demo key is never pinned silently.

Not persisted, by design: the in-memory session caches (`latest_verdict`, `documents`, NL sessions). They are
empty after a restart. The books, mandate, approvals, nonces and the operations log live in the store.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings, get_settings
from app.domain.fixtures import seed_state
from app.domain.models import Commitment, CompiledOffer, CompileStatus, FinancialState, Mandate, Outcome
from app.domain.ports import LedgerStore
from app.mandate import load_signed_mandate
from app.mandate.fixture import demo_owner_public_key_hex
from app.operations import Executor
from app.persistence import InMemoryLedgerStore, SqlLedgerStore
from app.persistence.errors import NotFound


class StartupError(RuntimeError):
    """The runtime cannot start safely (missing owner key, or an unprovisioned non-demo database)."""


class ResetRefused(RuntimeError):
    """Runtime.reset() was called against a non-demo deployment backed by a persistent store."""


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
                        reverify=self.reverify, admit=self.admit)

    def admit(self, op: Any, state: FinancialState, mandate: Mandate) -> Any:
        """A05: one funding operation judged on today's books with the planner's engine and predicates."""
        from app.books import current_books
        from app.funding.admission import admit

        return admit(op, current_books(state, self.store.commitments()), mandate)

    def reverify(self, c: Commitment, state: FinancialState, mandate: Mandate, now: int) -> Outcome | None:
        """Re-evaluate a commitment's obligations on today's books (ADR-0006 section 5). The other commitments
        in the store count as live; the one being committed does not. None when it cannot be evaluated."""
        try:
            from app.verifier import evaluate_verdict

            # ADR-0009: never apply a commitment twice. Terms already written into the state (adjustments, or
            # invoices carrying them) are not evaluated again as a candidate.
            written = {a.id for a in state.invoice_adjustments} | {i for r in state.receivables for i in r.applied}
            obligations = [o for o in c.obligations if f"{c.id}:{o.id}" not in written]
            offer = CompiledOffer(offer_id=f"REVERIFY-{c.id}", counterparty_id=c.counterparty_id,
                                  doc_ids=sorted({sp.doc_id for o in c.obligations for sp in o.spans}),
                                  received_day=now, status=CompileStatus.COMPILED, obligations=obligations,
                                  compiler="whatif-reverify", prompt_version="reverify-v1")
            others = [x for x in self.store.commitments() if x.id != c.id]
            return evaluate_verdict(offer, state, mandate, trusted_owner_key_hex=self.owner_key_hex, day=now,
                                    commitments=others).outcome
        except Exception:  # noqa: BLE001  fail closed: the executor refuses on None
            return None

    def hydrate(self) -> None:
        """Read the clock and the seeded scenario from the stored books (start-up; nothing is written)."""
        state = self.store.get_state()
        self.day = state.as_of_day
        if state.scenario:
            self.scenario = state.scenario

    def is_owner(self, token: str | None) -> bool:
        from app.api.auth import is_owner

        return is_owner(token)

    def advance_to(self, day: int) -> Any:
        """Move simulated time forward (ADR-0006 §2). The books close every day before `day`."""
        from app.clock import advance
        from app.domain.models import Actor

        with self.lock:
            from app.api.auth import demo_mode
            from app.domain.fixtures import scenario_events

            # Scenario events (the golden demo's day-42 payroll) belong to the demo books they were written for:
            # only in DEMO_MODE and only the scenario the stored books name. Provisioned books name none.
            name = self.store.get_state().scenario
            events = scenario_events(name) if demo_mode() and name else []
            adv = advance(self.store, day, Actor.SYSTEM, events=events)
            self.day = self.store.get_state().as_of_day
            return adv

    def reset(self, scenario: str = "golden_sme") -> None:
        """Reload fixtures and clear the ledger (POST /demo/reset). Refused (ResetRefused) when DEMO_MODE is off
        and the store is not the in-memory one: a real deployment's books are never wiped."""
        from app.api.auth import demo_mode

        if not demo_mode() and not isinstance(self.store, InMemoryLedgerStore):
            raise ResetRefused("reset is a demo-only operation; refused because DEMO_MODE is off and the store is persistent")
        with self.lock:
            self.store.reset()
            _seed(self.store, scenario)
            self.day = 0
            self.scenario = scenario
            self.latest_verdict.clear()
            self.documents.clear()
            from app.nl import reset_sessions

            reset_sessions()


def _seed(store: LedgerStore, scenario: str = "golden_sme") -> None:
    """Write the demo fixture state and the signed demo mandate. Never deletes."""
    store.put_state(seed_state(scenario))  # the scenario's name is stored with the books
    store.put_mandate(load_signed_mandate())


def _has(read: Any) -> bool:
    try:
        read()
    except NotFound:
        return False
    return True


def _owner_key_hex(s: Settings, demo: bool) -> str:
    if demo:
        return demo_owner_public_key_hex()
    key = s.owner_public_key_hex.strip().lower()
    if not key:
        raise StartupError("DEMO_MODE is off: set OWNER_PUBLIC_KEY_HEX to the owner's Ed25519 public key (64 hex "
                           "characters). The published demo key is never pinned outside DEMO_MODE.")
    if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
        raise StartupError("OWNER_PUBLIC_KEY_HEX must be 64 hex characters (an Ed25519 public key).")
    return key


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    """Open the configured store and hydrate from it. Never deletes; seeds only an empty store, in DEMO_MODE."""
    global _runtime
    if _runtime is None:
        from app.api.auth import demo_mode

        s = get_settings()
        demo = demo_mode()
        owner_key = _owner_key_hex(s, demo)
        store: LedgerStore = InMemoryLedgerStore() if s.database_url == "memory" else SqlLedgerStore(s.database_url)
        try:
            has_state, has_mandate = _has(store.get_state), _has(store.get_mandate)
            seedable = demo or isinstance(store, InMemoryLedgerStore)  # an in-memory store is empty by definition
            if not has_state and not seedable:
                raise StartupError("DEMO_MODE is off and the store holds no books: provision the database first "
                                   "(a financial state and an owner-signed mandate); the demo fixture is not seeded "
                                   "into a non-demo deployment.")
            if not has_state:
                _seed(store)
            elif not has_mandate:
                if not seedable:
                    raise StartupError("the store holds a financial state but no mandate: provision the "
                                       "owner-signed mandate before starting with DEMO_MODE off.")
                store.put_mandate(load_signed_mandate())
            rt = Runtime(settings=s, store=store, owner_key_hex=owner_key)
            rt.hydrate()
        except Exception:
            if isinstance(store, SqlLedgerStore):
                store.dispose()
            raise
        _runtime = rt
    return _runtime


def set_runtime(rt: Runtime | None) -> None:
    """Tests inject an in-memory runtime."""
    global _runtime
    _runtime = rt
