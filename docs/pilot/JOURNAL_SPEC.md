# The pilot journal: specification

For wayfinder map [#58](https://github.com/peachoolongtee/smu2sz/issues/58), ticket #60 item 3. The pilot journal is the
learning ledger's **outcome column**: for each answer FLOW gave in a pilot week, what FLOW said, and what the owner then did.
The first entries of the learning ledger are these records (`docs/STRATEGY_RESEARCH.md` section I, "The shadow pilot").

Status: specified and implemented behind `FEATURE_PILOT_JOURNAL` (default off). Its home was to be confirmed on grilling
[#59](https://github.com/peachoolongtee/smu2sz/issues/59); until the owner says otherwise it is a separate store table
with two owner-authenticated routes, so that moving it (to a file under `docs/pilot/`, say) later costs one module.

## 1. What it is, and what it is not

- **A record the owner makes.** One entry is one decision the owner took (or declined to take) against one answer in one week.
  Nothing writes an entry by itself: FLOW does not record, infer or score the owner.
- **Append-only.** There is no edit and no delete route. A correction is a new entry that says it corrects an earlier one in
  `owner_did`. The stores expose no update or delete for the table, and the SQL guard refuses a Core `UPDATE` or `DELETE`
  aimed at it.
- **Outside the engine.** The journal is a separate table (`pilot_journal`). It is never written to the financial state, never
  an operation, never in the hash-chained operations log, never an input to a verdict, a projection, a funding plan, an alert
  or the three answers' caches. Writing an entry does not change `state_version`, the operations count or the chain head
  (tests pin all three). The modules `app/financial`, `app/verifier`, `app/funding`, `app/alerts` and `app/operations` do not
  import the journal module (a test pins that).
- **Nothing acts.** The journal route does not execute, queue, approve or send anything. It does not read the books except to
  stamp the entry with the books' version and the clock's day.
- **No money.** An entry has no money field (`*_fen`, `*_bp`) and the read route's response carries none. The figures an
  answer showed are inside `flow_said` as the owner read them, and in the exported route file whose hash is `snapshot_hash`.
- **Not a place for real counterparty data.** `sme` is a label, never a company name. Counterparties in `flow_said` and
  `owner_did` are the anonymous labels the books used. The route refuses a free-text field holding a run of twelve or more
  digits (spaces and hyphens ignored), the shape of a bank account or card number; that is a backstop, not the control
  (`docs/pilot/RUNBOOK.md` section 5).

## 2. Where it lives

| Piece | Path |
| --- | --- |
| Flag | `FEATURE_PILOT_JOURNAL` (`Features.pilot_journal` in `services/api/app/config.py`), default **off** |
| Entry model, validation, the digit guard | `services/api/app/pilot/journal.py` |
| Routes | `services/api/app/api/pilot.py`, mounted in `app/main.py`; owner token on the router, `require_feature("pilot_journal")` first in each route |
| Table | `pilot_journal` in `services/api/app/persistence/tables.py`; migration `0005_pilot_journal.py`; a kept table (like telemetry): `reset()` leaves it unless asked to clear telemetry |
| Stores | `add_pilot_journal(...)` and `pilot_journal()` on `InMemoryLedgerStore` and `SqlLedgerStore`; the record is `PilotJournalRecord` in `app/persistence/records.py`. They are not in the `LedgerStore` port: the routes reach them through a small `PilotJournalStore` protocol |
| Web | A read-only "Pilot journal" section at the foot of the Activity page, behind `NEXT_PUBLIC_STRATEGY_MVP=1`, live mode only; hidden on a 403 |

With the flag off both routes answer 403 `FEATURE_DISABLED` and nothing else in the app differs.

## 3. The fields

Written by the caller (the owner's session at the weekly record), validated by the route:

| Field | Type and limits | Source |
| --- | --- | --- |
| `week` | integer, 1 to 60 | The pilot week number in `docs/pilot/<label>/week-NN/` (1 is the first session) |
| `sme` | string, 1 to 64 characters, letters, digits, space, `_` or `-` | The SME's anonymous label (`sme-a`), as in the folder name |
| `answer` | `envelope`, `worth` or `curve` | Which of the three answers the decision was against: the Safe Deal Envelope (`GET /buyers/{id}/envelope`), collections worth (`GET /receivables/worth`), the cash price curve (`GET /cash/price-curve`) |
| `flow_said` | string, 1 to 2000 characters | The displayed sentence, copied exactly from the route's JSON: `primary` (envelope), `top_action` (worth, or the row's `action_sentence`), `sentence` (curve). Never retyped or paraphrased |
| `snapshot_hash` | 64 lowercase hexadecimal characters | The sha256 of the route's JSON **file as exported and committed** that week (`sha256sum`), computed by the caller. The server cannot recompute it (it is a hash of a response that has since moved on); it only checks the shape |
| `owner_did` | string, 1 to 2000 characters | What the owner did, in their own words, verbatim; "n/a" where `choice` is `not_applicable` |
| `choice` | `followed`, `partly`, `ignored` or `not_applicable` | The recorder's typed reading of `owner_did` against `flow_said`: the owner's response was one of FLOW's packages or inside its zone (envelope), the chase order matched FLOW's net order (worth), or the saving was acted on (curve), respectively; `ignored` when it was not; `not_applicable` when the answer did not bear on any decision that week |
| `recorded_on` | ISO date `YYYY-MM-DD` | The date the owner made the record (not the date of the decision, which belongs in `owner_did`) |

Stamped by the server:

| Field | Type | Source |
| --- | --- | --- |
| `id` | `PJ-` and the six-digit sequence number | The store's append position |
| `seq` | integer from 1, gap-free | The store's append position (the table's row id) |
| `state_version` | integer | The books' version at the moment of the write (`state.state_version`, read, never changed) |
| `day` | integer | The runtime's clock day at the write (`rt.day`; day 0 is the week's `as_of`) |
| `recorded_at` | ISO 8601 UTC timestamp | The server clock at the write, as `evidence_exports.exported_at` is stamped |

