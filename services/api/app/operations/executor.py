"""The operations executor: the security core (INVARIANTS 1, 3, 6, 7, 8 and 12).

Every typed operation goes through the same gates, in this order, and every outcome (including
refusals and duplicates) is appended to the hash-chained log:

1. idempotency: a known key returns the original result as DUPLICATE; nothing is re-run;
   then dating: the operation's `day` must be the executor's clock day (otherwise
   STALE_OPERATION; a backdated one is also a REPLAY), so logged days are executed days;
2. mandate: signature (pinned to the owner key), expiry, revocation and version;
3. tier, computed here from the typed operation and the STORED commitment/verdict:
   Tier 3 is refused for every caller; then the counterparty circuit breaker; then, for
   AcceptOffer/RecordCommitment, the replay / expiry / terms-hash screen; then Tier 2 is queued
   for the owner (PENDING_APPROVAL);
4. per-kind preconditions and state effects on the simulated bank (`FinancialState`).

Nothing the caller supplies can lower a tier. Owner decisions (`decide`) re-run the queued
operation through every gate except the Tier-2 queue, against the mandate in force at decision time.

Atomicity (F-01). Every public entry point runs as one store unit of work (`store.transaction()`):
the state, the commitment, the nonce, any approval or security event and the log entry are
committed together or not at all. If the log append fails, nothing the operation did survives, so
a retry with the same idempotency key executes exactly once.
"""

from __future__ import annotations

import hmac
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Any

from app.commitments import CommitmentError, check_acceptance, terms_hash, transition
from app.domain.models import (
    AcceptOffer,
    Actor,
    AddFacility,
    ApplyForFacility,
    ChangeMandate,
    Commitment,
    CommitmentStatus,
    Contingency,
    CounterOffer,
    Counterparty,
    DrawFacility,
    Facility,
    FacilityKind,
    FacilityStatus,
    FinancialState,
    ForwardConcession,
    GenerateBorrowerFile,
    IssueEquity,
    Mandate,
    ObligationType,
    OperationResult,
    OperationStatus,
    Outcome,
    PledgeCollateral,
    ReceivePayment,
    RecordCommitment,
    RejectOffer,
    RepayFacility,
    Repayment,
    RequestOwnerApproval,
    SecurityEvent,
    SecurityEventKind,
    SignPersonalGuarantee,
    SubmitInvoiceForFinancing,
    Tier,
    Verdict,
    Violation,
    ViolationCode,
)
from app.domain.money import fmt_yuan
from app.domain.ports import LedgerStore
from app.mandate import check_validity, tier_for
from app.operations.charges import finance_invoice_charges, line_interest, upfront_fee
from app.operations.log import (
    RESET_CIRCUIT_KIND,
    REVOKE_COMMITMENT_KIND,
    LoggedEntry,
    LogReader,
    advance_for,
    open_lots,
    parse_operation,
)
from app.persistence import ApprovalAlreadyDecided, ApprovalStatus, NonceAlreadyUsed, NotFound, canonical_json

Code = ViolationCode
EXECUTED = OperationStatus.EXECUTED
REFUSED = OperationStatus.REFUSED
PENDING = OperationStatus.PENDING_APPROVAL
DUPLICATE = OperationStatus.DUPLICATE

CIRCUIT_THRESHOLD = 3  # refusals for one counterparty ...
CIRCUIT_WINDOW_DAYS = 7  # ... within this many days open its circuit

_TIER_RANK = {Tier.TIER_1: 1, Tier.TIER_2: 2, Tier.TIER_3: 3}

_TIER3_CODES: dict[type, ViolationCode] = {
    SignPersonalGuarantee: Code.TIER3_PERSONAL_GUARANTEE,
    PledgeCollateral: Code.TIER3_COLLATERAL,
    IssueEquity: Code.TIER3_EQUITY,
    ChangeMandate: Code.TIER3_MANDATE_CHANGE,
}

_NOT_DRAWABLE = (
    FacilityKind.INVOICE_FINANCING,
    FacilityKind.BUYER_EARLY_PAY,
    FacilityKind.BANK_ACCEPTANCE_BILL,
    FacilityKind.EQUITY,
)

_ACCEPTANCE_SECURITY = {
    Code.REPLAY: SecurityEventKind.REPLAY,
    Code.COMMITMENT_EXPIRED: SecurityEventKind.EXPIRED,
    Code.TERMS_CHANGED: SecurityEventKind.TERMS_CHANGED,
}

_MANDATE_SECURITY = {
    Code.MANDATE_REVOKED: SecurityEventKind.REVOKED,
    Code.MANDATE_EXPIRED: SecurityEventKind.EXPIRED,
    Code.BAD_SIGNATURE: SecurityEventKind.PRIVILEGE_ESCALATION,
}

def approval_id_of(result: OperationResult) -> str | None:
    """The owner-approval queue entry a PENDING_APPROVAL result points at, if any."""
    return result.approval_id


def _max_tier(*tiers: Tier) -> Tier:
    return max(tiers, key=lambda t: _TIER_RANK[t])


def _v(code: ViolationCode, message: str, **inputs: object) -> Violation:
    return Violation(code=code, message=message, inputs={k: str(v) for k, v in inputs.items()})


def committable(obligations: list[Any]) -> list[Any]:
    """Obligations a commitment may carry: claimed-but-unevidenced ones are never booked."""
    return [
        o
        for o in obligations
        if o.contingency != Contingency.CLAIMED_UNEVIDENCED and o.type != ObligationType.CLAIMED_PRIOR_CONCESSION
    ]


def lengthens_terms(obligations: list[Any]) -> bool:
    """A terms change that needs the owner (Tier 2): a TERMS_EXTENSION that lengthens terms. A shortening
    (days_delta < 0, e.g. EX05's move to 30 days) is a gain and stays Tier 1. An unbound delta (None)
    cannot be shown to shorten, so it counts as lengthening (fail closed; tiers only rise)."""
    return any(o.type == ObligationType.TERMS_EXTENSION and (o.days_delta is None or o.days_delta > 0)
               for o in obligations)


def only_early_pay(obligations: list[Any]) -> bool:
    """True when every obligation is an immediate discount on a named invoice (the only Tier-1 acceptance)."""
    return bool(obligations) and all(
        o.type == ObligationType.IMMEDIATE_DISCOUNT and o.base.receivable_id for o in obligations)


def has_terms_change(commitment: Commitment) -> bool:
    return lengthens_terms(commitment.obligations)


