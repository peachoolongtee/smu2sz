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

Mock mode replays replies recorded from the real API (`mocks/nl_script.json`, `lib/mock/nl.ts`). To re-record, run
the API as above and POST each scripted text to `/nl` after `/demo/reset`.

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
`live` runs `demo`, `whatif`, `alerts`, `chat`, `contract` and `live` specs against uvicorn (:8000, in-memory store,
recorded LLM cache, no Supabase) and a live-mode build on :3000. `demo.spec.ts` and `chat.spec.ts` are the same files in both
modes and asserts the same golden numbers. `contract.spec.ts` calls the live adapters from Node against the
running API. Mock and live builds use separate `NEXT_DIST_DIR`s (`.next-e2e-mock`, `.next-e2e-live`).

Specs that are not about sign-in import `test` from `e2e/fixtures.ts`, which pre-seeds the owner token in the live
project; `chat.spec.ts` signs in through the dialog like a user.
