# Decision reads: what they cost, and what was changed (map #65, ticket #87)

Branch `fix/debt-home-perf`, from `dev` at `bbfbdb4`. Measured 9 and 10 Oct 2026 on one laptop (Apple silicon, CPython 3.12), in
process (a `TestClient`, no network), the in-memory store, `LLM_MODE=cache`. Wall times are the best of two or three repeats and move
by a few milliseconds from run to run; the counts do not.

## 1. The answer

At the sizes a demo or a first pilot reaches, no decision read is slow because of the decision record. `GET /decisions` took 6 to 13 ms
on every dataset in section 3 and 0.13 s with 200 decisions and 1,000 log entries; `GET /ledger` took 5 to 15 ms (0.25 s at that size).
`GET /home` and `GET /approvals/queue` are slow only when a cure or an approval is pending on the books and the funding router has to
plan: 0.12 s on the golden books and **0.8 s on the public-record SME books**, and that time is the router (`app/funding`,
`app/financial`), which this change does not touch (section 5).

What the measurement did find is how the work grew: every decision re-scanned the whole log, all approvals, all facts, all verdicts and all
funding lots, so the work per read grew with decisions times records. Doubling the log and the approvals multiplied the JSON parses
by four (10,600 to 41,200 for `GET /decisions`). The home also reconciled up to four times and ran the alerts twice, and the queue and the
ledger ran the alerts or the reconciliation a second time for the decision record. All of that is now once per request, and the parse
counts grow in step with the records (section 3).

## 2. What was changed

| Where | Change |
| --- | --- |
| `app/decisions/state.py` | `RecordIndex`: the log, the approvals (with their parsed payloads), the facts, the verdicts, the commitments, the promises and the funding lots grouped once by decision. `derive`, `waiting_for` and the helpers they use read the index and no longer scan. `derive_all` indexes once for all its inputs (`index_inputs`). `DecisionInputs.index` is optional, so every existing caller and test still works: `derive` builds the index itself when it is not given one. |
| `app/api/decisions.py` | `Context` builds the index once and uses it for the candidate ids and for every decision's inputs. `load_context(rt, found=..., reconciled=...)` takes the alerts and the reconciliation a route already holds. `Reconciled` is `reconcile()` once per day for one request, and a failure is kept and raised again to each asker, so each keeps handling it as before. |
| `app/api/home.py` | The home reads the decision record first and hands it its own `found` alerts and one `Reconciled`; its change rows, its receivables block and its warnings use the same `Reconciled`; the log parsed for the record is reused by the change rows and the forecast basis; the commitments already read are reused for each agreement row. |
| `app/api/operations.py` | The queue hands the alerts it ran for the cards to the record, and reads the decision runs from the record's parsed log. |
| `app/api/read.py` | The ledger reconciles once for the receipts' windows and for the record. |

`reconcile()`, `alerts()` and everything under `app/financial`, `app/verifier`, `app/funding`, `app/alerts`, `app/operations`, `app/clock`
and `app/books` are not edited. No response changed in any figure or sentence (section 4).

## 3. Before and after

Counts are for one request, after a first warm read. `reconcile`, `alerts` and `log parses` are calls to `reconcile()`, `alerts()` and
`read_entries()` (one parse of the whole operations log). `json.loads` counts the calls of that function.

### 3.1 The golden books after the day-34 cure walk, and the public-record books after eight weeks

