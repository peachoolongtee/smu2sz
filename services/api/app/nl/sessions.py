"""Multi-turn sessions, kept in module state (independent of the Runtime) with a TTL.

A session remembers only typed references: the last offer and verdict ids, a pending plan (intent +
typed slots + proposed steps) awaiting confirmation or correction, a pending clarification, and the
typed operations each `request_id` produced (so a retried request is replayed, not re-planned).
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.nl.models import ClarifyOption, Intent, PlanStep, Slots

DEFAULT_TTL_S = 30 * 60
MAX_SESSIONS = 1_000


@dataclass
class PendingPlan:
    """What the owner was shown and is asked to confirm. `ops` are the exact typed operations (kind, facility,
    receivable, amount) that a "go ahead" sends, `quoted_cost_fen` the total cost quoted for them (None when the
    plan states none), and `state_version`, `mandate_version` and `day` the books the proposal was built on. A
    confirmation never re-plans: it sends these operations (app/nl/plans.py states the rule)."""

    intent: Intent
    slots: Slots
    steps: list[PlanStep]
    data: dict[str, Any] = field(default_factory=dict)  # typed ids only (verdict ids, counter ids)
    ops: list[Any] = field(default_factory=list)
    quoted_cost_fen: int | None = None
    state_version: int | None = None
    mandate_version: int | None = None
    day: int | None = None
    # The economics shown with the plan, as the QUOTED fact the API layer stores when the plan runs (app/nl/quoting.py); None when none
    # could be built. Never read by a confirmation: it only describes what the owner was shown.
    quote: Any = None

    def bind(self, ctx: Any, ops: Any = None, cost: int | None = None) -> PendingPlan:
        """Fix the books and the operations this plan was built on (the context supplies today's state, mandate, day)."""
        if ops is not None:
            self.ops = list(ops)
        if cost is not None:
            self.quoted_cost_fen = cost
        self.state_version = ctx.state().state_version
        self.mandate_version = ctx.mandate().version
        self.day = ctx.day
        return self


@dataclass
class PendingClarification:
    intent: Intent
    slot: str  # which slot the answer fills
    options: list[ClarifyOption]
    slots: Slots
    values: dict[str, Any] = field(default_factory=dict)  # option id -> typed slot value
    text: str = ""  # the owner's words that raised the question: the answer resumes THEM ("60 days instead of 45"), not "Foshan"


@dataclass
class PendingAsk:
    """A read-only question that asked which customer (app/nl/ask.py): the tool that was running and the slots already read from the
    question (the new terms, the rate ...). The owner's next turn that names a customer finishes it with those slots; any other turn drops it."""

    tool: str
    slots: dict[str, Any]
    question: str


@dataclass
class Session:
    id: str
    actor: str
    owner_auth: bool = False  # opened with the owner token; only the same credential may continue it
    # who opened it (SEC-21): "owner", "agent", "buyer:<id>" (a verified channel key) or "anon"; only the same principal continues it
    principal: str = ""
    counterparty_id: str | None = None
    lang: str = "en"
    buyer_profile: str | None = None
    created: float = field(default_factory=time.monotonic)
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex[:12])  # distinguishes a recreated session's keys
    touched: float = field(default_factory=time.monotonic)
    turn: int = 0
    last_offer_id: str | None = None
    last_verdict_id: str | None = None
    last_fixture_id: str | None = None
    bound_verdict_id: str | None = None  # the page's decision this session was last pointed at (app/nl/binding.py)
    offer_fixtures: dict[str, str] = field(default_factory=dict)  # offer id -> fixture id (declared costs)
    pending_plan: PendingPlan | None = None
    pending_clarification: PendingClarification | None = None
    pending_ask: PendingAsk | None = None
    requests: dict[str, list[Any]] = field(default_factory=dict)  # request_id -> typed ops sent
    history: list[tuple[int, str]] = field(default_factory=list)  # (turn, intent)
    # approval ids the previous turn showed the owner: the only queue items a bare "approve it" / "yes" may decide
    shown_approvals: list[str] = field(default_factory=list)


class SessionStore:
    def __init__(self, ttl_s: float | None = None) -> None:
        self.ttl_s = float(os.environ.get("NL_SESSION_TTL_S", ttl_s or DEFAULT_TTL_S))
        self._sessions: dict[str, Session] = {}
        # ids ended with "New conversation" (`end`), with when: such an id is never continued again, by anyone, until it ages out
        self._ended: dict[str, float] = {}
        self._lock = threading.RLock()

    def _expire(self, now: float) -> None:
        dead = [k for k, s in self._sessions.items() if now - s.touched > self.ttl_s]
        for k in dead:
            del self._sessions[k]
        for k in [k for k, t in self._ended.items() if now - t > self.ttl_s]:
            del self._ended[k]
        if len(self._ended) > MAX_SESSIONS:  # bounded: the oldest ended ids go first
            for k, _ in sorted(self._ended.items(), key=lambda kv: kv[1])[:len(self._ended) - MAX_SESSIONS]:
                del self._ended[k]
        if len(self._sessions) > MAX_SESSIONS:
            # SEC-21: anyone else's sessions go first, the oldest first, so a flood of agent or anonymous turns cannot push out the
            # owner's session and its pending plan; the owner's own go only when the owner alone fills the store
            excess = len(self._sessions) - MAX_SESSIONS
            ranked = sorted(self._sessions.items(), key=lambda kv: (kv[1].owner_auth, kv[1].touched))
            for k, _ in ranked[:excess]:
                del self._sessions[k]

    def get_or_create(self, session_id: str | None, actor: str, owner_auth: bool = False,
                      principal: str = "") -> tuple[Session, bool]:
        """A session is bound to the actor, the credential class and the principal that opened it: a counterparty cannot
        continue an owner session (or the reverse), a caller without the owner token cannot continue a session the owner
        opened (or the reverse), and a sender without a buyer's key cannot continue that buyer's keyed session (SEC-21), by
        guessing or knowing its id; each gets a fresh, server-issued one instead. A free id the client chose is still taken, unless
        that conversation was ended (`end`): an ended id gets a fresh, server-issued one too, so nothing of it can come back."""
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            s = self._sessions.get(session_id) if session_id else None
            if s is not None and s.actor == actor and s.owner_auth == owner_auth and s.principal == principal:
                s.touched = now
                return s, False
            free = bool(session_id) and s is None and session_id not in self._ended
            sid = session_id if free else f"nls-{uuid.uuid4().hex[:16]}"
            s = Session(id=sid, actor=actor, owner_auth=owner_auth, principal=principal)
            self._sessions[sid] = s
            return s, True

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def end(self, session_id: str, principal: str | None) -> bool:
        """"New conversation": forget this session (its last offer and verdict, pending plan, pending clarification, shown approvals
        and replayed requests) and never continue its id again. `principal` None is the owner's authority (any session); otherwise
        only the principal that opened the session may end it (SEC-21). True when a session was ended; a session that does not
        exist or is someone else's is left as it is and answers False, the same answer either way."""
        with self._lock:
            self._expire(time.monotonic())
            s = self._sessions.get(session_id)
            if s is None or (principal is not None and s.principal != principal):
                return False
            del self._sessions[session_id]
            self._ended[session_id] = time.monotonic()
            return True

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._ended.clear()

    def __len__(self) -> int:
        return len(self._sessions)


SESSIONS = SessionStore()


def reset_sessions() -> None:
    SESSIONS.clear()
