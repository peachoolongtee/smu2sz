# FLOW web app (`apps/web`)

The web app of FLOW (the package and code name is TermsLedger). Next.js 16 (App Router) + TypeScript + Tailwind v4 +
Recharts. The UI never computes money: it renders the server's `*_display` strings and passes integer fen to charts for axes
only (INVARIANT 13).

```
pnpm install
pnpm dev                 # mock mode by default
pnpm lint && pnpm typecheck && pnpm build
pnpm test:unit           # mocks match fixtures/golden/golden_values.json
pnpm exec playwright install chromium   # once
pnpm test:e2e            # mock project + live project (starts the API and both web builds itself)
pnpm test:e2e:mock       # mock project only, no backend needed
pnpm test:e2e:live       # live project only (needs `uv`)
```

Run these from `apps/web`; the commands in the sections below that start with `cd` say where they run from. The same
steps, the two servers and the database choices are in the root `README.md`; this file adds the web-specific parts.

## Modes

- `NEXT_PUBLIC_API_MODE=mock|live` (default `mock`), `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
  Mock mode is the offline fallback: answers come from `mocks/*.json` and need no backend.
- All data access goes through `lib/api.ts`. Mock answers live in `lib/mock/handlers.ts`; live answers in
  `lib/live/` (`http.ts` is the only `fetch`). Routes whose response already has the mock shape are
  passthroughs; `lib/live/trajectory.ts` and `lib/live/approvals.ts` reshape the ones that differ. Adapters
  rename fields and copy server strings; they never add, subtract or format money.
- Types are in `lib/types.ts` (hand-written; most API routes return untyped dicts, so there is no useful
  OpenAPI schema to generate from yet). Read views follow one rule: every `<name>_fen` / `<name>_bp` has a
  sibling `<name>_display` (see `Displayed<T>`).
- All labels (English and Chinese) are in `lib/dictionary.ts`.

### Running live locally

The simplest way, on any shell including PowerShell: `pnpm demo` (here or at the repository root) starts both servers with the
safe settings below and picks the CORS origin for you; `pnpm demo --web-port 3141 --api-port 8041` for other ports,
`pnpm demo:mock` for this app alone on the mocks, and `pnpm demo:keep` (at the repository root; `node ../../scripts/demo.mjs
--keep` from here) to keep the books in `.demo-data/flow-demo.db` across restarts. `pnpm dev:live` / `pnpm dev:mock` start this app alone in either mode on any
shell (`dev:live` reads `NEXT_PUBLIC_API_URL`, default `http://localhost:8000`).

By hand (bash syntax), two terminals, both starting at the repository root:

```
cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 uv run uvicorn app.main:app --port 8000
cd apps/web && NEXT_PUBLIC_API_MODE=live pnpm dev      # must be on :3000, the API's CORS allow-list
```

`DATABASE_URL=memory` keeps the books in the API process and writes no file. Leave `DATABASE_URL` out and the API uses
`sqlite:///./termsledger.db`, a file in the directory it was started from (`services/api/termsledger.db`, git-ignored); the
app creates the file and its tables itself on the first request, so there is no Alembic step. For a file elsewhere give the
absolute form, `DATABASE_URL=sqlite:////absolute/path/to/file.db` (four slashes). `TERMSLEDGER_NO_DOTENV=1` stops the API
reading a repo-root `.env`, so a stray one cannot change the database or the model mode.

`pnpm dev` writes `AGENTS.md` and `CLAUDE.md` in this directory (Next.js 16 does it on start); both are git-ignored.

To use other ports, tell the API to allow the web origin and tell the web app where the API is (without `CORS_ORIGINS` the
browser's preflight gets a 400 and every request fails):

```
cd services/api && CORS_ORIGINS=http://localhost:3141 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 uv run uvicorn app.main:app --port 8041
cd apps/web && NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8041 pnpm dev -p 3141
```

### Owner sign-in

The API gates its owner routes on `X-Owner-Token`. No token is built into the bundle. A 401 from any owner request
opens the **Owner sign-in** dialog; the token is checked against the API (`GET /state`), then kept in
`sessionStorage` only (every storage access is in a try/catch, so a blocked store just means the token lives for
the page) and sent on owner requests. **Sign out** in the header clears it. A 503 with `*_NOT_CONFIGURED` shows
"Server credentials not configured". Counterparty chat turns never send a credential.

For a local demo build only, `NEXT_PUBLIC_DEMO=1` prefills the dialog with the API's published `demo-owner-token`
and shows a "Demo credentials" badge. Do not set it for a deployment. Mock mode accepts any non-empty token, so the
dialog can be tried offline. Downloads (borrower file `.html` / `.docx`) are fetched with the header and saved from
an object URL, because a plain link cannot send it.

### Chat (`/chat` and the slide-over)

`POST /nl` through `lib/api.ts` (`nl`). State is in `lib/chat.ts` (one conversation per role, shared by the page and
the slide-over reachable from every page). Owner turns send the token; buyer turns (BUYER-1, BUYER-2, FASTCAPITAL)
send none. Each answer renders the intent, verdict and reason codes, plan checklist, operations (kind, status, tier,
seq, hash), clarification buttons, the Go ahead / Cancel confirmation, the "Corrected" flag and any security events
in red. A failed send keeps its `request_id`, so Retry is replay-safe; a 401 resends the turn after sign-in.
Suggested prompts are in `lib/chat-prompts.ts` (from `services/api/evals/e2e/scenarios.yaml`).

Mock mode replays replies recorded from the real API (`mocks/nl_script.json`, `lib/mock/nl.ts`). Every file in `mocks/`
is recorded, none is written by hand. To re-record all of them (the chat script, the home script, the verdicts, funding,
trajectory, what-if and the rest) start the API on port 8011 and run one command:

```
cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8011
cd apps/web && node scripts/record-mocks.mjs --api http://localhost:8011      # or: pnpm mocks:record
```

`scripts/record-mocks.mjs` resets the books and replays the demo stepper, the pages' reads and the chat prompts through the
same client code as live mode (`lib/api.ts`, `lib/live/*`), so a mock file is exactly what the live adapters return. Output is
deterministic (re-running on a fresh API leaves `git status mocks` empty); the few volatile values it normalises (the
commitment id and nonce and the hashes derived from them, what-if timings) are listed in the script header.

### Business and Demo modes

Two shells, chosen with the switch in the header and remembered in `localStorage` (`tl-mode`, `lib/mode.ts`). **Business** is
the product the owner uses: the brand FLOW 流 · AI working-capital agent, a navigation of Business sections (Home, Deals,
Attach deals, Cash & funding, Sandbox, Capex, Receivables, Activity: `BUSINESS_NAV` in `components/app-shell.tsx`; Limits
opens from the account menu), an Approvals badge that appears in the header only
while something waits for the owner (the `/approvals` route stays), one account menu (signed-in state, sign out, language, what
the data is; Sign in stays visible when signed out), one "Demo data" pill, no clock, no stepper, no mock or sample controls.
Business pages speak in distances from today ("in 12 days", `lib/when.ts` or the server's `*_when` strings), never "Day N"
(the shared plan, violation and counter cards decide this with `lib/use-business-today.ts`: the Demo views keep "Day N", a
Business page gets `whenText` and the server's `*_when` twins such as the ledger's `message_when` and a counter's `text_when`);
the reserve is the "minimum cash reserve"; authority copy is the owner's signed limits. Recent changes and Activity lead with the server's business sentence (`event_text`, with `event_detail` beside it; `GET /home` `changes[]`, `GET /ledger` operations and the act results), and the executor's own sentence, the operation id, the tier and the hashes stay behind Audit details. The account menu holds "Signed in as Owner", the language and Sign out; the header button is the avatar. The chat button is "Ask FLOW", and on a Business page `promptsFor(role, lang, pathname)` puts that page's own questions first (each one a sentence the NL rules read; `services/api/tests/nl/test_business_page_prompts.py`). **Demo** is for judges: the story page (`/demo`) with the
story's scenes (`GET /demo/story`), the clock, the scenario switch and the side doors, the story bar on every page, and the engine views (Mandate,
Inbox, Trajectory, Funding, Verdict, What-if, Capex, Ledger, Alerts, Reconciliation, Security, Evidence). Engine routes
always render the Demo shell; business routes render the Demo shell only while Demo mode is on (running a step or Reset
turns it on, so the walk through `/approvals` keeps its bar). `docs/UX_AUDIT.md` is the audit behind the split.

### Home (`/`)

The Business home is one owner read, `GET /home?lang=` (`services/api/app/api/home.py`): a status word (SAFE, WATCH,
ACTION_NEEDED, CRITICAL) with one sentence, the three figures (cash today, safe level, lowest cash ahead), the best next
action (for a reserve breach, the router's cheapest runnable plan priced all-in on the router's own convention, with every
cost line and the basis in words; the alert's own cure when the router has none, or when the cheaper plan would need
several separate approvals, in which case the cheaper option is named; `services/api/app/funding/recommend.py`), with what
the owner receives, what it costs, the day the money lands, who decides and why, what happens if nothing is done, and the
after-state read from the plan's own projection, the pending
approvals as questions, what changed in the last week, who has not paid and the next expected receipt, and the details
(funding in transit, warnings, facilities, the debt readings). Every sentence and figure is the server's; the page renders
and never computes. "Go ahead" sends the same bound act as the alerts page (`POST /alerts/{id}/act` with the state version
and the suggestions shown); when the cost is above the owner's yearly limit the server queues it and the home says it waits.
The approval cards (`/approvals`) read the queue's `presentation` fields (the question, names, cost, landing day).

The read also carries the projection behind every figure as `cash.series` (the baseline) and `cash.plan_series` (the same
books with the recommended plan applied); the Cash & funding chart draws these two series and nothing else, so it cannot
disagree with the headline, and its y axis extends below zero when a projection does. "Go ahead" sends the plan's legs as
shown; `POST /alerts/{id}/act` accepts them when they equal the plan the server recomputes (409 `ALERT_CHANGED` otherwise).

Mock mode replays summaries recorded on the demo path (`mocks/home_summary_*.json`, `lib/mock/home.ts`): the opening books,
after the day-0 fix ran, after the deal (quiet), day 34 with the late invoice, the queued fix and the approved fix.

### Documents (`/documents`)

Contract ingestion (brief 03). Read a demo document (`POST /documents {fixture_id, format}`, Markdown, Word or PDF) or upload
a file (`{kind, counterparty_id, filename, content_base64}`); the review screen (`?id=DOC-…`) highlights every clause the agent
read with `components/annotated-text.tsx` beside the term it gave, lists the fields left blank and the flags, sets a lender
agreement against the facility on the books, and labels the reading "AI-generated, for reference" until the owner confirms
or rejects it (`POST /documents/{id}/confirm|reject {doc_hash, link_facility_id?}`). Confirming is logged on the chain and
changes no books.

The demo reset opens on the three demo documents read by the agent and confirmed by the owner (the first three ledger
entries). The deal summary sits on Deals, inside "Your agreements" (`components/deals/deal-summary.tsx`, rendered by
`commitments.tsx`): once both parties have agreed a deal (the "Terms negotiated" stage done in `GET /deals`) each buyer's
agreement shows a headline, two to four facts and the one next action, with the stages, contract terms, changes, terms in
force, invoices, what is owed and the checks behind one fold, and links to the contract. A failed `GET /deals` shows the
standard error state in that section. `GET /deals`, `GET /documents` and `GET /documents/{id}` take `lang` like `GET /ledger`
and are read again when the language changes; Business pages say every "when" from the server's `*_when` string (else as a
distance from today) and keep ids, the entry number, the reader and the hash behind the Audit details fold. Confirm and reject
are irreversible and hash-bound: both buttons go dead while one is sent, a changed text (`TERMS_CHANGED`) or an earlier
decision (`ALREADY_DECIDED`) is said in words with a Reload, the facility link starts unticked, and below 1024 px the decision
card is a bar at the foot of the screen above the tab bar. `/documents` is a Business route opened from a summary and an engine view in Demo mode; Activity links each
confirmation to its contract. "Read again" on a demo document is a new reading to review and confirm or reject.

Mock mode (`lib/mock/documents.ts`) starts from the same point and serves the three demo documents as the live API left
them, read again, and that reading confirmed and rejected (`mocks/documents.json`), and the deal summary for each point of
the story (`mocks/deals_*.json`: day 0 before and after the buyer agrees, day 0 after a new reading of the supply agreement is
confirmed, then day 34 before the cure is queued, while it waits for approval and after approval). The mock marks the deal
agreed when the negotiation (Deals, the stepper) or the chat's "go ahead" agrees it, as the live books do. Any other file needs live mode.

### Live-mode notes

- The demo stepper compiles the server fixtures (`POST /offers {fixture_id}`) and passes the fixture id back
  to `/evaluate` so the owner-declared costs apply.
- Executing a funding plan changes the books, so a fresh `/router/plan` afterwards is empty. The Funding
  screen therefore shows the snapshot taken when the decision was made (`demo.funding`).
- The reworded offer (EX01B) is evaluated on the same books as EX01 before anything executes; the later
  "reworded" step only switches to it.
- The trajectory screen draws the verdict's `cured_trajectory` as the dashed "with committed cure" line; the Security
  screen reads `documents` and `summary.reply_text`; approval rows use the queue's `subject`, `tier`, `created_day`
  and `amount_display`, and a 404 or 409 on a decision refreshes the list with a plain explanation.

## Tests

`playwright.config.ts` has three projects (`PW_CHROMIUM_PATH` points them at a pre-installed Chromium when the pinned build cannot be downloaded). `desktop` and `phone` run against a mock-mode build on :3100.
`live` runs the specs its `testMatch` names (`demo`, `whatif`, `alerts`, `chat`, `contract`, `documents`, `live`, `activity`,
`trust`, `tracker` and others) against uvicorn (:8000, in-memory store, recorded LLM cache, no Supabase) and a live-mode build
on :3000. `demo.spec.ts` and `chat.spec.ts` are the same files in both
modes and asserts the same golden numbers. `contract.spec.ts` calls the live adapters from Node against the
running API. Mock and live builds use separate `NEXT_DIST_DIR`s (`.next-e2e-mock`, `.next-e2e-live`).

Counts on `dev` at `975e082f`, 17 Oct 2026 (the lead's gate, as recorded in
[`docs/deliverables/evidence/EVIDENCE_PACK.md`](../../docs/deliverables/evidence/EVIDENCE_PACK.md), section 1):

| Command | Result |
| --- | --- |
| `pnpm test:unit` | 169 passed |
| `E2E_TARGET=mock pnpm exec playwright test` (`pnpm test:e2e:mock`) | 445 passed, 0 failed |
| `E2E_TARGET=live pnpm exec playwright test` (`pnpm test:e2e:live`) | 139 passed; known failures `live.spec.ts:333` and `:347` (#157, the write-conflict retries) |

Some listed tests skip themselves; the strategy specs run only with `E2E_STRATEGY=1`.

Switches, all read by `playwright.config.ts`:

- `E2E_TARGET=mock|live|all` (default `all`): which servers start.
- `E2E_PORT` (mock, default 3100), `E2E_LIVE_PORT` (default 3000), `E2E_API_PORT` (default 8000): move the servers when
  another program holds a port. The config tells the API it starts to allow the live web origin (`CORS_ORIGINS`).
- `E2E_DATABASE_URL` (default `memory`): the `DATABASE_URL` of the API the config starts, for example
  `E2E_DATABASE_URL=sqlite:////absolute/path/e2e.db E2E_TARGET=live pnpm exec playwright test e2e/live.spec.ts`. After a run
  `sqlite3 <file> .tables` lists the tables the API created (18 after `e2e/live.spec.ts`). The specs reset the books, so the file holds the seed state
  (8 facilities, 7 counterparties, 1 mandate, 1 state) and an empty `operations` table.
- `E2E_REUSE_API=1`: the config starts no API and the live project uses the one already listening on `E2E_API_PORT`. Start
  it yourself from `services/api` with `TERMSLEDGER_NO_DOTENV=1 LLM_MODE=cache` and `CORS_ORIGINS=<the live web origin>`
  (and any `DATABASE_URL` you like; `E2E_DATABASE_URL` is ignored in this mode), for example
  `E2E_TARGET=live E2E_REUSE_API=1 E2E_LIVE_PORT=3242 E2E_API_PORT=8172 pnpm exec playwright test e2e/live.spec.ts`.
  The live web build is still started by Playwright. Without this switch the config refuses to start when something already
  listens on the API port.
- `E2E_STRATEGY=1`: builds the web app with the strategy flag and starts the API with the strategy feature flags, so the
  strategy specs run instead of skipping.

Specs that are not about sign-in import `test` from `e2e/fixtures.ts`, which pre-seeds the owner token in the live
project; `chat.spec.ts` signs in through the dialog like a user.
