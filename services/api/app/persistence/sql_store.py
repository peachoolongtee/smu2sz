"""SQLAlchemy 2 `LedgerStore`. SQLite for dev and tests, Postgres to deploy (ADR-0001).

Only portable Core constructs are used for data. The operations log is append-only: this class has
no update or delete for it, an engine hook refuses any Core/ORM UPDATE or DELETE aimed at
`operations` or `used_nonces`, and database triggers (`guards`, migration 0003) refuse any UPDATE or
DELETE there, textual SQL included (only `reset()` is allowed through). The hash chain is computed
in Python, so a row edited behind the store's back is caught by `verify_chain()`.

`transaction()` is the unit of work (F-01): every store call made inside it on the same thread runs
on one connection in one database transaction, committed together or rolled back together.

Concurrency (docs/research/concurrency-certification-2026-10-03.md). The serialisation boundary is the
organisation's books, enforced by the database, not by a process-local lock:

- compare-and-swap on the log head: a unit of work records the head `seq` when it begins, and its
  append must land on that head. Two units that overlap and both append cannot both commit: the
  later one gets `ConcurrentWriteConflict` (a moved head, or the `seq` primary key) and nothing of it
  is kept, so the chain's `prev_hash` stays contiguous and every unit sees what committed before it;
- compare-and-swap on the state: `put_state(state, expected_version=v)` refuses
  (`StateVersionConflict`) unless the current stored state is version `v`;
- inside a unit, a unique key another writer claimed between this unit's check and its write (a nonce,
  an approval id) is a `ConcurrentWriteConflict`, not a business answer; the caller runs the unit again;
- on a file SQLite database a unit of work starts with `BEGIN IMMEDIATE`, so writers queue on the
  database lock and the compare-and-swap is the backstop. `sqlite_begin="deferred"` turns that off: reads
  then take no lock (like PostgreSQL READ COMMITTED) and the compare-and-swap alone must hold; the
  concurrency tests run both.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import (
    Connection,
    CursorResult,
    Engine,
    Row,
    Table,
    create_engine,
    event,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.dml import Delete, Update

from app.domain.models import (
    Commitment,
    CompiledOffer,
    FinancialState,
    Mandate,
    SecurityEvent,
    Verdict,
)
from app.domain.ports import OperationRecord
from app.persistence import guards
from app.persistence import tables as t
from app.persistence.canonical import canonical_json
from app.persistence.chain import (
    GENESIS_HASH,
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
    AppendOnlyViolation,
    ApprovalAlreadyDecided,
    ConcurrentWriteConflict,
    NonceAlreadyUsed,
    NotFound,
    OfferVersionConflict,
    PersistenceError,
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

_RESET_OPTION = "termsledger_reset"
_PROTECTED = frozenset({t.operations.name, t.used_nonces.name, t.pilot_journal.name})
_RETRIES = 5

T = TypeVar("T")


def _sqlite_memory(database_url: str) -> bool:
    return database_url in {"sqlite://", "sqlite:///:memory:"} or "mode=memory" in database_url


def _make_engine(database_url: str) -> Engine:
    kwargs: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if _sqlite_memory(database_url):
            kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **kwargs)


def _guard_append_only(
    conn: Connection, clauseelement: Any, multiparams: Any, params: Any, execution_options: Mapping[str, Any]
) -> None:
    if not isinstance(clauseelement, (Update, Delete)):
        return
    name = getattr(getattr(clauseelement, "table", None), "name", None)
    if name not in _PROTECTED:
        return
    if clauseelement.get_execution_options().get(_RESET_OPTION) or execution_options.get(_RESET_OPTION):
        return
    raise AppendOnlyViolation(f"{name} is append-only; UPDATE/DELETE refused")


def _inserted_id(result: CursorResult[Any]) -> int:
    pk = result.inserted_primary_key
    if pk is None:
        raise PersistenceError("insert returned no primary key")
    return int(pk[0])


def _entry(row: Row[Any]) -> LedgerEntry:
    return LedgerEntry(
        seq=int(row.seq),
        op_id=row.op_id,
        kind=row.kind,
        idempotency_key=row.idempotency_key,
        payload_json=row.payload_json,
        result_json=row.result_json,
        prev_hash=row.prev_hash,
        entry_hash=row.entry_hash,
    )


def _approval(row: Row[Any]) -> ApprovalRecord:
    return ApprovalRecord(
        id=row.id,
        op_id=row.op_id,
        kind=row.kind,
        op_json=row.op_json,
        reason=row.reason,
        status=ApprovalStatus(row.status),
        decided_by=row.decided_by,
        decided_day=row.decided_day,
    )


class SqlLedgerStore:
    """Satisfies `app.domain.ports.LedgerStore`.

    `create_tables=True` runs `metadata.create_all` (idempotent) for tests and local dev; a
    deployment runs `alembic upgrade head` instead and may pass `create_tables=False`.
    """

    def __init__(
        self,
        database_url: str,
        *,
        create_tables: bool = True,
        engine: Engine | None = None,
        sqlite_begin: str = "immediate",
    ) -> None:
        if sqlite_begin not in {"immediate", "deferred"}:
            raise ValueError("sqlite_begin must be 'immediate' or 'deferred'")
        self.database_url = database_url
        self.engine = engine if engine is not None else _make_engine(database_url)
        # A file SQLite database shared by several connections or processes: a unit of work takes the
        # write lock when it begins. An in-memory one (one shared connection) cannot be contended.
        self._begin_immediate = (
            sqlite_begin == "immediate"
            and self.engine.dialect.name == "sqlite"
            and not _sqlite_memory(database_url)
        )
        self._local = threading.local()
        event.listen(self.engine, "before_execute", _guard_append_only)
        if create_tables:
            t.metadata.create_all(self.engine)
            with self.engine.begin() as conn:
                guards.install(conn)

    def dispose(self) -> None:
        self.engine.dispose()

    # ------------------------------------------------------------ unit of work

    def _tx(self) -> Connection | None:
        return getattr(self._local, "conn", None)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """One database transaction for every store call made inside the block on this thread.

        Commits when the block exits normally and rolls everything back if it raises. A nested
        block joins the open transaction (it does not commit on its own).

        The log head is read when the unit begins: an append inside the unit must land on it
        (compare-and-swap), so a unit that overlapped another committed writer fails with
        `ConcurrentWriteConflict` instead of committing decisions made on books that moved."""
        if self._tx() is not None:
            yield
            return
        with self.engine.begin() as conn:
            if self._begin_immediate:
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            self._local.conn = conn
            self._local.head = self._head_seq(conn)
            try:
                yield
            finally:
                self._local.conn = None
                self._local.head = None

    @staticmethod
    def _head_seq(conn: Connection) -> int:
        return int(conn.execute(select(func.max(t.operations.c.seq))).scalar() or 0)

    @contextmanager
    def _reading(self) -> Iterator[Connection]:
        conn = self._tx()
        if conn is not None:
            yield conn
            return
        with self.engine.connect() as c:
            yield c

    # ------------------------------------------------------------ helpers

    def _retry(
        self, fn: Callable[[Connection], T], on_conflict: Callable[[IntegrityError], Exception] | None = None
    ) -> T:
        conn = self._tx()
        if conn is not None:  # inside a unit of work: one attempt; a conflict fails the whole unit
            try:
                return fn(conn)
            except IntegrityError as exc:
                if on_conflict is not None:
                    raise on_conflict(exc) from exc
                # A unique key the unit's own reads found free was claimed by another writer.
                raise ConcurrentWriteConflict(f"a concurrent writer claimed a key first: {exc.orig}") from exc
        for attempt in range(_RETRIES):
            try:
                with self.engine.begin() as conn:
                    return fn(conn)
            except IntegrityError as exc:
                if on_conflict is not None:
                    raise on_conflict(exc) from exc
                if attempt == _RETRIES - 1:
                    raise
        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _upsert(conn: Connection, table: Table, key: Mapping[str, Any], values: Mapping[str, Any]) -> None:
        where = [table.c[k] == v for k, v in key.items()]
        exists = conn.execute(select(func.count()).select_from(table).where(*where)).scalar_one()
        if exists:
            if values:
                conn.execute(update(table).where(*where).values(**values))
        else:
            conn.execute(insert(table).values(**key, **values))

    def _read_all(self, table: Table, order: Any, *where: Any) -> list[Row[Any]]:
        with self._reading() as conn:
            return list(conn.execute(select(table).where(*where).order_by(order)))

    # ------------------------------------------------------------ operations log

    def append_operation(
        self, op_id: str, kind: str, idempotency_key: str, payload_json: str, result_json: str
    ) -> LedgerEntry:
        parse_json(payload_json, "payload_json")
        parse_json(result_json, "result_json")
        ops = t.operations

        def _append(conn: Connection) -> LedgerEntry:
            last = conn.execute(
                select(ops.c.seq, ops.c.entry_hash).order_by(ops.c.seq.desc()).limit(1)
            ).first()
            seq = 1 if last is None else int(last.seq) + 1
            in_unit = self._tx() is conn
            if in_unit and seq - 1 != self._local.head:
                raise ConcurrentWriteConflict(
                    f"the log head moved from seq {self._local.head} to seq {seq - 1} while this unit of work ran"
                )
            prev = GENESIS_HASH if last is None else last.entry_hash
            entry = LedgerEntry(
                seq=seq,
                op_id=op_id,
                kind=kind,
                idempotency_key=idempotency_key,
                payload_json=payload_json,
                result_json=result_json,
                prev_hash=prev,
                entry_hash=compute_entry_hash(prev, payload_json, result_json),
            )
            conn.execute(
                insert(ops).values(
                    seq=entry.seq,
                    op_id=entry.op_id,
                    kind=entry.kind,
                    idempotency_key=entry.idempotency_key,
                    payload_json=entry.payload_json,
                    result_json=entry.result_json,
                    prev_hash=entry.prev_hash,
                    entry_hash=entry.entry_hash,
                )
            )
            if in_unit:
                self._local.head = seq
            return entry

        return self._retry(_append)

    def find_by_idempotency_key(self, key: str) -> LedgerEntry | None:
        ops = t.operations
        with self._reading() as conn:
            row = conn.execute(
                select(ops).where(ops.c.idempotency_key == key).order_by(ops.c.seq).limit(1)
            ).first()
        return _entry(row) if row is not None else None

    def operations(self) -> list[OperationRecord]:
        return [_entry(r) for r in self._read_all(t.operations, t.operations.c.seq)]

    def verify_chain(self) -> bool:
        return verify_entries(self.operations())

    def nonce_used(self, nonce: str) -> bool:
        with self._reading() as conn:
            n = conn.execute(
                select(func.count()).select_from(t.used_nonces).where(t.used_nonces.c.nonce == nonce)
            ).scalar_one()
        return bool(n)

    def mark_nonce_used(self, nonce: str) -> None:
        nonces = t.used_nonces

        def _mark(conn: Connection) -> None:
            # Checked first so a replay inside a unit of work raises before any statement fails
            # (a failed statement would abort a Postgres transaction). The primary key still
            # refuses a concurrent duplicate.
            if conn.execute(select(func.count()).select_from(nonces).where(nonces.c.nonce == nonce)).scalar_one():
                raise NonceAlreadyUsed(nonce)
            conn.execute(insert(nonces).values(nonce=nonce))

        def _conflict(_exc: IntegrityError) -> Exception:
            # Inside a unit of work the check above found the nonce free, so the primary key was
            # claimed by a concurrent writer: run the unit again (it then sees the nonce as used).
            if self._tx() is not None:
                return ConcurrentWriteConflict(f"nonce {nonce} was claimed by a concurrent writer")
            return NonceAlreadyUsed(nonce)

        self._retry(_mark, on_conflict=_conflict)

    # ------------------------------------------------------------ commitments

    def put_commitment(self, c: Commitment) -> None:
        values = {
            "offer_id": c.offer_id,
            "offer_version": c.offer_version,
            "counterparty_id": c.counterparty_id,
            "verdict_id": c.verdict_id,
            "status": c.status.value,
            "terms_hash": c.terms_hash,
            "nonce": c.nonce,
            "expires_day": c.expires_day,
            "mandate_version": c.mandate_version,
            "forward_value_fen": c.forward_value_fen,
            "payload_json": canonical_json(c),
        }
        self._retry(lambda conn: self._upsert(conn, t.commitments, {"id": c.id}, values))

    def get_commitment(self, commitment_id: str) -> Commitment | None:
        rows = self._read_all(t.commitments, t.commitments.c.row_id, t.commitments.c.id == commitment_id)
        return Commitment.model_validate_json(rows[0].payload_json) if rows else None

    def commitments(self) -> list[Commitment]:
        return [
            Commitment.model_validate_json(r.payload_json)
            for r in self._read_all(t.commitments, t.commitments.c.row_id)
        ]

    # ------------------------------------------------------------ state and mandate (versioned rows)

    def get_state(self) -> FinancialState:
        rows = self._read_all(t.states, t.states.c.row_id.desc())
        if not rows:
            raise NotFound("no financial state stored")
        return FinancialState.model_validate_json(rows[0].payload_json)

    def state_history(self) -> list[FinancialState]:
        return [
            FinancialState.model_validate_json(r.payload_json)
            for r in self._read_all(t.states, t.states.c.row_id)
        ]

    def put_state(self, state: FinancialState, expected_version: int | None = None) -> None:
        """Store a new version of the books. With `expected_version` this is a compare-and-swap: it
        refuses (`StateVersionConflict`, nothing written) unless the current stored state is that
        version. Without it (fixtures, seeding) the write is unconditional, as before."""

        def _put(conn: Connection) -> None:
            if expected_version is not None:
                # PostgreSQL: the organisation's row lock queues compare-and-swap writers, so the check
                # below sees the state a concurrent writer committed. SQLite renders no FOR UPDATE: the
                # INSERT takes the database write lock before the check runs.
                conn.execute(
                    select(t.organizations.c.id).where(t.organizations.c.id == state.org_id).with_for_update()
                )
            res = conn.execute(
                insert(t.states).values(
                    org_id=state.org_id,
                    state_version=state.state_version,
                    as_of=state.as_of,
                    cash_fen=state.cash_fen,
                    monthly_ebitda_fen=state.monthly_ebitda_fen,
                    payload_json=canonical_json(state),
                )
            )
            state_row_id = _inserted_id(res)
            if expected_version is not None:
                current = conn.execute(
                    select(t.states.c.state_version)
                    .where(t.states.c.row_id != state_row_id)
                    .order_by(t.states.c.row_id.desc())
                    .limit(1)
                ).scalar()
                if current != expected_version:
                    raise StateVersionConflict(
                        f"state version {expected_version} expected but the stored books are version {current}"
                    )
            self._upsert(conn, t.organizations, {"id": state.org_id}, {})
            for cp in state.counterparties:
                self._upsert(
                    conn,
                    t.counterparties,
                    {"id": cp.id},
                    {
                        "org_id": state.org_id,
                        "name": cp.name,
                        "role": cp.role,
                        "known": cp.known,
                        "payload_json": canonical_json(cp),
                    },
                )
            for f in state.facilities:
                conn.execute(
                    insert(t.facilities).values(
                        state_row_id=state_row_id,
                        facility_id=f.id,
                        org_id=state.org_id,
                        kind=f.kind.value,
                        status=f.status.value,
                        lender_id=f.lender_id,
                        owner_approved=f.owner_approved,
                        limit_fen=f.limit_fen,
                        drawn_fen=f.drawn_fen,
                        rate_bp=f.rate_bp,
                        payload_json=canonical_json(f),
                    )
                )

        self._retry(_put)

    def get_mandate(self) -> Mandate:
        rows = self._read_all(t.mandates, t.mandates.c.row_id.desc())
        if not rows:
            raise NotFound("no mandate stored")
        return Mandate.model_validate_json(rows[0].payload_json)

    def mandate_history(self) -> list[Mandate]:
        return [
            Mandate.model_validate_json(r.payload_json)
            for r in self._read_all(t.mandates, t.mandates.c.row_id)
        ]

    def put_mandate(self, mandate: Mandate) -> None:
        def _put(conn: Connection) -> None:
            conn.execute(
                insert(t.mandates).values(
                    org_id=mandate.org_id,
                    version=mandate.version,
                    issued_day=mandate.issued_day,
                    expires_day=mandate.expires_day,
                    revoked=mandate.revoked,
                    min_cash_fen=mandate.min_cash_fen,
                    payload_json=canonical_json(mandate),
                )
            )
            self._upsert(conn, t.organizations, {"id": mandate.org_id}, {})

        self._retry(_put)

    # ------------------------------------------------------------ offers, verdicts, security events

    def put_offer(self, offer: CompiledOffer) -> None:
        ob = t.obligations

        def _put(conn: Connection) -> None:
            key = {"offer_id": offer.offer_id, "version": offer.version}
            existing = conn.execute(
                select(t.offers.c.payload_json).where(
                    t.offers.c.offer_id == offer.offer_id, t.offers.c.version == offer.version
                )
            ).first()
            if existing is not None and offer_fingerprint(
                CompiledOffer.model_validate_json(existing.payload_json)
            ) != offer_fingerprint(offer):
                raise OfferVersionConflict(
                    f"offer {offer.offer_id} v{offer.version} is already stored with other terms"
                )
            self._upsert(
                conn,
                t.offers,
                key,
                {
                    "counterparty_id": offer.counterparty_id,
                    "status": offer.status.value,
                    "received_day": offer.received_day,
                    "payload_json": canonical_json(offer),
                },
            )
            conn.execute(
                ob.delete().where(ob.c.offer_id == offer.offer_id, ob.c.offer_version == offer.version)
            )
            for o in offer.obligations:
                conn.execute(
                    insert(ob).values(
                        offer_id=offer.offer_id,
                        offer_version=offer.version,
                        obligation_id=o.id,
                        type=o.type.value,
                        counterparty_id=o.counterparty_id,
                        contingency=o.contingency.value,
                        rate_bp=o.rate_bp,
                        amount_fen=o.amount_fen,
                        days_delta=o.days_delta,
                        effective_day=o.effective_day,
                        payload_json=canonical_json(o),
                    )
                )

        self._retry(_put)

    def get_offer(self, offer_id: str, version: int | None = None) -> CompiledOffer | None:
        where = [t.offers.c.offer_id == offer_id]
        if version is not None:
            where.append(t.offers.c.version == version)
        rows = self._read_all(t.offers, t.offers.c.version.desc(), *where)
        return CompiledOffer.model_validate_json(rows[0].payload_json) if rows else None

    def put_verdict(self, verdict: Verdict) -> None:
        values = {
            "offer_id": verdict.offer_id,
            "offer_version": verdict.offer_version,
            "outcome": verdict.outcome.value,
            "required_tier": verdict.required_tier.value,
            "mandate_version": verdict.mandate_version,
            "state_version": verdict.state_version,
            "forward_concession_total_fen": verdict.forward_concession_total_fen,
            "payload_json": canonical_json(verdict),
        }
        self._retry(lambda conn: self._upsert(conn, t.verdicts, {"id": verdict.id}, values))

    def get_verdict(self, verdict_id: str) -> Verdict | None:
        rows = self._read_all(t.verdicts, t.verdicts.c.row_id, t.verdicts.c.id == verdict_id)
        return Verdict.model_validate_json(rows[0].payload_json) if rows else None

    def verdicts(self) -> list[Verdict]:
        return [Verdict.model_validate_json(r.payload_json) for r in self._read_all(t.verdicts, t.verdicts.c.row_id)]

    def add_security_event(self, event: SecurityEvent) -> None:
        self._retry(
            lambda conn: conn.execute(
                insert(t.security_events).values(
                    id=event.id,
                    day=event.day,
                    kind=event.kind.value,
                    counterparty_id=event.counterparty_id,
                    trace_id=event.trace_id,
                    payload_json=canonical_json(event),
                )
            )
        )

    def security_events(self) -> list[SecurityEvent]:
        return [
            SecurityEvent.model_validate_json(r.payload_json)
            for r in self._read_all(t.security_events, t.security_events.c.row_id)
        ]

    # ------------------------------------------------------------ approvals (Tier-2 queue)

    def add_approval(self, op_json: str, reason: str) -> str:
        parse_json(op_json, "op_json")
        op_id, kind = op_identity(op_json)

        def _add(conn: Connection) -> str:
            n = conn.execute(select(func.count()).select_from(t.approvals)).scalar_one()
            aid = approval_id(int(n) + 1)
            conn.execute(
                insert(t.approvals).values(
                    id=aid,
                    op_id=op_id,
                    kind=kind,
                    op_json=op_json,
                    reason=reason,
                    status=ApprovalStatus.PENDING.value,
                    decided_by=None,
                    decided_day=None,
                )
            )
            return aid

        return self._retry(_add)

    def get_approval(self, approval_id_: str) -> ApprovalRecord | None:
        rows = self._read_all(t.approvals, t.approvals.c.row_id, t.approvals.c.id == approval_id_)
        return _approval(rows[0]) if rows else None

    def approvals(self, status: ApprovalStatus | str | None = None) -> list[ApprovalRecord]:
        where = [] if status is None else [t.approvals.c.status == ApprovalStatus(status).value]
        return [_approval(r) for r in self._read_all(t.approvals, t.approvals.c.row_id, *where)]

    def decide_approval(self, approval_id_: str, approved: bool, by: str, day: int | None = None) -> ApprovalRecord:
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        a = t.approvals
        with self.transaction():
            conn = self._tx()
            assert conn is not None
            res = conn.execute(
                update(a)
                .where(a.c.id == approval_id_, a.c.status == ApprovalStatus.PENDING.value)
                .values(status=status.value, decided_by=str(by), decided_day=day)
            )
            row = conn.execute(select(a).where(a.c.id == approval_id_)).first()
        if row is None:
            raise NotFound(f"approval {approval_id_} not found")
        if res.rowcount == 0:
            raise ApprovalAlreadyDecided(f"approval {approval_id_} is {row.status}")
        return _approval(row)

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
        def _add(conn: Connection) -> int:
            res = conn.execute(
                insert(t.llm_calls).values(
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
            )
            return _inserted_id(res)

        return self._retry(_add)

    def llm_calls(self) -> list[LlmCallRecord]:
        return [
            LlmCallRecord(
                id=int(r.row_id),
                backend=r.backend,
                model=r.model,
                prompt_version=r.prompt_version,
                input_sha256=r.input_sha256,
                status=r.status,
                output_json=r.output_json,
                latency_ms=r.latency_ms,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cache_hit=bool(r.cache_hit),
                trace_id=r.trace_id,
                error=r.error,
            )
            for r in self._read_all(t.llm_calls, t.llm_calls.c.row_id)
        ]

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

        def _add(conn: Connection) -> int:
            res = conn.execute(
                insert(t.evaluation_runs).values(
                    suite=suite,
                    passed=passed,
                    failed=failed,
                    metrics_json=metrics_json,
                    git_sha=git_sha,
                    notes=notes,
                )
            )
            return _inserted_id(res)

        return self._retry(_add)

    def evaluation_runs(self) -> list[EvaluationRunRecord]:
        return [
            EvaluationRunRecord(
                id=int(r.row_id),
                suite=r.suite,
                passed=r.passed,
                failed=r.failed,
                metrics_json=r.metrics_json,
                git_sha=r.git_sha,
                notes=r.notes,
            )
            for r in self._read_all(t.evaluation_runs, t.evaluation_runs.c.row_id)
        ]

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
        """Append one entry. The table is append-only (an engine hook refuses Core UPDATE and DELETE on it, as for the
        operations log) and nothing here touches the books, the operations log or the hash chain."""
        recorded_at = datetime.now(UTC).isoformat()

        def _add(conn: Connection) -> PilotJournalRecord:
            seq = _inserted_id(
                conn.execute(
                    insert(t.pilot_journal).values(
                        week=week, sme=sme, answer=answer, flow_said=flow_said, snapshot_hash=snapshot_hash,
                        owner_did=owner_did, choice=choice, recorded_on=recorded_on, state_version=state_version,
                        day=day, recorded_at=recorded_at,
                    )
                )
            )
            return PilotJournalRecord(
                seq=seq, week=week, sme=sme, answer=answer, flow_said=flow_said, snapshot_hash=snapshot_hash,
                owner_did=owner_did, choice=choice, recorded_on=recorded_on, state_version=state_version, day=day,
                recorded_at=recorded_at,
            )

        return self._retry(_add)

    def pilot_journal(self) -> list[PilotJournalRecord]:
        """Every entry, oldest first."""
        return [
            PilotJournalRecord(
                seq=int(r.row_id), week=int(r.week), sme=r.sme, answer=r.answer, flow_said=r.flow_said,
                snapshot_hash=r.snapshot_hash, owner_did=r.owner_did, choice=r.choice, recorded_on=r.recorded_on,
                state_version=int(r.state_version), day=int(r.day), recorded_at=r.recorded_at,
            )
            for r in self._read_all(t.pilot_journal, t.pilot_journal.c.row_id)
        ]

    # ------------------------------------------------------------ evidence

    def export_evidence(self) -> str:
        entries = self.operations()
        text = build_evidence(entries)
        self._retry(
            lambda conn: conn.execute(
                insert(t.evidence_exports).values(
                    operations=len(entries),
                    head_hash=head_hash(entries),
                    chain_valid=verify_entries(entries),
                    content_sha256=content_sha256(text),
                    exported_at=datetime.now(UTC).isoformat(),
                )
            )
        )
        return text

    def evidence_exports(self) -> list[EvidenceExportRecord]:
        return [
            EvidenceExportRecord(
                id=int(r.row_id),
                operations=int(r.operations),
                head_hash=r.head_hash,
                chain_valid=bool(r.chain_valid),
                content_sha256=r.content_sha256,
                exported_at=r.exported_at,
            )
            for r in self._read_all(t.evidence_exports, t.evidence_exports.c.row_id)
        ]

    # ------------------------------------------------------------ reset

    def reset(self, include_telemetry: bool = False) -> None:
        """Clear the ledger (demo reset). LLM calls and evaluation runs survive unless asked.

        The append-only guard is lifted for this transaction only (`guards.lifted`): the other
        tables are cleared first, so the transaction is open before any trigger DDL runs, and the
        triggers are back in place before it commits."""
        keep = set() if include_telemetry else {table.name for table in t.TELEMETRY_TABLES}
        tables = [table for table in reversed(t.metadata.sorted_tables) if table.name not in keep]
        with self.transaction():
            conn = self._tx()
            assert conn is not None
            for table in tables:
                if table.name not in _PROTECTED:
                    conn.execute(table.delete())
            with guards.lifted(conn):
                for table in tables:
                    if table.name in _PROTECTED:
                        conn.execute(table.delete().execution_options(**{_RESET_OPTION: True}))
