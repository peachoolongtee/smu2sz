# Concurrency and recovery certification of the TermsLedger backend

- **Date:** 3 Oct 2026, branch `test/concurrency-invariants` off `dev` at `919de9f`.
- **Question (from the audit):** the executor serialises with a process-local `threading.RLock`; could a second process double-book?
- **Answer:** yes, before this branch. With the fixes on this branch the store enforces the invariants itself, and two processes racing on one database end exactly as some serial order would. This is proven on SQLite (file database). PostgreSQL is **UNVERIFIED**: the same suite runs against it unchanged once `TERMSLEDGER_TEST_DATABASE_URL` is supplied.

Paths are relative to `services/api/` unless they start with `docs/`.

---

## 1. What was wrong

Measured, not inferred: the new suite was run against the original `app/persistence/` and `app/operations/executor.py` (from `dev`), with two worker processes on one SQLite file. 16 of the 20 SQLite cases failed:

| Race | What happened on `dev` |
| --- | --- |
| Two ¥100,000 draws against ¥150,000 of room | **both EXECUTED**: ¥200,000 drawn on a ¥150,000 line |
| Two ¥10,000 / ¥20,000 draws on the same books | both EXECUTED, `drawn_fen` ¥20,000 (one draw lost: a lost update) |
| One bank receipt, same idempotency key, twice | **both EXECUTED**: cash counted twice |
| One bank receipt, same `bank_reference`, two keys | both EXECUTED: cash counted twice |
| Accept versus revoke of one commitment | the revocation was logged EXECUTED but the commitment ended ACTIVE with its concession booked |
| Two `put_state` from the same version | both written; the second silently replaced the first |

