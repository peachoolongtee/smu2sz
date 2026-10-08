"""In-memory `LedgerStore` for unit tests. Same semantics as `SqlLedgerStore`.

Stored contracts are frozen Pydantic models and log entries are frozen dataclasses, so nothing
handed out by this store can be used to change what it holds.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime

from app.domain.models import (
    Commitment,
    CompiledOffer,
    FinancialState,
    Mandate,
    SecurityEvent,
    Verdict,
)
from app.domain.ports import OperationRecord
from app.persistence.chain import (
    approval_id,
    build_evidence,
    compute_entry_hash,
    content_sha256,
    head_hash,
    offer_fingerprint,
    op_identity,
    parse_json,
    verify_entries,
)
from app.persistence.errors import (
    ApprovalAlreadyDecided,
    NonceAlreadyUsed,
    NotFound,
    OfferVersionConflict,
    StateVersionConflict,
)
from app.persistence.records import (
    ApprovalRecord,
    ApprovalStatus,
    EvaluationRunRecord,
    EvidenceExportRecord,
    LedgerEntry,
    LlmCallRecord,
    PilotJournalRecord,
)


class InMemoryLedgerStore:
    """Satisfies `app.domain.ports.LedgerStore`. Thread-safe via one lock."""

    # Every container the store mutates; `transaction()` snapshots and restores exactly these.
    _CONTAINERS = (
        "_ops", "_nonces", "_commitments", "_states", "_mandates", "_offers", "_verdicts",
        "_security_events", "_approvals", "_evidence_exports", "_llm_calls", "_evaluation_runs",
    )

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tx_depth = 0
        self._llm_calls: list[LlmCallRecord] = []
        self._evaluation_runs: list[EvaluationRunRecord] = []
        self._pilot_journal: list[PilotJournalRecord] = []  # kept by reset(), like telemetry; not in `_CONTAINERS`
        self._clear_ledger()

    # ------------------------------------------------------------ unit of work

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """One unit of work: every write inside it is kept together or none is (F-01).

        The outermost block holds the store lock and snapshots every container (shallow copies;
        the values are frozen), and restores them all if the block raises. Nested blocks join the
        outer one, as a nested `SqlLedgerStore.transaction()` joins the open DB transaction."""
        with self._lock:
            if self._tx_depth:
                self._tx_depth += 1
                try:
                    yield
                finally:
                    self._tx_depth -= 1
                return
            snapshot = {name: _copy(getattr(self, name)) for name in self._CONTAINERS}
            self._tx_depth = 1
            try:
                yield
            except BaseException:
                for name, value in snapshot.items():
                    setattr(self, name, value)
                raise
            finally:
                self._tx_depth = 0

    def _clear_ledger(self) -> None:
        self._ops: list[LedgerEntry] = []
        self._nonces: set[str] = set()
        self._commitments: dict[str, Commitment] = {}
        self._states: list[FinancialState] = []
        self._mandates: list[Mandate] = []
        self._offers: dict[tuple[str, int], CompiledOffer] = {}
        self._verdicts: dict[str, Verdict] = {}
        self._security_events: list[SecurityEvent] = []
        self._approvals: dict[str, ApprovalRecord] = {}
        self._evidence_exports: list[EvidenceExportRecord] = []

    # ------------------------------------------------------------ operations log

    def append_operation(
        self, op_id: str, kind: str, idempotency_key: str, payload_json: str, result_json: str
    ) -> LedgerEntry:
        parse_json(payload_json, "payload_json")
        parse_json(result_json, "result_json")
        with self._lock:
            prev = head_hash(self._ops)
            entry = LedgerEntry(
                seq=len(self._ops) + 1,
                op_id=op_id,
                kind=kind,
                idempotency_key=idempotency_key,
                payload_json=payload_json,
                result_json=result_json,
                prev_hash=prev,
                entry_hash=compute_entry_hash(prev, payload_json, result_json),
            )
            self._ops.append(entry)
            return entry

    def find_by_idempotency_key(self, key: str) -> LedgerEntry | None:
        with self._lock:
            return next((e for e in self._ops if e.idempotency_key == key), None)

    def operations(self) -> list[OperationRecord]:
        with self._lock:
            return list(self._ops)

    def verify_chain(self) -> bool:
        with self._lock:
            return verify_entries(self._ops)

    def nonce_used(self, nonce: str) -> bool:
        with self._lock:
            return nonce in self._nonces

    def mark_nonce_used(self, nonce: str) -> None:
        with self._lock:
            if nonce in self._nonces:
                raise NonceAlreadyUsed(nonce)
            self._nonces.add(nonce)

    # ------------------------------------------------------------ commitments

    def put_commitment(self, c: Commitment) -> None:
        with self._lock:
            self._commitments[c.id] = c

    def get_commitment(self, commitment_id: str) -> Commitment | None:
        with self._lock:
            return self._commitments.get(commitment_id)

    def commitments(self) -> list[Commitment]:
        with self._lock:
            return list(self._commitments.values())

    # ------------------------------------------------------------ state and mandate (versioned)

    def get_state(self) -> FinancialState:
        with self._lock:
            if not self._states:
                raise NotFound("no financial state stored")
            return self._states[-1]

    def put_state(self, state: FinancialState, expected_version: int | None = None) -> None:
        """Compare-and-swap with `expected_version`, as `SqlLedgerStore.put_state`. The store lock makes
        the check and the append one step; a unit of work holds the lock for its whole run."""
        with self._lock:
            if expected_version is not None:
                current = self._states[-1].state_version if self._states else None
                if current != expected_version:
                    raise StateVersionConflict(
                        f"state version {expected_version} expected but the stored books are version {current}"
                    )
            self._states.append(state)

    def state_history(self) -> list[FinancialState]:
        with self._lock:
            return list(self._states)

    def get_mandate(self) -> Mandate:
        with self._lock:
            if not self._mandates:
                raise NotFound("no mandate stored")
            return self._mandates[-1]

    def put_mandate(self, mandate: Mandate) -> None:
        with self._lock:
            self._mandates.append(mandate)

    def mandate_history(self) -> list[Mandate]:
        with self._lock:
            return list(self._mandates)

    # ------------------------------------------------------------ offers, verdicts, security events

    def put_offer(self, offer: CompiledOffer) -> None:
        """Store an offer version. An (offer_id, version) already stored with different economic
        content (counterparty or obligation terms) is refused: a version is immutable (F-07)."""
        with self._lock:
            key = (offer.offer_id, offer.version)
            existing = self._offers.get(key)
            if existing is not None and offer_fingerprint(existing) != offer_fingerprint(offer):
                raise OfferVersionConflict(f"offer {offer.offer_id} v{offer.version} is already stored with other terms")
            self._offers[key] = offer

    def get_offer(self, offer_id: str, version: int | None = None) -> CompiledOffer | None:
        with self._lock:
            if version is not None:
                return self._offers.get((offer_id, version))
            versions = [v for (oid, v) in self._offers if oid == offer_id]
            return self._offers[(offer_id, max(versions))] if versions else None

    def put_verdict(self, verdict: Verdict) -> None:
        with self._lock:
            self._verdicts[verdict.id] = verdict

    def get_verdict(self, verdict_id: str) -> Verdict | None:
        with self._lock:
            return self._verdicts.get(verdict_id)

    def verdicts(self) -> list[Verdict]:
        with self._lock:
            return list(self._verdicts.values())

    def add_security_event(self, event: SecurityEvent) -> None:
        with self._lock:
            self._security_events.append(event)

    def security_events(self) -> list[SecurityEvent]:
        with self._lock:
            return list(self._security_events)

    # ------------------------------------------------------------ approvals (Tier-2 queue)

    def add_approval(self, op_json: str, reason: str) -> str:
        parse_json(op_json, "op_json")
        op_id, kind = op_identity(op_json)
        with self._lock:
            aid = approval_id(len(self._approvals) + 1)
            self._approvals[aid] = ApprovalRecord(
                id=aid, op_id=op_id, kind=kind, op_json=op_json, reason=reason, status=ApprovalStatus.PENDING
            )
            return aid

    def get_approval(self, approval_id_: str) -> ApprovalRecord | None:
        with self._lock:
            return self._approvals.get(approval_id_)

    def approvals(self, status: ApprovalStatus | str | None = None) -> list[ApprovalRecord]:
        with self._lock:
            rows = list(self._approvals.values())
        if status is None:
            return rows
        wanted = ApprovalStatus(status)
        return [a for a in rows if a.status == wanted]

    def decide_approval(self, approval_id_: str, approved: bool, by: str, day: int | None = None) -> ApprovalRecord:
        with self._lock:
            current = self._approvals.get(approval_id_)
            if current is None:
                raise NotFound(f"approval {approval_id_} not found")
            if current.status != ApprovalStatus.PENDING:
                raise ApprovalAlreadyDecided(f"approval {approval_id_} is {current.status}")
            status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            decided = replace(current, status=status, decided_by=str(by), decided_day=day)
            self._approvals[approval_id_] = decided
            return decided

    # ------------------------------------------------------------ telemetry

    def record_llm_call(
        self,
        *,
        backend: str,
        model: str,
        prompt_version: str,
        input_sha256: str,
        status: str,
        output_json: str | None = None,
        latency_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_hit: bool = False,
        trace_id: str | None = None,
        error: str | None = None,
    ) -> int:
        with self._lock:
            rec = LlmCallRecord(
                id=len(self._llm_calls) + 1,
                backend=backend,
                model=model,
                prompt_version=prompt_version,
                input_sha256=input_sha256,
                status=status,
                output_json=output_json,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_hit=cache_hit,
                trace_id=trace_id,
                error=error,
            )
            self._llm_calls.append(rec)
            return rec.id

    def llm_calls(self) -> list[LlmCallRecord]:
        with self._lock:
            return list(self._llm_calls)

    def add_evaluation_run(
        self,
        *,
        suite: str,
        passed: int,
        failed: int,
        metrics_json: str = "{}",
        git_sha: str | None = None,
        notes: str = "",
    ) -> int:
        parse_json(metrics_json, "metrics_json")
        with self._lock:
            rec = EvaluationRunRecord(
                id=len(self._evaluation_runs) + 1,
                suite=suite,
                passed=passed,
                failed=failed,
                metrics_json=metrics_json,
                git_sha=git_sha,
                notes=notes,
            )
            self._evaluation_runs.append(rec)
            return rec.id

    def evaluation_runs(self) -> list[EvaluationRunRecord]:
        with self._lock:
            return list(self._evaluation_runs)

    # ------------------------------------------------------------ the pilot's journal (docs/pilot/JOURNAL_SPEC.md)

    def add_pilot_journal(
        self,
        *,
        week: int,
        sme: str,
        answer: str,
        flow_said: str,
        snapshot_hash: str,
        owner_did: str,
        choice: str,
        recorded_on: str,
        state_version: int,
        day: int,
    ) -> PilotJournalRecord:
        """Append one entry. Append-only: the store has no update or delete for it, and nothing here touches the books,
        the operations log or the hash chain."""
        with self._lock:
            rec = PilotJournalRecord(
                seq=len(self._pilot_journal) + 1, week=week, sme=sme, answer=answer, flow_said=flow_said,
                snapshot_hash=snapshot_hash, owner_did=owner_did, choice=choice, recorded_on=recorded_on,
                state_version=state_version, day=day, recorded_at=datetime.now(UTC).isoformat(),
            )
            self._pilot_journal.append(rec)
            return rec

    def pilot_journal(self) -> list[PilotJournalRecord]:
        """Every entry, oldest first."""
        with self._lock:
            return list(self._pilot_journal)

    # ------------------------------------------------------------ evidence

    def export_evidence(self) -> str:
        with self._lock:
            entries = list(self._ops)
            text = build_evidence(entries)
            self._evidence_exports.append(
                EvidenceExportRecord(
                    id=len(self._evidence_exports) + 1,
                    operations=len(entries),
                    head_hash=head_hash(entries),
                    chain_valid=verify_entries(entries),
                    content_sha256=content_sha256(text),
                    exported_at=datetime.now(UTC).isoformat(),
                )
            )
            return text

    def evidence_exports(self) -> list[EvidenceExportRecord]:
        with self._lock:
            return list(self._evidence_exports)

    # ------------------------------------------------------------ reset

    def reset(self, include_telemetry: bool = False) -> None:
        """Clear the ledger (demo reset). LLM calls and evaluation runs survive unless asked."""
        with self._lock:
            self._clear_ledger()
            if include_telemetry:
                self._llm_calls = []
                self._evaluation_runs = []
                self._pilot_journal = []


def _copy(value: object) -> object:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, set):
        return set(value)
    raise TypeError(f"cannot snapshot {type(value).__name__}")