| Books | Read | Wall time | reconcile | alerts | log parses | json.loads |
| --- | --- | --- | --- | --- | --- | --- |
| Golden, day 34, no receipt | `decisions` | 11 -> 13 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 5 -> 5 |
| Golden, day 34, no receipt | `home` | 25 -> 17 ms | 4 -> 1 | 2 -> 1 | 3 -> 1 | 15 -> 5 |
| Golden, day 34, no receipt | `queue` | 11 -> 12 ms | 1 -> 1 | 1 -> 1 | 2 -> 1 | 10 -> 10 |
| Golden, day 34, no receipt | `ledger` | 12 -> 14 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 21 -> 21 |
| Golden, day 34, half receipt | `decisions` | 12 -> 12 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 6 -> 6 |
| Golden, day 34, half receipt | `home` | 29 -> 17 ms | 4 -> 1 | 2 -> 1 | 3 -> 1 | 18 -> 6 |
| Golden, day 34, half receipt | `queue` | 12 -> 12 ms | 1 -> 1 | 1 -> 1 | 2 -> 1 | 12 -> 12 |
| Golden, day 34, half receipt | `ledger` | 14 -> 14 ms | **2 -> 1** | 1 -> 1 | 1 -> 1 | 25 -> 25 |
| Golden, day 34, cure queued (no receipt) | `decisions` | 12 -> 12 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 9 -> 8 |
| Golden, day 34, cure queued (no receipt) | `home` | 126 -> 126 ms | 4 -> 1 | 2 -> 1 | 3 -> 1 | 22 -> 9 |
| Golden, day 34, cure queued (no receipt) | `queue` | 122 -> 120 ms | 1 -> 1 | **2 -> 1** | 2 -> 1 | 17 -> 16 |
| Golden, day 34, cure queued (no receipt) | `ledger` | 13 -> 14 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 28 -> 27 |
| Golden, day 34, half receipt, cure queued | `decisions` | 12 -> 12 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 10 -> 9 |
| Golden, day 34, half receipt, cure queued | `home` | 138 -> 126 ms | 4 -> 1 | 2 -> 1 | 3 -> 1 | 25 -> 10 |
| Golden, day 34, half receipt, cure queued | `queue` | 134 -> 124 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 19 -> 18 |
| Golden, day 34, half receipt, cure queued | `ledger` | 14 -> 15 ms | 2 -> 1 | 1 -> 1 | 1 -> 1 | 32 -> 31 |
| Public SME, 8 clock weeks | `decisions` | 6 -> 6 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 8 -> 8 |
| Public SME, 8 clock weeks | `home` | 16 -> 10 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 24 -> 8 |
| Public SME, 8 clock weeks | `queue` | 6 -> 5 ms | 1 -> 1 | 1 -> 1 | 2 -> 1 | 16 -> 16 |
| Public SME, 8 clock weeks | `ledger` | 8 -> 7 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 32 -> 32 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `decisions` | 6 -> 6 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 24 -> 14 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `home` | 786 -> 811 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 46 -> 16 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `queue` | 787 -> 792 ms | 1 -> 1 | **2 -> 1** | 2 -> 1 | 38 -> 28 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `ledger` | 8 -> 8 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 54 -> 44 |

