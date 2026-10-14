"""Per-request context: the only doorway from /nl to the verifier, the executor and the egress guard.

- `evaluate()` always runs the verifier (conservative mode) and stores the offer, the verdict and its
  security events. Nothing in /nl decides an outcome itself.
- `execute()` sends one typed Operation to the executor, dated `day`, with an idempotency key derived
  from session + request (or turn) + step. The executor computes the tier; /nl never supplies one.
- `guard()` passes every outbound text through `app.egress.guard` and logs any security event.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.books import Books, current_books
from app.domain.models import (
    Actor,
    Commitment,
    CompiledOffer,
    FinancialState,
    Mandate,
    OperationResult,
    SecurityEvent,
    SecurityEventKind,
    SourceSpan,
)
from app.domain.ports import LedgerStore
from app.egress import AllowedValue, guard, protected_for
from app.nl.sessions import Session
from app.operations import Executor
from app.verifier import OwnerConstraints, VerdictBundle
from app.verifier import evaluate as verify
from app.verifier.evaluate import Plans


@dataclass
class NlContext:
    store: LedgerStore
    executor: Executor
    day: int
    owner_key_hex: str
    owner_authenticated: bool
    session: Session
    lang: str
    trace_id: str
    request_id: str | None = None
    binding: Any = None  # app.nl.binding.Binding: the validated page context of this owner turn, if any
    reads: Any = None  # app.nl.binding.OwnerReads: the Home read and the business-words rewrite (owner turns only)
    scope_used: Any = None  # app.nl.models.ScopeUsed: the scope the request carried and the server honoured, if any
    scope_customer: str | None = None  # the buyer the request's scope narrows to (a customer, an invoice's or a negotiation's), if any
    scope_invoice: str | None = None  # the invoice the request's scope narrows to, if any
    scope_read: str | None = None  # "filtered": the read listed only the scope's rows; "company": the read is company-wide whatever the scope
    results: list[OperationResult] = field(default_factory=list)
    sent: list[Any] = field(default_factory=list)  # the typed operations sent this turn
    events: list[str] = field(default_factory=list)
    _n: int = 0

    # ------------------------------------------------------------ reads

    def state(self) -> FinancialState:
        return self.store.get_state()

    def mandate(self) -> Mandate:
        return self.store.get_mandate()

    def books(self, state: FinancialState | None = None) -> Books:
        """Current books (ADR-0006): the stored state (or a hypothetical `state`) plus the obligations of
        the live commitments. Every projection in /nl runs on `books.state` and `books.with_(...)`."""
        return current_books(state or self.state(), self.store.commitments())

    @property
    def requested_by(self) -> Actor:
        """An owner claim without the owner token is the AGENT (as on POST /operations)."""
        if self.session.actor == "OWNER" and self.owner_authenticated:
            return Actor.OWNER
        return Actor.AGENT

    # ------------------------------------------------------------ verifier

    def declared(self, state: FinancialState, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Owner-side facts the verifier binds bases to: the expected orders in the state (spec §6.1)
        plus any costs the owner declared for a fixture (e.g. EX05's shipment cost)."""
        purchases: dict[str, int] = {}
        for eo in state.expected_orders:
            purchases[eo.counterparty_id] = purchases.get(eo.counterparty_id, 0) + eo.amount_fen
        return {"period_purchases_fen": purchases, **(dict(extra) if extra else {})}

    def evaluate(self, offer: CompiledOffer, *, declared: Mapping[str, Any] | None = None,
                 remember: bool = True, state: FinancialState | None = None,
                 owner_constraints: OwnerConstraints | None = None, plans: Plans = "committed",
                 commitments: Sequence[Commitment] | None = None) -> VerdictBundle:
        """`state` is a hypothetical variant of the stored state (e.g. one gap only); the verdict is
        still the verifier's, and the operations built from it still pass the executor's gates.
        `owner_constraints` passes the owner's goal to the verifier (it only tightens). `plans` defaults
        to "committed": no /nl handler reads the display-only expected plan, and the verdict is the same.
        `commitments` defaults to every commitment in the store; the verifier projects current books."""
        state = state or self.state()
        mandate = self.mandate()
        if declared is None and offer.offer_id in self.session.offer_fixtures:
            from app.domain.fixtures import load_offers

            declared = load_offers()[self.session.offer_fixtures[offer.offer_id]].get("declared_costs")
        bundle = verify(offer, state, mandate, trusted_owner_key_hex=self.owner_key_hex, day=self.day,
                        owner_declared=self.declared(state, declared),
                        commitments=self.store.commitments() if commitments is None else commitments,
                        owner_constraints=owner_constraints, plans=plans)
        self.store.put_offer(offer)
        self.store.put_verdict(bundle.verdict)
        for ev in bundle.security_events:
            self.log_event(ev)
        if remember:
            self.session.last_offer_id = offer.offer_id
            self.session.last_verdict_id = bundle.verdict.id
        return bundle

    def evaluate_accepted(self, package: CompiledOffer) -> VerdictBundle:
        """The verdict on an accepted counter's package, for the gap that remains. Once the accept has
        executed, the package's obligations are already live in the books; they are counted once, so the
        commitment that holds exactly these terms is left out of the books for this evaluation. A queued
        (PENDING_APPROVAL) accept is not live and the package is projected as the plan's assumption."""
        def terms(obs: Iterable[Any]) -> list[str]:
            return sorted(o.model_dump_json(exclude={"id", "spans", "confidence"}) for o in obs)

        want = terms(package.obligations)
        rest = [c for c in self.store.commitments()
                if not (c.counterparty_id == package.counterparty_id and terms(c.obligations) == want)]
        return self.evaluate(package, remember=False, commitments=rest)

    # ------------------------------------------------------------ executor

    def next_key(self, kind: str) -> tuple[str, str]:
        self._n += 1
        # a request id is the caller's own retry handle; without one the key is scoped to this session object,
        # so a session recreated under the same id (expiry, reset, restart) never reuses an old key
        scope = f"r:{self.request_id}" if self.request_id else f"t{self.session.turn}:{self.session.nonce}"
        key = f"nl:{self.session.id}:{scope}:{self._n}:{kind}"
        return "NL-" + hashlib.sha256(key.encode()).hexdigest()[:16], key

    # Funding the agent plans and runs on a "go ahead" is the agent's act, whoever is in the chat: a leg above the
    # mandate's ceiling therefore waits for the owner's explicit approval, in an owner session as on every other path.
    AGENT_RUN_KINDS = frozenset({"DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING", "REPAY_FACILITY"})

    def base(self, kind: str) -> dict[str, Any]:
        op_id, key = self.next_key(kind)
        by = Actor.AGENT if kind in self.AGENT_RUN_KINDS else self.requested_by
        return {"op_id": op_id, "idempotency_key": key, "mandate_version": self.mandate().version,
                "requested_by": by, "day": self.day}

    def execute(self, op: Any) -> OperationResult:
        if op.day != self.day:  # built by this module only; a mismatch is a bug, not a user error
            raise ValueError("an /nl operation must be dated to the runtime day")
        result = self.executor.execute(op)
        self.sent.append(op)
        self.results.append(result)
        return result

    # ------------------------------------------------------------ security and egress

    def log_event(self, ev: SecurityEvent) -> None:
        if ev.id not in {e.id for e in self.store.security_events()}:
            self.store.add_security_event(ev)
        if ev.id not in self.events:
            self.events.append(ev.id)

    def new_event(self, kind: SecurityEventKind, counterparty_id: str | None, detail: str,
                  spans: Iterable[SourceSpan] = (), action: str = "treated as data; nothing executed") -> SecurityEvent:
        basis = f"{self.session.id}|{self.session.turn}|{kind}|{detail}"
        ev = SecurityEvent(id="SEC-NL-" + hashlib.sha256(basis.encode()).hexdigest()[:16], day=self.day, kind=kind,
                           counterparty_id=counterparty_id, action_taken=action, detail=detail, spans=list(spans),
                           trace_id=self.trace_id)
        self.log_event(ev)
        return ev

    def guard(self, text: str, recipient_id: str, allow: Iterable[AllowedValue] = ()) -> tuple[str, bool]:
        """(text to send, ok). A blocked text is replaced whole by the guard's safe template."""
        protected = protected_for(self.store)  # the books, the mandate, the canaries and every contract record
        res = guard(text, protected, recipient_id=recipient_id, allow=list(allow), day=self.day,
                    trace_id=self.trace_id, lang=self.lang if self.lang in ("en", "zh") else None)  # type: ignore[arg-type]
        if res.security_event is not None:
            self.log_event(res.security_event)
        return res.text_out, res.ok