Why. The process lock never protected anything beyond one process (and `Runtime.executor` builds a new `Executor`, so a new lock, on every access; only the API routes' `rt.lock` serialised calls within one process). Inside a unit of work every decision is made on reads taken without a lock (pysqlite only begins a transaction at the first write; PostgreSQL READ COMMITTED takes no read locks), and the writes were unconditional inserts: a new state row, and a log row whose `seq` was read inside the writer's own transaction once it held the write lock, so the chain stayed contiguous while the books under it diverged from any serial order.

## 2. What the store now enforces

The serialisation boundary is the organisation's books (one organisation in this product), enforced by the database:

1. **Compare-and-swap on the log head.** `SqlLedgerStore.transaction()` records the head `seq` when the unit begins; an append inside the unit must land on that head (then on its own previous append). A unit that overlapped another committed writer fails with `ConcurrentWriteConflict` and keeps nothing. Every executor entry point that decides something appends exactly one log entry, so any two overlapping decisions conflict: whatever the second one read, it can only commit if nothing committed since it began. The `seq` primary key is the backstop when both append at once (`IntegrityError`, mapped to `ConcurrentWriteConflict`). The chain's `prev_hash` therefore stays contiguous by construction, not by luck.
2. **Compare-and-swap on the state.** `put_state(state, expected_version=v)` (both stores) refuses with `StateVersionConflict` unless the current stored state is version `v`. SQL: the organisation row is locked `FOR UPDATE` (PostgreSQL; SQLite renders no clause), the row is inserted, and the previous row's version is checked while the write lock is held. The executor writes every state it computes this way (`_run`, `revoke_commitment`). Without `expected_version` the write is unconditional as before (fixtures, seeding, the clock).
3. **Unique keys claimed by a concurrent writer are a conflict, not an answer.** Inside a unit, an `IntegrityError` after the unit's own check found the key free (a nonce, an approval id) is `ConcurrentWriteConflict`; outside a unit the old behaviour stands (`NonceAlreadyUsed`, bounded retries).
4. **SQLite `BEGIN IMMEDIATE`.** On a file database a unit of work takes the write lock when it begins, so writers queue (30 s busy timeout) and compare-and-swap is the backstop. `SqlLedgerStore(..., sqlite_begin="deferred")` turns this off for the tests, to force the PostgreSQL-like interleaving. In-memory SQLite (one shared connection) is unchanged.
5. **The executor runs a lost unit again.** `Executor._atomically` wraps `execute`, `decide`, `revoke_commitment`, `reset_circuit` and `propose_commitment`: on `ConcurrentWriteConflict` (or SQLSTATE 40001 / 40P01, `is_retryable`) the unit, which kept nothing, runs again on the books as they now are, at most 8 times. The second of two concurrent draws is then refused for room, the second bank event is a DUPLICATE, and so on. No financial rule, admission check or tier changed; the in-memory store keeps its lock.

No schema change and no migration were needed; no dependency was added.

## 3. How it is proven

`tests/concurrency/` (harness, fixtures, `test_invariants.py`). Two long-lived **spawned worker processes** (separate interpreters, separate executor locks, separate engines) share a `multiprocessing.Barrier`. No sleeps: barriers and events only, every wait bounded (60 s).

Each test runs on three engines:

| Engine | Unit of work begins with | Rendezvous | What it proves |
| --- | --- | --- | --- |
| `sqlite-immediate` | `BEGIN IMMEDIATE` (shipped default) | `call`: both processes call the executor at the same instant | the shipped SQLite configuration serialises two processes |
| `sqlite-deferred` | nothing (reads take no lock) | `first-write`: inside the unit, after every read, both wait before their first write | the worst interleaving, where both have read the same `state_version` and log head; only the compare-and-swap can hold. The test asserts the loser really did run its unit again |
| `postgres` | READ COMMITTED | `first-write` | the same, on PostgreSQL. **Skipped unless `TERMSLEDGER_TEST_DATABASE_URL` is set** |

After every scenario (invariant 8) the committed actions are **replayed serially, in log order, on a fresh in-memory store seeded the same way**, and the concurrent books must be byte-identical to the serial ones: the same log entry hashes in the same order, the same state, commitments and approvals. Then: the chain verifies, `seq` is 1..n, the state versions written after seeding are consecutive, and their number equals the number of log entries whose unit wrote the state (each one EXECUTED, or a clock entry).

| # | Invariant | Test | sqlite-immediate | sqlite-deferred | postgres |
| --- | --- | --- | --- | --- | --- |
| 1 | two draws on the last room: one executes, the other is refused for room; `drawn_fen` never above the limit in any state version; lots sum to drawn | `test_1_...` | PROVEN | PROVEN | UNVERIFIED |
| 2 | receipt and invoice financing on one invoice: financed-then-paid repays the lender from the receipt; paid-then-financed refuses the financing; the invoice is settled once, the lender owed nothing, cash conserves | `test_2_...` | PROVEN | PROVEN | UNVERIFIED |
| 3 | accept versus revoke: one outcome; the forward concession is booked at most once in every state version; no concession or adjustment remains for the REVOKED commitment; the nonce is used iff the acceptance executed | `test_3_...` | PROVEN | PROVEN | UNVERIFIED |
| 4 | one bank event twice at once: same idempotency key gives EXECUTED + DUPLICATE; same `bank_reference` under two keys gives EXECUTED + REFUSED; cash counted once | `test_4a_...`, `test_4b_...` | PROVEN | PROVEN | UNVERIFIED |
| 5 | a log append that fails after the state write (owner approval; and a draw) while another process books: state, commitment, nonce and approval all roll back; the retry executes exactly once, a second decision is refused, a second retry is a DUPLICATE | `test_5_...` | PROVEN | PROVEN | UNVERIFIED |
| 6 | restart mid-approval: a process queues a Tier-2 acceptance, starts the owner's decision and is **killed** inside the unit (every write but the log entry done, nothing committed); the database shows none of it; two fresh processes hydrate the runtime with `get_runtime()` and decide at once: one decision, the other `ApprovalAlreadyDecided`; the operation runs once; the chain verifies | `test_6_...` | PROVEN | PROVEN | UNVERIFIED |
| 7 | two writers read the same `state_version` and both write: the second `put_state` is refused (`StateVersionConflict`), nothing is overwritten; two executors on one version lose no update (both draws land, version +2) | `test_7_...`, `test_7b_...` | PROVEN | PROVEN | UNVERIFIED |
| 8 | chain integrity: after every test above, plus a burst of 12 mixed operations from two processes (draws to the limit, one bank event twice, accept versus revoke) | `assert_serial_and_accounted`, `test_8_...` | PROVEN | PROVEN | UNVERIFIED |

Store-level contract tests in one process with two connections: `tests/persistence/test_concurrency_cas.py` (compare-and-swap on both stores, a lost compare-and-swap rolls back its unit, a moved log head refuses the append, `BEGIN IMMEDIATE` takes the lock when the unit begins while readers are not blocked, the executor runs a lost unit again, `is_retryable`).

The suite was run six times in a row without a failure (about 8 s per run on Windows).

## 4. Running it on PostgreSQL

```
TERMSLEDGER_TEST_DATABASE_URL=postgresql+psycopg://user:pass@host/termsledger_ci \
  SKIP_PERF_BENCH=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/concurrency
```

The suite refuses (fails, touching nothing) a database that already holds tables it did not create. An empty database is claimed by creating the marker table `termsledger_concurrency_marker`; from then on the suite drops and recreates its own tables before each test. Use a dedicated, empty database.

## 5. What remains UNVERIFIED or open

- **PostgreSQL**: every row above, until a URL is supplied. Specific points to watch there: the `FOR UPDATE` lock on the organisation row inside `put_state`; the `seq` primary-key collision aborting the transaction (it is raised as `ConcurrentWriteConflict` and the unit is rolled back before anything else runs); deadlocks (40P01) and serialization failures (40001) are retried, but none was observed.
- **The clock** (`app/clock`, read-only here): `advance` runs in one unit and appends, so it is protected by the log-head compare-and-swap, but it writes the state without `expected_version` and does not retry; two processes advancing at once make the loser raise `ConcurrentWriteConflict`. The runtime's `day` is also process-local: a second process on another day refuses operations as STALE_OPERATION.
- **The API** does not map `ConcurrentWriteConflict` (after 8 attempts) to an HTTP status; it would surface as a 500.
- **Reads outside a unit of work** (GET endpoints) read committed data statement by statement, so a page built from several reads can straddle a commit. No write invariant depends on it.
- **Writers outside the executor** (`put_offer`, `put_verdict`, security events written by NL or the API outside a unit) append nothing to the log and are not covered by the log-head compare-and-swap; none of them changes the books.
- **Throughput on SQLite**: `BEGIN IMMEDIATE` holds the write lock for the whole unit, including re-verification (about 0.5 to 0.9 s for EX01); other writers wait up to the 30 s busy timeout.
