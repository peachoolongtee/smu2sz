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

### Home (`/`)

The owner home answers "what needs me today". Eight cards, each reading through `lib/api.ts`: **Today** (GET `/clock` and a
labelled demo control, POST `/clock/advance {days}`), **What needs you** (POST `/nl/opener`; "Go ahead" / "Not now" send
"go ahead" / "cancel" through `lib/chat.ts` in the owner's session, so the opener and the answer also show in the chat
panel), **Position** (cash from `/state`; floor, lowest cash, month-1 DSCR and leverage and their limits from
`/trajectory`), **Your deals** (`/deals`: each buyer's confirmed contract beside the books, as in the brief-03 prototype),
**Documents the agent has read** (`/documents`), **Waiting for you** (`/approvals/queue`), **At risk** (`/alerts`, with "Let the agent fix this" on
`actionable` alerts, POST `/alerts/{id}/act`; the same button is on `/alerts`) and **Done by the agent** (`/ledger`,
`requested_by = AGENT`). Every section refetches after a clock advance or an executed action (`bump()`). The owner calls
answer 403 without the token; `ownerOn403` in `lib/live/http.ts` opens the sign-in dialog for that too.

Mock mode replays a script recorded from the real API on the demo path (`mocks/home_*.json`, `lib/mock/home.ts`): day 0 to 33
"nothing needs you"; from day 34 the opener has news and the reserve alert is actionable until it is cured.

### Documents (`/documents`)

Contract ingestion (brief 03). Read a demo document (`POST /documents {fixture_id, format}`, Markdown, Word or PDF) or upload
a file (`{kind, counterparty_id, filename, content_base64}`); the review screen (`?id=DOC-…`) highlights every clause the agent
read with `components/annotated-text.tsx` beside the term it gave, lists the fields left blank and the flags, sets a lender
agreement against the facility on the books, and labels the reading "AI-generated, for reference" until the owner confirms
or rejects it (`POST /documents/{id}/confirm|reject {doc_hash, link_facility_id?}`). Confirming is logged on the chain and
changes no books.

The demo reset opens on the three demo documents read by the agent and confirmed by the owner (the first three ledger
entries), so the home page shows the deal card at once. "Read again" on a demo document is a new reading to review and
confirm or reject.

Mock mode (`lib/mock/documents.ts`) starts from the same point and serves the three demo documents as the live API left
them, read again, and that reading confirmed and rejected (`mocks/documents.json`), and the deal card for each point of the
story (`mocks/deals_*.json`: day 0, day 0 after a new reading of the supply agreement is confirmed, then day 34 before the
cure is queued, while it waits for approval and after approval). Any other file needs live mode.

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

`playwright.config.ts` has three projects. `desktop` and `phone` run against a mock-mode build on :3100.
`live` runs `demo`, `whatif`, `alerts`, `chat`, `contract`, `documents` and `live` specs against uvicorn (:8000, in-memory store,
recorded LLM cache, no Supabase) and a live-mode build on :3000. `demo.spec.ts` and `chat.spec.ts` are the same files in both
modes and asserts the same golden numbers. `contract.spec.ts` calls the live adapters from Node against the
running API. Mock and live builds use separate `NEXT_DIST_DIR`s (`.next-e2e-mock`, `.next-e2e-live`).

Specs that are not about sign-in import `test` from `e2e/fixtures.ts`, which pre-seeds the owner token in the live
project; `chat.spec.ts` signs in through the dialog like a user.
