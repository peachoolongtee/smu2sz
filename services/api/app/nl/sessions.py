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
    intent: Intent
    slots: Slots
    steps: list[PlanStep]
    data: dict[str, Any] = field(default_factory=dict)  # typed ids only (verdict ids, counter ids)


@dataclass
class PendingClarification:
    intent: Intent
    slot: str  # which slot the answer fills
    options: list[ClarifyOption]
    slots: Slots
    values: dict[str, Any] = field(default_factory=dict)  # option id -> typed slot value


@dataclass
class Session:
    id: str
    actor: str
    counterparty_id: str | None = None
    lang: str = "en"
    buyer_profile: str | None = None
    created: float = field(default_factory=time.monotonic)
    touched: float = field(default_factory=time.monotonic)
    turn: int = 0
    last_offer_id: str | None = None
    last_verdict_id: str | None = None
    last_fixture_id: str | None = None
    offer_fixtures: dict[str, str] = field(default_factory=dict)  # offer id -> fixture id (declared costs)
    pending_plan: PendingPlan | None = None
    pending_clarification: PendingClarification | None = None
    requests: dict[str, list[Any]] = field(default_factory=dict)  # request_id -> typed ops sent
    history: list[tuple[int, str]] = field(default_factory=list)  # (turn, intent)
    # approval ids the previous turn showed the owner: the only queue items a bare "approve it" / "yes" may decide
    shown_approvals: list[str] = field(default_factory=list)


class SessionStore:
    def __init__(self, ttl_s: float | None = None) -> None:
        self.ttl_s = float(os.environ.get("NL_SESSION_TTL_S", ttl_s or DEFAULT_TTL_S))
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def _expire(self, now: float) -> None:
        dead = [k for k, s in self._sessions.items() if now - s.touched > self.ttl_s]
        for k in dead:
            del self._sessions[k]
        if len(self._sessions) > MAX_SESSIONS:
            for k, _ in sorted(self._sessions.items(), key=lambda kv: kv[1].touched)[: len(self._sessions) - MAX_SESSIONS]:
                del self._sessions[k]

    def get_or_create(self, session_id: str | None, actor: str) -> tuple[Session, bool]:
        """A session is bound to the actor that opened it: a counterparty cannot continue an owner
        session (or the reverse) by guessing its id; it gets a fresh one instead."""
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            s = self._sessions.get(session_id) if session_id else None
            if s is not None and s.actor == actor:
                s.touched = now
                return s, False
            sid = session_id if session_id and s is None else f"nls-{uuid.uuid4().hex[:16]}"
            s = Session(id=sid, actor=actor)
            self._sessions[sid] = s
            return s, True

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def __len__(self) -> int:
        return len(self._sessions)


SESSIONS = SessionStore()


def reset_sessions() -> None:
    SESSIONS.clear()
