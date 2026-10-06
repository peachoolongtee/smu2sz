# TermsLedger web

Next.js (App Router) + TypeScript + Tailwind v4 + Recharts. The UI never computes money: it renders the
server's `*_display` strings and passes integer fen to charts for axes only (INVARIANT 13).

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

```
cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache uv run uvicorn app.main:app --port 8000
cd apps/web && NEXT_PUBLIC_API_MODE=live pnpm dev      # must be on :3000, the API's CORS allow-list
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
cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 uv run uvicorn app.main:app --port 8011
cd apps/web && node scripts/record-mocks.mjs --api http://localhost:8011      # or: pnpm mocks:record
```

`scripts/record-mocks.mjs` resets the books and replays the demo stepper, the pages' reads and the chat prompts through the
same client code as live mode (`lib/api.ts`, `lib/live/*`), so a mock file is exactly what the live adapters return. Output is
deterministic (re-running on a fresh API leaves `git status mocks` empty); the few volatile values it normalises (the
commitment id and nonce and the hashes derived from them, what-if timings) are listed in the script header.

### Business and Demo modes

Two shells, chosen with the switch in the header and remembered in `localStorage` (`tl-mode`, `lib/mode.ts`). **Business** is
the product the owner uses: a top navigation of six questions (Home, Deals, Cash & funding, Receivables, Approvals, Activity,
plus Limits), no clock, no stepper, no mock or sample controls. **Demo** is for judges: the story page (`/demo`) with the
fifteen steps, the clock, the scenario switch and the side doors, the story bar on every page, and the engine views (Mandate,
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
`live` runs `demo`, `whatif`, `alerts`, `chat`, `contract` and `live` specs against uvicorn (:8000, in-memory store,
recorded LLM cache, no Supabase) and a live-mode build on :3000. `demo.spec.ts` and `chat.spec.ts` are the same files in both
modes and asserts the same golden numbers. `contract.spec.ts` calls the live adapters from Node against the
running API. Mock and live builds use separate `NEXT_DIST_DIR`s (`.next-e2e-mock`, `.next-e2e-live`).

Specs that are not about sign-in import `test` from `e2e/fixtures.ts`, which pre-seeds the owner token in the live
project; `chat.spec.ts` signs in through the dialog like a user.