## 4. The routes

Both: owner token (`X-Owner-Token`), then the flag.

### `POST /pilot/journal`

Body: the eight caller fields above, all required, no others (an unknown field is a 422). Appends one entry and returns
`201` with `{"entry": {...}}`, the stored entry with its server fields. Errors: 401 no owner token; 403 `FEATURE_DISABLED`;
422 a field out of its limits, an unknown `answer` or `choice`, a malformed date or hash, or a free-text field that looks
like an account number (the message names the field, in a sentence). The route holds no lock on the runtime and does not
enter the engine's unit of work.

### `GET /pilot/journal`

Returns `{"entries": [...], "count": n}`, newest first (`seq` descending). Optional filters `week` and `sme` narrow the list.
Each entry is the stored entry above; there is no money field and no `*_display` sibling. The response is `displayed`-safe: it
passes through `displayed()` unchanged because it holds no `*_fen`, `*_bp` or `{num, den}` field (a test pins that).

## 5. The journal in the pilot's week

1. The owner's decisions are recorded in `weekly-record.md` first, in their words (`docs/pilot/weekly-record.md` sections 3, 4).
2. For each decision against an answer, one `POST /pilot/journal` (`docs/pilot/RUNBOOK.md` section 4, step 6).
3. `GET /pilot/journal` is exported to `journal.json` in the week's folder **before the runtime is stopped** (the pilot
   runtime is in memory), and committed after the owner's approval.
4. The pilot report counts the entries by `answer` and `choice`: that count is the outcome column. The gates' own figures are
   read from the weekly records (`docs/pilot/RUNBOOK.md` section 7); the journal is the ledger's record of them.

## 6. Tests (`services/api/tests/pilot/`)

- Both routes are 403 `FEATURE_DISABLED` with the flag off, and 401 without the owner token, flag on.
- An entry round-trips: what was posted is what is read, with `seq`, `id`, `state_version`, `day`, `recorded_at` stamped;
  newest first; filters by `week` and `sme`.
- A write changes neither the engine's `state_version`, nor the operations count, nor the chain head, and the chain still
  verifies; the store's state history is unchanged.
- The journal's entries survive `demo/reset`'s ledger clear (a kept table) and cannot be updated or deleted through the SQL store.
- Validation: each limit, each enum, the date, the hash, and the account-number guard.
- The same contract on `InMemoryLedgerStore` and `SqlLedgerStore` (SQLite), and migration 0005 matches `tables.py`.
- No file under `app/financial`, `app/verifier`, `app/funding`, `app/alerts` or `app/operations` imports the journal module
  (`app.pilot`) or names `pilot_journal`.
- Web: with the flag build off (and in mock mode) the section is not mounted and the client does not call the route.

## 7. Out of scope, on purpose

An edit or delete route; a link from an entry to an operation; any score, ranking or "accuracy" computed from entries by the
server; a write from the agent or a counterparty (owner only); a server-side check of `snapshot_hash`; a journal in the SQL store across
runtimes (the durable copy is the per-SME JSON-lines file the runtime keeps with `--journal-file`, replayed at start and
appended before each answer; the weekly export is the committed copy); a Chinese reading of the entries (the section's
labels are translated; the entries are the owner's own words in the language they spoke).