def verdict_forward_value(verdict: Verdict) -> int:
    """The net new forward concession a verdict verified: concessions plus FIRM gains (contingent gains
    count as zero; INVARIANT 5), floored at 0 as in the aggregate. Never an immediate cost."""
    by_id = {o.id: o for o in verdict.bound_obligations}
    net = 0
    for cv in verdict.concession_values:
        ob = by_id.get(cv.obligation_id)
        if cv.value_fen >= 0 or (ob is not None and ob.contingency == Contingency.FIRM):
            net += cv.value_fen
    return max(0, net)


class _Refused(Exception):
    def __init__(self, violations: list[Violation], security: SecurityEventKind | None = None) -> None:
        super().__init__("; ".join(v.message for v in violations))
        self.violations = violations
        self.security = security


def _refuse(code: ViolationCode, message: str, security: SecurityEventKind | None = None, **inputs: object) -> _Refused:
    return _Refused([_v(code, message, **inputs)], security)


@dataclass
class _Effect:
    message: str
    state: FinancialState | None = None
    commitment: Commitment | None = None
    nonce: str | None = None
    approval: tuple[str, str] | None = None  # (op_json, reason) to queue for the owner
    approval_id: str | None = None  # an existing queue entry the result points at
    status: OperationStatus = EXECUTED


@dataclass
class _Ctx:
    op: Any
    now: int
    state: FinancialState
    mandate: Mandate | None
    commitment: Commitment | None
    verdict: Verdict | None
    counterparty_id: str | None
    tier: Tier


def _bump(state: FinancialState, **updates: object) -> FinancialState:
    return state.model_copy(update={**updates, "state_version": state.state_version + 1})


def _facility(state: FinancialState, facility_id: str) -> Facility:
    f = next((f for f in state.facilities if f.id == facility_id), None)
    if f is None:
        raise _refuse(Code.PRECONDITION_FAILED, f"Facility {facility_id} is not on the owner's funding menu",
                      facility_id=facility_id)
    return f


def _with_facility(state: FinancialState, f: Facility) -> list[Facility]:
    return [f if x.id == f.id else x for x in state.facilities]


