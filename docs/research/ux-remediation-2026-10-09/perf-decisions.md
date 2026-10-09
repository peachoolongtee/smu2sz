# Decision reads: what they cost, and what was changed (map #65, ticket #87)

Branch `fix/debt-home-perf`, on `dev` at `c404512`. "Before" is `dev` at that head (a second worktree), "after" is this branch. Measured
9 and 10 Oct 2026 on one laptop (Apple silicon, CPython 3.12), in process (a `TestClient`, no network), the in-memory store,
`LLM_MODE=cache`. Wall times are the best of two or three repeats (one for the lots datasets) and move by a few milliseconds, and by up
to about 10 percent for the reads that run the funding router, from run to run; the counts do not.

## 1. The answer

At the sizes a demo or a first pilot reaches, no decision read is slow because of the decision record. `GET /decisions` took 5 to 13 ms
on the golden and public-record datasets of 3.1, 0.13 s with 200 decisions and 1,000 log entries, and 0.24 s with 100 decisions and 400
funding lots (almost all of it `alerts()`); `GET /ledger` took 7 to 14 ms (0.25 s at 1,000 log entries).
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
| Golden, day 34, no receipt | `queue` | 11 -> 12 ms | 1 -> 1 | 1 -> 1 | 2 -> 1 | 10 -> 5 |
| Golden, day 34, no receipt | `ledger` | 12 -> 14 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 21 -> 21 |
| Golden, day 34, half receipt | `decisions` | 11 -> 13 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 6 -> 6 |
| Golden, day 34, half receipt | `home` | 26 -> 18 ms | 4 -> 1 | 2 -> 1 | 3 -> 1 | 18 -> 6 |
| Golden, day 34, half receipt | `queue` | 11 -> 13 ms | 1 -> 1 | 1 -> 1 | 2 -> 1 | 12 -> 6 |
| Golden, day 34, half receipt | `ledger` | 12 -> 14 ms | 2 -> 1 | 1 -> 1 | 1 -> 1 | 25 -> 25 |
| Golden, day 34, cure queued (no receipt) | `decisions` | 11 -> 13 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 9 -> 8 |
| Golden, day 34, cure queued (no receipt) | `home` | 127 -> 126 ms | 4 -> 1 | 2 -> 1 | 3 -> 1 | 22 -> 9 |
| Golden, day 34, cure queued (no receipt) | `queue` | 123 -> 123 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 17 -> 10 |
| Golden, day 34, cure queued (no receipt) | `ledger` | 12 -> 14 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 28 -> 27 |
| Golden, day 34, half receipt, cure queued | `decisions` | 11 -> 12 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 10 -> 9 |
| Golden, day 34, half receipt, cure queued | `home` | 128 -> 128 ms | 4 -> 1 | 2 -> 1 | 3 -> 1 | 25 -> 10 |
| Golden, day 34, half receipt, cure queued | `queue` | 124 -> 123 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 19 -> 11 |
| Golden, day 34, half receipt, cure queued | `ledger` | 12 -> 14 ms | 2 -> 1 | 1 -> 1 | 1 -> 1 | 32 -> 31 |
| Public SME, 8 clock weeks | `decisions` | 5 -> 5 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 8 -> 8 |
| Public SME, 8 clock weeks | `home` | 14 -> 10 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 24 -> 8 |
| Public SME, 8 clock weeks | `queue` | 5 -> 5 ms | 1 -> 1 | 1 -> 1 | 2 -> 1 | 16 -> 8 |
| Public SME, 8 clock weeks | `ledger` | 7 -> 7 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 32 -> 32 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `decisions` | 5 -> 6 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 24 -> 14 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `home` | 731 -> 807 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 46 -> 16 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `queue` | 759 -> 794 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 38 -> 18 |
| Public SME, 8 weeks, 4 offers, 2 approvals pending | `ledger` | 7 -> 9 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 54 -> 44 |