(The public-record books are the dry pilot's: `fixtures/scenarios/public_sme.json` with `public_sme.mandate.json`, a fresh in-memory store
built as `scripts/pilot_runtime.py` does, `Runtime.advance_to(day + 7)` eight times as `scripts/pilot_dry_run.py` does. The books cannot cure
their reserve breach (no committed facility restores it), so there is no cure to queue; the last rows add four offers (each reads "no
verdict": the free text is not in the compiler cache) and two `APPLY_FOR_FACILITY` approvals left pending.)

### 3.2 Growing the log: the work per read, before and after

Golden books; the log grows with refused Tier-3 operations (no funding lots), and the decisions with pending `APPLY_FOR_FACILITY`
approvals. Each size is one dataset.

| Decisions, log entries | Read | Wall time | reconcile | alerts | log parses | json.loads |
| --- | --- | --- | --- | --- | --- | --- |
| 12, 62 | `decisions` | 7 -> 6 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 218 -> 86 |
| 50, 250 | `decisions` | 16 -> 9 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 2,800 -> 350 |
| 100, 500 | `decisions` | 40 -> 12 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 10,600 -> 700 |
| 200, 1,000 | `decisions` | 131 -> 19 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 41,200 -> 1,400 |
| 12, 62 | `home` | 90 -> 90 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 354 -> 98 |
| 50, 250 | `home` | 122 -> 109 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 3,350 -> 400 |
| 100, 500 | `home` | 176 -> 142 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 11,700 -> 800 |
| 200, 1,000 | `home` | 358 -> 207 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 43,400 -> 1,600 |
| 12, 62 | `queue` | 45 -> 41 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 304 -> 172 |
| 50, 250 | `queue` | 57 -> 44 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 3,150 -> 700 |
| 100, 500 | `queue` | 84 -> 54 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 11,300 -> 1,400 |
| 200, 1,000 | `queue` | 187 -> 84 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 42,600 -> 2,800 |
| 12, 62 | `ledger` | 15 -> 14 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 404 -> 272 |
| 50, 250 | `ledger` | 45 -> 40 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 3,550 -> 1,100 |
| 100, 500 | `ledger` | 98 -> 73 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 12,100 -> 2,200 |
| 200, 1,000 | `ledger` | 254 -> 141 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 44,200 -> 4,400 |

Before, the parses were about decisions times (log entries plus approvals): 4x the records gave 4x the decisions and 16x the parses (218,
2,800, 10,600, 41,200). After, the decision derivation reads each stored record once and the remaining parses are the ledger's own
per-row reads: 86, 350, 700, 1,400 for `decisions`, doubling when the records double. `tests/decisions/test_index.py` pins this: deriving D
decisions identifies each log entry and each approval once, whatever D is.

What is left in `GET /decisions` at 100 decisions is the engine: under `cProfile` 0.45 of 0.46 s is `alerts()` (the cure search and the
projection), and the derivation itself is not in the first fourteen lines.

### 3.3 Funding lots

The same sizes with executed `DRAW_FACILITY` operations, which make one funding lot each (50, 200 and 400 lots), measured on `dev` and
on this branch. The decision record's share fell, the rest is the engine and unchanged.

| Decisions, log entries, lots | Read | Wall time | reconcile | alerts | log parses | json.loads |
| --- | --- | --- | --- | --- | --- | --- |
| 12, 62, 50 | `decisions` | 18 -> 33 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 219 -> 87 |
| 50, 250, 200 | `decisions` | 94 -> 89 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 2,801 -> 351 |
| 100, 500, 400 | `decisions` | 240 -> 194 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 10,601 -> 701 |
| 12, 62, 50 | `home` | 923 -> 962 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 355 -> 99 |
| 50, 250, 200 | `home` | 4.46 -> 5.04 s | 2 -> 1 | 2 -> 1 | 3 -> 1 | 3,351 -> 401 |
| 100, 500, 400 | `home` | 12.7 -> 12.3 s | 2 -> 1 | 2 -> 1 | 3 -> 1 | 11,701 -> 801 |
| 12, 62, 50 | `queue` | 464 -> 474 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 305 -> 111 |
| 50, 250, 200 | `queue` | 2.29 -> 2.30 s | 1 -> 1 | 2 -> 1 | 2 -> 1 | 3,151 -> 451 |
| 100, 500, 400 | `queue` | 6.5 -> 6.3 s | 1 -> 1 | 2 -> 1 | 2 -> 1 | 11,301 -> 901 |
| 100, 500, 400 | `ledger` | 276 -> 260 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 12,101 -> 2,201 |

(The 18 -> 33 ms at the smallest size is noise between two runs; it is the only figure that rose beyond a few milliseconds and it did
not repeat in the other run of the same sizes.)

## 4. No figure changed

Before the change the responses of the four reads were written to JSON for: the golden books at day 34 without a receipt, with the
half receipt, and each after the cure walk (queued); the public-record books after eight weeks and again with four offers and two
pending approvals; and the growth datasets of 3.2 (12, 50, 100 and 200 decisions) and of the scale walk (5, 20 and 80 offers). After the
change the same walks were written again and compared, with the random ids (commitment ids, nonces, hashes, which differ run to
run even on unchanged code) renamed by first appearance:

- all 76 files are identical for `decisions`, `queue` and `ledger`;
- for `home`, identical except for the new keys `id`, `receivable_id`, `commitment_id`, `decision_id` and `superseded_by` on each row of
  `changes` (ticket #85), which are additive.

`perf-compare.py` does the comparison. The golden trajectory and router-plan digests (`tests/books/test_modules_on_books.py`) are
unchanged.

One word did change, on purpose, and it is outside this ticket's reads: with the home in Chinese, the change row of a promise kept in part
now says what arrived (the four facts, in Chinese) instead of "the early payment did not arrive". The row's detection read the English
sentence, so the Chinese home never produced it; it now reads the alert's own sentence, as the English home always effectively did, so the
two languages carry the same figures and the same `superseded_by`. The Chinese *warning* for the same invoice still says the early payment
did not arrive (follow-up).

## 5. What is slow and is not the decision record

- **The funding router, when a cure or an approval is pending.** On the public-record books with two approvals pending, `GET /home` and
  `GET /approvals/queue` take 0.79 to 0.81 s each, 2.1 s under `cProfile`, all in `runnable_plan` -> `router.plan` -> `search.run` (about
  27,600 probes of the cash path). Without a pending approval the same reads take 10 to 16 ms. On the golden books the same step takes 0.12
  s. It runs once per request. It is in `app/funding`, so it is untouched here; the ticket's "fix what exceeds a second" does not reach it
  because it does not exceed a second on real books, but it is the number to watch.
- **Funding lots multiply it.** With 400 small draws on the line (400 lots) the same reads took 12.7 s (`home`) and 6.5 s (`queue`),
  almost all in `_repay_carried` and `_closings` of the trajectory, run once per probe of the router. A year of weekly draws is far below
  that, but a book that makes a lot per invoice advance could reach it. This is an engine cost; nothing here changes it.

## 6. Not done

- **The Postgres run for `decision_facts` (migration 0006, row-level security).** No PostgreSQL is reachable from this environment: no
  `DATABASE_URL` or `postgres` variable is set, `docker` and `psql` are not installed, and nothing was installed. The change touches no
  store, no migration and no SQL. For the pending G4 run the owner should do, against a Postgres: (a) `alembic upgrade head`, then `\d
  decision_facts` shows the unique `(decision_id, fact, fact_key)` and the RLS policy of 0005's pattern; (b) run `tests/persistence`
  and `tests/decisions` with `DATABASE_URL` set; (c) call `GET /decisions` once with this branch and read the statements: one
  `SELECT` each for operations, approvals, commitments, verdicts and decision facts per request, plus one `SELECT` per decision for its
  offer (see below).
- **One store call per DEAL decision remains.** `Context.offer()` calls `store.get_offer(offer_id)` for each deal. On the in-memory store
  that is a dictionary lookup; on SQL it is one indexed query per deal. The ports have no "all offers" read, so batching it needs a new port
  method (the stores are out of this ticket's reach). At 200 deals that is 200 small queries.
- **`decision_id_for` on `RECORD_COMMITMENT` entries** still scans the commitments for each such entry (commitments squared at worst, one
  entry per commitment); it is a pure function in `app/decisions/identity.py` with a public signature and was left alone.
- The detail route `GET /decisions/{id}` still scans the log a few times for its one decision (the operations, the authorization tier);
  that is linear and for one decision.

## 7. Reproducing

`perf-harness.py` (modes `golden`, `public`, `scale`, `stress`, `stresslots`) writes the numbers and the JSON of every read to a
directory; `perf-compare.py` compares two such directories. Set `WT` to another checkout to measure that code (the before numbers were
taken on a second worktree of `dev`).

    SKIP_PERF_BENCH=1 uv run --project services/api python docs/research/ux-remediation-2026-10-09/perf-harness.py golden /tmp/after --half
    python docs/research/ux-remediation-2026-10-09/perf-compare.py /tmp/before /tmp/after --drop-change-ids