class Executor:
    """Satisfies `app.domain.ports.Executor`. The only writer of commitments and the operations log.

    `trusted_owner_key_hex` pins the owner's Ed25519 key: a mandate signed by any other key is
    refused (BAD_SIGNATURE). `clock` returns the simulated current day.
    """

    def __init__(self, store: LedgerStore, *, trusted_owner_key_hex: str, clock: Callable[[], int],
                 reverify: Callable[[Commitment, FinancialState, Mandate, int], Outcome | None] | None = None) -> None:
        if not trusted_owner_key_hex:
            raise ValueError("the executor needs the owner's public key to pin mandate signatures")
        self._store = store
        self._owner_key = trusted_owner_key_hex
        self._clock = clock
        self._reverify = reverify
        self._reader = LogReader()
        self._lock = threading.RLock()

    # ================================================================ public API

    def _unit_of_work(self) -> AbstractContextManager[Any]:
        """The store's transaction (both shipped stores have one). A store without it gets no
        atomicity; `LedgerStore` should declare it (interface change request)."""
        tx = getattr(self._store, "transaction", None)
        return tx() if callable(tx) else nullcontext()

    def execute(self, op: Any) -> OperationResult:
        with self._lock, self._unit_of_work():
            return self._run(op, approved=False)

    def decide(self, approval_id: str, approved: bool, actor: Actor) -> OperationResult:
        """Owner decision on a queued Tier-2 operation. Anyone else is refused and logged."""
        with self._lock, self._unit_of_work():
            rec = self._store.get_approval(approval_id)
            if rec is None:
                raise NotFound(f"approval {approval_id} not found")
            op = parse_operation(rec.op_json)
            if op is None:
                raise ValueError(f"approval {approval_id} does not hold a typed operation")
            now = self._clock()
            if actor != Actor.OWNER:
                v = _v(Code.INSUFFICIENT_AUTHORITY, f"Only the owner may decide {approval_id}; {actor} may not",
                       approval_id=approval_id, actor=actor)
                self._security(SecurityEventKind.PRIVILEGE_ESCALATION, op, now, None,
                               f"{actor} tried to decide approval {approval_id} ({op.kind})")
                result = OperationResult(op_id=op.op_id, kind=op.kind, status=REFUSED, tier=Tier.TIER_2,
                                         violations=[v], effective_day=now, approval_id=approval_id,
                                         message=v.message)
                return self._log(op, result, key=f"{op.idempotency_key}#decide:{approval_id}:{actor}")
            if rec.status != ApprovalStatus.PENDING:
                raise ApprovalAlreadyDecided(f"approval {approval_id} is {rec.status}")
            self._store.decide_approval(approval_id, approved, Actor.OWNER.value)
            if not approved:
                result = OperationResult(op_id=op.op_id, kind=op.kind, status=REFUSED, tier=Tier.TIER_2,
                                         effective_day=now, approval_id=approval_id,
                                         message=f"Declined by the owner ({approval_id}); nothing executed")
                return self._log(op, result)
            # Re-run at decision time: every gate except the Tier-2 queue, against today's mandate.
            result = self._run(op.model_copy(update={"day": now}), approved=True)
            return result.model_copy(update={"approval_id": approval_id})

    def reset_circuit(self, counterparty_id: str, actor: Actor) -> OperationResult:
        """Close a counterparty's circuit breaker. Owner only; logged either way."""
        with self._lock, self._unit_of_work():
            now = self._clock()
            op_id = f"RESET-{counterparty_id}-{now}-{len(self._store.operations()) + 1}"
            payload = {"kind": RESET_CIRCUIT_KIND, "op_id": op_id, "counterparty_id": counterparty_id,
                       "requested_by": actor.value, "day": now}
            if actor != Actor.OWNER:
                v = _v(Code.INSUFFICIENT_AUTHORITY, f"Only the owner may reset the circuit for {counterparty_id}",
                       actor=actor, counterparty_id=counterparty_id)
                self._add_security(SecurityEventKind.PRIVILEGE_ESCALATION, now, counterparty_id,
                                   f"{actor} tried to reset the circuit breaker for {counterparty_id}")
                result = OperationResult(op_id=op_id, kind=RESET_CIRCUIT_KIND, status=REFUSED,
                                         tier=Tier.TIER_2, violations=[v], effective_day=now, message=v.message)
            else:
                result = OperationResult(op_id=op_id, kind=RESET_CIRCUIT_KIND, status=EXECUTED,
                                         tier=Tier.TIER_2, effective_day=now, message=f"Circuit for {counterparty_id} reset by the owner")
            rec = self._store.append_operation(op_id, RESET_CIRCUIT_KIND, op_id,
                                               canonical_json(payload), canonical_json(result))
            return result.model_copy(update={"seq": rec.seq, "entry_hash": rec.entry_hash, "prev_hash": rec.prev_hash})

    def revoke_commitment(self, commitment_id: str, actor: Actor) -> OperationResult:
        """Revoke a commitment (the compensating action for a booked concession). Owner only.

        Logged as a REVOKE_COMMITMENT entry either way, like RESET_CIRCUIT (it is not a typed
        Operation). For the owner: the commitment moves to REVOKED and its forward concession
        leaves the state, in one unit of work with the log entry. Anyone else is refused with a
        PRIVILEGE_ESCALATION event; an unknown, expired, fulfilled or already revoked commitment
        is refused with PRECONDITION_FAILED."""
        with self._lock, self._unit_of_work():
            now = self._clock()
            op_id = f"REVOKE-{commitment_id}-{now}-{len(self._store.operations()) + 1}"
            payload = {"kind": REVOKE_COMMITMENT_KIND, "op_id": op_id, "commitment_id": commitment_id,
                       "requested_by": actor.value, "day": now}
            c = self._store.get_commitment(commitment_id)
            cp = c.counterparty_id if c is not None else None

            def done(status: OperationStatus, message: str, violations: list[Violation] | None = None) -> OperationResult:
                result = OperationResult(op_id=op_id, kind=REVOKE_COMMITMENT_KIND, status=status, tier=Tier.TIER_2,
                                         violations=violations or [], effective_day=now, message=message)
                rec = self._store.append_operation(op_id, REVOKE_COMMITMENT_KIND, op_id,
                                                   canonical_json(payload), canonical_json(result))
                return result.model_copy(update={"seq": rec.seq, "entry_hash": rec.entry_hash,
                                                 "prev_hash": rec.prev_hash})

            if actor != Actor.OWNER:
                v = _v(Code.INSUFFICIENT_AUTHORITY, f"Only the owner may revoke commitment {commitment_id}; "
                       f"{actor} may not", actor=actor, commitment_id=commitment_id)
                self._add_security(SecurityEventKind.PRIVILEGE_ESCALATION, now, cp,
                                   f"{actor} tried to revoke commitment {commitment_id}")
                return done(REFUSED, v.message, [v])
            if c is None:
                v = _v(Code.PRECONDITION_FAILED, f"Commitment {commitment_id} does not exist",
                       commitment_id=commitment_id)
                return done(REFUSED, v.message, [v])
            try:
                revoked = transition(c, CommitmentStatus.REVOKED, now)
            except CommitmentError as exc:
                v = _v(Code.PRECONDITION_FAILED, f"Commitment {c.id} is {c.status.value}; it cannot be revoked "
                       f"({exc})", commitment_id=c.id, status=c.status.value)
                return done(REFUSED, v.message, [v])
            state = self._store.get_state()
            kept = [fc for fc in state.forward_concessions if fc.commitment_id != c.id]
            removed = sum(fc.value_fen for fc in state.forward_concessions if fc.commitment_id == c.id)
            self._store.put_commitment(revoked)
            if len(kept) != len(state.forward_concessions):
                self._store.put_state(_bump(state, forward_concessions=kept))
            return done(EXECUTED, f"Commitment {c.id} revoked by the owner ({c.status.value} -> REVOKED); "
                                  f"forward concession {fmt_yuan(removed)} removed")

    def circuit_open(self, counterparty_id: str) -> bool:
        return self._recent_refusals(counterparty_id, self._clock()) >= CIRCUIT_THRESHOLD

    def propose_commitment(self, verdict_id: str, *, expires_day: int, counter_id: str | None = None,
                           nonce: str | None = None) -> Commitment:
        """Create the PROPOSED commitment a verdict (or one of its counters) allows. Deterministic
        code builds it from typed rows only (INVARIANT 1); acceptance later needs its nonce.

        It commits exactly what was verified: the verdict's `bound_obligations` (never the raw compiled
        offer, whose terms may still be unbound), or the chosen counter's obligations. Its forward value is
        the forward concession those obligations book (`counter.forward_value_fen`, or the verdict's net
        forward value), never a counter's immediate `supplier_cost_fen`."""
        from app.commitments import new_commitment

        with self._lock, self._unit_of_work():
            verdict = self._store.get_verdict(verdict_id)
            if verdict is None:
                raise NotFound(f"verdict {verdict_id} not found")
            offer = self._store.get_offer(verdict.offer_id)
            if offer is None or offer.version != verdict.offer_version:
                raise NotFound(f"offer {verdict.offer_id} v{verdict.offer_version} not found")
            if counter_id is not None:
                counter = next((c for c in verdict.counters if c.id == counter_id), None)
                if counter is None:
                    raise NotFound(f"counter {counter_id} is not in verdict {verdict_id}")
                obligations, value = committable(counter.obligations), counter.forward_value_fen
            elif verdict.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
                obligations, value = committable(verdict.bound_obligations), verdict_forward_value(verdict)
                if not obligations:
                    raise ValueError(f"verdict {verdict_id} verified no bound obligations; nothing to commit")
            else:
                raise ValueError(f"verdict {verdict_id} is {verdict.outcome}; only a counter can be committed")
            kwargs = {"nonce_factory": (lambda: nonce)} if nonce else {}
            c = new_commitment(offer, verdict_id, obligations, verdict.mandate_version, expires_day, value, **kwargs)
            self._store.put_commitment(c)
            return c

    # ================================================================ the pipeline

    def _run(self, op: Any, *, approved: bool) -> OperationResult:
        now = self._clock()
        kind = getattr(op, "kind", type(op).__name__)

        # 1. idempotency ------------------------------------------------------------
        dup = self._duplicate(op, approved)
        if dup is not None:
            return dup

        ctx = self._context(op, now)

        def refuse(exc: _Refused) -> OperationResult:
            if exc.security is not None:
                self._security(exc.security, op, now, ctx.counterparty_id, exc.violations[0].message)
            msg = "Refused: " + "; ".join(v.message for v in exc.violations)
            return self._log(op, OperationResult(op_id=op.op_id, kind=kind, status=REFUSED, tier=ctx.tier,
                                                 violations=exc.violations, effective_day=now, message=msg))

        try:
            # 1b. dating: the log's days are executed days (interest, windows, expiry)
            if op.day != now:
                raise self._misdated(op, now)
            # 2. mandate ---------------------------------------------------------------
            self._check_mandate(ctx)
            # 3. tier ------------------------------------------------------------------
            if ctx.tier == Tier.TIER_3:
                raise self._tier3(ctx)
            if ctx.counterparty_id is not None and self._recent_refusals(ctx.counterparty_id, now) >= CIRCUIT_THRESHOLD:
                raise _refuse(Code.CIRCUIT_OPEN,
                              f"Circuit open for {ctx.counterparty_id}: {CIRCUIT_THRESHOLD} refusals within "
                              f"{CIRCUIT_WINDOW_DAYS} days; the owner must reset it",
                              counterparty_id=ctx.counterparty_id)
            if isinstance(op, AcceptOffer | RecordCommitment):
                self._screen_commitment(ctx)
            if ctx.tier == Tier.TIER_2 and not approved:
                reason = self._tier2_reason(ctx)
                aid = self._store.add_approval(canonical_json(op), reason)
                return self._log(op, OperationResult(
                    op_id=op.op_id, kind=kind, status=PENDING, tier=ctx.tier, effective_day=now, approval_id=aid,
                    message=f"Queued for owner approval ({aid}): {reason}"))
            # 4. preconditions and effects -------------------------------------------------
            effect = self._handle(ctx)
        except _Refused as exc:
            return refuse(exc)

        try:
            if effect.nonce is not None:
                self._store.mark_nonce_used(effect.nonce)
        except NonceAlreadyUsed:
            return refuse(_refuse(Code.REPLAY, "Nonce already used", SecurityEventKind.REPLAY))
        if effect.commitment is not None:
            self._store.put_commitment(effect.commitment)
        if effect.state is not None:
            self._store.put_state(effect.state)
        message, queued = effect.message, effect.approval_id
        if effect.approval is not None:
            queued = self._store.add_approval(*effect.approval)
            message = f"{message} ({queued})"
        return self._log(op, OperationResult(op_id=op.op_id, kind=kind, status=effect.status, tier=ctx.tier,
                                             effective_day=now, approval_id=queued, message=message))

    @staticmethod
    def _misdated(op: Any, now: int) -> _Refused:
        """An operation must be dated to the executor's day. A backdated one is also a replay: it
        could only carry an older day to dodge an expiry or a window."""
        violations = [_v(Code.STALE_OPERATION, f"Operation dated day {op.day} but the executor clock is day {now}",
                         op_day=op.day, clock_day=now)]
        if op.day < now:
            violations.append(_v(Code.REPLAY, f"Operation backdated from day {now} to day {op.day}",
                                 op_day=op.day, clock_day=now))
            return _Refused(violations, SecurityEventKind.REPLAY)
        return _Refused(violations)

    # ---------------------------------------------------------------- logging

    def _log(self, op: Any, result: OperationResult, key: str | None = None) -> OperationResult:
        payload = canonical_json(op)
        rec = self._store.append_operation(op.op_id, result.kind, key or op.idempotency_key, payload,
                                           canonical_json(result))
        return result.model_copy(update={"seq": rec.seq, "entry_hash": rec.entry_hash, "prev_hash": rec.prev_hash})

    def _entries(self) -> list[LoggedEntry]:
        return self._reader.entries(self._store.operations())

    def _duplicate(self, op: Any, approved: bool) -> OperationResult | None:
        key = op.idempotency_key
        if self._store.find_by_idempotency_key(key) is None:
            return None
        records = self._store.operations()
        entries = self._reader.entries(records)
        if any(r.idempotency_key == key for r in records if r.seq in self._reader.unreadable):
            # A log row with this key no longer parses (tampering): its status cannot be known, so
            # nothing runs again (fail closed).
            now = self._clock()
            v = _v(Code.PRECONDITION_FAILED, f"The log entry for idempotency key {key} is unreadable; "
                   f"nothing re-executed", idempotency_key=key)
            return self._log(op, OperationResult(op_id=op.op_id, kind=op.kind, status=REFUSED, tier=Tier.TIER_3,
                                                 violations=[v], effective_day=now, message=v.message))
        prior = [e for e in entries if e.idempotency_key == key and e.result.status != DUPLICATE]
        if approved:  # an owner-approved re-run: only a completed execution makes it a duplicate
            prior = [e for e in prior if e.result.status == EXECUTED]
        if not prior:
            return None
        original = prior[-1]
        o = original.result
        result = OperationResult(
            op_id=o.op_id, kind=o.kind, status=DUPLICATE, tier=o.tier, violations=o.violations,
            effective_day=o.effective_day, approval_id=o.approval_id,
            message=f"Duplicate of seq {original.seq} (status {o.status.value}); nothing re-executed. {o.message}",
        )
        return self._log(op, result)

    def _security(self, kind: SecurityEventKind, op: Any, day: int, counterparty_id: str | None,
                  detail: str) -> None:
        self._add_security(kind, day, counterparty_id, f"{getattr(op, 'kind', '?')} {op.op_id}: {detail}")

    def _add_security(self, kind: SecurityEventKind, day: int, counterparty_id: str | None, detail: str) -> None:
        n = len(self._store.security_events()) + 1
        self._store.add_security_event(SecurityEvent(
            id=f"SEC-OPS-{n:06d}", day=day, kind=kind, counterparty_id=counterparty_id,
            action_taken="refused by the executor; nothing booked", detail=detail))

    # ---------------------------------------------------------------- context and tier

    def _context(self, op: Any, now: int) -> _Ctx:
        state = self._store.get_state()
        try:
            mandate: Mandate | None = self._store.get_mandate()
        except NotFound:
            mandate = None
        commitment = self._find_commitment(op)
        verdict = self._store.get_verdict(commitment.verdict_id) if commitment is not None else None
        ctx = _Ctx(op=op, now=now, state=state, mandate=mandate, commitment=commitment, verdict=verdict,
                   counterparty_id=self._counterparty(op, state), tier=Tier.TIER_3)
        ctx.tier = self._tier(ctx)
        return ctx

    def _tier(self, ctx: _Ctx) -> Tier:
        """Computed from the typed operation and stored rows only; extra facts only raise it."""
        if ctx.mandate is None:
            return Tier.TIER_3
        op, c = ctx.op, ctx.commitment
        terms_change, value, beyond = False, None, False
        if isinstance(op, AcceptOffer | RecordCommitment) and c is not None:
            terms_change, value = has_terms_change(c), c.forward_value_fen
            beyond = not only_early_pay(c.obligations)
        tier = tier_for(op, ctx.mandate, ctx.state, accepts_terms_change=terms_change, commitment_value_fen=value,
                        accepts_beyond_early_pay=beyond)
        v = ctx.verdict
        verdict_backs_offer = v is not None and v.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL)
        if isinstance(op, AcceptOffer | RecordCommitment) and c is not None and v is not None and verdict_backs_offer:
            tier = _max_tier(tier, v.required_tier)
        return tier

    def _find_commitment(self, op: Any) -> Commitment | None:
        if isinstance(op, RecordCommitment):
            return self._store.get_commitment(op.commitment_id)
        if not isinstance(op, AcceptOffer):
            return None
        cands = [c for c in self._store.commitments()
                 if c.offer_id == op.offer_id and c.offer_version == op.offer_version]
        by_nonce = [c for c in cands if hmac.compare_digest(c.nonce.encode(), op.nonce.encode())]
        if by_nonce:
            return by_nonce[-1]
        live = [c for c in cands if c.status in (CommitmentStatus.PROPOSED, CommitmentStatus.ACCEPTED)]
        if live:
            return live[-1]
        return cands[-1] if cands else None

    def _counterparty(self, op: Any, state: FinancialState) -> str | None:
        """Who an operation is with, for the circuit breaker."""
        if isinstance(op, AddFacility):
            return op.facility.lender_id
        if isinstance(op, AcceptOffer | RecordCommitment):
            c = self._find_commitment(op)
            if c is not None:
                return c.counterparty_id
        if isinstance(op, AcceptOffer | CounterOffer | RejectOffer):
            offer = self._store.get_offer(op.offer_id)
            if offer is not None:
                return offer.counterparty_id
            c = next((c for c in self._store.commitments() if c.offer_id == op.offer_id), None)
            return c.counterparty_id if c is not None else None
        facility_id = getattr(op, "facility_id", None)
        if isinstance(facility_id, str):
            f = next((f for f in state.facilities if f.id == facility_id), None)
            return f.lender_id if f is not None else None
        if isinstance(op, ReceivePayment):
            r = next((r for r in state.receivables if r.id == op.receivable_id), None)
            return r.counterparty_id if r is not None else None
        return None

    def _recent_refusals(self, counterparty_id: str, now: int) -> int:
        """Refusals with violations for `counterparty_id` in the last CIRCUIT_WINDOW_DAYS days,
        counted since the owner last reset its circuit."""
        entries = self._entries()
        state = self._store.get_state()
        start = 0
        for e in entries:
            if (e.kind == RESET_CIRCUIT_KIND and e.result.status == EXECUTED
                    and e.payload.get("counterparty_id") == counterparty_id):
                start = e.seq
        n = 0
        for e in entries:
            if e.seq <= start or e.op is None or e.result.status != REFUSED or not e.result.violations:
                continue
            if e.day is None or not (now - CIRCUIT_WINDOW_DAYS < e.day <= now):
                continue
            if self._counterparty(e.op, state) == counterparty_id:
                n += 1
        return n

    # ---------------------------------------------------------------- gates

    def _check_mandate(self, ctx: _Ctx) -> None:
        if ctx.mandate is None:
            raise _refuse(Code.BAD_SIGNATURE, "No owner-signed mandate is stored", SecurityEventKind.PRIVILEGE_ESCALATION)
        violations = check_validity(ctx.mandate, ctx.now, ctx.op.mandate_version, self._owner_key)
        if violations:
            kinds = [_MANDATE_SECURITY[v.code] for v in violations if v.code in _MANDATE_SECURITY]
            raise _Refused(violations, kinds[0] if kinds else None)

    def _tier3(self, ctx: _Ctx) -> _Refused:
        op = ctx.op
        if isinstance(op, AddFacility):
            lender = op.facility.lender_id
            known = any(c.id == lender and c.known for c in ctx.state.counterparties)
            if not known:
                return _refuse(Code.UNKNOWN_COUNTERPARTY,
                               f"Facility {op.facility.id} from unregistered lender {lender} cannot enter the "
                               f"funding menu; only the owner adds facilities", SecurityEventKind.UNKNOWN_COUNTERPARTY,
                               requested_by=op.requested_by, lender_id=lender)
            return _refuse(Code.INSUFFICIENT_AUTHORITY,
                           f"Only the owner can add a facility; {op.requested_by} cannot", SecurityEventKind.TIER3,
                           requested_by=op.requested_by, lender_id=lender)
        code = _TIER3_CODES.get(type(op), Code.INSUFFICIENT_AUTHORITY)
        return _refuse(code, f"{getattr(op, 'kind', type(op).__name__)} is Tier 3 and is never executed, "
                             f"whoever asks ({getattr(op, 'requested_by', '?')})", SecurityEventKind.TIER3)

    def _screen_commitment(self, ctx: _Ctx) -> None:
        """Replay, expiry and terms checks, plus the verdict that must back the commitment."""
        op, c, v = ctx.op, ctx.commitment, ctx.verdict
        if c is None:
            ref = op.commitment_id if isinstance(op, RecordCommitment) else f"offer {op.offer_id} v{op.offer_version}"
            raise _refuse(Code.PRECONDITION_FAILED, f"No proposed commitment for {ref}")
        if c.status == CommitmentStatus.REVOKED:
            raise _refuse(Code.PRECONDITION_FAILED, f"Commitment {c.id} was revoked")
        presented = op.terms_hash if isinstance(op, AcceptOffer) else c.terms_hash
        codes = check_acceptance(c, presented, op.nonce, ctx.now, self._store)
        if c.status not in (CommitmentStatus.PROPOSED, CommitmentStatus.ACCEPTED, CommitmentStatus.EXPIRED) \
                and Code.REPLAY not in codes:
            codes.insert(0, Code.REPLAY)
        if codes:
            texts = {
                Code.REPLAY: f"Nonce for commitment {c.id} is wrong or already used",
                Code.COMMITMENT_EXPIRED: f"Commitment {c.id} expired on day {c.expires_day}",
                Code.TERMS_CHANGED: f"Presented terms differ from commitment {c.id}'s terms hash",
            }
            raise _Refused([_v(code, texts[code], commitment_id=c.id, day=ctx.now) for code in codes],
                           _ACCEPTANCE_SECURITY[codes[0]])
        assert ctx.mandate is not None
        if c.mandate_version != ctx.mandate.version:
            raise _refuse(Code.MANDATE_VERSION_MISMATCH,
                          f"Commitment {c.id} was made under mandate v{c.mandate_version}, "
                          f"current is v{ctx.mandate.version}")
        if v is None or v.offer_id != c.offer_id or v.offer_version != c.offer_version:
            raise _refuse(Code.INSUFFICIENT_AUTHORITY, f"No verifier verdict backs commitment {c.id}")
        # F-07: the commitment must carry exactly what the verifier verified, at the value it verified:
        # the verdict's bound obligations or one of its counters. The stored offer row is never
        # consulted here, so replacing it after the verdict changes nothing that is committed.
        verified: list[tuple[str, int]] = []
        if v.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
            bound = committable(v.bound_obligations)
            if bound:
                verified.append((terms_hash(bound), verdict_forward_value(v)))
        if v.outcome in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL, Outcome.REJECT, Outcome.COUNTER):
            verified += [(terms_hash(committable(k.obligations)), k.forward_value_fen) for k in v.counters]
        allowed = any(hmac.compare_digest(h, c.terms_hash) and value == c.forward_value_fen for h, value in verified)
        if not allowed:
            raise _refuse(Code.INSUFFICIENT_AUTHORITY,
                          f"Verdict {v.id} ({v.outcome.value}) does not allow the terms of commitment {c.id}")

    def _tier2_reason(self, ctx: _Ctx) -> str:
        op, m = ctx.op, ctx.mandate
        assert m is not None
        if isinstance(op, AddFacility):
            return f"owner request to add facility {op.facility.id} ({op.facility.lender_id})"
        if isinstance(op, ApplyForFacility):
            return f"apply for facility {op.facility_id} ({fmt_yuan(op.amount_fen)})"
        if isinstance(op, GenerateBorrowerFile):
            return f"prepare the borrower file for {op.facility_id} (prepared, not sent)"
        if isinstance(op, DrawFacility | SubmitInvoiceForFinancing):
            return f"facility {op.facility_id} is not COMMITTED and owner-approved"
        if isinstance(op, ReceivePayment):
            return (f"receipt of {fmt_yuan(op.amount_fen)} on {op.receivable_id} reported by {op.requested_by}; "
                    f"only the bank feed or the owner records a receipt without confirmation")
        c = ctx.commitment
        if c is not None and has_terms_change(c):
            return f"commitment {c.id} lengthens payment terms"
        if c is not None and c.forward_value_fen > m.tier2_single_commitment_fen:
            return (f"commitment {c.id} of {fmt_yuan(c.forward_value_fen)} is above the Tier-2 threshold "
                    f"{fmt_yuan(m.tier2_single_commitment_fen)}")
        return "the verdict requires owner approval"

    # ================================================================ handlers (Tier 1, or owner-approved)

    def _handle(self, ctx: _Ctx) -> _Effect:
        op = ctx.op
        match op:
            case AcceptOffer() | RecordCommitment():
                return self._commit(ctx)
            case CounterOffer():
                return self._counter(op)
            case RejectOffer():
                codes = ", ".join(c.value for c in op.reason_codes) or "none"
                return _Effect(f"Offer {op.offer_id} rejected (reasons: {codes})")
            case DrawFacility():
                return self._draw(op, ctx)
            case RepayFacility():
                return self._repay(op, ctx)
            case SubmitInvoiceForFinancing():
                return self._finance(op, ctx)
            case ReceivePayment():
                return self._receive(op, ctx)
            case AddFacility():
                return self._add_facility(op, ctx)
            case ApplyForFacility():
                return self._apply(op, ctx)
            case GenerateBorrowerFile():
                _facility(ctx.state, op.facility_id)
                return _Effect(f"Borrower file for {op.facility_id} authorised: prepared, not sent")
            case RequestOwnerApproval():
                return self._request_approval(op)
        raise _refuse(Code.INSUFFICIENT_AUTHORITY, f"No handler for {getattr(op, 'kind', type(op).__name__)}")

    def _check_binding(self, ctx: _Ctx) -> None:
        """ADR-0006 section 5: a verdict is not standing authority. Re-check the commitment against the
        state and mandate at this moment; any failure refuses (and is logged like any refusal)."""
        c, v, m = ctx.commitment, ctx.verdict, ctx.mandate
        assert c is not None and m is not None
        state = ctx.state
        # 1. every named receivable is still owed (RI: ids are generated future invoices)
        by_id = {r.id: r for r in state.receivables}
        for o in c.obligations:
            rid = o.base.receivable_id
            if not rid or rid.startswith("RI:"):
                continue
            r = by_id.get(rid)
            status = r.status if r is not None else "absent from the books"
            if r is None or r.status not in ("OPEN", "FINANCED"):
                raise _refuse(Code.STALE_VERDICT, f"Receivable {rid} is {status}; re-evaluate the offer",
                              commitment_id=c.id, receivable_id=rid, status=status)
        # 2. exclusivity: one live commitment per named receivable
        mine = {o.base.receivable_id for o in c.obligations if o.base.receivable_id}
        for other in self._store.commitments():
            if other.id == c.id or other.status not in (CommitmentStatus.ACCEPTED, CommitmentStatus.ACTIVE):
                continue
            shared = sorted(mine & {o.base.receivable_id for o in other.obligations if o.base.receivable_id})
            if shared:
                raise _refuse(Code.CONFLICTING_COMMITMENT,
                              f"Commitment {c.id} and the earlier {other.status.value} commitment {other.id} both "
                              f"cover receivable {shared[0]}; the owner must revoke {other.id} first",
                              commitment_id=c.id, other_commitment_id=other.id, receivable_id=shared[0])
        # 3. caps, with the verifier's netting: this commitment adds its (non-negative) forward value
        booked = sum(fc.value_fen for fc in state.forward_concessions)
        cap = m.max_aggregate_forward_concession_fen
        if booked + c.forward_value_fen > cap:
            raise _refuse(Code.STALE_VERDICT,
                          f"Aggregate forward-concession cap would be exceeded: "
                          f"{fmt_yuan(booked + c.forward_value_fen)} vs {fmt_yuan(cap)}",
                          booked_fen=booked, this_fen=c.forward_value_fen, cap_fen=cap)
        buyer_cap = m.per_buyer_caps_fen.get(c.counterparty_id)
        if buyer_cap is not None:
            buyer_booked = sum(fc.value_fen for fc in state.forward_concessions
                               if fc.counterparty_id == c.counterparty_id)
            if buyer_booked + c.forward_value_fen > buyer_cap:
                raise _refuse(Code.STALE_VERDICT,
                              f"Per-buyer forward-concession cap for {c.counterparty_id} would be exceeded: "
                              f"{fmt_yuan(buyer_booked + c.forward_value_fen)} vs {fmt_yuan(buyer_cap)}",
                              booked_fen=buyer_booked, this_fen=c.forward_value_fen, cap_fen=buyer_cap,
                              counterparty_id=c.counterparty_id)
        # 4. the books moved since the verdict: the terms must still verify on today's books
        if v is not None and v.state_version != state.state_version and self._reverify is not None:
            try:
                outcome = self._reverify(c, state, m, ctx.now)
            except Exception:  # noqa: BLE001  fail closed: a hook that cannot evaluate refuses
                outcome = None
            if outcome not in (Outcome.ACCEPT, Outcome.NEEDS_OWNER_APPROVAL):
                raise _refuse(Code.STALE_VERDICT,
                              f"The books changed since verdict {v.id} (state v{v.state_version} \u2192 "
                              f"v{state.state_version}) and the terms no longer verify; re-evaluate",
                              verdict_id=v.id, verdict_state_version=v.state_version,
                              state_version=state.state_version, outcome=outcome.value if outcome else "none")

    def _commit(self, ctx: _Ctx) -> _Effect:
        c = ctx.commitment
        assert c is not None
        self._check_binding(ctx)
        try:
            if c.status == CommitmentStatus.PROPOSED:
                c = transition(c, CommitmentStatus.ACCEPTED, ctx.now)
            c = transition(c, CommitmentStatus.ACTIVE, ctx.now)
        except CommitmentError as exc:
            raise _refuse(Code.PRECONDITION_FAILED, str(exc)) from exc
        fc = ForwardConcession(id=f"FC-{c.id}", counterparty_id=c.counterparty_id, value_fen=c.forward_value_fen,
                               commitment_id=c.id, label=f"Commitment {c.id} on offer {c.offer_id} v{c.offer_version}")
        state = _bump(ctx.state, forward_concessions=[*ctx.state.forward_concessions, fc])
        return _Effect(f"Commitment {c.id} is ACTIVE; forward concession {fmt_yuan(c.forward_value_fen)} booked",
                       state=state, commitment=c, nonce=c.nonce)

    def _counter(self, op: CounterOffer) -> _Effect:
        v = self._store.get_verdict(op.source_verdict_id) if op.source_verdict_id else None
        if v is None or v.offer_id != op.offer_id:
            raise _refuse(Code.INSUFFICIENT_AUTHORITY, f"No verdict on offer {op.offer_id} backs this counter")
        counter = next((k for k in v.counters if k.id == op.counter_id), None)
        if counter is None:
            raise _refuse(Code.INSUFFICIENT_AUTHORITY, f"Counter {op.counter_id} is not in verdict {v.id}")
        return _Effect(counter.text)

    def _check_borrowing(self, ctx: _Ctx) -> None:
        assert ctx.mandate is not None
        if not ctx.mandate.allow_new_borrowing:
            raise _refuse(Code.INSUFFICIENT_AUTHORITY, "The mandate does not allow new borrowing")

    @staticmethod
    def _require_committed(f: Facility) -> None:
        if not (f.status == FacilityStatus.COMMITTED and f.owner_approved):
            raise _refuse(Code.UNCOMMITTED_FACILITY, f"Facility {f.id} is {f.status.value}; only a COMMITTED, "
                          f"owner-approved facility can be used", facility_id=f.id, status=f.status.value)

    def _draw(self, op: DrawFacility, ctx: _Ctx) -> _Effect:
        f = _facility(ctx.state, op.facility_id)
        self._require_committed(f)
        if f.kind in _NOT_DRAWABLE or f.repayment == Repayment.ON_RECEIPT:
            raise _refuse(Code.PRECONDITION_FAILED, f"Facility {f.id} ({f.kind.value}) cannot be drawn")
        self._check_borrowing(ctx)
        available = f.limit_fen - f.drawn_fen
        if op.amount_fen > available:
            raise _refuse(Code.PRECONDITION_FAILED,
                          f"Draw {fmt_yuan(op.amount_fen)} exceeds {f.id}'s available {fmt_yuan(available)}",
                          amount_fen=op.amount_fen, limit_fen=f.limit_fen, drawn_fen=f.drawn_fen)
        fee = upfront_fee(f, op.amount_fen)
        state = _bump(ctx.state, cash_fen=ctx.state.cash_fen + op.amount_fen - fee,
                      facilities=_with_facility(ctx.state, f.model_copy(update={"drawn_fen": f.drawn_fen + op.amount_fen})))
        fee_note = f", upfront fee {fmt_yuan(fee)}" if fee else ""
        return _Effect(f"Drew {fmt_yuan(op.amount_fen)} on {f.id} on day {ctx.now}{fee_note}", state=state)

    def _repay(self, op: RepayFacility, ctx: _Ctx) -> _Effect:
        f = _facility(ctx.state, op.facility_id)
        if f.repayment != Repayment.BULLET:
            raise _refuse(Code.PRECONDITION_FAILED, f"Facility {f.id} is repaid {f.repayment.value}, not on demand")
        if op.amount_fen > f.drawn_fen:
            raise _refuse(Code.PRECONDITION_FAILED,
                          f"Repayment {fmt_yuan(op.amount_fen)} exceeds {f.id}'s drawn {fmt_yuan(f.drawn_fen)}",
                          amount_fen=op.amount_fen, drawn_fen=f.drawn_fen)
        interest, left, parts = 0, op.amount_fen, []
        for day, remaining in open_lots(self._entries(), f.id, f.drawn_fen):
            if left == 0:
                break
            part = min(left, remaining)
            lot_interest = line_interest(part, f.rate_bp, ctx.now - day)
            interest += lot_interest
            parts.append(f"{fmt_yuan(part)} × {f.rate_bp}bp × {ctx.now - day}/365 = {fmt_yuan(lot_interest)}")
            left -= part
        total = op.amount_fen + interest
        if total > ctx.state.cash_fen:
            raise _refuse(Code.PRECONDITION_FAILED,
                          f"Repayment plus interest {fmt_yuan(total)} exceeds cash {fmt_yuan(ctx.state.cash_fen)}")
        state = _bump(ctx.state, cash_fen=ctx.state.cash_fen - total,
                      facilities=_with_facility(ctx.state, f.model_copy(update={"drawn_fen": f.drawn_fen - op.amount_fen})))
        return _Effect(f"Repaid {fmt_yuan(op.amount_fen)} on {f.id} with interest {fmt_yuan(interest)} "
                       f"({'; '.join(parts)})", state=state)

    def _finance(self, op: SubmitInvoiceForFinancing, ctx: _Ctx) -> _Effect:
        state = ctx.state
        f = _facility(state, op.facility_id)
        if f.kind != FacilityKind.INVOICE_FINANCING:
            raise _refuse(Code.PRECONDITION_FAILED, f"Facility {f.id} is not an invoice-financing facility")
        self._require_committed(f)
        self._check_borrowing(ctx)
        r = next((r for r in state.receivables if r.id == op.receivable_id), None)
        if r is None:
            raise _refuse(Code.PRECONDITION_FAILED, f"Receivable {op.receivable_id} does not exist")
        if r.status != "OPEN":
            raise _refuse(Code.PRECONDITION_FAILED, f"Receivable {r.id} is {r.status}, not OPEN")
        if not r.confirmed:
            raise _refuse(Code.PRECONDITION_FAILED, f"Receivable {r.id} is not buyer-confirmed (确权)")
        buyer = next((c for c in state.counterparties if c.id == r.counterparty_id), None)
        if buyer is None or buyer.role != "BUYER" or not buyer.known:
            raise _refuse(Code.UNKNOWN_COUNTERPARTY, f"Receivable {r.id} is not owed by a registered buyer",
                          SecurityEventKind.UNKNOWN_COUNTERPARTY)
        if ctx.now >= r.due_day:
            raise _refuse(Code.PRECONDITION_FAILED, f"Receivable {r.id} is due on day {r.due_day}; too late to finance")
        if f.advance_rate_bp is not None and op.advance_fen * 10_000 > f.advance_rate_bp * r.face_fen:
            raise _refuse(Code.PRECONDITION_FAILED,
                          f"Advance {fmt_yuan(op.advance_fen)} exceeds {f.advance_rate_bp}bp of {r.id}'s face "
                          f"{fmt_yuan(r.face_fen)}", advance_fen=op.advance_fen, face_fen=r.face_fen)
        available = f.limit_fen - f.drawn_fen
        if op.advance_fen > available:
            raise _refuse(Code.PRECONDITION_FAILED,
                          f"Advance {fmt_yuan(op.advance_fen)} exceeds {f.id}'s available {fmt_yuan(available)}")
        fee = upfront_fee(f, op.advance_fen)
        receivables = [x.model_copy(update={"status": "FINANCED"}) if x.id == r.id else x for x in state.receivables]
        new_state = _bump(state, cash_fen=state.cash_fen + op.advance_fen - fee, receivables=receivables,
                          facilities=_with_facility(state, f.model_copy(update={"drawn_fen": f.drawn_fen + op.advance_fen})))
        return _Effect(f"Advance {fmt_yuan(op.advance_fen)} on {r.id} from {f.id} on day {ctx.now}", state=new_state)

    def _receive(self, op: ReceivePayment, ctx: _Ctx) -> _Effect:
        state = ctx.state
        r = next((r for r in state.receivables if r.id == op.receivable_id), None)
        if r is None:
            raise _refuse(Code.PRECONDITION_FAILED, f"Receivable {op.receivable_id} does not exist")
        if r.status not in ("OPEN", "FINANCED"):
            raise _refuse(Code.PRECONDITION_FAILED, f"Receivable {r.id} is {r.status}; nothing is owed")
        if op.amount_fen > r.face_fen:
            raise _refuse(Code.PRECONDITION_FAILED,
                          f"Payment {fmt_yuan(op.amount_fen)} exceeds {r.id}'s face {fmt_yuan(r.face_fen)}")
        cash = state.cash_fen + op.amount_fen
        facilities = state.facilities
        note = ""
        if r.status == "FINANCED":
            found = advance_for(self._entries(), r.id)
            if found is None:
                raise _refuse(Code.PRECONDITION_FAILED, f"No executed advance on record for financed {r.id}")
            adv, adv_day = found
            f = _facility(state, adv.facility_id)
            days = ctx.now - adv_day
            interest, fee, periods = finance_invoice_charges(f, adv.advance_fen, days)
            cash -= adv.advance_fen + interest + fee
            facilities = _with_facility(state, f.model_copy(update={"drawn_fen": max(0, f.drawn_fen - adv.advance_fen)}))
            note = (f"; repaid advance {fmt_yuan(adv.advance_fen)} + interest {fmt_yuan(interest)} + fee "
                    f"{fmt_yuan(fee)} ({days} days billed as {periods} whole period(s)) to {f.id}")
        receivables = [x.model_copy(update={"status": "SETTLED"}) if x.id == r.id else x for x in state.receivables]
        new_state = _bump(state, cash_fen=cash, receivables=receivables, facilities=facilities)
        return _Effect(f"Received {fmt_yuan(op.amount_fen)} on {r.id}{note}", state=new_state)

    def _add_facility(self, op: AddFacility, ctx: _Ctx) -> _Effect:
        # Reached only for an owner-originated AddFacility the owner has approved (Tier 2).
        state = ctx.state
        if op.requested_by != Actor.OWNER:  # defence in depth; tier_for already made this Tier 3
            raise _refuse(Code.INSUFFICIENT_AUTHORITY, "Only the owner can add a facility", SecurityEventKind.TIER3)
        if any(f.id == op.facility.id for f in state.facilities):
            raise _refuse(Code.PRECONDITION_FAILED, f"Facility {op.facility.id} is already on the menu")
        fac = op.facility.model_copy(update={"owner_approved": True})
        counterparties = list(state.counterparties)
        if not any(c.id == fac.lender_id for c in counterparties):
            counterparties.append(Counterparty(id=fac.lender_id, name=fac.lender_id, role="LENDER", known=True))
        new_state = _bump(state, facilities=[*state.facilities, fac], counterparties=counterparties)
        return _Effect(f"Facility {fac.id} ({fac.status.value}) added to the funding menu by the owner", state=new_state)

    def _apply(self, op: ApplyForFacility, ctx: _Ctx) -> _Effect:
        f = _facility(ctx.state, op.facility_id)
        if f.status != FacilityStatus.NOT_APPLIED:
            raise _refuse(Code.PRECONDITION_FAILED, f"Facility {f.id} is {f.status.value}; nothing to apply for")
        new_state = _bump(ctx.state, facilities=_with_facility(ctx.state, f.model_copy(
            update={"status": FacilityStatus.PENDING})))
        return _Effect(f"Applied for {fmt_yuan(op.amount_fen)} on {f.id}; it is PENDING and counts as zero "
                       f"until committed", state=new_state)

    def _request_approval(self, op: RequestOwnerApproval) -> _Effect:
        entries = [e for e in self._entries() if e.op is not None and e.op.op_id == op.payload_op_id]
        if not entries:
            raise _refuse(Code.PRECONDITION_FAILED, f"Operation {op.payload_op_id} is not in the log")
        target = entries[-1]
        if any(e.result.status == EXECUTED for e in entries):
            raise _refuse(Code.PRECONDITION_FAILED, f"Operation {op.payload_op_id} was already executed")
        pending = [a for a in self._store.approvals(ApprovalStatus.PENDING) if a.op_id == op.payload_op_id]
        if pending:
            return _Effect(f"Already awaiting the owner ({pending[0].id})", status=PENDING, approval_id=pending[0].id)
        return _Effect(f"Owner approval requested: {op.subject}", status=PENDING,
                       approval=(canonical_json(target.op), op.subject))
