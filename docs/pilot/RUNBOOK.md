# FLOW shadow pilot: the runbook

For wayfinder map [#58](https://github.com/peachoolongtee/smu2sz/issues/58), ticket #60. The pilot runs four to eight weeks
on one or two real SMEs' books. Each week the books are entered, the three read-only answers are computed with the flags
on, and **nobody acts on them**; the owner records what they actually did, and that record is set beside what FLOW said.
The gates that read the result are `docs/STRATEGY_RESEARCH.md` section I (quoted in section 7 below).

## 0. The rules this runbook keeps

- **Stability mode.** No engine, operation, verdict or mandate change. The pilot runtime is the demo's code on the SME's
  books; the only additions are this folder, a start-up script (`services/api/scripts/pilot_runtime.py`) and the flagged
  journal (`docs/pilot/JOURNAL_SPEC.md`).
- **Nothing here acts.** No pilot step posts an operation, accepts an offer, draws, repays or queues an approval. A healthy
  pilot runtime has an empty operations log all the way through (section 4, step 6 checks it).
- **INVARIANT 13.** The UI and this runbook never compute money. Every figure in a record is copied from FLOW's displayed
  string or from the route's `*_display` field; a person never recomputes it.
- **Business words.** What the owner reads and what the owner says is recorded in business words (what it saves, what you
  can live with, whom to chase). Engine terms appear only in command lines and file names.
- **No real data in the repository without the owner's approval** (section 5). Nothing under `docs/pilot/` is committed
  before the owner has read it and said yes.

## 1. Before the first week

1. The owner has named the SMEs, the month and the three comprehension-test owners on grilling
   [#59](https://github.com/peachoolongtee/smu2sz/issues/59). Until then, run `docs/pilot/interviews.md` instead.
2. Pick an anonymous **label** per SME (`sme-a`, `sme-b`). The label, never the company name, is used in every file name,
   every journal entry and every commit.
3. Make a private folder **outside the repository** per SME, for example `~/pilot-private/sme-a/`. It holds that SME's
   `state.json`, `mandate.json`, `owner_key.json` and the name key (which label is which real buyer). It is never committed.
4. Tools: `uv`, `pnpm`, `curl`, `jq`, `sha256sum` (macOS: `shasum -a 256`). `pnpm install` once in `apps/web`, and
   `pnpm exec playwright install chromium` once if the screenshots are taken by script.
5. A **port per SME** for the API (say 8001 and 8002) and one for the web app (say 3100). Never port 3000, which the demo
   web app and the e2e live target use.

## 2. Start one pilot runtime per SME

### Why not `DATABASE_URL=memory` alone

`get_runtime()` (`app/api/runtime.py`) seeds **only an empty store**, and what it seeds is always the golden books:
`_seed()` writes `seed_state("golden_sme")` and the signed demo mandate, whatever `DEMO_MODE` says (an in-memory store is
"seedable" by definition). `Runtime.reset(scenario)` (`POST /demo/reset?scenario=NAME`) is the same: it reads
`fixtures/scenarios/NAME.json` (`app/domain/fixtures.py`, `FIXTURES` is fixed to the repository's `fixtures/`) and still
seeds `load_signed_mandate()`, the golden mandate, never the scenario's own. So there is no flag that starts the API empty
or on a custom mandate, and a scenario file for a real SME would have to be committed under `fixtures/scenarios/`.

`services/api/scripts/pilot_runtime.py` is the supported way: it reads the SME's two JSON files from the private folder,
validates them, signs the mandate, puts both into a fresh in-memory store (`put_state`, `put_mandate`, the calls the runtime
itself makes), hydrates the clock, and serves the unchanged app in the same process. **Never call `POST /demo/reset` on a
pilot runtime** (and never use the web app's story page `/demo` or the demo stepper, which call it): on an in-memory store it is allowed and it would
replace the SME's books with the golden demo.

### The command

From the repository root (the worktree you are running the pilot from):

```bash
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=0 PYTHONUTF8=1 \
  OWNER_TOKEN='<a token you choose>' AGENT_KEY='<another random string>' \
  FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_PILOT_JOURNAL=1 \
  CORS_ORIGINS=http://localhost:3100 \
  uv run --project services/api python services/api/scripts/pilot_runtime.py \
    --state ~/pilot-private/sme-a/state.json \
    --mandate ~/pilot-private/sme-a/mandate.json \
    --owner-key-file ~/pilot-private/sme-a/owner_key.json \
    --port 8001
```

What each setting is for: `DEMO_MODE=0` turns off the published demo credentials (`demo-owner-token` is refused with 401)
and the demo scenario's day-42 event; `OWNER_TOKEN` is what the owner types into the web app's sign-in dialog and what the
`curl` lines send as `X-Owner-Token`; the three `FEATURE_*` strategy flags and `FEATURE_PILOT_JOURNAL` switch the routes on
(each is off, 403 `FEATURE_DISABLED`, without it); `CORS_ORIGINS` lets the web app on port 3100 call this API. The script
refuses to start on port 3000, on a `DATABASE_URL` other than `memory`, on books or a mandate that do not validate, when the
two name different organisations, when the books do not start on day 0, and when the mandate is not valid on day 0. It
prints one sentence saying which.

`--owner-key-file` is a JSON file `{"private_key_hex": "<64 hex characters>"}`: the Ed25519 key that signs this SME's
mandate. Make one outside the repository:

```bash
uv run --project services/api python -c "import json; from nacl.signing import SigningKey; k=SigningKey.generate(); print(json.dumps({'private_key_hex': k.encode().hex(), 'public_key_hex': k.verify_key.encode().hex()}))" \
  > ~/pilot-private/sme-a/owner_key.json
```

Without `--owner-key-file` the mandate is signed with the repository's **published demo key**, which proves nothing about a
real owner. That is acceptable for a local, read-only pilot runtime and no more.

### Keep the journal across a restart: `--journal-file`

The runtime is restarted every week (section 3), and the journal lives in its memory. Add `--journal-file
~/pilot-private/sme-a/journal.jsonl` to the command and the journal is kept on that file as well: one JSON object per line,
the entry as `GET /pilot/journal` shows it (`seq`, `week`, ..., `recorded_at`). At start-up the file is read back into the runtime
(a line that does not validate stops the start with a sentence naming the line number, and the file is left as it was); every
`POST /pilot/journal` is written to the file, and synced, before the route answers. A file that cannot be written answers 500
and the entry is not kept. The file is append-only: do not edit it by hand. Keep it in the private folder; a path inside the
repository is refused, except `docs/pilot/<label>/<file>` when `--allow-repo-path` is also passed (only after section 5's
approval). The file changes nothing else: the books, the operations log and the hash chain are as without it.

### Check it started on the SME's books

```bash
OWN='X-Owner-Token: <the token>'
curl -s -H "$OWN" localhost:8001/state | jq '{org: .state.org_id, day, cash: .cash.text}'
curl -s -H "$OWN" localhost:8001/mandate | jq '{signature: .signature.status, validity: .validity.status, valid}'
curl -s localhost:8001/health | jq .features     # the four flags above read true
```

Expect `org` to be the SME's label (not `SME-1`), `day` 0, `cash` the figure the owner gave, `signature` `VALID`, `validity`
`ACTIVE`. If `org` reads `SME-1` you are on the golden books: stop. (`/state` also returns `scenario_id: "golden_sme"`; that is
the runtime's default label, not the books, so read `org` and `cash`.)

## 3. Enter the books

There is **no route that enters invoices, recurring invoices, cash or a mandate**; they enter through the two files above,
once per runtime start. (The only entry route in the API is `POST /operations` with `ADD_FACILITY`, owner only; it writes
the operations log, so the pilot does not use it. A new facility goes into `state.json` and the runtime is restarted.)
Because each week starts a fresh in-memory runtime, **each week's `state.json` is that week's books**: edit the file, restart.

Money is in **fen** (¥1 = 100 fen, whole numbers, no decimals: ¥12,345.67 is `1234567`). Days are counted from the books'
first day: **day 0 is `as_of`**, an invoice issued before it has a negative `issue_day`, and `due day = issue_day +
terms_days`. Set `as_of` to the date of the weekly session. `as_of_day` must be 0 and `scenario` must be absent.

A worked, synthetic example to copy: `docs/pilot/templates/state.example.json` and `docs/pilot/templates/mandate.example.json`
(org `SME-EXAMPLE`; two buyers, three facilities, two open invoices, two recurring invoices). Copy them to the private
folder and replace every value. Do not edit the templates.

### `state.json` (`FinancialState`, `app/domain/models.py`)

| Field | What to enter | Where the owner finds it |
| --- | --- | --- |
| `org_id` | The SME's label. Must equal the mandate's `org_id`. | |
| `as_of` | The session date, `YYYY-MM-DD`. | |
| `cash_fen` | Cash at the start of the day (the sum of the accounts the owner counts as usable). | The bank balance this morning |
| `monthly_ebitda_fen` | Last month's operating profit before interest and tax, whole yuan in fen. | The finance manager's monthly figure |
| `flows[]` | Each committed payment out or sure payment in over the next 120 days that is not an invoice: `{id, day, amount_fen (negative = out), kind (PAYROLL, SUPPLIER, OPERATING, ...), label, counterparty_id (null), confirmed (true)}`. | Payroll date, supplier schedule, rent, tax |
| `receivables[]` | Each **open** invoice: `{id, counterparty_id, face_fen, issue_day, terms_days, status "OPEN", confirmed true}`. `face_fen` is what is still owed. | The aged-debtor list |
| `recurring_invoices[]` | One per buyer that is invoiced on a rhythm: `{counterparty_id, face_fen, every_days, next_issue_day, terms_days}`. **Enter these for every buyer that has a rhythm**: the envelope's first gate counts buyers with one. | The sales manager / billing calendar |
| `facilities[]` | Each funding source the owner has, with its real terms: `{id, name, kind, lender_id, status, owner_approved, limit_fen, drawn_fen, rate_bp (annual, 640 = 6.40%), advance_rate_bp, fee_bp_per_advance, fee_period_days, upfront_fee_bp, lead_time_days, term_months, repayment, covenants[]}`. `status` is `COMMITTED` only for money the owner can use now; anything pending counts as zero. Copy the shape of `FAC-LINE` (credit line), `FAC-IF` (invoice financing), `FAC-EARLYPAY` (a buyer's early-payment offer) from the example. | The facility letters and the bank RM |
| `debts[]` | Existing loans: `{id, facility_id (null), label, principal_fen, monthly_debt_service_fen, rate_bp, payment_every_days, next_payment_day}`. | The loan statements |
| `expected_orders[]` | Optional. Leave `[]` unless the owner names a firm order. | |
| `counterparties[]` | Every id used above: `{id, name, role (BUYER, LENDER, SUPPLIER, OWNER), known true}`. **Use anonymous labels in `name` ("Buyer A")**: FLOW displays this name in its sentences, and the sentences are what is committed (section 5). Keep which label is which buyer in the private name key. | |
| `forward_concessions[]`, `invoice_adjustments[]`, `lots[]` | `[]`. No agreement is booked in the pilot. | |
| `state_version` 1, `as_of_day` 0 | As in the example. | |

The permanent funding source matters: the cash price sentence is measured against the cheapest committed source that can
carry a permanent need (a credit line). With none, FLOW says "there is no permanent funding source on the books to measure it
against" (422), which is itself a finding to record.

### `mandate.json` (`Mandate`, `app/domain/models.py`)

| Field | Meaning | Source |
| --- | --- | --- |
| `org_id` | The SME's label. | |
| `version` | 1. | |
| `min_cash_fen` | The floor the owner will not let cash go below. | The owner, in money |
| `max_aggregate_forward_concession_fen` | The total budget for what the owner will give buyers in future (rebates, longer terms, price cuts). The envelope's packages are limited by it. | The owner |
| `forward_concession_horizon_days` | 365. | |
| `per_buyer_caps_fen` | `{}` or `{"BUYER-1": ...}` per-buyer limits. | The owner |
| `max_immediate_discount_bp` | The largest discount for money received now (150 = 1.50%). The collections ceilings never exceed it. | The owner |
| `min_dscr_bp`, `max_leverage_bp` | The covenant limits (12500 = 1.25x). | The facility letters |
| `max_apr_bp` | The most the owner will pay, annualised, for any funding or early payment (1500 = 15.00%). | The owner |
| `require_clean_down`, `allow_new_borrowing` | `true` unless the owner says otherwise. | |
| `tier2_single_commitment_fen` | A single agreement above this needs the owner's approval. | The owner |
| `horizon_days` | 120. | |
| `issued_day`, `expires_day` | 0 and a day at least 90 out: the answers are not meaningful on an expired mandate (the script refuses it). | |
| `public_key_hex`, `signature_hex` | `null`. The script signs the mandate with the owner key at start-up (`app.mandate.sign`: Ed25519 over the canonical, sorted-key JSON without the signature, binding the signer's public key). A mandate that already carries a signature is verified, not re-signed. | |

The owner confirms the mandate's numbers **in the owner's own words and on the owner's own paper**, once, before week 1;
record that date in the first weekly record. Changing a mandate number later is a new `mandate.json`, noted in that week's
record: the answers move when it does.

### Routes the pilot reads (and nothing else)

| Route | Needs | Used for |
| --- | --- | --- |
| `GET /state`, `GET /mandate`, `GET /clock` | owner token | Check the books and the mandate loaded (section 2) |
| `GET /cash/price-curve?lang=en` | owner token, `FEATURE_PRICE_CURVE` | The cash price sentence (answer 1) |
| `GET /receivables/worth?lang=en` | owner token, `FEATURE_COLLECTIONS_WORTH` | The chase ranking (answer 2) |
| `GET /buyers/{buyer_id}/envelope?zone=1&lang=en` | owner token, `FEATURE_ENVELOPE` | What the owner can live with for one buyer (answer 3) |
| `POST /pilot/journal`, `GET /pilot/journal` | owner token, `FEATURE_PILOT_JOURNAL` | The owner's recorded decision against the answer (`docs/pilot/JOURNAL_SPEC.md`) |
| `GET /ledger` | owner token | Step 6's check that nothing acted |

## 4. The weekly procedure

One session per week, with the owner (or the finance manager the owner names), about an hour. Use the same weekday. The folder
for the week is `docs/pilot/<label>/week-NN/` (NN two digits, `01`..). Work in a scratch copy first and copy into the
repository only after the approval step (section 5).

1. **Update the books.** In the private `state.json`: set `as_of` to today; update `cash_fen`; close invoices that were paid
   (remove them from `receivables`, noting date received for step 8); add new invoices; update `flows`, `facilities`
   (drawn amounts), `recurring_invoices` (`next_issue_day`). Day numbers restart: recompute `issue_day` and `next_issue_day`
   relative to the new `as_of`. If a mandate number changed, edit `mandate.json`.
2. **Restart the runtime** with the command in section 2 (stop the old one first, and write down the port). Check it
   (section 2, "Check it started").
3. **Export the three answers as JSON.** Set `W=docs/pilot/<label>/week-NN` (in the scratch copy) and `P=8001`:

   ```bash
   OWN='X-Owner-Token: <the token>'; mkdir -p "$W"
   curl -s -H "$OWN" "localhost:$P/cash/price-curve?lang=en"          > "$W/price_curve.json"
   curl -s -H "$OWN" "localhost:$P/receivables/worth?lang=en"         > "$W/worth.json"
   # one file per buyer on the books (the ids are in state.json's counterparties with role BUYER); the first read of
   # each can take several seconds on large books, and with the zone table up to about 44 seconds: wait for it
   for B in BUYER-1 BUYER-2; do
     curl -s --max-time 180 -H "$OWN" "localhost:$P/buyers/$B/envelope?zone=1&lang=en" > "$W/envelope-$B.json"
   done
   ```

   Check each file is an answer, not a refusal: `jq -r '.sentence // .top_action // .primary' "$W"/*.json`
   (a 403 means the flag is off; a 422 carries FLOW's own sentence for why it cannot answer; record that sentence). Hash each
   file as it will be committed, and note the hashes in the weekly record: `sha256sum "$W"/*.json`
   (`shasum -a 256` on macOS). The journal's `snapshot_hash` is exactly this value.
4. **Take the three page screenshots** with the web flag on, live mode, against this runtime:

   ```bash
   cd apps/web
   NEXT_PUBLIC_STRATEGY_MVP=1 NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8001 pnpm exec next dev -p 3100
   ```

   Open `http://localhost:3100`, sign in with the owner token, switch to the Business shell, and save a full-page
   screenshot of each: **Cash & funding** (`/cash`, the sentence under the headroom line), **Receivables** (`/receivables`,
   the Worth collecting and Action columns), and **Deals** (`/deals`) with the buyer's message open where one is in the inbox
   (the envelope card "The most you can give" sits under the buyer's asks; with no message open the page has no envelope
   card, and `envelope-<id>.json` is the record). Save as `cash.png`, `receivables.png`, `deals-<id>.png` in `$W`. Use a
   browser window of 1440 px width. Hide nothing: the approval step removes what must go.
   The web app in live mode reads the runtime's own books; there is nothing to enter in the web app.
5. **The owner records what they did** (the template is `docs/pilot/weekly-record.md`; copy it to `$W/weekly-record.md`).
   This is the pilot's instrument: in the owner's words and the owner's order, **before** being shown what FLOW said
   where the answer concerns a decision already taken.
   - *Offers.* Each real offer a buyer made since the last session (terms, price, early payment, rebate): the date, what
     was asked, and **what the owner replied or did**, verbatim. The first ten offers of the pilot are numbered; they are
     the envelope gate's sample.
   - *Chase order.* In the order they did it: which buyers they chased since the last session, by what means, and why.
     Then show them `worth.json`'s ranking and record whether it matches, and if not, whether they say FLOW's order is
     the one they should have followed.
   - *Receipts.* Each invoice that was paid since the last session: the due date, the date the money arrived. Remove it from
     the next `state.json`.
   - *Open at once.* How many buyer deals were open at the same time this week (for the portfolio gate), and how many
     receivables are open (for the collections gate).
6. **Classify and record.** For each offer, whoever fills the record sets the envelope's answer against the owner's response
   using only what FLOW displayed (the packages' `summary` lines, the zone table's `terms_words` and `lowest_price_words`):
   *inside the zone*, *one of the packages*, *outside*, or *ignored the packages*, with a one-line reason. For the chase, set
   FLOW's net order (`jq -r '.rows[].receivable_id' "$W/worth.json"`) beside the overdue-amount order
   (`jq -r '.rows | sort_by(-.outstanding_fen) | .[].receivable_id' "$W/worth.json"`: the largest amount first, the clerk's
   natural list; FLOW's own gross-saving order is `jq -c .gross_order`) and say whether the net order and the amount order
   differ this week.
   For each decision write a journal entry (`POST /pilot/journal`, `docs/pilot/JOURNAL_SPEC.md`), then export all of them:

   ```bash
   curl -s -X POST -H "$OWN" -H 'Content-Type: application/json' "localhost:$P/pilot/journal" -d '{
     "week": 3, "sme": "sme-a", "answer": "envelope",
     "flow_said": "<the primary sentence, copied exactly as displayed>",
     "snapshot_hash": "<sha256 of envelope-BUYER-1.json from step 3>",
     "owner_did": "<what the owner did, in their words>",
     "choice": "followed", "recorded_on": "2026-10-19"}'
   curl -s -H "$OWN" "localhost:$P/pilot/journal" > "$W/journal.json"
   ```

   `choice` is one of `followed`, `partly`, `ignored`, `not_applicable`. The entries also show, read-only, at the foot of the web app's
   Activity page while the runtime is up (live mode, strategy flag on). The journal lives in the runtime's memory (and on the
   `--journal-file` if the command had one, section 2); stopping the runtime forgets the memory, so **`journal.json` must be exported before stopping**. Then confirm nothing acted:
   `curl -s -H "$OWN" localhost:$P/ledger | jq '{chain_length, commitments: (.commitments|length)}'` reads
   `{"chain_length": 0, "commitments": 0}`. Anything else means a step posted an operation: stop and tell the lead.
7. **Fill `docs/pilot/weekly-record.md`'s sections** from the files; copy figures as displayed.
8. **Approval** (section 5), then commit the folder, then stop the runtime.

## 5. The approval step: what may be committed

Nothing is committed until the **owner has read what is about to be committed and said yes**, in the same session, and the
record says so (the template's last section carries the date and the owner's initials).

**May be committed** (after the owner's yes):

- The owner's records: the offers' dates and what was asked in terms, percentages and days, the owner's replies in their own
  words, the chase order and reasons, receipt and due dates, the open-at-once counts.
- FLOW's displayed sentences and figures exactly as the routes returned them: `price_curve.json`, `worth.json`,
  `envelope-<id>.json`, `journal.json`, the three screenshots, and the hashes of the files.

**Anonymise before committing:** counterparty names (buyers, lenders, suppliers) become "Buyer A", "Buyer B", "Lender 1"
everywhere: in the record, in the journal text, in screenshots (crop or blur a name that appears), and in file names. If the
state file used anonymous labels from the start (section 3), FLOW's sentences are already clean; still read each file once
(`grep -il` for the real names, which are in the private name key) before the owner's yes. Company, person and place names go
too. Amounts the owner is unwilling to publish are replaced by a ratio or a band in the record's prose; the route files
stay as FLOW wrote them only if the owner agrees to those figures being public.

**Never committed, even with approval:** bank identifiers (account numbers, card numbers, IBANs, SWIFT codes, bank
references, payer references), tax numbers, phone numbers, email addresses, WeChat ids, the owner token, the agent key,
the owner key file, `state.json`, `mandate.json`, and the name key. The journal route refuses free text containing a run of
twelve or more digits (account-number shaped), which is a backstop and not a substitute for reading.

Commit one folder per week with a plain one-line message such as `Pilot sme-a week 03: the three answers and the owner's record`.
If the owner says no to anything, delete it from the scratch copy; do not commit a redacted file under the original name.

## 6. Weekly checklist

- Runtime started on the week's books, org is the label, day 0, signature VALID.
- Four files exported and hashed; three screenshots taken.
- Offers, chase, receipts and open-at-once recorded in the owner's words before FLOW's order was shown for the chase.
- Journal entries recorded and `journal.json` exported.
- Operations log is empty.
- Anonymised, owner has read and said yes, initials and date in the record.
- Committed; runtime stopped; private files stay private.

## 7. End of the pilot: reading the gates

Run once, by the lead, from the committed weekly records (never from memory). The thresholds are `docs/STRATEGY_RESEARCH.md`
section I, "Acceptance thresholds, tied to the kill criteria", quoted verbatim:

| Capability | Passes the gate when | Killed when (accepted criterion) |
| --- | --- | --- |
| Envelope | on at least five of the first ten real offers the owner's chosen response is inside the zone or is one of the packages; at least half the pilot's buyers have a recurring invoice; backtest: 100% of counters inside the envelope, zero approved package fails its re-check | chosen response outside the zone or packages ignored on more than half of the first ten offers; fewer than half the buyers have a recurring invoice |
| Collections | in at least one pilot week the net-value order differs from the overdue-amount order and the owner's chase order followed it (or they say it should have); at least one pilot has more than two open receivables at once | the orders coincide every week; no pilot has more than two open receivables |
| Cash price curve | three of three owners in the comprehension test explain "0.89%" as what earlier cash is worth to them, not a rate charged | any owner reads it as a charged rate (reword and retest once; then kill) |
| Portfolio (VALIDATE FIRST) | two or more deals open at the same time in most pilot weeks, and the greedy order differs from the enumeration in a case that occurs (it already does on the fixtures) | fewer than two simultaneous deals in most weeks |
| Stress-to-action, tripwires | the cold-user walk shows the alerts page does not already answer the question | it does |
| Conditional deals | a pilot owner asks for one unprompted | nobody does |

How each reading is taken:

- **Envelope.** Count the first ten numbered offers across all SMEs: how many are *inside the zone* or *one of the packages*
  (pass at five or more), how many *outside* or *ignored* (killed above five). Count buyers with a recurring invoice over
  buyers on the books in the last week (pass at one half or more). The backtest clause is already met: the backtest ran in map
  #47 (`docs/research/strategy/06-backtest-2026-10-08.md`); re-run it if the code changed.
- **Collections.** Look for one week where the net order and the overdue-amount order differ **and** the chase followed the net
  order or the owner says it should have; and the largest number of open receivables at once in any week.
- **Cash price curve.** Read `docs/pilot/comprehension-test.md`'s record: three of three pass; one reword and retest;
  any reading as a charged rate after the reword kills the sentence.
- **Portfolio.** The open-at-once count per week, from the records; "most weeks" is more than half the weeks run. The
  greedy-versus-enumeration clause is read from `fixtures/strategy/portfolio_default.json` and needs no pilot.
- **Stress-to-action, tripwires, conditional deals.** From the cold-user walk and the owner's unprompted requests, which the
  record's notes section catches (write down any request for a conditional deal in the owner's words when it happens).

Write the result as the pilot report: per answer the gate's figures, pass or fail, and the post-pilot action it earns
(`docs/STRATEGY_RESEARCH.md` section L, "Post-pilot"). Controlled action stays off until the report names one.

## 8. Dry pilot: a rehearsal on public-record or synthetic books

Before the real pilot the whole procedure is run once, by an agent, on books no one owns: the public-record SME fixture
(map #58, ticket #61) or the synthetic templates. It exercises sections 2 to 4 and the journal; it finds what breaks and what
reads wrongly **before an owner sees it**.

- **The label** is `dry-a`. Its folder is `docs/pilot/dry-a/`, its weeks `week-01`..`week-08`, and the same label is the journal's `sme`.
  A dry pilot's files may be committed (the books are synthetic or public); a real SME's never are before section 5.
- **The role-play rule.** Nobody plays the owner's judgment. Either the owner writes the week's decisions beforehand in
  `docs/pilot/dry-a/decisions.yaml` (copy `docs/pilot/decisions.example.yaml`; each is an answer, the owner's words and a choice),
  or the run says `--role-play auto`, which records `followed` for every answer with `owner_did` "role-play: followed FLOW's
  answer". The auto mode only exercises the pipeline; it says nothing about whether any answer is right, and the report must
  never describe it as an owner's behaviour.
- **What it does.** In one process (no server, no port), for each week it advances the clock seven days, reads the three
  answers through the real routes, writes `price_curve.json`, `worth.json`, `envelope-<buyer>.json` for each buyer with an open
  invoice, a recurring invoice or an expected order, `sentences.md` (the displayed sentences) and `sha256.txt` into
  `<out>/week-NN/`, prints the sentences and the open decisions, and records the week's decisions through `POST
  /pilot/journal` (`snapshot_hash` is the file's sha256, `flow_said` the displayed sentence). `<out>/summary.md` holds per week
  the sentences, the choices, the runtime, and every error with its week; an answer slower than 10 seconds is listed under
  "Slow". The exported files leave out the routes' timing field (`computed_in_seconds`), so a file's hash depends on the books
  alone and two runs on the same books list the same sha256; the seconds each answer took are in `summary.md` and on the
  console only. Unless a receipts file is given (below) it posts no operation. Moving the clock writes one `ADVANCE_CLOCK`
  entry per advance on the operations log (the clock's own entry), so a dry run ends with that many entries and **no other**
  (plus one `RECEIVE_PAYMENT` per receipt, with a receipts file); the run reports any other entry as an
  error. (A real pilot runtime never advances its clock, so section 4 step 6's empty log still holds there.)
- **Receipts: `--receipts receipts.yaml`.** Without it the clock never assumes a receipt and no buyer ever pays, so from week 2
  the books drift into a stress case. A receipts file lets the rehearsal follow the role-played decisions: a map of week
  number to a list of `{receivable_id, amount_fen, bank_reference}` and an optional `day` (1 to 7, the day of the week the
  credit arrives; the end of the week when left out). Copy `docs/pilot/receipts.example.yaml` (it uses the public-record
  fixture's ids). The file is checked against the run and the starting books before anything runs: a week outside the run,
  an unknown or already settled receivable, an amount that is not above zero, a bank reference used twice, or receipts that
  add up to more than the receivable owed, is refused with the reason (exit 2). Each receipt is then posted before that week's
  reads, the way the bank feed posts one (`RECEIVE_PAYMENT`, requested by `SYSTEM`, with the bank reference; the clock still
  assumes nothing), and recorded in the journal as an entry whose `answer` is `receipt`: the sentence names the receivable,
  the amount, the operation id (`dry-receipt-wNN-n`) and the balance still outstanding, and `snapshot_hash` is the sha256 of
  those facts. `summary.md` and the week's `sentences.md` list each receipt under its week. A receipt the executor refuses
  is an error for that week and no journal entry. Receipts are the rehearsal's own inventions, never an owner's money.
- **The command**, from the repository root:

  ```bash
  TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 \
    uv run --project services/api python services/api/scripts/pilot_dry_run.py \
      --state <state.json> --mandate <mandate.json> --label dry-a --weeks 8 --out docs/pilot/dry-a \
      --role-play auto
  # or, with the owner's written decisions:  --decisions docs/pilot/dry-a/decisions.yaml   (instead of --role-play auto)
  # optional: --journal-file <path> to keep the journal on a file (it must not hold entries yet), --owner-key-file <path>,
  #           --receipts docs/pilot/dry-a/receipts.yaml to land buyers' payments week by week (see the next item)
  ```

  `--state` and `--mandate` are the books and mandate of section 3 (for the synthetic templates: `docs/pilot/templates/state.example.json`
  and `mandate.example.json`). The flags and a random owner token are set by the script itself. Exit 0 means every week ran
  without an error; 1 means a week reported one (read `summary.md`); 2 means the arguments or files were refused, with a sentence.
- **What it teaches about itself.** Without a receipts file the runner lands no receipt and a decision never changes the books, so from week 2 the books drift into a stress case (see `docs/pilot/dry-pilot-report-2026-10-09.md`); a week on six buyers takes up to four minutes, so start it and wait.
- **No gate is read from a dry pilot.** The books are not an owner's, the decisions are written or role-played, and so no
  figure in a dry pilot counts toward any threshold in section 7; its report says what broke and what read wrongly, and is
  labelled a rehearsal.