(The public-record books are the dry pilot's: `fixtures/scenarios/public_sme.json` with `public_sme.mandate.json`, a fresh in-memory store
built as `scripts/pilot_runtime.py` does, `Runtime.advance_to(day + 7)` eight times as `scripts/pilot_dry_run.py` does. The books cannot cure
their reserve breach (no committed facility restores it), so there is no cure to queue; the last rows add four offers (each reads "no
verdict": the free text is not in the compiler cache) and two `APPLY_FOR_FACILITY` approvals left pending.)

### 3.2 Growing the log: the work per read, before and after

Golden books; the log grows with refused Tier-3 operations (no funding lots), and the decisions with pending `APPLY_FOR_FACILITY`
approvals. Each size is one dataset.

| Decisions, log entries | Read | Wall time | reconcile | alerts | log parses | json.loads |
| --- | --- | --- | --- | --- | --- | --- |
| 12, 62 | `decisions` | 6 -> 6 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 218 -> 86 |
| 50, 250 | `decisions` | 15 -> 9 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 2,800 -> 350 |
| 100, 500 | `decisions` | 41 -> 13 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 10,600 -> 700 |
| 200, 1,000 | `decisions` | 131 -> 21 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 41,200 -> 1,400 |
| 12, 62 | `home` | 85 -> 94 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 354 -> 98 |
| 50, 250 | `home` | 121 -> 111 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 3,350 -> 400 |
| 100, 500 | `home` | 178 -> 145 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 11,700 -> 800 |
| 200, 1,000 | `home` | 352 -> 213 ms | 2 -> 1 | 2 -> 1 | 3 -> 1 | 43,400 -> 1,600 |
| 12, 62 | `queue` | 43 -> 41 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 304 -> 110 |
| 50, 250 | `queue` | 56 -> 46 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 3,150 -> 450 |
| 100, 500 | `queue` | 86 -> 52 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 11,300 -> 900 |
| 200, 1,000 | `queue` | 182 -> 69 ms | 1 -> 1 | 2 -> 1 | 2 -> 1 | 42,600 -> 1,800 |
| 12, 62 | `ledger` | 14 -> 15 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 404 -> 272 |
| 50, 250 | `ledger` | 46 -> 40 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 3,550 -> 1,100 |
| 100, 500 | `ledger` | 101 -> 75 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 12,100 -> 2,200 |
| 200, 1,000 | `ledger` | 250 -> 146 ms | 1 -> 1 | 1 -> 1 | 1 -> 1 | 44,200 -> 4,400 |

Before, the parses were about decisions times (log entries plus approvals): doubling the decisions and the log (100 to 200 decisions,
500 to 1,000 entries) quadrupled them (10,600 to 41,200). After, the decision derivation reads each stored record once and the remaining parses are the ledger's own
per-row reads: 86, 350, 700, 1,400 for `decisions`, doubling when the records double. `tests/decisions/test_index.py` pins this: deriving D
decisions identifies each log entry and each approval once, whatever D is.

What is left in `GET /decisions` at 100 decisions is the engine: under `cProfile` 0.45 of 0.46 s is `alerts()` (the cure search and the
projection), and the derivation itself is not in the first fourteen lines.

### 3.3 Funding lots

The same sizes with executed `DRAW_FACILITY` operations, which make one funding lot each (50, 200 and 400 lots), measured on `dev` and
on this branch. The decision record's share fell, the rest is the engine and unchanged.

| Decisions, log entries, lots | Read | Wall time | reconcile | alerts | log parses | json.loads |
| --- | --- | --- | --- | --- | --- | --- |
| 12, 62, 50 | `decisions` | 0.02 -> 0.02 s | 1 -> 1 | 1 -> 1 | 1 -> 1 | 219 -> 87 |
| 50, 250, 200 | `decisions` | 0.09 -> 0.07 s | 1 -> 1 | 1 -> 1 | 1 -> 1 | 2,801 -> 351 |
| 100, 500, 400 | `decisions` | 0.24 -> 0.21 s | 1 -> 1 | 1 -> 1 | 1 -> 1 | 10,601 -> 701 |
| 12, 62, 50 | `home` | 0.92 -> 0.94 s | 2 -> 1 | 2 -> 1 | 3 -> 1 | 355 -> 99 |
| 50, 250, 200 | `home` | 4.46 -> 4.58 s | 2 -> 1 | 2 -> 1 | 3 -> 1 | 3,351 -> 401 |
| 100, 500, 400 | `home` | 12.69 -> 12.10 s | 2 -> 1 | 2 -> 1 | 3 -> 1 | 11,701 -> 801 |
| 12, 62, 50 | `queue` | 0.46 -> 0.46 s | 1 -> 1 | 2 -> 1 | 2 -> 1 | 305 -> 111 |
| 50, 250, 200 | `queue` | 2.29 -> 2.30 s | 1 -> 1 | 2 -> 1 | 2 -> 1 | 3,151 -> 451 |
| 100, 500, 400 | `queue` | 6.52 -> 6.16 s | 1 -> 1 | 2 -> 1 | 2 -> 1 | 11,301 -> 901 |
| 12, 62, 50 | `ledger` | 0.04 -> 0.02 s | 1 -> 1 | 1 -> 1 | 1 -> 1 | 405 -> 273 |
| 50, 250, 200 | `ledger` | 0.10 -> 0.10 s | 1 -> 1 | 1 -> 1 | 1 -> 1 | 3,551 -> 1,101 |
| 100, 500, 400 | `ledger` | 0.28 -> 0.24 s | 1 -> 1 | 1 -> 1 | 1 -> 1 | 12,101 -> 2,201 |

The home and the queue take the same time before and after to within run-to-run noise: they are the router (section 5).

## 4. No figure changed

On `dev` at `c404512` the responses of the four reads (English) were written to JSON for: the golden books at day 34 without a receipt
and with the half receipt, each before and after the cure was queued; the public-record books after eight weeks and again with four
offers and two pending approvals; the growth datasets of 3.2 (12, 50, 100 and 200 decisions); and the scale walk (5, 20 and 80 offers).
The same walks were written again on this branch and compared, with the random ids (commitment ids, nonces, hashes, which differ run to
run even on unchanged code) renamed by first appearance:

- all 52 files are identical for `decisions`, `queue` and `ledger`;
- for `home`, identical except for the new keys `id`, `receivable_id`, `commitment_id`, `decision_id` and `superseded_by` on each row of
  `changes` (ticket #85), which are additive.

(An earlier baseline taken on `bbfbdb4` differed in the queue cards of pending direct operations, which gained their stored quote from
tickets #83 and #84 on `dev`; the comparison above is against `c404512`, which has them.)

`perf-compare.py` does the comparison. The golden trajectory and router-plan digests (`tests/books/test_modules_on_books.py`) are
unchanged.

One sentence did change, on purpose, in Chinese only: with the home in Chinese, the change row of a promise kept in part
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
